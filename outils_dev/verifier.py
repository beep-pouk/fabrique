"""Recette d'un jalon : python outils_dev\\verifier.py --jalon J1 → docs\\VERIF_J1_PC.md (jamais suivi par git : il cite le PC), relu par la
supervision. Code de retour 0 si aucun point rouge.
J1 (plan technique § 7.1) : la construction vérifiée (suite verte, programme assemblé, installateur signé) et la recette d'installation dans le
bac à sable (installée à côté de Bramble Studio ; fenêtre ouverte, fermée, relancée ; sauvegarde puis restauration ; mise à jour jouée),
pendant que l'empreinte du dossier « Bramble Studio » et de « DONNEES » est prise avant et après : identique. Bramble Studio qui tourne réécrit
lui-même son état, sa base et ses journaux : ces fichiers-là sont montrés à part.
J2 : le moteur à recettes en vrais processus (moteur()), puis tout J1 (la recette d'installation joue aussi un essai de recette).
J3 : les preuves des longs passages de nuit, carte libre (egalite.py : égalité étape par étape ; essai_long.py : essai pleine longueur), lues ;
les tests de F1 et des écrans ; puis tout J2.
J4 : la publication en vrais processus (faux YouTube, page iPhone, paquets contre les fiches des réseaux, relevé du jour), la construction et
l'installation, puis les gestes de RT (§ 7.3) lus dans l'installation réelle.
J5 : une session créée de zéro en vrais processus et en simulation, comme la fenêtre le fait (nouvelle session pas à pas, univers, règles,
vidéo pilote fabriquée), exportée puis réimportée à l'identique (contenu des tables et empreintes des fichiers) ; les écrans du cahier sauf
Outils, Banc, Statistiques et Assistant (parcours et captures de la suite) ; la construction et l'installation.
J6 : un outil local candidat installé, passé au banc à l'aveugle contre l'outil en place, adopté : rien d'autre n'a bougé (code, tables) et la
vidéo suivante le prend ; un outil en ligne (faux service payant) refusé à 0 €, joué sous plafond, refusé au-delà ; la veille versée par
Claude ; l'outil en ligne réel si RT a donné sa clé ; la construction et l'installation.
J7 : F2 (compilation), F3 tirée d'une vidéo longue et F3 seule, en vrais processus et en simulation, contrôlées sans défaut bloquant ; les
mêmes en vrai, lus dans la racine des essais réels ; la construction et l'installation.
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
                                      f"plafond vérifié avant chaque appel, une nouvelle tentative, repli) — {dernier(r)}"))
    shutil.rmtree(tmp, ignore_errors=True)
    return points


def dernier(r) -> str:
    """La dernière ligne de pytest (son bilan) et les tests en échec, ou la fin de son erreur s'il n'a rien écrit."""
    lignes = r.stdout.strip().splitlines()
    return (lignes or [r.stderr.strip()[-300:] or f"code {r.returncode}"])[-1] + "".join(f" ; {l}" for l in lignes if l.startswith("FAILED"))[:600]


def j2(dire, publier: bool = False) -> list[tuple[bool, str]]:
    """J2 (plan § 7.1) : le moteur en vrais processus (moteur()), les tests qui le prouvent, puis la construction et la recette d'installation de
    J1 (avec un essai de recette par le programme installé), Bramble Studio intact du début à la fin."""
    avant = bramble_avant(dire)
    return moteur(dire) + construction(dire, publier) + bramble_points(avant)


EGALES = ["montage", "miniature", "revue", "images", "carte_voix", "carte_images", "carte_anim", "carte_bramble", "carte_musique",
          "carte_langue"]  # toutes les étapes de F1 v1 qui produisent, la version de langue comprise
GIT = DEPOT.parent / "git" / "cmd" / "git.exe"
DUREE_MIN_S = 900  # « pleine longueur » : 15 min au moins (plan § 8.6)


def moteur_change_depuis(commit: str) -> str:
    """Les fichiers du moteur changés depuis le commit essayé (vide : la preuve vaut pour le code d'aujourd'hui)."""
    r = subprocess.run([str(GIT), "diff", "--name-only", commit, "HEAD", "--", "fabrique/moteur"], cwd=DEPOT, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip().replace("\n", ", ") if r.returncode == 0 else f"commit {commit!r} illisible"


def preuves_j3() -> list[tuple[bool, str]]:
    """Les rapports des passages de nuit (outils_dev/egalite.py et essai_long.py), écrits dans OUTILS/fabrique_construction/egalite."""
    points = []
    try:
        r = json.loads((SORTIE / "egalite" / "RAPPORT.json").read_text(encoding="utf-8"))
        e = r["etapes"]
        manque = [x for x in EGALES if x not in e]
        points.append((r["reglages_identiques"] and not manque and all(e[x]["egal"] for x in EGALES),
                       f"égalité de F1 v1 avec le moteur de Bramble Studio, étape par étape (rendu {r['rendu']}) : réglages "
                       f"{'identiques' if r['reglages_identiques'] else 'DIFFÉRENTS'} ; " + " ; ".join(
                           f"{x} {'égal' if e[x]['egal'] else 'DIFFÉRENT ' + str(e[x].get('differents'))} ({e[x].get('fichiers', 0)} fichiers, {e[x]['date'][:16]})"
                           for x in EGALES if x in e) + (f" ; MANQUE : {', '.join(manque)}" if manque else "")))
    except (OSError, ValueError, KeyError) as x:
        points.append((False, f"égalité étape par étape : pas de rapport lisible ({x})"))
    try:
        r = json.loads((SORTIE / "egalite" / "ESSAI_LONG.json").read_text(encoding="utf-8"))
        c, f, rf = r["controle"], r["fin"], r.get("refaire") or {}
        change = moteur_change_depuis(r["commit"])
        fixes = {langue: d for langue, d in (r.get("plans_fixes") or {}).items() if d}
        coupure = r["coupure"]["images_avant"] >= 3 and r["coupure"]["jamais_refaites"]
        refait = rf.get("fin", {}).get("etat") == "finie" and rf.get("controle", {}).get("mesure") and rf.get("image_changee")
        niveau = {"Bramble (lèvres)": r["etapes"].get("bramble", 0) > 0, "musique": r["etapes"].get("musique", 0) > 0, "une version de langue": len(r["langues"]) >= 2,
                  "refaire": bool(refait), "arrêt et reprise": coupure, "quitter puis relancer": r["noyau_relance"]["seul"]}
        points += [
            (f["etat"] == "finie" and "erreur" not in r and r.get("recette") == "F1 v2" and not r["code_modifie"] and not change,
             f"essai pleine longueur fabriqué en vrai ({r['debut']}, {r.get('recette')}, commit {r['commit'][:7]}, session Essais, jamais publié) : {f['etat']}, "
             f"{f['progression']} morceaux" + (f" ; ERREUR : {r['erreur']}" if "erreur" in r else "") + (f" ; MOTEUR CHANGÉ DEPUIS : {change}" if change else "")
             + (" ; code pas commité pendant l'essai" if r["code_modifie"] else "")),
            (r.get("duree_video_s", 0) >= DUREE_MIN_S, f"pleine longueur : vidéo de {r.get('duree_video_s', 0) / 60:.1f} min (au moins {DUREE_MIN_S // 60})"),
            (coupure and r["noyau_relance"]["seul"],
             f"repris après une coupure : exécuteur tué avec {r['coupure']['images_avant']} images faites, "
             f"{'jamais refaites' if r['coupure']['jamais_refaites'] else 'REFAITES'} ; noyau tué puis relancé, l'exécuteur "
             f"{'continue seul' if r['noyau_relance']['seul'] else 'DOUBLÉ OU PERDU'}"),
            (len(r["langues"]) >= 2, f"une vidéo finie par langue : {', '.join(r['langues']) or 'aucune'} (« commun » = langue du script)"),
            (bool(r.get("duree_h")), f"durée réelle d'un épisode mesurée : {r.get('duree_h')} h à l'horloge (attente de la carte et coupure comprises), "
                                     f"{r.get('calcul_h')} h de calcul (étapes : " + ", ".join(f"{k} {v / 60:.0f} min" for k, v in r["etapes"].items()) + ")"),
            (c["mesure"] and c["note"] is not None and "analyse" in c.get("controles", []),
             f"analysé : note de Qwen {c['note']}/10, {len(c['defauts'])} défaut(s) minuté(s) (contrôles : {', '.join(c.get('controles', [])) or 'aucun'})"),
            (r.get("plans_fixes") is not None and not fixes and "revue" in c.get("controles", []),
             f"F1 v2 : aucun plan quasi fixe au-delà de plan_fixe_max_s, mesuré sur chaque langue ({', '.join(r.get('plans_fixes') or {}) or 'RIEN DE MESURÉ'})"
             + "".join(f" — {langue} : {len(d)} trouvé(s), dont {d[0]['texte']} à {d[0]['debut']:.0f} s" for langue, d in fixes.items())),
            (bool(refait), f"corrigé par un « refaire » du plan {rf.get('plan')} ({(rf.get('defaut') or {}).get('texte', 'aucun défaut minuté sur un plan d’image')}) : "
                           f"{rf.get('fin', {}).get('etat', 'pas fait')} en {rf.get('duree_h')} h, image {'changée' if rf.get('image_changee') else 'PAS CHANGÉE'}, "
                           f"recontrôlé (note {rf.get('controle', {}).get('note')}), défauts du plan {' → '.join(map(str, rf.get('defauts_du_plan', [])))}"),
            (all(niveau.values()), "au moins le niveau des essais du 13/11 : " + ", ".join(f"{k} {'oui' if v else 'NON'}" for k, v in niveau.items())),
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
                                      f"dépôt des discussions — {dernier(r)}"))
    return points + moteur(dire) + construction(dire, publier) + bramble_points(avant)


YOUTUBE_TXT = "TITRE :\nHistoire factice de la recette {n}\n\nDESCRIPTION :\nUne histoire factice.\n\n00:00 Début\n00:15 Milieu\n00:30 Fin\n\nCrédits : factices.\n\nTAGS :\nrecette, histoire factice\n"
VIDEOS_J4 = ((1, "2099-12-01-s1e01", 70), (2, "2099-12-02-s1e02", 40))  # 70 s : trop longue pour Snapchat (60 s) ; 40 s : tous les réseaux
HOTE_TS = "recette.tailnet-factice.ts.net"


def preparer_j4():
    """Dans un sous-processus (FABRIQUE_RACINE posée) : une session réelle, deux vidéos finies avec leurs fichiers finaux (vraie vidéo 16:9
    à silences, miniature, youtube.txt, sous-titres) ; écrit {session, videos} sur la sortie."""
    import os

    import django

    os.environ["DJANGO_SETTINGS_MODULE"] = "fabrique.settings"
    django.setup()
    from django.conf import settings

    from fabrique.moteur.faux import lancer, programme as exe
    from fabrique.noyau import bases, routeur
    from fabrique.session import models as m

    bases.migrer()
    s = bases.creer("Session de la recette")
    ids = []
    with routeur.session(s):
        m.Langue.objects.create(code="en", nom="Anglais")
        for n, nom, secondes in VIDEOS_J4:
            v = m.Video.objects.create(titre=f"Histoire factice {n}", nom=nom, script={"title": f"Histoire factice {n}", "language": "en"},
                                       recette={"id": "F1", "version": 2, "reglages": {"langues": ["en"]}, "etapes": []})
            m.Morceau.objects.create(video=v, etape="montage", brique="montage", unite="", langue="", ordre=0, outil="f1_montage", etat="fini")
            d = settings.SESSIONS / s.dossier / "videos" / v.id / "commun" / "atelier" / nom / "final"
            d.mkdir(parents=True)
            lancer(exe("ffmpeg"), "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s=1280x720:r=25:d={secondes}", "-f", "lavfi",
                   "-i", f"aevalsrc=0.4*sin(2*PI*330*t)*gte(mod(t\\,7)\\,0.6):s=44100:d={secondes}", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest",
                   d / f"{nom}.mp4")
            lancer(exe("ffmpeg"), "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=orange:s=1280x720", "-frames:v", "1", d / "miniature.jpg")
            (d / "youtube.txt").write_bytes(YOUTUBE_TXT.format(n=n).encode("utf-8"))
            (d / "sous_titres.srt").write_bytes(b"1\n00:00:00,000 --> 00:00:02,000\nUne phrase factice.\n")
            ids.append(v.id)
    print(json.dumps({"session": s.id, "videos": ids}))


def publication_j4(dire) -> list[tuple[bool, str]]:
    """En vrais processus, en simulation, sur un dossier temporaire : chaîne reliée au faux YouTube, vidéo 1 approuvée et publiée depuis le PC
    (non répertoriée : la première de la chaîne), vidéo 2 approuvée et publiée depuis l'iPhone (cookie de la page, code à 6 chiffres, hôte de
    Tailscale : privée puis publique au créneau), double clic refusé ; paquets faits par leur tâche et contrôlés contre les vraies fiches ;
    relevé du jour en base."""
    import os
    import socket
    import tempfile
    import time
    import urllib.error
    import urllib.request

    from fabrique.fenetre.client import Client, ErreurApi

    tmp = Path(tempfile.mkdtemp(prefix="fabrique_j4_"))
    racine, points = tmp / "FABRIQUE", []
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "FABRIQUE_RACINE": str(racine), "FABRIQUE_PORT": str(port), "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "-c", "import verifier; verifier.preparer_j4()"], cwd=DEPOT / "outils_dev", env=env, capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    if r.returncode:
        return [(False, f"recette J4 : préparation ratée — {r.stderr.strip()[-300:]}")]
    prep = json.loads(r.stdout.strip().splitlines()[-1])
    sid, (v1, v2) = prep["session"], prep["videos"]
    noyau = subprocess.Popen([sys.executable, "-m", "fabrique", "noyau"], cwd=DEPOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    fenetre = Client("fenetre", port=port, donnees=racine / "donnees")
    base = f"http://127.0.0.1:{port}"
    cookie = {}

    def iphone(methode: str, chemin: str, corps=None) -> tuple[int, dict]:
        h = {"Host": HOTE_TS, "Content-Type": "application/json", **({"X-Fabrique": "iphone"} if methode == "POST" else {}),
             **({"Cookie": f"fabrique_iphone={cookie['jeton']}"} if cookie else {})}
        q = urllib.request.Request(base + chemin, data=json.dumps(corps or {}).encode() if methode == "POST" else None, method=methode, headers=h)
        try:
            with urllib.request.urlopen(q, timeout=60) as rep:
                if c := rep.headers.get("Set-Cookie", ""):
                    cookie["entete"], cookie["jeton"] = c, c.split(";")[0].split("=", 1)[1]
                return rep.status, json.loads(rep.read() or b"null") if "json" in rep.headers.get("Content-Type", "") else {"html": True}
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def pubs(video: str) -> list[dict]:
        return fenetre.appeler("publications", id=sid, video=video)

    try:
        banc.attendre(fenetre.repond, 60, "le noyau répond")
        dire("chaîne reliée au faux YouTube (navigateur simulé)…")
        lien = fenetre.appeler("relier", id=sid, langue="en")
        with urllib.request.urlopen(lien["url"], timeout=30) as page:
            relie = "Chaîne reliée" in page.read().decode("utf-8")
        d = fenetre.appeler("destinations", id=sid)[0]
        points.append((relie and d["reliee"] and d["chaine"] != "", f"chaîne de la langue reliée (connexion guidée, faux Google) : {d['etat']}, « {d['chaine']} », "
                                                                    f"{len(d['playlists'])} playlist(s)"))
        dire("vidéo 1 : approuvée puis publiée depuis le PC…")
        fenetre.appeler("approuver", id=sid, video=v1)
        p = pubs(v1)[0]
        a = (p["non_repertorie"], p["miniature"] != "", len(p["chapitres"]), p["enfants"], p["ia"], p["fautes"])
        fenetre.appeler("publier", id=sid, pub=p["id"], action="publier")
        try:
            fenetre.appeler("publier", id=sid, pub=p["id"], action="publier")
            double = "accepté"
        except ErreurApi as e:
            double = str(e)
        p = banc.attendre(lambda: (x := pubs(v1)[0])["statut"] in ("non_repertoriee", "planifiee", "erreur") and x, 180, "l'envoi de la vidéo 1")
        points.append((a[0] and a[1] and a[2] == 3 and a[3] and a[4] and not a[5] and p["statut"] == "non_repertoriee" and p["lien"] != "" and double != "accepté"
                       and all(x in p["envoi"] for x in ("video", "sous_titres", "miniature")) and "playlist" not in p["envoi"],
                       f"depuis le PC : aperçu complet (non répertorié {a[0]}, miniature {a[1]}, {a[2]} chapitres, enfants {a[3]}, IA {a[4]}, "
                       f"fautes {a[5] or 'aucune'} ; une vidéo d'essai n'entre dans aucune playlist) ; "
                       f"publiée : {p['statut']} ({p['envoi']}) {p['lien']} ; double clic : {double}"))
        dire("page iPhone : code, cookie, puis vidéo 2 approuvée et publiée depuis l'iPhone…")
        code_page, page_ = iphone("GET", "/iphone/")
        sans = iphone("GET", "/api/etat")[0]
        code = fenetre.appeler("code_telephone")["code"]
        faux_code = iphone("POST", "/iphone/connexion", {"code": f"{(int(code) + 1) % 10**6:06d}"})[0]
        connecte = iphone("POST", "/iphone/connexion", {"code": code})[0]
        sur = all(x in cookie.get("entete", "") for x in ("HttpOnly", "Secure", "SameSite=Strict"))
        etat_i = iphone("GET", "/api/etat")[0]
        refus = iphone("POST", "/api/sauvegardes")[0]
        points.append((code_page == 200 and sans == 401 and faux_code == 403 and connecte == 200 and sur and etat_i == 200 and refus == 403,
                       f"page iPhone servie à l'hôte de Tailscale ({code_page}) ; sans cookie : {sans} ; mauvais code : {faux_code} ; bon code : {connecte}, cookie "
                       f"{'HttpOnly, Secure, SameSite=Strict' if sur else 'SANS SES PROTECTIONS'} ; état lu : {etat_i} ; sauvegarde (droit de la fenêtre) : {refus}"))
        st_a = iphone("POST", f"/api/sessions/{sid}/videos/{v2}/approuver")
        p = banc.attendre(lambda: pubs(v2), 30, "le brouillon de la vidéo 2")[0]
        fenetre.appeler("choisir", {"playlist": d["playlists"][0]["id"]}, id=sid, pub=p["id"])  # la playlist se choisit à la fenêtre seulement
        st_p = iphone("POST", f"/api/sessions/{sid}/publications/{p['id']}/publier")
        p = banc.attendre(lambda: (x := pubs(v2)[0])["statut"] in ("non_repertoriee", "planifiee", "erreur") and x, 180, "l'envoi de la vidéo 2")
        points.append((st_a[0] == st_p[0] == 200 and p["statut"] == "planifiee" and not p["non_repertorie"] and p["lien"] != ""
                       and all(x in p["envoi"] for x in ("video", "playlist", "sous_titres", "miniature")),
                       f"depuis l'iPhone : approuver {st_a[0]}, publier {st_p[0]} ({st_p[1].get('message', st_p[1].get('detail'))}) ; {p['statut']}, privée puis publique le "
                       f"{p['creneau']}, playlist « {p['playlist_titre']} » ({p['envoi']})"))
        with closing(sqlite3.connect(f"file:{racine / 'donnees' / 'noyau.sqlite3'}?mode=ro", uri=True)) as b:
            gestes = [json.loads(x) for (x,) in b.execute("SELECT detail FROM noyau_journal WHERE action = 'geste'")]
        vus = sorted({(g["quoi"], g["appelant"]) for g in gestes})
        points.append((vus == [("approuver", "fenetre"), ("approuver", "iphone"), ("publier", "fenetre"), ("publier", "iphone")],
                       f"gestes journalisés « RT » avec leur origine : {', '.join(f'{q} ({a})' for q, a in vus)}"))
        dire("paquets prêts à poster (tâche « paquets », vraies fiches)…")
        fiches = {f["id"]: f for f in json.loads((DEPOT / "fabrique" / "publication" / "reseaux.json").read_text(encoding="utf-8"))["reseaux"]}
        for v, (n, _, secondes) in ((v1, VIDEOS_J4[0]), (v2, VIDEOS_J4[1])):
            q = banc.attendre(lambda: (x := fenetre.appeler("paquets", id=sid, video=v)) and all(y["etat"] != "à faire" for y in x) and x, 900, f"les paquets de la vidéo {n}", pas=2)
            ecarts = []
            for y in q:
                f = fiches[y["reseau"]]
                for x in y["fichiers"]:
                    pr = json.loads(subprocess.run([ffprobe(), "-v", "error", "-show_entries", "stream=codec_name,pix_fmt", "-of", "json", str(Path(y["dossier"]) / x["nom"])],
                                                   capture_output=True, text=True, encoding="utf-8").stdout)["streams"]
                    if sorted(s["codec_name"] for s in pr) != ["aac", "h264"] or "yuv420p" not in [s.get("pix_fmt") for s in pr]:
                        ecarts.append(f"{x['nom']} : {pr}")
                ecarts += y["fautes"] + [f"{y['nom']} : texte de {len(t['texte'])} caractères" for t in y["textes"] if len(t["texte"]) > f["texte_max"]]
                ecarts += [f"{y['nom']} : titre trop long" for t in y["textes"] if len(t["titre"]) > f["titre_max"]]
            attendus = {k for k, f in fiches.items() if secondes <= f["duree_max_s"] * f["parties_max"]}
            faits = {y["reseau"] for y in q if y["etat"] == "fait"}
            points.append((faits == attendus and not ecarts and all(y["raison"] for y in q if y["etat"] == "impossible"),
                           f"paquets de la vidéo {n} ({secondes} s) conformes aux fiches (format, durée, poids, h264 + aac, texte) : "
                           + " ; ".join(f"{y['nom']} {y['etat']}" + (f" ({len(y['fichiers'])} fichier(s), {', '.join(str(x['largeur']) + '×' + str(x['hauteur']) for x in y['fichiers'])})"
                                                                     if y["fichiers"] else f" — {y['raison']}") for y in q)
                           + (f" ; ÉCARTS : {ecarts[:5]}" if ecarts else "")))
        dire("relevé des statistiques (tâche « releve »)…")
        r = subprocess.run([sys.executable, "-m", "fabrique", "executer", "releve"], cwd=DEPOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=300)
        dossier = next(p for p in (racine / "sessions").iterdir() if (p / "session.sqlite3").is_file() and p.name != "essais")
        with closing(sqlite3.connect(f"file:{dossier / 'session.sqlite3'}?mode=ro", uri=True)) as b:
            jours = b.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM session_statistiquejour WHERE publication_id IS NULL").fetchone()
        e = json.loads((racine / "donnees" / "taches" / "releve.json").read_text(encoding="utf-8"))
        points.append((r.returncode == 0 and e["etat"] == "fait" and e["fin"][:10] == f"{datetime.now():%Y-%m-%d}" and jours[0] > 0,
                       f"relevé du jour en base : {e['etat']} le {e['fin']}, chaîne : {jours[0]} jour(s) du {jours[1]} au {jours[2]} ({'; '.join(e.get('faits', []))})"))
    except (AssertionError, ErreurApi, OSError, KeyError, ValueError) as e:
        points.append((False, f"publication en vrais processus : {type(e).__name__} : {e}"))
    finally:
        subprocess.run([sys.executable, "-m", "fabrique", "arreter"], cwd=DEPOT, env=env, capture_output=True, timeout=120)
        noyau.kill()
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "fabrique/tests/test_publication.py", "fabrique/tests/test_telephone.py", "fabrique/tests/test_api.py",
                        "fabrique/tests/test_fenetre.py"], cwd=DEPOT, capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    points.append((r.returncode == 0, "tests de la publication : coupure et reprise à l'octet reçu (processus tué, jamais une 2e vidéo), double clic, non répertorié "
                                      "d'abord, langue sans chaîne, erreur en clair et alerte, jeton jamais rendu ni journalisé, refus de Google, simulation jamais vers une "
                                      "vraie chaîne, miniature, playlist, sous-titres ; paquets (parties aux silences, reprise, droits) ; relevé (quota, réessai) ; page "
                                      f"iPhone (code, cookie, droits) ; écrans Publication, Destinations, Téléphone — {dernier(r)}"))
    shutil.rmtree(tmp, ignore_errors=True)
    return points


def ffprobe() -> str:
    from fabrique.moteur.faux import programme

    return programme("ffprobe")


def gestes_j4() -> list[tuple[bool, str]]:
    """Les gestes de RT (plan § 7.3), lus dans l'installation réelle (lecture seule) : chaînes reliées, vidéo d'essai publiée en non répertorié
    depuis le PC puis depuis l'iPhone."""
    studio = garde.studio_bramble() or DEPOT.parents[1]
    donnees = studio / "FABRIQUE" / "donnees" / "noyau.sqlite3"
    try:
        with closing(sqlite3.connect(f"file:{donnees}?mode=ro", uri=True)) as b:
            gestes = [json.loads(x) for (x,) in b.execute("SELECT detail FROM noyau_journal WHERE action = 'geste' AND acteur = 'RT'")]
            sessions = [(i, d) for i, d in b.execute("SELECT id, dossier FROM noyau_session WHERE essais = 0")]
        reliees, publiees = [], []
        for i, d in sessions:
            with closing(sqlite3.connect(f"file:{studio / 'FABRIQUE' / 'sessions' / d / 'session.sqlite3'}?mode=ro", uri=True)) as b:
                reliees += [x for (x,) in b.execute("SELECT langue FROM session_destination WHERE simulation = 0 AND jeton != '' AND refusee IS NULL")]
                publiees += [(i, pk, s) for pk, s in b.execute("SELECT id, statut FROM session_publication WHERE simulation = 0 AND identifiant_youtube != ''")]
        non_rep = [(i, pk) for i, pk, s in publiees if s == "non_repertoriee"]
        depuis = {g["appelant"] for g in gestes if g.get("quoi") == "publier" and (g.get("session"), g.get("publication")) in non_rep}  # chaque origine : une non répertoriée
    except (sqlite3.Error, OSError, ValueError, KeyError) as e:
        return [(False, f"gestes de RT : installation réelle illisible ({e})")]
    return [(bool(reliees), f"geste de RT : chaînes reliées dans Fabrique (réel) : {', '.join(reliees) or 'AUCUNE ENCORE'}"),
            (bool(non_rep) and {"fenetre", "iphone"} <= depuis,
             f"geste de RT : vidéo d'essai publiée en non répertorié sur une chaîne reliée ({len(non_rep)} non répertoriée(s)), depuis : "
             f"{', '.join(sorted(depuis)) or 'NI LE PC NI L’IPHONE ENCORE'} (le PC puis l'iPhone attendus)")]


