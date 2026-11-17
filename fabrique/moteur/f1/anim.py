"""Nouveau moteur (J9c), étape anim = etape_anim + etape_anim_calques de production.py, moteur « calques 2,5D » (config.json -> video_moteur = calques) :
les calques de chaque plan avec des amis (décor sans personnage par Qwen-Image-Edit, masque BiRefNet ; ComfyUI, un plan après l'autre), puis
l'animation calculée de tous les plans en parallèle (processeur) -> clips/sNNN.mp4 et sNNN_last.png. Seule l'orchestration est réécrite :
calques.py et anime_calques.py sont APPELÉS tels quels depuis OUTILS/production (lecture seule, rien de copié dans l'app ; décision de la supervision
du 5/11, leur place se décidera à J9e avec RT). Ils font `import production as P` : un module de remplacement leur donne CFG, ROOT, FFMPEG, comfy et
qwen_edit (celui du nouveau moteur, moteur/images.py), sans production.py. Le calcul (numpy, scipy, Pillow) tourne dans le Python de production.py
(python_embeded : mêmes versions, mêmes pixels) : lancer(). Sans Django."""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import types
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from fabrique.moteur.f1 import copies
from fabrique.moteur.f1.outils import ComfySimule, Outils, charger

BIREFNET = Path("ComfyUI") / "models" / "background_removal" / "BiRefNet-general.safetensors"  # = calques.BIREFNET, sous ComfyUI (CUI)
PILOTE = "import sys; sys.path.insert(0, sys.argv[1]); sys.dont_write_bytecode = True; from moteur import anim; anim.principal(*sys.argv[2:])"


def installer(racine, cfg: dict, comfy=None, qwen_edit=None):
    """calques.py et anime_calques.py importés tels quels (OUTILS/production en lecture, en dernier dans le chemin, sans __pycache__), leur
    `import production` servi par le remplaçant ; aussi l'initialisation de chaque processus d'animation. Renvoie le module calques."""
    p = sys.modules.get("production")
    if not getattr(p, "remplacant", False):
        p = sys.modules["production"] = types.ModuleType("production")
        p.remplacant = True
    p.CFG, p.ROOT, p.FFMPEG, p.comfy, p.qwen_edit = cfg, Path(racine), Outils(racine).ffmpeg, comfy, qwen_edit
    sys.dont_write_bytecode = True
    dossier = str(copies.DOSSIER)  # J10 : calques.py et anime_calques.py copiés dans l'app
    if dossier not in sys.path:
        sys.path.append(dossier)
    import anime_calques
    import calques
    assert calques.P is p and anime_calques.P is p, "calques.py déjà importé avec production.py dans ce processus"
    return calques


def faire(racine, dossier, data: dict, scenes: list[dict], cfg: dict, comfy=None, log=print):
    """= etape_anim (moteur calques), précédée de durees comme dans production.py (_etapes) : un clip par scène qui n'en a pas (Bramble à part)."""
    from moteur import images, montage

    dossier, o = Path(dossier), Outils(racine)
    montage.Montage(dossier, cfg, o).durees(scenes)
    d = dossier / "clips"
    d.mkdir(exist_ok=True)
    todo = [s for s in scenes if not s.get("bramble") and not (d / f"s{s['id']:03d}.mp4").exists()]
    if not todo:
        log("anim : deja faite")
        return
    if cfg.get("video_moteur", "wan") != "calques":  # LTX : reste à production.py
        raise RuntimeError(f"nouveau moteur : seul le moteur vidéo « calques » est repris (config.json -> video_moteur = {cfg.get('video_moteur', 'wan')!r})")
    log(f"anim : {len(todo)} scene(s), moteur calques 2,5D")
    comfy = comfy or o.module("kit", "comfy")
    calques = installer(racine, cfg, comfy, images.Images(dossier, cfg, o, {}, {}, {}, comfy=comfy).qwen_edit)
    cast, hero = data.get("cast", {}), (data.get("bqw") or {}).get("hero")
    W, H = cfg["sortie"]["largeur"], cfg["sortie"]["hauteur"]
    travaux, comfy_lance = [], False
    for k in sorted({s["_plan"] for s in todo}):  # 1. les calques de tous les plans (carte graphique, un plan après l'autre)
        plan_sc = [x for x in scenes if x.get("_plan") == k and not x.get("bramble")]
        if not plan_sc:
            continue
        first = plan_sc[0]
        img = dossier / "images" / f"plan_{first['id']:03d}.png"
        txt = (first.get("image") or "") + " " + " ".join(x.get("motion") or "" for x in plan_sc)
        noms = [n for n in cast if re.search(r"\b" + re.escape(n) + r"\b", txt)]
        cal_dir = None
        if noms:
            if not comfy_lance:
                comfy.start()
                comfy_lance = True
            cal_dir = dossier / "calques" / f"plan_{first['id']:03d}"
            calques.calques_plan(img, noms, cal_dir, W, H, log=log)
        travaux.append((plan_sc, cal_dir, img, d, hero, W, H))
    nb = max(1, min(cfg.get("calques", {}).get("processus", 6), (os.cpu_count() or 4) - 2))  # 2. l'animation de tous les plans en parallèle (processeur)
    t = time.time()
    log(f"anim : {len(travaux)} plan(s) a animer, {nb} processus")
    with ProcessPoolExecutor(max_workers=nb, initializer=installer, initargs=(str(racine), cfg)) as ex:
        for lignes in ex.map(calques.rendre_plan, travaux):
            for ligne in lignes:
                log(ligne)
    log(f"anim : {len(travaux)} plan(s) animes en {(time.time() - t) / 60:.1f} min")


