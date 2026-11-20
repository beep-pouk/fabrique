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
ESSAIS = 3  # une chanson dont Whisper retrouve trop peu de paroles est refaite avec une autre graine (comme la voix de F1), la meilleure gardée
WHISPER_S = 1800


def estimer(fiche: Fiche, demande: Demande) -> Estimation:
    return Estimation(secondes=float(fiche.reglages.get("secondes", 10)), carte_go=fiche.besoins.carte_go)


def duree_visee(sc: dict) -> float:
    """La durée demandée à ACE-Step : celle des lignes et des sections sans paroles au tempo du script (recettes.duree_chantee), d'une à 4 min."""
    from fabrique.moteur import recettes

    return round(min(recettes.DUREE_CHANSON_MAX, max(recettes.DUREE_CHANSON_MIN, recettes.duree_chantee(sc))))


def texte_chante(sc: dict) -> str:
    return "\n\n".join(f"[{BALISES[s['type']]}]" + "".join(f"\n{l}" for l in s.get("paroles", [])) for s in sc["sections"])


def tonalite(t: str) -> str:
    """« B-flat major » → « Bb major » (l'écriture du nœud d'ACE-Step)."""
    return t.replace("-sharp", "#").replace("-flat", "b")


def ecouter(chanson: Path, langue: str) -> tuple[list[dict], str]:
    """(mots entendus par Whisper, erreur en clair) ; Whisper bloqué : arrêté dans Linux aussi (la carte rendue), jamais d'attente sans fin."""
    from fabrique.moteur.f1.outils import dans_wsl, wsl
    from fabrique.moteur.f1.voix import wslq

    lu = chanson.with_name("_entendus.json")
    script = Path(__file__).with_name("whisper_mots_wsl.py")
    try:
        r = subprocess.run(wsl(f"cd {dans_wsl('longcat')} && ./venv/bin/python {wslq(script)} {wslq(chanson)} {langue} {dans_wsl('whisper')} {wslq(lu)}"),
                           capture_output=True, timeout=WHISPER_S, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        subprocess.run(wsl("pkill -f whisper_mots_wsl.py"), capture_output=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return [], f"bloqué plus de {WHISPER_S // 60} min"
    except OSError as e:
        return [], f"Linux injoignable ({e})"
    try:
        entendus = json.loads(lu.read_text(encoding="utf-8"))
        lu.unlink()
        return entendus, ""
    except (OSError, ValueError):
        return [], (r.stderr or r.stdout or b"").decode("utf-8", "replace").strip()[-300:] or f"code {r.returncode}"


def chant(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    from fabrique.moteur.f1 import musique
    from fabrique.moteur.f1.outils import Outils

    L = par_plan.lieux(d)
    cfg, o = par_plan.config(d, L), Outils(L)
    cfg = {**cfg, "musique": {**cfg.get("musique", {}), **{k: v for k, v in fiche.reglages.items() if k != "secondes"}}}  # la fiche choisit son modèle et ses réglages
    sc = paroles.script_de(d)
    m, langue = sc["musique"], (d.langue or "en").split("-")[0]
    texte, mots_voulus, garde = texte_chante(sc), paroles.mots_du_texte(sc["sections"]), None
    for essai in range(ESSAIS):
        w = musique.workflow(m["tags"], m["bpm"], tonalite(m.get("tonalite", "C major")), duree_visee(sc), (d.graine + 1000 * essai) % 2**31, cfg)
        w["4"]["inputs"].update(lyrics=texte, language=langue)
        comfy = o.module("kit", "comfy")
        try:
            comfy.start()
            sortie = comfy.run(w, timeout=3600)[0]
        finally:
            comfy.stop()  # la carte libérée avant Whisper (et pour Bramble Studio), même après une erreur
        wav = dossier / f"_essai{essai}.wav"
        o.run([o.ffmpeg, "-y", "-v", "error", "-i", sortie, "-ar", "48000", "-ac", "2", wav])
        total = par_plan.duree(wav)
        entendus, erreur = ecouter(wav, langue)
        mots, compris = paroles.caler(mots_voulus, entendus, total)
        if garde is None or compris > garde["compris"]:
            garde = {"wav": wav, "total": total, "mots": mots, "compris": compris, "entendus": len(entendus), "erreur": erreur, "essai": essai + 1}
        if compris >= paroles.COMPRIS_MIN or erreur:  # Whisper en panne : refaire la chanson n'y changerait rien
            break
    garde["wav"].rename(dossier / "chanson.wav")
    for f in dossier.glob("_essai*.wav"):
        f.unlink()
    return Resultat(fichiers=["chanson.wav"], duree_s=round(garde["total"], 3), infos={
        "mots": garde["mots"], "sections": paroles.bornes(sc["sections"], garde["mots"], garde["total"]), "compris": round(garde["compris"], 3),
        "entendus": garde["entendus"], "essais": garde["essai"], **({"whisper_erreur": garde["erreur"]} if garde["erreur"] else {})})


def bornes_du_chant(f: Path) -> list[dict]:
    return json.loads((f.parent / "resultat.json").read_text(encoding="utf-8"))["infos"]["sections"]


def animation(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    image = (par_plan.principaux(d, ("images",)) or [None])[0]
    chants = [Path(f) for e, fs in d.entrees.items() if d.sources.get(e) == "chant" for f in fs if f.lower().endswith(".wav")]
    if image is None or not chants:
        raise RuntimeError("l'animation d'une section demande avant elle le chant et les images dans la recette")
    secondes = max([1.0, *(b["fin"] - b["debut"] for c in chants for b in bornes_du_chant(c) if b["id"] == d.unite)])
    return par_plan.filmer(image, d.consigne.get("mouvement", "avancee"), secondes, d, dossier)


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