def j4(dire, publier: bool = False) -> list[tuple[bool, str]]:
    """J4 (plan § 7.1) : la publication en vrais processus sur le faux YouTube, la page iPhone, les paquets contre les fiches, le relevé ; puis la
    construction et la recette d'installation, Bramble Studio intact ; enfin les gestes de RT lus dans l'installation réelle."""
    avant = bramble_avant(dire)
    return publication_j4(dire) + construction(dire, publier) + bramble_points(avant) + gestes_j4()


def comparer_j5(a: str, b: str):
    """Dans un sous-processus (FABRIQUE_RACINE posée) : les deux sessions comparées — chaque table de leur base (sauf la fiche, qui porte
    l'identifiant de la session) et chaque fichier de leur dossier, vidéos comprises (empreintes) ; écrit le résultat sur la sortie."""
    import os
    import sqlite3

    import django

    os.environ["DJANGO_SETTINGS_MODULE"] = "fabrique.settings"
    django.setup()
    from fabrique.noyau import echange, routeur
    from fabrique.noyau.models import Session

    def contenu(s):
        with closing(sqlite3.connect(routeur.chemin(s))) as c:
            tables = [x for (x,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'session_%' AND name != 'session_fiche'")]
            return {x: sorted(map(repr, c.execute(f"SELECT * FROM {x}"))) for x in tables}

    sa, sb = Session.objects.get(id=a), Session.objects.get(id=b)
    ta, tb = contenu(sa), contenu(sb)
    fa, fb = ({k: echange.empreinte(f) for k, f in echange.fichiers(s, True).items()} for s in (sa, sb))
    print(json.dumps({"tables": ta == tb, "n_tables": len(ta), "lignes": sum(map(len, ta.values())), "fichiers": fa == fb, "n_fichiers": len(fa),
                      "videos": sum(k.startswith("videos/") for k in fa), "differentes": sorted(k for k in ta if ta[k] != tb.get(k))[:5]}))


def sessions_j5(dire) -> list[tuple[bool, str]]:
    """En vrais processus, en simulation, sur un dossier temporaire, par les appels de la fenêtre : nouvelle session de zéro (7 étapes),
    univers (personnage, lieu, image de référence importée et validée, droits, style), règles et garde-fou, vidéo pilote fabriquée par la file,
    idée, calendrier ; puis exportée avec ses vidéos et réimportée : identique."""
    import os
    import socket
    import tempfile

    from fabrique.fenetre.client import Client, ErreurApi

    tmp = Path(tempfile.mkdtemp(prefix="fabrique_j5_"))
    racine, points = tmp / "FABRIQUE", []
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "FABRIQUE_RACINE": str(racine), "FABRIQUE_PORT": str(port), "PYTHONIOENCODING": "utf-8"}
    noyau = subprocess.Popen([sys.executable, "-m", "fabrique", "noyau"], cwd=DEPOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    f = Client("fenetre", port=port, donnees=racine / "donnees")
    try:
        banc.attendre(f.repond, 60, "le noyau répond")
        dire("nouvelle session de zéro, étape par étape…")
        sid = f.appeler("nouvelle_session", {"nom": "Session de la recette J5", "langues": [{"code": "en", "nom": "Anglais"}, {"code": "fr", "nom": "Français"}],
                                             "public": "enfants factices", "promesse": "une histoire calme et factice"})["id"]
        en_pause = next(x for x in f.appeler("sessions") if x["id"] == sid)["pause"]
        f.appeler("ecrire_reglages", {"formats": ["essai"], "assistant": "3"}, id=sid)
        f.appeler("ajouter_element", {"type": "personnage", "nom": "Ami Factice", "role": "ami", "description": "un renard factice"}, id=sid)
        f.appeler("ajouter_element", {"type": "lieu", "nom": "Clairière factice", "description": "", "role": ""}, id=sid)
        image = tmp / "Image de référence.png"
        image.write_bytes((DEPOT / "fabrique" / "tests" / "reference_factice.png").read_bytes())
        perso = f.appeler("univers", id=sid)["personnages"][0]
        f.appeler("importer_reference", {"fichier": str(image), "vue": "face"}, id=sid, pk=perso["id"])
        ref = f.appeler("univers", id=sid)["personnages"][0]["references"][0]
        f.appeler("valider_reference", {"validee": True}, id=sid, pk=ref["id"])
        f.appeler("ecrire_droits", {"licence": "image générée", "credit": "Fabrique (recette)"}, id=sid, type="personnage", pk=perso["id"])
        f.appeler("ecrire_reglages", {"style": "aquarelle factice", "assistant": "4"}, id=sid)
        f.appeler("ecrire_reglages", {"assistant": "5"}, id=sid)  # destinations : rien à relier en recette (une langue sans chaîne est fabriquée, pas envoyée)
        try:
            f.appeler("finir_session", id=sid)
            sans_difference = "acceptée"
        except ErreurApi as e:
            sans_difference = str(e)
        f.appeler("ecrire_reglages", {"difference": "un animal et un lieu différents à chaque vidéo", "duree_min": 3, "duree_max": 8, "assistant": "6"}, id=sid)
        f.appeler("ecrire_reglages", {"objectif": "une vidéo pilote", "arret": "après la recette", "plafond_eur": 0}, id=sid)
        f.appeler("finir_session", id=sid)
        r = f.appeler("reglages", id=sid)
        u = f.appeler("univers", id=sid)
        points.append((en_pause and "il manque encore" in sans_difference and not r["pause"] and r["assistant"] == "fini" and r["formats"] == ["essai"]
                       and [l["code"] for l in r["langues"]] == ["en", "fr"] and u["personnages"][0]["references"][0]["validee"]
                       and u["personnages"][0]["licence"] == "image générée" and u["style"] == "aquarelle factice" and len(u["lieux"]) == 1,
                       f"nouvelle session créée de zéro par les 6 étapes de la fenêtre (en pause pendant l'assistant : {en_pause} ; « Terminer » sans ce qui rend chaque "
                       f"vidéo différente : {sans_difference}) ; format {r['format']}, langues {', '.join(l['code'] for l in r['langues'])}, univers : "
                       f"{len(u['personnages'])} personnage (image copiée, validée, droits), {len(u['lieux'])} lieu, style"))
        dire("vidéo pilote en simulation, par la file…")
        f.appeler("pilote", id=sid)
        v = banc.attendre(lambda: (x := f.appeler("videos", id=sid)) and x[0]["progression"].split("/")[0] == x[0]["progression"].split("/")[1] and x[0], 240,
                          "la vidéo pilote finie")
        tache = next(x for x in f.appeler("file") if x["session"] == "Session de la recette J5")
        d = f.appeler("video", id=sid, video=v["id"])
        points.append((tache["etat"] == "finie" and v["erreurs"] == 0 and all(e["finis"] == e["total"] for e in d["etapes"])
                       and all(o.startswith("faux_") for e in d["etapes"] for o in e["outils"]),
                       f"vidéo pilote fabriquée en simulation par la file (tâche {tache['etat']}, {v['progression']} morceaux, outils : "
                       f"{', '.join(sorted({o for e in d['etapes'] for o in e['outils']}))})"))
        dire("puis « en vrai » : une idée devenue script, datée, écrite par Claude, fabriquée (simulation)…")
        claude = Client("claude", port=port, donnees=racine / "donnees")
        claude.appeler("ajouter_idee", {"titre": "Une idée factice", "resume": "", "source": ""}, id=sid)
        code = f.appeler("creer_script", {"titre": "", "date": "", "idee": f.appeler("idees", id=sid)[0]["id"]}, id=sid)["code"]
        f.appeler("dater_script", {"date": "2099-01-05"}, id=sid, code=code)
        claude.appeler("nouvelle_version", {"contenu": {"titre": "Une idée factice", "scenes": [{"id": "s1", "plans": [{"id": "p1", "texte": "Il était une fois."}]}]}},
                       id=sid, code=code)
        statuts = [f.appeler("calendrier", session=sid, debut="2099-01-01", fin="2099-01-31")[0]["statut"]]
        f.appeler("fabriquer", id=sid, code=code)
        statuts.append(f.appeler("calendrier", session=sid, debut="2099-01-01", fin="2099-01-31")[0]["statut"])
        banc.attendre(lambda: next(x for x in f.appeler("file") if x["titre"] == "Une idée factice")["etat"] == "finie", 240, "la vidéo du script finie")
        cal = f.appeler("calendrier", session=sid, debut="2099-01-01", fin="2099-01-31")
        statuts.append(cal[0]["statut"])
        cartes = {x["id"]: x for x in f.appeler("sessions")}
        points.append((statuts == ["prete", "fabrication", "a_verifier"] and [(x["code"], x["date"]) for x in cal] == [(code, "2099-01-05")]
                       and f.appeler("idees", id=sid)[0]["statut"] == "convertie" and cartes[sid]["videos"] == 2 and cartes[sid]["a_faire"] == 1,
                       f"idée (Claude) → script {code} daté du 05/01/2099 → version écrite par Claude → « Fabriquer » : au calendrier, statut {' → '.join(statuts)} ; "
                       f"carte du mur : {cartes[sid]['videos']} vidéos, {cartes[sid]['a_faire']} à faire (la vidéo du script ; la pilote se regarde seulement)"))
        dire("export avec les vidéos, puis import…")
        f.appeler("agir_session", {"nom": "", "videos": True}, id=sid, action="exporter")  # à côté de la requête : une notification à la fin
        fichier = str(banc.attendre(lambda: next((racine / "exports").glob("*.fabrique"), None), 120, "le fichier exporté"))
        f.appeler("importer_session", {"fichier": fichier, "nom": "Session de la recette J5 (réimportée)"})
        sid2 = next(x["id"] for x in f.appeler("sessions") if x["nom"] == "Session de la recette J5 (réimportée)")
        c = subprocess.run([sys.executable, "-c", f"import verifier; verifier.comparer_j5('{sid}', '{sid2}')"], cwd=DEPOT / "outils_dev", env=env,
                           capture_output=True, text=True, encoding="utf-8", timeout=300)
        egal = json.loads(c.stdout.strip().splitlines()[-1]) if c.returncode == 0 else {"tables": False, "fichiers": False, "erreur": c.stderr[-300:]}
        points.append((egal["tables"] and egal["fichiers"] and egal.get("videos", 0) > 0,
                       f"exportée ({Path(fichier).name}, {Path(fichier).stat().st_size // 1024} Ko) puis réimportée à l'identique : tables {egal['tables']} "
                       f"({egal.get('n_tables')} tables, {egal.get('lignes')} lignes), fichiers {egal['fichiers']} ({egal.get('n_fichiers')} fichiers dont "
                       f"{egal.get('videos')} de vidéos finales et leurs scripts, sans les pièces intermédiaires)"
                       f"{' — ' + str(egal.get('differentes') or egal.get('erreur')) if not (egal['tables'] and egal['fichiers']) else ''}"))
    except (AssertionError, ErreurApi, OSError, ValueError, KeyError, StopIteration) as e:
        points.append((False, f"recette J5 interrompue : {type(e).__name__} : {e}"))
    finally:
        try:
            f.appeler("arreter")
        except (OSError, ErreurApi):
            pass
        try:
            noyau.wait(30)
        except subprocess.TimeoutExpired:
            noyau.kill()
        shutil.rmtree(tmp, ignore_errors=True)
    return points


ECRANS_J5 = {  # cahier § 8, sauf Outils, Banc, Statistiques et Assistant : la capture de référence de chacun (tests/captures, comparées par la suite)
    "Accueil (mur des sessions, file, santé, à faire)": ["accueil", "accueil_2560"],
    "Session → Calendrier (et idées)": ["calendrier", "calendrier_150"], "Session → Vidéos": ["videos"], "Session → Scripts": ["sessions"],
    "Session → Univers": ["univers"], "Session → Formats": ["formats"], "Session → Destinations": ["destinations"], "Session → Règles": ["regles"],
    "Nouvelle session (pas à pas)": ["nouvelle", "nouvelle_5"],
    "Vidéo → Script": ["video_script", "script", "script_ecriture"], "Vidéo → Planche": ["planche"], "Vidéo → Fabrication": ["fabrication"],
    "Vidéo → Vérification": ["video"], "Vidéo → Publication": ["publication"], "Vidéo → Suivi": ["suivi"],
    "File": ["file"], "Système": ["systeme", "systeme_125", "systeme_150", "systeme_2560"],
}


def ecrans_j5() -> list[tuple[bool, str]]:
    """Les écrans : parcours (clics, clavier) et captures comparées, sans fenêtre visible ; la page iPhone par ses tests (servie, droits)."""
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "fabrique/tests/test_fenetre.py", "fabrique/tests/test_telephone.py", "fabrique/tests/test_sessions.py",
                        "fabrique/tests/test_echange.py"], cwd=DEPOT, capture_output=True, text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    captures = {f.stem for f in (DEPOT / "fabrique" / "tests" / "captures").glob("*.png")}
    manquent = [c for liste in ECRANS_J5.values() for c in liste if c not in captures]
    return [(r.returncode == 0, f"tests des écrans, de la page iPhone, des sessions et de l'échange : {dernier(r)}"),
            (not manquent, f"écrans du cahier (sauf Outils, Banc, Statistiques, Assistant), chacun avec sa capture de référence regardée : "
                           + " ; ".join(f"{e} ({', '.join(c)})" for e, c in ECRANS_J5.items()) + (f" — MANQUENT : {', '.join(manquent)}" if manquent else "")
                           + " ; page iPhone : tests (servie à l'hôte de Tailscale, code, cookie, droits)")]


def j5(dire, publier: bool = False) -> list[tuple[bool, str]]:
    """J5 (plan § 7.1) : une session créée de zéro, exportée puis réimportée à l'identique ; les écrans ; puis la construction et l'installation,
    Bramble Studio intact."""
    avant = bramble_avant(dire)
    return sessions_j5(dire) + ecrans_j5() + construction(dire, publier) + bramble_points(avant)


def tables_j6(racine: Path) -> dict:
    """Le contenu de chaque table de la base du noyau et des bases des sessions, lu sans écrire (lecture seule)."""
    contenu = {}
    for base in [racine / "donnees" / "noyau.sqlite3", *sorted((racine / "sessions").glob("*/session.sqlite3"))]:
        with closing(sqlite3.connect(f"file:{base}?mode=ro", uri=True)) as c:
            for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'django_migrations'"):
                contenu[f"{base.parent.name}/{t}"] = sorted(map(repr, c.execute(f"SELECT * FROM {t}")))
    return contenu


def empreinte_du_code() -> str:
    import hashlib

    h = hashlib.sha256()
    for f in sorted((DEPOT / "fabrique").rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts and "tests" not in f.parts:
            h.update(f.read_bytes())
    return h.hexdigest()


def outils_j6(dire) -> list[tuple[bool, str]]:
    """En vrais processus, en simulation, sur un dossier temporaire, par les appels de la fenêtre (RT) et les commandes de Claude : un outil
    local candidat installé par sa recette (tâche détachée), banc à l'aveugle contre l'outil en place sur une vidéo de la session Essais,
    votes, verdict, adoption ; rien d'autre n'a bougé ; la vidéo suivante prend le nouvel outil ; banc payant refusé à 0 €, joué sous
    plafond, refusé au-delà ; veille versée par Claude."""
    import os
    import socket
    import tempfile

    from fabrique.fenetre.client import Client, ErreurApi

    tmp = Path(tempfile.mkdtemp(prefix="fabrique_j6_"))
    racine, points = tmp / "FABRIQUE", []
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "FABRIQUE_RACINE": str(racine), "FABRIQUE_PORT": str(port), "PYTHONIOENCODING": "utf-8"}
    script = tmp / "script.json"
    script.write_text(json.dumps({**SCRIPT, "titre": "Essai de la recette J6"}), encoding="utf-8")

    def lancer(*args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "fabrique", *map(str, args)], cwd=DEPOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)

    noyau = subprocess.Popen([sys.executable, "-m", "fabrique", "noyau"], cwd=DEPOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    f = Client("fenetre", port=port, donnees=racine / "donnees")
    claude = Client("claude", port=port, donnees=racine / "donnees")
    candidat, en_ligne = "faux_voix_douce", "faux_voix_en_ligne"

    def outil(id_: str) -> dict:
        return next(o for b in f.appeler("outils")["briques"] for o in b["outils"] if o["id"] == id_)

    def video_finie() -> str:
        assert lancer("moteur", "essai", script).returncode == 0
        return banc.attendre(lambda: (t := [x for x in f.appeler("file") if not x["banc"]]) and t[0]["etat"] == "finie" and t[0], 240, "la vidéo d'essai finie")

    def banc_pret(n: int) -> dict:
        return banc.attendre(lambda: len(b := f.appeler("bancs")) >= n and b[0]["etat"] in ("a_voter", "erreur") and b[0], 240, "le banc prêt à voter")

    def voter(b: dict, pour: str):
        """RT (simulé) préfère `pour` : la recette lit dans la base de quel côté il est ; la fenêtre ne le montre jamais avant le verdict."""
        with closing(sqlite3.connect(f"file:{racine / 'donnees' / 'noyau.sqlite3'}?mode=ro", uri=True)) as c:
            entrees, a, bb = c.execute("SELECT entrees, outil_a, outil_b FROM noyau_banc WHERE id = ?", (b["id"],)).fetchone()
        cote = "a" if pour == a else "b"
        for i, e in enumerate(json.loads(entrees)):
            f.appeler("voter", {"entree": i, "choix": "egal" if i == 0 else "gauche" if e["gauche"] == cote else "droite"}, id=b["id"])
        f.appeler("rendre_verdict", id=b["id"])

    try:
        banc.attendre(f.repond, 60, "le noyau répond")
        essais = next(x["id"] for x in f.appeler("sessions") if x["essais"])
        dire("veille : avant et après le versement de Claude…")
        etat = racine / "donnees" / "etat.json"
        avant_veille = banc.attendre(lambda: etat.is_file() and json.loads(etat.read_text(encoding="utf-8"))["veille"], 60, "etat.json écrit")["a_faire"]
        (fv := tmp / "veille.json").write_text(json.dumps({"candidats": [{"brique": "voix", "nom": "Voix candidate factice", "licence": "Apache 2.0", "commercial": True,
                                                                          "avis": "repérée par la recette"}]}), encoding="utf-8")
        r = lancer("commande", "veille", fv)
        liste = f.appeler("veille")
        apres_veille = banc.attendre(lambda: not json.loads((racine / "donnees" / "etat.json").read_text(encoding="utf-8"))["veille"]["a_faire"], 90, "etat.json à jour")
        points.append((avant_veille and r.returncode == 0 and [x["nom"] for x in liste] == ["Voix candidate factice"] and liste[0]["statut"] == "nouveau" and apres_veille,
                       f"veille mensuelle : « à faire » dans etat.json avant ; « commande veille » (Claude) : {r.stdout.strip()} ; le candidat dans l'écran Outils (statut nouveau) ; "
                       f"plus « à faire » après"))
        dire("installer l'outil candidat (tâche détachée)…")
        c0 = outil(candidat)
        f.appeler("agir_outil", outil=candidat, action="installer")
        fait = banc.attendre(lambda: json.loads((racine / "donnees" / "taches" / "installation.json").read_text(encoding="utf-8")).get("etat") in ("faite", "erreur"),
                             120, "l'installation finie")
        c1 = outil(candidat)
        temoins = [p.name for p in (racine / "outils" / candidat / "2").rglob("*") if p.is_file()]
        points.append((fait and c0["action"] == "installer" and c1["action"] == "" and c1["installation"] == "version 2 installée" and c1["etat"] == "candidat"
                       and sorted(temoins) == ["modele.json", "pret.txt"],
                       f"outil candidat installé depuis l'écran Outils par sa recette (tâche détachée « installation », 3 pas) : « {c0['installation']} » → "
                       f"« {c1['installation']} » dans outils\\{candidat}\\2 ({', '.join(sorted(temoins))}) ; toujours candidat (jamais en service sans banc)"))
        dire("une vidéo d'essai, puis le banc à l'aveugle…")
        v1 = video_finie()
        video = f.appeler("videos", id=essais)[0]["id"]
        fichiers_avant = banc.empreinte(racine / "sessions", sauf=("*-wal", "*-shm"))
        f.appeler("nouveau_banc", {"session": essais, "video": video, "brique": "voix", "outil": candidat, "juge": "simule"})
        b = banc_pret(1)
        d = f.appeler("banc", id=b["id"])
        aveugle = all(x["qui"] is None and x["notes"] is None and x["gauche"] and x["droite"] for x in d["lignes"])
        voter(b, candidat)
        d = f.appeler("banc", id=b["id"])
        points.append((b["etat"] == "a_voter" and aveugle and d["etat"] == "fini" and d["peut_adopter"] and "Fausse voix douce" in d["gagnant"]
                       and all(x["notes"] for x in d["lignes"]) and (racine / "bancs" / str(b["id"]) / "verdict.json").is_file(),
                       f"banc à l'aveugle par la file (vidéo « {v1['titre']} », {b['entrees']} entrées, juge simulé) : avant le vote ni le nom des outils ni les notes du juge "
                       f"({'à l’aveugle' if aveugle else 'PAS À L’AVEUGLE'}) ; votes de RT (simulé) ; verdict gardé (base et verdict.json) : {d['verdict']}"))
        dire("adoption : rien d'autre ne doit bouger…")
        code_avant, avant = empreinte_du_code(), tables_j6(racine)
        message = f.appeler("adopter", {"ou": "brique"}, id=b["id"])["message"]
        code_apres, apres = empreinte_du_code(), tables_j6(racine)
        fichiers_apres = banc.empreinte(racine / "sessions", sauf=("*-wal", "*-shm"))
        bougees = sorted(t for t in set(avant) | set(apres) if avant.get(t) != apres.get(t))
        nouvelles = sorted(set(apres.get("donnees/noyau_parametre", [])) - set(avant.get("donnees/noyau_parametre", [])))
        attendues = {"donnees/noyau_parametre", "donnees/noyau_outil", "donnees/noyau_banc", "donnees/noyau_journal"}
        points.append((code_avant == code_apres and set(bougees) <= attendues and nouvelles == [repr(("outil.voix", candidat))] and fichiers_avant == fichiers_apres,
                       f"adoption par RT ({message}) : code du programme identique ; tables changées : {', '.join(bougees)} (le défaut de la brique, l'état de l'outil, le banc "
                       f"adopté, le journal) ; réglage ajouté : {', '.join(nouvelles)} ; toutes les tables des sessions identiques ; les {len(fichiers_avant)} fichiers des "
                       f"sessions {'identiques' if fichiers_avant == fichiers_apres else 'CHANGÉS'} du lancement du banc à l'adoption (le banc n'écrit que dans bancs\\)"))
        dire("la vidéo suivante prend le nouvel outil…")
        video_finie()
        v2 = next(x for x in f.appeler("videos", id=essais) if x["id"] != video)
        etapes = {e["id"]: e["outils"] for e in f.appeler("video", id=essais, video=v2["id"])["etapes"]}
        avant_etapes = {e["id"]: e["outils"] for e in f.appeler("video", id=essais, video=video)["etapes"]}
        autres = {k: v for k, v in etapes.items() if k != "voix"} == {k: v for k, v in avant_etapes.items() if k != "voix"}
        points.append((etapes["voix"] == [candidat] and avant_etapes["voix"] == ["faux_voix"] and autres,
                       f"un outil local remplacé par un autre après un banc : la voix de la vidéo suivante est faite par {', '.join(etapes['voix'])} (avant : "
                       f"{', '.join(avant_etapes['voix'])}) ; les 8 autres étapes gardent leurs outils ({'identiques' if autres else 'CHANGÉS'})"))
        dire("outil en ligne : plafond à 0 €, sous plafond, au-delà…")
        try:
            f.appeler("nouveau_banc", {"session": essais, "video": video, "brique": "voix", "outil": en_ligne, "juge": ""})
            a_zero = "accepté"
        except ErreurApi as e:
            a_zero = str(e)
        f.appeler("plafond", {"valeur": 1})
        f.appeler("ecrire_reglages", {"plafond_eur": 1}, id=essais)
        f.appeler("nouveau_banc", {"session": essais, "video": video, "brique": "voix", "outil": en_ligne, "juge": ""})
        b2 = banc_pret(2)
        dep = f.appeler("depenses")
        f.appeler("plafond", {"valeur": dep["depense_mois_eur"] + 0.1})
        try:
            f.appeler("nouveau_banc", {"session": essais, "video": video, "brique": "voix", "outil": en_ligne, "juge": ""})
            au_dela = "accepté"
        except ErreurApi as e:
            au_dela = str(e)
        points.append(("plafond du mois est de 0,00 €" in a_zero and b2["etat"] == "a_voter" and len(dep["lignes"]) == b2["entrees"] and dep["depense_mois_eur"] <= 1
                       and all(x["reel_eur"] is not None for x in dep["lignes"]) and "banc refusé" in au_dela,
                       f"outil en ligne (faux service payant) : plafond à 0 € → refusé (« {a_zero} ») ; plafond de 1 € → banc joué ({b2['entrees']} appels payants notés, "
                       f"{dep['depense_mois_eur']:.2f} € estimés et réels au journal des dépenses) ; plafond juste au-dessus → refusé avant tout appel (« {au_dela} »)"))
        try:
            f.appeler("agir_outil", outil=candidat, action="retirer")
            retrait = "accepté"
        except ErreurApi as e:
            retrait = str(e)
        points.append(("défaut de la brique" in retrait, f"l'outil devenu le défaut de la brique ne se retire pas : « {retrait} »"))
    except (AssertionError, ErreurApi, OSError, ValueError, KeyError, StopIteration, TypeError) as e:
        points.append((False, f"recette J6 interrompue : {type(e).__name__} : {e}"))
    finally:
        try:
            f.appeler("arreter")
        except (OSError, ErreurApi):
            pass
        try:
            noyau.wait(30)
        except subprocess.TimeoutExpired:
            noyau.kill()
        shutil.rmtree(tmp, ignore_errors=True)
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "fabrique/tests/test_outils.py", "fabrique/tests/test_moteur.py", "fabrique/tests/test_api.py",
                        "fabrique/tests/test_fenetre.py"], cwd=DEPOT, capture_output=True, text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    points.append((r.returncode == 0, "tests des outils, du moteur, de l'API et de la fenêtre : mise à jour installée à côté de l'ancienne version, retirer vers la corbeille "
                                      "et remettre, recette qui échoue (empreinte), coupure en plein banc reprise sans rien refaire, banc annulé avec sa tâche, victoire du "
                                      "juge sans écart non comptée, voix ElevenLabs contre un faux service (clé jamais dans un message), droits (Claude ne vote ni n'adopte "
                                      f"ni n'installe), écrans Outils et Banc (parcours, captures) — {dernier(r)}"))
    captures = {c.stem for c in (DEPOT / "fabrique" / "tests" / "captures").glob("*.png")}
    manquent = [c for c in ("outils", "outils_150", "banc", "banc_vote", "banc_verdict", "banc_2560") if c not in captures]
    points.append((not manquent, "écrans Outils et Banc avec leurs captures de référence regardées (outils, outils_150, banc, banc_vote, banc_verdict, banc_2560)"
                                 + (f" — MANQUENT : {', '.join(manquent)}" if manquent else "")))
    return points


