"""L'interface de la fenêtre (0.12) : entrée par le jeton de la fenêtre seulement et en local, cookie HttpOnly SameSite=Strict, en-tête exigé
pour agir, fichiers servis seulement sous les sessions, images réduites, vidéos par morceaux. Noms factices."""
from pathlib import Path

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
    r = Client(**LOCAL).get("/fenetre/entree", {"j": jetons.lire(settings.DONNEES, "claude"), "vers": "/#/x</script>"})
    assert r.status_code == 403 and b"pywebview.api.entrer" in r.content and b"</script>\"" not in r.content  # la fenêtre redemande l'entrée, sans impasse
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


def wav(f, secondes: float, flottant: bool = True):
    """Un .wav muet ; flottant : comme les voix de Bramble Studio (le module wave de Python le refuse)."""
    import struct

    debit, largeur = 24000, 4 if flottant else 2
    donnees = bytes(int(debit * secondes) * largeur)
    fmt = struct.pack("<HHIIHH", 3 if flottant else 1, 1, debit, debit * largeur, largeur, largeur * 8)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"RIFF" + struct.pack("<I", 36 + len(donnees)) + b"WAVEfmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(donnees)) + donnees)


def test_rendus_de_bramble_images_videos_et_voix_par_scene(tmp_path, monkeypatch):
    from fabrique.session import bramble

    monkeypatch.setattr(bramble, "rendus_bramble", lambda: tmp_path)
    base, autre = tmp_path / "2026-01-01-x1e01", tmp_path / "2026-01-01-x1e01.zz"
    (base / "images").mkdir(parents=True)
    (base / "images" / "plan_002.png").write_bytes(b"png")
    (base / "final").mkdir()
    (base / "final" / "film.mp4").write_bytes(b"mp4")
    wav(base / "voix" / "s001.wav", 2.5)
    wav(base / "voix" / "s002.wav", 1.0, flottant=False)
    wav(autre / "voix" / "s001.wav", 3.0)
    (tmp_path / "2026-01-01-x1e011").mkdir()  # un autre épisode au code voisin : jamais mêlé
    wav(tmp_path / "2026-01-01-x1e011" / "voix" / "s001.wav", 9.0)
    r = bramble.rendus("x1e01")
    assert list(r["images"]) == [2] and [v["langue"] for v in r["videos"]] == ["en"] and r["langues"] == ["en", "zz"]
    assert r["durees"] == {1: 2.5, 2: 1.0} and r["voix"][1].endswith("s001.wav")
    assert bramble.rendus("x1e01", "zz")["durees"] == {1: 3.0}
    (base / "voix" / "abime.wav").write_bytes(b"RIFF")
    assert bramble.duree_wav(base / "voix" / "abime.wav") == 0.0
    coupe = base / "voix" / "coupe.wav"
    coupe.write_bytes((base / "voix" / "s001.wav").read_bytes()[:44 + 24000 * 4])  # copie coupée à 1 s : l'en-tête dit encore 2,5 s
    assert bramble.duree_wav(coupe) == 1.0


def test_personnage_repris_de_bramble_ses_images_et_sa_voix(tmp_path):
    import json

    from fabrique.session import univers

    d = tmp_path / "univers" / "personnages" / "ami_deux"
    (d / "refs").mkdir(parents=True)
    for f in ("reference.png", "refs/a.jpg", "refs/b.jpg"):
        (d / f).write_bytes(b"img")
    (d / "catalogue.json").write_text(json.dumps({"images": [{"fichier": "refs/a.jpg", "vue": "de face", "statut": "garde"},
                                                             {"fichier": "refs/b.jpg", "vue": "rejetée", "statut": "rejete"}]}), encoding="utf-8")
    images = univers.images_du_dossier(tmp_path, "Ami_Deux")
    assert [(Path(i["chemin"]).name, i["validee"]) for i in images] == [("reference.png", True), ("a.jpg", False)]
    assert univers.images_du_dossier(tmp_path, "Inconnu") == []
    langue = lambda code, ref="": type("L", (), {"code": code, "reglages_voix": {"ref": ref} if ref else {}})()  # noqa: E731
    wav(tmp_path / "univers" / "voix" / "ami_deux_exemple.wav", 1)
    wav(tmp_path / "univers" / "voix_langues" / "zz" / "zz.wav", 1)
    v = univers.voix(tmp_path, "Ami_Deux", [langue("xx"), langue("zz", "univers/voix_langues/zz/zz.wav"), langue("yy", "absent.wav")])
    assert [x["langue"] for x in v] == ["xx", "zz"] and univers.voix(tmp_path, "Muet", [langue("xx")]) == []


