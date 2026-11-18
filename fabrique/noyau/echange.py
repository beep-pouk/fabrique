"""Exporter et importer une session (J5, cahier § B) : un fichier .fabrique (zip) = la base de la session, copiée par l'API de SQLite, son
dossier (univers, règles, réglages, calendrier ; les vidéos seulement si demandé) et un manifeste (nom, priorité, version de Fabrique,
empreinte sha256 de chaque fichier). L'import pose un dossier neuf, jamais par-dessus une session : zip contrôlé (intégrité, aucun chemin hors
de la session, rien de plus ni de moins que le manifeste, empreintes), puis base migrée et session inscrite dans le noyau. Une erreur en route :
rien n'est inscrit et le dossier à moitié posé est rangé dans donnees\\_corbeille. La session « Essais » ne s'exporte ni ne s'importe.
Les comptes ne voyagent pas : le jeton de chaque destination est retiré de la copie (une chaîne se relie dans la session qui la publie).
Dupliquer = exporter puis importer sous un autre nom ; un modèle = un export sans vidéos ni scripts ni idées ni comptes (cahier § B, § 7.1),
d'où part une nouvelle session."""
import hashlib
import json
import os
import shutil
import sqlite3
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path

from django.conf import settings

from fabrique.garde import Refus
from fabrique.noyau import bases, routeur
from fabrique.noyau.models import Session, noter
from fabrique.session.models import Fiche

EXT = ".fabrique"
MANIFESTE, BASE = "manifeste.json", "session.sqlite3"
FORMAT = 1
CONTENUS = ("statistiquejour", "publication", "morceau", "video", "versionscript", "prevision", "script", "idee", "destination")  # vidés d'un modèle
SAUTES = {"_old", "_corbeille"}


