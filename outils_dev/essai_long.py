"""Essai pleine longueur de J3 (plan § 7.1 et § 8.6 ; de nuit, carte libre : la file de Fabrique attend d'elle-même un rendu de Bramble Studio).
F1 (dernière version) pour de vrai sur une histoire d'essai, dans la session « Essais » de la racine de travail de l'égalité
(OUTILS\\fabrique_construction\\egalite\\FABRIQUE, où Bramble Studio est importé : son univers, ses réglages et ses textes y sont copiés), jamais
publiée. En vrais processus (noyau, file, exécuteur détaché), FABRIQUE_REEL=1 et le réglage « simulation » à non :
  1. « moteur F1 <script> » (la porte de Claude) ;
  2. coupure : l'exécuteur tué pendant l'étape des images (au moins 3 images faites), repris par le noyau ; les images d'avant la coupure jamais refaites ;
     puis le noyau tué et relancé (« quitter puis relancer ») : l'exécuteur continue, jamais doublé ;
  3. fin ; durée réelle (horloge, et chrono de chaque étape), durée de la vidéo, une vidéo finie par langue ;
  4. contrôle lu comme Vérification le montre : note, défauts minutés ; plans quasi fixes au-delà de plan_fixe_max_s mesurés sur chaque langue ;
  5. « refaire » du plan d'image qui couvre le premier défaut grave (sinon le premier défaut, sinon le premier plan d'image), refait et recontrôlé.
Rapport : OUTILS\\fabrique_construction\\egalite\\ESSAI_LONG.json (et .log), toujours écrit (erreur comprise), avec le commit du code essayé.
Un essai coupé (PC éteint) est repris au lancement suivant sur la même histoire (ESSAI_LONG_ETAT.json : sa tâche, sa coupure déjà faite) ;
arrêté par trop de coupures, il est repris comme RT le fait (« Reprendre »).
Outil de développement : jamais livré.
python outils_dev\\essai_long.py <histoire.json> [--sans-refaire]"""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEPOT = Path(__file__).resolve().parents[1]
SORTIE = DEPOT.parent / "fabrique_construction" / "egalite"
RACINE = SORTIE / "FABRIQUE"
with socket.socket() as _s:
    _s.bind(("127.0.0.1", 0))
    PORT = _s.getsockname()[1]
os.environ.update({"FABRIQUE_RACINE": str(RACINE), "FABRIQUE_REEL": "1", "FABRIQUE_PORT": str(PORT), "DJANGO_SETTINGS_MODULE": "fabrique.settings",
                   "PYTHONIOENCODING": "utf-8"})
sys.path.insert(0, str(DEPOT))
import banc  # noqa: E402
from fabrique.moteur import faux  # noqa: E402

JOURNAL = SORTIE / "ESSAI_LONG.log"
RAPPORT = SORTIE / "ESSAI_LONG.json"
ETAT = SORTIE / "ESSAI_LONG_ETAT.json"  # l'essai en cours : repris après une extinction du PC, jamais recommencé de zéro
GIT =DEPOT.parent / "git" / "cmd" / "git.exe"
COPIES = ("univers", "regles", "reglages", "moteur")  # ce que F1 lit dans une session (Lieux)


def dire(texte: str):
    ligne = f"{datetime.now():%d/%m %H:%M:%S} {texte}"
    print(ligne, flush=True)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(ligne + "\n")


def git(*args: str) -> str:
    return subprocess.run([str(GIT), *args], cwd=DEPOT, capture_output=True, text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW).stdout.strip()