def test_ce_que_bramble_fabrique_en_ce_moment(tmp_path, monkeypatch):
    import json
    import os
    from datetime import datetime, timedelta

    from fabrique import garde
    from fabrique.session import bramble

    monkeypatch.setattr(garde, "studio_bramble", lambda: tmp_path)
    assert bramble.en_cours() is None
    (tmp_path / "DONNEES").mkdir()
    images = tmp_path / "PROJET" / "rendus" / "2026-01-01-x1e01.zz" / "images"
    images.mkdir(parents=True)
    for n in ("007", "009"):
        (images / f"plan_{n}.png").write_bytes(b"png")
    os.utime(images / "plan_007.png", (1, 1))
    etat = lambda heure, ligne: (tmp_path / "DONNEES" / "etat.json").write_text(json.dumps(  # noqa: E731
        {"heure": heure, "episode": {"nom": "2026-01-01-x1e01.zz", "etape": "anim", "reste_min": 30, "total_min": 120, "plans": 40, "anim": 9,
                                     "journal_derniere": ligne}}), encoding="utf-8")
    maintenant = datetime(2026, 1, 1, 22, 0)
    etat("2026-01-01T21:55", "calques : plan_007 fond")
    e = bramble.en_cours(maintenant)
    assert (e["code"], e["langue"], e["etape"], e["reste_min"], e["fait"], e["tout"]) == ("x1e01", "zz", "anim", 120, 9, 40)  # le reste de tout
    assert e["image"].endswith("plan_007.png")
    etat("2026-01-01T21:55", "montage")
    assert bramble.en_cours(maintenant)["image"].endswith("plan_009.png")  # la plus récente
    assert bramble.en_cours(maintenant + timedelta(minutes=20)) is None  # état vieux : Bramble est arrêté


