"""J19 : une version de langue par le nouveau moteur (sous-commande « moteur --etape langue <date>-<code>.<langue>.json »). Elle part du rendu anglais
dont les visuels sont prêts (PROJET/rendus/<date>-<code>/) et ne refait JAMAIS une image, un calque ni une animation : images/, calques/ et clips/
sont des liens durs vers ceux de l'anglais. Refaits pour la langue : voix (l'outil validé au banc, même référence que l'anglais), contrôle Whisper
DANS la langue (copie whisper_langue_wsl.py ; score normalisé par écriture), Bramble qui parle (LongCat, sur la voix de la langue), musique (les
morceaux anglais recalés à la nouvelle durée, fondu final sur la dernière phrase), montage (durées de la voix : plans ralentis par setpts comme
l'anglais, jamais d'image figée au-delà), miniature au titre traduit (police libre de la langue ; texte composé par ffmpeg : harfbuzz + fribidi,
arabe lié et de droite à gauche), sous-titres (final/sous_titres.srt), textes YouTube traduits avec mention IA et crédit de la voix dans la langue
(PROJET/notes/langues.json, hors dépôt de l'app ; l'anglais sinon). Mêmes lignes de journal que les autres étapes. Sans Django."""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from core import dossiers
from fabrique.moteur.f1 import bramble, etape, montage
from fabrique.moteur.f1.langue_texte import score, srt
from fabrique.moteur.f1.outils import Outils, charger, composant, dans_wsl, wsl
from fabrique.moteur.f1.voix import wslp, wslq

VISUELS = ("images", "calques", "clips")
ETAPES = ("visuels", "voix", "bramble", "musique", "montage", "miniature", "revue")
SEUIL = 0.85  # contrôle Whisper hors anglais (écritures sans espaces, homophones) ; 0,93 en anglais
ESSAIS = 3


def anglais(scenario: Path) -> Path:
    """« 2026-10-26-s1e01.fr.json » → « 2026-10-26-s1e01.json » (même dossier)."""
    return scenario.with_name(scenario.stem.rsplit(".", 1)[0] + ".json")


def lier_visuels(en_run: Path, run: Path, scenes: list[dict]) -> int:
    """Liens durs vers les visuels de l'anglais (copie si le disque refuse le lien) ; refus si un clip manque (l'anglais n'est pas fini)."""
    manquent = [s["id"] for s in scenes if s.get("image") and not (en_run / "clips" / f"s{s['id']:03d}.mp4").is_file()]
    if manquent:
        raise RuntimeError(f"visuels de l'anglais pas prets ({en_run.name}) : clips manquants pour {len(manquent)} scene(s), dont {manquent[:5]}")
    n = 0
    for d in VISUELS:
        for f in (en_run / d).rglob("*") if (en_run / d).is_dir() else []:
            cible = run / f.relative_to(en_run)
            if f.is_file() and not cible.exists():
                cible.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(f, cible)
                except OSError:
                    shutil.copy2(f, cible)
                n += 1
    return n


def jobs_voix(run: Path, scenes: list[dict], langue: dict, essai: int = 0, ids=None) -> list[dict]:
    r = langue.get("reglages", {})
    return [{"text": s["narration"], "out": str(run / "voix" / f"s{s['id']:03d}.wav"), "seed": 42 + 1000 * essai, "langue": langue["code"],
             "exaggeration": r.get("exaggeration", 0.3), "cfg": r.get("cfg", 0.3)}
            for s in scenes if s["narration"] and (ids is None or s["id"] in ids) and not (run / "voix" / f"s{s['id']:03d}.wav").exists()]


def dire(o: Outils, run: Path, lot: list[dict], langue: dict, ref: str):
    """La voix de la langue avec l'outil validé au banc : Chatterbox Multilingual, CosyVoice, Qwen (venv de l'outil, poids du registre) ou VoxCPM2 (Linux)."""
    if not lot:
        return
    jf = run / "voix" / "_jobs_langue.json"
    r = langue.get("reglages", {})
    # ref_gen : la voix clonée (une référence native de la langue si le banc l'a retenue) ; ref : la voix 1, cible de la conversion « vc »
    json.dump({"ref": ref, "ref_gen": str(o.racine / r["ref"]) if r.get("ref") else ref, "langue": langue["code"], "reglages": r, "jobs": lot,
               "poids": str(composant(o.racine, "poids_voix"))},
              open(jf, "w", encoding="utf-8"), ensure_ascii=False)
    ici, outil = Path(__file__).parent, langue.get("outil")
    jouer = lambda cle, script: o.run([composant(o.racine, cle, "venv", "Scripts", "python.exe"), ici / script, jf], cwd=str(composant(o.racine, cle)))  # noqa: E731
    if outil == "voxcpm":
        o.run(wsl(f"HF_HOME={dans_wsl('cache_voix_linux')} HF_HUB_OFFLINE=1 {dans_wsl('voxcpm', 'bin', 'python')} {wslq(ici / 'tts_voxcpm_wsl.py')} {wslq(jf)}"))
    elif outil == "cosyvoice3":
        jouer("cosyvoice", "tts_cosyvoice3.py")
    elif outil in ("qwen3_tts", "qwen3_design"):
        jouer("qwen_tts", "tts_qwen.py")
    else:
        jouer("chatterbox", "tts_chatterbox_mtl.py")
    if r.get("vc"):  # conversion de timbre vers la voix 1 (Chatterbox VC), sur place
        jouer("chatterbox", "vc_chatterbox.py")


