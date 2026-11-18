"""Le processus du noyau (« Fabrique.exe noyau ») : instance unique (prise exclusive du port de l'API, faite ici : waitress seul laisserait deux
serveurs écouter le même port sous Windows), migrations en attente, jetons, puis l'API ; une boucle de fond écrit l'état chaque minute, publie
les changements, lance la sauvegarde du soir et le relevé quotidien des statistiques (installée seulement : jamais en développement), reprend un envoi que RT a lancé (Publier) et que plus rien n'envoie, fait les paquets prêts à poster d'une vidéo approuvée. Repris de Bramble
Studio (core/lancement.py)."""
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
from fabrique.publication import paquets, publication, statistiques
from fabrique.session import calendrier

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
    la tâche suivante lancée si la carte est libre (moteur/file.py) ; un envoi coupé repris (publication/publication.py), son échec notifié."""
    for nom, fn in (("dépôt", depot.traiter), ("file", file.tour), ("publication", publication.relancer), ("paquets", paquets.relancer),
                    ("ordre strict", calendrier.une_fois_par_jour)):
        try:  # chacun à part : une panne de l'un n'arrête ni les autres, ni l'état, ni la sauvegarde du soir
            fn()
        except Exception:  # noqa: BLE001 — le détail dans le journal, au tour suivant
            log.exception("%s : tour raté", nom)
    s, f, p = taches.lire("sauvegarde"), file.lister(), {t: taches.lire(t) for t in ("publication", "paquets")}
    change = s != vu.get("sauvegarde") or f != vu.get("file")
    if "sauvegarde" in vu:
        if s != vu["sauvegarde"]:
            evenements.publier("sauvegarde", **s)
        if f != vu["file"]:
            evenements.publier("file", taches=f)
        for t, titre in (("publication", "Publication"), ("paquets", "Paquets prêts à poster")):
            if p[t] != vu["publication"][t] and p[t].get("etat") == "erreur":
                for a in p[t].get("alertes", []):
                    evenements.publier("alerte", titre=titre, message=a)
    if change or time.monotonic() - vu.get("ecrit", -MINUTE) >= MINUTE:
        evenements.publier("etat", **etat.ecrire())
        vu["ecrit"] = time.monotonic()
    vu["sauvegarde"], vu["file"], vu["publication"] = s, f, p
    if programme.installee() and taches.due(Parametre.lire("auto_sauvegarde"), maintenant) and not taches.occupe("sauvegarde"):
        Parametre.ecrire("auto_sauvegarde", maintenant.isoformat(timespec="seconds"))
        taches.lancer("sauvegarde", "noyau")
    if programme.installee() and statistiques.du(maintenant) and not taches.occupe("releve"):
        statistiques.lancer("noyau")
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
