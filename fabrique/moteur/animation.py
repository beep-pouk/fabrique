"""Plan par plan (étape 5 du plan du 24/11) : des essais d'animation de chaque plan du découpage, refaits avec une consigne, comparés, le meilleur
gardé ; l'animatique monte l'essai gardé à la place du mouvement de caméra. Un essai = l'image du plan (celle de Bramble Studio, lue seulement),
cadrée comme le plan, animée par LTX-2.5 dans un ComfyUI à soi, celui des outils partagés lancé à part (graphe et réglages des essais de l'étape 2 : étage 1 à mi-taille,
étage 2 agrandi, caméra fixe, son de LTX jeté), à la durée du plan ; consigne de RT, sinon le mouvement que le script donne à la scène ; textes
et modèles : ceux de la session (reglages\\config.json → ltx). Carte : seulement libre (carte.py), rendue dès que Bramble Studio fabrique et au
plus 14 min par essai (règle du 24/11), 2 Go au plus déjà pris sur la carte avant de commencer. Mode simulation : la caméra glisse sur l'image, sans carte. Un essai à la fois (tâche détachée
« executer animation ») ; sortie : <session>\\animation\\<code>\\ (essais.json, <plan>_<n>.mp4)."""
import contextlib
import json
import logging
import math
import os
import random
import re
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

from django.conf import settings

from fabrique import dossiers, garde, programme
from fabrique.garde import Refus

log = logging.getLogger(__name__)
TACHE = "animation"
LIMITE_S = 14 * 60  # règle de RT (24/11) : 15 min de carte au plus par test, marge pour rendre la carte
CLE = re.compile(r"\d{1,5}\.\d{1,3}")
CONSIGNE_MAX = 600
PHRASE = re.compile(r"(?<=[.!?])\s+")
CAMERA = re.compile(r"\bcam[eé]ra\b", re.I)
FIXE = "The camera stays completely still, a locked-off shot."  # la caméra est celle du découpage, jamais celle de LTX
PORT = 8197  # ComfyUI à soi : celui de Bramble Studio (8188) n'est jamais touché
TASKKILL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")
CARTE_MAX_MO = 2048  # règle du 24/11 : un test seulement si la carte a moins de 2 Go pris


def dossier(s, code: str) -> Path:
    return garde.verifier(settings.SESSIONS / s.dossier / "animation" / code)


@contextlib.contextmanager
def _verrou(s, code: str):
    """essais.json lu puis réécrit par un seul à la fois, noyau et exécuteur détaché compris (verrou de fichier, comme f1/etape.py)."""
    import msvcrt

    d = dossier(s, code)
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "essais.lock", "a+") as f:
        for _ in range(100):
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise Refus("les essais de ce script sont occupés : réessayez dans un instant")
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def lire(s, code: str, strict: bool = False) -> dict:
    """{clé du plan: {"essais": [...], "garde": n (0 : aucun)}} ; `strict` (avant d'écrire) : un fichier illisible est refusé, jamais écrasé."""
    try:
        d = json.loads((dossier(s, code) / "essais.json").read_text(encoding="utf-8"))
        if not isinstance(d, dict) or not all(isinstance(p, dict) and isinstance(p.get("essais"), list) for p in d.values()):
            raise ValueError("forme inattendue")
        return d
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        if strict:
            raise Refus("les essais d'animation de ce script sont illisibles : rien n'est écrit") from None
        return {}


def _changer(s, code: str, cle: str, n: int, **champs):
    from fabrique.moteur.animatique import ecrire_json

    with _verrou(s, code):
        d = lire(s, code, strict=True)
        e = next((e for e in d.get(cle, {}).get("essais", []) if e["n"] == n), None)
        if e is None:
            raise Refus("essai inconnu")
        e.update(champs)
        ecrire_json(dossier(s, code) / "essais.json", d)


