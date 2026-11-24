"""La fenêtre WebView2 (0.12) sans l'ouvrir : adresse d'entrée relue à chaque fois (noyau relancé), seule porte de la page vers le PC
(liens http(s) seulement, entrée sur un chemin de l'interface), notifications tirées du flux du noyau, sonnette. Noms factices."""
import socket
import threading
from urllib.parse import urlsplit

from django.conf import settings
from django.test import Client

from fabrique.fenetre import main
from fabrique.noyau import jetons


def test_entree_relue_et_acceptee_par_le_noyau(monkeypatch):
    jetons.tirer(settings.DONNEES)
    adresse = main.entree("/#/episode/x")
    assert jetons.lire(settings.DONNEES, "fenetre") in adresse and adresse.endswith("vers=%2F%23%2Fepisode%2Fx")
    u = urlsplit(adresse)
    r = Client(HTTP_HOST="127.0.0.1").get(f"{u.path}?{u.query}")
    assert r.status_code == 302 and r["Location"] == "/#/episode/x"
    jetons.tirer(settings.DONNEES)
    assert main.entree() != adresse


def test_la_page_ne_peut_ouvrir_que_des_liens_web_et_rentrer_chez_elle(monkeypatch):
    ouverts, chargees = [], []
    monkeypatch.setattr(main.webbrowser, "open", ouverts.append)
    api = main.Api()
    assert not api.ouvrir("file:///C:/Windows/System32/cmd.exe") and not api.ouvrir("javascript:alert(1)")
    assert api.ouvrir("https://site-factice.example/video") and ouverts == ["https://site-factice.example/video"]
    api.vue = type("Vue", (), {"load_url": lambda self, u: chargees.append(u)})()
    api.entrer("//site-factice.example/")
    api.entrer("/#/file")
    assert len(chargees) == 1 and chargees[0].endswith("vers=%2F%23%2Ffile")


def test_notifications_du_flux():
    assert main.notification("sauvegarde", {"etat": "faite", "fichier": "sauvegarde_factice.zip"}) == ("Sauvegarde faite", "sauvegarde_factice.zip")
    assert main.notification("sauvegarde", {"etat": "erreur", "message": "disque plein"})[0] == "La sauvegarde a raté"
    assert main.notification("alerte", {"titre": "Titre factice", "message": "texte"}) == ("Titre factice", "texte")
    assert main.notification("battement", {}) is None


def test_sonnette():
    recus, fini = [], threading.Event()
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    threading.Thread(target=main.ecouter, args=(s, lambda m: (recus.append(m), fini.set())), daemon=True).start()
    with socket.create_connection(s.getsockname(), timeout=2) as c:
        c.sendall(b"montrer\n")
    assert fini.wait(5) and recus == ["montrer"]
    s.close()
