"""Recette d'un jalon : python outils_dev\\verifier.py --jalon J1 → docs\\VERIF_J1_PC.md (jamais suivi par git : il cite le PC), relu par la
supervision. Code de retour 0 si aucun point rouge.
J1 (plan technique § 7.1) : la construction vérifiée (suite verte, programme assemblé, installateur signé) et la recette d'installation dans le
bac à sable (installée à côté de Bramble Studio ; fenêtre ouverte, fermée, relancée ; sauvegarde puis restauration ; mise à jour jouée),
pendant que l'empreinte du dossier « Bramble Studio » et de « DONNEES » est prise avant et après : identique. Bramble Studio qui tourne réécrit
lui-même son état, sa base et ses journaux : ces fichiers-là sont montrés à part.
J2 : le moteur à recettes en vrais processus (moteur()), puis tout J1 (la recette d'installation joue aussi un essai de recette).
J3 : les preuves des longs passages de nuit, carte libre (egalite.py : égalité étape par étape ; essai_long.py : essai pleine longueur), lues ;
les tests de F1 et des écrans ; puis tout J2.
Outil de développement : jamais livré."""
import argparse
import fnmatch
import json
import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

import banc

DEPOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEPOT))
from fabrique import garde  # noqa: E402

SORTIE = DEPOT.parent / "fabrique_construction"
VIVANTS = ("etat.json", "etat.txt", "studio.db", "studio.db-wal", "studio.db-shm", "journaux/*", "arriere_plan/*", "webview/*")  # ce que Bramble Studio réécrit seul


def bramble_tourne(studio: Path) -> bool:
    return any(Path(c).name == "Bramble Studio.exe" for c in banc.sous(studio / "Bramble Studio").values())


def bramble_avant(dire) -> tuple:
    studio = garde.studio_bramble() or DEPOT.parents[1]
    lieux = {"Bramble Studio": studio / "Bramble Studio", "DONNEES": studio / "DONNEES"}
    dire(f"empreinte avant : {', '.join(str(d) for d in lieux.values())}")
    return studio, lieux, {n: banc.empreinte(d) for n, d in lieux.items()}, bramble_tourne(studio)


def bramble_points(avant: tuple) -> list[tuple[bool, str]]:
    """Le dossier « Bramble Studio » et « DONNEES » identiques avant et après (hors ce que Bramble Studio, s'il tourne, réécrit lui-même)."""
    studio, lieux, avant, tourne = avant
    apres, tourne = {n: banc.empreinte(d) for n, d in lieux.items()}, tourne and bramble_tourne(studio)
    d = banc.differences(avant["Bramble Studio"], apres["Bramble Studio"])
    points = [(not d, "dossier « Bramble Studio » identique avant et après" + ("" if not d else " : " + ", ".join(d[:10])))]
    d = banc.differences(avant["DONNEES"], apres["DONNEES"])
    siens = [x for x in d if tourne and any(fnmatch.fnmatch(x[2:], m) for m in VIVANTS)]
    autres = [x for x in d if x not in siens]
    points.append((not autres, "dossier « DONNEES » identique avant et après" + (f" ({len(siens)} fichier(s) réécrits par Bramble Studio lui-même, qui tourne : "
                                                                                    f"{', '.join(siens)})" if siens else "") + ("" if not autres else " — AUTRES : " + ", ".join(autres[:10]))))
    return points


