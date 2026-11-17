"""Nouveau moteur (J9a), étape voix = etape_voix + controle_voix de production.py : Chatterbox (OUTILS\\chatterbox\\venv, kit\\voix\\tts_chatterbox.py,
graine 42, réglages config.json -> voix, profils par acte si actifs), puis Whisper dans WSL (analyse\\controle_voix_wsl.py) réécoute chaque phrase ;
sous controle_voix_seuil, la phrase est refaite avec la graine 42 + 1000 × essai (3 essais au plus). Écrit seulement dans <dossier>/voix/. Sans Django."""
import json
import os
import re
import shlex
import subprocess
from pathlib import Path

from fabrique.moteur.f1.outils import Outils, composant, dans_wsl, wsl


def jobs(dossier: Path, scenes: list[dict], cfg: dict) -> list[dict]:
    """Une consigne Chatterbox par scène qui a une narration et pas encore de voix (rien n'est refait)."""
    d = Path(dossier) / "voix"
    v = cfg["voix"]
    pa = v.get("par_acte", {}) if v.get("par_acte", {}).get("actif") else {}   # pack son (rejeté, gardé éteint) : voix plus vivante au début, plus douce à la fin
    lot = []
    for i, s in enumerate(scenes):
        out = d / f"s{s['id']:03d}.wav"
        if s["narration"] and not out.exists():
            ex, cf, vi = v.get("exaggeration", 0.4), v.get("cfg", 0.5), v.get("vitesse", 0.85)
            if pa:
                acte = sum(i >= b * len(scenes) for b in pa.get("bornes", [0.33, 0.65]))
                ex, cf, vi = pa["profils"][acte]
            lot.append({"ref_audio": v["ref_audio"], "ref_text": v["ref_text"], "text": s["narration"],
                        "out": str(out), "speed": vi, "seed": 42, "exaggeration": ex, "cfg": cf})
    return lot


def pret(outils: Outils) -> str:
    """Vide si le Python du venv de Chatterbox démarre ; sinon la fin de son message d'erreur (le moteur s'arrêterait à la première voix)."""
    py = composant(outils.racine, "chatterbox", "venv", "Scripts", "python.exe")
    try:
        r = subprocess.run([str(py), "-c", "import encodings.aliases"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as e:
        return f"{py} : {e}"
    return "" if r.returncode == 0 else (r.stderr.strip().splitlines() or ["code " + str(r.returncode)])[-1][:300]


def chatterbox(outils: Outils, dossier: Path, lot: list[dict]):
    """Les consignes dans voix/_jobs.json, puis le script de production.py dans le venv de Chatterbox (carte graphique)."""
    jf = Path(dossier) / "voix" / "_jobs.json"
    json.dump({"jobs": lot}, open(jf, "w", encoding="utf-8"), ensure_ascii=False)
    c = lambda cle, *rel: composant(outils.racine, cle, *rel)  # noqa: E731
    outils.run([c("chatterbox", "venv", "Scripts", "python.exe"), c("kit", "voix", "tts_chatterbox.py"), jf],
               cwd=str(c("chatterbox")), env=dict(os.environ, HF_HOME=str(c("cache_voix"))))


def wslp(p) -> str:
    return "/mnt/" + str(p)[0].lower() + str(p)[2:].replace("\\", "/")


def wslq(p) -> str:
    """Le même chemin, à coller dans une commande bash : entre apostrophes s'il porte une espace (dossier « Bramble Studio ») ou un caractère que
    bash lirait, inchangé sinon (lettres accentuées comprises : production.py colle le chemin nu, les preuves d'égalité comparent)."""
    p = wslp(p)
    return shlex.quote(p) if re.search(r"[^\w@%+=:,./-]", p) else p


def controler(outils: Outils, dossier: Path, scenes: list[dict], cfg: dict, essais: int = 3) -> dict:
    """Whisper réécoute chaque phrase (voix/_controle.json : score, ce qu'il a entendu) ; une phrase sous le seuil est refaite avec une autre graine."""
    d = Path(dossier) / "voix"; v = cfg["voix"]; seuil = cfg.get("controle_voix_seuil", 0.93)
    fait = json.load(open(d / "_controle.json", encoding="utf-8")) if (d / "_controle.json").exists() else {}
    for essai in range(essais):
        lot = [{"wav": wslp(d / f"s{s['id']:03d}.wav"), "texte": s["narration"], "id": s["id"]}
               for s in scenes if s["narration"] and (d / f"s{s['id']:03d}.wav").exists() and str(s["id"]) not in fait]
        if not lot:
            break
        lf = d / "_controle_lot.json"; json.dump(lot, open(lf, "w", encoding="utf-8"), ensure_ascii=False)
        cmd = ("cd " + dans_wsl("longcat") + " && ./venv/bin/python " + wslq(composant(outils.racine, "analyse", "controle_voix_wsl.py")) + " " + wslq(lf))
        try:
            subprocess.run(wsl(cmd), capture_output=True, timeout=3600,  # Whisper bloqué (WSL) : pas d'attente sans fin, l'étape continue sans contrôle (14/11)
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            return fait
        rf = d / "_controle_lot_resultat.json"
        if not rf.exists():
            return fait  # contrôle Whisper impossible (WSL) : on continue sans, comme production.py
        mauvais = []
        for j, r in zip(lot, json.load(open(rf, encoding="utf-8"))):
            if r["score"] >= seuil or essai == essais - 1:
                fait[str(j["id"])] = r
            else:
                mauvais.append((j["id"], r))
        json.dump(fait, open(d / "_controle.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if not mauvais:
            break
        refaire = []
        for i, r in mauvais:
            s = next(x for x in scenes if x["id"] == i)
            out = d / f"s{i:03d}.wav"; out.unlink()
            refaire.append({"ref_audio": v["ref_audio"], "ref_text": v["ref_text"], "text": s["narration"], "out": str(out),
                            "speed": v.get("vitesse", 0.85), "seed": 42 + 1000 * (essai + 1),
                            "exaggeration": v.get("exaggeration", 0.4), "cfg": v.get("cfg", 0.5)})
        chatterbox(outils, dossier, refaire)
    return fait


def faire(outils: Outils, dossier: Path, scenes: list[dict], cfg: dict) -> dict:
    """= etape_voix : voix/sNNN.wav des scènes qui n'en ont pas, puis le contrôle Whisper ; renvoie voix/_controle.json."""
    (Path(dossier) / "voix").mkdir(exist_ok=True)
    lot = jobs(dossier, scenes, cfg)
    if lot:
        chatterbox(outils, dossier, lot)
    return controler(outils, dossier, scenes, cfg)
