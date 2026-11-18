"""Exporter et importer une session (J5, cahier § B) : un fichier .fabrique (zip) = la base de la session, copiée par l'API de SQLite, son
dossier (univers, règles, réglages, calendrier ; les vidéos seulement si demandé) et un manifeste (nom, priorité, version de Fabrique,
empreinte sha256 de chaque fichier). L'import pose un dossier neuf, jamais par-dessus une session : zip contrôlé (intégrité, aucun chemin hors
de la session, rien de plus ni de moins que le manifeste, empreintes), puis base migrée et session inscrite dans le noyau. Une erreur en route :
rien n'est inscrit et le dossier à moitié posé est rangé dans donnees\\_corbeille. La session « Essais » ne s'exporte ni ne s'importe."""
import hashlib
import json
import os
import shutil
import zipfile
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
SAUTES = {"_old", "_corbeille"}


def empreinte(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as x:
        for bloc in iter(lambda: x.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def fichiers(s: Session, videos: bool) -> dict[str, Path]:
    d = settings.SESSIONS / s.dossier
    return {f.relative_to(d).as_posix(): f for f in sorted(d.rglob("*"))
            if f.is_file() and not f.name.startswith(BASE) and not SAUTES & set(f.relative_to(d).parts) and (videos or f.relative_to(d).parts[0] != "videos")}


def exporter(s: Session, videos: bool = False, acteur: str = "RT") -> Path:
    if s.essais:
        raise Refus("la session « Essais » ne s'exporte pas")
    sortie = settings.RACINE / "exports"
    sortie.mkdir(parents=True, exist_ok=True)
    zip_ = sortie / f"{s.dossier}_{datetime.now():%Y-%m-%d_%Hh%Mm%S}{EXT}"
    tmp, copie = zip_.with_name(zip_.name + f".{os.getpid()}.tmp"), sortie / f".base_{os.getpid()}.sqlite3"
    try:
        bases.copier(routeur.chemin(s), copie)
        liste = fichiers(s, videos)
        manifeste = {"format": FORMAT, "nom": s.nom, "priorite": s.priorite, "version": settings.VERSION, "videos": videos, "ancien_id": s.id,
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
    noter(acteur, "session_exportee", session=s.id, fichier=zip_.name, videos=videos)
    return zip_


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
