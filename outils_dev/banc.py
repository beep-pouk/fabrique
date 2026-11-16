"""Aides Windows des recettes (repris de Bramble Studio, outils_dev\\fumee.py et recette_installation.py) : processus, fenêtres, consoles,
bibliothèques chargées, en-tête d'un exe, empreinte d'un dossier, registre et raccourcis lus. Outil de développement : jamais livré."""
import ctypes
import hashlib
import os
import re
import struct
import subprocess
import time
import winreg
from ctypes import wintypes as w
from pathlib import Path

CONSOLES = {"ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"}  # console classique, Terminal Windows
POWERSHELL = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
WINDOWS = os.path.normcase(os.environ.get("SystemRoot", r"C:\Windows")) + os.sep


class _Entree(ctypes.Structure):
    _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD), ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", w.DWORD),
                ("cntThreads", w.DWORD), ("th32ParentProcessID", w.DWORD), ("pcPriClassBase", w.LONG), ("dwFlags", w.DWORD), ("szExeFile", w.WCHAR * 260)]


def processus() -> dict[int, str]:
    """{pid: chemin complet de l'exe} de tous les processus lisibles."""
    k = ctypes.windll.kernel32
    k.CreateToolhelp32Snapshot.restype = k.OpenProcess.restype = w.HANDLE
    k.Process32FirstW.argtypes = k.Process32NextW.argtypes = [w.HANDLE, ctypes.POINTER(_Entree)]
    k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
    k.CloseHandle.argtypes = [w.HANDLE]
    vus, instantane, e = {}, k.CreateToolhelp32Snapshot(0x2, 0), _Entree()
    e.dwSize = ctypes.sizeof(_Entree)
    suite = k.Process32FirstW(instantane, ctypes.byref(e))
    while suite:
        h = k.OpenProcess(0x1000, False, e.th32ProcessID)
        if h:
            chemin, n = ctypes.create_unicode_buffer(32768), w.DWORD(32768)
            if k.QueryFullProcessImageNameW(h, 0, chemin, ctypes.byref(n)):
                vus[e.th32ProcessID] = chemin.value
            k.CloseHandle(h)
        suite = k.Process32NextW(instantane, ctypes.byref(e))
    k.CloseHandle(instantane)
    return vus


def sous(dossier: Path):
    """Les processus dont l'exe est dans `dossier`."""
    d = os.path.normcase(str(dossier)) + os.sep
    return {p: c for p, c in processus().items() if os.path.normcase(c).startswith(d)}


def fenetres() -> list[tuple[int, str, str, int, int]]:
    """(poignée, titre, classe, pid, largeur) des fenêtres visibles de premier niveau."""
    u, vues = ctypes.windll.user32, []

    @ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def chaque(h, _):
        if u.IsWindowVisible(h):
            titre, classe, pid, r = ctypes.create_unicode_buffer(300), ctypes.create_unicode_buffer(300), w.DWORD(), w.RECT()
            u.GetWindowTextW(h, titre, 300), u.GetClassNameW(h, classe, 300), u.GetWindowThreadProcessId(h, ctypes.byref(pid)), u.GetWindowRect(h, ctypes.byref(r))
            vues.append((h, titre.value, classe.value, pid.value, r.right - r.left))
        return True

    u.EnumWindows(chaque, 0)
    return vues


def fermer_fenetre(poignee: int):
    ctypes.windll.user32.PostMessageW(poignee, 0x0010, 0, 0)  # WM_CLOSE : comme la croix


def attendre(condition, delai: float, quoi: str, pas: float = 0.3):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if r := condition():
            return r
        time.sleep(pas)
    raise AssertionError(f"toujours pas après {delai:.0f} s : {quoi}")