def construction(dire, publier: bool) -> list[tuple[bool, str]]:
    import construire

    journal = SORTIE / f"construire_{construire.version()}.log"
    journal.parent.mkdir(parents=True, exist_ok=True)
    dire(f"construction et recette d'installation (journal : {journal})…")
    with open(journal, "w", encoding="utf-8") as sortie:
        r = subprocess.run([sys.executable, str(DEPOT / "outils_dev" / "construire.py"), *(["--publier"] if publier else [])], cwd=DEPOT, stdout=sortie, stderr=subprocess.STDOUT,
                           env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    points = [(r.returncode == 0, f"construction vérifiée (suite de tests verte, programme assemblé, installateur signé, recette d'installation"
                                  f"{', installateur publié' if publier else ''}) — {journal.name}")]
    try:
        preuve = json.loads((SORTIE / "recette_installation.json").read_text(encoding="utf-8"))
        bonne = r.returncode == 0 and preuve["arbres"] == construire.arbres() and preuve["version"] == construire.version()
        points += [(bonne, f"recette d'installation ({preuve['date']}) : {p}") for p in preuve["points"]]
    except (OSError, ValueError, KeyError):
        points.append((False, "recette d'installation : pas de preuve écrite"))
    captures = sorted(f.name for f in (DEPOT / "fabrique" / "tests" / "captures").glob("*.png"))
    points.append((len(captures) >= 5, f"captures de référence de la fenêtre comparées par la suite (100 %, 125 %, 150 %, 2560 × 1440) : {', '.join(captures)}"))
    return points


def j1(dire, publier: bool = False) -> list[tuple[bool, str]]:
    avant = bramble_avant(dire)
    return construction(dire, publier) + bramble_points(avant)


SCRIPT = {"titre": "Essai de la recette J2", "scenes": [{"id": f"s{i}", "plans": [{"id": f"p{j}", "texte": f"Texte factice {i}.{j}."} for j in (1, 2)]} for i in (1, 2)]}
MORCEAUX = 38  # recette d'essai sur 2 scènes de 2 plans, en et fr


def moteur(dire) -> list[tuple[bool, str]]:
    """En vrais processus, sur un dossier temporaire : le noyau et sa file, « moteur » (Claude), l'exécuteur détaché. L'état de Bramble Studio
    est simulé à côté de la racine (<tmp>\\DONNEES\\etat.json, lu par la garde de la carte comme celui du vrai studio)."""
    import os
    import socket
    import tempfile
    import time

    from fabrique.fenetre.client import Client

    tmp = Path(tempfile.mkdtemp(prefix="fabrique_j2_"))
    racine, points = tmp / "FABRIQUE", []
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "FABRIQUE_RACINE": str(racine), "FABRIQUE_PORT": str(port), "PYTHONIOENCODING": "utf-8"}
    etat, script = tmp / "DONNEES" / "etat.json", tmp / "script.json"
    etat.parent.mkdir(parents=True)
    script.write_text(json.dumps(SCRIPT), encoding="utf-8")

    def bramble(episode: bool):
        etat.write_text(json.dumps({"heure": datetime.now().isoformat(timespec="minutes"), "mode": "réel", "tache": {"nom": "EPISODE_SIMULE.bat", "episode": episode},
                                    "episode": {"code": "simulé"} if episode else None}), encoding="utf-8")

    def lancer(*args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "fabrique", *map(str, args)], cwd=DEPOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)

    client = Client("claude", port=port, donnees=racine / "donnees")
    videos = racine / "sessions" / "essais" / "videos"

    def tache() -> dict:
        return client.appeler("file")[0]  # la plus récente des actives d'abord : une seule à la fois ici

    def fin(quoi: str) -> dict:
        return banc.attendre(lambda: (t := tache())["etat"] in ("finie", "erreur") and t, 180, quoi, pas=0.2)

    bramble(True)
    noyau = subprocess.Popen([sys.executable, "-m", "fabrique", "noyau"], cwd=DEPOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        banc.attendre(client.repond, 60, "le noyau répond")
        dire("refus quand Bramble Studio fabrique…")
        r = lancer("moteur", "essai", script)
        time.sleep(8)  # quatre tours du noyau
        t = tache()
        points.append((r.returncode == 0 and "Bramble Studio fabrique" in r.stdout and t["etat"] == "attente" and t["raison"].startswith("Bramble Studio fabrique")
                       and t["progression"] == f"0/{MORCEAUX}", f"refus quand Bramble Studio fabrique (état simulé) : « moteur » le dit, la tâche attend 8 s sans rien lancer "
                                                               f"(« {t['raison']} », {t['progression']} morceaux)"))
        dire("Bramble Studio libre : la recette d'essai de bout en bout…")
        bramble(False)
        t0 = time.monotonic()
        t = fin("la recette d'essai est finie")
        d = next(videos.iterdir())
        duree = [json.loads((d / langue / "revue" / "video" / "rapport.json").read_text(encoding="utf-8"))["duree_s"] for langue in ("en", "fr")]
        points.append((t["etat"] == "finie" and t["progression"] == f"{MORCEAUX}/{MORCEAUX}" and all(abs(x - 4) < 0.2 for x in duree) and not list(d.rglob("*.tmp")),
                       f"en simulation, la recette d'essai de bout en bout dès la carte libre ({time.monotonic() - t0:.0f} s) : {t['progression']} morceaux (9 étapes, faux outils), "
                       f"une vidéo par langue contrôlée (en {duree[0]:.1f} s, fr {duree[1]:.1f} s), aucun .tmp{'' if t['etat'] == 'finie' else ' — ' + t['raison']}"))
        dire("exécuteur tué en plein milieu…")
        assert lancer("moteur", "essai", script).returncode == 0
        n = banc.attendre(lambda: (k := int(tache()["progression"].split("/")[0])) >= 6 and k, 60, "six morceaux finis", pas=0.05)
        d2 = next(v for v in videos.iterdir() if v != d)
        faits = {f: f.stat().st_mtime_ns for f in d2.rglob("resultat.json")}
        pid = json.loads((racine / "donnees" / "taches" / "fabrication.json").read_text(encoding="utf-8"))["pid"]
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)  # son code dit aussi les enfants déjà finis (ffmpeg) : on regarde le processus
        tue = banc.attendre(lambda: pid not in banc.processus(), 10, "l'exécuteur est tué", pas=0.05)
        coupe = len(list(d2.rglob("resultat.json")))
        t = fin("la vidéo reprise par le noyau est finie")
        intacts = {f: f.stat().st_mtime_ns for f in faits} == faits
        with closing(sqlite3.connect(f"file:{racine / 'donnees' / 'noyau.sqlite3'}?mode=ro", uri=True)) as base:
            reprises = [json.loads(d) for (d,) in base.execute("SELECT detail FROM noyau_journal WHERE acteur = 'noyau' AND action = 'file'")]
        repris = any(x.get("quoi") == "reprise" and x.get("tache") == t["id"] for x in reprises)
        points.append((tue and coupe < MORCEAUX and repris and t["etat"] == "finie" and intacts and len(list(d2.rglob("resultat.json"))) == MORCEAUX
                       and not list(d2.rglob("*.tmp")),
                       f"exécuteur tué en plein milieu (taskkill {'réussi' if tue else 'RATÉ'}, {coupe}/{MORCEAUX} morceaux sur le disque) : le noyau l'a relancé seul "
                       f"({'« reprise » au journal' if repris else 'AUCUNE reprise au journal'}), reprise au premier morceau non fini, les {len(faits)} morceaux déjà "
                       f"faits {'intacts' if intacts else 'REFAITS'}, {t['progression']}, aucun .tmp"))
        dire("pause d'un exécuteur vivant, puis reprise…")
        fenetre = Client("fenetre", port=port, donnees=racine / "donnees")
        assert lancer("moteur", "essai", script).returncode == 0
        banc.attendre(lambda: int(tache()["progression"].split("/")[0]) >= 6, 60, "six morceaux finis", pas=0.05)
        pid = json.loads((racine / "donnees" / "taches" / "fabrication.json").read_text(encoding="utf-8"))["pid"]
        fenetre.appeler("agir_file", id=tache()["id"], action="pause")
        arrete = banc.attendre(lambda: pid not in banc.processus(), 15, "l'exécuteur est arrêté")
        avant = tache()
        time.sleep(6)  # trois tours du noyau : rien ne repart
        apres = tache()
        fenetre.appeler("agir_file", id=apres["id"], action="reprendre")
        t = fin("la vidéo reprise après la pause est finie")
        points.append((arrete and avant["etat"] == apres["etat"] == "pause" and avant["progression"] == apres["progression"] and t["etat"] == "finie"
                       and t["progression"] == f"{MORCEAUX}/{MORCEAUX}",
                       f"pause par la fenêtre pendant la fabrication : exécuteur arrêté, rien ne repart en 6 s ({apres['progression']}), « reprendre » : {t['progression']}"))
        r = lancer("commande", "file")
        points.append((r.returncode == 0 and [x["etat"] for x in json.loads(r.stdout)] == ["finie"] * 3, "Claude lit la file (« commande file ») : les trois essais finis"))
    except AssertionError as e:
        points.append((False, f"moteur en vrais processus : {e}"))
    finally:
        lancer("arreter")
        noyau.kill()
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "fabrique/tests/test_moteur.py"], cwd=DEPOT, capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    points.append((r.returncode == 0, "tests du moteur : l'outil par défaut changé par une donnée (une fiche ajoutée ; réglage du noyau, de la session, du format, du "
                                      "plan) sans que le code change (empreinte identique, aucun outil nommé dans le code), un vrai outil jamais pris en simulation ; refus "
                                      "quand Bramble Studio fabrique, état figé ignoré, état illisible = attente, carte prise par un autre programme ; trois échecs puis "
                                      "alerte ; plantage en boucle arrêté après trois relances ; pause pendant un tour ; exécuteur unique ; outil payant (plafond à 0 €, "
                                      f"plafond vérifié avant chaque appel, une nouvelle tentative, repli) — {r.stdout.strip().splitlines()[-1]}"))
    shutil.rmtree(tmp, ignore_errors=True)
    return points


