"""Moteur « calques 2,5D » (25/10/2026, décision RT après la relecture d'E01 à 4,5/10) : une illustration est découpée en
calques, puis animée par calcul (aucune IA vidéo) : respiration, clignements (volet de paupière), oreilles, inclinaisons de
tête, déplacements (sauts, marche, vol) avec ombre et perspective, caméra, lucioles et étoiles. Zéro morphing : le dessin
du personnage est le même du début à la fin du plan ; les scènes d'un même plan s'enchaînent sans coupure d'état.

Calques d'un plan (cache : rendus/<ep>/calques/plan_XXX/) :
  fond.png      décor sans les personnages (Qwen-Image-Edit, ~250 s)
  matte.png     masque des personnages (BiRefNet dans ComfyUI, ~5 s ; repli : plaque verte Qwen)
  ferme.png     même illustration, yeux fermés (Qwen-Image-Edit, ~250 s ; sautée si personnages minuscules)
  meta.json     composantes (un calque par personnage : boîte, pieds, zone des yeux)
Usage kit : production.etape_anim -> calques.anime_plan(...) quand config.json -> video_moteur = "calques".
"""
import json, math, re, random, hashlib, shutil, subprocess, time
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
import production as P

BIREFNET = "BiRefNet-general.safetensors"
TETE = ("Picture 1 is a frame from a children's cartoon. Draw exactly the same picture, same drawing style, same framing and "
        "camera, same colors and lighting, with ONE change: ")
_ESP = None


def especes():
    global _ESP
    if _ESP is None:
        try:
            u = json.load(open(P.UNIVERS, encoding="utf-8"))["friends"]
            _ESP = {n: v["species"].split("/")[0].strip() for n, v in u.items()}
        except Exception:
            _ESP = {}
        _ESP.setdefault("Bramble", "hedgehog")
    return _ESP


def qui_texte(noms):
    sp = [especes().get(n, "animal") for n in noms]
    if not sp: return "the animal characters"
    if len(sp) == 1: return "the " + sp[0]
    return "the " + " and the ".join(sp)


# ----------------------------------------------------------------------------------------------------- 1. les calques
def matte_birefnet(png, out):
    """Masque des personnages par BiRefNet (noeuds natifs ComfyUI). Renvoie None si le modèle manque."""
    mod = Path(P.comfy.CUI) / "ComfyUI" / "models" / "background_removal" / BIREFNET
    if not mod.exists():
        return None
    shutil.copy(png, Path(P.comfy.CUI) / "ComfyUI" / "input" / "prod_calque_in.png")
    L = lambda n, i=0: [str(n), i]
    G = {"1": {"class_type": "LoadImage", "inputs": {"image": "prod_calque_in.png"}},
         "2": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": BIREFNET}},
         "3": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": L(2), "image": L(1)}},
         "4": {"class_type": "MaskToImage", "inputs": {"mask": L(3)}},
         "5": {"class_type": "SaveImage", "inputs": {"images": L(4), "filename_prefix": "prod/matte"}}}
    outs = P.comfy.run(G, timeout=1800)
    shutil.move(outs[0], out)
    return out


def alpha_depuis_vert(vert_png):
    v = np.asarray(Image.open(vert_png).convert("RGB"), np.float32)
    r, g, b = v[..., 0], v[..., 1], v[..., 2]
    return (~((g > 110) & (g > 1.45 * r) & (g > 1.45 * b))).astype(np.float32), v


def decoupe(alpha, rgb, mini):
    """Composantes connexes du masque -> liste de calques RGBA (boîte, pieds). Les miettes (< mini px) sont ignorées."""
    H, W = alpha.shape
    m = alpha > 0.5
    lab, n = ndimage.label(m)
    tailles = ndimage.sum(m, lab, range(1, n + 1))
    comps = [i + 1 for i, t in enumerate(tailles) if t >= mini]
    calques = []
    for c in comps:
        mc = lab == c
        mc = ndimage.binary_fill_holes(mc)
        a = ndimage.binary_erosion(mc, iterations=1).astype(np.float32)        # 1 px de moins : pas de liseré du décor
        a = ndimage.gaussian_filter(a, 0.8)
        ys, xs = np.where(mc)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        pad = 24
        Y0, Y1, X0, X1 = max(0, y0 - pad), min(H, y1 + pad), max(0, x0 - pad), min(W, x1 + pad)
        calques.append({"x0": int(X0), "y0": int(Y0), "x1": int(X1), "y1": int(Y1), "pied": int(y1 - Y0), "aire": int(tailles[c - 1]),
                        "rgba": np.dstack([rgb[Y0:Y1, X0:X1], a[Y0:Y1, X0:X1, None] * 255]).astype(np.uint8),
                        "coupe_bas": bool(y1 >= H - 2)})
    calques.sort(key=lambda c: -c["aire"])
    return calques


