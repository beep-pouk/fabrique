"""La seule fabrique de lignes de commande de Fabrique (repris de Bramble Studio, core/programme.py) : installée, « Fabrique.exe <sous-commande> » ;
en développement, « pythonw -m fabrique <sous-commande> » (jamais de console). Rien d'autre dans le code ne cite l'interpréteur ni « -m fabrique »
(tests/test_programme.py balaie le code). Sans Django."""
import os
import socket
import subprocess
import sys
from pathlib import Path

from fabrique import dossiers

NOM = "Fabrique"
EXE = NOM + ".exe"
IDENTITE = "StudioKids.Fabrique"  # AppUserModelID : épinglage, regroupement dans la barre des tâches, notifications au nom de l'app
SANS_CONSOLE = False  # posé par __main__ : lancée sans console (raccourci, démarrage de Windows), personne ne lit la sortie


def installee() -> bool:
    return dossiers.programme() is not None


def identite() -> str:
    """Le dépôt du code et l'installation d'essai ont la leur : leur fenêtre ne se range jamais avec celle de l'app installée."""
    return IDENTITE + (".Bac" if dossiers.bac() else "" if installee() else ".Dev")


def titre() -> str:
    return NOM + (" (bac à sable)" if dossiers.bac() else "" if installee() else " (développement)")


def commande(*args) -> list[str]:
    p = dossiers.programme()
    if p:
        return [str(p / EXE), *map(str, args)]
    python = Path(sys.executable)
    sans_console = python.with_name("pythonw.exe")
    return [str(sans_console if sans_console.is_file() else python), "-m", "fabrique", *map(str, args)]


def lancer_detache(*args, journal: Path, popen=subprocess.Popen):
    """Une sous-commande sans fenêtre, détachée de qui la lance (elle survit à son arrêt) ; sorties et plantages dans `journal`. Sous Windows un
    relais qui s'arrête aussitôt la lance : elle n'est l'enfant de personne."""
    options = {"cwd": str(dossiers.CODE.parent), "stdin": subprocess.DEVNULL}
    Path(journal).parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        return popen(commande("relais", journal, *args), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW, **options)
    with open(journal, "ab") as sortie:
        return popen(commande(*args), stdout=sortie, stderr=sortie, start_new_session=True, **options)


def relais(journal: str, *args) -> int:
    """« relais <journal> <sous-commande…> » : lance la sous-commande détachée et rend la main ; « relais <journal> --installateur <exe> … » :
    l'installateur d'une mise à jour, qui doit survivre à l'arrêt de l'app qu'il remplace."""
    with open(journal, "ab") as sortie:
        subprocess.Popen(list(args[1:]) if args[0] == "--installateur" else commande(*args), cwd=str(dossiers.CODE.parent), stdin=subprocess.DEVNULL,
                         stdout=sortie, stderr=subprocess.STDOUT, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    return 0


def image(pid: int) -> str:
    """Le chemin du programme d'un processus (vide : mort ou illisible)."""
    if os.name != "nt":
        return ""
    import ctypes
    from ctypes import wintypes

    k = ctypes.windll.kernel32
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        tampon, n = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
        return tampon.value if k.QueryFullProcessImageNameW(h, 0, tampon, ctypes.byref(n)) else ""
    finally:
        k.CloseHandle(h)


def de_l_app(pid: int) -> bool:
    """Le processus est un processus de CETTE installation (installée : son exe ; développement : un interpréteur Python)."""
    i = image(pid)
    p = dossiers.programme()
    return bool(i) and (os.path.normcase(i) == os.path.normcase(p / EXE) if p else Path(i).name.lower() in ("python.exe", "pythonw.exe"))


def tuer(pid: int):
    """Termine le processus et ses enfants, s'il est bien de l'app (un .pid périmé peut désigner un autre programme)."""
    if de_l_app(pid):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)


def boite(texte: str):
    """Une erreur de démarrage montrée dans une boîte Windows quand personne ne lit la sortie (lancée par un raccourci)."""
    if SANS_CONSOLE and os.name == "nt":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, texte, titre(), 0x10)


def prendre_port(port: int) -> socket.socket:
    """Le port à ce processus seul (instance unique) ; OSError s'il est pris. Prise exclusive : sous Windows, SO_REUSEADDR (que pose waitress)
    laisserait deux serveurs écouter le même port sans erreur."""
    prise = socket.socket()
    prise.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE if os.name == "nt" else socket.SO_REUSEADDR, 1)
    try:
        prise.bind(("127.0.0.1", port))
    except OSError:
        prise.close()
        raise
    return prise
