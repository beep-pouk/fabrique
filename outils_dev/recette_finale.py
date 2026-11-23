"""Recette « fini » de Fabrique (J12 ; cahier § 12, plan § 7.1 et § 9) : python outils_dev\\recette_finale.py [--fois 10] [--publier]
→ docs\\VERIF_FINI_PC.md (jamais suivi par git : il cite le PC). Les 12 critères, chacun avec ses preuves :
- la partie automatique (simulation, en vrais processus : les recettes J2 → J11 de verifier.py et la 2e session créée par l'assistant),
  jouée --fois de suite ; les passages verts s'additionnent d'un lancement à l'autre tant que le code ne change pas (même commit, dépôt
  propre), un rouge remet à zéro ; carte prise (Bramble Studio fabrique, ou un autre programme) avant ou pendant un passage : arrêt, sans
  compter ce passage (la file attend la carte, même pour de faux outils) ;
- la construction et la recette d'installation (installateur, mise à jour, sauvegarde et restauration), une fois par lancement ;
- les preuves « en vrai » lues, sans rien écrire : essais de nuit (racine des essais réels), installation réelle de RT (ses gestes, § 7.3).
Code de retour 0 si les 12 critères sont verts. Outil de développement : jamais livré."""
import argparse
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

import banc
import verifier as v

CRITERES = {  # cahier § 12, en bref
    1: "la session importée de Bramble Studio est la n° 1, sans perte ; Bramble Studio n'a pas bougé",
    2: "chacun des six formats fabrique une vidéo complète au seul clic, contrôlée sans défaut bloquant (F1 : au moins le niveau des essais du 13/11)",
    3: "une 2e session créée par l'assistant, sans code, fabrique sa vidéo pilote",
    4: "un outil remplacé après un banc à l'aveugle, rien d'autre ne bouge (local contre local, local contre en ligne, plafond respecté)",
    5: "une vidéo publiée sur YouTube (non répertoriée puis programmée) depuis le PC et depuis l'iPhone ; un paquet pour chaque autre réseau",
    6: "une vidéo en 10 langues, chacune prête pour la chaîne de sa langue (envoi réel vérifié sur une langue au moins)",
    7: "coupure pendant un rendu : reprise sans perte",
    8: "sauvegarde puis restauration ; export puis import d'une session",
    9: "statistiques relevées ; « quoi fabriquer ensuite » et « titres et miniatures » donnent un résultat",
    10: "l'assistant fait d'une demande écrite un plan chiffré, puis une session ou une vidéo préparée",
    11: "fenêtre native sombre, aucune page web sur le PC, aucun terminal visible ; page iPhone : voir, approuver, publier",
    12: "recette automatique verte 10 fois sur 10 ; installateur et mise à jour en un clic",
}
ETAT = v.SORTIE / "recette_finale.json"
DIX_LANGUES = v.SORTIE / "egalite" / "ESSAI_FORMATS_J12.json"


def deuxieme_session(dire) -> list[tuple[bool, str]]:
    """Critère 3 en simulation, en vrais processus, comme RT : il demande une session à l'assistant (faux moteur), dit « D'accord », termine le
    brouillon pas à pas dans la fenêtre (aucun code), puis « Vidéo pilote » : fabriquée par la file."""
    import os
    import socket
    import tempfile

    from fabrique.fenetre.client import Client, ErreurApi

    tmp = Path(tempfile.mkdtemp(prefix="fabrique_j12_"))
    racine, points = tmp / "FABRIQUE", []
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "FABRIQUE_RACINE": str(racine), "FABRIQUE_PORT": str(port), "PYTHONIOENCODING": "utf-8"}
    noyau = subprocess.Popen([sys.executable, "-m", "fabrique", "noyau"], cwd=v.DEPOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    f = Client("fenetre", port=port, donnees=racine / "donnees")
    try:
        banc.attendre(f.repond, 60, "le noyau répond")
        dire("2e session : demandée à l'assistant, terminée pas à pas, vidéo pilote…")
        plan = f.appeler("assistant", {"demande": "Je voudrais une nouvelle session de vidéos F1."})
        accord = f.appeler("assistant", {"demande": "D'accord, prépare la session.", "historique": plan["historique"], "accord": True})
        s = next(x for x in f.appeler("sessions") if x["nom"] == "Brouillon de l'assistant")
        sans_difference, r, _ = v.terminer_session(f, s["id"], tmp)
        tache, video, d = v.pilote(f, s["id"], s["nom"])
        points.append((not plan["brouillons"] and accord["brouillons"] == ["brouillon_session"] and s["pause"] and "il manque encore" in sans_difference
                       and r["assistant"] == "fini" and not r["pause"] and tache["etat"] == "finie" and video["erreurs"] == 0
                       and all(e["finis"] == e["total"] for e in d["etapes"]),
                       f"2e session par l'assistant (simulation) : « {plan['message']} » → après « D'accord » : « {accord['message']} » (en pause : {s['pause']}) ; "
                       f"terminée dans la fenêtre (« Terminer » trop tôt : {sans_difference}) ; vidéo pilote : tâche {tache['etat']}, {video['progression']} morceaux"))
    except (AssertionError, ErreurApi, OSError, ValueError, KeyError, StopIteration) as e:
        points.append((False, f"2e session par l'assistant interrompue : {type(e).__name__} : {e}"))
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


def tests_f1(dire) -> list[tuple[bool, str]]:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "fabrique/tests/test_f1.py", "fabrique/tests/test_import.py"], cwd=v.DEPOT, capture_output=True,
                       text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    return [(r.returncode == 0, f"tests de F1 et de l'import de Bramble Studio (sans perte, à l'identique) : {v.dernier(r)}")]


