"""La fenêtre (« Fabrique.exe », « --fond » : cachée près de l'horloge) : l'interface web (interface\\, servie par le noyau) dans une fenêtre
WebView2 (pywebview, comme Bramble Studio : le moteur de Qt ne lit pas le H.264). Aucune règle ici. Instance unique par sa sonnette (port de
l'API + 1) : un 2e lancement fait revenir la fenêtre. Elle démarre le noyau s'il ne répond pas, et le relance s'il ne répond plus (toutes les
30 s) ; la page, refusée (401) par un noyau relancé, redemande l'entrée (Api.entrer). Fermer la fenêtre la cache (icône près de l'horloge,
notifications) ; « Quitter » arrête la fenêtre seulement, jamais le noyau. pywebview et pystray ne sont importés qu'au lancement."""
import logging
import os
import socket
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote, urlsplit

from fabrique import dossiers, programme
from fabrique.fenetre.client import Client
from fabrique.noyau import jetons

log = logging.getLogger(__name__)
ICI = Path(__file__).resolve().parent
GARDE_S = 30
FOND = "#0B0D10"  # celui de l'interface (interface\\index.html) : aucun éclair blanc à l'ouverture


def entree(vers: str = "/") -> str:
    """L'adresse qui pose le jeton de la fenêtre en cookie puis ouvre l'interface (noyau/interface.py) ; relu à chaque fois (noyau relancé)."""
    return f"http://127.0.0.1:{dossiers.port()}/fenetre/entree?j={jetons.lire(dossiers.donnees(), 'fenetre')}&vers={quote(vers, safe='')}"


class Api:
    """window.pywebview.api : la seule porte de la page vers le PC (jamais un fichier ni un programme)."""

    def __init__(self):
        self._vue = None  # « _ » : pywebview n'expose pas à la page ce qui commence par un souligné (sinon load_url, evaluate_js…)

    def entrer(self, vers: str = "/"):
        """Le noyau a été relancé (jeton changé) : la page rouvre l'entrée, sur l'écran où elle était."""
        if self._vue and isinstance(vers, str) and vers.startswith("/") and not vers.startswith("//"):
            self._vue.load_url(entree(vers))

    def ouvrir(self, adresse):
        """Un lien d'un autre site (YouTube…) part dans le navigateur de RT."""
        if urlsplit(str(adresse)).scheme not in ("http", "https"):
            return False
        webbrowser.open(str(adresse))
        return True

    def plein_ecran(self):
        if self._vue:
            self._vue.toggle_fullscreen()


def fenetre_windows(titre: str):
    """La fenêtre native par son titre (0 si absente)."""
    import ctypes
    from ctypes import wintypes as w

    u = ctypes.windll.user32
    u.FindWindowW.restype, u.FindWindowW.argtypes = w.HWND, [w.LPCWSTR, w.LPCWSTR]
    return u.FindWindowW(None, titre) or 0


def barre_sombre(h):
    """Barre de titre sombre (DWMWA_USE_IMMERSIVE_DARK_MODE, Windows 10 20H1 et suivants)."""
    import ctypes

    oui = ctypes.c_int(1)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(h), 20, ctypes.byref(oui), ctypes.sizeof(oui))


