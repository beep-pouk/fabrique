"""Les bases : copie à chaud, « migrer » (noyau puis chaque session, après une copie de chaque base dans donnees\\_old), création d'une
session (sa base et sa fiche), amorçage (session « Essais » seulement : Bramble est importée au jalon J3)."""
import re
import sqlite3
import unicodedata
from contextlib import closing
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

from fabrique.noyau import routeur
from fabrique.noyau.models import Session
from fabrique.session.models import Fiche

ESSAIS = "Essais"


def copier(source: Path, cible: Path):
    """Copie par l'API de SQLite (cohérente même base ouverte et en écriture), contrôlée : une copie abîmée lève une erreur."""
    cible.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(cible)) as dst:
        src.backup(dst)
        if (r := dst.execute("PRAGMA quick_check").fetchone()[0]) != "ok":
            raise sqlite3.DatabaseError(f"copie de {source.name} abîmée : {r}")


def bases() -> dict[str, Path]:
    """Les bases présentes sur le disque, par chemin relatif à la racine (lues sans la base du noyau : marche avant toute migration)."""
    toutes = {"donnees/noyau.sqlite3": settings.DONNEES / "noyau.sqlite3",
              **{f"sessions/{p.parent.name}/session.sqlite3": p for p in sorted(settings.SESSIONS.glob("*/session.sqlite3"))}}
    return {rel: p for rel, p in toutes.items() if p.is_file()}


def copier_bases(raison: str, quand: datetime | None = None) -> Path | None:
    """Chaque base copiée dans donnees\\_old\\<raison>_<date> ; rend ce dossier (None : aucune base encore)."""
    presentes = bases()
    if not presentes:
        return None
    dossier = settings.DONNEES / "_old" / f"{raison}_{(quand or datetime.now()):%Y%m%d_%H%M%S}"
    for rel, p in presentes.items():
        copier(p, dossier / rel)
    return dossier


def _attend(alias: str) -> bool:
    e = MigrationExecutor(connections[alias])
    return bool(e.migration_plan(e.loader.graph.leaf_nodes()))


def en_attente() -> bool:
    if _attend("default"):
        return True
    return any(_attend(routeur.ouvrir(s)) for s in Session.objects.all())


def _preparer(s: Session):
    (settings.SESSIONS / s.dossier).mkdir(parents=True, exist_ok=True)
    call_command("migrate", database=routeur.ouvrir(s), verbosity=0)
    with routeur.session(s):
        Fiche.objects.get_or_create(id=s.id, defaults={"nom": s.nom})


def creer(nom: str, essais: bool = False) -> Session:
    base = re.sub(r"[^a-z0-9]+", "_", unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()).strip("_") or "session"
    dossier, n = base, 1
    while Session.objects.filter(dossier=dossier).exists() or (settings.SESSIONS / dossier).exists():
        n += 1
        dossier = f"{base}_{n}"
    s = Session.objects.create(nom=nom, dossier=dossier, essais=essais)
    _preparer(s)
    return s


def migrer(quand: datetime | None = None) -> Path | None:
    """Copie de chaque base, puis le noyau, puis chaque session. Rend le dossier des copies."""
    settings.DONNEES.mkdir(parents=True, exist_ok=True)
    copie = copier_bases("migrer", quand)
    call_command("migrate", database="default", verbosity=0)
    if not Session.objects.exists():
        creer(ESSAIS, essais=True)
    for s in Session.objects.all():
        _preparer(s)
    return copie
