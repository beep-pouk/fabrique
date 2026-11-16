"""Jetons de l'API, tirés à chaque lancement du noyau et écrits dans donnees : un jeton = un appelant = ses droits (api.DROITS). La fenêtre (et
les sous-commandes de l'app comme « arreter ») lit jeton_fenetre ; « commande » (Claude) lit jeton_claude. L'iPhone (J4) et l'assistant (J11)
auront les leurs."""
import os
import secrets
from pathlib import Path

APPELANTS: dict[str, str] = {}  # jeton -> appelant


def fichier(donnees: Path, appelant: str) -> Path:
    return Path(donnees) / f"jeton_{appelant}"


def tirer(donnees: Path):
    APPELANTS.clear()
    for appelant in ("fenetre", "claude"):
        j = secrets.token_urlsafe(32)
        APPELANTS[j] = appelant
        tmp = fichier(donnees, appelant).with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(j, encoding="ascii")
        tmp.replace(fichier(donnees, appelant))


def lire(donnees: Path, appelant: str) -> str:
    try:
        return fichier(donnees, appelant).read_text(encoding="ascii").strip()
    except OSError:
        return ""
