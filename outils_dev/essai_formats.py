"""Essais en vrai des formats par plan (J8 : F4 voix off + images, F3 créée seule ; J12 : F1 en 10 langues ; plan § 7.1 ; de nuit, carte libre : la file de Fabrique
attend d'elle-même un rendu de Bramble Studio). Dans la session « Essais » de la racine de travail des essais réels
(OUTILS\\fabrique_construction\\egalite\\FABRIQUE, où Bramble Studio est importé : son univers et ses réglages y sont copiés), jamais publiés, en
vrais processus (noyau, file, exécuteur détaché), FABRIQUE_REEL=1 et le réglage « simulation » à non. Pour chaque « <recette> <script.json> »
donné, dans l'ordre : « moteur » (la porte de Claude), suivi jusqu'à la fin, puis la vidéo finale de chaque langue mesurée (durée, cadre, son),
le contrôle lu (défauts minutés, aucun « forte » attendu), les chronos par étape. Refus de partir si un essai d'avant est encore dans la file de
la session Essais (jamais deux essais en même temps, jamais une tâche d'un autre annulée ; le même essai coupé par une extinction : annulé puis refait). Rapport : ESSAI_FORMATS.json (et .log), toujours
écrit (erreur comprise), avec le commit essayé. Outil de développement : jamais livré.
python outils_dev\\essai_formats.py F4 <script.json> [F3s <script.json> …]"""
import json
import re
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path

import essai_long as el  # même racine de travail, même préparation de la session Essais, même port tiré au hasard

JOURNAL = el.SORTIE / "ESSAI_FORMATS.log"
RAPPORT = el.SORTIE / "ESSAI_FORMATS.json"
DELAI_S = 8 * 3600  # une vidéo


def dire(texte: str):
    ligne = f"{datetime.now():%d/%m %H:%M:%S} {texte}"
    print(ligne, flush=True)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(ligne + "\n")