AUTO = [  # (critères, partie) : jouées à chaque passage
    ((1, 2), tests_f1), ((7,), v.moteur), ((5, 11), v.publication_j4), ((3, 8), v.sessions_j5), ((11,), lambda dire: v.ecrans_j5()),
    ((4,), v.outils_j6), ((2,), v.formats_j7), ((2,), v.formats_j8), ((2,), v.formats_j9), ((2,), v.formats_j10), ((9, 10), v.statistiques_j11),
    ((3,), deuxieme_session),
]


def reelle() -> tuple[Path, Path]:
    studio = v.garde.studio_bramble() or v.DEPOT.parents[1]
    return studio / "FABRIQUE" / "donnees" / "noyau.sqlite3", studio / "FABRIQUE" / "sessions"


def lire(base: Path, requete: str, *args) -> list[tuple]:
    with closing(sqlite3.connect(f"file:{base}?mode=ro", uri=True)) as b:
        return b.execute(requete, args).fetchall()


def importee() -> tuple[bool, str]:
    """Critère 1 en vrai : la session importée dans l'installation réelle de RT (lecture seule)."""
    noyau, sessions = reelle()
    try:
        s = lire(noyau, "SELECT id, dossier FROM noyau_session WHERE essais = 0 ORDER BY cree LIMIT 1")
        if not s:
            return False, "session de Bramble Studio importée dans l'installation réelle : PAS ENCORE"
        importee_ = any(json.loads(d).get("session") == s[0][0] for (d,) in lire(noyau, "SELECT detail FROM noyau_journal WHERE action = 'import_bramble'"))
        base = sessions / s[0][1] / "session.sqlite3"
        n = {t: lire(base, f"SELECT COUNT(*) FROM session_{t}")[0][0] for t in ("script", "langue", "personnage")}
        scenarios = [f for f in (reelle()[0].parents[2] / "PROJET" / "scenarios").glob("*.json") if re.fullmatch(r"\d{4}-\d\d-\d\d-s\d+e\d+", f.stem)]
        return (importee_ and n["script"] >= len(scenarios) > 0,
                f"première session de l'installation réelle : {'importée de Bramble Studio (journal)' if importee_ else 'PAS IMPORTÉE (aucune trace au journal)'} ; "
                f"{n['script']} scripts pour {len(scenarios)} scénarios chez Bramble Studio, {n['langue']} langues, {n['personnage']} personnages")
    except (sqlite3.Error, OSError) as e:
        return False, f"installation réelle illisible ({e})"


