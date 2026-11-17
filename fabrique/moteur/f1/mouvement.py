"""F1 v2, la revue (plan § 5.1, remarque de RT du 16/11) : le mouvement réel de chaque plan d'une vidéo finie — coupes d'image (score de
scène de ffmpeg), puis différence moyenne d'une image à la suivante (YDIF de signalstats) dans chaque plan ; un plan quasi fixe (YDIF moyen
sous SEUIL) qui reste plus de `plan_fixe_max_s` à l'écran est un défaut minuté. Seuils relevés sur l'ancien s1e01 (docs\\REPRISE.md, J3)."""
import re
import subprocess
from pathlib import Path

SEUIL = 0.2  # YDIF moyen : sous lui, l'image ne bouge presque pas (16 scènes sur 74 de l'ancien s1e01)
COUPE = 0.25  # score de scène : au-dessus, une autre image
NOIR = 24  # luminance moyenne (YAVG, noir vidéo = 16) : en dessous, un écran noir (fondu de fin, queue de musique du pack son), pas une image figée


def _lire(ffmpeg: str, video: Path, filtre: str) -> str:
    r = subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-i", str(video), "-vf", f"scale=320:-2,{filtre},metadata=print:file=-", "-an", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode:
        raise RuntimeError(f"ffmpeg (mouvement) : {r.stderr.strip()[-300:]}")
    return r.stdout


def plans(ffmpeg: str, video: Path, duree: float) -> list[dict]:
    """Chaque plan de la vidéo : début, fin, durée visible (jusqu'à sa dernière image non noire), mouvement moyen (YDIF) de ses images non noires."""
    coupes = [float(t) for t in re.findall(r"pts_time:([0-9.]+)", _lire(ffmpeg, video, f"select='gt(scene,{COUPE})'"))]
    images, t, lum = [], None, 0.0
    for ligne in _lire(ffmpeg, video, "signalstats").splitlines():
        if m := re.search(r"pts_time:([0-9.]+)", ligne):
            t = float(m.group(1))
        elif m := re.search(r"YAVG=([0-9.]+)", ligne):  # écrit avant YDIF pour chaque image
            lum = float(m.group(1))
        elif (m := re.search(r"YDIF=([0-9.]+)", ligne)) and t is not None:
            images.append((t, float(m.group(1)), lum))
    bornes = [0.0, *coupes, duree]
    resultat = []
    for a, b in zip(bornes, bornes[1:]):
        # la première image d'un plan (la coupe elle-même) n'est pas comptée, ni une image noire (un fondu au noir n'est pas toujours une coupe)
        pris = [(t, y) for t, y, l in images if a < t < b and l >= NOIR]
        resultat.append({"debut": round(a, 2), "fin": round(b, 2), "visible": round(max((t for t, _ in pris), default=a) - a, 2),
                         "mouvement": round(sum(y for _, y in pris) / len(pris), 3) if pris else 0.0})
    return resultat


def defauts(ffmpeg: str, video: Path, duree: float, max_s: float) -> list[dict]:
    """Les plans quasi fixes restés plus de `max_s` secondes à l'écran, en défauts minutés (un écran noir n'en est pas un)."""
    return [{"debut": p["debut"], "fin": round(p["debut"] + p["visible"], 2), "code": "plan_fixe",
             "texte": f"plan quasi fixe trop long : {p['visible']:.0f} s à l'écran (au-delà de {max_s:.0f} s), mouvement {p['mouvement']}"}
            for p in plans(ffmpeg, video, duree) if p["visible"] > max_s and p["mouvement"] < SEUIL]