def duree(video) -> float:
    r = subprocess.run([faux.programme("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], capture_output=True,
                       text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    return float(r.stdout.strip() or 0)


def lisible(f: Path) -> bool:
    """Une image entière (une image en cours d'écriture à la coupure ne compte pas : la reprise la refait, à juste titre)."""
    from PIL import Image

    try:
        with Image.open(f) as im:
            im.load()
        return True
    except Exception:  # noqa: BLE001 — tronquée, vide, en cours d'écriture
        return False


def md5(f: Path) -> str:
    import hashlib

    return hashlib.md5(f.read_bytes()).hexdigest() if f.is_file() else ""


def scenes_dans_la_video(atelier: Path) -> dict[int, tuple[float, float]]:
    """Le moment de chaque scène dans la vidéo finale : les segments du montage, dans l'ordre de sa liste."""
    t, r = 0.0, {}
    for nom, n in re.findall(r"file '(s(\d+)\.mp4)'", (atelier / "montage" / "_liste.txt").read_text(encoding="utf-8")):
        d = duree(atelier / "montage" / nom)
        r[int(n)] = (t, t + d)
        t += d
    return r


def choisir_plan(d: dict, scenes: dict[int, tuple[float, float]]) -> tuple[int, dict | None]:
    """Le plan d'image qui couvre le premier défaut grave, sinon le premier défaut, sinon le premier plan d'image (une scène de Bramble, refaite avec
    la même graine, rendrait la même chose)."""
    plans = [p for p in d["plans"] if p["image"]]
    for x in sorted((x for x in d["controle"]["defauts"] if x["debut"] is not None), key=lambda x: (x["gravite"] != "forte", x["debut"])):
        scene = next((s for s, (a, b) in scenes.items() if a <= x["debut"] < b), None)
        if plan := next((p for p in plans if scene in p["scenes"]), None):
            return plan["n"], x
    return plans[0]["n"], None


def dans_le_plan(defauts: list[dict], plan: dict, scenes: dict[int, tuple[float, float]]) -> int:
    a, b = min(scenes[s][0] for s in plan["scenes"]), max(scenes[s][1] for s in plan["scenes"])
    return sum(x["debut"] is not None and a <= x["debut"] < b for x in defauts)


def preparer() -> Path:
    """La session « Essais » reçoit l'univers de la session importée de Bramble Studio (fichiers et langues) ; la racine quitte la simulation."""
    import django

    django.setup()
    from fabrique.noyau import bases, routeur
    from fabrique.noyau.models import Parametre, Session
    from fabrique.session.models import Langue

    bases.migrer()
    essais = Session.objects.get(essais=True)
    bramble = Session.objects.exclude(essais=True).first()
    if bramble is None:
        raise SystemExit("la racine de travail n'a pas de session importée de Bramble Studio : lancer d'abord outils_dev\\egalite.py")
    vers = RACINE / "sessions" / essais.dossier
    for d in COPIES:
        if (RACINE / "sessions" / bramble.dossier / d).is_dir():
            shutil.copytree(RACINE / "sessions" / bramble.dossier / d, vers / d, dirs_exist_ok=True)
    with routeur.session(bramble):  # les langues et leurs voix : l'étape « langue » les lit dans la base de la session de la vidéo
        langues = [{f.name: getattr(l, f.name) for f in Langue._meta.fields if f.name != "id"} for l in Langue.objects.all()]
    with routeur.session(essais):
        for l in langues:
            Langue.objects.update_or_create(code=l["code"], defaults=l)
    Parametre.ecrire("simulation", "non")
    return vers


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("histoire")
    a.add_argument("--sans-refaire", action="store_true")
    a = a.parse_args(argv)
    from fabrique.fenetre.client import Client
    from fabrique.moteur import recettes
    from fabrique.moteur.f1 import mouvement

    RAPPORT.unlink(missing_ok=True)  # jamais le rapport d'un essai d'avant
    rapport = {"debut": datetime.now().isoformat(timespec="seconds"), "histoire": str(a.histoire), "commit": git("rev-parse", "HEAD"),
               "code_modifie": bool(git("status", "--porcelain", "fabrique"))}
    essais = preparer()
    env = dict(os.environ)
    claude, fenetre = Client("claude", port=PORT, donnees=RACINE / "donnees"), Client("fenetre", port=PORT, donnees=RACINE / "donnees")
    noyau = subprocess.Popen([sys.executable, "-m", "fabrique", "noyau"], cwd=DEPOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        banc.attendre(claude.repond, 60, "le noyau répond")
        assert claude.appeler("sante")["mode"] == "réel", "la racine de travail est restée en simulation"
        file = claude.appeler("file")
        lu = json.loads(ETAT.read_text(encoding="utf-8")) if ETAT.is_file() else {}
        suivie = next((t for t in file if lu.get("histoire") == str(a.histoire) and t["id"] == lu.get("tache") and t["etat"] != "annulee"), None)
        if suivie and suivie["etat"] == "erreur" and suivie["raison"].startswith("l'exécuteur s'est arrêté"):  # des extinctions du PC : RT clique « Reprendre »
            dire(f"tâche {suivie['id']} arrêtée par les coupures : {fenetre.appeler('agir_file', id=suivie['id'], action='reprendre')['message']}")
        for t in file:  # une autre tâche restée d'un essai interrompu : annulée, jamais suivie à la place de celle-ci
            if t["session"] == "Essais" and t["etat"] in ("attente", "en_cours", "pause") and t is not suivie:
                dire(f"tâche {t['id']} d'un essai d'avant : {fenetre.appeler('agir_file', id=t['id'], action='annuler')['message']}")
        if suivie:
            etat = lu
            dire(f"reprise de l'essai interrompu : tâche {suivie['id']} ({suivie['etat']} {suivie['progression']}), ses morceaux finis jamais refaits")
        else:
            r = subprocess.run([sys.executable, "-m", "fabrique", "moteur", "F1", a.histoire], cwd=DEPOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=300)
            dire(f"moteur : {r.stdout.strip() or r.stderr.strip()}")
            m = re.search(r"tâche (\d+), vidéo (\w+)", r.stdout)
            assert r.returncode == 0 and m, "l'essai n'est pas entré dans la file"
            etat = {"histoire": str(a.histoire), "tache": int(m.group(1)), "video": m.group(2)}
        etat.setdefault("lancements", []).append({"date": rapport["debut"], "commit": rapport["commit"]})
        ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
        tid, video, t0 = etat["tache"], etat["video"], time.monotonic()
        rapport |= {"video": video, "lancements": etat["lancements"]}

        def suivre(jusqu_a, delai: float, quoi: str) -> dict:
            vu = ""
            fin = time.monotonic() + delai
            while time.monotonic() < fin:
                t = next(t for t in claude.appeler("file") if t["id"] == tid)
                if (etat := f"{t['etat']} {t['progression']} {t['raison']}") != vu:
                    dire(etat)
                    vu = etat
                if r := jusqu_a(t):
                    return r
                time.sleep(20)
            raise AssertionError(f"toujours pas après {delai / 3600:.1f} h : {quoi}")

        base = essais / "videos" / video
        images = base / "commun" / "atelier"
        etat_fab = RACINE / "donnees" / "taches" / "fabrication.json"
        executeur = lambda: json.loads(etat_fab.read_text(encoding="utf-8")).get("pid")  # noqa: E731
        if "coupure" not in etat:  # une fois par essai, même repris
            dire("coupure : attente de 3 images faites…")
            # l'exécuteur vivant : après une extinction, fabrication.json garde le pid mort de la veille (jamais tuer un pid réutilisé)
            suivre(lambda t: (len([f for f in images.glob("*/images/plan_*.png") if lisible(f)]) >= 3 and executeur() in banc.processus())
                   or t["etat"] in ("finie", "erreur"), 6 * 3600, "3 images")
            pid = executeur()
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
            avant = {f: f.stat().st_mtime_ns for f in images.glob("*/images/plan_*.png") if lisible(f)}  # relevé après l'arrêt : plus rien ne s'écrit
            dire(f"exécuteur {pid} tué avec {len(avant)} image(s) faites")
            nouveau = banc.attendre(lambda: (p := executeur()) not in (None, pid) and p, 600, "l'exécuteur relancé", pas=2)
            noyau.kill()  # « Quitter puis relancer » : le noyau s'arrête net, l'exécuteur détaché continue ; relancé, le noyau ne le double pas
            noyau = subprocess.Popen([sys.executable, "-m", "fabrique", "noyau"], cwd=DEPOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            banc.attendre(claude.repond, 60, "le noyau relancé répond")
            time.sleep(60)
            seul = executeur() == nouveau and nouveau in banc.processus()
            dire(f"noyau tué puis relancé : l'exécuteur {nouveau} {'continue seul' if seul else 'A ÉTÉ DOUBLÉ OU PERDU'}")
            etat["coupure"] = {"avant": {str(f): m for f, m in avant.items()}, "noyau_relance": {"executeur": nouveau, "seul": seul}}
            ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
        avant = {Path(f): m for f, m in etat["coupure"]["avant"].items()}
        rapport["noyau_relance"] = etat["coupure"]["noyau_relance"]
        t = suivre(lambda t: t["etat"] in ("finie", "erreur") and t, 20 * 3600, "la fin de l'essai")
        rapport["duree_h"] = round((time.monotonic() - t0) / 3600, 2)  # horloge de ce lancement (attente de la carte et coupure comprises) ; calcul_h : l'essai entier
        rapport["coupure"] = {"images_avant": len(avant), "jamais_refaites": all(f.exists() and f.stat().st_mtime_ns == m for f, m in avant.items())}
        rapport["fin"] = t
        sid = next(s["id"] for s in claude.appeler("sessions") if s["nom"] == "Essais")
        d = fenetre.appeler("video", id=sid, video=video)
        rapport["recette"] = d["recette"]
        rapport["etapes"] = {e["id"]: e["secondes"] for e in d["etapes"]}
        rapport["calcul_h"] = round(sum(rapport["etapes"].values()) / 3600, 2)  # la somme des chronos des étapes
        finales = {f.relative_to(base).parts[0]: f for f in base.glob("*/atelier/*/final/*.mp4")}  # « commun » = la langue du script, puis chaque traduction
        rapport["langues"] = sorted(finales)
        rapport["duree_video_s"] = round(duree(d["controle"]["video"]), 1) if d["controle"]["video"] else 0
        max_s = recettes.lire("F1")["reglages"].get("plan_fixe_max_s")
        rapport["plans_fixes"] = {l: mouvement.defauts(faux.programme("ffmpeg"), f, duree(f), max_s) for l, f in finales.items()} if max_s else None
        rapport["controle"] = d["controle"]
        dire(f"fini en {rapport['duree_h']} h : {t['etat']} {t['progression']} ; note {d['controle']['note']}, {len(d['controle']['defauts'])} défaut(s)")
        if t["etat"] == "finie" and not a.sans_refaire:
            atelier = next(p for p in images.iterdir() if p.is_dir())
            scenes = scenes_dans_la_video(atelier)
            plan, defaut = choisir_plan(d, scenes)
            le_plan = next(p for p in d["plans"] if p["n"] == plan)
            image = atelier / "images" / f"plan_{plan:03d}.png"
            avant_md5 = md5(image)
            dire(f"refaire le plan {plan} ({defaut['texte'] if defaut else 'aucun défaut minuté sur un plan d’image'})…")
            msg = fenetre.appeler("refaire", {"plans": [plan]}, id=sid, video=video)["message"]
            dire(msg)
            tid, t1 = int(re.search(r"tâche (\d+)", msg).group(1)), time.monotonic()
            t = suivre(lambda t: t["etat"] in ("finie", "erreur") and t, 6 * 3600, "la fin du refaire")
            d2 = fenetre.appeler("video", id=sid, video=video)
            rapport["refaire"] = {"plan": plan, "defaut": defaut, "duree_h": round((time.monotonic() - t1) / 3600, 2), "fin": t, "controle": d2["controle"],
                                  "image_changee": bool(avant_md5) and md5(image) not in ("", avant_md5),
                                  "defauts_du_plan": [dans_le_plan(d["controle"]["defauts"], le_plan, scenes), dans_le_plan(d2["controle"]["defauts"], le_plan, scenes)]}
            dire(f"refait en {rapport['refaire']['duree_h']} h : note {d2['controle']['note']}, {len(d2['controle']['defauts'])} défaut(s) ; défauts du plan "
                 f"{rapport['refaire']['defauts_du_plan'][0]} → {rapport['refaire']['defauts_du_plan'][1]}")
        ETAT.unlink()  # l'essai est allé au bout : le prochain lancement en commence un nouveau
    except Exception as e:  # noqa: BLE001 — toute erreur va dans le rapport : jamais celui d'un essai d'avant, jamais rien
        rapport["erreur"] = f"{type(e).__name__} : {e}"
        dire(f"ARRÊT : {rapport['erreur']}")
    finally:
        rapport["fin_essai"] = datetime.now().isoformat(timespec="seconds")
        RAPPORT.write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
        subprocess.run([sys.executable, "-m", "fabrique", "arreter"], cwd=DEPOT, env=env, capture_output=True, timeout=120)
        noyau.kill()
    return 0 if "erreur" not in rapport else 1


if __name__ == "__main__":
    sys.exit(main())
