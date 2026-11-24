"""Reprise de Bramble Studio dans une session (plan § 10) : « commande importer-bramble » à blanc (le rapport seulement), puis
« --pour-de-vrai ». Lecture seule : la base de Bramble est lue sur une copie (ses fichiers db et wal copiés, jamais ouverts sur place : aucun
verrou ni fichier écrit chez lui) ; les fichiers sont copiés, jamais déplacés ; rien n'est écrit sous ses dossiers (garde). Rapport : nombres,
et empreintes de la source avant et après (elle n'a pas bougé) et des copies (identiques). Rejouable tant que la session n'a rien fabriqué :
la session d'avant part dans donnees\\_old. Pas importés : la connexion YouTube (RT la refait), les rendus d'essai, les secrets."""
import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.db import connections, transaction

from fabrique import garde
from fabrique.garde import Refus
from fabrique.noyau import bases, routeur
from fabrique.noyau.models import Session, noter
from fabrique.session import models as m

FICHIERS = (  # sous le studio de Bramble → sous la session ; un dossier est copié en entier
    ("PROJET/notes/univers.json", "univers/univers.json"),
    ("PROJET/notes/langues.json", "univers/langues.json"),
    ("PROJET/BIBLE.md", "univers/BIBLE.md"),
    ("PROJET/personnages", "univers/personnages"),
    ("PROJET/voix", "univers/voix"),
    ("PROJET/notes/plan_editorial.json", "calendrier/plan_editorial.json"),
    ("PROJET/notes/registre_editorial.json", "calendrier/registre_editorial.json"),
    ("PROJET/notes/fiches_a_venir.json", "calendrier/fiches_a_venir.json"),
    ("OUTILS/production/config.json", "reglages/config.json"),
    ("OUTILS/production/regles.json", "reglages/regles.json"),
    ("DONNEES/moteur/production_textes.py", "moteur/production_textes.py"),
)
REGLES = "OUTILS/production/regles"  # REGLES_<OUTIL>.md → regles\
PARAMETRES = ("depart_chaine", "ordre_strict_le")  # et « composant_* » : où sont les outils sur ce PC ; jamais les clés ni YouTube
PERSONNAGES = "PROJET/personnages/"
DIFFERENCE = ("Chaque épisode a son propre scénario, écrit pour lui, et le héros, l'ami et le lieu de sa fiche du calendrier éditorial "
              "(repris de Bramble Studio ; à préciser dans Règles).")  # le garde-fou de « Fabriquer » (session/reglages.py)


def studio() -> Path:
    s = garde.studio_bramble()
    if s is None or not (s / "DONNEES" / "studio.db").is_file():
        raise Refus("Bramble Studio n'est pas installé ici (sa base est introuvable) : rien à importer")
    return s


def lire_base(source: Path, dossier: Path) -> sqlite3.Connection:
    """La base de Bramble, copiée (db puis wal, recommencé si le wal a bougé pendant) et ouverte dans `dossier`, contrôlée."""
    wal = source.with_name(source.name + "-wal")
    marque = lambda: (wal.stat().st_size, wal.stat().st_mtime_ns) if wal.is_file() else None  # noqa: E731
    for _ in range(5):
        avant = marque()
        shutil.copyfile(source, dossier / "studio.db")
        if wal.is_file():
            shutil.copyfile(wal, dossier / "studio.db-wal")
        if marque() == avant:
            break
    else:
        raise Refus("la base de Bramble Studio change sans cesse pendant sa copie (il écrit) : rien n'est importé, réessayer dans un instant")
    c = sqlite3.connect(dossier / "studio.db")
    if (r := c.execute("PRAGMA quick_check").fetchone()[0]) != "ok":
        c.close()
        raise Refus(f"la copie de la base de Bramble Studio est abîmée ({r}) : rien n'est importé, réessayer")
    c.row_factory = sqlite3.Row
    return c


def lignes(c: sqlite3.Connection, requete: str) -> list[dict]:
    return [dict(r) for r in c.execute(requete)]


def quand(texte) -> datetime:
    d = datetime.fromisoformat(texte) if texte else datetime(2026, 1, 1)
    return d if d.tzinfo else d.replace(tzinfo=UTC)  # Bramble Studio range ses dates en UTC


