"""Outils de la chanson (J9 : F5), une section de chanson étant un plan. Selon la brique :
- chant (carte) : ACE-Step 1.5 par ComfyUI, le flux de F1 (f1/musique.workflow) avec les paroles et leurs balises de section au lieu de
  « [Instrumental] », le style du script (tags, tempo, tonalité), une durée tirée du nombre de lignes et du tempo ; puis le calage des paroles :
  Whisper large-v3 de Linux (whisper_mots_wsl.py, horodatage par mot) aligné sur les paroles connues (paroles.caler) → chaque mot, chaque
  section a son heure ; « compris » = la part des mots retrouvés (contrôle) ; Whisper muet : les mots sont répartis, « compris » à 0 ;
- animation (sans carte, « simulable ») : la caméra de F4 (par_plan.filmer) sur l'image de la section, à la durée de la section dans la chanson
  (la plus longue des langues : le montage coupe à la sienne) ;
- montage (sans carte, « simulable ») : chaque clip aux bornes de sa section (en images entières), la chanson entière, sous-titres karaoké
  incrustés (karaoke.ass, le mot surligné à son moment) quand le format les demande, video.srt par ligne chantée."""
import json
import subprocess
from pathlib import Path

from fabrique.moteur import paroles, par_plan
from fabrique.moteur.outils import Demande, Estimation, Fiche, Resultat

BALISES = {"intro": "Intro", "couplet": "Verse", "refrain": "Chorus", "pont": "Bridge", "fin": "Outro"}
TEMPS_PAR_LIGNE, TEMPS_SANS_PAROLES = 8, 16  # en temps de la mesure : une ligne de comptine ≈ 2 mesures, une intro ou une fin ≈ 4


def estimer(fiche: Fiche, demande: Demande) -> Estimation:
    return Estimation(secondes=float(fiche.reglages.get("secondes", 10)), carte_go=fiche.besoins.carte_go)


def duree_visee(sc: dict) -> float:
    """La durée demandée à ACE-Step : les lignes et les sections sans paroles au tempo du script, de 30 s à 4 min."""
    temps = sum(TEMPS_PAR_LIGNE * len(s.get("paroles", [])) or TEMPS_SANS_PAROLES for s in sc["sections"])
    return round(min(240.0, max(30.0, temps * 60 / sc["musique"]["bpm"])))


def texte_chante(sc: dict) -> str:
    return "\n\n".join(f"[{BALISES[s['type']]}]" + "".join(f"\n{l}" for l in s.get("paroles", [])) for s in sc["sections"])


