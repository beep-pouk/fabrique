"""Recette d'un jalon : python outils_dev\\verifier.py --jalon J1 → docs\\VERIF_J1_PC.md (jamais suivi par git : il cite le PC), relu par la
supervision. Code de retour 0 si aucun point rouge.
J1 (plan technique § 7.1) : la construction vérifiée (suite verte, programme assemblé, installateur signé) et la recette d'installation dans le
bac à sable (installée à côté de Bramble Studio ; fenêtre ouverte, fermée, relancée ; sauvegarde puis restauration ; mise à jour jouée),
pendant que l'empreinte du dossier « Bramble Studio » et de « DONNEES » est prise avant et après : identique. Bramble Studio qui tourne réécrit
lui-même son état, sa base et ses journaux : ces fichiers-là sont montrés à part. Outil de développement : jamais livré."""
import argparse
import fnmatch
import json
import subprocess
import sys
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


def j1(dire) -> list[tuple[bool, str]]:
    import construire

    studio = garde.studio_bramble() or DEPOT.parents[1]
    lieux = {"Bramble Studio": studio / "Bramble Studio", "DONNEES": studio / "DONNEES"}
    dire(f"empreinte avant : {', '.join(str(d) for d in lieux.values())}")
    avant, tourne = {n: banc.empreinte(d) for n, d in lieux.items()}, bramble_tourne(studio)
    journal = SORTIE / f"construire_{construire.version()}.log"
    journal.parent.mkdir(parents=True, exist_ok=True)
    dire(f"construction et recette d'installation (journal : {journal})…")
    with open(journal, "w", encoding="utf-8") as sortie:
        r = subprocess.run([sys.executable, str(DEPOT / "outils_dev" / "construire.py")], cwd=DEPOT, stdout=sortie, stderr=subprocess.STDOUT,
                           env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    apres, tourne = {n: banc.empreinte(d) for n, d in lieux.items()}, tourne and bramble_tourne(studio)
    points = [(r.returncode == 0, f"construction vérifiée (suite de tests verte, programme assemblé, installateur signé, recette d'installation) — {journal.name}")]
    try:
        preuve = json.loads((SORTIE / "recette_installation.json").read_text(encoding="utf-8"))
        bonne = r.returncode == 0 and preuve["arbres"] == construire.arbres() and preuve["version"] == construire.version()
        points += [(bonne, f"recette d'installation ({preuve['date']}) : {p}") for p in preuve["points"]]
    except (OSError, ValueError, KeyError):
        points.append((False, "recette d'installation : pas de preuve écrite"))
    d = banc.differences(avant["Bramble Studio"], apres["Bramble Studio"])
    points.append((not d, "dossier « Bramble Studio » identique avant et après" + ("" if not d else " : " + ", ".join(d[:10]))))
    d = banc.differences(avant["DONNEES"], apres["DONNEES"])
    siens = [x for x in d if tourne and any(fnmatch.fnmatch(x[2:], m) for m in VIVANTS)]
    autres = [x for x in d if x not in siens]
    points.append((not autres, "dossier « DONNEES » identique avant et après" + (f" ({len(siens)} fichier(s) réécrits par Bramble Studio lui-même, qui tourne : "
                                                                                    f"{', '.join(siens)})" if siens else "") + ("" if not autres else " — AUTRES : " + ", ".join(autres[:10]))))
    captures = sorted(f.name for f in (DEPOT / "fabrique" / "tests" / "captures").glob("*.png"))
    points.append((len(captures) >= 5, f"captures de référence de la fenêtre comparées par la suite (100 %, 125 %, 150 %, 2560 × 1440) : {', '.join(captures)}"))
    return points


JALONS = {"J1": j1}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Recette d'un jalon de Fabrique (outil de développement)")
    p.add_argument("--jalon", required=True, choices=list(JALONS))
    a = p.parse_args(argv)
    debut = datetime.now()
    points = JALONS[a.jalon](lambda t: print(f"[verifier] {t}", flush=True))
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