def gardes(s, code: str) -> dict[str, dict]:
    """Les essais gardés, prêts : {clé du plan: l'essai (source, cadre, duree), sa vidéo en `video`}. L'animatique ne le monte que sur un plan de
    même image et même cadre (une autre langue ou une autre version du script découpe autrement)."""
    d, ici = lire(s, code), dossier(s, code)
    gardes = {}
    for cle, p in d.items():
        e = next((e for e in p["essais"] if e["n"] == p.get("garde") and e.get("etat") == "fait"), None)
        if e and (ici / e["fichier"]).is_file():
            gardes[cle] = {**e, "video": str(ici / e["fichier"])}
    return gardes


def etat(s, code: str) -> dict:
    """Pour l'écran Épisode : les essais de chaque plan (vidéo, consigne, état), le gardé, l'essai qui tourne."""
    from fabrique.noyau import taches

    t = taches.lire(TACHE)
    vivante = taches.vivante(t)
    ici = dossier(s, code)
    plans = {}
    for cle, p in lire(s, code).items():
        essais = []
        for e in p["essais"]:
            et = e.get("etat", "")
            if et in ("attente", "en_cours") and not (vivante and (t.get("session"), t.get("code"), t.get("cle"), t.get("n")) == (s.id, code, cle, e["n"])):
                et, e = "erreur", {**e, "message": "l'essai s'est arrêté sans finir (PC éteint ?) : refaites-le"}
            essais.append({"n": e["n"], "consigne": e.get("consigne", ""), "etat": et, "message": e.get("message", ""), "simule": bool(e.get("simule")),
                           "video": str(ici / e["fichier"]) if et == "fait" else "", "date": e.get("date", ""), "duree": e.get("duree", 0.0),
                           "cadre": e.get("cadre", [])})
        plans[cle] = {"essais": essais, "garde": int(p.get("garde", 0))}
    return {"plans": plans, "occupe": bool(vivante), "ici": bool(vivante and (t.get("session"), t.get("code")) == (s.id, code))}


def _plan(s, code: str, langue: str, cle: str) -> dict:
    """Le plan `cle` de l'animatique montée en `langue` (repère : durée, cadre, image, scène)."""
    from fabrique.moteur import animatique

    try:
        p = json.loads((animatique.dossier(s) / f"{code}.{langue}" / "plans.json").read_text(encoding="utf-8"))
        r = next(r for r in p["plans"] if r.get("cle") == cle)
    except (OSError, ValueError, KeyError, StopIteration):
        raise Refus("ce plan n'est pas dans l'animatique : remontez-la puis réessayez") from None
    if r.get("valeur") == "bramble":
        raise Refus("Bramble a déjà ses lèvres qui bougent : son plan ne s'anime pas")
    return r


