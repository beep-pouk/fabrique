"""Nouveau moteur (J9a), étapes montage et miniature = durees / segment / mix_audio / etape_montage / etape_miniature de production.py : mêmes
commandes ffmpeg, mêmes réglages de config.json, même dessin de la miniature. Différence voulue : le dossier du rendu, les réglages et les outils sont
des paramètres (pas de variables globales) et il n'écrit que dans ce dossier. Sans Django."""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from fabrique.moteur.f1.outils import Outils


class Montage:
    def __init__(self, dossier: Path, cfg: dict, outils: Outils):
        self.dossier, self.cfg, self.o = Path(dossier), cfg, outils

    def son_pack(self) -> dict:
        sp = self.cfg.get("son_pack", {})
        return sp if sp.get("actif") else {}

    def ambiance_cfg(self) -> dict:
        a = self.cfg.get("ambiance", {})
        return a if a.get("actif") else {}

    def durees(self, scenes: list[dict]) -> float:
        """Durée à l'écran de chaque scène = voix + pause + hold_s (+ silences qui grandissent en fin d'épisode : pack son)."""
        sp = self.son_pack()
        for i, s in enumerate(scenes):
            w = self.dossier / "voix" / f"s{s['id']:03d}.wav"
            voix = self.o.duree(w) if w.exists() else 0.0
            s["_voix"] = voix
            hold = float(s.get("hold_s") or 0)
            if sp.get("silences"):
                if i >= len(scenes) - 5: hold = max(hold, 2.5)
                elif i >= sp.get("descente_debut", 0.65) * len(scenes): hold = max(hold, 1.5)
            s["_duree"] = round(voix + self.cfg["pause_apres_phrase_s"] + hold, 3)
        return sum(s["_duree"] for s in scenes)

    def mix_audio(self, total: float, ambiance: bool = False) -> str:
        """Graphe ffmpeg du son final : entrée 0 = voix (piste du montage), 1 = musique.wav, [2 = ambiance.wav] -> [a]. Pack son : voix et musique
        normalisées à part, musique baissée sous la voix (ducking), descente à partir de descente_debut, queue de musique, fondu final."""
        cfg = self.cfg
        so, sp = cfg["sortie"], self.son_pack()
        amb = (f"[2:a]aloop=loop=-1:size=2e9,aresample=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
               f"volume={self.ambiance_cfg().get('db', -32)}dB[amb];") if ambiance else ""
        if not sp:
            return (amb + f"[1:a]aloop=loop=-1:size=2e9,volume={cfg['musique_volume_db']}dB[m];[0:a][m]" + ("[amb]amix=inputs=3" if ambiance else "amix=inputs=2")
                    + f":duration=first:dropout_transition=0,loudnorm=I={so['lufs']}:TP=-1.5:LRA=11[a]")
        q = sp.get("queue_s", 90); t1 = total * sp.get("descente_debut", 0.65); dt = max(1.0, total - t1)
        rampe = lambda db: f"volume='if(lt(t,{t1:.2f}),1,pow(10,{db}*min(1,(t-{t1:.2f})/{dt:.2f})/20))':eval=frame"
        duck = (f"[m1][k]sidechaincompress=threshold={sp.get('ducking_seuil', 0.03)}:ratio={sp.get('ducking_ratio', 3)}:attack=50:release=600[m];"
                if sp.get("ducking", True) else "[m1]anull[m];[k]anullsink;")
        return (f"[0:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I={so['lufs']}:TP=-1.5:LRA=11,aresample=48000,apad=whole_dur={total + q:.2f},aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,asplit=2[v][k];"
                f"[1:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I={so['lufs']}:TP=-1.5:LRA=11,aresample=48000,volume={cfg['musique_volume_db']}dB,"
                f"{rampe(sp.get('descente_musique_db', -3))},"
                f"volume='if(lt(t,{total:.2f}),1,pow(10,{sp.get('queue_gain_db', 12)}*min(1,(t-{total:.2f})/8)/20))':eval=frame,apad=whole_dur={total + q:.2f},atrim=duration={total + q:.2f},aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[m1];" + duck +
                amb + f"[v][m]" + ("[amb]amix=inputs=3" if ambiance else "amix=inputs=2") + f":duration=first:normalize=0,volume={sp.get('gain_db', -1.5)}dB,{rampe(sp.get('descente_voix_db', -4))},"
                f"afade=t=out:st={total + q - 20:.2f}:d=20,alimiter=limit=0.84[a]")

    def segment(self, s: dict, out: Path):
        """Une scène : clip ralenti (sans interpolation) ou Bramble (clip LongCat, sinon sa pose fixe), voix, fondu au noir au début / à la fin de l'épisode."""
        so = self.cfg["sortie"]; W, H, FPS = so["largeur"], so["hauteur"], so["fps"]
        D = s["_duree"]; f = self.cfg["fondu_s"]
        voix = self.dossier / "voix" / f"s{s['id']:03d}.wav"
        if s.get("bramble"):
            src = self.dossier / "bramble" / f"s{s['id']:03d}.mp4"
            if not src.exists():  # plan sans parole (ou LongCat absent) : pose fixe
                src = self.o.poses / f"{s['bramble']}.png"
            vf = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},fps={FPS},tpad=stop_mode=clone:stop_duration={D}"
        else:
            src = self.dossier / "clips" / f"s{s['id']:03d}.mp4"
            c = self.o.duree(src)
            k = max(1.0, D / c)
            vf = (f"setpts={k:.4f}*PTS," + f"fps={FPS},"  # pas d'interpolation de mouvement : elle fait fondre les formes (aspect IA)
                  + f"scale={W}:{H}:flags=lanczos,tpad=stop_mode=clone:stop_duration={D}")
        fades = []
        if s.get("_ep_debut"):
            fades.append(f"fade=t=in:st=0:d={f}")
        if s.get("_ep_fin"):
            fades.append(f"fade=t=out:st={max(0, D - 2 * f):.3f}:d={2 * f}")
        vf = vf + ("," + ",".join(fades) if fades else "") + f",trim=duration={D},format=yuv420p"
        is_img = str(src).endswith(".png")
        cmd = [self.o.ffmpeg, "-y", "-v", "error"] + (["-loop", "1", "-framerate", str(FPS)] if is_img else []) + ["-i", str(src)]
        if voix.exists():
            cmd += ["-i", str(voix)]
            af = f"aresample=48000,apad,atrim=duration={D}"
        else:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            af = f"atrim=duration={D}"
        cmd += ["-filter_complex", f"[0:v]{vf}[v];[1:a]{af},aformat=channel_layouts=stereo[a]", "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-t", f"{D}", str(out)]
        self.o.run(cmd)

    def monter(self, data: dict, scenes: list[dict]) -> Path:
        """Segments (ceux qui existent ne sont pas refaits), liste, collage sans réencodage, puis vidéo finale : image tenue pendant la queue de musique
        (pack son), étalonnage + grain papier si config.json -> montage, son mixé (mix_audio). Les durées (durees) doivent être calculées avant."""
        d = self.dossier / "montage"; d.mkdir(exist_ok=True)
        for s in scenes:
            out = d / f"s{s['id']:03d}.mp4"
            if not out.exists():
                self.segment(s, out)
        lst = d / "_liste.txt"
        lst.write_text("".join(f"file 's{s['id']:03d}.mp4'\n" for s in scenes), encoding="utf-8")  # fins de ligne du système, comme production.py
        brut = d / "_brut.mp4"
        self.o.run([self.o.ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(brut)])
        fin = self.dossier / "final"; fin.mkdir(exist_ok=True)
        titre = re.sub(r"[^\w\- ]", "", data["title"]).strip()[:80] or "episode"
        final = fin / f"{titre}.mp4"
        so = self.cfg["sortie"]
        music = self.dossier / "musique.wav"; amb = self.dossier / "ambiance.wav"
        amb_in = ["-i", str(amb)] if self.ambiance_cfg() and amb.exists() else []
        mo = self.cfg.get("montage", {}); vf = [mo["etalonnage"]] if mo.get("etalonnage") else []
        grain = []
        if mo.get("grain_opacite"):
            if not self.o.papier.is_file():  # production.py le fabriquerait dans OUTILS\production : le nouveau moteur n'y écrit jamais
                raise RuntimeError(f"texture papier absente : {self.o.papier}")
            grain = ["-i", str(self.o.papier)]
            gi = 2 + len(amb_in) // 2   # index ffmpeg du papier (après l'ambiance éventuelle)
            vf.append(f"[{gi}:v]blend=all_mode=multiply:all_opacity={mo['grain_opacite']}")
        if self.son_pack().get("queue_s") and music.exists():   # pack son : image tenue (noir du fondu final) pendant la queue de musique
            vf.insert(0, f"tpad=stop_mode=clone:stop_duration={self.son_pack()['queue_s']}")
        v = ("[0:v]" + re.sub(r",\[(\d+):v\]", r"[g];[g][\1:v]", ",".join(vf)) + "[v]") if vf else ""
        enc = ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p"] if vf else ["-c:v", "copy"]
        if music.exists():
            fc = self.mix_audio(self.durees(scenes), bool(amb_in)) + (";" + v if v else "")
            self.o.run([self.o.ffmpeg, "-y", "-v", "error", "-i", str(brut), "-i", str(music)] + amb_in + grain + ["-filter_complex", fc, "-map", "[v]" if v else "0:v",
                        "-map", "[a]"] + enc + ["-c:a", "aac", "-b:a", "192k", str(final)])
        else:
            fc = f"[0:a]loudnorm=I={so['lufs']}:TP=-1.5:LRA=11[a]" + (";" + re.sub(r"\[\d+:v\]blend", "[1:v]blend", v) if v else "")
            self.o.run([self.o.ffmpeg, "-y", "-v", "error", "-i", str(brut)] + grain + ["-filter_complex", fc, "-map", "[v]" if v else "0:v", "-map", "[a]"]
                       + enc + ["-c:a", "aac", "-b:a", "192k", str(final)])
        return final


