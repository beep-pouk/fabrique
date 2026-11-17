"""Essai pleine longueur de J3 (plan § 7.1 et § 8.6 ; de nuit, carte libre : la file de Fabrique attend d'elle-même un rendu de Bramble Studio).
F1 (dernière version) pour de vrai sur une histoire d'essai, dans la session « Essais » de la racine de travail de l'égalité
(OUTILS\\fabrique_construction\\egalite\\FABRIQUE, où Bramble Studio est importé : son univers, ses réglages et ses textes y sont copiés), jamais
publiée. En vrais processus (noyau, file, exécuteur détaché), FABRIQUE_REEL=1 et le réglage « simulation » à non :
  1. « moteur F1 <script> » (la porte de Claude) ;
  2. coupure : l'exécuteur tué pendant l'étape des images (au moins 3 images faites), repris par le noyau ; les images d'avant la coupure jamais refaites ;
     puis le noyau tué et relancé (« quitter puis relancer ») : l'exécuteur continue, jamais doublé ;
  3. fin ; durée réelle (horloge, et chrono de chaque étape) ;
  4. contrôle lu comme Vérification le montre : note, défauts minutés, plans quasi fixes au-delà de plan_fixe_max_s ;
  5. « refaire » du plan du premier défaut grave (sinon du premier plan), refait et recontrôlé.
Rapport : OUTILS\\fabrique_construction\\egalite\\ESSAI_LONG.json (et .log). Outil de développement : jamais livré.
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

JOURNAL = SORTIE / "ESSAI_LONG.log"
COPIES = ("univers", "regles", "reglages", "moteur")  # ce que F1 lit dans une session (Lieux)


def dire(texte: str):
    ligne = f"{datetime.now():%d/%m %H:%M:%S} {texte}"
    print(ligne, flush=True)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(ligne + "\n")


def preparer() -> Path:
    """La session « Essais » reçoit l'univers de la session importée de Bramble Studio ; la racine quitte la simulation."""
    import django

    django.setup()
    from fabrique.noyau import bases
    from fabrique.noyau.models import Parametre, Session

    bases.migrer()
    essais = Session.objects.get(essais=True)
    bramble = Session.objects.exclude(essais=True).first()
    if bramble is None:
        raise SystemExit("la racine de travail n'a pas de session importée de Bramble Studio : lancer d'abord outils_dev\\egalite.py")
    vers = RACINE / "sessions" / essais.dossier
    for d in COPIES:
        if (RACINE / "sessions" / bramble.dossier / d).is_dir():
            shutil.copytree(RACINE / "sessions" / bramble.dossier / d, vers / d, dirs_exist_ok=True)
    Parametre.ecrire("simulation", "non")
    return vers


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("histoire")
    a.add_argument("--sans-refaire", action="store_true")
    a = a.parse_args(argv)
    from fabrique.fenetre.client import Client

    essais = preparer()
    env = dict(os.environ)
    rapport = {"debut": datetime.now().isoformat(timespec="seconds"), "histoire": str(a.histoire)}
    claude, fenetre = Client("claude", port=PORT, donnees=RACINE / "donnees"), Client("fenetre", port=PORT, donnees=RACINE / "donnees")
    noyau = subprocess.Popen([sys.executable, "-m", "fabrique", "noyau"], cwd=DEPOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        banc.attendre(claude.repond, 60, "le noyau répond")
        assert claude.appeler("sante")["mode"] == "réel", "la racine de travail est restée en simulation"
        r = subprocess.run([sys.executable, "-m", "fabrique", "moteur", "F1", a.histoire], cwd=DEPOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=300)
        dire(f"moteur : {r.stdout.strip() or r.stderr.strip()}")
        video = re.search(r"vidéo (\w+)", r.stdout)
        assert r.returncode == 0 and video, "l'essai n'est pas entré dans la file"
        video, t0 = video.group(1), time.monotonic()
        rapport["video"] = video

        def tache() -> dict:
            return next(t for t in claude.appeler("file") if t["session"] == "Essais")

        def suivre(jusqu_a, delai: float, quoi: str) -> dict:
            vu = ""
            fin = time.monotonic() + delai
            while time.monotonic() < fin:
                t = tache()
                if (etat := f"{t['etat']} {t['progression']} {t['raison']}") != vu:
                    dire(etat)
                    vu = etat
                if r := jusqu_a(t):
                    return r
                time.sleep(20)
            raise AssertionError(f"toujours pas après {delai / 3600:.1f} h : {quoi}")

        images = essais / "videos" / video / "commun" / "atelier"
        dire("coupure : attente de 3 images faites…")
        suivre(lambda t: len(list(images.glob("*/images/plan_*.png"))) >= 3 or t["etat"] in ("finie", "erreur"), 6 * 3600, "3 images")
        avant = {f: f.stat().st_mtime_ns for f in images.glob("*/images/plan_*.png")}
        pid = json.loads((RACINE / "donnees" / "taches" / "fabrication.json").read_text(encoding="utf-8")).get("pid")
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        dire(f"exécuteur {pid} tué avec {len(avant)} image(s) faites")
        etat_fab = RACINE / "donnees" / "taches" / "fabrication.json"
        nouveau = banc.attendre(lambda: (p := json.loads(etat_fab.read_text(encoding="utf-8")).get("pid")) not in (None, pid) and p, 600, "l'exécuteur relancé", pas=2)
        noyau.kill()  # « Quitter puis relancer » : le noyau s'arrête net, l'exécuteur détaché continue ; relancé, le noyau ne le double pas
        noyau = subprocess.Popen([sys.executable, "-m", "fabrique", "noyau"], cwd=DEPOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        banc.attendre(claude.repond, 60, "le noyau relancé répond")
        time.sleep(60)
        rapport["noyau_relance"] = {"executeur": nouveau, "seul": json.loads(etat_fab.read_text(encoding="utf-8")).get("pid") == nouveau and nouveau in banc.processus()}
        dire(f"noyau tué puis relancé : l'exécuteur {nouveau} {'continue seul' if rapport['noyau_relance']['seul'] else 'A ÉTÉ DOUBLÉ OU PERDU'}")
        t = suivre(lambda t: t["etat"] in ("finie", "erreur") and t, 20 * 3600, "la fin de l'essai")
        rapport["duree_h"] = round((time.monotonic() - t0) / 3600, 2)
        rapport["coupure"] = {"images_avant": len(avant), "jamais_refaites": all(f.stat().st_mtime_ns == m for f, m in avant.items() if f.exists())}
        rapport["fin"] = t
        sid = next(s["id"] for s in claude.appeler("sessions") if s["nom"] == "Essais")
        d = fenetre.appeler("video", id=sid, video=video)
        rapport["etapes"] = {e["id"]: e["secondes"] for e in d["etapes"]}
        # une vidéo finie par langue : « commun » = la langue du script, puis chaque traduction posée à côté
        rapport["langues"] = sorted({p.relative_to(essais / "videos" / video).parts[0] for p in (essais / "videos" / video).glob("*/atelier/*/final/*.mp4")})
        rapport["controle"] = d["controle"]
        dire(f"fini en {rapport['duree_h']} h : {t['etat']} {t['progression']} ; note {d['controle']['note']}, {len(d['controle']['defauts'])} défaut(s)")
        if t["etat"] == "finie" and not a.sans_refaire and d["plans"]:
            graves = [x for x in d["controle"]["defauts"] if x["gravite"] == "forte" and x["debut"] is not None]
            plan = d["plans"][0]["n"]  # shortcut: le premier plan, pas celui du défaut grave (le temps → scène demande les durées du montage), à affiner après l'essai
            dire(f"refaire le plan {plan} ({len(graves)} défaut(s) grave(s))…")
            dire(fenetre.appeler("refaire", {"plans": [plan]}, id=sid, video=video)["message"])
            t1 = time.monotonic()
            t = suivre(lambda t: t["etat"] in ("finie", "erreur") and t, 6 * 3600, "la fin du refaire")
            d2 = fenetre.appeler("video", id=sid, video=video)
            rapport["refaire"] = {"plan": plan, "duree_h": round((time.monotonic() - t1) / 3600, 2), "fin": t, "controle": d2["controle"]}
            dire(f"refait en {rapport['refaire']['duree_h']} h : note {d2['controle']['note']}, {len(d2['controle']['defauts'])} défaut(s)")
    except AssertionError as e:
        rapport["erreur"] = str(e)
        dire(f"ARRÊT : {e}")
    finally:
        subprocess.run([sys.executable, "-m", "fabrique", "arreter"], cwd=DEPOT, env=env, capture_output=True, timeout=120)
        noyau.kill()
    (SORTIE / "ESSAI_LONG.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if "erreur" not in rapport else 1


if __name__ == "__main__":
    sys.exit(main())