def test_animatique_images_fixes_voix_musique_reperes_et_notes(tmp_path, monkeypatch):
    """Étape 3 : l'épisode en images fixes par le montage de F1 (vrai ffmpeg), repères dans l'ordre des scènes (une réplique de Bramble coupe un
    plan en deux passages), notes à la seconde ; une voix qui manque : refus en clair."""
    import json
    import subprocess
    from types import SimpleNamespace

    from fabrique.garde import Refus
    from fabrique.moteur import animatique, faux
    from fabrique.session import bramble

    monkeypatch.setattr(bramble, "rendus_bramble", lambda: tmp_path)
    base = tmp_path / "2026-01-01-x1e01"
    (base / "images").mkdir(parents=True)
    subprocess.run([faux.programme("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x5c8048:s=320x180", "-frames:v", "1",
                    str(base / "images" / "plan_001.png")], check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for i, d in ((1, 1.0), (2, 0.5), (3, 0.5)):
        wav(base / "voix" / f"s{i:03d}.wav", d)
    wav(base / "musique.wav", 4.0)
    s = SimpleNamespace(id="sx", dossier="anim_factice")
    (settings.SESSIONS / s.dossier / "reglages").mkdir(parents=True)
    cfg = {"pause_apres_phrase_s": 0.5, "fondu_s": 0.2, "musique_volume_db": -20, "sortie": {"largeur": 1920, "hauteur": 1080, "fps": 12, "lufs": -14}}
    (settings.SESSIONS / s.dossier / "reglages" / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    contenu = {"title": "Essai", "scenes": [{"id": 1, "image": "une clairière"}, {"id": 2, "bramble": "pose_factice"}, {"id": 3, "image": "same"}]}
    vus = []
    video = animatique.faire(s, "x1e01", "en", contenu, avancer=lambda f, t: vus.append((f, t)))
    e = animatique.etat(s, "x1e01", "en")
    assert e["etat"] == "faite" and e["video"] == str(video) and vus[-1] == (3, 4)
    assert e["plans"] == [{"n": 1, "debut": 0.0, "duree": 1.5}, {"n": 2, "debut": 1.5, "duree": 1.0}, {"n": 1, "debut": 2.5, "duree": 1.0}]
    assert abs(e["fin"] - 3.5) < 0.2 and not (video.parent / "_travail").exists()
    animatique.noter_a(s, "x1e01", 2.04, "  le chat   arrive trop tôt ", "en")
    animatique.noter_a(s, "x1e01", 0.5, "début", "zz")
    assert [(n["t"], n["texte"]) for n in animatique.etat(s, "x1e01", "en")["notes"]] == [(0.5, "début"), (2.0, "le chat arrive trop tôt")]
    premiere = animatique.lire_notes(s, "x1e01")[0]["id"]
    assert [n["texte"] for n in animatique.retirer_note(s, "x1e01", premiere)] == ["le chat arrive trop tôt"]
    with pytest.raises(Refus, match="déjà retirée"):  # un double clic ne retire pas la voisine
        animatique.retirer_note(s, "x1e01", premiere)
    with pytest.raises(Refus, match="vide"):
        animatique.noter_a(s, "x1e01", 1, "   ", "en")
    animatique._fichier_notes(s, "x1e01").write_text("[{,", encoding="utf-8")  # retouché à la main et abîmé : jamais écrasé
    with pytest.raises(Refus, match="illisibles"):
        animatique.noter_a(s, "x1e01", 1, "encore", "en")
    with pytest.raises(Refus, match="script inconnu"):
        animatique.contenu_du_script(s, "s1e01.x\\..\\..\\y")
    with pytest.raises(Refus, match="langue"):
        animatique.verifier_langue("../x")
    (base / "voix" / "s003.wav").unlink()
    with pytest.raises(Refus, match="voix en en ne sont pas encore faites pour 1 scène"):
        animatique.faire(s, "x1e01", "en", contenu)


def test_essai_d_animation_depose_puis_liste(tmp_path):
    """Étape 2 : Claude dépose la scène animée et celle de Bramble ; copiées dans la session, listées pour l'écran Épisode ; demande mal formée refusée."""
    from types import SimpleNamespace

    from fabrique.moteur import comparaison

    s = SimpleNamespace(id="sx", dossier="comparaison_factice")
    (tmp_path / "b.mp4").write_bytes(b"b")
    (tmp_path / "f.mp4").write_bytes(b"f")
    demande = {"titre": "Scène factice", "bramble": str(tmp_path / "b.mp4"), "fabrique": str(tmp_path / "f.mp4"), "plans": [{"debut": 0, "duree": 4.5}, {"debut": 4.5, "duree": 6}]}
    assert "2 plans" in comparaison.deposer(s, "x1e01", demande)
    (e,) = comparaison.lister(s, "x1e01")
    assert e["titre"] == "Scène factice" and e["duree"] == 10.5 and Path(e["fabrique"]).read_bytes() == b"f" and Path(e["bramble"]).parent.parent.name == "x1e01"
    for mauvais in ({**demande, "fabrique": str(tmp_path / "f.txt")}, {**demande, "plans": []}, {**demande, "plans": [{"debut": -1, "duree": 2}]}, {**demande, "titre": ""}):
        with pytest.raises(ValueError):
            comparaison.deposer(s, "x1e01", mauvais)