def deuxieme_reelle() -> tuple[bool, str]:
    """Critère 3 en vrai (geste de RT, § 7.3) : une session créée par l'assistant, sa vidéo pilote lancée par RT et finie."""
    noyau, _ = reelle()
    try:
        crees = {json.loads(d)["session"] for (d,) in lire(noyau, "SELECT detail FROM noyau_journal WHERE action = 'session' AND acteur = 'assistant'")
                 if json.loads(d).get("quoi") == "creer"}
        pilotes = [json.loads(d) for (d,) in lire(noyau, "SELECT detail FROM noyau_journal WHERE action = 'pilote' AND acteur = 'RT'")]
        finies = [p for p in pilotes if p["session"] in crees and lire(noyau, "SELECT 1 FROM noyau_tache WHERE session_id = ? AND video_id = ? AND etat = 'finie'",
                                                                        p["session"], p["video"])]
    except (sqlite3.Error, OSError, ValueError, KeyError) as e:
        return False, f"geste de RT (2e session) : installation réelle illisible ({e})"
    return bool(finies), (f"geste de RT : 2e session créée par l'assistant dans l'installation réelle ({len(crees)}), vidéo pilote lancée par RT et finie : "
                          f"{'oui' if finies else 'PAS ENCORE' if crees else 'PAS ENCORE (aucune session de l’assistant)'}")


def dix_langues() -> tuple[bool, str]:
    """Critère 6 en vrai : l'essai de nuit F1 en 10 langues (outils_dev/essai_formats.py, F1 et ses 9 traductions)."""
    try:
        r = json.loads(DIX_LANGUES.read_text(encoding="utf-8"))
        x = r["videos"][0]
        change = v.moteur_change_depuis(r["commit"])
        langues, fortes = x.get("langues", {}), sum(l["forte"] for l in x.get("langues", {}).values())
        return (x.get("recette") == "F1" and x.get("etat") == "finie" and len(langues) >= 10 and not fortes and not r.get("erreur") and not r["code_modifie"] and not change,
                f"F1 en vrai en {len(langues)} langues ({r['debut'][:16]}, commit {r['commit'][:7]}) : {x.get('etat')}, {fortes} défaut(s) bloquant(s) ; "
                + ", ".join(f"{l} {d['duree_s'] or 0:.0f} s" for l, d in langues.items()) + (f" ; ERREUR : {r['erreur']}" if r.get("erreur") else "") + (f" ; MOTEUR CHANGÉ DEPUIS : {change}" if change else "")
                + (" ; code pas commité pendant l'essai" if r["code_modifie"] else ""))
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return False, "F1 en vrai en 10 langues : PAS ENCORE — essai de nuit (essai_formats.py F1 essai-langues.json), carte libre"


def en_vrai() -> dict[int, list[tuple[bool, str]]]:
    j3 = v.preuves_j3()  # égalité étape par étape, puis l'essai pleine longueur (F1, coupure)
    gestes = v.gestes_j4()
    return {1: [j3[0], importee()], 2: j3[1:] + v.en_vrai_j7() + v.en_vrai_j8() + v.en_vrai_j9() + v.en_vrai_j10(), 3: [deuxieme_reelle()],
            4: [(ok and "PAS ENCORE" not in t, t) for ok, t in v.cle_en_ligne_j6()], 5: gestes, 6: [dix_langues(), *(gestes[1:2] or gestes[:1])], 7: [p for p in j3 if p[1].startswith("repris après une coupure")] or [(False, "coupure en vrai : pas de rapport complet de l'essai long")], 10: [v.assistant_en_vrai()]}


def carte_prise() -> str:
    from fabrique.moteur import carte

    return carte.bramble(datetime.now()) or carte.autre_programme()


def code() -> str:
    """Le commit essayé ; vide si le dépôt a des changements (les passages ne s'additionnent alors pas d'un lancement à l'autre)."""
    propre = not subprocess.run([str(v.GIT), "status", "--porcelain", "--", ".", ":!docs"], cwd=v.DEPOT, capture_output=True, text=True).stdout.strip()
    return v.GIT.exists() and propre and subprocess.run([str(v.GIT), "rev-parse", "HEAD"], cwd=v.DEPOT, capture_output=True, text=True).stdout.strip() or ""