# ---- miniature (= etape_miniature, zone_calme, medaillon_bramble de production.py) ----

def police(fichier: Path | None, taille: int = 120):
    """La police de production.py (OUTILS/polices/Fredoka.ttf, graisse Bold), sinon celle de Pillow sans taille, comme production.py."""
    try:
        f = ImageFont.truetype(str(fichier), taille)
    except Exception:  # noqa: BLE001 — absente ou illisible : comme production.py
        return ImageFont.load_default()
    try:
        f.set_variation_by_name("Bold")
    except Exception:  # noqa: BLE001 — police non variable : telle quelle, comme production.py
        pass
    return f


def zone_calme(img: Image.Image, h_bande: int) -> str:
    """Haut ou bas pour le titre : la bande qui recouvre le moins la tête du héros (pixels de fourrure / tricot orange-brun) ; sans héros : haut."""
    g = img.resize((img.width // 8, img.height // 8)).convert("HSV"); w, h = g.size; px = list(g.getdata())
    rows = [sum(1 for H, S, V in px[y * w:(y + 1) * w] if 3 <= H <= 25 and S > 70 and V > 60) for y in range(h)]
    ys = [y for y, c in enumerate(rows) if c >= w * 0.04]
    if len(ys) < h * 0.08:
        return "haut"
    y0, y1 = ys[0] * 8, ys[-1] * 8; tete = (y0, y0 + (y1 - y0) * 0.35)
    rec = lambda a, b: max(0, min(b, tete[1]) - max(a, tete[0]))
    return "haut" if rec(40, 40 + h_bande) <= rec(img.height - h_bande, img.height) else "bas"


def medaillon(img: Image.Image, pose: Path, taille: int = 300, marge: int = 28, coin: str = "bas_gauche"):
    """Bramble (pose recadrée au centre en rond, liseré ambre) dans un coin gauche : en bas (YouTube met la durée en bas à droite), en haut si le titre est en bas."""
    if not pose or not Path(pose).is_file():
        return
    pose_img = Image.open(pose).convert("RGB")
    c = min(pose_img.size); l, t = (pose_img.width - c) // 2, (pose_img.height - c) // 2
    pose_img = pose_img.crop((l, t, l + c, t + c)).resize((taille, taille), Image.LANCZOS)
    masque = Image.new("L", (taille, taille), 0); ImageDraw.Draw(masque).ellipse((0, 0, taille - 1, taille - 1), fill=255)
    x = marge; y = marge if coin == "haut_gauche" else img.height - taille - marge
    ImageDraw.Draw(img).ellipse((x - 8, y - 8, x + taille + 8, y + taille + 8), fill=(232, 166, 76))
    img.paste(pose_img, (x, y), masque)


def dessiner(source: Path, txt: str, mc: dict, fichier_police: Path | None, pose: Path | None, out: Path) -> Path:
    """Miniature 1280×720 : image agrandie puis recadrée au centre, pastel si réglé, titre sur 2 lignes (crème, contour nuit, halo flou) en haut, ou en bas
    si « titre » vaut auto et que le héros est en haut, médaillon de Bramble dans le coin gauche libre ; JPEG qualité 92."""
    img = Image.open(source).convert("RGB")
    W, H = 1280, 720
    r = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * r), round(img.height * r)), Image.LANCZOS)
    l, t = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((l, t, l + W, t + H))
    if mc.get("pastel"):
        img = ImageEnhance.Contrast(ImageEnhance.Brightness(img).enhance(mc.get("luminosite", 1.35))).enhance(mc.get("contraste", 0.85))
        img = Image.blend(ImageEnhance.Color(img).enhance(0.9), Image.new("RGB", img.size, (250, 236, 214)), mc.get("voile", 0.12))
    d = ImageDraw.Draw(img)
    f = police(fichier_police)
    mots, lignes = txt.split(), []
    for m in mots:
        if lignes and d.textlength(lignes[-1] + " " + m, font=f) < W * 0.86:
            lignes[-1] += " " + m
        else:
            lignes.append(m)
    nl = min(2, len(lignes)); bande = 40 + 130 * nl
    bas = mc.get("titre", "haut") == "auto" and zone_calme(img, bande) == "bas"
    y0 = H - bande if bas else 40
    y = y0
    calque = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dc = ImageDraw.Draw(calque)
    for li in lignes[:2]:
        w = d.textlength(li, font=f); x = (W - w) / 2
        dc.text((x, y), li, font=f, fill=(14, 23, 48, 255), stroke_width=14, stroke_fill=(14, 23, 48, 255))
        y += 130
    calque = calque.filter(ImageFilter.GaussianBlur(6))
    img.paste(calque, (0, 0), calque)
    d = ImageDraw.Draw(img); y = y0
    for li in lignes[:2]:
        w = d.textlength(li, font=f); x = (W - w) / 2
        d.text((x, y), li, font=f, fill=(250, 232, 190), stroke_width=4, stroke_fill=(14, 23, 48))
        y += 130
    medaillon(img, pose, coin="haut_gauche" if bas else "bas_gauche")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=92)
    return out


