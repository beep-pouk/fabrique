"""Les tâches détachées du noyau (« executer <tâche> ») : la sauvegarde (le soir à 23 h 30, ou au clic de RT), tâche légère, et la fabrication
d'une vidéo de la file (moteur/file.py), tâche lourde. L'état de chacune est un fichier (donnees\\taches\\<tâche>.json) : lu par le noyau, par
« libre » (installateur) et par Claude, sans la base. Sans Django en tête de module : « libre » le lit sans le démarrer."""
import json
import logging
import os
from datetime import datetime, timedelta

from fabrique import dossiers, programme

log = logging.getLogger(__name__)
TACHES = ("sauvegarde", "fabrication")
DEMARRAGE_S = 60  # lancée, pas encore de pid (le relais démarre l'exécuteur) : comptée comme en cours
HEURE_SAUVEGARDE = (23, 30)


def fichier(nom: str = "sauvegarde"):
    return dossiers.donnees() / "taches" / f"{nom}.json"


def lire(nom: str = "sauvegarde") -> dict:
    try:
        return json.loads(fichier(nom).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ecrire(nom: str, etat: dict):
    f = fichier(nom)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(etat, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def vivante(e: dict) -> bool:
    if e.get("etat") != "en_cours":
        return False
    if pid := int(e.get("pid", 0)):
        return programme.de_l_app(pid)
    try:
        return (datetime.now() - datetime.fromisoformat(e.get("lancee", ""))).total_seconds() < DEMARRAGE_S
    except ValueError:
        return False


def occupe(*noms: str) -> str:
    """Ce qui tourne parmi `noms` (toutes par défaut ; vide : rien) ; une tâche « en cours » dont le processus est mort ne compte pas."""
    return next((nom for nom in noms or TACHES if vivante(lire(nom))), "")


def lancer(nom: str, acteur: str) -> str:
    """Lance la tâche détachée (elle survit à l'arrêt du noyau) ; refus si elle tourne déjà."""
    from fabrique.garde import Refus
    from fabrique.noyau.models import noter

    if occupe(nom):
        raise Refus(f"la {nom} est déjà en cours")
    programme.lancer_detache("executer", nom, journal=dossiers.donnees() / "journaux" / f"sortie_{nom}.log")
    noter(acteur, nom, quoi="lancée")
    return "Sauvegarde lancée : une notification dira quand elle est finie."


def due(derniere: str, maintenant: datetime) -> bool:
    """La sauvegarde du soir est due : jamais lancée depuis le dernier 23 h 30 passé (rattrapage au démarrage)."""
    prevue = maintenant.replace(hour=HEURE_SAUVEGARDE[0], minute=HEURE_SAUVEGARDE[1], second=0, microsecond=0)
    if prevue > maintenant:
        prevue -= timedelta(days=1)
    try:
        return datetime.fromisoformat(derniere) < prevue
    except ValueError:
        return True


def executer(nom: str = "", *args) -> int:
    if nom not in TACHES:
        print(f"tâche inconnue : {nom} (connues : {', '.join(TACHES)})")
        return 2
    if nom == "fabrication":
        from fabrique.moteur import file

        return file.executer(*args)
    if occupe(nom):
        print(f"la {nom} est déjà en cours")
        return 3
    from fabrique.noyau import sauvegarde

    ecrire(nom, {"etat": "en_cours", "pid": os.getpid(), "debut": datetime.now().isoformat(timespec="seconds")})
    try:
        z = sauvegarde.sauvegarder()
    except Exception as e:  # noqa: BLE001 — dite à RT (état, notification), le détail dans le journal
        log.exception("sauvegarde ratée")
        ecrire(nom, {"etat": "erreur", "fin": datetime.now().isoformat(timespec="seconds"), "message": str(e)[:300]})
        return 1
    ecrire(nom, {"etat": "faite", "fin": datetime.now().isoformat(timespec="seconds"), "fichier": z.name, "taille_mo": round(z.stat().st_size / 1e6, 1)})
    print(f"sauvegarde faite : {z}")
    return 0
