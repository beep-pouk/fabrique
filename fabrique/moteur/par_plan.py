"""Outils réels par plan (J8 : F4 voix off + images, et F3 créée seule), tirés des étapes de F1 : mêmes outils partagés de Bramble Studio (lus
seulement), mêmes réglages (reglages\\config.json de la session), mêmes graines. Une étape qui demande la carte fait d'un coup tous les morceaux
de sa langue (ou de la vidéo) dans l'atelier : le modèle n'est chargé qu'une fois par étape (plan § 5.3), puis chaque morceau lie le sien.
Un lot en cours est marqué (_lot_en_cours) : coupé (PC éteint, exécuteur tué), son dernier fichier écrit, peut-être à moitié, est rangé dans
_coupes et refait ; le reste n'est jamais refait. Selon la brique :
- voix (carte) : une phrase par plan ; anglais : Chatterbox, graine 42, Whisper réécoute (f1/voix.py) ; autre langue : l'outil de voix de la
  langue dans la session (f1/langue.py) ; sous le seuil de F1, refaite avec une autre graine (3 essais) ; le score va au contrôle ; un seul lot
  par langue (_lot.json : Whisper n'est pas relancé à chaque morceau s'il a échoué) ;
- images (carte) : Qwen-Image par ComfyUI (f1/images.py), la consigne du plan, le style et le négatif de la session, au cadre du format, graine
  1000 + n ; une image à cadre blanc refaite (4 essais, comme F1) ; présentateur (F6) : ses plans face caméra ont une seule image, cadrée par
  Qwen-Image-Edit de F1 d'après la référence du personnage copiée avec la vidéo (presentateur.png) ;
- lèvres (carte, F6) : plans face caméra = LongCat-Video-Avatar 1.5 par le lanceur de F1 (lipsync_batch.py, un lot par langue, ComfyUI arrêté
  d'abord) sur l'image cadrée et la voix du plan ; un insert = la caméra sur son image ;
- musique (carte, commune aux langues) : ACE-Step par ComfyUI (f1/musique.py), morceaux enchaînés en fondu, à la durée de la plus longue langue ;
- animation (sans carte, « simulable ») : mouvement de caméra sur l'image (zoompan de ffmpeg), à la durée de la plus longue voix du plan ;
- montage (sans carte, « simulable ») : chaque clip à la durée de sa voix + la pause de F1, voix, musique sous la voix, fondus, sous-titres par plan.
Le n d'un plan est son rang dans le script (1, 2…) : voix\\s001.wav, images\\plan_001.png dans l'atelier. « lot » (infos) : les fichiers faits
par cet appel (les chronos de l'étape s'y divisent ; 0 : rien de calculé)."""
import json
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from fabrique.moteur.outils import Demande, Estimation, Fiche, Resultat

PAUSE_S = 0.6  # après chaque phrase, sans réglage de la session (pause_apres_phrase_s de F1)
MUSIQUE_DB = -20  # la musique sous la voix, sans réglage de la session (musique_volume_db de F1)
IPS = 25
CADRES = {"16:9": (1920, 1080), "9:16": (1080, 1920)}


def estimer(fiche: Fiche, demande: Demande) -> Estimation:
    return Estimation(secondes=float(fiche.reglages.get("secondes", 10)), carte_go=fiche.besoins.carte_go)


# ---- ce que les étapes partagent ----

def lieux(d: Demande):
    from fabrique import dossiers, garde
    from fabrique.moteur.f1.outils import Lieux

    return Lieux(garde.studio_bramble() or dossiers.racine().parent, Path(d.session))


def reglages_session(d: Demande) -> dict:
    f = Path(d.session) / "reglages" / "config.json"
    return json.loads(f.read_text(encoding="utf-8")) if d.session and f.is_file() else {}


def config(d: Demande, L) -> dict:
    if not (cfg := reglages_session(d)):
        raise RuntimeError("la session n'a pas de réglages des outils réels (reglages\\config.json) : seules les sessions reprises de Bramble Studio en ont")
    return L.config(cfg)


def pause(d: Demande) -> float:
    return float(reglages_session(d).get("pause_apres_phrase_s", PAUSE_S))