def voix(o: Outils, run: Path, scenes: list[dict], langue: dict, ref: str, log=print) -> dict:
    """voix/sNNN.wav puis Whisper dans la langue ; sous le seuil, la phrase est refaite avec une autre graine (3 essais) ; voix/_controle.json."""
    d = run / "voix"; d.mkdir(exist_ok=True)
    dire(o, run, jobs_voix(run, scenes, langue), langue, ref)
    fait = json.loads((d / "_controle.json").read_text(encoding="utf-8")) if (d / "_controle.json").exists() else {}
    for essai in range(ESSAIS):
        lot = [{"wav": wslp(d / f"s{s['id']:03d}.wav"), "langue": langue["code"], "id": s["id"], "texte": s["narration"]}
               for s in scenes if s["narration"] and str(s["id"]) not in fait]
        if not lot:
            break
        lf = d / "_controle_lot.json"; json.dump(lot, open(lf, "w", encoding="utf-8"), ensure_ascii=False)
        cmd = "cd " + dans_wsl("longcat") + " && ./venv/bin/python " + wslq(Path(__file__).parent / "whisper_langue_wsl.py") + " " + wslq(lf) + " " + dans_wsl("whisper")
        subprocess.run(wsl(cmd), capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        rf = d / "_controle_lot_resultat.json"
        if not rf.exists():
            log("voix : controle Whisper impossible (WSL), on continue sans")
            return fait
        mauvais = []
        for r in json.loads(rf.read_text(encoding="utf-8")):
            r["score"] = score(r["texte"], r["entendu"], langue["code"])
            if r["score"] >= SEUIL or essai == ESSAIS - 1:
                fait[str(r["id"])] = r
            else:
                mauvais.append(r["id"])
        rf.unlink()
        json.dump(fait, open(d / "_controle.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if not mauvais:
            break
        log(f"voix : {len(mauvais)} phrase(s) sous {SEUIL} refaite(s) (essai {essai + 2})")
        for i in mauvais:
            (d / f"s{i:03d}.wav").unlink(missing_ok=True)
        dire(o, run, jobs_voix(run, scenes, langue, essai + 1, set(mauvais)), langue, ref)
    return fait


def musique(o: Outils, en_run: Path, run: Path, total: float, queue: float = 0) -> Path:
    """Les morceaux anglais (musique.wav) recalés à la durée de la langue : coupés avec un fondu final de 8 s qui finit sur la dernière phrase (+ la queue
    de musique du pack son), ou prolongés en reprenant leur milieu par un fondu croisé de 8 s. Rien n'est régénéré (mêmes réglages, même consigne)."""
    out = run / "musique.wav"
    if out.exists():
        return out
    src = en_run / "musique.wav"
    if not src.is_file():
        raise RuntimeError(f"musique de l'anglais absente : {src}")
    cible, d0 = total + queue, o.duree(src)
    entrees, fc, n, d = ["-i", str(src)], "", 1, d0
    while d < cible + 1:  # prolonger : le morceau anglais repris à son quart, à la suite, en fondu croisé (pas de coupure audible)
        entrees += ["-ss", f"{d0 * 0.25:.2f}", "-i", str(src)]
        d += d0 * 0.75 - 8
        n += 1
    last = "[0:a]"
    for k in range(1, n):
        fc += f"{last}[{k}:a]acrossfade=d=8:c1=tri:c2=tri[x{k}];"
        last = f"[x{k}]"
    fc += f"{last}atrim=duration={cible:.2f},afade=t=out:st={max(0, cible - 8):.2f}:d=8[a]"
    o.run([o.ffmpeg, "-y", "-v", "error", *entrees, "-filter_complex", fc, "-map", "[a]", str(out)])
    return out


def _texte_png(o: Outils, ligne: str, police: Path, taille: int, couleur: str, bord: str, epaisseur: int, out: Path) -> Image.Image:
    """Une ligne composée par ffmpeg drawtext (harfbuzz : ligatures arabes, conjoints devanagari ; fribidi : droite à gauche) sur fond transparent."""
    t = out.with_suffix(".txt"); t.write_text(ligne, encoding="utf-8")
    esc = lambda p: str(p).replace("\\", "/").replace(":", "\\:")
    vf = (f"drawtext=fontfile='{esc(police)}':textfile='{esc(t)}':text_shaping=1:fontsize={taille}:fontcolor={couleur}:borderw={epaisseur}:"
          f"bordercolor={bord}:x=(w-text_w)/2:y=(h-text_h)/2")
    o.run([o.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black@0.0:s=1280x{taille + 60},format=rgba", "-vf", vf, "-frames:v", "1", str(out)])
    t.unlink()
    return Image.open(out).convert("RGBA")


def lignes_titre(txt: str, f, largeur: float) -> list[str]:
    """2 lignes au plus : mots répartis comme la miniature anglaise ; une écriture sans espaces (japonais) est coupée en deux moitiés."""
    mots = txt.split()
    if len(mots) == 1 and f.getlength(txt) > largeur:
        return [txt[:len(txt) // 2 + len(txt) % 2], txt[len(txt) // 2 + len(txt) % 2:]]
    lignes = []
    for m in mots:
        if lignes and f.getlength(lignes[-1] + " " + m) < largeur:
            lignes[-1] += " " + m
        else:
            lignes.append(m)
    if len(lignes) > 2:
        lignes = [" ".join(mots[:(len(mots) + 1) // 2]), " ".join(mots[(len(mots) + 1) // 2:])]
    return lignes


def miniature(o: Outils, run: Path, data: dict, scenes: list[dict], cfg: dict, police: Path | None) -> Path:
    """La miniature de l'anglais (même image, même médaillon, même dessin) au titre traduit. Écriture latine (police None) : le dessin de l'anglais
    tel quel (Fredoka en gras, Pillow) ; autre écriture : la police libre de la langue, texte composé par ffmpeg (Pillow n'a pas raqm ici)."""
    out = run / "final" / "miniature.jpg"
    if out.exists():
        return out
    mc = cfg.get("miniature", {})
    src = montage.source_miniature(run, data, scenes, o.poses)
    if police is None:
        return montage.dessiner(src, (data.get("thumbnail_text") or data["title"]).strip(), mc, o.police, o.poses / "welcome.png", out)
    img = Image.open(src).convert("RGB"); W, H = 1280, 720
    r = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * r), round(img.height * r)), Image.LANCZOS)
    l, t = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((l, t, l + W, t + H))
    if mc.get("pastel"):
        img = ImageEnhance.Contrast(ImageEnhance.Brightness(img).enhance(mc.get("luminosite", 1.35))).enhance(mc.get("contraste", 0.85))
        img = Image.blend(ImageEnhance.Color(img).enhance(0.9), Image.new("RGB", img.size, (250, 236, 214)), mc.get("voile", 0.12))
    txt = (data.get("thumbnail_text") or data["title"]).strip()
    taille = 110
    f = ImageFont.truetype(str(police), taille)
    lignes = lignes_titre(txt, f, W * 0.86)
    while taille > 60 and max(f.getlength(li) for li in lignes) > W * 0.9:  # mesure approchée (sans composition) : la ligne doit tenir
        taille -= 10; f = ImageFont.truetype(str(police), taille)
    nl = min(2, len(lignes)); bande = 40 + 130 * nl
    bas = mc.get("titre", "haut") == "auto" and montage.zone_calme(img, bande) == "bas"
    y = H - bande if bas else 40
    tmp = run / "final" / "_titre"; tmp.mkdir(parents=True, exist_ok=True)
    for i, li in enumerate(lignes[:2]):
        halo = _texte_png(o, li, police, taille, "0x0E1730", "0x0E1730", 14, tmp / f"halo{i}.png").filter(ImageFilter.GaussianBlur(6))
        net = _texte_png(o, li, police, taille, "0xFAE8BE", "0x0E1730", 4, tmp / f"net{i}.png")
        yy = y + 65 - net.height // 2 + taille // 2
        img.paste(halo, (0, yy), halo); img.paste(net, (0, yy), net)
        y += 130
    shutil.rmtree(tmp, ignore_errors=True)
    montage.medaillon(img, o.poses / "welcome.png", coin="haut_gauche" if bas else "bas_gauche")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=92)
    return out


def textes_youtube(racine: Path, run: Path, data: dict, scenes: list[dict], code: str, credit_ref: str = ""):
    """final/youtube.txt de la langue : titre traduit (son suffixe traduit est dans le titre), description, mention IA et crédit de la voix dans la langue,
    tags traduits ; sous-titres final/sous_titres.srt (débuts de scène = durées du montage)."""
    t = 0.0
    for s in scenes:
        s["_debut"] = t; t += s.get("_duree", 0)
    (run / "final").mkdir(exist_ok=True)
    (run / "final" / "sous_titres.srt").write_text(srt(scenes), encoding="utf-8")
    try:
        credits = json.loads((Path(racine) / "PROJET" / "notes" / "langues.json").read_text(encoding="utf-8"))[code]["credits"]
    except (OSError, ValueError, KeyError):
        credits = ""
    if not credits:  # pas de crédit traduit : celui de l'anglais (obligatoire : licence de la voix, déclaration IA)
        etape.textes_youtube(racine, run, data, scenes)
        if credit_ref:  # référence native CC BY retenue au banc des voix : à créditer aussi
            f = run / "final" / "youtube.txt"; f.write_text(f.read_text(encoding="utf-8") + f"\n{credit_ref}\n", encoding="utf-8")
        return
    credits += f"\n{credit_ref}" if credit_ref else ""
    chap = "".join(f"\n{c}" for c in data.get("chapters", []))
    txt = f"TITRE :\n{data['title']}\n\nDESCRIPTION :\n{data.get('description', '')}{chap}\n\n{credits}\n\nTAGS :\n{', '.join(data.get('tags', []))}\n"
    (run / "final" / "youtube.txt").write_text(txt, encoding="utf-8")


def faire(racine, scenario, cfg: dict, langue: dict, ref: str, ecran=print, dossier=None) -> int:
    """La version de langue en entier (étapes ETAPES), reprise là où elle s'était arrêtée ; mêmes journal.txt, chrono.csv et verrou que etape.jouer."""
    racine, scenario = Path(racine), Path(scenario)
    rendus = racine / "PROJET" / "rendus"
    run, en_run = Path(dossier) if dossier else rendus / scenario.stem, rendus / anglais(scenario).stem
    run.mkdir(parents=True, exist_ok=True)
    verrou = open(run / "en_cours.lock", "a+")  # noqa: SIM115
    try:
        try:
            import msvcrt
            msvcrt.locking(verrou.fileno(), msvcrt.LK_NBLCK, 1)
        except ImportError:
            pass
        except OSError:
            ecran("Ce rendu tourne deja : on ne le lance pas deux fois.")
            return 0

        def log(*a):
            msg = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
            ecran(msg.encode("ascii", "replace").decode())
            with open(run / "journal.txt", "a", encoding="utf-8") as f:
                f.write(msg + "\n")

        o = Outils(racine)
        data, scenes, plans = charger(o, scenario)
        coupes = etape.ranger_coupes(run, o)
        log(f"=== {data['title']} ({scenario.name}) : {len(scenes)} scenes, {len(plans)} plans, langue {langue['code']}")
        if coupes:
            log(f"reprise : {len(coupes)} fichier(s) coupe(s) par l'arret range(s) dans _coupes, a refaire : {', '.join(coupes[:5])}")
        m = montage.Montage(run, cfg, o)
        for e in ETAPES:
            t = time.time()
            if e == "visuels":
                log(f"visuels : {lier_visuels(en_run, run, scenes)} fichier(s) repris de l'anglais, aucune image ni animation refaite")
            elif e == "voix":
                c = voix(o, run, scenes, langue, ref, log)
                log(f"voix : {len(c)} phrase(s), score Whisper moyen {sum(x['score'] for x in c.values()) / max(1, len(c)):.3f}")
            elif e == "bramble":
                m.durees(scenes)
                bramble.faire(racine, run, scenes, cfg, log=log)
            elif e == "musique":
                musique(o, en_run, run, m.durees(scenes), m.son_pack().get("queue_s", 0))
            elif e == "montage":
                m.durees(scenes); m.monter(data, scenes)
            elif e == "miniature":
                miniature(o, run, data, scenes, cfg, dossiers.livre(racine, "polices", langue["police"]) if langue.get("police") else None)
            elif e == "revue":
                m.durees(scenes); textes_youtube(racine, run, data, scenes, langue["code"], langue.get("reglages", {}).get("credit", ""))
            minutes = (time.time() - t) / 60
            log(f"--- etape {e} : {minutes:.1f} min")
            with open(run / "chrono.csv", "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M')};{e};{minutes:.1f}\n")
        log("=== termine")
        return 0
    finally:
        verrou.close()
