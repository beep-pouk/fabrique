"""L'interface de la fenêtre (0.12) : entrée par le jeton de la fenêtre seulement et en local, cookie HttpOnly SameSite=Strict, en-tête exigé
pour agir, fichiers servis seulement sous les sessions, images réduites, vidéos par morceaux. Noms factices."""
import pytest
from django.conf import settings
from django.test import Client

from fabrique.noyau import interface, jetons

LOCAL = {"HTTP_HOST": "127.0.0.1:8800"}


@pytest.fixture(autouse=True)
def propre():
    jetons.tirer(settings.DONNEES)


def entrer() -> Client:
    c = Client(**LOCAL)
    r = c.get("/fenetre/entree", {"j": jetons.lire(settings.DONNEES, "fenetre"), "vers": "/#/episode/x"})
    assert r.status_code == 302 and r["Location"] == "/#/episode/x"
    m = r.cookies[interface.COOKIE]
    assert m["httponly"] and m["samesite"] == "Strict"
    return c


def test_entree_refusee_sans_le_jeton_de_la_fenetre_ou_hors_local():
    assert Client(**LOCAL).get("/fenetre/entree", {"j": jetons.lire(settings.DONNEES, "claude")}).status_code == 403
    assert Client(HTTP_HOST="pc-factice.tailnet-factice.ts.net").get("/fenetre/entree", {"j": jetons.lire(settings.DONNEES, "fenetre")}).status_code == 403
    r = Client(**LOCAL).get("/fenetre/entree", {"j": jetons.lire(settings.DONNEES, "fenetre"), "vers": "//site-factice.example/"})
    assert r["Location"] == "/"


def test_le_cookie_ouvre_la_lecture_et_l_ecriture_seulement_avec_l_en_tete():
    c = entrer()
    assert c.get("/api/sante").json()["appelant"] == "fenetre"
    assert c.post("/api/sauvegardes").status_code == 401
    assert c.post("/api/telephone/code", HTTP_X_FABRIQUE="fenetre").status_code == 200
    assert Client(**LOCAL).get("/api/sante").status_code == 401
    jetons.tirer(settings.DONNEES)  # noyau relancé : l'ancien cookie ne vaut plus rien
    assert c.get("/api/sante").status_code == 401


def test_fichiers_bornes_aux_sessions_images_reduites_et_videos_par_morceaux(tmp_path):
    from PIL import Image

    c = entrer()
    dossier = settings.SESSIONS / "session_factice"
    dossier.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1920, 1080), "navy").save(dossier / "plan_002.png")
    (dossier / "essai.mp4").write_bytes(bytes(range(256)) * 10)
    (tmp_path / "secret.txt").write_text("rien", encoding="utf-8")
    assert c.get("/api/fichier", {"chemin": str(tmp_path / "secret.txt")}).status_code == 403
    assert c.get("/api/fichier", {"chemin": str(dossier / ".." / ".." / "donnees" / "jeton_claude")}).status_code == 403
    r = c.get("/api/fichier", {"chemin": str(dossier / "plan_002.png"), "largeur": 500})
    assert r.status_code == 200 and r["Content-Type"] == "image/jpeg"
    with Image.open(__import__("io").BytesIO(b"".join(r.streaming_content))) as im:
        assert im.size == (640, 360)
    r = c.get("/api/fichier", {"chemin": str(dossier / "essai.mp4")}, HTTP_RANGE="bytes=10-19")
    assert r.status_code == 206 and r["Content-Range"] == "bytes 10-19/2560" and b"".join(r.streaming_content) == bytes(range(10, 20))
    assert c.get("/api/fichier", {"chemin": str(dossier / "essai.mp4")}, HTTP_RANGE="bytes=-5").status_code == 206


def test_page_de_l_interface_ou_message_clair(monkeypatch, tmp_path):
    monkeypatch.setattr(interface, "web", lambda: tmp_path)
    assert Client(**LOCAL).get("/").status_code == 503
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>Fabrique</title>", encoding="utf-8")
    (tmp_path / "assets" / "app-1.js").write_text("1", encoding="utf-8")
    assert b"Fabrique" in b"".join(Client(**LOCAL).get("/").streaming_content)
    r = Client(**LOCAL).get("/assets/app-1.js")
    assert r.status_code == 200 and "immutable" in r["Cache-Control"]
    assert b"Fabrique" in b"".join(Client(**LOCAL).get("/assets/absent.js").streaming_content)