def zones_yeux(orig, ferme, calque):
    """Masque des yeux d'un calque = ce qui change entre l'illustration et sa version « yeux fermés », dans la moitié haute."""
    x0, y0, x1, y1 = calque["x0"], calque["y0"], calque["x1"], calque["y1"]
    a = calque["rgba"][..., 3] > 128
    d = np.abs(orig[y0:y1, x0:x1].astype(np.float32) - ferme[y0:y1, x0:x1].astype(np.float32)).sum(-1) > 70
    h = y1 - y0
    d &= a & (np.arange(h)[:, None] < 0.62 * h)
    lab, n = ndimage.label(ndimage.binary_dilation(d, iterations=4))
    if n == 0: return None
    tailles = ndimage.sum(d, lab, range(1, n + 1))
    ordre = np.argsort(tailles)[::-1][:2]
    garde = [int(i) + 1 for i in ordre if tailles[i] >= 100]
    if not garde: return None
    m = np.isin(lab, garde)
    aire = m.sum() / max(1, a.sum())
    if not (0.002 <= aire <= 0.08):      # trop petit = bruit ; trop grand = Qwen a redessiné autre chose que les yeux
        return None
    return ndimage.gaussian_filter(m.astype(np.float32), 2.5)


def yeux_procedural(rgba):
    """Trouve les deux yeux (gros disques sombres dans la moitié haute, même hauteur, même taille) et fabrique la version
    « yeux fermés » : disque rempli de la couleur du pelage autour + paupière en arc (le style de la série). Sans IA, 0 s,
    toujours aligné. Renvoie (rgb_ferme, masque_yeux) ou None."""
    rgb = rgba[..., :3].astype(np.float32); a = rgba[..., 3] > 128
    h, w = a.shape
    lum = rgb.mean(-1)
    sombre = (lum < 70) & a & (np.arange(h)[:, None] < 0.65 * h)
    sombre = ndimage.binary_fill_holes(ndimage.binary_closing(sombre, iterations=2))
    lab, n = ndimage.label(sombre)
    if n < 2: return None
    aire_p = a.sum(); cands = []
    for i in range(1, n + 1):
        m = lab == i; s_ = m.sum()
        if not (0.0015 * aire_p <= s_ <= 0.05 * aire_p): continue
        ys, xs = np.where(m); bh, bw = int(np.ptp(ys)) + 1, int(np.ptp(xs)) + 1
        if bh == 0 or bw == 0: continue
        rond = s_ / (bw * bh); allonge = max(bh, bw) / min(bh, bw)
        if rond < 0.5 or allonge > 2.4: continue           # pas une pointe d'oreille, pas une bande (œil de 3/4 : allongé)
        cands.append({"m": m, "cx": xs.mean(), "cy": ys.mean(), "r": (bw + bh) / 4, "aire": s_})
    best = None
    for i in range(len(cands)):
        for j in range(i + 1, len(cands)):
            u, v = cands[i], cands[j]
            dy = abs(u["cy"] - v["cy"]); dx = abs(u["cx"] - v["cx"]); r = (u["r"] + v["r"]) / 2
            if dy > 0.9 * r or not (1.2 * r <= dx <= 7 * r): continue
            if max(u["aire"], v["aire"]) > 3.2 * min(u["aire"], v["aire"]): continue
            score = u["aire"] + v["aire"] - 3 * dy
            if best is None or score > best[0]: best = (score, u, v)
    if best is None: return None
    ferme = rgb.copy(); masque = np.zeros((h, w), np.float32)
    for e in best[1:]:
        m = ndimage.binary_dilation(e["m"], iterations=3)
        anneau = ndimage.binary_dilation(m, iterations=9) & ~m & a
        if anneau.sum() < 20: return None
        peau = np.percentile(rgb[anneau], 35, axis=0)          # côté sombre du pelage voisin (le clair = joue, reflet)
        enc = np.median(rgb[e["m"] & (lum < 50)], axis=0) if (e["m"] & (lum < 50)).sum() > 10 else np.array([40, 25, 15], np.float32)
        ferme[m] = peau
        yy, xx = np.mgrid[0:h, 0:w]
        rx, ry = e["r"] * 1.05, e["r"] * 0.70; ep = max(1.8, e["r"] * 0.19)
        ang = np.arctan2((yy - e["cy"]) / ry, (xx - e["cx"]) / rx)
        dist = np.abs(np.hypot((xx - e["cx"]) / rx, (yy - e["cy"]) / ry) - 1.0) * min(rx, ry)
        arc = (dist < ep) & (ang > 0.25) & (ang < math.pi - 0.25)       # arc du bas : œil fermé souriant
        ferme[arc] = enc
        zone = ndimage.binary_dilation(m, iterations=6).astype(np.float32)
        masque = np.maximum(masque, ndimage.gaussian_filter(zone, 2.0))
    return np.clip(ferme, 0, 255).astype(np.uint8), np.clip(masque, 0, 1)