def empreinte(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as x:
        for bloc in iter(lambda: x.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def fichiers(s: Session, videos: bool, modele: bool = False) -> dict[str, Path]:
    """Le dossier de la session, sans _old ni _corbeille ; ses vidéos seulement si demandé, et alors les finales (dossiers « final », sorties du
    montage et de la miniature) et le script de chacune, jamais les pièces intermédiaires (refaites au besoin, plan § 4.2) ; un modèle : ni
    calendrier ni scripts."""
    from fabrique.moteur import execution
    from fabrique.session.models import Morceau

    d = settings.SESSIONS / s.dossier
    finales = set()
    if videos:
        with routeur.session(s):
            finales = {execution.dossier(s, mo) for mo in Morceau.objects.filter(brique__in=("montage", "miniature"))}

    def retenu(f: Path) -> bool:
        parts = f.relative_to(d).parts
        if parts[0] != "videos":
            return not (modele and parts[0] in ("calendrier", "scripts"))
        return videos and (len(parts) == 3 or "final" in parts or any(p in finales for p in f.parents))

    return {f.relative_to(d).as_posix(): f for f in sorted(d.rglob("*"))
            if f.is_file() and not f.name.startswith(BASE) and not SAUTES & set(f.relative_to(d).parts) and retenu(f)}


def exporter(s: Session, videos: bool = False, acteur: str = "RT", modele: str = "", vider: tuple = ()) -> Path:
    if s.essais:
        raise Refus("la session « Essais » ne s'exporte pas")
    sortie = settings.RACINE / ("modeles" if modele else "exports")
    sortie.mkdir(parents=True, exist_ok=True)
    zip_ = sortie / (f"{bases.dossier_libre(modele)}{EXT}" if modele else f"{s.dossier}_{datetime.now():%Y-%m-%d_%Hh%Mm%S}{EXT}")
    if modele and zip_.exists():
        raise Refus(f"un modèle s'appelle déjà « {modele} »")
    tmp, copie = zip_.with_name(zip_.name + f".{os.getpid()}.tmp"), sortie / f".base_{os.getpid()}.sqlite3"
    try:
        bases.copier(routeur.chemin(s), copie)
        with closing(sqlite3.connect(copie)) as c:
            c.execute("UPDATE session_destination SET jeton = '', reliee = NULL, refusee = NULL")
            for table in CONTENUS if modele else vider:
                c.execute(f"DELETE FROM session_{table}")
            c.commit()
            c.execute("VACUUM")
        liste = fichiers(s, videos and not modele, modele=bool(modele))
        manifeste = {"format": FORMAT, "nom": modele or s.nom, "modele": bool(modele), "priorite": s.priorite, "version": settings.VERSION, "videos": videos, "ancien_id": s.id,
                     "empreintes": {BASE: empreinte(copie), **{rel: empreinte(f) for rel, f in liste.items()}}}
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            z.writestr(MANIFESTE, json.dumps(manifeste, ensure_ascii=False, indent=1))
            z.write(copie, BASE)
            for rel, f in liste.items():
                z.write(f, rel, compress_type=zipfile.ZIP_STORED if f.suffix.lower() in (".mp4", ".png", ".jpg", ".wav") else zipfile.ZIP_DEFLATED)
        tmp.replace(zip_)
    finally:
        tmp.unlink(missing_ok=True)
        copie.unlink(missing_ok=True)
    noter(acteur, "modele_enregistre" if modele else "session_exportee", session=s.id, fichier=zip_.name, videos=videos)
    return zip_


def dupliquer(s: Session, nom: str, acteur: str = "RT") -> Session:
    z = exporter(s, videos=False, acteur=acteur, vider=("statistiquejour", "publication"))  # une copie n'a rien publié
    try:
        return importer(z, nom, acteur)
    finally:
        z.unlink(missing_ok=True)


def modeles() -> list[dict]:
    d = settings.RACINE / "modeles"
    lus = []
    for z in sorted(d.glob(f"*{EXT}")) if d.is_dir() else []:
        try:
            with zipfile.ZipFile(z) as f:
                lus.append({"nom": lire_manifeste(f)["nom"], "fichier": z.name})
        except (Refus, zipfile.BadZipFile, OSError):  # un modèle abîmé ne cache pas les autres
            continue
    return lus


def lire_manifeste(z: zipfile.ZipFile) -> dict:
    try:
        m = json.loads(z.read(MANIFESTE))
        assert m["format"] == FORMAT and isinstance(m["empreintes"], dict) and BASE in m["empreintes"] and m["nom"].strip()
        return m
    except (KeyError, ValueError, AssertionError, AttributeError, TypeError) as e:
        raise Refus(f"ce fichier n'est pas une session exportée par Fabrique (manifeste : {e!r})") from None


def importer(fichier: Path, nom: str = "", acteur: str = "RT") -> Session:
    fichier = Path(fichier)
    try:
        z = zipfile.ZipFile(fichier)
    except (zipfile.BadZipFile, OSError) as e:
        raise Refus(f"{fichier.name} illisible : {e}") from None
    with z:
        if z.testzip() is not None:
            raise Refus(f"{fichier.name} est abîmé (contrôle d'intégrité) : rien n'est importé")
        m = lire_manifeste(z)
        membres = [x for x in z.namelist() if not x.endswith("/")]
        if hors := [x for x in membres if x.startswith("/") or "\\" in x or ":" in x or ".." in x.split("/")]:  # jamais hors du dossier de la session
            raise Refus(f"{fichier.name} contient des chemins inattendus ({', '.join(hors[:3])}) : rien n'est importé")
        if set(membres) != {MANIFESTE, *m["empreintes"]}:
            raise Refus(f"{fichier.name} ne correspond pas à son manifeste (fichiers en trop ou manquants) : rien n'est importé")
        nom = (nom or m["nom"]).strip()
        if Session.objects.filter(nom=nom).exists():
            raise Refus(f"une session s'appelle déjà « {nom} » : importer sous un autre nom")
        dossier = bases.dossier_libre(nom)
        tmp = settings.SESSIONS / f".import_{os.getpid()}_{dossier}"
        try:
            for x in membres:
                if x != MANIFESTE:
                    z.extract(x, tmp)
            if faux := [rel for rel, h in m["empreintes"].items() if empreinte(tmp / rel) != h]:
                raise Refus(f"{fichier.name} : empreinte fausse pour {', '.join(faux[:3])} : rien n'est importé")
            tmp.rename(settings.SESSIONS / dossier)
        except BaseException:
            if tmp.exists():
                shutil.move(tmp, settings.DONNEES / "_corbeille" / f"{tmp.name}_{datetime.now():%Y%m%d_%H%M%S}")
            raise
    s = Session.objects.create(nom=nom, dossier=dossier, priorite=m.get("priorite", 0))
    with routeur.session(s):
        Fiche.objects.filter(id=m.get("ancien_id", "")).update(id=s.id, nom=s.nom)  # la fiche porte l'identifiant de la session, neuf ici
    bases.preparer(s)  # base migrée au schéma de cette version
    noter(acteur, "session_importee", session=s.id, fichier=fichier.name, depuis=m.get("version"))
    return s