def plans(d: Demande) -> list[dict]:
    """Les plans du script dans l'ordre, dans la langue du morceau (sa traduction posée à côté du script, si elle existe)."""
    script = Path(d.script)
    if d.langue and (t := script.with_name(f"{script.stem}.{d.langue}.json")).is_file():
        script = t
    s = json.loads(script.read_text(encoding="utf-8"))
    if "sections" in s:  # une chanson : une section = un plan (ses paroles pour texte)
        return [{**x, "unite": x["id"], "texte": "\n".join(x.get("paroles", []))} for x in s["sections"]]
    defaut = {"vue": "face"} if "presentateur" in s else {}  # F6 : un plan sans vue est face caméra (recettes.PlanPresentateur)
    return [{"unite": f"{sc['id']}/{p['id']}", **defaut, **p} for sc in s["scenes"] for p in sc["plans"]]


def rang(d: Demande, tous: list[dict]) -> int:
    return next(n for n, p in enumerate(tous, 1) if p["unite"] == d.unite)


def lier(source: Path, cible: Path):
    from fabrique.moteur.f1.adaptateur import lier as f1

    if not source.is_file():
        raise RuntimeError(f"l'outil n'a pas écrit {source.name}")
    f1(source, cible)


@contextmanager
def lot(dossier: Path, motifs: list[str]):
    """Marque un lot en cours ; si celui d'avant a été coupé, son dernier fichier écrit (les outils écrivent l'un après l'autre) est rangé dans
    _coupes\\<heure>, pour être refait. Le marqueur reste après une erreur : le lot suivant se méfie aussi."""
    dossier.mkdir(parents=True, exist_ok=True)
    marque = dossier / "_lot_en_cours"
    if marque.exists():
        depuis = marque.stat().st_mtime
        if faits := [f for m in motifs for f in dossier.glob(m) if f.is_file() and f.stat().st_mtime >= depuis]:
            dernier = max(faits, key=lambda f: f.stat().st_mtime)
            (vers := dossier / "_coupes" / time.strftime("%Y%m%d_%H%M%S") / dernier.relative_to(dossier)).parent.mkdir(parents=True, exist_ok=True)
            dernier.replace(vers)  # deux coupures dans la même seconde : la dernière gardée
    marque.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    yield
    marque.unlink()


def principaux(d: Demande, briques: tuple[str, ...]) -> list[Path]:
    """Le fichier principal de chaque morceau de la dernière étape d'avant faite par l'une de ces briques, dans l'ordre des plans."""
    etapes = [e for e, b in d.sources.items() if b in briques and d.entrees.get(e)]
    if not etapes:
        return []
    return list({Path(f).parent: Path(f) for f in reversed(d.entrees[etapes[-1]])}.values())[::-1]  # le premier de chaque dossier de morceau


def demande_de(f: Path) -> dict:
    """La demande du morceau qui a rendu ce fichier (son texte dans sa langue, son unité)."""
    return json.loads((f.parent / "demande.json").read_text(encoding="utf-8")) if (f.parent / "demande.json").is_file() else {}


def duree(f: Path) -> float:
    from fabrique.moteur import montages

    return montages.mesure(f)["duree_s"]


def lancer(*args):
    from fabrique.moteur import montages
    from fabrique.moteur.faux import programme

    return montages.lancer(programme(args[0]), *args[1:])


# ---- carte : voix, images, musique ----

