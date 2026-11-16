"""Sauvegarde et restauration (repris de Bramble Studio, core/sauvegarde.py). Un zip daté : la base du noyau, la base et les textes de chaque
session ; 30 jours gardés. Dossier : réglage « sauvegardes » ; sinon, installée chez RT, celui de Bramble Studio (son réglage, lu sans rien
écrire) + \\fabrique ; sinon <racine>\\sauvegardes. Restaurer : l'état du moment part d'abord dans donnees\\_old, puis chaque base est remise
en place par l'API de SQLite (le noyau peut tourner), chaque texte remplacé."""
import os
import re
import shutil
import sqlite3
import zipfile
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.db import connections

from fabrique import dossiers, garde
from fabrique.garde import Refus
from fabrique.noyau import bases
from fabrique.noyau.models import Parametre

GARDER_JOURS = 30
TEXTES = (".json", ".md", ".txt")
NOM = "fabrique_%Y-%m-%d_%Hh%Mm%S.zip"
MEMBRE = re.compile(r"donnees/noyau\.sqlite3|sessions/[\w-]+/[^:\\]+")  # rien d'autre ne sort d'un zip de Fabrique


def bramble() -> Path | None:
    """Installée chez RT (pas le bac à sable) : le dossier des sauvegardes de Bramble Studio + \\fabrique. Sa base est ouverte immuable : ni
    verrou, ni fichier à côté, aucune écriture."""
    if not dossiers.programme() or dossiers.bac():
        return None
    base = (garde.studio_bramble() or settings.RACINE.parent) / "DONNEES" / "studio.db"
    try:
        with closing(sqlite3.connect(f"{base.as_uri()}?mode=ro&immutable=1", uri=True)) as c:
            r = c.execute("select valeur from core_parametre where cle = 'sauvegardes'").fetchone()
    except (sqlite3.Error, ValueError):
        return None
    return Path(r[0]) / "fabrique" if r and r[0] else None


def dossier() -> Path:
    v = Parametre.lire("sauvegardes")
    return garde.verifier(Path(v) if v else bramble() or settings.RACINE / "sauvegardes")


def date(z: Path) -> datetime | None:
    try:
        return datetime.strptime(z.name, NOM)
    except ValueError:
        return None


def lister(d: Path | None = None) -> list[Path]:
    """Les sauvegardes, la plus récente d'abord."""
    d = d or dossier()
    return sorted((z for z in d.glob("fabrique_*.zip") if date(z)), key=date, reverse=True) if d.is_dir() else []


def elaguer(d: Path, maintenant: datetime) -> list[Path]:
    """Les sauvegardes de plus de 30 jours partent ; la plus récente reste toujours. Un zip verrouillé reste (réessayé le lendemain)."""
    partis = []
    for z in lister(d)[1:]:
        if date(z) < maintenant - timedelta(days=GARDER_JOURS):
            try:
                z.unlink()
                partis.append(z)
            except OSError:
                pass
    return partis


def sauvegarder(quand: datetime | None = None) -> Path:
    quand = quand or datetime.now()
    d = dossier()
    d.mkdir(parents=True, exist_ok=True)
    zip_ = d / quand.strftime(NOM)
    tmp, travail = zip_.with_name(f"{zip_.name}.{os.getpid()}.tmp"), d / f".copies_{os.getpid()}"
    try:  # écrit à part puis renommé : un zip interrompu (disque plein) ne compte jamais parmi les sauvegardes
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for rel, p in bases.bases().items():
                bases.copier(p, travail / rel)
                z.write(travail / rel, rel)
            for f in sorted(settings.SESSIONS.rglob("*")):
                rel = f.relative_to(settings.RACINE)
                if f.is_file() and f.suffix in TEXTES and not {"_old", "_corbeille"} & set(rel.parts):
                    z.write(f, rel.as_posix())
        tmp.replace(zip_)
    finally:
        tmp.unlink(missing_ok=True)
        shutil.rmtree(travail, ignore_errors=True)
    elaguer(d, quand)
    return zip_


def intacte(z: Path) -> bool:
    try:
        with zipfile.ZipFile(z) as f:
            return f.testzip() is None
    except (zipfile.BadZipFile, OSError):
        return False


def restaurer(nom: str, quand: datetime | None = None) -> str:
    z = dossier() / nom
    if Path(nom).name != nom or not date(z) or not z.is_file():
        raise Refus(f"sauvegarde inconnue : {nom}")
    if not intacte(z):
        raise Refus(f"{nom} est abîmée (contrôle d'intégrité) : rien n'est restauré")
    with zipfile.ZipFile(z) as f:
        membres = [m for m in f.namelist() if not m.endswith("/")]
        if hors := [m for m in membres if not MEMBRE.fullmatch(m) or ".." in m.split("/")]:
            raise Refus(f"{nom} contient des chemins inattendus ({', '.join(hors[:3])}) : rien n'est restauré")
        old = settings.DONNEES / "_old" / f"restauration_{(quand or datetime.now()):%Y%m%d_%H%M%S}"
        for m in membres:  # d'abord, tout l'état du moment
            dest = garde.verifier(settings.RACINE / m)
            if dest.is_file():
                (bases.copier if m.endswith(".sqlite3") else _copier)(dest, old / m)
        connections.close_all()
        for m in membres:
            dest = settings.RACINE / m
            dest.parent.mkdir(parents=True, exist_ok=True)
            f.extract(m, old / "_zip")
            if m.endswith(".sqlite3"):
                bases.copier(old / "_zip" / m, dest)  # dans la base vivante : le noyau la relit telle quelle
            else:
                shutil.copy2(old / "_zip" / m, dest)
        shutil.rmtree(old / "_zip")
    return f"{nom} restaurée ; l'état d'avant est gardé dans {old}"


def _copier(source: Path, cible: Path):
    cible.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, cible)
