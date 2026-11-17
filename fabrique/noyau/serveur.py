"""Le processus du noyau (« Fabrique.exe noyau ») : instance unique (prise exclusive du port de l'API, faite ici : waitress seul laisserait deux
serveurs écouter le même port sous Windows), migrations en attente, jetons, puis l'API ; une boucle de fond écrit l'état chaque minute, publie
les changements, lance la sauvegarde du soir (installée seulement : jamais en développement). Repris de Bramble Studio (core/lancement.py)."""
import logging
import os
import threading
import time
from datetime import datetime

from django.conf import settings
from django.db import connections

from fabrique import dossiers, programme
from fabrique.moteur import file
from fabrique.noyau import bases, depot, etat, evenements, jetons, sauvegarde, taches
from fabrique.noyau.models import Parametre, noter

log = logging.getLogger(__name__)
PAS = 2  # secondes entre deux tours de la boucle de fond
MINUTE = 60


def quitter_bientot(delai: float = 0.5):
    """Après la réponse en cours : le .pid retiré, puis fin du processus (les bases en WAL ne craignent rien)."""
    def fin():
        (settings.DONNEES / "noyau.pid").unlink(missing_ok=True)
        log.info("noyau arrêté")
        os._exit(0)
    threading.Timer(delai, fin).start()


def tour(vu: dict, maintenant: datetime) -> dict:
    """Un tour de la boucle de fond ; `vu` garde ce qui a été publié (état de la sauvegarde, de la file, heure du dernier état écrit). La file :
    la tâche suivante lancée si la carte est libre (moteur/file.py)."""
    try:  # une file ou un dépôt en panne n'arrêtent ni l'état ni la sauvegarde du soir
        depot.traiter()
        file.tour()
    except Exception:  # noqa: BLE001 — le détail dans le journal, au tour suivant
        log.exception("dépôt ou file : tour raté")
    s, f = taches.lire("sauvegarde"), file.lister()
    change = s != vu.get("sauvegarde") or f != vu.get("file")
    if "sauvegarde" in vu:
        if s != vu["sauvegarde"]:
            evenements.publier("sauvegarde", **s)
        if f != vu["file"]:
            evenements.publier("file", taches=f)
    if change or time.monotonic() - vu.get("ecrit", -MINUTE) >= MINUTE:
        evenements.publier("etat", **etat.ecrire())
        vu["ecrit"] = time.monotonic()
    vu["sauvegarde"], vu["file"] = s, f
    if programme.installee() and taches.due(Parametre.lire("auto_sauvegarde"), maintenant) and not taches.occupe("sauvegarde"):
        Parametre.ecrire("auto_sauvegarde", maintenant.isoformat(timespec="seconds"))
        taches.lancer("sauvegarde", "noyau")
    return vu


def boucle():
    vu: dict = {}
    while True:
        try:
            vu = tour(vu, datetime.now())
        except Exception:  # noqa: BLE001 — base occupée un instant, disque : au tour suivant
            log.exception("boucle du noyau : tour raté")
        finally:
            connections.close_all()
        time.sleep(PAS)


def noyau(ecrire=print) -> int:
    from waitress import create_server

    from fabrique.wsgi import application

    try:
        prise = programme.prendre_port(dossiers.port())
    except OSError:
        ecrire(f"Un noyau tourne déjà sur le port {dossiers.port()}.")
        return 0
    settings.DONNEES.mkdir(parents=True, exist_ok=True)
    if bases.en_attente():
        bases.migrer()
    sauvegarde.dossier()  # garde : refus si le dossier des sauvegardes est un dossier de Bramble Studio
    jetons.tirer(settings.DONNEES)
    (settings.DONNEES / "noyau.pid").write_text(str(os.getpid()), encoding="ascii")
    noter("noyau", "demarrage", version=settings.VERSION, pid=os.getpid())
    connections.close_all()
    threading.Thread(target=boucle, name="boucle du noyau", daemon=True).start()
    log.info("noyau %s sur 127.0.0.1:%s", settings.VERSION, dossiers.port())
    ecrire(f"Noyau de {programme.titre()} sur http://127.0.0.1:{dossiers.port()}")
    create_server(application, sockets=[prise], threads=8, channel_timeout=3600).run()
    return 0
