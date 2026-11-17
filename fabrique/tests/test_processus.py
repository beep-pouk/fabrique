"""Les processus pour de vrai (développement, dossier temporaire, port libre) : noyau à instance unique, « commande » de Claude, « libre »,
« migrer », « arreter »."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from fabrique.fenetre.client import Client, ouvert

DEPOT = Path(__file__).parents[2]


def lancer(env, *args, **options):
    return subprocess.run([sys.executable, "-m", "fabrique", *args], cwd=DEPOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120, **options)


def test_noyau_commande_arret(tmp_path, libre_port):
    env = {**os.environ, "FABRIQUE_RACINE": str(tmp_path / "FABRIQUE"), "FABRIQUE_PORT": str(libre_port), "PYTHONIOENCODING": "utf-8"}
    noyau = subprocess.Popen([sys.executable, "-m", "fabrique", "noyau"], cwd=DEPOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        client = Client(port=libre_port, donnees=tmp_path / "FABRIQUE" / "donnees")
        fin = time.monotonic() + 60
        while not client.repond() and time.monotonic() < fin:
            time.sleep(0.25)
        assert client.appeler("sante")["appelant"] == "fenetre"
        assert "tourne déjà" in lancer(env, "noyau").stdout  # instance unique
        r = lancer(env, "commande", "sessions")
        assert r.returncode == 0 and [s["nom"] for s in json.loads(r.stdout)] == ["Essais"]
        assert lancer(env, "commande", "sauvegarder").returncode == 2  # Claude ne lance rien à J1
        (tmp_path / "script.json").write_text("{}", encoding="utf-8")
        r = lancer(env, "commande", "script", "inconnue", "s1e01", tmp_path / "script.json")
        assert r.returncode == 1 and "session inconnue" in r.stdout, r.stdout  # Claude écrit un script par l'API, droits compris
        assert lancer(env, "libre").returncode == 0
        assert lancer(env, "moteur").returncode == 2
        r = lancer(env, "arreter")
        assert r.returncode == 0 and not ouvert(libre_port), r.stdout
        assert noyau.wait(10) == 0
        r = lancer(env, "migrer")
        assert r.returncode == 0 and "_old" in r.stdout
        assert (tmp_path / "FABRIQUE" / "donnees" / "etat.json").is_file() and (tmp_path / "FABRIQUE" / "sessions" / "essais" / "session.sqlite3").is_file()
    finally:
        noyau.kill()