def j2(dire, publier: bool = False) -> list[tuple[bool, str]]:
    """J2 (plan § 7.1) : le moteur en vrais processus (moteur()), les tests qui le prouvent, puis la construction et la recette d'installation de
    J1 (avec un essai de recette par le programme installé), Bramble Studio intact du début à la fin."""
    avant = bramble_avant(dire)
    return moteur(dire) + construction(dire, publier) + bramble_points(avant)


EGALES = ["montage", "miniature", "revue", "images", "carte_voix", "carte_images", "carte_anim", "carte_bramble"]  # toutes les étapes de F1 v1 qui produisent


def preuves_j3() -> list[tuple[bool, str]]:
    """Les rapports des passages de nuit (outils_dev/egalite.py et essai_long.py), écrits dans OUTILS/fabrique_construction/egalite."""
    points = []
    try:
        r = json.loads((SORTIE / "egalite" / "RAPPORT.json").read_text(encoding="utf-8"))
        e = r["etapes"]
        manque = [x for x in EGALES if x not in e]
        points.append((r["reglages_identiques"] and not manque and all(e[x]["egal"] for x in EGALES),
                       f"égalité de F1 v1 avec le moteur de Bramble Studio, étape par étape ({r['date']}, rendu {r['rendu']}) : réglages "
                       f"{'identiques' if r['reglages_identiques'] else 'DIFFÉRENTS'} ; " + " ; ".join(
                           f"{x} {'égal' if e[x]['egal'] else 'DIFFÉRENT ' + str(e[x].get('differents'))} ({e[x].get('fichiers', 0)} fichiers)" for x in EGALES if x in e)
                       + (f" ; MANQUE : {', '.join(manque)}" if manque else "")))
    except (OSError, ValueError, KeyError) as x:
        points.append((False, f"égalité étape par étape : pas de rapport lisible ({x})"))
    try:
        r = json.loads((SORTIE / "egalite" / "ESSAI_LONG.json").read_text(encoding="utf-8"))
        c, f = r["controle"], r["fin"]
        fixes = [d for d in c["defauts"] if "plan quasi fixe" in d["texte"]]
        points += [
            (f["etat"] == "finie" and "erreur" not in r, f"essai pleine longueur fabriqué en vrai ({r['debut']}, F1 dernière version, session Essais, jamais publié) : "
                                                         f"{f['etat']}, {f['progression']} morceaux"),
            (r["coupure"]["images_avant"] >= 3 and r["coupure"]["jamais_refaites"] and r["noyau_relance"]["seul"],
             f"repris après une coupure : exécuteur tué avec {r['coupure']['images_avant']} images faites, "
             f"{'jamais refaites' if r['coupure']['jamais_refaites'] else 'REFAITES'} ; noyau tué puis relancé, l'exécuteur "
             f"{'continue seul' if r['noyau_relance']['seul'] else 'DOUBLÉ OU PERDU'}"),
            (len(r.get("langues", [])) >= 2, f"une vidéo finie par langue : {', '.join(r.get('langues', [])) or 'aucune'} (« commun » = langue du script)"),
            (bool(r.get("duree_h")), f"durée réelle d'un épisode mesurée : {r.get('duree_h')} h (étapes : "
                                     + ", ".join(f"{k} {v / 60:.0f} min" for k, v in r.get("etapes", {}).items()) + ")"),
            (c["mesure"] and c["note"] is not None, f"analysé : note de Qwen {c['note']}/10, {len(c['defauts'])} défaut(s) minuté(s)"),
            (not fixes, f"F1 v2 : aucun plan quasi fixe au-delà de plan_fixe_max_s" + (f" — {len(fixes)} trouvé(s) : {fixes[0]['texte']}" if fixes else "")),
            ((rf := r.get("refaire") or {}).get("fin", {}).get("etat") == "finie" and rf["controle"]["mesure"],
             f"corrigé par un « refaire » (plan {rf.get('plan')}) : {rf.get('fin', {}).get('etat', 'pas fait')} en {rf.get('duree_h')} h, recontrôlé "
             f"(note {rf.get('controle', {}).get('note')})"),
        ]
    except (OSError, ValueError, KeyError, TypeError) as x:
        points.append((False, f"essai pleine longueur : pas de rapport complet ({x!r})"))
    return points