def cle_en_ligne_j6() -> list[tuple[bool, str]]:
    """L'outil en ligne réel (si RT donne une clé, § 7.3) : la clé est dans l'installation de RT, chiffrée pour son compte ; la recette ne la lit pas,
    elle regarde seulement si l'essai a été fait (journal des dépenses de l'installation réelle, lu sans écrire)."""
    base = garde.studio_bramble() and Path(garde.studio_bramble()) / "FABRIQUE" / "donnees" / "noyau.sqlite3"
    try:
        with closing(sqlite3.connect(f"file:{base}?mode=ro", uri=True)) as c:
            cle = bool(c.execute("SELECT 1 FROM noyau_parametre WHERE cle = 'cle_elevenlabs' AND valeur != ''").fetchone())
            appels = c.execute("SELECT count(*), coalesce(sum(reel_eur), 0) FROM noyau_depense WHERE outil = 'elevenlabs_voix' AND reel_eur IS NOT NULL").fetchone()
            plafond = float((c.execute("SELECT valeur FROM noyau_parametre WHERE cle = 'plafond_mois_eur'").fetchone() or ["0"])[0] or 0)
    except (sqlite3.Error, TypeError, ValueError):
        cle, appels, plafond = False, (0, 0), 0
    if appels[0]:  # seuls les appels que le service a facturés (coût réel rendu) : un refus du service n'en est pas un
        return [(appels[1] <= plafond, f"outil en ligne réel (voix ElevenLabs) essayé dans l'installation de RT : {appels[0]} appel(s) réussis, {appels[1]:.2f} € "
                                       f"pour un plafond du mois de {plafond:.2f} €")]
    return [(True, "outil en ligne réel (voix ElevenLabs) : facultatif (« si RT donne une clé », § 7.3) — PAS ENCORE JOUÉ "
                   + ("(clé saisie, essai à lancer)" if cle else "(pas de clé dans l'installation de RT : QUESTIONS.md)")
                   + " ; l'adaptateur est prouvé contre un faux service local")]


