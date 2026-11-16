"""« Fabrique.exe diagnostic » : contrôles du produit, en mots simples ; code de retour 0 = tout va bien. Les tests et recettes sont dans outils_dev\\."""
import ctypes
import os
import shutil
import sqlite3
from contextlib import closing

from django.conf import settings

from fabrique import dossiers, garde
from fabrique.fenetre.client import Client
from fabrique.noyau import bases, sauvegarde

PLACE_GO = 10


def eleve() -> bool:
    """Le processus a des droits d'administrateur (Fabrique n'en demande jamais)."""
    return os.name == "nt" and bool(ctypes.windll.shell32.IsUserAnAdmin())


def controles() -> list[tuple[bool, str]]:
    r = [(not any(garde.protege(d) for d in (settings.DONNEES, settings.SESSIONS, dossiers.versions(settings.RACINE))),
          "dossiers de Fabrique hors de Bramble Studio")]
    try:
        r.append((not garde.protege(d := sauvegarde.dossier()), f"dossier des sauvegardes : {d}"))
    except garde.Refus as e:
        r.append((False, str(e)))
    for rel, p in bases.bases().items():
        try:
            with closing(sqlite3.connect(f"{p.as_uri()}?mode=ro", uri=True)) as c:
                ok = c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        except sqlite3.Error:
            ok = False
        r.append((ok, f"base {rel}" + ("" if ok else " abîmée ou illisible")))
    libre = shutil.disk_usage(settings.RACINE).free / 1e9
    r.append((libre > PLACE_GO, f"{libre:.0f} Go libres sur le disque"))
    r.append((not eleve(), "sans droits d'administrateur"))
    r.append((Client().repond(), f"le noyau répond (port {dossiers.port()})"))
    return r


def jouer(ecrire=print) -> int:
    r = controles()
    for ok, texte in r:
        ecrire(f"{'ok' if ok else '!!'} {texte}")
    return 0 if all(ok for ok, _ in r) else 1
