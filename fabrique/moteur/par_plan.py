"""Outils réels par plan (J8 : F4 voix off + images, et F3 créée seule), tirés des étapes de F1 : mêmes outils partagés de Bramble Studio (lus
seulement), mêmes réglages (reglages\\config.json de la session), mêmes graines. Une étape qui demande la carte fait d'un coup tous les morceaux
de sa langue dans l'atelier de la vidéo (le modèle n'est chargé qu'une fois par étape, plan § 5.3), puis chaque morceau lie le sien ; une
coupure reprend aux fichiers qui manquent. Selon la brique :
- voix (carte) : une phrase par plan ; anglais : Chatterbox, graine 42, Whisper réécoute (f1/voix.py) ; autre langue : l'outil de voix de la
  langue dans la session (f1/langue.py) ; sous le seuil de F1, refaite avec une autre graine (3 essais) ; le score va au contrôle ;
- images (carte) : Qwen-Image par ComfyUI (f1/images.py), la consigne du plan et le style de la session, au cadre du format, graine 1000 + n ;
- musique (carte, par vidéo) : ACE-Step par ComfyUI (f1/musique.py), morceaux enchaînés en fondu, à la durée de la voix montée ;
- animation (sans carte, « simulable ») : mouvement de caméra sur l'image (zoompan de ffmpeg), à la durée de la plus longue voix du plan ;
- montage (sans carte, « simulable ») : chaque clip à la durée de sa voix + une pause, voix, musique sous la voix, fondus, sous-titres par plan.
Le n d'un plan est son rang dans le script (1, 2…) : voix\\s001.wav, images\\plan_001.png dans l'atelier."""
import json
from pathlib import Path

from fabrique.moteur.outils import Demande, Estimation, Fiche, Resultat

PAUSE_S = 0.6  # après chaque phrase (pause_apres_phrase_s de F1)
IPS = 25
CADRES = {"16:9": (1920, 1080), "9:16": (1080, 1920)}
MUSIQUE_DB = -20  # la musique sous la voix


def estimer(fiche: Fiche, demande: Demande) -> Estimation:
    return Estimation(secondes=float(fiche.reglages.get("secondes", 10)), carte_go=fiche.besoins.carte_go)


# ---- ce que les étapes partagent ----

def lieux(d: Demande):
    from fabrique import dossiers, garde
    from fabrique.moteur.f1.outils import Lieux

    return Lieux(garde.studio_bramble() or dossiers.racine().parent, Path(d.session))


def config(d: Demande, L) -> dict:
    f = Path(d.session) / "reglages" / "config.json"
    if not f.is_file():
        raise RuntimeError(f"la session n'a pas de réglages des outils réels ({f.name}) : seules les sessions reprises de Bramble Studio en ont")
    return L.config(json.loads(f.read_text(encoding="utf-8")))


def plans(d: Demande) -> list[dict]:
    """Les plans du script dans l'ordre, dans la langue du morceau (sa traduction posée à côté du script, si elle existe)."""
    script = Path(d.script)
    if d.langue and (t := script.with_name(f"{script.stem}.{d.langue}.json")).is_file():
        script = t
    return [{"unite": f"{sc['id']}/{p['id']}", **p} for sc in json.loads(script.read_text(encoding="utf-8"))["scenes"] for p in sc["plans"]]


def rang(d: Demande, tous: list[dict]) -> int:
    return next(n for n, p in enumerate(tous, 1) if p["unite"] == d.unite)


def lier(source: Path, cible: Path):
    from fabrique.moteur.f1.adaptateur import lier as f1

    if not source.is_file():
        raise RuntimeError(f"l'outil n'a pas écrit {source.name}")
    f1(source, cible)


def principaux(d: Demande, briques: tuple[str, ...]) -> list[Path]:
    """Le fichier principal de chaque morceau de la dernière étape d'avant faite par l'une de ces briques, dans l'ordre des plans."""
    etapes = [e for e, b in d.sources.items() if b in briques and d.entrees.get(e)]
    if not etapes:
        return []
    return list({Path(f).parent: Path(f) for f in reversed(d.entrees[etapes[-1]])}.values())[::-1]  # le premier de chaque dossier de morceau


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
    (atelier / "voix").mkdir(parents=True, exist_ok=True)
    tous = plans(d)
    scenes = [{"id": n, "narration": p["texte"]} for n, p in enumerate(tous, 1)]
    if (d.langue or "en") == "en":
        controle, seuil = f1.faire(o, atelier, scenes, cfg), cfg.get("controle_voix_seuil", 0.93)
    else:
        journal: list[str] = []
        controle, seuil = langue.voix(o, atelier, scenes, langue_de(Path(d.session), d.langue), cfg["voix"]["ref_audio"], log=journal.append), langue.SEUIL
    n = rang(d, tous)
    lier(atelier / "voix" / f"s{n:03d}.wav", dossier / "voix.wav")
    c = controle.get(str(n))  # absent : Whisper n'a pas pu réécouter (Linux), comme F1
    return Resultat(fichiers=["voix.wav"], duree_s=duree(dossier / "voix.wav"),
                    infos={"mots": None, "controle": {"score": c.get("score"), "entendu": c.get("entendu", ""), "seuil": seuil} if c else None})