def passages(dire, fois: int) -> tuple[dict[int, list], dict]:
    """Les passages de la partie automatique ; rend (points du dernier passage joué par critère, état : commit, verts de suite, historique)."""
    commit = code()
    try:
        etat = json.loads(ETAT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        etat = {}
    if not commit or etat.get("commit") != commit:
        etat = {"commit": commit, "verts": 0, "passages": []}
    dernier = {int(c): [tuple(x) for x in liste] for c, liste in etat.get("points", {}).items()}  # le dernier passage joué, même d'un lancement d'avant
    while etat["verts"] < fois:
        if raison := carte_prise():
            etat["arret"] = f"{datetime.now():%d/%m %H:%M} carte prise avant le passage : {raison}"
            break
        dire(f"passage {etat['verts'] + 1} sur {fois}…")
        debut, points = datetime.now(), {}
        for criteres, partie in AUTO:
            try:
                res = partie(dire)
            except Exception as e:  # noqa: BLE001 — un passage planté est un passage rouge, avec son rapport
                res = [(False, f"{getattr(partie, '__name__', 'partie')} a planté : {type(e).__name__} : {e}")]
            for p in res:
                for c in criteres:
                    points.setdefault(c, []).append(p)
        rouges = [t for c in points for ok, t in points[c] if not ok]
        if rouges and (raison := carte_prise()):  # la file a attendu la carte : ce passage ne dit rien du code
            etat["arret"] = f"{datetime.now():%d/%m %H:%M} carte prise pendant le passage : {raison}"
            etat["passages"].append({"debut": debut.isoformat(timespec="seconds"), "ecarte": raison, "rouges": rouges[:5]})
            if commit:
                ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
            break
        dernier, etat["points"], etat["arret"] = points, points, ""
        etat["verts"] = 0 if rouges else etat["verts"] + 1
        etat["passages"].append({"debut": debut.isoformat(timespec="seconds"), "minutes": int((datetime.now() - debut).total_seconds() // 60), "vert": not rouges,
                                 "rouges": rouges[:5]})
        if commit:
            ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
        if rouges:
            break
    return dernier, etat


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Recette « fini » de Fabrique (outil de développement)")
    p.add_argument("--fois", type=int, default=10, help="passages verts de suite de la partie automatique (critère 12)")
    p.add_argument("--publier", action="store_true", help=r"la construction pose aussi l'installateur dans <studio>\FABRIQUE\versions")
    p.add_argument("--sans-construction", action="store_true", help="seulement les passages et les preuves (la construction est déjà prouvée)")
    a = p.parse_args(argv)
    debut = datetime.now()
    dire = lambda t: print(f"[recette finale] {t}", flush=True)  # noqa: E731
    avant = v.bramble_avant(dire)
    auto, etat = passages(dire, a.fois)
    construction = [] if a.sans_construction else [(False, f"construction pas jouée : {raison}")] if (raison := carte_prise()) else v.construction(dire, a.publier)
    points = {c: auto.get(c, [] if c not in {x for cs, _ in AUTO for x in cs} else [(False, "partie automatique pas jouée : voir le critère 12")])
              for c in CRITERES}
    for c, liste in en_vrai().items():
        points[c] += liste
    points[1] += v.bramble_points(avant)
    if not construction:
        construction = [(False, "construction et recette d'installation pas jouées (--sans-construction)")]
    jouee = construction[0][1].startswith("construction vérifiée")
    points[8] += [x for x in construction if "sauvegarde" in x[1]] or construction[:1]
    points[11] += [x for x in construction if "console" in x[1] or "contrôles du banc" in x[1] or "captures" in x[1]] if jouee else construction[:1]
    points[12] += construction + [(etat["verts"] >= max(a.fois, 10), f"partie automatique verte {etat['verts']} fois de suite sur {max(a.fois, 10)} (commit {etat['commit'][:7] or 'NON COMMITÉ : ne compte pas'})"
                                   + (f" ; ARRÊT : {etat['arret']}" if etat.get("arret") else "")
                                   + "".join(f" ; passage du {x['debut'][:16]} ROUGE : {' | '.join(x['rouges'])[:400]}" for x in etat["passages"][-1:] if not x["vert"]))]
    verts = [c for c in CRITERES if points[c] and all(ok for ok, _ in points[c])]
    texte = [f"# Recette « fini » de Fabrique — {debut:%d/%m/%Y %H:%M} ({int((datetime.now() - debut).total_seconds() // 60)} min)", "",
             f"**{len(verts)} critère(s) vert(s) sur 12**" + (" — tout est vert." if len(verts) == 12 else f" ; rouges : {', '.join(str(c) for c in CRITERES if c not in verts)}."), ""]
    for c, nom in CRITERES.items():
        texte += [f"## {'✅' if c in verts else '❌'} {c}. {nom}", "", *(f"- {'✅' if ok else '❌'} {t}" for ok, t in points[c]), ""]
    rapport = v.DEPOT / "docs" / "VERIF_FINI_PC.md"
    rapport.write_text("\n".join(texte), encoding="utf-8")
    print("\n".join(texte))
    print(f"rapport : {rapport}")
    return 0 if len(verts) == 12 else 1


if __name__ == "__main__":
    sys.exit(main())
