"""La fenêtre (« Fabrique.exe », « --fond » : cachée près de l'horloge) : Qt Quick (Main.qml) piloté en Python. Aucune règle ici : elle ne parle
qu'à l'API du noyau (client.py). Instance unique par sa sonnette (port de l'API + 1) : un 2e lancement fait revenir la fenêtre. Elle démarre le
noyau s'il ne répond pas, et le relance s'il ne répond plus (toutes les 30 s). Fermer la fenêtre ne l'arrête pas (icône près de l'horloge,
notifications) ; « Quitter » arrête la fenêtre seulement, jamais le noyau. Pièges de Qt repris de la maquette du banc (NOTES.md) : raccourcis
par un filtre d'événements sur la fenêtre (pas Shortcut), une touche tenue n'est jamais rejouée."""
import logging
import os
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import Property, QEvent, QObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QIcon, QWindow
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401 — importé : la fenêtre racine arrive en QQuickWindow (grabWindow)
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from fabrique import dossiers, programme
from fabrique.fenetre.client import Client, ErreurApi

log = logging.getLogger(__name__)
ICI = Path(__file__).resolve().parent
GARDE_MS = 30_000
CREATIONS = {"nouvelle_session", "relier", "code_telephone"}  # des lectures qui font quelque chose : leur refus est dit à RT
VK_1, VK_2, VK_3, VK_4 = 0x31, 0x32, 0x33, 0x34  # touches 1 à 4 du haut du clavier, quelle que soit la disposition (AZERTY : « & », « é »…)


class Pont(QObject):
    """Ce que le QML demande au noyau (en fond : la fenêtre ne gèle jamais) et ce qui lui revient."""

    recu = Signal(str, "QVariant")  # nom de l'appel, réponse
    fait = Signal(str, str, bool)  # nom de l'action, message pour RT, réussie
    aller = Signal(str)  # écran demandé au clavier ; vide : actualiser
    evenement = Signal(str, "QVariant")  # flux du noyau

    def __init__(self, client: Client, notifier=None):
        super().__init__()
        self.client, self.fond, self.tenues = client, ThreadPoolExecutor(4), set()
        self.notifier = notifier or (lambda titre, texte, grave=False: None)
        self.evenement.connect(self._evenement)

    @Property(str, constant=True)
    def titre(self):
        return programme.titre()

    @Slot(str)
    def charger(self, nom: str):
        self.fond.submit(self._lire, nom)

    @Slot(str, "QVariantMap")
    def lire(self, nom: str, params):
        """Une lecture avec ses paramètres (la session choisie) ; la réponse revient sous son nom."""
        self.fond.submit(self._lire, nom, dict(params))

    def _lire(self, nom: str, params: dict | None = None):
        params = params or {}
        try:
            self.recu.emit(nom, self.client.appeler(nom, params.pop("corps", None), **params))  # corps : les règles d'un brouillon, une nouvelle session
        except ErreurApi as e:  # le refus d'une lecture qui crée (nouvelle session : nom pris…) est dit à RT ; les autres seulement journalisés
            log.warning("lecture %s : %s", nom, e)
            if nom in CREATIONS:
                self.fait.emit(nom, str(e)[:1].upper() + str(e)[1:] + ".", False)
        except OSError as e:
            log.warning("lecture %s : %s", nom, e)

    @Slot(str, "QVariantMap")
    def agir(self, nom: str, params):
        self.fond.submit(self._agir, nom, dict(params))

    def _agir(self, nom: str, params: dict):
        corps = params.pop("corps", None) or ({"valeur": params.pop("valeur")} if "valeur" in params else None)
        try:
            self.fait.emit(nom, self.client.appeler(nom, corps, **params)["message"], True)
        except ErreurApi as e:
            self.fait.emit(nom, str(e)[:1].upper() + str(e)[1:] + ".", False)
        except OSError:
            self.fait.emit(nom, "Le noyau ne répond pas : il redémarre tout seul dans un instant.", False)
        except Exception:  # noqa: BLE001 — un fil de fond ne doit rien perdre en silence
            log.exception("action %s", nom)
            self.fait.emit(nom, "Erreur inattendue : le détail est dans le journal (Système).", False)

    def _evenement(self, type_: str, d):
        if type_ == "sauvegarde" and d.get("etat") == "faite":
            self.notifier("Sauvegarde faite", d.get("fichier", ""))
        elif type_ == "sauvegarde" and d.get("etat") == "erreur":
            self.notifier("La sauvegarde a raté", d.get("message", ""), True)
        elif type_ == "noyau":
            self.notifier("Le noyau de Fabrique ne démarre pas", d.get("message", ""), True)
        elif type_ == "alerte":
            self.notifier(d.get("titre", "Fabrique"), d.get("message", ""), True)
        elif type_ == "info":
            self.notifier(d.get("titre", "Fabrique"), d.get("message", ""))

    def eventFilter(self, _, e):
        if e.type() == QEvent.Type.KeyPress:
            # sous Windows, la répétition d'une touche tenue arrive comme un appui neuf quand un modificateur change (maquette du banc)
            repetee = e.isAutoRepeat() or e.key() in self.tenues
            self.tenues.add(e.key())
            ctrl = bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier)
            touche = next((ecran for vk, ecran in ((VK_1, "accueil"), (VK_2, "sessions"), (VK_3, "file"), (VK_4, "systeme"))
                           if ctrl and vk in (e.key(), e.nativeVirtualKey())), None)
            ecran = touche or ("" if e.key() == Qt.Key.Key_F5 else None)
            if ecran is not None:
                if not repetee:
                    self.aller.emit(ecran)
                return True
        elif e.type() == QEvent.Type.KeyRelease and not e.isAutoRepeat():
            self.tenues.discard(e.key())
        return False