def jour(texte) -> date | None:
    return date.fromisoformat(texte[:10]) if texte else None


def charge(texte, defaut):
    return json.loads(texte) if texte else defaut


def sources(s: Path, langues: list[dict]) -> dict[str, Path]:
    """Chaque fichier à copier : destination relative à la session → source."""
    r: dict[str, Path] = {}
    for src, dst in FICHIERS:
        p = s / src
        if p.is_dir():
            r.update({f"{dst}/{f.relative_to(p).as_posix()}": f for f in sorted(p.rglob("*")) if f.is_file()})
        elif p.is_file():
            r[dst] = p
    r.update({f"regles/{f.name}": f for f in sorted((s / REGLES).glob("REGLES_*.md"))})
    for l in langues:  # la voix de référence d'une langue, sous le studio (les poids des modèles restent dans le dossier des modèles)
        if (ref := charge(l["reglages_voix"], {}).get("ref")) and (s / ref).is_file():
            r[f"univers/voix_langues/{l['code']}/{Path(ref).name}"] = s / ref
    return r


def empreinte(fichiers: dict[str, Path]) -> str:
    h = hashlib.sha256()
    for rel, f in sorted(fichiers.items()):
        h.update(rel.encode())
        with open(f, "rb") as lu:
            while bloc := lu.read(1 << 20):
                h.update(bloc)
    return h.hexdigest()


def lire(c: sqlite3.Connection) -> dict:
    """Ce qui est importé de la base (sans les connexions YouTube ni les secrets)."""
    personnages = {p["id"]: p for p in lignes(c, "select * from core_personnage")}
    lieux = {l["id"]: l for l in lignes(c, "select * from core_lieu")}
    nom = lambda table, i: table[i]["nom"] if i in table else ""  # noqa: E731
    episodes = lignes(c, "select * from core_episode order by code")
    fiches_episodes = {e["fiche_id"]: e["code"] for e in episodes if e["fiche_id"]}
    return {
        "nom": (lignes(c, "select nom from core_chaine order by id") or [{"nom": "Bramble"}])[0]["nom"],
        "episodes": episodes,
        "versions": lignes(c, "select v.*, e.code from core_scenarioversion v join core_episode e on e.id = v.episode_id order by e.code, v.numero"),
        "fiches": [{**f, "heros": nom(personnages, f["heros_id"]), "camee": nom(personnages, f["camee_id"]), "lieu": nom(lieux, f["lieu_id"]),
                    "episode": fiches_episodes.get(f["id"], "")} for f in lignes(c, "select * from core_fiche order by date_prevue, id")],
        "idees": lignes(c, "select * from core_idee order by id"),
        "personnages": list(personnages.values()),
        "lieux": list(lieux.values()),
        "references": lignes(c, "select * from core_reference order by id"),
        "langues": lignes(c, "select * from core_langue order by ordre, code"),
        "ressources": [{**r, "type": "musique"} for r in lignes(c, "select * from core_musique order by id")]
                      + [{**r, "type": "voix"} for r in lignes(c, "select * from core_voix order by id")],
        "parametres": {p["cle"]: p["valeur"] for p in lignes(c, "select cle, valeur from core_parametre")
                       if p["cle"] in PARAMETRES or p["cle"].startswith("composant_")},
    }