def j6(dire, publier: bool = False) -> list[tuple[bool, str]]:
    """J6 (plan § 7.1) : un outil local remplacé par un autre après un banc, rien d'autre n'a bougé ; un outil en ligne essayé sous plafond (faux
    service payant ; le vrai si RT a donné une clé) ; puis la construction et l'installation, Bramble Studio intact."""
    avant = bramble_avant(dire)
    return outils_j6(dire) + cle_en_ligne_j6() + construction(dire, publier) + bramble_points(avant)


def formats_j7(dire) -> list[tuple[bool, str]]:
    """En vrais processus, en simulation, sur un dossier temporaire, par les commandes de Claude (session Essais) : trois vidéos d'essai, puis
    une compilation (F2), un extrait vertical (F3) et une courte verticale créée seule (F3s), chacune passée au contrôle technique."""
    import os
    import socket
    import tempfile

    from fabrique.fenetre.client import Client, ErreurApi

    class montages:  # mesure sans Django (le noyau tourne à part)
        @staticmethod
        def mesure(v: Path) -> dict:
            r = json.loads(subprocess.run([ffprobe(), "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", str(v)],
                                          capture_output=True, text=True, encoding="utf-8").stdout)
            im = next(x for x in r["streams"] if x["codec_type"] == "video")
            return {"largeur": im["width"], "hauteur": im["height"], "duree_s": float(r["format"]["duration"])}

    tmp = Path(tempfile.mkdtemp(prefix="fabrique_j7_"))
    racine, points = tmp / "FABRIQUE", []
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "FABRIQUE_RACINE": str(racine), "FABRIQUE_PORT": str(port), "PYTHONIOENCODING": "utf-8"}

    def lancer(*args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "fabrique", *map(str, args)], cwd=DEPOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)

    noyau = subprocess.Popen([sys.executable, "-m", "fabrique", "noyau"], cwd=DEPOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    f = Client("fenetre", port=port, donnees=racine / "donnees")

    def fabriquer(recette: str, script: dict) -> dict:
        (fs := tmp / f"{len(list(tmp.glob('*.json')))}.json").write_text(json.dumps(script), encoding="utf-8")
        r = lancer("moteur", recette, fs)
        assert r.returncode == 0, r.stdout + r.stderr
        return banc.attendre(lambda: (t := [x for x in f.appeler("file") if x["titre"] == script["titre"]]) and t[0]["etat"] in ("finie", "erreur") and t[0], 240,
                             f"« {script['titre']} » finie")

    def video(essais: str, titre: str) -> dict:
        return next(x for x in f.appeler("videos", id=essais) if x["titre"] == titre)

    def resultats(essais_dossier: Path, vid: str, etape: str) -> tuple[Path, dict, dict]:
        d = essais_dossier / "videos" / vid / "en"
        r = json.loads((d / etape / "video" / "resultat.json").read_text(encoding="utf-8"))
        return d / etape / "video" / r["fichiers"][0], r, json.loads((d / "revue" / "video" / "rapport.json").read_text(encoding="utf-8"))

    try:
        banc.attendre(f.repond, 60, "le noyau répond")
        essais = next(x for x in f.appeler("sessions") if x["essais"])
        dossier = racine / "sessions" / essais["dossier"]
        dire("trois vidéos d'essai…")
        for i in range(3):
            assert fabriquer("essai", {**SCRIPT, "titre": f"Vidéo d'essai {i + 1}"})["etat"] == "finie"
        ids = [video(essais["id"], f"Vidéo d'essai {i + 1}")["id"] for i in range(3)]
        dire("F2 : compilation…")
        t = fabriquer("F2", {"titre": "Compilation de la recette J7", "intro": ids[0], "videos": ids[1:]})
        vf, r, rap = resultats(dossier, video(essais["id"], "Compilation de la recette J7")["id"], "assemblage")
        m = montages.mesure(vf)
        parts = [montages.mesure(next((dossier / "videos" / x / "en" / "montage" / "video").glob("*.mp4")))["duree_s"] for x in ids]
        points.append((t["etat"] == "finie" and abs(m["duree_s"] - sum(parts)) < 0.5 and [c["titre"] for c in r["infos"]["chapitres"]][1:] == ["Vidéo d'essai 2", "Vidéo d'essai 3"]
                       and (vf.parent / "video.srt").is_file() and not [d for d in rap["defauts"] if d["gravite"] == "forte"],
                       f"F2 en simulation (commande « moteur F2 » de Claude, session Essais) : introduction puis deux vidéos bout à bout, {m['duree_s']:.1f} s "
                       f"(somme des parties {sum(parts):.1f} s), chapitres {', '.join(c['titre'] for c in r['infos']['chapitres'])}, sous-titres décalés, miniature ; "
                       f"contrôle technique sans défaut bloquant ({len(rap['defauts'])} défaut(s))"))
        dire("F3 : extrait vertical…")
        t = fabriquer("F3", {"titre": "Extrait de la recette J7", "source": ids[1], "debut_s": 1, "fin_s": 3})
        vf, r, rap = resultats(dossier, video(essais["id"], "Extrait de la recette J7")["id"], "verticale")
        m = montages.mesure(vf)
        points.append((t["etat"] == "finie" and (m["largeur"], m["hauteur"]) == (1080, 1920) and abs(m["duree_s"] - 2) < 0.3 and r["infos"]["incrustes"] >= 1
                       and not [d for d in rap["defauts"] if d["gravite"] == "forte"],
                       f"F3 tirée d'une vidéo longue en simulation : {m['largeur']} × {m['hauteur']}, {m['duree_s']:.1f} s (de 1 à 3 s de la source), "
                       f"{r['infos']['incrustes']} sous-titre(s) incrusté(s), contrôle technique sans défaut bloquant"))
        dire("F3 créée seule…")
        t = fabriquer("F3s", {**SCRIPT, "titre": "Courte verticale de la recette J7"})
        vf, r, rap = resultats(dossier, video(essais["id"], "Courte verticale de la recette J7")["id"], "verticale")
        m = montages.mesure(vf)
        points.append((t["etat"] == "finie" and (m["largeur"], m["hauteur"]) == (1080, 1920) and r["infos"]["incrustes"] >= 1 and not [d for d in rap["defauts"] if d["gravite"] == "forte"],
                       f"F3 créée seule en simulation (par plan, faux outils) : {m['largeur']} × {m['hauteur']}, {m['duree_s']:.1f} s, {r['infos']['incrustes']} sous-titre(s) "
                       f"incrusté(s), contrôle technique sans défaut bloquant"))
        (tmp / "absente.json").write_text(json.dumps({"titre": "x", "intro": "inconnue", "videos": ids[:2]}), encoding="utf-8")
        r = lancer("moteur", "F2", tmp / "absente.json")
        points.append((r.returncode == 1 and "vidéo inconnue" in r.stdout, f"une compilation qui cite une vidéo absente est refusée tout de suite : {r.stdout.strip()}"))
    except (AssertionError, ErreurApi, OSError, ValueError, KeyError, StopIteration) as e:
        points.append((False, f"recette J7 interrompue : {type(e).__name__} : {e}"))
    finally:
        try:
            f.appeler("arreter")
        except (OSError, ErreurApi):
            pass
        try:
            noyau.wait(30)
        except subprocess.TimeoutExpired:
            noyau.kill()
        shutil.rmtree(tmp, ignore_errors=True)
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "fabrique/tests/test_formats.py", "fabrique/tests/test_moteur.py", "fabrique/tests/test_fenetre.py"],
                       cwd=DEPOT, capture_output=True, text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    points.append((r.returncode == 0, "tests des formats F2 et F3 (refus sans vidéo finale ou hors langue, extrait de plus de 3 min, contrôle bloquant d'une durée hors "
                                      f"bornes, format propre à un script), du moteur et de la fenêtre — {dernier(r)}"))
    return points