def demander(s, code: str, langue: str, cle: str, consigne: str, acteur: str) -> str:
    """Un nouvel essai du plan `cle` (consigne vide : le mouvement que le script donne à sa scène, sans ses phrases de caméra : la caméra est
    celle du découpage), lancé tout de suite si la carte est libre."""
    from fabrique.moteur import animatique, carte
    from fabrique.noyau import etat as etat_noyau
    from fabrique.noyau import taches
    from fabrique.noyau.models import noter

    if not CLE.fullmatch(cle):
        raise Refus("plan inconnu")
    contenu = animatique.contenu_du_script(s, code)
    r = _plan(s, code, animatique.verifier_langue(langue), cle)
    mouvement = next((str(sc.get("motion", "")) for sc in contenu.get("scenes", []) if str(sc.get("id")) == str(r.get("scene"))), "")
    consigne = " ".join(consigne.split()) or " ".join(p for p in PHRASE.split(" ".join(mouvement.split())) if not CAMERA.search(p))
    if not consigne:
        raise Refus("dites ce qui doit bouger dans ce plan")
    if len(consigne) > CONSIGNE_MAX:
        raise Refus(f"la consigne dépasse {CONSIGNE_MAX} caractères")
    simule = etat_noyau.simulation()
    with _verrou(s, code):  # vérifié et pris d'un coup : deux clics ne lancent jamais deux essais
        if taches.occupe(TACHE):
            raise Refus("un essai d'animation est déjà en cours : le suivant partira quand il aura fini (quelques minutes)")
        if not simule and (raison := carte.occupee() or ("un autre programme occupe la carte" if (g := carte.gpu()) and g[1] > CARTE_MAX_MO else "")):
            raise Refus(f"la carte graphique n'est pas libre ({raison}) : réessayez quand elle le sera")
        d = lire(s, code, strict=True)
        p = d.setdefault(cle, {"essais": [], "garde": 0})
        n = max((e["n"] for e in p["essais"]), default=0) + 1
        p["essais"].append({"n": n, "consigne": consigne, "graine": random.randint(1, 2**31 - 1), "etat": "attente", "duree": r["duree"],
                            "source": r["source"], "cadre": r["cadre"], "langue": langue, "simule": simule, "date": datetime.now().isoformat(timespec="minutes")})
        animatique.ecrire_json(dossier(s, code) / "essais.json", d)
        e = {"etat": "en_cours", "pid": 0, "lancee": datetime.now().isoformat(timespec="seconds"), "session": s.id, "code": code, "cle": cle, "n": n}
        taches.ecrire(TACHE, e)
    try:
        programme.lancer_detache("executer", TACHE, s.id, code, cle, str(n), journal=dossiers.donnees() / "journaux" / "sortie_animation.log")
    except Exception:  # noqa: BLE001 — sinon la tâche resterait « en cours » une minute
        log.exception("essai d'animation non lancé")
        taches.ecrire(TACHE, {**e, "etat": "erreur"})
        _changer(s, code, cle, n, etat="erreur", message="l'essai n'a pas pu démarrer")
        raise Refus("l'essai n'a pas pu démarrer : réessayer dans un instant") from None
    noter(acteur, TACHE, session=s.id, code=code, plan=cle, essai=n)
    return "Simulation : la caméra glisse sur l'image (quelques secondes)." if simule else "L'essai s'anime sur la carte graphique : 5 à 8 minutes."


def garder(s, code: str, cle: str, n: int, acteur: str) -> str:
    """Garde l'essai `n` du plan (0 : aucun, le plan reprend le mouvement de caméra) ; l'animatique le montera à la prochaine fois."""
    from fabrique.moteur import animatique
    from fabrique.noyau.models import noter

    animatique.contenu_du_script(s, code)
    with _verrou(s, code):
        d = lire(s, code, strict=True)
        p = d.get(cle) if CLE.fullmatch(cle) else None
        if p is None or (n and not any(e["n"] == n and e.get("etat") == "fait" for e in p["essais"])):
            raise Refus("essai inconnu ou pas encore fini")
        p["garde"] = n
        animatique.ecrire_json(dossier(s, code) / "essais.json", d)
    noter(acteur, "garder_essai", session=s.id, code=code, plan=cle, essai=n)
    return "Essai gardé : remontez l'animatique pour le voir à sa place." if n else "Le plan reprend le mouvement de caméra."


def executer(session_id: str = "", code: str = "", cle: str = "", n: str = "0") -> int:
    from fabrique.noyau import taches
    from fabrique.noyau.models import Session

    e0 = taches.lire(TACHE)
    if int(e0.get("pid", 0)) not in (0, os.getpid()) and taches.vivante(e0):  # un autre essai tourne : jamais deux sur la carte
        print("un essai d'animation est déjà en cours")
        return 3
    e = {"etat": "en_cours", "pid": os.getpid(), "lancee": datetime.now().isoformat(timespec="seconds"), "session": session_id, "code": code,
         "cle": cle, "n": int(n)}
    taches.ecrire(TACHE, e)
    try:
        sortie = faire(Session.objects.get(id=session_id), code, cle, int(n))
    except Exception as x:  # noqa: BLE001 — dite à RT (écran Épisode), le détail dans le journal
        log.exception("essai d'animation raté")
        taches.ecrire(TACHE, {**e, "etat": "erreur", "fin": datetime.now().isoformat(timespec="seconds"), "message": str(x)[:300]})
        return 1
    taches.ecrire(TACHE, {**e, "etat": "fait", "fin": datetime.now().isoformat(timespec="seconds")})
    print(f"essai fait : {sortie}")
    return 0


