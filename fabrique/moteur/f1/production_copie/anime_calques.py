"""Animation calculée des calques (voir calques.py). anime_plan(plan_scenes, cal, out_dir, cast, hero) écrit un mp4 par scène
(taille et cadence de config.json -> sortie), les scènes d'un plan s'enchaînant dans un seul état continu.
Vocabulaire lu dans le champ `motion` : saut / marche / vol (direction, « closer », « away »), tête qui se tourne ou se penche,
oreilles, s'endort / se réveille, clignements ; caméra : pousse, recule, panoramique, fixe. Tout le reste = vie au repos."""
import math, re, random, subprocess
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
import production as P

W = H = FPS = None


def _init():
    global W, H, FPS
    so = P.CFG["sortie"]; W, H, FPS = so["largeur"], so["hauteur"], so["fps"]


def lisse(u):  # 0..1 -> 0..1 en douceur
    u = min(1.0, max(0.0, u)); return 0.5 - 0.5 * math.cos(math.pi * u)


# ----------------------------------------------------------------------------------------- 1. lecture du mouvement
LOCO = re.compile(r"\b(hops?|hopping|bounds?|bounces?|leaps?|jumps?|skips?)\b", re.I)
MARCHE = re.compile(r"\b(walks?|paces?|trots?|wanders?|steps?|runs?|scampers?|dashes|strolls?|waddles?|crawls?|creeps?)\b", re.I)
VOL = re.compile(r"\b(flies|fly|flutters?|glides?|swoops?|soars?|hovers?|swims?|paddles?)\b", re.I)
TETE = re.compile(r"\b(turns? (his|her|its) head|looks? (up|down|left|right|around|over|toward|towards|at|back)|tilts? (his|her|its) head|nods?|peeks?|glances?)\b", re.I)
OREILLES = re.compile(r"\bears?\b", re.I)
DORT = re.compile(r"\b(falls? asleep|closes? (his|her|its|their) eyes|eyes (close|closed|drift shut)|asleep|dozes?|drifts? off|sleeps?|sleeping|snoozes?)\b", re.I)
REVEIL = re.compile(r"\b(wakes?|opens? (his|her|its|their) eyes|eyes open)\b", re.I)
CORPS = re.compile(r"\b(sits? up|stands? (up|tall)|stretch(es)?|yawns?|shifts? (his|her|its) weight|leans?|sways?|rocks?|settles?|smooths?|wiggles?|shakes?)\b", re.I)


def lire_mouvement(motion, camera):
    m = motion or ""
    mv = {"type": "repos", "dir": 0, "zoom": 0, "tete": bool(TETE.search(m)), "oreilles": bool(OREILLES.search(m)),
          "dort": bool(DORT.search(m)) and not REVEIL.search(m), "reveil": bool(REVEIL.search(m)), "corps": bool(CORPS.search(m)),
          "cam": "static"}
    if LOCO.search(m): mv["type"] = "saut"
    elif VOL.search(m): mv["type"] = "vol"
    elif MARCHE.search(m): mv["type"] = "marche"
    if mv["type"] != "repos":
        if re.search(r"\b(to the left|leftwards?|left)\b", m, re.I): mv["dir"] = -1
        elif re.search(r"\b(to the right|rightwards?|right)\b", m, re.I): mv["dir"] = 1
        if re.search(r"\b(closer|toward(s)? (the camera|us|the viewer)|nearer|forward)\b", m, re.I): mv["zoom"] = 1
        elif re.search(r"\b(away|into the distance|deeper|farther|further away|off into)\b", m, re.I): mv["zoom"] = -1
    cm = re.search(r"The camera[^.]*\.", m, re.I)
    c = (cm.group(0).lower() if cm else "") or (camera or "")
    if "pull" in c or "back" in c: mv["cam"] = "pull"
    elif "push" in c or "closer" in c or "zoom" in c: mv["cam"] = "push"
    elif "left" in c: mv["cam"] = "pan_left"
    elif "right" in c: mv["cam"] = "pan_right"
    elif "still" in c or "static" in c or "locked" in c: mv["cam"] = "static"
    elif camera == "slow_push": mv["cam"] = "push"
    return mv


