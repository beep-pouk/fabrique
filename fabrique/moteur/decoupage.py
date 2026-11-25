"""Mise en scène (étape 4 du plan du 24/11) : un passage à l'écran d'une même image (une ou plusieurs scènes qui se suivent) est découpé en
plans de 4 à 8 s, coupés de préférence entre deux scènes, sinon entre deux phrases ; chaque plan a sa valeur (large, moyen, gros plan), son
cadre dans l'image et un mouvement de caméra lent (le cadre de départ glisse vers celui d'arrivée). Les personnages sont cadrés grâce aux
calques de Bramble Studio (calques\\plan_NNN\\meta.json à côté de images\\, lus seulement) ; sans calques, cadres centrés. Un cadre =
[cx, cy, taille] en fractions de l'image 16:9 (taille = part de la largeur, l'image garde sa forme). Sans Django."""
import hashlib
import json
import math
import re
from pathlib import Path

from PIL import Image

PLAN_MIN, PLAN_MAX, PLAN_VISE = 4.0, 8.0, 6.0
GROS_MIN = 0.5  # un gros plan plus serré agrandirait trop l'image (flou)
PHRASE = re.compile(r"(?<=[.!?…])\s+")


def personnages(image: Path) -> list[dict]:
    """Les personnages de l'image d'après ses calques : nom, boîte et visage (centre des yeux, d'après leur masque yeux_N.png ; à défaut, le haut
    d'un personnage debout ; None pour un personnage couché ou un groupe sans yeux), en fractions ; [] sans calques ou s'ils ne sont pas de
    cette image."""
    meta = image.parent.parent / "calques" / image.stem / "meta.json"
    try:
        m = json.loads(meta.read_text(encoding="utf-8"))
        with Image.open(image) as im:
            if im.size != (m["largeur"], m["hauteur"]) or meta.stat().st_mtime < image.stat().st_mtime:
                return []  # image refaite après ses calques
        W, H, noms, persos = m["largeur"], m["hauteur"], m.get("noms") or [], []
        for i, c in enumerate(m.get("calques", [])):
            if c["x1"] <= c["x0"] or c["y1"] <= c["y0"]:
                continue
            visage = ((c["x0"] + c["x1"]) / 2 / W, (c["y0"] + 0.3 * (c["y1"] - c["y0"])) / H) if c["y1"] - c["y0"] >= 0.8 * (c["x1"] - c["x0"]) else None
            if c.get("yeux") and (yeux := meta.parent / f"yeux_{i}.png").is_file():
                with Image.open(yeux) as y:
                    if b := y.convert("L").getbbox():
                        visage = ((c["x0"] + (b[0] + b[2]) / 2) / W, (c["y0"] + (b[1] + b[3]) / 2) / H)
            persos.append({"nom": noms[i] if i < len(noms) else "", "boite": (c["x0"] / W, c["y0"] / H, c["x1"] / W, c["y1"] / H), "visage": visage})
        return [q for q in persos if q["nom"]] or persos  # un calque sans nom à côté de personnages nommés : un morceau détaché (queue, ombre)
    except (OSError, ValueError, KeyError, TypeError):
        return []


def couper(debut: float, fin: float, coupes: list[tuple[float, int]]) -> list[float]:
    """Les instants de coupe entre debut et fin : plans de 4 à 8 s (sauf un passage de moins de 4 s), au plus près de 6 s ; coupes = (instant,
    préférence) proposés (0 : entre deux scènes, 1 : entre deux phrases) ; faute de mieux, coupe au milieu du texte."""
    t, faites = debut, []
    while fin - t > PLAN_MAX:
        bons = [(p, abs(c - t - PLAN_VISE), c) for c, p in coupes if t + PLAN_MIN <= c <= t + PLAN_MAX and (fin - c >= PLAN_MIN)]
        c = min(bons)[2] if bons else t + min(PLAN_VISE, fin - t - PLAN_MIN)
        faites.append(c)
        t = c
    return faites