def empreinte(dossier: Path, sauf=()) -> dict:
    """{chemin relatif: (taille, date, sha256)} de tout le dossier ; `sauf` : motifs de chemins relatifs ignorés."""
    r = {}
    for f in sorted(Path(dossier).rglob("*")):
        rel = f.relative_to(dossier).as_posix()
        try:
            if f.is_file() and not any(Path(rel).match(m) for m in sauf):
                s = f.stat()
                r[rel] = (s.st_size, s.st_mtime_ns, hashlib.sha256(f.read_bytes()).hexdigest() if s.st_size < 50_000_000 else "")
        except OSError as e:  # tenu par un autre programme : noté tel quel, comparé tel quel
            r[rel] = ("illisible", e.__class__.__name__, "")
    return r


def differences(avant: dict, apres: dict) -> list[str]:
    return sorted([f"+ {f}" for f in apres.keys() - avant.keys()] + [f"- {f}" for f in avant.keys() - apres.keys()]
                  + [f"≠ {f}" for f in avant.keys() & apres.keys() if avant[f] != apres[f]])


def bibliotheques(pid: int) -> tuple[list[str], set[str]]:
    """Les .dll, .exe et .pyd chargés par le processus, et ceux d'un processus témoin de Windows (le PowerShell qui fait la lecture) :
    ce que l'antivirus injecte dans tout processus se retrouve dans les deux."""
    ps = (f"(Get-Process -Id {pid}).Modules | ForEach-Object {{ 'C ' + $_.FileName }}; "
          "[Diagnostics.Process]::GetCurrentProcess().Modules | ForEach-Object { 'T ' + $_.FileName }")
    r = subprocess.run([str(POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=subprocess.CREATE_NO_WINDOW)
    lignes = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    return [l[2:] for l in lignes if l.startswith("C ")], {os.path.normcase(l[2:]) for l in lignes if l.startswith("T ")}


def externes(pid: int, prog: Path) -> list[str]:
    """Bibliothèques chargées hors du programme et hors de Windows, sauf celles qu'un processus de Windows a aussi (injectées par l'antivirus) ;
    le runtime C de Visual Studio pris dans Windows compte comme externe : le programme livre le sien (contrôle du banc d'interface)."""
    p = os.path.normcase(str(prog)) + os.sep
    charges, temoin = bibliotheques(pid)
    return [m for m in charges if not (c := os.path.normcase(m)).startswith(p) and c not in temoin
            and (not c.startswith(WINDOWS) or re.search(r"\\(msvcp|vcruntime|vcomp|concrt)\d", c))]


def sous_systeme(exe: Path) -> int:
    """2 : programme fenêtré (jamais de console) ; 3 : programme de console."""
    d = Path(exe).read_bytes()[:4096]
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    return struct.unpack_from("<H", d, pe + 24 + 68)[0]


def registre(cle: str, valeur: str) -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cle) as k:
            return str(winreg.QueryValueEx(k, valeur)[0])
    except OSError:
        return None


def raccourcis() -> dict[str, Path]:
    menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    bureau = Path(subprocess.run([str(POWERSHELL), "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"], capture_output=True, text=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW).stdout.strip())
    return {"menu Démarrer": menu, "bureau": bureau, "démarrage": menu / "Startup"}


def identite(raccourci: Path) -> str:
    """« <AppUserModelID> | <cible> » d'un raccourci, lus par l'Explorateur."""
    ps = ("$i = (New-Object -ComObject Shell.Application).Namespace($env:R_DOSSIER).ParseName($env:R_NOM); "
          "\"$($i.ExtendedProperty('System.AppUserModel.ID')) | $($i.GetLink.Path)\"")
    return subprocess.run([str(POWERSHELL), "-NoProfile", "-Command", ps], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
                          env={**os.environ, "R_DOSSIER": str(raccourci.parent), "R_NOM": raccourci.name}).stdout.strip()


def signataire(fichier: Path) -> str:
    ps = "$s = Get-AuthenticodeSignature -LiteralPath $env:R_FICHIER; if ($s.SignerCertificate) { $s.SignerCertificate.Thumbprint }"
    return subprocess.run([str(POWERSHELL), "-NoProfile", "-Command", ps], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
                          env={**os.environ, "R_FICHIER": str(fichier)}).stdout.strip()