def faire(s, code: str, cle: str, n: int) -> Path:
    """L'essai `n` du plan `cle` : animé (simulé s'il a été demandé en simulation), noté fait ; un échec est noté sur l'essai, dit simplement."""
    try:
        essai = next(x for x in lire(s, code, strict=True)[cle]["essais"] if x["n"] == n)
    except (KeyError, StopIteration):
        raise Refus("essai inconnu") from None
    _changer(s, code, cle, n, etat="en_cours")
    sortie = dossier(s, code) / f"{cle}_{n}.mp4"
    try:
        (simuler if essai.get("simule") else animer)(s, essai, sortie)
    except Exception as x:
        _changer(s, code, cle, n, etat="erreur", message=str(x)[:300] if isinstance(x, Refus) else "l'essai a échoué (détail dans le journal de Fabrique)")
        raise
    _changer(s, code, cle, n, etat="fait", fichier=sortie.name)
    return sortie


def _outils(s):
    from fabrique.moteur.f1.outils import Lieux, Outils

    return Outils(Lieux(garde.studio_bramble() or dossiers.racine().parent, settings.SESSIONS / s.dossier))


def simuler(s, essai: dict, sortie: Path):
    """Mode simulation : la caméra s'approche lentement dans le cadre du plan (sans carte)."""
    from fabrique.moteur import decoupage

    o = _outils(s)
    cx, cy, t = essai["cadre"]
    decoupage.filmer(o.run, o.ffmpeg, Path(essai["source"]), [{"duree": essai["duree"], "de": [cx, cy, t], "a": [cx, cy, round(t * 0.9, 4)]}],
                     sortie, 1280, 720, 25)


def entree(source: Path, cadre: list[float], W: int, H: int):
    """L'image du plan cadrée comme lui ([cx, cy, taille] en fractions, taille = part de la largeur, forme 16:9), à W×H."""
    from PIL import Image

    with Image.open(source) as im:
        cx, cy, t = cadre
        k = max(W / im.width, H / im.height) / t  # comme decoupage.filmer : l'image mise en W×H (centrée), le cadre en fractions de celle-ci
        im = im.convert("RGB").resize((math.ceil(im.width * k), math.ceil(im.height * k)), Image.LANCZOS)
        g, d = (im.width - W / t) / 2, (im.height - H / t) / 2
        x0 = round(min(max(g + cx * W / t - W / 2, g), g + W / t - W))
        y0 = round(min(max(d + cy * H / t - H / 2, d), d + H / t - H))
        return im.crop((x0, y0, x0 + W, y0 + H))


def images_ltx(duree: float, fps: int) -> int:
    return 8 * math.ceil((duree * fps - 1) / 8) + 1  # LTX : 8n + 1 images