# ------------------------------------------------------------------------------------------ 2. transformations
def deforme(rgb, a, pied, sx, sy, oreilles=0.0, tete=0.0, penche=0.0, cou=None):
    """Échelle autour des pieds (respiration, écrasement), balancement du haut (oreilles), rotation de la tête (rigide
    au-dessus du cou quand il est connu, sinon pondérée vers le haut), inclinaison du corps (cisaillement)."""
    ph, pw = a.shape
    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    rel = np.clip((pied - yy) / max(pied, 1), 0, 1)
    cx = pw / 2
    sy_ = pied - (pied - yy) / sy
    sx_ = cx + (xx - cx) / sx - oreilles * rel ** 2 - penche * rel
    if tete:
        if cou is not None and 0 < cou < pied:
            w = np.clip((cou + 15 - yy) / 30.0, 0, 1)      # tête rigide au-dessus du cou, bande de fondu de 30 px
            col = a[: int(cou)].sum(axis=0)
            px = (col * np.arange(pw)).sum() / max(1.0, col.sum()); py = float(cou)
        else:
            w = rel ** 1.5; px, py = cx, pied * 0.45       # pas de cou visible : flexion douce vers le haut
        ang = math.radians(tete) * w
        dx, dy = sx_ - px, sy_ - py
        sx_ = px + dx * np.cos(ang) - dy * np.sin(ang)
        sy_ = py + dx * np.sin(ang) + dy * np.cos(ang)
    co = [sy_, sx_]
    out = np.stack([ndimage.map_coordinates(rgb[..., c], co, order=1, mode="nearest") for c in range(3)], -1)
    oa = ndimage.map_coordinates(a, co, order=1, mode="constant", cval=0.0)
    return out, oa


def poser(img, rgb, a, x_pied, y_pied, pied, zoom=1.0):
    ph, pw = a.shape
    if abs(zoom - 1) > 1e-3:
        hh, ww = max(2, int(ph * zoom)), max(2, int(pw * zoom))
        rgb = np.asarray(Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).resize((ww, hh), Image.BILINEAR), np.float32)
        a = np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).resize((ww, hh), Image.BILINEAR), np.float32) / 255
    else:
        hh, ww = ph, pw
    X0, Y0 = int(round(x_pied - ww / 2)), int(round(y_pied - pied * zoom))
    xa, ya, xb, yb = max(0, X0), max(0, Y0), min(W, X0 + ww), min(H, Y0 + hh)
    if xb <= xa or yb <= ya: return img
    ca = a[ya - Y0:yb - Y0, xa - X0:xb - X0][..., None]
    img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - ca) + rgb[ya - Y0:yb - Y0, xa - X0:xb - X0] * ca
    return img


def ombre(img, x, y, largeur, force):
    if force <= 0: return img
    xa, xb = int(max(0, x - largeur)), int(min(W, x + largeur)); ya, yb = int(max(0, y - largeur / 5)), int(min(H, y + largeur / 5))
    if xb <= xa or yb <= ya: return img
    yy, xx = np.mgrid[ya:yb, xa:xb]
    e = ((xx - x) / (largeur / 2)) ** 2 + ((yy - y) / (largeur / 8)) ** 2
    s = np.clip(1 - e, 0, 1) ** 1.5 * force * 0.35
    img[ya:yb, xa:xb] *= (1 - s[..., None]); return img


def lucioles(img, t, n, graine):
    rnd = random.Random(graine)
    for i in range(n):
        ax, ay, f1, f2 = rnd.random(), rnd.random(), 0.3 + rnd.random() * 0.5, 0.8 + rnd.random()
        x = W * (0.1 + 0.8 * ((ax + 0.012 * t * (1 + i % 3)) % 1)) + 25 * math.sin(t * f1 + i)
        y = H * (0.2 + 0.55 * ((ay + 0.006 * t) % 1)) + 18 * math.sin(t * f2 + 2 * i)
        inten = max(0.0, math.sin(t * (0.9 + 0.25 * i) + i * 1.7)) ** 2
        if inten < 0.05: continue
        ya, yb, xa, xb = int(max(0, y - 12)), int(min(H, y + 12)), int(max(0, x - 12)), int(min(W, x + 12))
        if yb <= ya or xb <= xa: continue
        yy, xx = np.mgrid[ya:yb, xa:xb]; gl = np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / 12.0) * inten * 0.85
        img[ya:yb, xa:xb] += gl[..., None] * np.array([255, 225, 110], np.float32)
    return img