def chant(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    from fabrique.moteur.f1 import musique
    from fabrique.moteur.f1.outils import Outils, dans_wsl, wsl
    from fabrique.moteur.f1.voix import wslq

    L = par_plan.lieux(d)
    cfg, o = par_plan.config(d, L), Outils(L)
    sc = paroles.script_de(d)
    m, langue = sc["musique"], (d.langue or "en").split("-")[0]
    cle = m["tonalite"]
    for a, b in musique.KEYS.items():
        cle = cle.replace(a, b)
    w = musique.workflow(m["tags"], m["bpm"], cle, duree_visee(sc), d.graine % 2**31, cfg)
    w["4"]["inputs"].update(lyrics=texte_chante(sc), language=langue)
    comfy = o.module("kit", "comfy")
    try:
        comfy.start()
        sortie = comfy.run(w, timeout=3600)[0]
    finally:
        comfy.stop()  # la carte libérée avant Whisper (et pour Bramble Studio), même après une erreur
    wav = dossier / "chanson.wav"
    o.run([o.ffmpeg, "-y", "-v", "error", "-i", sortie, "-ar", "48000", "-ac", "2", wav])
    total, entendus = par_plan.duree(wav), []
    lu = dossier / "_entendus.json"
    try:  # Whisper bloqué (Linux) : pas d'attente sans fin ; les mots sont alors répartis, « compris » à 0 (le contrôle le dit)
        subprocess.run(wsl(f"cd {dans_wsl('longcat')} && ./venv/bin/python {wslq(Path(__file__).with_name('whisper_mots_wsl.py'))} {wslq(wav)} {langue} "
                           f"{dans_wsl('whisper')} {wslq(lu)}"), capture_output=True, timeout=1800, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        entendus = json.loads(lu.read_text(encoding="utf-8"))
        lu.unlink()
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass
    mots, compris = paroles.caler(paroles.mots_du_texte(sc["sections"]), entendus, total)
    return Resultat(fichiers=["chanson.wav"], duree_s=round(total, 3),
                    infos={"mots": mots, "sections": paroles.bornes(sc["sections"], mots, total), "compris": round(compris, 3), "entendus": len(entendus)})


def bornes_du_chant(f: Path) -> list[dict]:
    return json.loads((f.parent / "resultat.json").read_text(encoding="utf-8"))["infos"]["sections"]


def animation(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    image = (par_plan.principaux(d, ("images",)) or [None])[0]
    chants = [Path(f) for e, fs in d.entrees.items() if d.sources.get(e) == "chant" for f in fs if f.lower().endswith(".wav")]
    if image is None or not chants:
        raise RuntimeError("l'animation d'une section demande avant elle le chant et les images dans la recette")
    secondes = max([1.0, *(b["fin"] - b["debut"] for c in chants for b in bornes_du_chant(c) if b["id"] == d.unite)])
    mouvement = d.consigne.get("mouvement", "avancee")
    if mouvement == "fixe" and (max_s := d.reglages.get("plan_fixe_max_s")) and secondes > max_s:
        mouvement = "avancee"  # jamais une image tenue sans mouvement au-delà de la limite du format
    return par_plan.filmer(image, mouvement, secondes, d, dossier)


def montage(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    from fabrique.moteur import montages
    from fabrique.moteur.faux import programme
    from fabrique.publication import publication

    chants, clips = par_plan.principaux(d, ("chant",)), par_plan.principaux(d, ("animation",))
    if len(chants) != 1:
        raise RuntimeError("le montage d'une chanson demande le chant de sa langue avant lui dans la recette")
    infos = json.loads((chants[0].parent / "resultat.json").read_text(encoding="utf-8"))["infos"]
    sections, mots = infos["sections"], infos["mots"]
    if len(clips) != len(sections):
        raise RuntimeError(f"une image animée par section attendue ({len(clips)} clips, {len(sections)} sections)")
    l, h = par_plan.CADRES.get(d.reglages.get("cadre", "16:9"), par_plan.CADRES["16:9"])
    total = sections[-1]["fin"]
    parties, plans = [], []
    for i, (b, c) in enumerate(zip(sections, clips)):
        n = max(1, round(b["fin"] * par_plan.IPS) - round(b["debut"] * par_plan.IPS))  # bornes en images entières : aucune dérive sur la chanson
        fondu = (",fade=t=in:d=0.5" if i == 0 else "") + (f",fade=t=out:st={max(0, n / par_plan.IPS - 1):.3f}:d=1" if i == len(sections) - 1 else "")
        partie = dossier / f"_p{i:04d}.mkv"
        par_plan.lancer("ffmpeg", "-nostdin", "-y", "-v", "error", "-i", c, "-filter_complex",
                        f"[0:v]scale={l}:{h}:force_original_aspect_ratio=increase,crop={l}:{h},setsar=1,fps={par_plan.IPS},"
                        f"tpad=stop_mode=clone:stop_duration={n / par_plan.IPS:.3f},trim=end_frame={n},setpts=PTS-STARTPTS{fondu}[v]",
                        "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", partie)
        parties.append(partie)
        plans.append({"unite": b["id"], "debut": b["debut"], "fin": b["fin"]})
    (liste := dossier / "_liste.txt").write_text("".join(f"file '{p.name}'\n" for p in parties), encoding="utf-8")
    par_plan.lancer("ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", liste, "-c", "copy", dossier / "_joint.mkv")
    segs = paroles.segments(mots)
    incruster = d.reglages.get("sous_titres") == "incrustes" and bool(segs)
    if incruster:
        (dossier / "karaoke.ass").write_text(paroles.ass(mots, l, h), encoding="utf-8")
    montages.lancer(programme("ffmpeg"), "-nostdin", "-y", "-v", "error", "-i", "_joint.mkv", "-i", chants[0], "-map", "0:v", "-map", "1:a",
                    *(("-vf", "subtitles=karaoke.ass") if incruster else ()), "-af", f"afade=t=out:st={max(0, total - 1.5):.3f}:d=1.5",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", "video.mp4", cwd=dossier)  # « subtitles » lit un chemin relatif (un chemin Windows complet demande des échappements)
    for f in [*parties, liste, dossier / "_joint.mkv"]:
        f.unlink()
    fichiers = ["video.mp4", *(["karaoke.ass"] if incruster else [])]
    if segs:
        (dossier / "video.srt").write_text(publication.srt(segs), encoding="utf-8")
        fichiers.append("video.srt")
    return Resultat(fichiers=fichiers, duree_s=round(par_plan.duree(dossier / "video.mp4"), 3), infos={"plans": plans, "incrustes": len(segs) if incruster else 0})


def fabriquer(fiche: Fiche, demande: Demande, dossier: Path) -> Resultat:
    return {"chant": chant, "animation": animation, "montage": montage}[demande.brique](fiche, demande, dossier)