def orientation(rgba):
    """+1 = regarde vers la droite, -1 = vers la gauche, 0 = de face / inconnu. Yeux décalés dans la tête (vue de 3/4),
    sinon tête en avant du corps (course, saut)."""
    a = rgba[..., 3] > 128; h, w = a.shape
    if a.sum() < 100: return 0
    haut = a[: int(0.4 * h)]; bas = a[int(0.5 * h):]
    cx_h = np.where(haut)[1].mean() if haut.any() else w / 2; cx_b = np.where(bas)[1].mean() if bas.any() else w / 2
    lum = rgba[..., :3].astype(np.float32).mean(-1)
    sombre = (lum < 70) & a & (np.arange(h)[:, None] < 0.65 * h)
    lab, n = ndimage.label(sombre); yeux = []
    for i in range(1, n + 1):
        m = lab == i; s_ = m.sum()
        if 0.0015 * a.sum() <= s_ <= 0.05 * a.sum():
            ys, xs = np.where(m); bh, bw = np.ptp(ys) + 1, np.ptp(xs) + 1
            if s_ / (bw * bh) >= 0.5 and max(bh, bw) / min(bh, bw) <= 2.4: yeux.append((xs.mean(), ys.mean()))
    if len(yeux) >= 2:
        yeux.sort(key=lambda e: e[1]); e1, e2 = yeux[0], yeux[1]
        cx_yeux = (e1[0] + e2[0]) / 2; ligne = int((e1[1] + e2[1]) / 2)
        tete = a[max(0, ligne - 40): ligne + 40]
        cx_t = np.where(tete)[1].mean() if tete.any() else w / 2
        if abs(cx_yeux - cx_t) > 0.06 * w: return 1 if cx_yeux > cx_t else -1
    if abs(cx_h - cx_b) > 0.08 * w: return 1 if cx_h > cx_b else -1
    return 0


