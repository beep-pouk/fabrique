"""Égalité de F1 avec le moteur de Bramble Studio, sur le PC (outil de développement, jamais livré ; plan § 9, méthode de
OUTILS\\app\\docs\\EGALITE_REFERENCE.md). Les deux moteurs jouent la même étape sur les mêmes entrées, copiées d'un rendu fini de Bramble (lu
seulement) dans OUTILS\\fabrique_construction\\egalite\\<étape>\\{bramble,fabrique}\\<date>-<code> : Bramble Studio par son propre code
(OUTILS\\app\\studio\\moteur, importé en lecture, sur ses propres réglages et son projet), Fabrique par F1 sur une session importée de Bramble
(import pour de vrai dans une racine de travail, à côté). Sans carte : montage, miniature, revue (fichiers identiques octet pour octet),
images au niveau des consignes (ComfyUI simulé, juge factice : consignes et références envoyées identiques). Avec la carte (--carte, de nuit,
carte libre, jamais pendant un rendu : vérifié avant chaque moteur) : voix (3 scènes), images (3 plans), anim (2 plans), lèvres (1 plan), musique
(3 scènes), version de langue (une scène d'image et une de Bramble, phrases d'essai en français, sur les visuels du rendu), pour de vrai,
le même pilote de ComfyUI (celui de Fabrique) et le juge des images coupé des deux côtés. Rapport (cumulé) : egalite\\RAPPORT.json.
python outils_dev\\egalite.py [--etapes montage,miniature,revue,images] [--carte voix,images,anim,bramble,musique,langue [--relire]]"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tomllib
import types
import urllib.request
from datetime import datetime
from pathlib import Path

DEPOT = Path(__file__).resolve().parents[1]
SORTIE = DEPOT.parent / "fabrique_construction" / "egalite"
os.environ["FABRIQUE_RACINE"] = str(SORTIE / "FABRIQUE")
os.environ["DJANGO_SETTINGS_MODULE"] = "fabrique.settings"  # jamais celui de Bramble Studio (config.settings), même lancé depuis lui
sys.path.insert(0, str(DEPOT))

BRAMBLE = "1.5.6"  # la version d'où F1 est repris (test_f1.ECARTS)
RENDU = "2026-10-26-s1e01_refaire_1"  # le rendu de référence (le seul fini sur le disque)
SCENARIO = "2026-10-26-s1e01"
ENTREES = {  # ce que chaque étape lit dans l'atelier, copié du rendu de référence
    "montage": ["voix", "clips", "bramble", "musique.wav", "musique"],
    "miniature": ["images"],
    "revue": ["voix"],
    "images": [],
}
CARTE = {  # étape → (scènes prises dans le scénario, entrées copiées du rendu)
    "voix": (lambda sc, r: [s["id"] for s in sc["scenes"] if (s.get("narration") or "").strip()][:3], []),
    "images": (lambda sc, r: plans_images(sc, r), []),
    "anim": (lambda sc, r: [s["id"] for s in sc["scenes"] if not s.get("bramble") and s.get("image") and s["image"] != "same"
                            and (r / "images" / f"plan_{s['id']:03d}.png").is_file()][1:3], ["images", "voix"]),
    "bramble": (lambda sc, r: [min((s["id"] for s in sc["scenes"] if s.get("bramble") and (r / "bramble" / f"s{s['id']:03d}.mp4").is_file()),
                                   key=lambda i: (r / "voix" / f"s{i:03d}.wav").stat().st_size)], ["voix"]),
    "musique": (lambda sc, r: CARTE["voix"][0](sc, r), ["voix"]),
    # version française (phrases d'essai) d'une scène d'image et de la scène de Bramble la plus courte, sur les visuels et la musique du rendu
    "langue": (lambda sc, r: [*CARTE["anim"][0](sc, r)[:1], *CARTE["bramble"][0](sc, r)], []),
}
# écrits par chaque moteur avec l'heure : comparés sans elle ; lipsync.log = sortie brute de LongCat (heures, adresses mémoire), sa ligne « OK »
# est dans le journal comparé
HORS = {"journal.txt", "chrono.csv", "en_cours.lock", "lipsync.log"}


def md5(f: Path) -> str:
    h = hashlib.md5()
    with open(f, "rb") as lu:
        while bloc := lu.read(1 << 20):
            h.update(bloc)
    return h.hexdigest()


TEXTES = {".json", ".txt", ".csv", ".md"}


def formes(p: Path) -> list[str]:
    """Un chemin tel qu'un fichier du moteur peut l'écrire : en JSON (antislashs doublés), tel quel, vu de Linux (/mnt/d/…)."""
    w = str(p)
    return [w.replace("\\", "\\\\"), w, "/mnt/" + w[0].lower() + w[2:].replace("\\", "/")]


def empreinte(f: Path, remplacer: list[tuple[str, str]]) -> str:
    """md5, sauf : un .wav par son audio seul (l'en-tête PEAK de libsndfile porte l'heure d'écriture), un texte avec ses chemins remplacés
    (l'atelier de chaque moteur, la voix de référence du studio ou de la session)."""
    if f.suffix not in TEXTES | {".wav"}:
        return md5(f)
    b = f.read_bytes()
    if f.suffix == ".wav":
        return hashlib.md5(b[b.find(b"data"):]).hexdigest()
    t = b.decode("utf-8", errors="replace")
    for ancien, nouveau in remplacer:
        t = t.replace(ancien, nouveau)
    return hashlib.md5(t.encode("utf-8")).hexdigest()


def produits(run: Path, avant: set[str], remplacer: list[tuple[str, str]] = ()) -> dict[str, str]:
    """L'empreinte de TOUT l'atelier après passage : ce qui a été produit, et les entrées (une entrée réécrite ou abîmée se voit aussi)."""
    remplacer = [(x, "<atelier>") for x in formes(run)] + list(remplacer)
    return {f.relative_to(run).as_posix(): empreinte(f, remplacer) for f in sorted(run.rglob("*")) if f.is_file() and f.name not in HORS}


def journal(run: Path) -> list[str]:
    """Les lignes du journal sans l'heure, ni les durées chronométrées (« --- etape X : N min », « plan 2 (166s) », « 1 segment(s), 106s »),
    ni le chemin de l'atelier."""
    t = (run / "journal.txt").read_text(encoding="utf-8") if (run / "journal.txt").is_file() else ""
    for x in formes(run):
        t = t.replace(x, "<atelier>")
    return [re.sub(r"( : [0-9.]+ min| \(\d+s\)|, \d+s)$", "", re.sub(r"^\d\d:\d\d:\d\d ", "", l)) for l in t.splitlines()]


def plans_images(scenario: dict, rendu: Path) -> list[int]:
    """Trois plans faits au premier essai dans le rendu : un décor seul, un avec un ami, un avec deux amis (repris de l'ancien banc de Bramble)."""
    refaits = {int(p.name.split("_")[1]) for p in (rendu / "images" / "_refus").glob("plan_*_*.png")}
    choix = {}
    for s in scenario["scenes"]:
        if not s.get("bramble") and s.get("image") and s["image"] != "same" and s["id"] not in refaits and (rendu / "images" / f"plan_{s['id']:03d}.png").is_file():
            choix.setdefault(min(sum(n in s["image"] for n in scenario.get("cast", {})), 2), s["id"])
    return [choix[k] for k in sorted(choix)]


def preparer(etape: str, studio: Path, ids: list[int] | None = None, entrees: list[str] | None = None, nom: str = "") -> tuple[Path, Path, Path, set[str]]:
    base = SORTIE / (nom or etape)
    if base.exists():
        shutil.rmtree(base)
    runs = []
    for qui in ("bramble", "fabrique"):
        run = base / qui / SCENARIO
        for rel in ENTREES[etape] if entrees is None else entrees:
            src = studio / "PROJET" / "rendus" / RENDU / rel
            (shutil.copytree if src.is_dir() else shutil.copy2)(src, run / rel) if src.exists() else None
        run.mkdir(parents=True, exist_ok=True)
        runs.append(run)
    scen = base / f"{SCENARIO}.json"
    sc = json.loads((studio / "PROJET" / "scenarios" / f"{SCENARIO}.json").read_text(encoding="utf-8"))
    if ids is not None:
        sc["scenes"] = [s for s in sc["scenes"] if s["id"] in ids]
    scen.write_text(json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8")
    return scen, runs[0], runs[1], {f.relative_to(runs[0]).as_posix() for f in runs[0].rglob("*") if f.is_file()}


def langue_essai(scen: Path, rendu: Path, ids: list[int], runs: tuple[Path, Path]) -> Path:
    """La traduction d'essai à côté du scénario (des phrases d'essai, jamais un texte du projet) et, pour chaque moteur, son « anglais » : les
    visuels des scènes choisies et la musique, copiés du rendu de référence."""
    sc = json.loads(scen.read_text(encoding="utf-8"))
    sc.update(title="Essai d'égalité", thumbnail_text="Essai", language="fr", thumbnail_scene=ids[0])
    for s in sc["scenes"]:
        s["narration"] = f"Voici la phrase d'essai numéro {s['id']}." if (s.get("narration") or "").strip() else ""
    fr = scen.with_name(f"{scen.stem}.fr.json")
    fr.write_text(json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8")
    for run in runs:
        en = run.parent / "anglais"
        for f in [x for i in ids for x in (*rendu.glob(f"clips/s{i:03d}*"), *rendu.glob(f"images/plan_{i:03d}*"), *rendu.glob(f"calques/plan_{i:03d}"))]:
            (en / f.relative_to(rendu)).parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if f.is_dir() else shutil.copy2)(f, en / f.relative_to(rendu))
        shutil.copy2(rendu / "musique.wav", en / "musique.wav")
    return fr


def comparer(etape: str, b: Path, f: Path, avant: set[str], dossiers: list[tuple[Path, Path]] = ()) -> dict:
    """`dossiers` : des paires (dossier de Bramble Studio, son double dans la session : voix de référence, personnages) ; une paire est remplacée
    dans les textes seulement si chaque fichier de l'un a son double identique dans l'autre (sinon la différence se voit)."""
    rb, rf = [], []
    for i, (db, ds) in enumerate(dossiers):
        if all((ds / x.relative_to(db)).is_file() and md5(x) == md5(ds / x.relative_to(db)) for x in db.rglob("*") if x.is_file()):
            rb += [(x, f"<dossier {i}>") for x in formes(db)]
            rf += [(x, f"<dossier {i}>") for x in formes(ds)]
    pb, pf = produits(b, avant, rb), produits(f, avant, rf)
    # deux fichiers identiques octet pour octet sont égaux (une entrée copiée porte le chemin de Bramble : il n'est remplacé que d'un côté)
    diff = sorted(k for k in pb.keys() | pf.keys() if pb.get(k) != pf.get(k) and not (k in pb and k in pf and md5(b / k) == md5(f / k)))
    return {"egal": bool(pb.keys() - avant) and not diff and journal(b) == journal(f), "fichiers": len(pb.keys() - avant), "differents": diff[:20],
            "journal_identique": journal(b) == journal(f)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--etapes", default="montage,miniature,revue,images")
    p.add_argument("--carte", default="", help="étapes jouées pour de vrai sur la carte : voix,images,anim,bramble (de nuit)")
    p.add_argument("--relire", action="store_true", help="avec --carte : refaire seulement la comparaison des passages déjà joués")
    a = p.parse_args(argv)
    import django

    django.setup()
    from fabrique import garde
    from fabrique.moteur.f1 import etape as f_etape
    from fabrique.moteur.f1 import images as f_images
    from fabrique.moteur.f1.outils import ComfySimule as FComfy
    from fabrique.moteur.f1.outils import Lieux
    from fabrique.moteur.f1.outils import Outils as FOutils
    from fabrique.noyau import bases
    from fabrique.noyau.models import Session
    from fabrique.session import bramble as import_bramble

    studio = garde.studio_bramble()
    version = tomllib.loads((studio / "OUTILS" / "app" / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if version != BRAMBLE:
        print(f"le code de Bramble Studio est en {version}, F1 a été repris de la {BRAMBLE} : comparer d'abord les deux codes")
        return 2
    sys.path.insert(0, str(studio / "OUTILS" / "app" / "studio"))
    sys.dont_write_bytecode = True  # rien d'écrit dans le dépôt de Bramble Studio
    from moteur import copies as b_copies  # le moteur de Bramble Studio, lu dans son dépôt
    from moteur import etape as b_etape
    from moteur import images as b_images
    from moteur.outils import ComfySimule as BComfy
    from moteur.outils import Outils as BOutils

    b_copies.textes = lambda racine, donnees=None: studio / "DONNEES" / "moteur" / "production_textes.py"  # sans Django : ses textes, lus sur place
    try:
        urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=3)
        print("ComfyUI tourne déjà : les deux moteurs l'arrêtent à la fin d'une étape, rien n'est lancé")
        return 2
    except OSError:
        pass
    bases.migrer()
    nom = import_bramble.importer()["session"]
    if not Session.objects.filter(nom=nom).exists():
        print("import de Bramble Studio dans la racine de travail (une fois)…", flush=True)
        import_bramble.importer(pour_de_vrai=True, acteur="egalite")
    s = Session.objects.get(nom=nom)
    session = Path(os.environ["FABRIQUE_RACINE"]) / "sessions" / s.dossier
    lieux = Lieux(studio, session)
    cfg_b = json.loads((studio / "OUTILS" / "production" / "config.json").read_text(encoding="utf-8"))
    cfg_f = json.loads((session / "reglages" / "config.json").read_text(encoding="utf-8"))
    lu = json.loads((SORTIE / "RAPPORT.json").read_text(encoding="utf-8")) if (SORTIE / "RAPPORT.json").is_file() else {}
    rapport = {"date": datetime.now().isoformat(timespec="seconds"), "rendu": RENDU, "reglages_identiques": cfg_b == cfg_f, "etapes": lu.get("etapes", {})}
    for etape in [e for e in a.etapes.split(",") if e]:
        print(f"{etape}…", flush=True)
        scen, rb, rf, avant = preparer(etape, studio)
        if etape == "images":  # niveau consigne : ComfyUI simulé (copie d'une image du rendu), juge factice
            fausse = studio / "PROJET" / "rendus" / RENDU / "images" / "plan_002.png"
            notes = {}
            for qui, run, mod, outils, comfy, regles, univers, constantes in (
                    ("bramble", rb, b_images, BOutils(studio), BComfy(rb, fausse), studio / "OUTILS" / "production" / "regles.json",
                     studio / "PROJET" / "notes" / "univers.json", b_images.constantes_production(studio)),
                    ("fabrique", rf, f_images, FOutils(lieux), FComfy(rf, fausse), lieux.regles(), lieux.univers(), f_images.constantes_production(lieux))):
                data, scenes, plans = (b_etape if qui == "bramble" else f_etape).charger(outils, scen)
                im = mod.Images(run, cfg_b if qui == "bramble" else cfg_f, outils, json.loads(regles.read_text(encoding="utf-8")),
                                json.loads(univers.read_text(encoding="utf-8")), constantes, comfy=comfy, juge=lambda *x: {"ok": True})
                im.faire(data, scenes, plans)
                notes[qui] = json.loads(json.dumps({"consignes": comfy.consignes, "entrees": comfy.entrees}).replace(str(run).replace("\\", "\\\\"), "<run>"))
            rapport["etapes"][etape] = {"egal": notes["bramble"] == notes["fabrique"] and bool(notes["bramble"]["consignes"]),
                                        "consignes": len(notes["bramble"]["consignes"]), **comparer(etape, rb, rf, avant)}
            rapport["etapes"][etape]["egal"] &= not rapport["etapes"][etape]["differents"]
        else:
            b_etape.jouer(studio, scen, etape, cfg_b, dossier=rb, ecran=lambda *x: None, fond=lambda *x: False)
            f_etape.jouer(lieux, scen, etape, cfg_f, dossier=rf, ecran=lambda *x: None, fond=lambda *x: False)
            rapport["etapes"][etape] = comparer(etape, rb, rf, avant)
        rapport["etapes"][etape]["date"] = datetime.now().isoformat(timespec="seconds")
        print(f"  {etape} : {'ÉGAL' if rapport['etapes'][etape]['egal'] else 'DIFFÉRENT'} {rapport['etapes'][etape]}", flush=True)
    if a.carte:
        from fabrique.moteur import carte
        from fabrique.moteur.f1 import comfy as f_comfy

        pilote = f_comfy.pour(lieux)
        module = BOutils.module
        BOutils.module = lambda self, cle, nom: pilote if (cle, nom) == ("kit", "comfy") else module(self, cle, nom)  # le même pilote des deux côtés
        sans_juge = lambda c: {**c, "controle_images": False}  # noqa: E731 — le juge (Gemini, en ligne) ne départage pas deux moteurs
        from moteur import langue as b_langue

        from fabrique.moteur.f1 import langue as f_langue
        from fabrique.moteur.f1.adaptateur import langue_de

        francais = langue_de(session, "fr") if "langue" in a.carte else {"reglages": {}}
        if francais["reglages"].get("ref"):  # la session la range ailleurs que Bramble Studio : les deux moteurs ne liraient plus la même
            raise SystemExit("la voix française a une voix de référence propre : l'égalité de langue ne sait pas encore la donner à chaque moteur")
        rendu = studio / "PROJET" / "rendus" / RENDU
        scenario = json.loads((studio / "PROJET" / "scenarios" / f"{SCENARIO}.json").read_text(encoding="utf-8"))
        for etape in a.carte.split(","):
            choix, entrees = CARTE[etape]
            ids = choix(scenario, rendu)
            print(f"{etape} sur la carte, scènes {ids}…", flush=True)
            if a.relire:
                rb, rf = (SORTIE / f"carte_{etape}" / qui / SCENARIO for qui in ("bramble", "fabrique"))
                avant = {x.relative_to(rendu).as_posix() for rel in entrees for x in ((rendu / rel).rglob("*") if (rendu / rel).is_dir() else [rendu / rel]) if x.is_file()}
            else:
                scen, rb, rf, avant = preparer(etape, studio, ids, entrees, nom=f"carte_{etape}")
            if etape == "langue" and not a.relire:
                scen = langue_essai(scen, rendu, ids, (rb, rf))
            for qui, moteur, lieu, cfg, run in (("bramble", b_etape, studio, cfg_b, rb), ("fabrique", f_etape, lieux, cfg_f, rf)) if not a.relire else ():
                if raison := carte.occupee():
                    raise SystemExit(f"carte prise avant le moteur {qui} ({etape}) : {raison} — rien n'est lancé")
                if etape != "langue":
                    moteur.jouer(lieu, scen, etape, sans_juge(cfg), dossier=run, ecran=lambda *x: None, fond=lambda *x: False)
                elif qui == "bramble":  # son anglais est lu sous PROJET\rendus : ici, la copie à côté (un chemin absolu gagne dans une jointure)
                    b_langue.anglais = lambda sc, en=run.parent / "anglais": types.SimpleNamespace(stem=str(en))
                    b_langue.faire(studio, scen, sans_juge(cfg), francais, cfg["voix"]["ref_audio"], ecran=lambda *x: None, dossier=run)
                else:
                    c = lieux.config(sans_juge(cfg))  # comme l'adaptateur de l'étape « langue »
                    f_langue.faire(lieux, scen, c, francais, c["voix"]["ref_audio"], ecran=lambda *x: None, dossier=run, anglais_run=run.parent / "anglais")
            paires = [(studio / "PROJET" / d, session / "univers" / d) for d in ("voix", "personnages")] + [(rb.parent / "anglais", rf.parent / "anglais")]
            jouee = datetime.fromtimestamp(max(r.joinpath("journal.txt").stat().st_mtime for r in (rb, rf))) if a.relire else datetime.now()
            rapport["etapes"][f"carte_{etape}"] = {**comparer(etape, rb, rf, avant, paires), "scenes": ids, "date": jouee.isoformat(timespec="seconds")}
            print(f"  {etape} : {'ÉGAL' if rapport['etapes'][f'carte_{etape}']['egal'] else 'DIFFÉRENT'} {rapport['etapes'][f'carte_{etape}']}", flush=True)
    (SORTIE / "RAPPORT.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if rapport["reglages_identiques"] and all(e["egal"] for e in rapport["etapes"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
