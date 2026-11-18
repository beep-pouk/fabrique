"""Les faux outils (plan § 5.2) : une sortie plausible par brique en une fraction de seconde, sans carte, par ffmpeg (repris de Bramble Studio,
moteur/simulation.py : couleur unie, son de synthèse). C'est la simulation, et la base des tests. Réglages de la fiche : « hauteur_hz » (le
son), « couleur » (l'image), « en_panne » (le service ne répond pas : les tests le posent)."""
import json
import shutil
import subprocess
from pathlib import Path

from fabrique import garde
from fabrique.moteur.outils import Demande, Estimation, Fiche, Resultat

SORTIES = {"voix": "voix.wav", "images": "image.png", "animation": "clip.mp4", "musique": "musique.wav", "levres": "clip.mp4",
           "montage": "video.mp4", "miniature": "miniature.png", "controle": "rapport.json", "chant": "chanson.wav"}
SECONDES = 0.3  # estimation sans chrono


def programme(nom: str) -> str:
    """ffmpeg ou ffprobe du studio (OUTILS\\ffmpeg, partagé avec Bramble Studio, lu seulement), sinon du PATH."""
    for studio in garde.studios():
        if (p := studio / "OUTILS" / "ffmpeg" / f"{nom}.exe").is_file():
            return str(p)
    if p := shutil.which(nom):
        return p
    raise RuntimeError(f"{nom} introuvable (ni dans OUTILS\\ffmpeg du studio, ni sur le chemin)")


def lancer(*args) -> str:
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode:
        raise RuntimeError(f"{Path(str(args[0])).stem} : {(r.stderr or r.stdout).strip()[-300:]}")
    return r.stdout


def _mots(voix: str) -> list[dict]:
    """Les mots horodatés rendus avec une voix (resultat.json de son morceau)."""
    try:
        return json.loads((Path(voix).parent / "resultat.json").read_text(encoding="utf-8"))["infos"].get("mots", [])
    except (OSError, ValueError, KeyError):
        return []


def estimer(fiche: Fiche, demande: Demande) -> Estimation:
    return Estimation(secondes=SECONDES, cout_eur=fiche.prix_unite_eur, carte_go=fiche.besoins.carte_go)


def fabriquer(fiche: Fiche, demande: Demande, dossier: Path) -> Resultat:
    r = fiche.reglages
    if r.get("en_panne"):
        raise RuntimeError(f"{fiche.nom} : le service ne répond pas")
    sortie = dossier / SORTIES[demande.brique]
    infos = {"cout_eur": fiche.prix_unite_eur} if not fiche.local else {}
    if demande.brique == "controle":  # le contrôle mesure ce que le montage a produit
        montages = [fichiers[0] for etape, fichiers in demande.entrees.items() if demande.sources.get(etape) == "montage" and fichiers]
        if not montages:
            raise RuntimeError("le contrôle demande une étape de montage avant lui dans la recette")
        video = montages[-1]
        duree = float(lancer(programme("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video).strip())
        sortie.write_text(json.dumps({"video": Path(video).name, "duree_s": duree, "defauts": []}, ensure_ascii=False), encoding="utf-8")
        return Resultat(fichiers=[sortie.name], duree_s=duree, infos={**infos, "defauts": []})
    if demande.brique == "chant":  # deux secondes par section, les mots de ses paroles répartis dedans, comme l'outil réel les cale
        from fabrique.moteur import paroles

        sections, mots = paroles.script_de(demande)["sections"], []
        for i, s in enumerate(sections):
            ms = paroles.mots_du_texte([s])
            mots += [{**m, "debut": round(2 * i + 2 * j / len(ms), 3), "fin": round(2 * i + 2 * (j + 1) / len(ms), 3)} for j, m in enumerate(ms)]
        duree = 2.0 * len(sections)
        lancer(programme("ffmpeg"), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={r.get('hauteur_hz', 440)}:duration={duree}:sample_rate=24000", sortie)
        return Resultat(fichiers=[sortie.name], duree_s=duree, infos={**infos, "mots": mots, "sections": paroles.bornes(sections, mots, duree), "compris": 1.0})
    duree = float(max([1, *map(len, demande.entrees.values())])) if demande.brique == "montage" else 1.0  # le montage : une seconde par plan
    couleur, hz = r.get("couleur", "5c8048"), r.get("hauteur_hz", 440)
    image = f"color=c=0x{couleur}:s={'36x64' if demande.reglages.get('cadre') == '9:16' else '64x36'}"
    son = f"sine=frequency={hz}:duration={duree}:sample_rate=24000"
    if sortie.suffix == ".wav":
        args = ["-f", "lavfi", "-i", son]
    elif sortie.suffix == ".png":
        args = ["-f", "lavfi", "-i", image, "-frames:v", "1"]
    else:
        args = ["-f", "lavfi", "-i", f"{image}:d={duree}:r=12", "-f", "lavfi", "-i", son, "-shortest", "-pix_fmt", "yuv420p", "-c:a", "aac"]
    lancer(programme("ffmpeg"), "-nostdin", "-v", "error", "-y", *args, sortie)
    if demande.brique == "montage":  # une transcription comme celle de l'analyse : les mots de chaque plan dans sa seconde
        voix, mots = next((e for e, b in demande.sources.items() if b == "voix"), ""), []
        for i, f in enumerate(demande.entrees.get(voix, [])):
            ms = [x["mot"] for x in _mots(f)]
            mots += [{"t": i + j / len(ms), "fin": i + (j + 1) / len(ms), "mot": w} for j, w in enumerate(ms)]
        if mots:
            sortie.with_name(sortie.stem + ".transcription.json").write_text(json.dumps({"mots": mots}, ensure_ascii=False), encoding="utf-8")
    if demande.brique == "voix":
        mots = demande.texte.split() or ["…"]
        infos["mots"] = [{"mot": m, "debut": round(i * duree / len(mots), 3), "fin": round((i + 1) * duree / len(mots), 3)} for i, m in enumerate(mots)]
    return Resultat(fichiers=[sortie.name], duree_s=None if sortie.suffix == ".png" else duree, infos=infos)
