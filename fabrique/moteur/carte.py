"""Verrou de la carte (plan § 5.4), vérifié avant chaque tâche lourde : 1) une seule des nôtres à la fois, et aucune pendant l'installation d'un outil ; 2) Bramble Studio ne fabrique rien
(son DONNEES\\etat.json, lu sans jamais l'écrire : il le réécrit au moins chaque minute, un état de plus de 15 min veut dire qu'il est arrêté ;
récent mais illisible : on attend ; seule une tâche d'épisode compte, ses autres tâches lourdes (analyses) sont vues par la règle 3) ;
3) aucun autre gros programme sur la carte (nvidia-smi : utilisation d'au moins 50 %, le seuil de Bramble Studio, ou la moitié de sa mémoire
prise, par exemple un modèle de langue chargé). Rend la raison en clair ; vide : libre. nvidia-smi muet : non bloquant (repris de Bramble
Studio, core/pipeline/machine.py et core/pilotage.py)."""
import json
import subprocess
from datetime import datetime, timedelta

from fabrique import garde
from fabrique.noyau import taches

SEUIL_PCT = 50
FRAIS = timedelta(minutes=15)
REQUETE = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"]


def bramble(maintenant: datetime) -> str:
    for studio in garde.studios():
        f = studio / "DONNEES" / "etat.json"
        try:
            if maintenant - datetime.fromtimestamp(f.stat().st_mtime) > FRAIS:
                continue
            e = json.loads(f.read_text(encoding="utf-8-sig"))
            if maintenant - datetime.fromisoformat(e["heure"]) > FRAIS:
                continue
        except FileNotFoundError:
            continue
        except (OSError, ValueError, KeyError, TypeError):  # récent mais illisible : Bramble Studio le réécrit à cet instant
            return "l'état de Bramble Studio est illisible pour l'instant"
        tache = e.get("tache") or {}
        if e.get("episode") or tache.get("episode"):
            return f"Bramble Studio fabrique ({tache.get('nom') or 'un épisode'})"
    return ""


def gpu() -> tuple[float, float, float] | None:
    """(utilisation %, mémoire utilisée Mio, mémoire totale Mio) ; None si nvidia-smi ne répond pas."""
    try:
        r = subprocess.run(REQUETE, capture_output=True, text=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        u, utilisee, totale = (float(x) for x in r.stdout.strip().splitlines()[0].split(","))
        return u, utilisee, totale
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def autre_programme() -> str:
    g = gpu()
    if g and (g[0] >= SEUIL_PCT or g[1] >= g[2] / 2):
        return "un autre programme occupe la carte"  # texte stable : la raison est réécrite seulement quand elle change
    return ""


def occupee(maintenant: datetime | None = None) -> str:
    return ("une fabrication est déjà en cours" if taches.occupe("fabrication") else "") or ("un essai d'animation est en cours" if taches.occupe("animation") else "") or ("un outil s'installe" if taches.occupe("installation") else "") or bramble(maintenant or datetime.now()) or autre_programme()