def ouvrir(client: Client, notifier=None):
    """La fenêtre chargée (cachée) sur ce client : (moteur QML, pont, fenêtre). Une QApplication doit exister."""
    moteur = QQmlApplicationEngine()
    pont = Pont(client, notifier)
    moteur.rootContext().setContextProperty("pont", pont)
    moteur.load(QUrl.fromLocalFile(str(ICI / "Main.qml")))
    if not moteur.rootObjects():
        raise RuntimeError("Main.qml n'a pas pu être chargé (voir le journal)")
    fenetre = moteur.rootObjects()[0]
    fenetre.installEventFilter(pont)
    return moteur, pont, fenetre


def demarrer_noyau(client: Client, attente: float = 0) -> bool:
    programme.lancer_detache("noyau", journal=dossiers.donnees() / "journaux" / "sortie_noyau.log")
    fin = time.monotonic() + attente
    while time.monotonic() < fin and not client.repond():
        time.sleep(0.25)
    return client.repond()


def ecouter(sonnette: socket.socket, recue: Signal):
    sonnette.listen(5)
    while True:
        c, _ = sonnette.accept()
        with c:
            c.settimeout(2)
            try:
                recue.emit(c.recv(64).decode(errors="replace").strip())
            except OSError:
                pass


def suivre(client: Client, pont: Pont):
    while True:  # le flux tombe quand le noyau s'arrête : on se rebranche (le jeton est relu à chaque fois)
        try:
            for type_, d in client.evenements():
                pont.evenement.emit(type_, d)
        except (OSError, ValueError):
            pass
        time.sleep(2)


class Sonnette(QObject):
    """Reçue dans le fil de la sonnette, traitée dans celui de la fenêtre (méthode d'un objet de ce fil : connexion différée par Qt)."""
    recue = Signal(str)

    def __init__(self, montrer, quitter):
        super().__init__()
        self.montrer, self.quitter = montrer, quitter
        self.recue.connect(self.agir)

    @Slot(str)
    def agir(self, message: str):
        self.quitter() if message == "quitter" else self.montrer()


def lancer(fond: bool = False) -> int:
    port = dossiers.port()
    try:
        sonnette = programme.prendre_port(port + 1)
    except OSError:  # une fenêtre de cette installation tourne : elle revient (sauf --fond, démarrage de Windows)
        from fabrique.fenetre.client import sonner

        if not fond:
            sonner("montrer", port)
        return 0
    if os.name == "nt":  # avant toute fenêtre : fenêtre, icône et notifications portent l'identité de l'app
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(programme.identite())
    os.environ["QML_DISABLE_DISK_CACHE"] = "1"  # rien n'est écrit hors du dossier de Fabrique (cache de Qt dans le profil)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DisableShaderDiskCache)
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)  # barre de titre sombre
    icone = QIcon(str(ICI / "icone.ico"))
    app.setWindowIcon(icone)
    client = Client()
    if not client.repond() and not demarrer_noyau(client, 30):
        programme.boite(f"{programme.titre()} : le noyau n'a pas démarré (journal : {dossiers.donnees() / 'journaux'}).")
    barre = QSystemTrayIcon(icone)
    moteur, pont, fenetre = ouvrir(client, lambda titre, texte, grave=False: barre.showMessage(
        titre, texte, QSystemTrayIcon.MessageIcon.Critical if grave else QSystemTrayIcon.MessageIcon.Information))
    pid = dossiers.donnees() / "fenetre.pid"
    pid.write_text(str(os.getpid()), encoding="ascii")
    app.aboutToQuit.connect(lambda: pid.unlink(missing_ok=True))

    def montrer():
        fenetre.showNormal() if fenetre.visibility() == QWindow.Visibility.Minimized else fenetre.show()
        fenetre.raise_()
        fenetre.requestActivate()

    menu = QMenu()
    menu.addAction("Ouvrir Fabrique", montrer)
    menu.addAction("Quitter la fenêtre (le noyau continue)", app.quit)
    barre.setContextMenu(menu)
    barre.setToolTip(programme.titre())
    barre.activated.connect(lambda raison: montrer() if raison == QSystemTrayIcon.ActivationReason.Trigger else None)
    barre.show()
    recue = Sonnette(montrer, app.quit)
    threading.Thread(target=ecouter, args=(sonnette, recue.recue), name="sonnette", daemon=True).start()
    threading.Thread(target=suivre, args=(client, pont), name="flux du noyau", daemon=True).start()

    rates = 0

    def veiller():
        nonlocal rates
        if client.repond():
            rates = 0
            return
        rates += 1
        log.warning("le noyau ne répond plus : relancé (%d fois de suite)", rates)
        if rates == 3:  # une seule alerte : il meurt sans doute au démarrage, la fenêtre seule ne peut rien y faire
            pont.evenement.emit("noyau", {"message": f"Relancé sans succès depuis 1 min 30 ; le détail est dans {dossiers.donnees() / 'journaux'}."})
        demarrer_noyau(client)

    garde = QTimer(interval=GARDE_MS)
    garde.timeout.connect(lambda: pont.fond.submit(veiller))
    garde.start()
    if not fond:
        montrer()
    log.info("fenêtre ouverte (%s)", "cachée" if fond else "visible")
    return app.exec()