class SansComfy:
    """ComfyUI interdit : les calques du plan sont déjà faits (animation seule, sans carte graphique)."""
    CUI = ""

    def start(self, *a, **k):
        pass

    def run(self, *a, **k):
        raise RuntimeError("ComfyUI interdit ici : des calques seraient à refaire (illustration changée depuis les calques ?)")


def principal(racine, dossier, scenario, mode="", fausse="", notes=""):
    """Dans le Python de production.py : faire() sur `dossier` et `scenario`, réglages lus sur l'entrée standard. Mode « capture » : ComfyUI simulé
    (consignes notées, sorties = copies de `fausse`) ; « sans_comfy » : ComfyUI interdit ; sinon le vrai (consignes notées). `notes` : consignes et journal."""
    cfg = json.loads(sys.stdin.read())
    data, scenes, _ = charger(Outils(racine), Path(scenario))
    consignes, journal = [], []
    if mode == "capture":
        comfy = ComfySimule(dossier, fausse)
        (Path(comfy.CUI) / BIREFNET).parent.mkdir(parents=True, exist_ok=True)
        (Path(comfy.CUI) / BIREFNET).touch()  # le masque passe par BiRefNet comme sur le PC (sans modèle, calques.py prendrait la plaque verte)
        consignes = comfy.consignes
    elif mode == "sans_comfy":
        comfy = SansComfy()
    else:
        comfy = Outils(racine).module("kit", "comfy")
        vrai = comfy.run
        comfy.run = lambda prompt, **kw: (consignes.append(json.loads(json.dumps(prompt))), vrai(prompt, **kw))[1]
    log = lambda *a: (journal.append(" ".join(str(x) for x in a)), print(*a, flush=True))
    try:
        faire(racine, dossier, data, scenes, cfg, comfy=comfy, log=log)
    finally:
        if notes:
            Path(notes).write_text(json.dumps({"consignes": consignes, "entrees": getattr(comfy, "entrees", []), "journal": journal}, ensure_ascii=False, indent=1),
                                   encoding="utf-8")


def lancer(racine, dossier, scenario, cfg: dict, mode: str = "", fausse="", notes="", log=None) -> str:
    """faire() joué par le Python de production.py (python_embeded) ; chaque ligne écrite passe à `log` dès qu'elle sort (journal en direct, plan par plan,
    comme production.py) ; renvoie tout ce qu'il a écrit, erreur s'il échoue."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    sortie = []
    with tempfile.TemporaryFile() as err:  # stderr dans un fichier : jamais de tube plein qui bloquerait la lecture de stdout
        p = subprocess.Popen([str(Outils(racine).python), "-B", "-c", PILOTE, str(Path(__file__).resolve().parents[1]), str(racine), str(dossier), str(scenario),
                              mode, str(fausse), str(notes)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, text=True, encoding="utf-8",
                             errors="replace", env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        p.stdin.write(json.dumps(cfg))
        p.stdin.close()
        for ligne in p.stdout:
            sortie.append(ligne)
            if log:
                log(ligne.rstrip("\n"))
        if p.wait() != 0:
            err.seek(0)
            raise RuntimeError(f"nouveau moteur (anim) : {(err.read().decode('utf-8', 'replace') or ''.join(sortie))[-2000:]}")
    return "".join(sortie)
