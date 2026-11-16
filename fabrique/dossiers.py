"""Dossiers et modes de Fabrique, sans Django (lu avant lui). Repris de Bramble Studio (core/dossiers.py), disposition simplifiée :
- installée : le code tourne dans <racine>\\programme\\app\\fabrique, à côté de <racine>\\programme\\runtime\\python312.dll ; tout ce que Fabrique
  écrit va sous <racine> (le dossier FABRIQUE : donnees, sessions, versions), jamais dans programme ; le dossier se déduit de l'emplacement du
  programme (aucune clé de registre à lire) ;
- bac à sable : programme posé par l'installateur d'essai (fichier BAC_A_SABLE dans le dossier du programme) : autre port, autre identité ;
- développement (dépôt git) : racine = variable FABRIQUE_RACINE, sinon <dépôt>\\dev (ignoré par git) ; simulation toujours."""
import os
from pathlib import Path

CODE = Path(__file__).resolve().parent  # le paquet fabrique\ du code
PORT, PORT_DEV, PORT_BAC = 8790, 8800, 8810  # API du noyau ; + 1 : sonnette de la fenêtre (instance unique). Bramble Studio garde 8765-8780


def programme(code: Path = CODE) -> Path | None:
    """Le dossier du programme installé, None en développement."""
    p = code.parent.parent
    return p if code.parent.name == "app" and (p / "runtime" / "python312.dll").is_file() else None


def bac(code: Path = CODE) -> bool:
    p = programme(code)
    return bool(p and (p / "BAC_A_SABLE").is_file())


def racine(code: Path = CODE) -> Path:
    if v := os.environ.get("FABRIQUE_RACINE"):
        return Path(v)
    p = programme(code)
    return p.parent if p else code.parent / "dev"


def donnees(r: Path | None = None) -> Path:
    """Base du noyau, journaux, jetons, état, copies _old."""
    return (r or racine()) / "donnees"


def sessions(r: Path | None = None) -> Path:
    return (r or racine()) / "sessions"


def versions(r: Path | None = None) -> Path:
    """Installateurs prêts et versions.json, posés par outils_dev\\construire.py --publier."""
    return (r or racine()) / "versions"


def port() -> int:
    """L'API du noyau : variable FABRIQUE_PORT (tests), sinon selon le mode."""
    if v := os.environ.get("FABRIQUE_PORT"):
        return int(v)
    return PORT_BAC if bac() else PORT if programme() else PORT_DEV
