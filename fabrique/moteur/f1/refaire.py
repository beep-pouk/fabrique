"""« Je coche, Fabrique refait » pour F1 (plan § 5.3), repris du « Refaire » de Bramble Studio (core/verification.py, 1.5.6) : les fichiers des
plans cochés (image, calques, clips de chacune de leurs scènes, lèvres, segments du montage), la vidéo finale et, si l'un d'eux la fait, la
miniature, sont DÉPLACÉS dans <atelier>\\_refaits\\<horodatage>\\ (jamais supprimés : l'avant reste à côté de l'après) ; la graine de leur image
est décalée (images\\_graines.json, lu par l'étape des images) ; les étapes à refaire sont rendues : seules ces pièces manquent, elles seules
sont refaites. Sans Django."""
import json
from datetime import datetime
from pathlib import Path

from fabrique.garde import Refus

ETAPES = ["images", "anim", "bramble", "montage", "revue"]  # = ETAPES_REFAIRE de Bramble Studio, et la revue (ses textes suivent le montage)


def unites(scenes: list[dict]) -> list[dict]:
    """Ce qui se refait : un plan (scène à image nouvelle, et les scènes « same » qui suivent, même après une interjection de Bramble) ou une
    scène de Bramble ; n = id de la scène. (= verification.unites)"""
    u = {}
    for i, s in enumerate(scenes):
        if s.get("image") and s["image"] != "same":
            memes = []
            for t in scenes[i + 1:]:
                if "bramble" in t and not t.get("image"):
                    continue
                if t.get("image") != "same":
                    break
                memes.append(t["id"])
            u[s["id"]] = {"n": s["id"], "image": True, "bramble": "bramble" in s, "scenes": [s["id"]] + memes}
        if "bramble" in s and s["id"] not in u:
            u[s["id"]] = {"n": s["id"], "image": False, "bramble": True, "scenes": [s["id"]]}
    return [u[k] for k in sorted(u)]


def fichiers_unite(u: dict) -> list[str]:
    """Image et calques du plan, clip de chaque scène du plan, lèvres, segment du montage de chaque scène. (= verification.fichiers_unite)"""
    n = u["n"]
    f = [f"images/plan_{n:03d}.png", f"calques/plan_{n:03d}"] + [c for m in u["scenes"] for c in (f"clips/s{m:03d}.mp4", f"clips/s{m:03d}_last.png")] if u["image"] else []
    f += [f"bramble/s{n:03d}.mp4"] if u["bramble"] else []
    return f + [f"montage/s{m:03d}.mp4" for m in u["scenes"]]


def deplacer(atelier: Path, rels: list[str], horodatage: str) -> list[str]:
    """Dans _refaits/<horodatage>/, même arborescence ; au premier échec (Windows : fichier ouvert), ce qui a bougé revient. (= verification.deplacer)"""
    vers = atelier / "_refaits" / horodatage
    faits = []
    try:
        for rel in rels:
            if (atelier / rel).exists():
                (vers / rel).parent.mkdir(parents=True, exist_ok=True)
                (atelier / rel).rename(vers / rel)
                faits.append(rel)
    except OSError as e:
        for fait in reversed(faits):
            (vers / fait).rename(atelier / fait)
        raise Refus(f"{rel} ne peut pas être déplacé ({e.__class__.__name__}) : fermer le lecteur vidéo et réessayer ; rien n'a bougé") from e
    return faits


def etapes(scenario: dict, plans: list[int]) -> tuple[list[int], list[str], bool]:
    """Les plans cochés (contrôlés), les étapes à refaire, et si la miniature en est faite ; rien ne bouge."""
    par_n = {u["n"]: u for u in unites(scenario.get("scenes", []))}
    choisis = sorted(set(plans))
    if not choisis:
        raise Refus("aucun plan coché")
    if inconnus := [n for n in choisis if n not in par_n]:
        raise Refus(f"plan(s) inconnu(s) : {inconnus}")
    miniature = any(str(m) == str(scenario.get("thumbnail_scene")) for n in choisis for m in par_n[n]["scenes"])
    return choisis, ETAPES[:-1] + (["miniature"] if miniature else []) + ETAPES[-1:], miniature


def preparer(atelier: Path, scenario: dict, plans: list[int], quand: datetime | None = None) -> dict:
    """Range les pièces des plans cochés et décale leurs graines ; rend les étapes à refaire, ce qui a été rangé et l'horodatage."""
    par_n = {u["n"]: u for u in unites(scenario.get("scenes", []))}
    choisis, a_refaire, miniature = etapes(scenario, plans)
    fichiers = [f for n in choisis for f in fichiers_unite(par_n[n])]
    if not any((atelier / f).exists() for f in fichiers):
        raise Refus(f"plans {choisis} : aucune de leurs pièces dans l'atelier (vidéo pas encore fabriquée ?)")
    graines_f = atelier / "images" / "_graines.json"
    graines = json.loads(graines_f.read_text(encoding="utf-8")) if graines_f.is_file() else {}
    for n in choisis:
        if par_n[n]["image"]:
            graines[str(n)] = int(graines.get(str(n), 0)) + 1  # graine = 1000 + id + décalage, lue par l'étape des images
    horodatage = f"{quand or datetime.now():%Y%m%d_%H%M%S_%f}"
    finale = [p.relative_to(atelier).as_posix() for p in (atelier / "final").glob("*.mp4")]
    ranges = deplacer(atelier, finale + fichiers + (["final/miniature.jpg"] if miniature else []), horodatage)
    graines_f.parent.mkdir(exist_ok=True)
    graines_f.write_text(json.dumps(graines, indent=1) + "\n", encoding="utf-8")
    return {"etapes": a_refaire, "ranges": ranges, "horodatage": horodatage, "plans": choisis}


def planche(scenario: dict) -> list[dict]:
    """Les plans d'un scénario, tels que la Planche (avant « Fabriquer ») et la Vérification (à cocher) les montrent."""
    images = {s.get("id"): s.get("image", "") for s in scenario.get("scenes", [])}
    return [{"n": u["n"], "image": images.get(u["n"], "") if u["image"] else "", "scenes": u["scenes"], "bramble": u["bramble"]}
            for u in unites(scenario.get("scenes", []))]