def en_vrai_j7() -> list[tuple[bool, str]]:
    """Les essais en vrai (session Essais, jamais publiés) : lus dans la racine de travail des essais réels (OUTILS\\fabrique_construction\\egalite),
    sans rien y écrire ; rouges tant qu'ils ne sont pas faits (QUESTIONS.md)."""
    racine = SORTIE / "egalite" / "FABRIQUE" / "sessions" / "essais"
    faits = {}

    def reels(c, ids: list[str]) -> bool:
        """Toutes ces vidéos faites par de vrais outils (aucun faux)."""
        return bool(ids) and not c.execute(f"SELECT 1 FROM session_morceau WHERE video_id IN ({','.join('?' * len(ids))}) AND outil LIKE 'faux%'", ids).fetchone()

    try:
        with closing(sqlite3.connect(f"file:{racine / 'session.sqlite3'}?mode=ro", uri=True)) as c:
            for vid, script in c.execute("SELECT id, script FROM session_video"):
                sc = json.loads(script)
                recette = "F2" if "intro" in sc else "F3" if "source" in sc else "F3s" if (racine / "videos" / vid / "en" / "verticale").is_dir() else ""
                cites = [sc.get("intro"), *sc.get("videos", []), sc.get("source")]
                try:
                    rapport = json.loads(next((racine / "videos" / vid).glob("*/revue/video/rapport.json")).read_text(encoding="utf-8"))
                except (StopIteration, OSError, ValueError):
                    continue
                if recette and reels(c, [vid, *[x for x in cites if x]]) and not [x for x in rapport["defauts"] if x["gravite"] == "forte"]:
                    faits.setdefault(recette, vid)
    except sqlite3.Error:
        pass
    return [(recette in faits, f"{recette} en vrai (session Essais, outils réels, sources comprises : aucun faux outil) : " + (f"fait (vidéo {faits[recette]}), contrôle sans défaut bloquant" if recette in faits
                                                                                         else "PAS ENCORE — " + attente))
            for recette, attente in (("F2", "il faut l'essai long de J3 (cette nuit) et une introduction inédite faite par F1 de nuit (QUESTIONS)"),
                                     ("F3", "il faut l'essai long de J3 (cette nuit), puis quelques minutes sans carte"),
                                     ("F3s", "il faut des outils réels par plan : J8 (QUESTIONS)"))]


def j7(dire, publier: bool = False) -> list[tuple[bool, str]]:
    """J7 (plan § 7.1) : une vidéo de chaque format (F2, F3 tirée d'une vidéo longue, F3 seule) en simulation puis en vrai, contrôlée sans défaut
    bloquant ; puis la construction et l'installation, Bramble Studio intact."""
    avant = bramble_avant(dire)
    return formats_j7(dire) + en_vrai_j7() + construction(dire, publier) + bramble_points(avant)


JALONS = {"J1": j1, "J2": j2, "J3": j3, "J4": j4, "J5": j5, "J6": j6, "J7": j7}


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
