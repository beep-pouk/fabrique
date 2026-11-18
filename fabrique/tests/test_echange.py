"""Exporter puis importer une session à l'identique (J5) ; un fichier abîmé, trafiqué ou qui sort de la session : rien d'importé. Noms factices."""
import json
import sqlite3
import zipfile
from contextlib import closing

import pytest
from django.conf import settings

from fabrique.garde import Refus
from fabrique.noyau import bases, echange, routeur
from fabrique.noyau.models import Session
from fabrique.session import models as m


def contenu(s: Session) -> dict:
    """Chaque table de la base de la session (sauf la fiche, qui porte l'identifiant de la session), lignes triées."""
    with closing(sqlite3.connect(routeur.chemin(s))) as c:
        tables = [t for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'session_%' AND name != 'session_fiche'")]
        return {t: sorted(map(repr, c.execute(f"SELECT * FROM {t}"))) for t in tables}


@pytest.fixture
def remplie(request):
    s = bases.creer(f"Exportée {request.node.name}")
    with routeur.session(s):
        m.Langue.objects.create(code="xx", nom="Langue factice")
        m.Script.objects.create(code="s1e01", titre="Une histoire factice", langue="xx", statut="scenario")
        m.Video.objects.create(titre="Le petit renard", nom="2099-12-01-s1e01", script={}, recette={})
    d = settings.SESSIONS / s.dossier
    (d / "univers" / "personnages").mkdir(parents=True)
    (d / "univers" / "univers.json").write_bytes(json.dumps({"nom": "Univers factice"}).encode())
    (d / "univers" / "personnages" / "renard é.png").write_bytes(b"\x89PNG faux " * 100)
    (d / "videos" / "v1" / "final").mkdir(parents=True)
    (d / "videos" / "v1" / "final" / "v.mp4").write_bytes(b"video factice")
    (d / "_old").mkdir()
    (d / "_old" / "vieux.txt").write_bytes(b"jamais exporte")
    return s


def test_exporter_puis_importer_a_l_identique(remplie):
    z = echange.exporter(remplie)
    with zipfile.ZipFile(z) as f:
        noms = set(f.namelist())
    assert noms == {"manifeste.json", "session.sqlite3", "univers/univers.json", "univers/personnages/renard é.png"}  # ni vidéos, ni _old
    s = echange.importer(z, nom=f"Réimportée {remplie.nom}")
    assert s.id != remplie.id and s.dossier != remplie.dossier and not s.essais
    assert contenu(s) == contenu(remplie)
    a, b = echange.fichiers(remplie, False), echange.fichiers(s, False)
    assert set(a) == set(b) and all(echange.empreinte(a[k]) == echange.empreinte(b[k]) for k in a)
    with routeur.session(s):
        assert list(m.Fiche.objects.values_list("id", "nom")) == [(s.id, s.nom)]
    with pytest.raises(Refus, match="s'appelle déjà"):
        echange.importer(z, nom=s.nom)
    (settings.SESSIONS / remplie.dossier / "videos" / "v1" / "commun" / "images" / "s1").mkdir(parents=True)
    (settings.SESSIONS / remplie.dossier / "videos" / "v1" / "commun" / "images" / "s1" / "plan.png").write_bytes(b"piece intermediaire")
    avec = echange.exporter(remplie, videos=True)
    with zipfile.ZipFile(avec) as f:
        assert "videos/v1/final/v.mp4" in f.namelist() and not [n for n in f.namelist() if "images" in n]  # les finales, jamais les pièces


def test_un_fichier_trafique_n_importe_rien(remplie, tmp_path):
    z = echange.exporter(remplie)
    avant = Session.objects.count()

    def refait(nom, change):
        sortie = tmp_path / nom
        with zipfile.ZipFile(z) as src, zipfile.ZipFile(sortie, "w") as dst:
            for i in src.infolist():
                dst.writestr(i, change(i.filename, src.read(i.filename)))
        return sortie

    trafique = refait("trafique.fabrique", lambda n, d: b"autre chose" if n == "univers/univers.json" else d)
    with pytest.raises(Refus, match="empreinte fausse"):
        echange.importer(trafique, nom="Trafiquée")
    assert Session.objects.count() == avant and not (settings.SESSIONS / "trafiquee").exists()
    assert any(p.name.startswith(".import_") for p in (settings.DONNEES / "_corbeille").iterdir())  # le dossier à moitié posé, rangé
    sortant = tmp_path / "sortant.fabrique"
    with zipfile.ZipFile(z) as src, zipfile.ZipFile(sortant, "w") as dst:
        for i in src.infolist():
            dst.writestr(i, src.read(i.filename))
        dst.writestr("../hors.txt", b"x")
    with pytest.raises(Refus, match="chemins inattendus"):
        echange.importer(sortant, nom="Sortante")
    (tmp_path / "abime.fabrique").write_bytes(b"pas un zip")
    with pytest.raises(Refus, match="illisible"):
        echange.importer(tmp_path / "abime.fabrique", nom="Abîmée")
    assert Session.objects.count() == avant


def test_la_session_essais_ne_s_exporte_pas():
    with pytest.raises(Refus):
        echange.exporter(Session.objects.get(essais=True))


def test_les_comptes_ne_voyagent_pas_dupliquer_et_modele(remplie):
    with routeur.session(remplie):
        m.Destination.objects.create(langue="xx", reseau="youtube", jeton="jeton-chiffre-factice", chaine="Chaîne factice")
        m.Publication.objects.create(video=m.Video.objects.get(), langue="xx", dossier="commun", statut="en_file")
    (settings.SESSIONS / remplie.dossier / "calendrier").mkdir()
    (settings.SESSIONS / remplie.dossier / "calendrier" / "plan.json").write_bytes(b"{}")
    copie = echange.dupliquer(remplie, f"Copie {remplie.nom}")
    with routeur.session(copie):
        d = m.Destination.objects.get()
        assert (d.jeton, d.reliee, d.chaine) == ("", None, "Chaîne factice") and m.Script.objects.count() == 1 and m.Video.objects.count() == 1
        assert not m.Publication.objects.exists()  # une copie n'a rien publié (et n'enverra rien)
    assert not list((settings.RACINE / "exports").glob(f"{remplie.dossier}_*.fabrique.tmp"))
    z = echange.exporter(remplie, modele=f"Modèle {remplie.nom}")
    assert z.parent.name == "modeles" and {"nom": f"Modèle {remplie.nom}", "fichier": z.name} in echange.modeles()
    with pytest.raises(Refus, match="déjà"):
        echange.exporter(remplie, modele=f"Modèle {remplie.nom}")
    neuve = echange.importer(z, f"Neuve {remplie.nom}")
    with routeur.session(neuve):  # le cadre seulement : langues, univers ; ni scripts, ni vidéos, ni comptes
        assert m.Langue.objects.count() == 1 and not m.Script.objects.exists() and not m.Video.objects.exists() and not m.Destination.objects.exists()
    assert (settings.SESSIONS / neuve.dossier / "univers" / "univers.json").is_file() and not (settings.SESSIONS / neuve.dossier / "calendrier").exists()


def test_vie_d_une_session_par_l_api(remplie, monkeypatch):
    from django.test import Client

    from fabrique.moteur import carte, file
    from fabrique.noyau import jetons
    from fabrique.noyau.models import Tache

    jetons.tirer(settings.DONNEES)

    def post(chemin, corps=None, qui="fenetre"):
        return Client().post(chemin, corps or {}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {jetons.lire(settings.DONNEES, qui)}")

    t = Tache.objects.create(session_id=remplie.id, video_id="v", titre="Le petit renard", acteur="RT")
    monkeypatch.setattr(carte, "occupee", lambda *a: "carte prise (essai)")  # rien ne se lance pendant ce test
    assert post(f"/api/sessions/{remplie.id}/pause", qui="claude").status_code == 403
    assert post(f"/api/sessions/{remplie.id}/pause").status_code == 200
    file.tour(lancer=lambda *a, **k: pytest.fail("lancée"))
    assert t.id not in [x.id for x in file.ordre()] and Tache.objects.get(id=t.id).raison == file.PAUSE
    assert post(f"/api/sessions/{remplie.id}/reprendre").status_code == 200 and t.id in [x.id for x in file.ordre()]
    assert post(f"/api/sessions/{remplie.id}/archiver").status_code == 200
    lue = next(x for x in Client().get("/api/sessions", HTTP_AUTHORIZATION=f"Bearer {jetons.lire(settings.DONNEES, 'fenetre')}").json() if x["id"] == remplie.id)
    assert lue["pause"] and lue["archivee"] and t.id not in [x.id for x in file.ordre()]
    assert post(f"/api/sessions/{remplie.id}/desarchiver").status_code == 200 and Session.objects.get(id=remplie.id).archivee is None
    Tache.objects.filter(id=t.id).update(etat="annulee")
    essais = Session.objects.get(essais=True)
    assert post(f"/api/sessions/{essais.id}/pause").status_code == 409
    assert post(f"/api/sessions/{remplie.id}/dupliquer").status_code == 409  # un nom est attendu
    assert "Copie" in post(f"/api/sessions/{remplie.id}/dupliquer", {"nom": f"Double {remplie.nom}"}).json()["message"]
    r = post(f"/api/sessions/{remplie.id}/modele", {"nom": f"Cadre {remplie.nom}"})
    assert r.status_code == 200 and "Modèle enregistré" in r.json()["message"]
    nom = next(x["fichier"] for x in echange.modeles() if x["nom"] == f"Cadre {remplie.nom}")
    assert post("/api/sessions/importer", {"fichier": nom, "nom": f"Depuis le cadre {remplie.nom}"}).status_code == 200
    assert Session.objects.filter(nom=f"Depuis le cadre {remplie.nom}").exists()
    r = post(f"/api/sessions/{remplie.id}/exporter", {"videos": True})  # des Go avec les vidéos : à côté de la requête, une notification à la fin
    assert r.status_code == 200 and "lancé" in r.json()["message"]
    import time

    fin = time.monotonic() + 30
    while time.monotonic() < fin and not list((settings.RACINE / "exports").glob(f"{remplie.dossier}_*.fabrique")):
        time.sleep(0.2)
    with zipfile.ZipFile(max((settings.RACINE / "exports").glob(f"{remplie.dossier}_*.fabrique"))) as z:
        assert "videos/v1/final/v.mp4" in z.namelist()
