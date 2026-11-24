"""Captures de l'interface (0.12) servie par le noyau de développement (port 8800, lancé à part : « python -m fabrique noyau »), par Edge sans
fenêtre (même moteur que WebView2) : python outils_dev\\capturer.py [écran …] ; un écran = l'adresse après # (« episodes »,
« episode/<session>/<code> »). Sortie : OUTILS\\fabrique_construction\\captures_012\\<écran>.png, en 1920×1080 (fenêtre agrandie)."""
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

DEPOT = Path(__file__).resolve().parents[1]
SORTIE = DEPOT.parent / "fabrique_construction" / "captures_012"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def capturer(ecran: str, largeur: int = 1920, hauteur: int = 1080) -> Path:
    jeton = (DEPOT / "dev" / "donnees" / "jeton_fenetre").read_text(encoding="ascii").strip()
    f = SORTIE / f"{ecran.replace('/', '_') or 'accueil'}{'' if largeur == 1920 else f'_{largeur}'}.png"
    SORTIE.mkdir(parents=True, exist_ok=True)
    adresse = f"http://127.0.0.1:8800/fenetre/entree?j={jeton}&vers={quote('/#/' + ecran, safe='')}"
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio", f"--window-size={largeur},{hauteur}",
                    f"--user-data-dir={SORTIE / 'profil'}", "--virtual-time-budget=9000", f"--screenshot={f}", adresse],
                   check=True, capture_output=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
    return f


if __name__ == "__main__":
    for e in sys.argv[1:] or ["", "episodes", "personnages", "file", "systeme"]:
        print(capturer(e))