def graphe(l: dict, consigne: str, graine: int, image: str, prefixe: str, duree: float) -> dict:
    """Le graphe de l'étape 2 (deux étages, LoRA distillée au second), réglages `l` = config.json → ltx de la session."""
    L = lambda n, i=0: [str(n), i]  # noqa: E731
    W, H, fps = int(l["largeur"]), int(l["hauteur"]), int(l["fps"])
    nf = images_ltx(duree, fps)
    texte = " ".join(x for x in (l.get("style", ""), consigne, FIXE, l.get("ancre_corps", "") if l.get("ancre_corps_actif") else "", l.get("son", "")) if x)
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image}},
        "2": {"class_type": "LTXVPreprocess", "inputs": {"image": L(1), "img_compression": int(l.get("img_compression", 18))}},
        "3": {"class_type": "UNETLoader", "inputs": {"unet_name": l["modele"], "weight_dtype": "default"}},
        "4": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": L(3), "lora_name": l["lora_distillee"], "strength_model": 1.0}},
        "5": {"class_type": "CLIPLoader", "inputs": {"clip_name": l["encodeur"], "type": "ltxv"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": texte, "clip": L(5)}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": l.get("negatif", ""), "clip": L(5)}},
        "8": {"class_type": "LTXVConditioning", "inputs": {"positive": L(6), "negative": L(7), "frame_rate": float(fps)}},
        "9": {"class_type": "VAELoader", "inputs": {"vae_name": "ltx-2.5-video-vae-bf16.safetensors"}},
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": "ltx-2.5-audio-vae-bf16.safetensors"}},
        "11": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": W // 2, "height": H // 2, "length": nf, "batch_size": 1}},
        "12": {"class_type": "LTXVImgToVideoInplace", "inputs": {"vae": L(9), "image": L(2), "latent": L(11), "strength": float(l.get("force_image_etage1", 0.8)), "bypass": False}},
        "13": {"class_type": "LTXVEmptyLatentAudio", "inputs": {"frames_number": nf, "frame_rate": fps, "batch_size": 1, "audio_vae": L(10)}},
        "14": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": L(12), "audio_latent": L(13)}},
        "15": {"class_type": "RandomNoise", "inputs": {"noise_seed": graine}},
        "16": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
        "17": {"class_type": "LTXVScheduler", "inputs": {"steps": int(l.get("pas", 30)), "max_shift": 2.05, "base_shift": 0.95, "stretch": True, "terminal": 0.1, "latent": L(14)}},
        "18": {"class_type": "LTXVDualCFGGuider", "inputs": {"model": L(3), "positive": L(8), "negative": L(8, 1), "video_cfg": float(l.get("cfg", 4.0)), "audio_cfg": 1.0}},
        "19": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": L(15), "guider": L(18), "sampler": L(16), "sigmas": L(17), "latent_image": L(14)}},
        "20": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": L(19)}},
        "21": {"class_type": "LatentUpscaleModelLoader", "inputs": {"model_name": "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"}},
        "22": {"class_type": "LTXVLatentUpsampler", "inputs": {"samples": L(20), "upscale_model": L(21), "vae": L(9)}},
        "23": {"class_type": "LTXVImgToVideoInplace", "inputs": {"vae": L(9), "image": L(2), "latent": L(22), "strength": 1.0, "bypass": False}},
        "24": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": L(23), "audio_latent": L(20, 1)}},
        "25": {"class_type": "RandomNoise", "inputs": {"noise_seed": 42}},
        "26": {"class_type": "ManualSigmas", "inputs": {"sigmas": "0.85, 0.7250, 0.4219, 0.0"}},
        "27": {"class_type": "LTXVDualCFGGuider", "inputs": {"model": L(4), "positive": L(8), "negative": L(8, 1), "video_cfg": 1.0, "audio_cfg": 1.0}},
        "28": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": L(25), "guider": L(27), "sampler": L(16), "sigmas": L(26), "latent_image": L(24)}},
        "29": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": L(28)}},
        "30": {"class_type": "VAEDecodeTiled", "inputs": {"samples": L(29), "vae": L(9), "tile_size": 512, "overlap": 64, "temporal_size": 64, "temporal_overlap": 16}},
        "31": {"class_type": "SaveImage", "inputs": {"images": L(30), "filename_prefix": prefixe}},
    }