def ecrire(s: Session, d: dict, studio_: Path) -> list[str]:
    """Les lignes de la base de la session ; rend les remarques (ce qui a été ajusté)."""
    remarques = []
    with routeur.session(s), transaction.atomic(using=routeur.ouvrir(s)):
        scripts = {}
        for e in d["episodes"]:
            scripts[e["code"]] = m.Script.objects.create(
                code=e["code"], titre=e["titre"], langue=e["langue"], statut=e["statut"], date_prevue=jour(e["date_prevue"]),
                details={k: e[k] for k in ("compilation", "duree", "mots", "note_finale", "date_fabrique", "date_publie")} | {"compilation": charge(e["compilation"], [])})
        for v in d["versions"]:
            m.VersionScript.objects.create(script=scripts[v["code"]], numero=v["numero"], auteur=v["auteur"], date=quand(v["date"]),
                                           contenu=charge(v["contenu"], {}), validee=bool(v["validee"]), regles=charge(v["resultat_regles"], {}))
        for code, sc in scripts.items():  # le fichier du projet, s'il diffère de la dernière version (modifié hors de l'app) : une version de plus
            fichier = next((f for f in sorted((studio_ / "PROJET" / "scenarios").glob(f"*-{code}.json"))), None)
            derniere = sc.versions.order_by("-numero").first()
            if fichier and (contenu := json.loads(fichier.read_text(encoding="utf-8-sig"))) != (derniere.contenu if derniere else None):
                m.VersionScript.objects.create(script=sc, numero=(derniere.numero if derniere else 0) + 1, auteur="fichier", date=quand(None), contenu=contenu)
                remarques.append(f"{code} : le fichier du projet diffère de sa dernière version, gardé comme version de plus")
        for f in d["fiches"]:
            m.Prevision.objects.create(date=jour(f["date_prevue"]), statut=f["statut"],
                                       details={k: f[k] for k in ("type", "evenement", "obstination", "fait_nature", "saison", "heros", "camee", "lieu", "episode")})
        for i in d["idees"]:
            m.Idee.objects.create(titre=i["titre"], resume=i["resume"], source=i["source"], tags=charge(i["tags"], []), statut=i["statut"], creee=quand(i["creee"]))
        persos = {}
        for p in d["personnages"]:
            persos[p["id"]] = m.Personnage.objects.create(nom=p["nom"], role=p["role"], statut=p["statut"], details={
                k: p[k] for k in ("espece", "description", "vetements", "yeux", "date_statut", "plafond_references")})
        for lieu in d["lieux"]:
            m.Lieu.objects.create(nom=lieu["nom"], description=lieu["description"])
        hors = 0
        for r in d["references"]:
            fichier = r["fichier"].replace("\\", "/")
            if fichier.startswith(PERSONNAGES):
                fichier = "univers/personnages/" + fichier[len(PERSONNAGES):]
            else:
                hors += 1
            m.Reference.objects.create(personnage=persos[r["personnage_id"]], fichier=fichier, vue=r["vue"], source=r["source"], validee=bool(r["validee"]),
                                       verifiee=bool(r["verifiee"]), date=quand(r["date"]))
        if hors:
            remarques.append(f"{hors} référence(s) hors des dossiers des personnages : chemin gardé tel quel")
        for l in d["langues"]:
            reglages = charge(l["reglages_voix"], {})
            if ref := reglages.get("ref"):
                reglages["ref"] = f"univers/voix_langues/{l['code']}/{Path(ref).name}"
            m.Langue.objects.create(code=l["code"], nom=l["nom"], ordre=l["ordre"], rtl=bool(l["rtl"]), police=l["police"], voix_validee=bool(l["voix_validee"]),
                                    outil_voix=l["outil_voix"], reglages_voix=reglages, raison=l["raison"], note=l["note"] or "", preselectionnee=bool(l["preselectionnee"]))
        for r in d["ressources"]:
            m.Ressource.objects.create(type=r["type"], nom=r["nom"], consigne=r["consigne"] or "", outil=r["outil"] or "", licence=r["licence"] or "",
                                       credit=r["credit"] or "", verrouillee=bool(r["verrouillee"]))
        for cle, valeur in (("origine", "bramble"), ("formats", '["F1"]'), ("format", "F1"), ("assistant", "fini"), ("difference", DIFFERENCE)):
            m.Reglage.objects.update_or_create(cle=cle, defaults={"valeur": valeur})
    return remarques


