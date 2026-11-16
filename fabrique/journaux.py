"""Journaux (repris de Bramble Studio, core/journaux.py) : un fichier par processus dans donnees\\journaux, secrets masqués avant écriture,
gros journal mis de côté au démarrage, journaux de plus de 14 jours effacés ; lecture des avertissements et erreurs pour Système."""
import logging
import re
import time
from datetime import datetime
from pathlib import Path

SECRETS = re.compile(r"ya29\.[\w.-]+|1//[\w-]+|GOCSPX-[\w-]+|sk-ant-[\w-]+|AIza[\w-]{30,}|(?<=upload_id=)[\w-]+|(?<=Bearer )[\w.-]+")
GROS = 5_000_000  # octets : au-delà, le journal est mis de côté au démarrage (une erreur en boucle l'a gonflé)
JOURS = 14
LIGNE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ (WARNING|ERROR|CRITICAL) (\S+) : (.*)")
MOTS = {"WARNING": "à surveiller", "ERROR": "problème", "CRITICAL": "problème"}
LIMITE = 2_000_000  # octets lus par journal (la fin) : un journal énorme ne gèle pas l'écran


def masquer(texte: str) -> str:
    return SECRETS.sub("[masqué]", texte)


class Masque(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return masquer(super().format(record))


def tourner(journal: Path, maintenant: datetime | None = None):
    """Un journal trop gros est rangé sous <nom>.log.<date>.<heure> (les 3 derniers gardés) ; tenu par un autre processus : laissé."""
    try:
        if journal.stat().st_size > GROS:
            journal.rename(journal.with_name(f"{journal.name}.{maintenant or datetime.now():%Y-%m-%d.%H%M%S}"))
            for vieux in sorted(journal.parent.glob(f"{journal.name}.????-??-??.??????"))[:-3]:
                vieux.unlink()
    except OSError:
        pass


def elaguer(dossier: Path, maintenant: float | None = None) -> int:
    """Les journaux du dossier que personne n'a écrits depuis 14 jours sont effacés."""
    limite, n = (maintenant or time.time()) - JOURS * 86400, 0
    for f in dossier.glob("*.log*"):
        try:
            if f.is_file() and f.stat().st_mtime < limite:
                f.unlink()
                n += 1
        except OSError:  # tenu par un autre processus : laissé
            pass
    return n


def configurer(dossier: Path, role: str):
    """Au démarrage d'un processus : journal <rôle>.log, avertissements et plus seulement pour les bibliothèques."""
    dossier.mkdir(parents=True, exist_ok=True)
    tourner(dossier / f"{role}.log")
    elaguer(dossier)
    h = logging.FileHandler(dossier / f"{role}.log", encoding="utf-8")
    h.setFormatter(Masque("%(asctime)s %(levelname)s %(name)s : %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[h], force=True)
    for bruit in ("waitress", "django"):
        logging.getLogger(bruit).setLevel(logging.WARNING)


def _fin(f: Path) -> str:
    with open(f, "rb") as h:
        h.seek(max(0, f.stat().st_size - LIMITE))
        return h.read().decode("utf-8", errors="replace")


def recents(dossier: Path, n: int = 30) -> list[dict]:
    """Avertissements et erreurs des journaux, les plus récents d'abord."""
    r = [{"date": m[1], "niveau": MOTS[m[2]], "source": f.stem, "message": masquer(m[4])[:300]}
         for f in sorted(dossier.glob("*.log")) for ligne in _fin(f).splitlines() if (m := LIGNE.match(ligne))]
    return sorted(r, key=lambda x: x["date"], reverse=True)[:n]