def camera(img, k, dx=0.0):
    """Zoom k (>1 = plus près) centré, décalage horizontal dx (fraction de la largeur)."""
    if abs(k - 1) < 1e-4 and abs(dx) < 1e-5: return img
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    return np.asarray(im.transform((W, H), Image.AFFINE, (1 / k, 0, W * (1 - 1 / k) / 2 + dx * W, 0, 1 / k, H * (1 - 1 / k) / 2), resample=Image.BICUBIC), np.float32)


# ------------------------------------------------------------------------------------------------- 3. le plan
def anime_plan(plan_scenes, cal, out_dir, hero=None, log=print):
    """Rend chaque scène du plan en mp4 (s{id}.mp4) à partir des calques `cal` (calques.charger_calques)."""
    _init()
    out_dir = Path(out_dir); fond = cal["fond"]; persos = cal["persos"]
    total = sum(s["_duree"] for s in plan_scenes)
    rnd = random.Random(plan_scenes[0]["id"])
    nuit = bool(re.search(r"\b(moon|moonlit|moonlight|night|stars?|dark|dusk|lantern|glow)\b", (plan_scenes[0].get("image") or ""), re.I))
    # état par personnage (le plus grand = héros, seul à se déplacer ; les autres vivent sur place)
    etats = []
    for i, p in enumerate(persos):
        ph, pw = p["a"].shape
        etats.append({"x": p["x0"] + pw / 2, "y": p["y0"] + p["pied"], "zoom": 1.0, "yeux": 0.0, "phase": rnd.random() * 6.28,
                      "clins": [], "mobile": (i == 0)})
    # plan de caméra : un seul mouvement doux sur tout le plan (comme camera_clip)
    mv0 = lire_mouvement(plan_scenes[0].get("motion"), plan_scenes[0].get("camera"))
    amp = min(0.08, 0.004 * total + 0.03)
    def cam_k(p):
        p = lisse(p)
        if mv0["cam"] == "push": return 1 + amp * p, 0.0
        if mv0["cam"] == "pull": return 1 + amp * (1 - p), 0.0
        if mv0["cam"] == "pan_left": return 1 + amp, -amp * 0.5 * (1 - 2 * p)
        if mv0["cam"] == "pan_right": return 1 + amp, amp * 0.5 * (1 - 2 * p)
        return 1 + 0.03 * p, 0.004 * math.sin(2 * math.pi * p * 1.3)
    t_plan = 0.0; derniere = None
    for s in plan_scenes:
        D = s["_duree"]; n = max(2, round(D * FPS)); mv = lire_mouvement(s.get("motion"), s.get("camera"))
        # déplacement du héros pendant cette scène (au plus 5 s, ~60 % de la scène), direction choisie dans l'espace libre
        depl = None
        n_anim = sum(1 for q in persos if q.get("anime", True))
        groupe = len(cal.get("meta", {}).get("noms", [])) >= 2 and n_anim == 1       # deux amis dans un seul calque
        if mv["type"] != "repos" and persos and not groupe:
            e = etats[0]; p = persos[0]; ph, pw = p["a"].shape
            duree = min(5.0, max(1.2, 0.6 * D))
            d = mv["dir"] or p.get("face", 0) or (1 if e["x"] < W / 2 else -1)     # sens : texte, puis regard, puis espace libre
            marge = pw * e["zoom"] * 0.5 + 40
            libre = (W - marge - e["x"]) if d > 0 else (e["x"] - marge)
            dist = max(0.0, min(0.28 * W, libre * 0.85))
            zf = {1: 1.12, -1: 0.92, 0: 1.0}[mv["zoom"]]
            dy = (0.07 * H if mv["zoom"] == 1 else -0.035 * H if mv["zoom"] == -1 else 0.0) if not p["coupe_bas"] else 0.0
            depl = {"t0": 0.35, "t1": 0.35 + duree, "x0": e["x"], "x1": e["x"] + d * dist, "y0": e["y"], "y1": e["y"] + dy,
                    "z0": e["zoom"], "z1": e["zoom"] * zf, "type": mv["type"], "T": 0.62 if mv["type"] == "saut" else 0.5}
        # clignements et micro-actions de la scène (regards, coups d'oreille, tassements) : la vie entre les actions
        for e in etats:
            t = 0.9 + rnd.random() * 1.5; e["clins"] = []
            while t < D - 0.3: e["clins"].append(t); t += 2.6 + rnd.random() * 2.4
            e["regards"] = [(0.4 + rnd.random() * 0.8, 1 if (s["id"] + rnd.randrange(2)) % 2 else -1)] if mv["tete"] else []
            t = 2.5 + rnd.random() * 3.0
            while t < D - 2.5: e["regards"].append((t, rnd.choice((-1, 1)))); t += 5.0 + rnd.random() * 4.0
            e["coups"] = []; t = 1.5 + rnd.random() * 4.0
            while t < D - 1.0: e["coups"].append(t); t += 4.0 + rnd.random() * 5.0
            e["tasse"] = []; t = 3.0 + rnd.random() * 5.0
            while t < D - 1.0: e["tasse"].append(t); t += 7.0 + rnd.random() * 6.0
        ff = subprocess.Popen([P.FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                               "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p", str(out_dir / f"s{s['id']:03d}.mp4")],
                              stdin=subprocess.PIPE)
        for i in range(n):
            t = i / FPS; img = fond.copy()
            if nuit: img = lucioles(img, t_plan + t, 3, plan_scenes[0]["id"])
            for k, (p, e) in enumerate(zip(persos, etats)):
                ph, pw = p["a"].shape
                if not p.get("anime", True):                      # calque posé fixe (morceau détaché, objet pris pour un ami)
                    img = poser(img, p["rgb"], p["a"], e["x"], e["y"], p["pied"]); continue
                # --- état des yeux (0 ouverts, 1 fermés) : sommeil, réveil, clignement par volet
                if mv["dort"] and (e["mobile"] or n_anim == 1):
                    cible = 1.0 if t > 0.3 * D else 0.0
                    e["yeux"] += (cible - e["yeux"]) * 0.12
                elif mv["reveil"]:
                    e["yeux"] += (0.0 - e["yeux"]) * 0.15
                clin = 0.0
                for c in e["clins"]:
                    d_ = t - c
                    if 0 <= d_ < 0.22: clin = min(d_ / 0.08, 1.0, (0.22 - d_) / 0.08)
                ferm = max(e["yeux"], clin)
                rgb, a = p["rgb"], p["a"]
                if ferm > 0.01 and p["yeux"] is not None:
                    ys = np.where(p["yeux"].max(axis=1) > 0.3)[0]
                    if len(ys):
                        yt, yb = ys[0], ys[-1]
                        volet = np.clip((ferm * 1.25 - (np.arange(ph) - yt) / max(1, yb - yt)) * 5, 0, 1)[:, None]   # paupière qui descend
                        wgt = (p["yeux"] * volet)[..., None]
                        rgb = rgb * (1 - wgt) + p["ferme"] * wgt
                # --- respiration, oreilles, tête, corps
                T = t_plan + t
                resp = math.sin(2 * math.pi * T / (3.4 if ferm < 0.5 else 4.6) + e["phase"])
                sx, sy = 1 - 0.007 * resp, 1 + (0.016 if ferm < 0.5 else 0.020) * resp
                ech = min(1, ph / 600)
                ore = (9.0 if mv["oreilles"] and e["mobile"] else 5.0) * math.sin(2 * math.pi * T / 5.1 + e["phase"]) * ech
                for c in e["coups"]:                                    # coup d'oreille : vif, 0,5 s
                    d_ = t - c
                    if 0 <= d_ < 0.5: ore += 14.0 * ech * math.sin(math.pi * d_ / 0.5) * math.sin(4 * math.pi * d_ / 0.5)
                tete = (1.8 if p.get("cou") else 1.3) * math.sin(2 * math.pi * T / 7.9 + e["phase"] * 1.3)   # tête jamais tout à fait immobile
                for (c, sens) in e["regards"]:                           # regard : se tourne, tient, revient (2,6 s)
                    tt = t - c
                    if 0 <= tt < 2.6: tete += (6.0 if p.get("cou") else 4.0) * sens * lisse(tt / 0.7) * lisse((2.6 - tt) / 0.7)
                penche = 3.0 * math.sin(2 * math.pi * T / 6.3 + e["phase"])                # balancement lent du corps
                if mv["corps"] and e["mobile"]: penche += 4.0 * math.sin(2 * math.pi * T / 7.3 + e["phase"])
                for c in e["tasse"]:                                     # petit tassement puis redressement (0,9 s)
                    d_ = t - c
                    if 0 <= d_ < 0.9: q = math.sin(math.pi * d_ / 0.9); sy *= 1 - 0.035 * q; sx *= 1 + 0.02 * q
                x, y, zoom = e["x"], e["y"], e["zoom"]
                # --- déplacement
                if depl and e["mobile"] and depl["t0"] <= t <= depl["t1"]:
                    u = (t - depl["t0"]) / (depl["t1"] - depl["t0"]); ul = lisse(u) if depl["type"] != "saut" else u
                    x = depl["x0"] + (depl["x1"] - depl["x0"]) * ul; y = depl["y0"] + (depl["y1"] - depl["y0"]) * ul
                    zoom = depl["z0"] + (depl["z1"] - depl["z0"]) * ul
                    phs = ((t - depl["t0"]) % depl["T"]) / depl["T"]
                    if depl["type"] == "saut":
                        air = 4 * phs * (1 - phs); contact = 1.0 if (phs < 0.12 or phs > 0.88) else 0.0
                        y -= 0.065 * ph * zoom * air
                        sx *= 1 + 0.06 * contact - 0.03 * air; sy *= 1 - 0.07 * contact + 0.05 * air
                        ore += -9.0 * math.cos(2 * math.pi * phs) * min(1, ph / 600)
                        sol = depl["y0"] + (depl["y1"] - depl["y0"]) * ul
                        if not p["coupe_bas"]: img = ombre(img, x, sol + 3, pw * 0.35 * zoom, 1 - 0.75 * air)
                    elif depl["type"] == "marche":
                        y -= 0.012 * ph * abs(math.sin(2 * math.pi * phs)); penche += 2.0 * (1 if depl["x1"] > depl["x0"] else -1)
                    else:   # vol
                        y += 0.03 * ph * math.sin(2 * math.pi * phs); ore += 4.0 * math.sin(2 * math.pi * phs)
                    if t >= depl["t1"] - 1 / FPS:
                        e["x"], e["y"], e["zoom"] = depl["x1"], depl["y1"], depl["z1"]
                elif depl and e["mobile"] and t > depl["t1"]:
                    x, y, zoom = depl["x1"], depl["y1"], depl["z1"]
                rgb2, a2 = deforme(rgb, a, p["pied"], sx, sy, oreilles=ore, tete=tete, penche=penche, cou=p.get("cou"))
                img = poser(img, rgb2, a2, x, y, p["pied"], zoom)
            k_cam, dx = cam_k((t_plan + t) / total)
            img = camera(img, k_cam, dx)
            derniere = np.clip(img, 0, 255).astype(np.uint8)
            ff.stdin.write(derniere.tobytes())
        ff.stdin.close(); ff.wait()
        if depl:
            for e in etats:
                if e["mobile"]: e["x"], e["y"], e["zoom"] = depl["x1"], depl["y1"], depl["z1"]
        Image.fromarray(derniere).save(out_dir / f"s{s['id']:03d}_last.png")
        t_plan += D
        log(f"anim : scene {s['id']} (calques : {mv['type']}{', tête' if mv['tete'] else ''}{', dort' if mv['dort'] else ''}, {D:.1f}s)")