def devant(h) -> bool:
    """Au premier plan par l'API de Windows (leçon de Bramble Studio, 11/11 : jamais `on_top` de pywebview, qui figeait la fenêtre)."""
    import ctypes
    from ctypes import wintypes as w

    if not h:
        return False
    u = ctypes.windll.user32
    u.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT]
    u.SetForegroundWindow.argtypes = [w.HWND]
    for rang in (-1, -2):  # HWND_TOPMOST puis HWND_NOTOPMOST ; ni déplacée, ni redimensionnée, ni activée ici
        u.SetWindowPos(h, w.HWND(rang), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
    u.SetForegroundWindow(h)
    return True


def demarrer_noyau(client: Client, attente: float = 0) -> bool:
    programme.lancer_detache("noyau", journal=dossiers.donnees() / "journaux" / "sortie_noyau.log")
    fin = time.monotonic() + attente
    while time.monotonic() < fin and not client.repond():
        time.sleep(0.25)
    return client.repond()


def ecouter(sonnette: socket.socket, agir):
    sonnette.listen(5)
    while True:
        try:
            c, _ = sonnette.accept()
        except OSError:
            return
        with c:
            c.settimeout(2)
            try:
                message = c.recv(64).decode(errors="replace").strip()
            except OSError:
                continue
        try:
            agir(message)
        except Exception:  # noqa: BLE001 — la sonnette doit survivre à une fenêtre pas encore prête
            log.exception("sonnette : %s", message)


NOTIFIEES = {"sauvegarde", "noyau", "alerte", "info"}


def notification(type_: str, d: dict) -> tuple[str, str] | None:
    """Ce que le flux du noyau dit à RT par une notification de Windows : (titre, texte), ou None."""
    if type_ == "sauvegarde" and d.get("etat") == "faite":
        return "Sauvegarde faite", d.get("fichier", "")
    if type_ == "sauvegarde" and d.get("etat") == "erreur":
        return "La sauvegarde a raté", d.get("message", "")
    if type_ == "noyau":
        return "Fabrique ne démarre pas", d.get("message", "")
    if type_ in ("alerte", "info"):
        return d.get("titre", programme.NOM), d.get("message", "")
    return None


def suivre(client: Client, notifier):
    while True:  # le flux tombe quand le noyau s'arrête : on se rebranche (le jeton est relu à chaque fois)
        try:
            for type_, d in client.evenements():
                if n := notification(type_, d if isinstance(d, dict) else {}):
                    notifier(*n)
        except (OSError, ValueError):
            pass
        time.sleep(2)


def lancer(fond: bool = False) -> int:
    port = dossiers.port()
    try:
        sonnette = programme.prendre_port(port + 1)
    except OSError:  # une fenêtre de cette installation tourne : elle revient (sauf --fond, démarrage de Windows)
        from fabrique.fenetre.client import sonner

        log.info("une fenêtre tourne déjà (port %d pris)%s", port + 1, " : démarrage de Windows sans effet" if fond else " : elle revient")
        if not fond:
            sonner("montrer", port)
        return 0
    import ctypes

    import pystray
    import webview
    from PIL import Image

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(programme.identite())  # fenêtre, icône et notifications à l'identité de l'app
    client = Client()
    if not client.repond() and not demarrer_noyau(client, 30):
        programme.boite(f"{programme.titre()} : le noyau n'a pas démarré (journal : {dossiers.donnees() / 'journaux'}).")
    titre = programme.titre()
    api = Api()
    vue = webview.create_window(titre, entree(), js_api=api, width=1440, height=900, min_size=(1100, 700), hidden=True, maximized=True,
                                background_color=FOND, text_select=True)
    api._vue = vue
    pid = dossiers.donnees() / "fenetre.pid"
    pid.write_text(str(os.getpid()), encoding="ascii")
    icone = pystray.Icon(programme.identite(), Image.open(ICI / "icone.ico"), titre)

    reduite = threading.Event()
    vue.events.minimized += reduite.set
    vue.events.restored += reduite.clear
    vue.events.maximized += reduite.clear

    def montrer():
        vue.show()
        if reduite.is_set():
            vue.restore()
        devant(fenetre_windows(titre))

    sortie = threading.Event()

    def quitter():
        sortie.set()  # destroy() passe aussi par « closing » : sans ce drapeau, fermer() l'annulerait
        icone.stop()
        vue.destroy()

    def cacher():
        try:
            vue.evaluate_js("window.fabriqueCachee && window.fabriqueCachee()")  # sons et vidéos s'arrêtent avec la fenêtre
        except Exception:  # noqa: BLE001 — page pas encore prête : rien ne joue
            pass
        vue.hide()

    def fermer():
        if sortie.is_set():
            return True
        threading.Thread(target=cacher, daemon=True).start()
        return False  # la fermeture est annulée : la fenêtre se cache près de l'horloge

    vue.events.closing += fermer
    icone.menu = pystray.Menu(pystray.MenuItem("Ouvrir Fabrique", lambda: montrer(), default=True),
                              pystray.MenuItem("Quitter la fenêtre (Fabrique continue en fond)", lambda: quitter()))
    notifier = lambda t, x: icone.notify(x or " ", t)  # noqa: E731
    threading.Thread(target=icone.run, name="icône", daemon=True).start()
    threading.Thread(target=ecouter, args=(sonnette, lambda m: quitter() if m == "quitter" else montrer()), name="sonnette", daemon=True).start()
    threading.Thread(target=suivre, args=(client, notifier), name="flux du noyau", daemon=True).start()

    def veiller():
        rates = 0
        while True:
            time.sleep(GARDE_S)
            try:  # une panne d'un tour (Popen pendant une mise à jour…) ne doit pas tuer la garde
                if client.repond():
                    rates = 0
                    continue
                rates += 1
                log.warning("le noyau ne répond plus : relancé (%d fois de suite)", rates)
                if rates == 3:  # une seule alerte : il meurt sans doute au démarrage, la fenêtre seule ne peut rien y faire
                    notifier("Fabrique ne démarre pas", f"Relancé sans succès depuis 1 min 30 ; le détail est dans {dossiers.donnees() / 'journaux'}.")
                demarrer_noyau(client)
            except Exception:  # noqa: BLE001
                log.exception("garde du noyau")

    threading.Thread(target=veiller, name="garde du noyau", daemon=True).start()

    def pret():
        barre_sombre(fenetre_windows(titre))
        if not fond:
            montrer()
        log.info("fenêtre ouverte (%s)", "cachée" if fond else "visible")

    try:
        webview.start(pret, icon=str(ICI / "icone.ico"), private_mode=False, storage_path=str(dossiers.donnees() / "webview"))
    finally:
        icone.stop()
        pid.unlink(missing_ok=True)
    return 0