def source_miniature(dossier: Path, data: dict, scenes: list[dict], poses: Path | None = None) -> Path:
    """L'illustration de la miniature : celle du plan de la scène « thumbnail_scene » (sinon de la première scène sans Bramble) ; un épisode sans
    illustration (Bramble seul, essai du 13/11 : StopIteration) prend la pose de Bramble de sa première scène."""
    sid = data.get("thumbnail_scene")
    sc = next((s for s in scenes if s["id"] == sid and not s.get("bramble")), None) or next((s for s in scenes if not s.get("bramble")), None)
    if sc is None:
        return Path(poses) / f"{scenes[0]['bramble']}.png"
    first = next(x for x in scenes if x.get("_plan") == sc["_plan"])
    return Path(dossier) / "images" / f"plan_{first['id']:03d}.png"


def miniature(dossier: Path, data: dict, scenes: list[dict], cfg: dict, outils: Outils) -> Path:
    """= etape_miniature : final/miniature.jpg du rendu (déjà là : rien n'est refait)."""
    out = Path(dossier) / "final" / "miniature.jpg"
    if out.exists():
        return out
    return dessiner(source_miniature(dossier, data, scenes, outils.poses), (data.get("thumbnail_text") or data["title"]).strip(), cfg.get("miniature", {}), outils.police,
                    outils.poses / "welcome.png", out)