def _cadre(boite: tuple, taille: float, haut: float = 0.5) -> list[float]:
    """Le cadre de `taille` centré sur la boîte (à `haut` de sa hauteur), gardé dans l'image."""
    x0, y0, x1, y1 = boite
    demi = taille / 2
    cx = min(max((x0 + x1) / 2, demi), 1 - demi)
    cy = min(max(y0 + haut * (y1 - y0), demi), 1 - demi)
    return [round(cx, 4), round(cy, 4), round(taille, 4)]


def cadres(persos: list[dict], vise: str, rang: int) -> dict:
    """Valeur et mouvement du plan n° `rang` d'un passage : large d'abord, puis moyen et gros plan en alternance (gros plan sur `vise`, le
    personnage nommé en premier par la scène, sinon le plus grand) ; sans personnages connus : large et moyen centré."""
    large = [0.5, 0.5, 1.0]
    if rang == 0:
        return {"valeur": "large", "de": large, "a": [0.5, 0.5, 0.92]}  # lente approche
    if not persos:  # moyen centré qui glisse, puis large qui recule, en alternance
        return ({"valeur": "moyen", "de": [0.47, 0.55, 0.72], "a": [0.53, 0.55, 0.72]} if rang % 2 else {"valeur": "large", "de": [0.5, 0.5, 0.9], "a": [0.5, 0.5, 0.98]})
    taille = lambda p: (p["boite"][2] - p["boite"][0]) * (p["boite"][3] - p["boite"][1])  # noqa: E731
    ordre = sorted(persos, key=lambda p: (not (p["nom"] and p["nom"].lower() == vise.lower()), -taille(p)))
    p = ordre[((rang + 1) // 2 - 1) % len(ordre)]  # le personnage visé, puis les autres à tour de rôle
    h = p["boite"][3] - p["boite"][1]
    if rang % 2:  # moyen : le groupe s'il tient dans un cadre plus serré que l'image, sinon le personnage en pied ; approche puis recul
        tous = (min(q["boite"][0] for q in persos), min(q["boite"][1] for q in persos), max(q["boite"][2] for q in persos), max(q["boite"][3] for q in persos))
        t = max(0.62, 1.25 * max(tous[2] - tous[0], tous[3] - tous[1]))
        boite, t = (tous, t) if t < 0.95 else (p["boite"], min(0.85, max(0.62, 1.1 * h)))
        de, a = _cadre(boite, t), _cadre(boite, max(0.6, t * 0.94))
        return {"valeur": "moyen", "de": de if rang % 4 == 1 else a, "a": a if rang % 4 == 1 else de}
    if not p.get("visage"):  # visage inconnu (couché, groupe) : plan moyen sur lui plutôt qu'un gros plan sur ses oreilles
        t = min(0.85, max(0.62, 1.1 * max(p["boite"][2] - p["boite"][0], h)))
        return {"valeur": "moyen", "de": _cadre(p["boite"], t), "a": _cadre(p["boite"], max(0.6, t * 0.94))}
    vx, vy = p["visage"]
    t = min(0.8, max(GROS_MIN, 0.65 * h))
    g = lambda t: _cadre((vx, vy + 0.1 * t, vx, vy + 0.1 * t), t)  # noqa: E731 — les yeux un peu au-dessus du centre
    return {"valeur": "gros", "de": g(t), "a": g(max(0.45, t * 0.93))}


def decouper(scenes: list[dict]) -> list[dict]:
    """Les plans de l'épisode, dans l'ordre. Chaque scène a `_source` (son image), `_duree` (à l'écran), `_voix` (durée de sa voix) ; une
    scène de Bramble (`bramble`) reste un seul plan sur sa pose. Pose aussi sur chaque scène `_plans` : ses morceaux de plans {t, duree,
    valeur, de, a}, un plan coupé par la fin de la scène continuant son mouvement dans la suivante."""
    plans, t, i = [], 0.0, 0
    while i < len(scenes):
        j = i + 1
        while j < len(scenes) and not scenes[i].get("bramble") and not scenes[j].get("bramble") and scenes[j]["_source"] == scenes[i]["_source"]:
            j += 1
        passage, debut = scenes[i:j], t
        coupes, u = [], t
        for k, sc in enumerate(passage):
            phrases = [p for p in PHRASE.split(str(sc.get("narration", "")).strip()) if p]
            n = sum(len(p) for p in phrases) or 1
            fait = 0
            for p in phrases[:-1]:  # dans la voix, au prorata des lettres
                fait += len(p)
                coupes.append((u + sc["_voix"] * fait / n, 1))
            u += sc["_duree"]
            if k < len(passage) - 1:
                coupes.append((u, 0))
        fin = u
        bornes = [debut, *([] if passage[0].get("bramble") else couper(debut, fin, coupes)), fin]
        noms = re.findall(r"\b[A-Z][a-z]+", str(passage[0].get("image", "")))
        persos = [] if passage[0].get("bramble") else personnages(Path(passage[0]["_source"]))
        vise = next((n for n in noms if any(p["nom"].lower() == n.lower() for p in persos)), "")
        for r, (a, b) in enumerate(zip(bornes, bornes[1:])):
            c = {"valeur": "bramble", "de": [0.5, 0.5, 1.0], "a": [0.5, 0.5, 1.0]} if passage[0].get("bramble") else cadres(persos, vise, r)
            u, ou = debut, passage[0]["id"]  # la scène où le plan commence (la planche le range sous son plan)
            for sc in passage:
                if u <= a + 1e-6:
                    ou = sc["id"]
                u += sc["_duree"]
            plans.append({"debut": round(a, 3), "duree": round(b - a, 3), "scene": ou, **c})
        u = debut
        for sc in passage:  # les morceaux de chaque scène
            sc["_plans"] = []
            for p in plans:
                a, b = max(p["debut"], u), min(p["debut"] + p["duree"], u + sc["_duree"])
                if b - a > 1e-3:
                    f = lambda x: [round(d + (e - d) * (x - p["debut"]) / p["duree"], 4) for d, e in zip(p["de"], p["a"])]  # noqa: E731
                    sc["_plans"].append({"t": round(a - u, 3), "duree": round(b - a, 3), "valeur": p["valeur"], "de": f(a), "a": f(b)})
            u += sc["_duree"]
        t, i = fin, j
    return plans


def filmer(run, ffmpeg: str, source: Path, morceaux: list[dict], sortie: Path, W: int, H: int, fps: int) -> Path:
    """Les morceaux de plans d'une scène filmés dans son image, sans son : chaque cadre glisse de `de` à `a` (zoompan de ffmpeg sur l'image
    agrandie deux fois et mise en 16:9 une seule fois, pour un mouvement sans à-coups), puis collés."""
    grande = sortie.parent / f"_{hashlib.sha1(str(source).encode()).hexdigest()[:12]}_{W}.png"
    if not grande.is_file():
        with Image.open(source) as im:
            k = max(2 * W / im.width, 2 * H / im.height)
            im = im.convert("RGB").resize((math.ceil(im.width * k), math.ceil(im.height * k)), Image.LANCZOS)
            g, h = (im.width - 2 * W) // 2, (im.height - 2 * H) // 2
            im.crop((g, h, g + 2 * W, h + 2 * H)).save(grande)
    cmd, fc = [ffmpeg, "-y", "-v", "error"], []
    for k, m in enumerate(morceaux):
        n = max(1, round(m["duree"] * fps))
        p = f"(on/{max(1, n - 1)})"
        (x0, y0, s0), (x1, y1, s1) = m["de"], m["a"]
        fc.append(f"[{k}:v]zoompan=z='1/({s0}+({s1 - s0:.4f})*{p})':x='({x0}+({x1 - x0:.4f})*{p})*iw-iw/zoom/2':y='({y0}+({y1 - y0:.4f})*{p})*ih-ih/zoom/2'"
                  f":d=1:s={W}x{H}:fps={fps},trim=end_frame={n},setpts=PTS-STARTPTS[v{k}]")
        cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{(n + 1) / fps:.3f}", "-i", str(grande)]
    fc.append("".join(f"[v{k}]" for k in range(len(morceaux))) + f"concat=n={len(morceaux)}:v=1:a=0,format=yuv420p[v]")
    run(cmd + ["-filter_complex", ";".join(fc), "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-r", str(fps), str(sortie)])
    return sortie

