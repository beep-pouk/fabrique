"""Nouveau moteur (J9d), étape bramble = etape_bramble de production.py : chaque scène de Bramble qui parle (« bramble » et une narration) sans
bramble/sNNN.mp4 devient un plan LongCat-Video-Avatar 1.5, tous en un lot dans WSL (un seul chargement des modèles) : ComfyUI arrêté (carte libérée),
bramble/_jobs.json, la commande de Linux (torchrun et moteur/production_copie/lipsync_batch.py : la commande le copie
dans le dossier de LongCat), journal bramble/lipsync.log ; la vidéo arrive directement en bramble/sNNN.mp4. Reprise : un
plan déjà fait (sNNN.mp4) est sauté, ici et par lipsync_batch.py ; un plan interrompu n'a pas de .mp4 et se refait en entier. Le prompt =
prompt_longcat de production.py, lu dans son code sans l'exécuter (ses textes ne sont pas recopiés dans l'app). Sans Django."""
import ast
import json
import subprocess
from pathlib import Path

from fabrique.moteur.f1 import copies
from fabrique.moteur.f1.outils import Outils, composant, dans_wsl, wsl
from fabrique.moteur.f1.voix import wslp, wslq


def prompt_longcat(racine):
    """prompt_longcat de production.py (et le LIPSYNC_ACTION qu'il lit), compilé seul depuis son code : production.py n'est pas exécuté.
    Lu dans les textes du projet (copies.textes : hors du dépôt)."""
    arbre = ast.parse(copies.textes(racine).read_text(encoding="utf-8"))  # J10 : la copie hors dépôt de ses définitions
    ns = {n.targets[0].id: ast.literal_eval(n.value) for n in arbre.body
          if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "LIPSYNC_ACTION"}
    fonction = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "prompt_longcat")
    exec(compile(ast.Module([fonction], type_ignores=[]), "production_textes.py", "exec"), ns)  # noqa: S102 — les textes du projet, joués à chaque rendu
    return ns["prompt_longcat"]


def faire(racine, dossier, scenes: list[dict], cfg: dict, comfy=None, popen=subprocess.Popen, log=print):
    """= etape_bramble : le lot LongCat des plans de Bramble qui parlent ; rien à faire : « bramble : deja fait »."""
    o, dossier = Outils(racine), Path(dossier)
    d = dossier / "bramble"
    d.mkdir(exist_ok=True)
    prompt = prompt_longcat(racine)
    jobs = []
    for s in scenes:
        if not s.get("bramble") or not s["narration"] or (d / f"s{s['id']:03d}.mp4").exists():
            continue
        jobs.append({"image": wslp(o.poses / f"{s['bramble']}.png"), "audio": wslp(dossier / "voix" / f"s{s['id']:03d}.wav"), "out": wslp(d / f"s{s['id']:03d}"),
                     "prompt": (prompt(s["bramble"]) + " " + cfg.get("lipsync_prompt_plus", "")).strip(), "resolution": cfg.get("lipsync_resolution", "480p")})
    if not jobs:
        log("bramble : deja fait")
        return
    (comfy or o.module("kit", "comfy")).stop()  # libère la carte graphique
    jf = d / "_jobs.json"
    with open(jf, "w", encoding="utf-8") as f:  # mode texte, comme production.py : mêmes octets (fins de ligne du PC)
        json.dump(jobs, f, ensure_ascii=False, indent=1)
    log(f"bramble : {len(jobs)} plan(s) LongCat-Video-Avatar")
    prod = wslq(copies.DOSSIER)  # J10 : lipsync_batch.py et offload.py copiés dans l'app (production.py : son propre dossier)
    cmd = ("cd " + dans_wsl("longcat") + " && cp " + prod + "/lipsync_batch.py . && OFFLOAD_DIR=" + prod + " STOP_FILE=" + wslq(composant(racine, "kit", "STOP_LIPSYNC")) + " "
           "./venv/bin/torchrun --nproc_per_node=1 --master_port=29512 lipsync_batch.py --jobs " + wslq(jf) + ("" if cfg.get("lipsync_distill", True) else " --full"))
    p = popen(wsl(cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
              encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))  # sans fenêtre : l'atelier tourne sans console
    with open(d / "lipsync.log", "a", encoding="utf-8") as f:
        for ligne in p.stdout:
            f.write(ligne)
            if ligne.startswith("[lipsync]"):
                log(ligne.strip())
    if p.wait() != 0:
        raise RuntimeError("LongCat a echoue : voir bramble/lipsync.log")