def animer(s, essai: dict, sortie: Path):
    """L'essai sur la carte, dans un ComfyUI à soi (port à part, dossiers à soi : celui de Bramble Studio n'est jamais touché), arrêté à la fin :
    carte rendue. Arrêté aussi dès que Bramble Studio fabrique (vu deux fois de suite à 20 s d'écart : un état illisible un instant ne compte
    pas) ou après 14 min."""
    from fabrique.moteur import carte
    from fabrique.moteur.f1.outils import composant

    o = _outils(s)
    l = json.loads((settings.SESSIONS / s.dossier / "reglages" / "config.json").read_text(encoding="utf-8"))["ltx"]
    cui, io = composant(o.racine, "comfyui"), dossiers.donnees() / "comfy_animation"
    for d in ("input", "output", "temp", "user"):
        (io / d).mkdir(parents=True, exist_ok=True)
    try:
        _http("/system_stats")
        raise Refus("un autre programme se sert déjà du port de l'essai : réessayez plus tard")
    except (OSError, ValueError):
        pass  # personne n'écoute : le port est à nous
    prefixe = f"essai_{uuid.uuid4().hex[:10]}"
    entree(Path(essai["source"]), essai["cadre"], int(l["largeur"]), int(l["hauteur"])).save(io / "input" / f"{prefixe}.png")
    journal = dossiers.donnees() / "journaux" / "comfyui_animation.log"
    journal.parent.mkdir(parents=True, exist_ok=True)
    with open(journal, "ab") as sortie_cui:
        pr = subprocess.Popen([str(cui / "python_embeded" / "python.exe"), "-s", r"ComfyUI\main.py", "--windows-standalone-build", "--disable-auto-launch",
                               "--port", str(PORT), *(x for d in ("input", "output", "temp", "user") for x in (f"--{d}-directory", str(io / d)))],
                              cwd=str(cui), stdout=sortie_cui, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    t0, alertes, prochain, demande = time.monotonic(), 0, 0.0, None
    try:
        while True:
            if pr.poll() is not None:
                raise RuntimeError("ComfyUI s'est arrêté seul (journal comfyui_animation.log)")
            if time.monotonic() - t0 > LIMITE_S:
                raise Refus("essai arrêté pour rendre la carte : la limite de 14 min est atteinte")
            if time.monotonic() >= prochain:
                prochain = time.monotonic() + 20
                alertes = alertes + 1 if (raison := carte.bramble(datetime.now())) else 0
                if alertes >= 2:
                    raise Refus(f"essai arrêté pour rendre la carte : {raison}")
            try:
                if demande is None:
                    _http("/system_stats")  # prêt ?
                    try:
                        demande = _http("/prompt", {"prompt": graphe(l, essai["consigne"], essai["graine"], f"{prefixe}.png", prefixe, essai["duree"]),
                                                    "client_id": prefixe})["prompt_id"]
                    except urllib.error.HTTPError as x:
                        raise RuntimeError(f"ComfyUI refuse le graphe : {x.read().decode(errors='replace')[:2000]}") from None
                elif demande in (h := _http(f"/history/{demande}")):
                    if h[demande].get("status", {}).get("status_str") == "error":
                        raise RuntimeError("erreur de ComfyUI : " + json.dumps(h[demande]["status"].get("messages", [])[-2:], ensure_ascii=False)[:2000])
                    break
            except (OSError, ValueError):
                pass  # pas encore prêt, ou occupé à charger les modèles
            time.sleep(1 if demande is None else 5)
        images = sorted((io / "output").glob(f"{prefixe}_*.png"))
        if not images:
            raise RuntimeError("ComfyUI n'a rendu aucune image")
        o.run([o.ffmpeg, "-y", "-v", "error", "-framerate", str(l["fps"]), "-start_number", "1", "-i", str(io / "output" / f"{prefixe}_%05d_.png"),
               "-t", f"{essai['duree']:.3f}", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", str(sortie)])
    finally:
        subprocess.run([TASKKILL, "/PID", str(pr.pid), "/T", "/F"], capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        pr.wait(60)
        for f in [io / "input" / f"{prefixe}.png", *(io / "output").glob(f"{prefixe}_*.png")]:
            f.unlink(missing_ok=True)


def _http(chemin: str, donnees=None):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{chemin}", json.dumps(donnees).encode() if donnees is not None else None, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())