def voix(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    from fabrique.moteur.f1 import langue, voix as f1
    from fabrique.moteur.f1.adaptateur import langue_de
    from fabrique.moteur.f1.outils import Outils

    L = lieux(d)
    cfg, o, atelier = config(d, L), Outils(L), Path(d.atelier)
    v = atelier / "voix"
    tous = plans(d)
    n, anglais = rang(d, tous), (d.langue or "en") == "en"
    avant = set(v.glob("s*.wav"))
    if not ((v / f"s{n:03d}.wav").is_file() and (v / "_lot.json").is_file()):  # le lot de la langue : fait une fois, repris s'il manque une voix
        scenes = [{"id": i, "narration": p["texte"]} for i, p in enumerate(tous, 1)]
        with lot(v, ["s*.wav"]):
            if anglais:
                f1.faire(o, atelier, scenes, cfg)
            else:
                langue.voix(o, atelier, scenes, langue_de(Path(d.session), d.langue), cfg["voix"]["ref_audio"], log=lambda *a: None)
        (v / "_lot.json").write_text(json.dumps({"fait": time.strftime("%Y-%m-%d %H:%M:%S"), "voix": len(tous)}), encoding="utf-8")
    lier(v / f"s{n:03d}.wav", dossier / "voix.wav")
    controle = json.loads((v / "_controle.json").read_text(encoding="utf-8")) if (v / "_controle.json").is_file() else {}
    c, seuil = controle.get(str(n)), cfg.get("controle_voix_seuil", 0.93) if anglais else langue.SEUIL
    return Resultat(fichiers=["voix.wav"], duree_s=duree(dossier / "voix.wav"), infos={
        "mots": None, "lot": len(set(v.glob("s*.wav")) - avant),
        "controle": {"score": c.get("score"), "entendu": c.get("entendu", ""), "seuil": seuil} if c else None})  # None : Whisper n'a pas pu réécouter (Linux)


def images(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    from fabrique.moteur.f1.images import Images
    from fabrique.moteur.f1.outils import Outils

    L = lieux(d)
    cfg, o, atelier = config(d, L), Outils(L), Path(d.atelier)
    i = atelier / "images"
    tous = plans(d)
    vertical = d.reglages.get("cadre") == "9:16"
    l, h = cfg["images"]["largeur"], cfg["images"]["hauteur"]
    l, h = (h, l) if vertical else (l, h)
    with lot(i, ["plan_*.png", "presentateur.png"]):
        todo = [(n, p) for n, p in enumerate(tous, 1) if p.get("vue") != "face" and not (i / f"plan_{n:03d}.png").is_file()]
        cadrer = any(p.get("vue") == "face" for p in tous) and not (i / "presentateur.png").is_file()
        if todo or cadrer:
            regles = json.loads(L.regles().read_text(encoding="utf-8")) if L.regles().is_file() else {}
            im = Images(atelier, cfg, o, regles, {}, {})
            try:
                im.comfy.start()
                if cadrer:
                    face_camera(im, d, cfg, i / "presentateur.png", l, h)
                for n, p in todo:  # la consigne d'un décor de F1 : style, consigne du plan, cadre plein
                    prompt = ", ".join([cfg.get("style_histoire", cfg.get("style", "")), im.sans_outils(p["image"]).strip().rstrip("."),
                                        f"filling the whole frame, {'tall 9:16' if vertical else 'wide 16:9'} composition"])
                    for essai in range(4):
                        im.qwen_image(prompt, i / f"plan_{n:03d}.png", seed=1000 + n + 100 * essai, w=l, h=h, neg=cfg.get("negatif_histoire"))
                        if not im.bord_blanc(i / f"plan_{n:03d}.png"):
                            break
            finally:
                im.comfy.stop()  # la carte libérée pour l'étape suivante (et pour Bramble Studio), même après une erreur
    n = rang(d, tous)
    lier(i / ("presentateur.png" if tous[n - 1].get("vue") == "face" else f"plan_{n:03d}.png"), dossier / "image.png")
    return Resultat(fichiers=["image.png"], infos={"lot": len(todo) + cadrer})


def face_camera(im, d: Demande, cfg: dict, cible: Path, l: int, h: int):
    """Le cadrage face caméra du présentateur (F6) : Qwen-Image-Edit de F1, le personnage garde l'apparence de sa référence (copiée avec la
    vidéo à la préparation), tête et épaules, au centre, le regard vers le spectateur, dans son décor ; une image à cadre blanc refaite."""
    s = json.loads(Path(d.script).read_text(encoding="utf-8"))
    if (ref := next(Path(d.script).parent.glob("_presentateur.*"), None)) is None:
        raise RuntimeError("la référence du présentateur n'a pas été copiée avec la vidéo (préparation d'avant J10 ?)")
    prompt = (f"{s['presentateur']} from Picture 1, same face, colours and clothes, faces the camera and talks to the viewer: head and shoulders, "
              f"centered, eyes looking straight at the viewer, mouth closed, in {im.sans_outils(s['decor']).strip().rstrip('.')}. "
              f"{cfg.get('style_histoire', cfg.get('style', ''))}, filling the whole frame, {'tall 9:16' if h > l else 'wide 16:9'} composition")
    for essai in range(4):
        im.qwen_edit(prompt, [ref], cible, seed=7 + 100 * essai, w=l, h=h, negatif=cfg.get("negatif_histoire"))
        if not im.bord_blanc(cible):
            break


def musique(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    from fabrique.moteur.f1 import musique as f1
    from fabrique.moteur.f1.outils import Outils

    L = lieux(d)
    cfg, o, atelier = config(d, L), Outils(L), Path(d.atelier)
    totaux: dict[str, float] = {}
    for v in principaux(d, ("voix",)):  # toutes les langues : la musique est commune, à la durée de la plus longue
        langue_ = demande_de(v).get("langue", "")
        totaux[langue_] = totaux.get(langue_, 0) + duree(v) + pause(d)
    if not totaux:
        raise RuntimeError("la musique demande une étape de voix avant elle dans la recette")
    try:
        with lot(atelier, ["musique/m*.wav", "musique.wav"]):
            deja = (atelier / "musique.wav").is_file()
            lier(f1.faire(o, atelier, {}, max(totaux.values()), cfg), dossier / "musique.wav")
    finally:
        o.module("kit", "comfy").stop()  # la carte libérée (F1 l'arrête à la fin de chaque étape) ; sans effet s'il ne tourne pas
    return Resultat(fichiers=["musique.wav"], duree_s=round(max(totaux.values()), 3), infos={"lot": 0 if deja else 1})


# ---- sans carte : animation, montage ----

def camera(mouvement: str, secondes: float) -> tuple[str, str, str]:
    """zoompan : (zoom, x, y) d'un mouvement sur `secondes` ; l'ampleur suit la durée (1 % par seconde, de 8 à 40 %) : mesuré sur une image de
    F1, un plan de 15 s bouge de 0,41 (avancée) à 0,58 (panoramique) au détecteur de la revue, au-dessus de son seuil de 0,2."""
    a, n = min(0.4, max(0.08, 0.01 * secondes)), max(1, round(secondes * IPS))
    centre_x, centre_y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    return {"fixe": ("1", centre_x, centre_y),
            "avancee": (f"1+{a}*on/{n}", centre_x, centre_y),
            "recul": (f"1+{a}-{a}*on/{n}", centre_x, centre_y),
            "droite": (f"1+{a}", f"(iw-iw/zoom)*on/{n}", centre_y),
            "gauche": (f"1+{a}", f"(iw-iw/zoom)*(1-on/{n})", centre_y)}[mouvement]


def animation(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    image = (principaux(d, ("images",)) or [None])[0]
    if image is None:
        raise RuntimeError("l'animation demande une étape d'images avant elle dans la recette")
    voix_ = [Path(f) for e, fs in d.entrees.items() if d.sources.get(e) == "voix" for f in fs if f.lower().endswith(".wav")]
    secondes = max([duree(v) for v in voix_], default=3.0) + pause(d)  # toutes les langues : le montage coupe à la sienne
    return filmer(image, d.consigne.get("mouvement", "avancee"), secondes, d, dossier)


def filmer(image: Path, mouvement: str, secondes: float, d: Demande, dossier: Path) -> Resultat:
    """clip.mp4 : la caméra sur l'image pendant `secondes`, au cadre du format."""
    if mouvement == "fixe" and (max_s := d.reglages.get("plan_fixe_max_s")) and secondes > max_s:
        mouvement = "avancee"  # jamais une image tenue sans mouvement au-delà de la limite du format (F1 v2)
    l, h = CADRES.get(d.reglages.get("cadre", "16:9"), CADRES["16:9"])
    z, x, y = camera(mouvement, secondes)
    n = max(1, round(secondes * IPS))
    lancer("ffmpeg", "-nostdin", "-y", "-v", "error", "-loop", "1", "-i", image, "-filter_complex",  # l'image doublée d'abord : zoompan sans saccades
           f"scale={2 * l}:{2 * h}:force_original_aspect_ratio=increase,crop={2 * l}:{2 * h},zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={l}x{h}:fps={IPS},format=yuv420p",
           "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", dossier / "clip.mp4")
    return Resultat(fichiers=["clip.mp4"], duree_s=round(n / IPS, 3), infos={"mouvement": mouvement})


def du_plan(f: Path, d: Demande, unite: str) -> Path:
    """Le fichier principal du morceau `unite` de la même étape et de la même langue que `f` (le fichier principal du plan de `d`)."""
    base = f.parents[d.unite.count("/") + 1]
    return base / unite / json.loads((base / unite / "resultat.json").read_text(encoding="utf-8"))["fichiers"][0]


def levres(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    """F6 : un plan face caméra = LongCat-Video-Avatar 1.5 par le lanceur de F1 (f1/bramble.py : lipsync_batch.py dans le venv Linux de LongCat),
    tous les plans face de la langue en un lot (un seul chargement), chacun sur son image cadrée et sa voix ; ComfyUI arrêté d'abord. Le
    mouvement du clip est mesuré (celui de la revue de F1) : un présentateur figé est un défaut du contrôle. Un insert = la caméra sur son image."""
    image, voix_ = (principaux(d, ("images",)) or [None])[0], (principaux(d, ("voix",)) or [None])[0]
    if image is None or voix_ is None:
        raise RuntimeError("les lèvres demandent une étape de voix et une étape d'images avant elles dans la recette")
    if d.consigne.get("vue") != "face":  # un insert : sa voix continue sur son image
        r = filmer(image, d.consigne.get("mouvement", "avancee"), duree(voix_) + pause(d), d, dossier)
        r.infos["lot"] = 0  # shortcut: aucun chrono pour un insert (il fausserait la médiane des plans face), estimé comme un plan face ; à séparer si l'estimation de F6 gêne
        return r
    from fabrique.moteur.f1 import copies, mouvement
    from fabrique.moteur.f1.outils import Outils, composant, dans_wsl, wsl
    from fabrique.moteur.f1.voix import wslp, wslq
    from fabrique.moteur.faux import programme

    L = lieux(d)
    cfg, o, atelier = config(d, L), Outils(L), Path(d.atelier)
    tous, dl = plans(d), atelier / "levres"
    sortie = dl / f"s{rang(d, tous):03d}.mp4"
    prompt = (f"{json.loads(Path(d.script).read_text(encoding='utf-8'))['presentateur']} talks to the viewer, natural lip movements matching "
              f"the speech, gentle head motion, blinking. {cfg.get('lipsync_prompt_plus', '')}").strip()
    with lot(dl, ["s*.mp4"]):  # toujours : un lot coupé range d'abord son dernier clip (peut-être à moitié écrit), même si celui-ci est fait
        jobs = [{"image": wslp(du_plan(image, d, p["unite"])), "audio": wslp(du_plan(voix_, d, p["unite"])), "out": wslp(dl / f"s{k:03d}"),
                 "prompt": prompt, "resolution": cfg.get("lipsync_resolution", "480p")}
                for k, p in enumerate(tous, 1) if p.get("vue") == "face" and not (dl / f"s{k:03d}.mp4").is_file()]
        if jobs:
            o.module("kit", "comfy").stop()  # la carte libérée pour LongCat
            (jf := dl / "_jobs.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=1), encoding="utf-8")
            prod = wslq(copies.DOSSIER)
            cmd = ("cd " + dans_wsl("longcat") + " && cp " + prod + "/lipsync_batch.py . && OFFLOAD_DIR=" + prod + " STOP_FILE="
                   + wslq(composant(L, "kit", "STOP_LIPSYNC")) + " ./venv/bin/torchrun --nproc_per_node=1 --master_port=29512 lipsync_batch.py --jobs "
                   + wslq(jf) + ("" if cfg.get("lipsync_distill", True) else " --full"))
            with open(dl / "lipsync.log", "a", encoding="utf-8") as journal:
                r = subprocess.run(wsl(cmd), stdout=journal, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode or not sortie.is_file():
                raise RuntimeError("LongCat a échoué : voir levres\\lipsync.log dans l'atelier")
    lier(sortie, dossier / "clip.mp4")
    s, dv = duree(dossier / "clip.mp4"), duree(voix_)
    parle = dossier / "_parle.mp4"  # le mouvement mesuré pendant la phrase seulement (LongCat complète son dernier segment en silence)
    lancer("ffmpeg", "-nostdin", "-y", "-v", "error", "-i", dossier / "clip.mp4", "-t", f"{min(s, dv):.3f}", "-an", "-c:v", "libx264", "-preset", "ultrafast", parle)
    morceaux = mouvement.plans(programme("ffmpeg"), parle, min(s, dv))
    parle.unlink()
    bouge = sum(p["mouvement"] * (p["fin"] - p["debut"]) for p in morceaux) / max(min(s, dv), 0.001)
    return Resultat(fichiers=["clip.mp4"], duree_s=round(s, 3), infos={"vue": "face", "lot": len(jobs), "mouvement": round(bouge, 3), "voix_s": round(dv, 3)})


def montage(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    from fabrique.publication import publication

    voix_, clips = principaux(d, ("voix",)), principaux(d, ("animation", "levres"))
    if not voix_ or len(voix_) != len(clips):
        raise RuntimeError(f"le montage par plan demande une voix et un clip par plan ({len(voix_)} voix, {len(clips)} clips)")
    musique_ = [p for p in principaux(d, ("musique",)) if p.suffix.lower() == ".wav"]
    l, h = CADRES.get(d.reglages.get("cadre", "16:9"), CADRES["16:9"])
    blanc, volume = pause(d), float(reglages_session(d).get("musique_volume_db", MUSIQUE_DB))
    parties, segs, plans_, debut = [], [], [], 0.0
    for i, (v, c) in enumerate(zip(voix_, clips)):
        dv = duree(v)
        n = max(1, round((dv + blanc) * IPS))  # en images entières : ni dérive ni trou d'un plan à l'autre
        fondu = (",fade=t=in:d=0.5" if i == 0 else "") + (f",fade=t=out:st={max(0, n / IPS - 1):.3f}:d=1" if i == len(voix_) - 1 else "")
        partie = dossier / f"_p{i:04d}.mkv"
        lancer("ffmpeg", "-nostdin", "-y", "-v", "error", "-i", c, "-i", v, "-filter_complex",
               f"[0:v]scale={l}:{h}:force_original_aspect_ratio=increase,crop={l}:{h},setsar=1,fps={IPS},tpad=stop_mode=clone:stop_duration={n / IPS:.3f},"
               f"trim=end_frame={n},setpts=PTS-STARTPTS{fondu}[v];[1:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={n / IPS:.3f}[a]",
               "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", partie)
        parties.append(partie)
        dem = demande_de(v)  # le texte dans la langue du morceau
        if dem.get("texte", "").strip():
            segs.append({"start": debut, "end": debut + dv, "text": " ".join(dem["texte"].split())})
        plans_.append({"unite": dem.get("unite", ""), "debut": round(debut, 3), "fin": round(debut + n / IPS, 3)})
        debut += n / IPS
    (liste := dossier / "_liste.txt").write_text("".join(f"file '{p.name}'\n" for p in parties), encoding="utf-8")
    lancer("ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", liste, "-c", "copy", dossier / "_joint.mkv")
    son = (f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={volume}dB,atrim=duration={debut:.3f}[m];"
           f"[0:a][m]amix=inputs=2:duration=first:normalize=0,afade=t=out:st={max(0, debut - 1):.3f}:d=1[a]") if musique_ else \
        f"[0:a]afade=t=out:st={max(0, debut - 1):.3f}:d=1[a]"
    lancer("ffmpeg", "-nostdin", "-y", "-v", "error", "-i", dossier / "_joint.mkv", *(("-i", musique_[0]) if musique_ else ()), "-filter_complex", son,
           "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", dossier / "video.mp4")
    for f in [*parties, liste, dossier / "_joint.mkv"]:
        f.unlink()
    fichiers = ["video.mp4"]
    if segs:
        (dossier / "video.srt").write_text(publication.srt(segs), encoding="utf-8")
        fichiers.append("video.srt")
    return Resultat(fichiers=fichiers, duree_s=round(duree(dossier / "video.mp4"), 3), infos={"plans": plans_})


def fabriquer(fiche: Fiche, demande: Demande, dossier: Path) -> Resultat:
    return {"voix": voix, "images": images, "musique": musique, "animation": animation, "levres": levres, "montage": montage}[demande.brique](fiche, demande, dossier)