def importer(pour_de_vrai: bool = False, acteur: str = "claude", studio_: Path | None = None) -> dict:
    s0 = studio_ or studio()
    with tempfile.TemporaryDirectory(prefix="fabrique_import_") as t:
        with closing(lire_base(s0 / "DONNEES" / "studio.db", Path(t))) as c:
            d = lire(c)
    fichiers = sources(s0, d["langues"])
    avant = empreinte(fichiers)
    rapport = {"a_blanc": not pour_de_vrai, "session": d["nom"], "date": datetime.now().isoformat(timespec="seconds"),
               "base": {k: len(d[k]) for k in ("episodes", "versions", "fiches", "idees", "personnages", "lieux", "references", "langues", "ressources")},
               "fichiers": {"nombre": len(fichiers), "mo": round(sum(f.stat().st_size for f in fichiers.values()) / 1e6, 1)},
               "empreinte_source": avant, "remarques": []}
    if pour_de_vrai:
        s, copies, rapport["remarques"] = vraiment(d, fichiers, s0, acteur)
        rapport |= {"dossier": s.dossier, "copies_identiques": copies == avant, "source_intacte": empreinte(fichiers) == avant}
        (settings.SESSIONS / s.dossier / "import_bramble.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    return rapport


def ranger(s: Session, raison: str):
    """Une session de l'import (la précédente, ou une ratée) rangée dans donnees\\_old, sa ligne retirée."""
    connections[routeur.ouvrir(s)].close()
    garde.verifier(cible := settings.DONNEES / "_old" / f"{raison}_{datetime.now():%Y%m%d_%H%M%S}" / s.dossier)
    cible.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(settings.SESSIONS / s.dossier, cible)
    except OSError as e:
        raise Refus(f"la session « {s.nom} » est ouverte ailleurs ({e.__class__.__name__}) : arrêter Fabrique (Système) puis rejouer l'import") from e
    s.delete()


def vraiment(d: dict, fichiers: dict[str, Path], s0: Path, acteur: str) -> tuple[Session, str, list[str]]:
    """La session (remplacée si un import précédent n'a rien fabriqué), ses fichiers, sa base ; rend la session, l'empreinte des copies, les
    remarques."""
    ancienne = Session.objects.filter(nom=d["nom"]).first()
    if ancienne:
        with routeur.session(ancienne):
            if m.Reglage.objects.filter(cle="origine", valeur="bramble").count() != 1:
                raise Refus(f"une session « {ancienne.nom} » existe déjà et ne vient pas de l'import : rien n'est remplacé")
            if m.Video.objects.exists():
                raise Refus(f"la session « {ancienne.nom} » a déjà fabriqué : l'import ne se rejoue plus")
            if ecrites := m.VersionScript.objects.exclude(auteur__in=("import", "fichier")).count():
                raise Refus(f"{ecrites} version(s) de script écrite(s) dans Fabrique depuis l'import : il ne se rejoue plus (elles seraient perdues)")
        ranger(ancienne, "import")
    s = bases.creer(d["nom"])
    try:
        racine = garde.verifier(settings.SESSIONS / s.dossier)
        for rel, f in fichiers.items():
            (racine / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, racine / rel)
        (racine / "reglages" / "parametres_bramble.json").write_text(json.dumps(d["parametres"], ensure_ascii=False, indent=1), encoding="utf-8")
        remarques = ecrire(s, d, s0)
    except Exception as e:  # un import raté ne laisse pas une session à moitié faite (le rejouer resterait refusé) : elle part dans _old
        ranger(s, "import_rate")
        if isinstance(e, (KeyError, ValueError)):
            raise Refus(f"données de Bramble Studio inattendues ({type(e).__name__} : {e}) : rien n'est importé") from e
        raise
    noter(acteur, "import_bramble", session=s.id, fichiers=len(fichiers), remplace=bool(ancienne))
    return s, empreinte({rel: racine / rel for rel in fichiers}), remarques


def rendus_bramble() -> Path | None:
    """Le dossier des rendus de Bramble Studio (lecture seule : l'interface y montre ses images et ses vidéos), None sans Bramble."""
    s = garde.studio_bramble()
    return s / "PROJET" / "rendus" if s and (s / "PROJET" / "rendus").is_dir() else None


def duree_wav(f: Path) -> float:
    """Secondes d'un .wav, PCM ou flottant (le module wave refuse le flottant des voix de Bramble) ; 0 s'il est illisible ou vide. La taille
    annoncée est bornée par celle du fichier : un wav tronqué ou en cours d'écriture (en-tête provisoire) ne s'allonge pas."""
    try:
        taille_fichier = f.stat().st_size
        with f.open("rb") as h:
            if h.read(12)[8:] != b"WAVE":
                return 0.0
            debit = 0
            while len(t := h.read(8)) == 8:
                nom, taille = t[:4], int.from_bytes(t[4:], "little")
                if nom == b"data":
                    return round(min(taille, taille_fichier - h.tell()) / debit, 2) if debit else 0.0
                bloc = h.read(taille + (taille & 1))
                if nom == b"fmt ":
                    debit = int.from_bytes(bloc[8:12], "little")  # octets par seconde
    except OSError:
        pass
    return 0.0


def rendus(code: str, langue: str = "en") -> dict:
    """Ce que Bramble a rendu pour ce script, toutes langues et reprises : images des plans, vidéos finies, et la voix de `langue` scène par
    scène. Image du plan n : plan_NNN.png (n = première scène du plan), la plus récente ; vidéo : la plus récente de final par langue ;
    voix : voix\\sNNN.wav la plus récente, et sa durée (le vrai rythme des plans) ; langues : celles qui ont des voix."""
    r = rendus_bramble()
    dossiers_ = [d for d in r.iterdir() if d.is_dir() and re.fullmatch(rf"\d{{4}}-\d\d-\d\d-{re.escape(code)}([._].+)?", d.name)] if r else []
    images: dict[int, Path] = {}
    videos: dict[str, Path] = {}
    voix: dict[int, Path] = {}
    langues: set[str] = set()
    plus_recent = lambda f, g: g is None or f.stat().st_mtime > g.stat().st_mtime  # noqa: E731
    for d in dossiers_:
        for f in (d / "images").glob("plan_[0-9][0-9][0-9].png"):
            if plus_recent(f, images.get(n := int(f.stem[5:]))):
                images[n] = f
        l = m_[1] if (m_ := re.search(r"\.([A-Za-z-]+)$", d.name)) else "en"
        for f in (d / "final").glob("*.mp4"):
            if plus_recent(f, videos.get(l)):
                videos[l] = f
        for f in (d / "voix").glob("s[0-9][0-9][0-9].wav"):
            langues.add(l)
            if l == langue and plus_recent(f, voix.get(n := int(f.stem[1:]))):
                voix[n] = f
    return {"images": {n: str(f) for n, f in sorted(images.items())}, "videos": [{"langue": l, "chemin": str(f)} for l, f in sorted(videos.items())],
            "langues": sorted(langues), "voix": {n: str(f) for n, f in sorted(voix.items())}, "durees": {n: duree_wav(f) for n, f in sorted(voix.items())}}


def en_cours(maintenant: datetime | None = None) -> dict | None:
    """Ce que Bramble Studio fabrique en ce moment (son DONNEES\etat.json, lu seulement ; plus de 15 min : arrêté) : script, langue, étape,
    minutes restantes en tout (son total_min ; son reste_min n'est que celui de l'étape), avancée de l'étape (plans faits / tous, s'il les
    compte) et l'image du plan qu'il traite (celle que nomme la dernière ligne de son journal, sinon la plus récente)."""
    s = garde.studio_bramble()
    try:
        e = json.loads((s / "DONNEES" / "etat.json").read_text(encoding="utf-8-sig")) if s else {}
        if (maintenant or datetime.now()) - datetime.fromisoformat(e["heure"]) > timedelta(minutes=15):
            return None
        ep = e.get("episode") or {}
        nom = str(ep["nom"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    images = s / "PROJET" / "rendus" / nom / "images"
    n = re.search(r"plan_(\d{3})", str(ep.get("journal_derniere", "")))
    image = images / f"plan_{n[1]}.png" if n else None
    if not (image and image.is_file()):
        image = max(images.glob("plan_[0-9][0-9][0-9].png"), key=lambda f: f.stat().st_mtime, default=None)
    code = m_[1] if (m_ := re.fullmatch(r"\d{4}-\d\d-\d\d-([^._]+).*", nom)) else nom
    etape = str(ep.get("etape", ""))
    fait, tout = {"images": ("images", "plans"), "anim": ("anim", "plans"), "bramble": ("bramble", "nbr")}.get(etape, ("", ""))
    return {"code": code, "langue": m_[1] if (m_ := re.search(r"\.([A-Za-z-]+)$", nom)) else "en", "etape": etape,
            "reste_min": ep.get("total_min"), "fait": ep.get(fait), "tout": ep.get(tout), "image": str(image) if image else ""}
