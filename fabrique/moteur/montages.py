"""Outils réels sans carte de F2 et F3 (ffmpeg, quelques secondes à quelques minutes ; permis en simulation : « simulable »). Selon la brique :
- assemblage (F2, repris de core/compilations.py de Bramble) : l'introduction puis les vidéos finies, bout à bout (copie quand tout est au
  même format, sinon réencodé au cadre de la recette) ; un chapitre par partie ; sous-titres de chaque partie décalés (video.srt) ;
- verticale (F3) : un extrait d'une vidéo finie (F3 tirée d'une vidéo longue) ou le montage de la vidéo (F3 seule), 1080 × 1920 sur son propre
  fond flouté (repris des paquets prêts à poster), sous-titres de la source incrustés, décalés au début de l'extrait ;
- miniature : une image de la vidéo montée (au tiers), au cadre de la recette ;
- controle : contrôle technique de la vidéo montée (ffprobe) : durée dans les bornes de la recette, cadre, son, sous-titres incrustés quand le
  format les demande ; un défaut « forte » est bloquant pour la vérification (Vérification le montre, la recette du jalon l'exige absent).
Les vidéos sources sont les vidéos finales de la session (execution.finale), par langue."""
import json
import re
from pathlib import Path

from fabrique.moteur.outils import Demande, Estimation, Fiche, Resultat

CADRES = {"16:9": (1920, 1080), "9:16": (1080, 1920)}
FORMAT = ("codec_name", "profile", "width", "height", "pix_fmt", "sample_aspect_ratio", "r_frame_rate", "time_base", "sample_rate", "channels", "channel_layout")  # bout à bout sans réencoder : tout égal
BLOC_SRT = re.compile(r"(\d+:\d+:\d+[,.]\d+)\s*-->\s*(\d+:\d+:\d+[,.]\d+)[^\n]*\n(.+?)(?:\n\s*\n|\Z)", re.S)


def estimer(fiche: Fiche, demande: Demande) -> Estimation:
    return Estimation(secondes=float(fiche.reglages.get("secondes", 20)))


def sources(demande: Demande, ids: list[str]) -> list[tuple[Path, str]]:
    """(vidéo finale, titre) de chaque vidéo de la session, dans la langue du morceau (celle du script pour un morceau commun)."""
    from fabrique.moteur import execution
    from fabrique.noyau import routeur
    from fabrique.noyau.models import Session
    from fabrique.session.models import Video

    s = Session.objects.get(dossier=Path(demande.session).name)
    with routeur.session(s):
        titres = dict(Video.objects.filter(id__in=ids).values_list("id", "titre"))
    return [(execution.finale(s, i, demande.langue), titres.get(i, i)) for i in ids]


def script(demande: Demande) -> dict:
    return json.loads(Path(demande.script).read_text(encoding="utf-8"))


def lancer(*args, cwd: Path | None = None) -> str:
    """ffmpeg ou ffprobe, caché (paquets.outil) ; `cwd` : le filtre « subtitles » lit un chemin relatif (un chemin Windows complet y demande des
    échappements)."""
    from fabrique.publication import paquets

    return paquets.outil(*args, delai=6 * 3600, cwd=cwd)


def mesure(f: Path) -> dict:
    from fabrique.moteur.faux import programme

    r = json.loads(lancer(programme("ffprobe"), "-v", "error", "-show_entries", f"stream={','.join(FORMAT)},codec_type:format=duration", "-of", "json", f))
    v = next((x for x in r["streams"] if x["codec_type"] == "video"), {})
    a = next((x for x in r["streams"] if x["codec_type"] == "audio"), {})
    return {"largeur": v.get("width", 0), "hauteur": v.get("height", 0), "duree_s": float(r["format"].get("duration") or 0), "son": bool(a),
            "format": tuple((x.get(k) for x in (v, a) for k in FORMAT))}