def calques_plan(plan_png, noms, out_dir, W, H, log=print):
    """Fabrique (ou relit) les calques d'une illustration. Renvoie le dict meta + tableaux chargés."""
    plan_png = Path(plan_png); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.md5(plan_png.read_bytes()).hexdigest()[:12]
    meta_f = out_dir / "meta.json"
    if meta_f.exists() and json.load(open(meta_f)).get("hash") == h and (out_dir / "fond.png").exists():
        meta = json.load(open(meta_f))
        if meta.get("yeux_version") != 2:     # calques faits avant les yeux procéduraux : on complète sans tout refaire
            for k, c in enumerate(meta["calques"]):
                if c.get("yeux"): continue
                rgba = np.asarray(Image.open(out_dir / f"perso_{k}.png").convert("RGBA"))
                if (rgba[..., 3] > 128).sum() < 0.04 * meta["largeur"] * meta["hauteur"]: continue
                if "face" not in c: c["face"] = orientation(rgba)
                r = yeux_procedural(rgba)
                if r is None: continue
                Image.fromarray(np.dstack([r[0], rgba[..., 3]]), "RGBA").save(out_dir / f"perso_{k}_ferme.png")
                Image.fromarray((r[1] * 255).astype(np.uint8), "L").save(out_dir / f"yeux_{k}.png"); c["yeux"] = True
            meta["yeux_version"] = 2; json.dump(meta, open(meta_f, "w"), indent=1)
            log(f"calques : {plan_png.stem} yeux recalculés ({sum(c['yeux'] for c in meta['calques'])})")
        return charger_calques(out_dir, W, H)
    for f in out_dir.glob("*"): 
        try: f.unlink()
        except OSError: pass
    qui = qui_texte(noms)
    t0 = time.time()
    P.qwen_edit(TETE + f"{qui} completely removed from the picture. Only the empty landscape remains; the ground and the background "
                f"continue naturally where {qui} stood, exactly as they are elsewhere in the picture. No animals at all, no text.", [str(plan_png)], str(out_dir / "fond.png"),
                seed=701, negatif=P.CFG.get("negatif_histoire"), pas=P.CFG.get("calques", {}).get("pas_fond", 20))
    log(f"calques : {plan_png.stem} fond ({time.time()-t0:.0f}s)")
    orig = np.asarray(Image.open(plan_png).convert("RGB"))
    Hi, Wi = orig.shape[:2]
    t0 = time.time(); mode = "birefnet"
    if matte_birefnet(str(plan_png), str(out_dir / "matte.png")):
        alpha = np.asarray(Image.open(out_dir / "matte.png").convert("L"), np.float32) / 255
        if alpha.shape != (Hi, Wi):
            alpha = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).resize((Wi, Hi), Image.BILINEAR), np.float32) / 255
        rgb = orig
    else:
        mode = "vert"
        P.qwen_edit(f"Picture 1 is a frame from a children's cartoon. Draw exactly {qui}: same pose, same size, same position in the "
                    f"frame, same face, same knitted garments, same colors and outlines, but the ENTIRE background is replaced by one flat, "
                    f"uniform, pure bright green color (RGB 0,255,0). Nothing else: no ground, no shadow, no plants, no moon, no text.",
                    [str(plan_png)], str(out_dir / "vert.png"), seed=702, negatif=P.CFG.get("negatif_histoire"))
        alpha, rgb = alpha_depuis_vert(out_dir / "vert.png")
        rgb = rgb.astype(np.uint8)
    log(f"calques : {plan_png.stem} masque {mode} ({time.time()-t0:.0f}s)")
    calques = decoupe(alpha, rgb, mini=0.0025 * Hi * Wi)
    if not calques:   # garde-fou : personnage non détecté -> on garde l'illustration entière comme fond (jamais un décor vide)
        shutil.copy(plan_png, out_dir / "fond.png"); mode += "+aucun"
        log(f"calques : {plan_png.stem} AUCUN personnage détecté -> illustration entière en fond")
    if mode == "vert":   # anti-frange verte sur les contours
        for c in calques:
            rg = c["rgba"]; bord = (rg[..., 3] > 0) & (rg[..., 3] < 250) & (rg[..., 1] > rg[..., 0]) & (rg[..., 1] > rg[..., 2])
            rg[bord, 1] = np.minimum(rg[bord, 1], ((rg[bord, 0].astype(int) + rg[bord, 2]) // 2).astype(np.uint8))
    grands = [c for c in calques if c["aire"] >= 0.04 * Hi * Wi]
    if grands and P.CFG.get("calques", {}).get("yeux_qwen"):
        t0 = time.time()
        P.qwen_edit(TETE + f"{qui} now has the eyes gently closed, as if peacefully asleep, with a soft calm expression. Everything else "
                    "stays exactly identical, same position and pose.", [str(plan_png)], str(out_dir / "ferme.png"), seed=703,
                    negatif=P.CFG.get("negatif_histoire"))
        ferme = np.asarray(Image.open(out_dir / "ferme.png").convert("RGB").resize((Wi, Hi), Image.LANCZOS))
        log(f"calques : {plan_png.stem} yeux fermés ({time.time()-t0:.0f}s)")
    else:
        ferme = None
    meta = {"hash": h, "mode": mode, "largeur": Wi, "hauteur": Hi, "noms": noms, "yeux_version": 2, "calques": []}
    for k, c in enumerate(calques):
        Image.fromarray(c["rgba"], "RGBA").save(out_dir / f"perso_{k}.png")
        yeux = None
        if any(c is g for g in grands):
            r = yeux_procedural(c["rgba"])
            if r is not None:
                rgb_f, yeux = r
                Image.fromarray(np.dstack([rgb_f, c["rgba"][..., 3]]), "RGBA").save(out_dir / f"perso_{k}_ferme.png")
            elif ferme is not None:
                yeux = zones_yeux(orig, ferme, c)
                if yeux is not None:
                    x0, y0, x1, y1 = c["x0"], c["y0"], c["x1"], c["y1"]
                    Image.fromarray(np.dstack([ferme[y0:y1, x0:x1], c["rgba"][..., 3]]), "RGBA").save(out_dir / f"perso_{k}_ferme.png")
        if yeux is not None:
            Image.fromarray((yeux * 255).astype(np.uint8), "L").save(out_dir / f"yeux_{k}.png")
        meta["calques"].append({k2: v for k2, v in c.items() if k2 != "rgba"} | {"yeux": yeux is not None, "face": orientation(c["rgba"])})
    json.dump(meta, open(meta_f, "w"), indent=1)
    log(f"calques : {plan_png.stem} -> {len(calques)} personnage(s), yeux {sum(c['yeux'] for c in meta['calques'])}")
    return charger_calques(out_dir, W, H)


def cou_de(alpha):
    """Ligne du cou d'un calque (en px du calque) : la rangée la plus étroite entre 25 et 70 % de la hauteur, nettement plus
    étroite que ce qu'il y a au-dessus (la tête) et au-dessous (le corps). None si le personnage n'a pas de cou visible."""
    h = alpha.shape[0]; larg = alpha.sum(axis=1).astype(np.float32)
    if h < 60 or larg.max() == 0: return None
    y0, y1 = int(0.25 * h), int(0.70 * h)
    seg = larg[y0:y1]
    if not seg.size: return None
    k = int(np.argmin(np.convolve(seg, np.ones(9) / 9, mode="same"))) ; y = y0 + k
    if larg[y] < 0.72 * larg[:y].max() and larg[y] < 0.72 * larg[y:].max() and larg[y] > 0.08 * larg.max():
        return int(y)
    return None


def charger_calques(out_dir, W, H):
    """Charge les calques à la taille de sortie (facteur d'échelle appliqué aux boîtes)."""
    out_dir = Path(out_dir); meta = json.load(open(out_dir / "meta.json"))
    sx, sy = W / meta["largeur"], H / meta["hauteur"]
    fond = np.asarray(Image.open(out_dir / "fond.png").convert("RGB").resize((W, H), Image.LANCZOS), np.float32)
    persos = []
    # garde-fou (plan_057 d'E01 : 8 « personnages » = des champignons) : seuls les (amis cités + 1) plus grands calques
    # sont animés, et jamais un calque < 12 % du plus grand ; les autres sont posés fixes (morceau détaché, champignon)
    plus_grand = max([c["aire"] for c in meta["calques"]] or [1]); n_max = len(meta.get("noms") or []) + 1
    retenus = [k for k, c in enumerate(meta["calques"]) if c["aire"] >= 0.12 * plus_grand][:n_max]
    for k, c in enumerate(meta["calques"]):
        im = Image.open(out_dir / f"perso_{k}.png").convert("RGBA")
        w, h = round(im.width * sx), round(im.height * sy)
        cou = c.get("cou", cou_de(np.asarray(im)[..., 3] > 128))     # ligne du cou : rotation rigide de la tête
        rgba = np.asarray(im.resize((w, h), Image.LANCZOS), np.float32)
        p = {"rgb": rgba[..., :3], "a": rgba[..., 3] / 255, "x0": c["x0"] * sx, "y0": c["y0"] * sy, "pied": c["pied"] * sy,
             "coupe_bas": c["coupe_bas"], "aire": c["aire"] * sx * sy, "yeux": None, "ferme": None, "face": c.get("face", 0),
             "cou": cou * sy if cou is not None else None, "anime": k in retenus}   # non retenu = posé fixe (morceau, champignon)
        if c.get("yeux"):
            p["yeux"] = np.asarray(Image.open(out_dir / f"yeux_{k}.png").convert("L").resize((w, h), Image.BILINEAR), np.float32) / 255
            p["ferme"] = np.asarray(Image.open(out_dir / f"perso_{k}_ferme.png").convert("RGBA").resize((w, h), Image.LANCZOS), np.float32)[..., :3]
        persos.append(p)
    return {"fond": fond, "persos": persos, "meta": meta}


# ----------------------------------------------------------------------------------- 3. rendu parallèle des plans
def rendre_plan(args):
    """Travail d'un processus fils : charge les calques (ou le fond seul) et anime un plan. Renvoie les lignes de journal."""
    plan_sc, cal_dir, img, out_dir, hero, W, H = args
    import anime_calques
    lignes = []
    if cal_dir:
        cal = charger_calques(cal_dir, W, H)
    else:
        cal = {"fond": np.asarray(Image.open(img).convert("RGB").resize((W, H), Image.LANCZOS), np.float32), "persos": [], "meta": {}}
    anime_calques.anime_plan(plan_sc, cal, out_dir, hero=hero, log=lignes.append)
    return lignes