def j3(dire, publier: bool = False) -> list[tuple[bool, str]]:
    """J3 (plan § 7.1) : preuves de nuit lues, tests de F1 et des écrans, puis tout J2 (moteur en vrais processus, construction, installation)."""
    avant = bramble_avant(dire)
    points = preuves_j3()
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "fabrique/tests/test_f1.py", "fabrique/tests/test_fenetre.py", "fabrique/tests/test_session_api.py",
                        "fabrique/tests/test_import.py", "fabrique/tests/test_depot.py"], cwd=DEPOT, capture_output=True, text=True, encoding="utf-8",
                       env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    points.append((r.returncode == 0, "tests de F1 et des écrans : code de F1 = moteur de Bramble à quelques lignes comptées près, F1 v2 sans carte, analyse, "
                                      "« je coche, Fabrique refait », import de Bramble, écrans (Accueil, Sessions, Script, Vidéo, Vérification et son lecteur), "
                                      f"dépôt des discussions — {r.stdout.strip().splitlines()[-1]}"))
    return points + moteur(dire) + construction(dire, publier) + bramble_points(avant)


JALONS = {"J1": j1, "J2": j2, "J3": j3}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Recette d'un jalon de Fabrique (outil de développement)")
    p.add_argument("--jalon", required=True, choices=list(JALONS))
    p.add_argument("--publier", action="store_true", help=r"la construction pose aussi l'installateur dans <studio>\FABRIQUE\versions")
    a = p.parse_args(argv)
    debut = datetime.now()
    points = JALONS[a.jalon](lambda t: print(f"[verifier] {t}", flush=True), a.publier)
    rouges = sum(not ok for ok, _ in points)
    texte = [f"# Recette {a.jalon} de Fabrique — {debut:%d/%m/%Y %H:%M} ({(datetime.now() - debut).seconds // 60} min)", "",
             f"**{'Tout est vert' if not rouges else f'{rouges} point(s) rouge(s)'}** ({len(points)} points).", "",
             *(f"- {'✅' if ok else '❌'} {t}" for ok, t in points), ""]
    rapport = DEPOT / "docs" / f"VERIF_{a.jalon}_PC.md"
    rapport.write_text("\n".join(texte), encoding="utf-8")
    print("\n".join(texte))
    print(f"rapport : {rapport}")
    return 1 if rouges else 0


if __name__ == "__main__":
    sys.exit(main())