def sous_titres(video: Path) -> list[dict]:
    """Les sous-titres d'une vidéo finale : <vidéo>.srt ou sous_titres.srt à côté, sinon sa transcription (segments start / end / text) ; pour une
    vidéo de F1, ceux de son atelier (final\\, où l'analyse écrit la transcription : le morceau n'en garde que la vidéo)."""
    from fabrique.publication import publication

    racine = next((p for p in video.parents if p.parent.name == "videos"), None)  # videos\<id>
    ateliers = sorted(racine.glob(f"*/atelier/*/final/{video.name}")) if racine else []
    sec = lambda t: sum(float(x) * m for x, m in zip(t.replace(",", ".").split(":"), (3600, 60, 1)))  # noqa: E731
    for v in (video, *ateliers):
        for f in (v.with_suffix(".srt"), v.with_name("sous_titres.srt")):
            if f.is_file():  # un bloc illisible est sauté
                return [{"start": sec(a), "end": sec(b), "text": " ".join(t.split())} for a, b, t in BLOC_SRT.findall(f.read_text(encoding="utf-8-sig").replace("\r", ""))]
        if segs := publication.segments(v):
            return segs
    return []


def assemblage(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    from fabrique.moteur.faux import programme
    from fabrique.publication import publication

    sc = script(d)
    parties = sources(d, [sc["intro"], *sc["videos"]])
    mesures = [mesure(v) for v, _ in parties]
    sortie = dossier / "video.mp4"
    if len({m["format"] for m in mesures}) == 1:  # même chaîne de fabrication : bout à bout sans réencoder
        (liste := dossier / "liste.txt").write_text("".join(f"file '{v.as_posix()}'\n" for v, _ in parties), encoding="utf-8")
        lancer(programme("ffmpeg"), "-nostdin", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", liste, "-c", "copy", "-movflags", "+faststart", sortie)
        liste.unlink()
    else:
        l, h = CADRES.get(d.reglages.get("cadre", "16:9"), CADRES["16:9"])
        entrees = [x for v, _ in parties for x in ("-i", v)]
        son = lambda i, m: (f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]" if m["son"]  # noqa: E731
                            else f"anullsrc=r=48000:cl=stereo,atrim=duration={m['duree_s']:.3f}[a{i}]")  # une partie muette : du silence de sa durée
        filtres = ";".join(f"[{i}:v]scale={l}:{h}:force_original_aspect_ratio=decrease,pad={l}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25[v{i}];{son(i, m)}"
                           for i, m in enumerate(mesures))
        lancer(programme("ffmpeg"), "-nostdin", "-y", "-v", "error", *entrees, "-filter_complex",
               filtres + ";" + "".join(f"[v{i}][a{i}]" for i in range(len(parties))) + f"concat=n={len(parties)}:v=1:a=1[v][a]",
               "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
               "-movflags", "+faststart", sortie)
    chapitres, segs, debut = [], [], 0.0
    for (v, titre), m in zip(parties, mesures):
        chapitres.append({"debut": round(debut, 3), "titre": "Introduction" if not chapitres else titre})
        segs += [{**x, "start": float(x["start"]) + debut, "end": float(x["end"]) + debut} for x in sous_titres(v)]
        debut += m["duree_s"]
    fichiers = [sortie.name]
    if segs:
        (dossier / "video.srt").write_text(publication.srt(segs), encoding="utf-8")
        fichiers.append("video.srt")
    return Resultat(fichiers=fichiers, duree_s=round(mesure(sortie)["duree_s"], 3), infos={"chapitres": chapitres})


def verticale(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    from fabrique.moteur.faux import programme
    from fabrique.publication import paquets, publication

    sc = script(d)
    video = sources(d, [sc["source"]])[0][0] if "source" in sc else montee(d)  # un extrait d'une vidéo longue, ou le montage de cette vidéo (F3 seule)
    m = mesure(video)
    a, b = (float(sc["debut_s"]), min(float(sc["fin_s"]), m["duree_s"])) if "source" in sc else (0.0, m["duree_s"])
    if b - a < 1:
        raise RuntimeError(f"extrait vide : la vidéo source dure {m['duree_s']:.1f} s")
    l, h = CADRES["9:16"]
    segs = [{**x, "start": max(0.0, float(x["start"]) - a), "end": min(b, float(x["end"])) - a} for x in sous_titres(video) if float(x["end"]) > a and float(x["start"]) < b]
    filtre = paquets.cadre(m["largeur"], m["hauteur"], l, h)
    fichiers = ["video.mp4"]
    if segs and d.reglages.get("sous_titres") == "incrustes":
        (dossier / "video.srt").write_text(publication.srt(segs), encoding="utf-8")
        filtre += ",subtitles=video.srt:force_style='FontName=Segoe UI,FontSize=16,Outline=2,MarginV=60'"
        fichiers.append("video.srt")
    lancer(programme("ffmpeg"), "-nostdin", "-y", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", video, "-filter_complex", filtre,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "video.mp4",
           cwd=dossier)
    return Resultat(fichiers=fichiers, duree_s=round(mesure(dossier / "video.mp4")["duree_s"], 3), infos={"incrustes": len(segs) if "video.srt" in fichiers else 0})


def montee(d: Demande) -> Path:
    """La vidéo montée que la miniature et le contrôle regardent : la dernière étape d'avant qui a rendu une vidéo."""
    videos = [f[0] for e, f in d.entrees.items() if f and f[0].lower().endswith(".mp4")]
    if not videos:
        raise RuntimeError("aucune vidéo montée avant cette étape dans la recette")
    return Path(videos[-1])


def miniature(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    from fabrique.moteur.faux import programme
    from fabrique.publication import paquets

    video = montee(d)
    m = mesure(video)
    l, h = (1280, 720) if d.reglages.get("cadre", "16:9") == "16:9" else (720, 1280)
    lancer(programme("ffmpeg"), "-nostdin", "-y", "-v", "error", "-ss", f"{m['duree_s'] / 3:.3f}", "-i", video, "-filter_complex", paquets.cadre(m["largeur"], m["hauteur"], l, h),
           "-frames:v", "1", "-q:v", "3", dossier / "miniature.jpg")
    return Resultat(fichiers=["miniature.jpg"])


def controle(fiche: Fiche, d: Demande, dossier: Path) -> Resultat:
    video = montee(d)
    m = mesure(video)
    defauts = []
    if bornes := d.reglages.get("duree_s"):
        if not bornes[0] <= m["duree_s"] <= bornes[1]:
            defauts.append({"debut": None, "fin": None, "texte": f"durée {m['duree_s']:.1f} s hors des bornes du format ({bornes[0]} à {bornes[1]} s)", "gravite": "forte"})
    l, h = CADRES.get(d.reglages.get("cadre", "16:9"), CADRES["16:9"])
    if (m["largeur"] > m["hauteur"]) != (l > h) or not m["largeur"]:
        defauts.append({"debut": None, "fin": None, "texte": f"cadre {m['largeur']} × {m['hauteur']} : le format attend {d.reglages.get('cadre', '16:9')}", "gravite": "forte"})
    if not m["son"]:
        defauts.append({"debut": None, "fin": None, "texte": "pas de son", "gravite": "forte"})
    try:
        incrustes = json.loads((video.parent / "resultat.json").read_text(encoding="utf-8"))["infos"].get("incrustes")
    except (OSError, ValueError, KeyError):
        incrustes = None
    if d.reglages.get("sous_titres") == "incrustes" and incrustes == 0:
        defauts.append({"debut": None, "fin": None, "texte": "sous-titres incrustés attendus par le format : la source n'en a aucun", "gravite": "forte"})
    (dossier / "rapport.json").write_text(json.dumps({"video": str(video), **{k: v for k, v in m.items() if k != "format"}, "defauts": defauts}, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    return Resultat(fichiers=["rapport.json"], duree_s=m["duree_s"], infos={"defauts": defauts})


def fabriquer(fiche: Fiche, demande: Demande, dossier: Path) -> Resultat:
    return {"assemblage": assemblage, "verticale": verticale, "miniature": miniature, "controle": controle}[demande.brique](fiche, demande, dossier)