def images(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    from fabrique.moteur.f1.images import Images
    from fabrique.moteur.f1.outils import Outils

    L = lieux(d)
    cfg, o, atelier = config(d, L), Outils(L), Path(d.atelier)
    (atelier / "images").mkdir(parents=True, exist_ok=True)
    tous = plans(d)
    l, h = cfg["images"]["largeur"], cfg["images"]["hauteur"]
    if d.reglages.get("cadre") == "9:16":
        l, h = h, l
    todo = [(n, p) for n, p in enumerate(tous, 1) if not (atelier / "images" / f"plan_{n:03d}.png").is_file()]
    if todo:
        regles = json.loads(L.regles().read_text(encoding="utf-8")) if L.regles().is_file() else {}
        im = Images(atelier, cfg, o, regles, {}, {})
        im.comfy.start()
        try:
            for n, p in todo:
                consigne = im.sans_outils(p["image"]).strip().rstrip(".")
                im.qwen_image(f"{consigne}. Style: {cfg.get('style', '')}", atelier / "images" / f"plan_{n:03d}.png", seed=1000 + n, w=l, h=h)
        finally:
            im.comfy.stop()  # la carte libérée pour l'étape suivante (et pour Bramble Studio)
    lier(atelier / "images" / f"plan_{rang(d, tous):03d}.png", dossier / "image.png")
    return Resultat(fichiers=["image.png"])


def musique(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    from fabrique.moteur.f1 import musique as f1
    from fabrique.moteur.f1.outils import Outils

    L = lieux(d)
    cfg, o = config(d, L), Outils(L)
    voix_ = principaux(d, ("voix",))
    if not voix_:
        raise RuntimeError("la musique demande une étape de voix avant elle dans la recette")
    total = sum(duree(v) + PAUSE_S for v in voix_)
    try:
        lier(f1.faire(o, Path(d.atelier), {}, total, cfg), dossier / "musique.wav")
    finally:
        o.module("kit", "comfy").stop()  # la carte libérée (F1 l'arrête à la fin de chaque étape) ; sans effet s'il ne tourne pas
    return Resultat(fichiers=["musique.wav"], duree_s=round(total, 3))


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
    secondes = max([duree(v) for v in voix_], default=3.0) + PAUSE_S  # toutes les langues : le montage coupe à la sienne
    mouvement = d.consigne.get("mouvement", "avancee")
    if mouvement == "fixe" and (max_s := d.reglages.get("plan_fixe_max_s")) and secondes > max_s:
        mouvement = "avancee"  # jamais une image tenue sans mouvement au-delà de la limite du format (F1 v2)
    l, h = CADRES.get(d.reglages.get("cadre", "16:9"), CADRES["16:9"])
    z, x, y = camera(mouvement, secondes)
    n = max(1, round(secondes * IPS))
    lancer("ffmpeg", "-nostdin", "-y", "-v", "error", "-loop", "1", "-i", image, "-filter_complex",  # l'image doublée d'abord : zoompan sans saccades
           f"scale={2 * l}:{2 * h}:force_original_aspect_ratio=increase,crop={2 * l}:{2 * h},zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={l}x{h}:fps={IPS},format=yuv420p",
           "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", dossier / "clip.mp4")
    return Resultat(fichiers=["clip.mp4"], duree_s=round(n / IPS, 3), infos={"mouvement": mouvement})


def montage(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    from fabrique.publication import publication

    voix_, clips = principaux(d, ("voix",)), principaux(d, ("animation", "levres"))
    if not voix_ or len(voix_) != len(clips):
        raise RuntimeError(f"le montage par plan demande une voix et un clip par plan ({len(voix_)} voix, {len(clips)} clips)")
    musique_ = [p for p in principaux(d, ("musique",)) if p.suffix.lower() == ".wav"]
    l, h = CADRES.get(d.reglages.get("cadre", "16:9"), CADRES["16:9"])
    parties, segs, plans_, debut = [], [], [], 0.0
    for i, (v, c) in enumerate(zip(voix_, clips)):
        dv = duree(v)
        n = max(1, round((dv + PAUSE_S) * IPS))  # en images entières : ni dérive ni trou d'un plan à l'autre
        fondu = (",fade=t=in:d=0.5" if i == 0 else "") + (f",fade=t=out:st={max(0, n / IPS - 1):.3f}:d=1" if i == len(voix_) - 1 else "")
        partie = dossier / f"_p{i:04d}.mkv"
        lancer("ffmpeg", "-nostdin", "-y", "-v", "error", "-i", c, "-i", v, "-filter_complex",
               f"[0:v]scale={l}:{h}:force_original_aspect_ratio=increase,crop={l}:{h},setsar=1,fps={IPS},tpad=stop_mode=clone:stop_duration={n / IPS:.3f},"
               f"trim=end_frame={n},setpts=PTS-STARTPTS{fondu}[v];[1:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={n / IPS:.3f}[a]",
               "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", partie)
        parties.append(partie)
        dem = json.loads((v.parent / "demande.json").read_text(encoding="utf-8")) if (v.parent / "demande.json").is_file() else {}  # le texte dans la langue
        if dem.get("texte", "").strip():
            segs.append({"start": debut, "end": debut + dv, "text": " ".join(dem["texte"].split())})
        plans_.append({"unite": dem.get("unite", ""), "debut": round(debut, 3), "fin": round(debut + n / IPS, 3)})
        debut += n / IPS
    (liste := dossier / "_liste.txt").write_text("".join(f"file '{p.name}'\n" for p in parties), encoding="utf-8")
    lancer("ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", liste, "-c", "copy", dossier / "_joint.mkv")
    son = (f"[0:a]volume=1[voix];[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={MUSIQUE_DB}dB,atrim=duration={debut:.3f}[m];"
           f"[voix][m]amix=inputs=2:duration=first:normalize=0,afade=t=out:st={max(0, debut - 1):.3f}:d=1[a]") if musique_ else \
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
    return {"voix": voix, "images": images, "musique": musique, "animation": animation, "montage": montage}[demande.brique](fiche, demande, dossier)
