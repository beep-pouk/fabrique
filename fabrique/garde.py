"""Garde Bramble Studio : Fabrique lit Bramble Studio sans jamais écrire sous son programme, ses données, son dépôt ni son projet.
Tout ce que Fabrique écrit part d'un dossier vérifié ici : sa racine, ses données, ses sessions, ses sauvegardes, ses versions (au démarrage de
chaque processus, et à chaque réglage d'un dossier)."""
import os
from pathlib import Path

from fabrique import dossiers

PROTEGES = ("Bramble Studio", "DONNEES", "DEPOT", "PROJET")
CLE_BRAMBLE = r"Software\Bramble Studio"  # lue seulement (posée par l'installateur de Bramble Studio) : où est son studio


class Refus(Exception):
    """Un refus dit à RT, en français ; rien n'a été fait."""


def studio_bramble() -> Path | None:
    if os.name != "nt":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLE_BRAMBLE) as cle:
            return Path(winreg.QueryValueEx(cle, "Studio")[0])
    except OSError:
        return None


def interdits() -> list[Path]:
    """Les dossiers de Bramble Studio : dans son studio (registre) et à côté de la racine de Fabrique (installée dans <studio>\\FABRIQUE)."""
    studios = {s for s in (studio_bramble(), dossiers.racine().parent) if s}
    return [s / p for s in studios for p in PROTEGES]


def _norme(p: Path) -> str:
    return os.path.normcase(os.path.abspath(p))


def protege(chemin: Path) -> bool:
    c = _norme(chemin)
    return any(c == (i := _norme(d)) or c.startswith(i + os.sep) for d in interdits())


def verifier(chemin: Path) -> Path:
    if protege(chemin):
        raise Refus(f"{chemin} est un dossier de Bramble Studio : Fabrique n'y écrit jamais")
    return Path(chemin)
