"""Essais d'animation (étape 2 du plan du 24/11) : une scène animée par Fabrique, à côté de la même scène dans la vidéo de Bramble Studio, pour
que RT les compare dans l'écran Épisode. Claude les dépose (dépôt, action « comparaison » : les deux vidéos et les plans) ; elles sont copiées
dans la session : comparaisons\\<code>\\<date>\\ (bramble.mp4, fabrique.mp4, fiche.json)."""
import json
import math
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings

from fabrique import garde
from fabrique.garde import Refus

MAX_MO = 2000
MAX_PLANS = 200


def dossier(s, code: str) -> Path:
    return garde.verifier(settings.SESSIONS / s.dossier / "comparaisons" / code)


def deposer(s, code: str, demande: dict) -> str:
    """La demande du dépôt : {"titre", "bramble": chemin .mp4, "fabrique": chemin .mp4, "plans": [{"debut", "duree"}…]} ; `code` déjà vérifié."""
    titre = demande.get("titre")
    plans = demande.get("plans")
    if not isinstance(titre, str) or not titre.strip() or len(titre) > 200:
        raise ValueError("« titre » attendu (200 caractères au plus)")
    if not isinstance(plans, list) or not 0 < len(plans) <= MAX_PLANS or not all(
            isinstance(p, dict) and all(isinstance(v := p.get(k), (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v < 86400
                                        for k in ("debut", "duree")) and p["duree"] > 0 for p in plans):
        raise ValueError(f"« plans » attendus : de 1 à {MAX_PLANS} {{\"debut\", \"duree\"}} en secondes")
    from fabrique import dossiers

    videos, racine = {}, (garde.studio_bramble() or dossiers.racine().parent).resolve()
    for cle in ("bramble", "fabrique"):
        f = Path(str(demande.get(cle, "")))
        if not re.fullmatch(r"[A-Za-z]:\\.+", str(f)) or not f.resolve().is_relative_to(racine):  # ni chemin réseau ni relatif : sous le studio
            raise ValueError(f"« {cle} » : un chemin complet sous {racine} attendu")
        if f.suffix.lower() != ".mp4" or not f.is_file():
            raise ValueError(f"« {cle} » : une vidéo .mp4 qui existe attendue ({f})")
        if f.stat().st_size > MAX_MO * 1e6:
            raise ValueError(f"« {cle} » : plus de {MAX_MO} Mo")
        videos[cle] = f
    cible = dossier(s, code) / f"{datetime.now():%Y%m%d_%H%M%S}"
    cible.mkdir(parents=True)
    for cle, f in videos.items():
        shutil.copy2(f, cible / f"{cle}.mp4")
        affiche(cible / f"{cle}.mp4")
    plans = [{"debut": round(float(p["debut"]), 3), "duree": round(float(p["duree"]), 3)} for p in plans]
    (cible / "fiche.json").write_text(json.dumps({"titre": titre.strip(), "date": datetime.now().isoformat(timespec="minutes"), "plans": plans,
                                                  "duree": round(max(p["debut"] + p["duree"] for p in plans), 3)}, ensure_ascii=False), encoding="utf-8")
    return f"essai d'animation « {titre.strip()} » ajouté à {code} ({len(plans)} plans)"


def lister(s, code: str) -> list[dict]:
    """Les essais de ce script, le plus récent d'abord (une fiche illisible ou une vidéo manquante : l'essai est ignoré)."""
    racine = dossier(s, code)
    essais = []
    for d in sorted(racine.iterdir(), reverse=True) if racine.is_dir() else []:
        try:
            fiche = json.loads((d / "fiche.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (d / "bramble.mp4").is_file() and (d / "fabrique.mp4").is_file():
            essais.append({"dossier": d.name, "titre": fiche.get("titre", ""), "date": fiche.get("date", ""), "duree": fiche.get("duree", 0.0),
                           "plans": fiche.get("plans", []), "bramble": str(d / "bramble.mp4"), "fabrique": str(d / "fabrique.mp4"),
                           "affiches": [str(f) if (f := d / f"{c}.jpg").is_file() else "" for c in ("bramble", "fabrique")]})
    return essais


def affiche(video: Path):
    """Une image de la vidéo (à 1 s) à côté d'elle : le lecteur la montre tout de suite. Facultative : sans ffmpeg, le lecteur reste noir avant la lecture."""
    from fabrique import dossiers, garde
    from fabrique.moteur.f1.outils import Lieux, Outils

    try:
        subprocess.run([Outils(Lieux(garde.studio_bramble() or dossiers.racine().parent, video.parent)).ffmpeg, "-v", "error", "-y", "-ss", "1", "-i", str(video), "-frames:v", "1", "-vf", "scale=960:-2",
                        str(video.with_suffix(".jpg"))], capture_output=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, RuntimeError, subprocess.SubprocessError):
        pass
