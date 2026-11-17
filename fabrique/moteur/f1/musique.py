"""Nouveau moteur (J9a), étape musique = ace_morceau + etape_musique + etape_ambiance de production.py : ACE-Step 1.5 dans ComfyUI (même workflow, même
consigne, graines 3000 + k), morceaux de morceau_s secondes enchaînés en fondu croisé de 8 s, coupés à la durée de l'épisode, fondu final ; lit
d'ambiance si config.json -> ambiance est actif. ComfyUI est piloté par kit\\comfy.py (importé en lecture). Écrit seulement dans le dossier. Sans Django."""
import math
from pathlib import Path

from fabrique.moteur.f1.outils import Outils

KEYS = {"B-flat": "Bb", "E-flat": "Eb", "A-flat": "Ab", "D-flat": "Db", "G-flat": "Gb", "F-sharp": "F#", "C-sharp": "C#"}
TAGS = "gentle lullaby, soft felt piano, warm cello, music box, calm, sleepy, instrumental, no drums, no vocals"
TAGS_AMBIANCE = "field recording, quiet night forest ambience, soft wind in leaves, distant crickets, no melody, no instruments, no drums, no vocals"


def workflow(tags: str, bpm: int, key: str, secondes: float, seed: int, cfg: dict) -> dict:
    """La consigne envoyée à ComfyUI (format API), = celle d'ace_morceau."""
    ac = cfg.get("musique", {})
    L = lambda n, i=0: [str(n), i]
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": ac.get("modele", "acestep_v1.5_xl_sft_bf16.safetensors"), "weight_dtype": "default"}},
        "2": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "qwen_0.6b_ace15.safetensors", "clip_name2": ac.get("lm", "qwen_4b_ace15.safetensors"), "type": "ace"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ace_1.5_vae.safetensors"}},
        "4": {"class_type": "TextEncodeAceStepAudio1.5", "inputs": {"clip": L(2), "tags": tags, "lyrics": "[Instrumental]", "seed": seed,
              "bpm": bpm, "duration": float(secondes), "timesignature": "3" if "waltz" in tags else "4", "language": "en",
              "keyscale": key, "generate_audio_codes": True, "cfg_scale": 2.0, "temperature": 0.85, "top_p": 0.9, "top_k": 0, "min_p": 0.0}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": L(4)}},
        "6": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": L(1), "shift": ac.get("shift", 3.0)}},
        "7": {"class_type": "EmptyAceStep1.5LatentAudio", "inputs": {"seconds": float(secondes), "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {"model": L(6), "positive": L(4), "negative": L(5), "latent_image": L(7), "seed": seed,
              "steps": ac.get("pas", 50), "cfg": ac.get("cfg", 4.0), "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "9": {"class_type": "VAEDecodeAudio", "inputs": {"samples": L(8), "vae": L(3)}},
        "10": {"class_type": "SaveAudio", "inputs": {"audio": L(9), "filename_prefix": "prod/musique"}},
    }


def morceau(outils: Outils, comfy, tags: str, bpm: int, key: str, secondes: float, seed: int, out: Path, cfg: dict):
    outs = comfy.run(workflow(tags, bpm, key, secondes, seed, cfg), timeout=3600)
    outils.run([outils.ffmpeg, "-y", "-v", "error", "-i", outs[0], "-ar", "48000", "-ac", "2", str(out)])


def enchainement(n: int, total: float) -> str:
    """Graphe ffmpeg : n morceaux en fondu croisé de 8 s, coupés à `total` secondes, fondu final de 8 s."""
    fc, last = "", "[0:a]"
    for k in range(1, n):
        fc += f"{last}[{k}:a]acrossfade=d=8:c1=tri:c2=tri[x{k}];"
        last = f"[x{k}]"
    return fc + f"{last}atrim=duration={total:.2f},afade=t=out:st={max(0, total-8):.2f}:d=8[a]"


def faire(outils: Outils, dossier: Path, data: dict, total: float, cfg: dict) -> Path:
    """= etape_musique : musique.wav (déjà là : rien n'est refait) ; ComfyUI n'est démarré que s'il manque un morceau."""
    dossier = Path(dossier)
    out = dossier / "musique.wav"
    if out.exists():
        return out
    m = data.get("music", {})
    tags = m.get("tags", TAGS)
    bpm = int(m.get("bpm", 60)); key = m.get("key", "F major")
    for a, b in KEYS.items():
        key = key.replace(a, b)
    piece = cfg.get("musique", {}).get("morceau_s", 240)
    n = max(1, math.ceil((total + 10) / (piece - 8)))
    d = dossier / "musique"; d.mkdir(exist_ok=True)
    comfy = None
    for k in range(n):
        p = d / f"m{k}.wav"
        if not p.exists():
            comfy = comfy or _comfy(outils)
            morceau(outils, comfy, tags, bpm, key, piece, 3000 + k, p, cfg)
    inputs = []
    for k in range(n):
        inputs += ["-i", str(d / f"m{k}.wav")]
    outils.run([outils.ffmpeg, "-y", "-v", "error"] + inputs + ["-filter_complex", enchainement(n, total), "-map", "[a]", str(out)])
    ambiance(outils, dossier, cfg, comfy)
    return out


def ambiance(outils: Outils, dossier: Path, cfg: dict, comfy=None):
    """= etape_ambiance : lit d'ambiance de forêt (un morceau ACE-Step sans mélodie, bouclé au mixage) si config.json -> ambiance est actif."""
    ac = cfg.get("ambiance", {}); out = Path(dossier) / "ambiance.wav"
    if not ac.get("actif") or out.exists():
        return
    morceau(outils, comfy or _comfy(outils), ac.get("tags", TAGS_AMBIANCE), 60, "C major", ac.get("morceau_s", 240), 3100, out, cfg)


def _comfy(outils: Outils):
    comfy = outils.module("kit", "comfy")
    comfy.start()
    return comfy