def lire_video(essais, vid: str) -> dict:
    """Ce que la vidéo a donné : par langue, la vidéo finale mesurée et le contrôle ; les chronos par étape ; les outils (aucun faux attendu)."""
    with closing(sqlite3.connect(f"file:{essais / 'session.sqlite3'}?mode=ro", uri=True)) as c:
        chronos = {e: round(s or 0) for e, s in c.execute("SELECT etape, SUM(secondes) FROM session_morceau WHERE video_id = ? GROUP BY etape ORDER BY MIN(ordre)", (vid,))}
        outils = sorted({o for (o,) in c.execute("SELECT outil FROM session_morceau WHERE video_id = ?", (vid,))})
    langues = {}
    for rapport in sorted((essais / "videos" / vid).glob("*/revue/video/rapport.json")):
        rap = json.loads(rapport.read_text(encoding="utf-8"))
        langues[rapport.parents[2].name] = {"video": rap.get("video"), "duree_s": rap.get("duree_s"), "cadre": f"{rap.get('largeur')} × {rap.get('hauteur')}",
                                            "son": rap.get("son"), "defauts": rap["defauts"], "forte": sum(d["gravite"] == "forte" for d in rap["defauts"])}
    return {"chronos_s": chronos, "outils": outils, "langues": langues}


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or len(args) % 2:
        print(__doc__.splitlines()[-1])
        return 2
    from fabrique.fenetre.client import Client

    RAPPORT.unlink(missing_ok=True)  # jamais le rapport d'un essai d'avant
    rapport = {"debut": datetime.now().isoformat(timespec="seconds"), "commit": el.git("rev-parse", "HEAD"),
               "code_modifie": bool(el.git("status", "--porcelain", "fabrique")), "videos": []}
    noyau = None
    try:
        essais = el.preparer()
        claude = Client("claude", port=el.PORT, donnees=el.RACINE / "donnees")
        noyau = subprocess.Popen([sys.executable, "-m", "fabrique", "noyau"], cwd=el.DEPOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        el.banc.attendre(claude.repond, 60, "le noyau répond")
        assert claude.appeler("sante")["mode"] == "réel", "la racine de travail est restée en simulation"
        actives = [t for t in claude.appeler("file") if t["session"] == "Essais" and t["etat"] in ("attente", "en_cours", "pause", "erreur")]
        titres = {(d := json.loads(Path(s).read_text(encoding="utf-8"))).get("titre") or d.get("title") for s in args[1::2]}  # F1 : « title »
        for t in [t for t in actives if t["titre"] in titres]:  # le même essai coupé (PC éteint) : annulé puis refait ; un autre essai : refus
            dire(f"tâche {t['id']} du même essai coupé : {Client('fenetre', port=el.PORT, donnees=el.RACINE / 'donnees').appeler('agir_file', id=t['id'], action='annuler')['message']}")
            actives.remove(t)
        if actives := [t for t in actives if t["etat"] != "erreur"]:
            raise AssertionError(f"un essai d'avant est encore dans la file (tâche {actives[0]['id']}, « {actives[0]['titre']} ») : rien lancé")
        for recette, script in zip(args[::2], args[1::2]):
            r = subprocess.run([sys.executable, "-m", "fabrique", "moteur", recette, script], cwd=el.DEPOT, capture_output=True, text=True, encoding="utf-8", timeout=300)
            dire(f"moteur {recette} : {r.stdout.strip() or r.stderr.strip()}")
            m = re.search(r"tâche (\d+), vidéo (\w+)", r.stdout)
            if r.returncode or not m:
                rapport["videos"].append({"recette": recette, "script": script, "erreur": (r.stdout + r.stderr).strip()[-500:]})
                continue
            tid, vid, t0, vu = int(m.group(1)), m.group(2), time.monotonic(), ""
            while time.monotonic() - t0 < DELAI_S:
                t = next(t for t in claude.appeler("file") if t["id"] == tid)
                if (etat := f"{t['etat']} {t['progression']} {t['raison']}") != vu:
                    dire(etat)
                    vu = etat
                if t["etat"] in ("finie", "erreur", "annulee"):
                    break
                time.sleep(20)
            fait = {"recette": recette, "script": script, "video": vid, "etat": t["etat"], "raison": t["raison"], "horloge_s": round(time.monotonic() - t0),
                    **lire_video(essais, vid)}
            rapport["videos"].append(fait)
            dire(f"{recette} : {t['etat']} en {fait['horloge_s'] / 60:.0f} min ; " + " ; ".join(
                f"{l} : {x['duree_s'] or 0:.0f} s, {x['cadre']}, {len(x['defauts'])} défaut(s) dont {x['forte']} bloquant(s)" for l, x in fait["langues"].items()))
    except Exception as e:  # noqa: BLE001 — le rapport dit toujours ce qui s'est passé
        rapport["erreur"] = f"{type(e).__name__} : {e}"
        dire(f"ERREUR {rapport['erreur']}")
    finally:
        if noyau:
            try:
                Client("fenetre", port=el.PORT, donnees=el.RACINE / "donnees").appeler("arreter")
                noyau.wait(60)
            except Exception:  # noqa: BLE001
                noyau.kill()
        try:  # la carte rendue : plus rien des nôtres dessus (ComfyUI arrêté après chaque étape)
            m = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True,
                               timeout=30, creationflags=subprocess.CREATE_NO_WINDOW).stdout.split(",")
            rapport["carte_apres"] = {"memoire_mio": int(m[0]), "totale_mio": int(m[1])}
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            rapport["carte_apres"] = None
        rapport["fin"] = datetime.now().isoformat(timespec="seconds")
        RAPPORT.write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = not rapport.get("erreur") and all(v.get("etat") == "finie" and v["langues"] and not any(x["forte"] for x in v["langues"].values()) for v in rapport["videos"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
