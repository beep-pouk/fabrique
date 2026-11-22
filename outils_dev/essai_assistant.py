"""Essai en vrai de l'assistant (J11, plan § 7.1 et § 8.3 ; de nuit, carte libre) : gpt-oss par llama-server, trois demandes d'essai écrites,
sans accord (lecture seule), sur une racine temporaire en mode réel. Attendu pour chacune : une réponse finie, l'estimation appelée, aucun
brouillon. llama-server arrêté à la fin (carte rendue). Rapport : OUTILS\\fabrique_construction\\egalite\\ESSAI_ASSISTANT.json, toujours écrit,
lu par verifier.py --jalon J11. Outil de développement : jamais livré.
python outils_dev\\essai_assistant.py"""
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

DEPOT = Path(__file__).resolve().parents[1]
RAPPORT = DEPOT.parent / "fabrique_construction" / "egalite" / "ESSAI_ASSISTANT.json"
DEMANDES = ["Combien de temps et de carte pour trois vidéos F1 de plus ?", "Quelles sessions ai-je, et que fabriquer ensuite ?",
            "Prépare-moi un plan pour deux chansons F5 ce mois-ci."]


def main() -> int:
    os.environ.update({"FABRIQUE_RACINE": tempfile.mkdtemp(prefix="fabrique_assistant_"), "FABRIQUE_REEL": "1", "DJANGO_SETTINGS_MODULE": "fabrique.settings"})
    sys.path.insert(0, str(DEPOT))
    import django

    django.setup()
    from fabrique.noyau import assistant, bases
    from fabrique.noyau.models import Parametre

    bases.migrer()
    Parametre.ecrire("simulation", "non")
    essais, ok = [], True
    try:
        for d in DEMANDES:
            t = time.monotonic()
            try:
                r = assistant.demander(d, [], accord=False)
                bon = not r["message"].startswith("Je n'ai pas fini") and "estimer" in [o["outil"] for o in r["outils"]] and not r["brouillons"]
                essais.append({"demande": d, "secondes": round(time.monotonic() - t), "message": r["message"][:600], "outils": [o["outil"] for o in r["outils"]], "ok": bon})
            except Exception as e:  # noqa: BLE001 — écrit dans le rapport
                bon = False
                essais.append({"demande": d, "secondes": round(time.monotonic() - t), "erreur": f"{type(e).__name__} : {e}", "ok": False})
            ok = ok and bon
    finally:
        assistant.ranger(True)
    resume = " ; ".join(f"« {e['demande']} » {e['secondes']} s {'ok' if e['ok'] else 'RATÉ'}" for e in essais)
    RAPPORT.write_text(json.dumps({"date": f"{datetime.now():%d/%m/%Y %H:%M}", "ok": ok, "resume": resume, "essais": essais}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    print(resume)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
