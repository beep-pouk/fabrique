"""J5, côté noyau (noms factices) : nouvelle session pas à pas jusqu'à sa vidéo pilote, garde-fou, calendrier (statuts, ordre strict, créneaux
estimés), idées, univers complet (galerie, import, droits, historique, partage), mur des sessions."""
from datetime import date, datetime, timedelta, timezone as tz
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client as Navigateur
from django.utils import timezone

from fabrique.garde import Refus
from fabrique.moteur import file
from fabrique.noyau import etat, routeur
from fabrique.noyau.models import Journal, Session, Tache
from fabrique.session import calendrier, reglages, univers
from fabrique.session import models as m
from fabrique.tests.test_session_api import entete


@pytest.fixture
def nouvelle(request):
    n = Navigateur()
    r = n.post("/api/sessions", {"nom": f"Nouvelle {request.node.name}", "langues": [{"code": "xx", "nom": "Langue factice"}, {"code": "yy", "nom": ""}],
                                 "public": "petits", "promesse": "une histoire calme"}, content_type="application/json", **entete("fenetre"))
    assert r.status_code == 200, r.content
    s = Session.objects.get(id=r.json()["id"])
    yield s
    Tache.objects.filter(session_id=s.id).delete()


def poster(chemin, corps=None, qui="fenetre"):
    return Navigateur().post(chemin, corps or {}, content_type="application/json", **entete(qui))


def test_nouvelle_session_pas_a_pas_jusqu_au_pilote(nouvelle, monkeypatch):
    s = nouvelle
    assert s.pause  # en pause jusqu'à la fin de l'assistant
    d = Navigateur().get(f"/api/sessions/{s.id}/reglages", **entete("fenetre")).json()
    assert d["langues"] == [{"code": "xx", "nom": "Langue factice"}, {"code": "yy", "nom": "yy"}] and d["assistant"] == "2" and d["promesse"] == "une histoire calme"
    assert d["manque"] == ["un format", "ce qui rend chaque vidéo différente (Règles)"]
    assert poster(f"/api/sessions/{s.id}/finir").status_code == 409
    assert poster(f"/api/sessions/{s.id}/reglages", {"formats": ["inconnu"]}).status_code == 409
    assert poster(f"/api/sessions/{s.id}/reglages", {"difference": "  "}).json()["detail"].startswith("dire ce qui rend")
    assert poster(f"/api/sessions/{s.id}/reglages", {"duree_min": 9, "duree_max": 3}).status_code == 409
    assert poster(f"/api/sessions/{s.id}/reglages", {"formats": ["essai"], "difference": "un animal différent chaque soir", "objectif": "1 000 vues",
                                                     "arret": "moins de 10 vues après 10 vidéos", "plafond_eur": 5, "enfants": True, "duree_min": 3,
                                                     "duree_max": 8}).status_code == 200
    d = reglages.lire(s)
    assert (d["format"], d["formats"], d["plafond_eur"], d["duree_max"]) == ("essai", ["essai"], 5.0, 8.0)
    assert poster(f"/api/sessions/{s.id}/reglages", {"format": "F1"}).status_code == 409  # pas parmi ceux de la session
    assert poster(f"/api/sessions/{s.id}/reglages", {"style": "x"}, qui="claude").status_code == 403
    assert poster(f"/api/sessions/{s.id}/pilote").status_code == 409  # pas finie : rien ne part
    assert poster(f"/api/sessions/{s.id}/finir").status_code == 200
    s.refresh_from_db()
    assert not s.pause and reglages.lire(s)["assistant"] == "fini"
    monkeypatch.setattr(etat, "simulation", lambda: False)  # même en mode réel, la vidéo pilote est faite par les faux outils
    assert poster(f"/api/sessions/{s.id}/pilote").status_code == 200
    assert poster(f"/api/sessions/{s.id}/pilote").json()["detail"] == "la vidéo pilote est déjà dans la file"
    t = Tache.objects.get(session_id=s.id)
    with routeur.session(s):
        v = m.Video.objects.get(id=t.video_id)
        assert v.recette["reglages"]["langues"] == ["xx", "yy"] and {mo.outil for mo in v.morceaux.all()} <= {f"faux_{b}" for b in
                                                                                                           ("voix", "images", "animation", "musique", "levres", "montage", "miniature", "controle")}
    assert [x["code"] for x in calendrier.lire(s)] == []  # la vidéo pilote n'est pas au calendrier


def test_nouvelle_session_refus(nouvelle):
    assert poster("/api/sessions", {"nom": nouvelle.nom, "langues": [{"code": "xx"}]}).json()["detail"].startswith("une session s'appelle déjà")
    assert poster("/api/sessions", {"nom": "Autre factice", "langues": [{"code": "Anglais"}]}).status_code == 409
    assert poster("/api/sessions", {"nom": "Autre factice", "langues": []}).status_code == 409
    assert poster("/api/sessions", {"nom": "Autre factice", "langues": [{"code": "xx"}], "modele": "..\\ailleurs.fabrique"}).status_code == 409
    assert not Session.objects.filter(nom="Autre factice").exists()  # jamais une session à moitié créée


def scripts(s, *codes_dates_statuts):
    with routeur.session(s):
        for code, jour, statut in codes_dates_statuts:
            sc = m.Script.objects.create(code=code, titre=f"Titre {code}", langue="xx", statut=statut, date_prevue=jour)
            if statut != "idee":
                m.VersionScript.objects.create(script=sc, numero=1, auteur="RT", date=timezone.now(), contenu={}, regles={"erreurs": []})


def test_statuts_et_ordre_strict(nouvelle):
    s, j = nouvelle, date(2026, 12, 1)
    scripts(s, ("e1", j, "scenario"), ("e2", j + timedelta(days=2), "scenario"), ("e3", j + timedelta(days=3), "publie"), ("e4", None, "idee"))
    lu = {x["code"]: x for x in calendrier.lire(s)}
    assert [x["code"] for x in calendrier.lire(s)] == ["e1", "e2", "e3", "e4"] and lu["e1"]["statut"] == "prete" and lu["e3"]["statut"] == "publiee"
    assert lu["e4"]["statut"] == "idee" and [x["code"] for x in calendrier.lire(s, j, j + timedelta(days=2))] == ["e1", "e2"]
    with routeur.session(s):  # e2 approuvée, son brouillon de publication suit sa date
        v = m.Video.objects.create(titre="v", nom=f"{j + timedelta(days=2)}-e2", script={}, recette={})
        p = m.Publication.objects.create(video=v, langue="xx", dossier="commun")
    assert calendrier.lire(s)[1]["statut"] == "approuvee"
    faits = calendrier.recalculer(s, j)  # le jour de e1, pas prête : elle passe à demain, e2 garde son écart de 2 jours
    assert faits == ["e1 : 01/12/2026 → 02/12/2026", "e2 : 03/12/2026 → 04/12/2026"]
    with routeur.session(s):
        assert m.Script.objects.get(code="e3").date_prevue == j + timedelta(days=3)  # publiée : jamais bougée
        p.refresh_from_db()
        assert timezone.localdate(p.planifiee_le) == j + timedelta(days=3)
    lu = {x["code"]: x for x in calendrier.lire(s)}
    assert lu["e1"]["statut"] == "reportee" and lu["e1"]["statut_nom"] == "reportée" and lu["e2"]["statut"] == "approuvee"
    with routeur.session(s):  # e2 déjà confiée à YouTube : sa date ne bouge plus, une alerte le dit
        m.Publication.objects.filter(id=p.id).update(statut="planifiee", planifiee_le=datetime(2026, 12, 4, 18, tzinfo=tz.utc))
    assert calendrier.recalculer(s, j + timedelta(days=1)) == ["e1 : 02/12/2026 → 03/12/2026"]  # e2 devrait glisser au 05 (écart de 2 jours)
    alertes = Journal.objects.filter(action="alerte_ordre", detail__session=s.id, detail__code="e2")
    assert alertes.count() == 1  # mais elle est confiée à YouTube : rien ne bouge chez elle, une alerte le dit
    assert calendrier.recalculer(s, j + timedelta(days=4)) == ["e1 : 03/12/2026 → 06/12/2026"]
    assert alertes.count() == 1  # une seule alerte pour la même date
    reglages.ecrire(s, {"ordre_strict": False}, "RT")
    assert calendrier.recalculer(s, j + timedelta(days=9)) == []


def test_une_fois_par_jour(nouvelle, monkeypatch):
    vus = []
    monkeypatch.setattr(calendrier, "recalculer", lambda s, jour: vus.append(s.id) or [])
    calendrier.une_fois_par_jour(date(2030, 1, 1))
    calendrier.une_fois_par_jour(date(2030, 1, 1))
    assert vus.count(nouvelle.id) == 1 and not set(vus) & set(Session.objects.filter(essais=True).values_list("id", flat=True))


def test_creneaux_estimes():
    soir = datetime(2026, 12, 1, 23, 0)
    assert calendrier.ajouter(soir, 30 * 60) == datetime(2026, 12, 1, 23, 30)
    assert calendrier.ajouter(soir, 2 * 3600) == datetime(2026, 12, 2, 8, 0)  # PC éteint de minuit à 7 h
    assert calendrier.ajouter(datetime(2026, 12, 2, 3, 0), 600) == datetime(2026, 12, 2, 7, 10)


def test_file_estimee_et_calendrier_d_ensemble(nouvelle):
    s = nouvelle
    reglages.ecrire(s, {"formats": ["essai"], "difference": "un animal différent"}, "RT")
    reglages.finir(s, "RT")
    s.refresh_from_db()
    scripts(s, (reglages.PILOTE, None, "idee"))  # un script « pilote » existe déjà : la vidéo pilote en fait une version de plus
    reglages.pilote(s, "RT")
    lu = Navigateur().get("/api/file", **entete("fenetre")).json()
    t = next(x for x in lu if x["session"] == s.nom)
    assert t["reste_s"] > 0 and t["cout_eur"] == 0 and len(t["pret_vers"]) == 11
    scripts(s, ("e1", date(2099, 1, 1), "scenario"))
    tout = Navigateur().get("/api/calendrier?debut=2099-01-01&fin=2099-01-31", **entete("fenetre")).json()
    assert [(x["session_nom"], x["code"]) for x in tout if x["session"] == s.id] == [(s.nom, "e1")]
    assert Navigateur().get("/api/calendrier?debut=demain", **entete("fenetre")).status_code == 400


def test_idees(nouvelle):
    assert poster(f"/api/sessions/{nouvelle.id}/idees", {"titre": "Un hibou qui compte les étoiles"}, qui="claude").status_code == 200
    assert poster(f"/api/sessions/{nouvelle.id}/idees", {"titre": " "}).status_code == 409
    lu = Navigateur().get(f"/api/sessions/{nouvelle.id}/idees", **entete("fenetre")).json()
    assert [(i["titre"], i["source"]) for i in lu] == [("Un hibou qui compte les étoiles", "claude")]


def test_univers_complet(nouvelle, tmp_path):
    s = nouvelle
    assert poster(f"/api/sessions/{s.id}/univers/ajouter", {"type": "personnage", "nom": "Ami Un", "role": "ami", "description": "un renard"}).status_code == 200
    assert poster(f"/api/sessions/{s.id}/univers/ajouter", {"type": "personnage", "nom": "Ami Un"}).status_code == 409
    assert poster(f"/api/sessions/{s.id}/univers/ajouter", {"type": "lieu", "nom": "La clairière"}).status_code == 200
    assert poster(f"/api/sessions/{s.id}/univers/ajouter", {"type": "musique", "nom": "Berceuse"}).status_code == 200
    assert poster(f"/api/sessions/{s.id}/univers/ajouter", {"type": "personnage", "nom": "Intrus"}, qui="claude").status_code == 403
    u = univers.lire(s)
    p, musique = u["personnages"][0], u["ressources"][0]
    image = tmp_path / "Mon image.PNG"
    image.write_bytes(b"\x89PNG factice")
    assert poster(f"/api/sessions/{s.id}/personnages/{p['id']}/references", {"fichier": str(image), "vue": "face"}).status_code == 200
    assert poster(f"/api/sessions/{s.id}/personnages/{p['id']}/references", {"fichier": str(image)}, qui="claude").status_code == 200  # import par Claude
    texte = tmp_path / "notes.txt"
    texte.write_text("x")
    assert poster(f"/api/sessions/{s.id}/personnages/{p['id']}/references", {"fichier": str(texte)}).status_code == 409
    assert poster(f"/api/sessions/{s.id}/personnages/{p['id']}/references", {"fichier": "relatif.png"}).status_code == 409
    assert image.is_file()  # copiée, jamais déplacée
    refs = univers.lire(s)["personnages"][0]["references"]
    assert [Path(r["chemin"]).name for r in refs] == ["mon_image.png", "mon_image_2.png"] and [r["source"] for r in refs] == ["RT", "claude"]
    assert all(Path(r["chemin"]).read_bytes() == b"\x89PNG factice" for r in refs) and not any(r["validee"] for r in refs)
    assert poster(f"/api/sessions/{s.id}/references/{refs[1]['id']}/valider", {"validee": True}).status_code == 200
    assert univers.lire(s)["personnages"][0]["references"][0]["id"] == refs[1]["id"]  # les validées d'abord
    assert poster(f"/api/sessions/{s.id}/univers/musique/{musique['id']}/droits", {"licence": "libre", "credit": "Compositeur Factice"}).status_code == 200
    assert poster(f"/api/sessions/{s.id}/univers/personnage/{p['id']}/droits", {"licence": "image générée", "credit": ""}).status_code == 200
    assert poster(f"/api/sessions/{s.id}/univers/voix/{musique['id']}/droits", {"licence": "x", "credit": ""}).status_code == 409  # pas une voix
    assert poster(f"/api/sessions/{s.id}/univers/style", {"valeur": "aquarelle"}).status_code == 200
    u = univers.lire(s)
    assert (u["ressources"][0]["licence"], u["ressources"][0]["credit"], u["personnages"][0]["licence"], u["style"]) == ("libre", "Compositeur Factice", "image générée", "aquarelle")
    autre = reglages.creer(f"Autre {s.nom}", [{"code": "xx"}])
    assert poster(f"/api/sessions/{s.id}/univers/personnage/{p['id']}/partager", {"vers": autre.id}).status_code == 200
    assert poster(f"/api/sessions/{s.id}/univers/personnage/{p['id']}/partager", {"vers": autre.id}).status_code == 409  # déjà là
    assert poster(f"/api/sessions/{s.id}/univers/personnage/{p['id']}/partager", {"vers": s.id}).status_code == 409
    v = univers.lire(autre)["personnages"][0]
    assert v["nom"] == "Ami Un" and len(v["references"]) == 2 and all(Path(r["chemin"]).read_bytes() == b"\x89PNG factice" for r in v["references"])
    assert str(settings.SESSIONS / autre.dossier) in v["references"][0]["chemin"]
    h = Navigateur().get(f"/api/sessions/{s.id}/historique", **entete("fenetre")).json()
    assert len(h) == 10 and h[0]["quoi"] == f"personnage « Ami Un » partagé avec « {autre.nom} »" and h[-1]["quoi"] == "personnage « Ami Un » ajouté"
    assert [x["quoi"] for x in univers.historique(autre)] == [f"personnage « Ami Un » reçu de « {s.nom} »"]


def test_mur_des_sessions(nouvelle):
    s = nouvelle
    scripts(s, ("e1", timezone.localdate() + timedelta(days=1), "scenario"))
    with routeur.session(s):
        v = m.Video.objects.create(titre="Le petit renard", nom="2099-01-01-e1", script={}, recette={})
        d = m.Destination.objects.create(langue="xx", reseau="youtube")
        m.StatistiqueJour.objects.create(destination=d, date=timezone.localdate() - timedelta(days=1), vues=1200)
        m.StatistiqueJour.objects.create(destination=d, date=timezone.localdate() - timedelta(days=40), vues=99)
    c = next(x for x in Navigateur().get("/api/sessions", **entete("fenetre")).json() if x["id"] == s.id)
    demain = timezone.localdate() + timedelta(days=1)
    assert (c["videos"], c["derniere"], c["a_faire"], c["prochain"], c["rendement"], c["assistant"]) == (
        1, "Le petit renard", 1, f"{demain:%d/%m} Titre e1", "1 200 vues sur 28 jours", "2")  # à faire : la vidéo finie, à approuver
    with routeur.session(s):
        m.Morceau.objects.create(video=v, etape="voix", brique="voix", unite="", langue="", ordre=0, outil="faux_voix")
    assert calendrier.carte(s)["a_faire"] == 0 and calendrier.lire(s)[0]["statut"] == "prete"  # pas finie, pas dans la file
    file.mettre(s, v.id, v.titre, "RT")
    assert calendrier.lire(s)[0]["statut"] == "fabrication"


def test_commandes_de_claude(monkeypatch):
    from fabrique.__main__ import commande
    from fabrique.fenetre import client

    vus = []
    monkeypatch.setattr(client.Client, "appeler", lambda self, appel, corps=None, /, **p: vus.append((self.appelant, appel, corps, p)) or {"message": "ok"})
    assert commande(["idee", "s1", "Un hibou", "qui", "compte"]) == 0
    assert commande(["reference", "s1", "3", "D:/images/hibou.png"]) == 0
    assert commande(["reference", "s1", "3"]) == 2  # incomplète : l'aide
    assert vus == [("claude", "ajouter_idee", {"titre": "Un hibou", "resume": "qui compte", "source": "claude"}, {"id": "s1"}),
                   ("claude", "importer_reference", {"fichier": "D:/images/hibou.png"}, {"id": "s1", "pk": "3"})]


def test_scripts_crees_et_dates(nouvelle):
    """Une session neuve met des scripts au calendrier : d'une idée ou non, datés par RT ; jamais une vidéo déjà confiée à YouTube."""
    s = nouvelle
    poster(f"/api/sessions/{s.id}/idees", {"titre": "Le hibou qui compte"})
    idee = calendrier.idees(s)[0]["id"]
    r = poster(f"/api/sessions/{s.id}/scripts", {"idee": idee}, qui="claude")
    assert r.status_code == 200 and r.json()["code"] == "e01"
    assert calendrier.idees(s)[0]["statut"] == "convertie"
    assert poster(f"/api/sessions/{s.id}/scripts", {"titre": "Le pont", "date": "2099-02-03"}).json()["code"] == "e02"
    assert poster(f"/api/sessions/{s.id}/scripts", {"titre": "x", "date": "demain"}).status_code == 400
    assert poster(f"/api/sessions/{s.id}/scripts/e01/dater", {"date": "2099-02-01"}).status_code == 200
    assert poster(f"/api/sessions/{s.id}/scripts/e01/dater", {"date": "2099-02-01"}, qui="claude").status_code == 403
    assert [(x["code"], x["date"], x["statut"]) for x in calendrier.lire(s, date(2099, 2, 1), date(2099, 2, 28))] == [
        ("e01", "2099-02-01", "idee"), ("e02", "2099-02-03", "idee")]
    with routeur.session(s):
        v = m.Video.objects.create(titre="v", nom="2099-02-03-e02", script={}, recette={})
        m.Publication.objects.create(video=v, langue="xx", dossier="commun", statut="erreur", identifiant_youtube="ABC")  # déjà chez YouTube, même en erreur
    assert "confiée à YouTube" in poster(f"/api/sessions/{s.id}/scripts/e02/dater", {"date": ""}).json()["detail"]
    assert poster(f"/api/sessions/{s.id}/scripts/e01/dater", {"date": ""}).status_code == 200  # retiré du calendrier
    assert [x["code"] for x in calendrier.lire(s, date(2099, 2, 1), date(2099, 2, 28))] == ["e02"]


def test_fiches_du_calendrier_editorial(nouvelle):
    s = nouvelle
    with routeur.session(s):
        m.Prevision.objects.create(date=date(2099, 3, 1), statut="acceptee", details={"type": "histoire", "heros": "Ami Un", "lieu": "Clairière", "saison": "hiver", "episode": ""})
        m.Prevision.objects.create(date=date(2099, 3, 2), statut="refusee", details={"type": "histoire"})
        m.Prevision.objects.create(date=date(2099, 3, 3), statut="acceptee", details={"type": "histoire", "episode": "e09"})
        m.Script.objects.create(code="e09", titre="Déjà écrit", langue="xx", statut="idee", date_prevue=date(2099, 3, 3))
    lu = calendrier.lire(s, date(2099, 3, 1), date(2099, 3, 31))
    assert [(x["code"], x["titre"], x["statut_nom"]) for x in lu] == [("e09", "Déjà écrit", "idée"), ("", "histoire · Ami Un · Clairière · hiver", "fiche du calendrier éditorial")]


def test_regles_selon_la_forme_du_format(nouvelle):
    from fabrique.session import regles

    reglages.ecrire(nouvelle, {"formats": ["essai"]}, "RT")
    assert regles.controler(nouvelle, {"titre": "t", "scenes": [{"id": "s1", "plans": [{"id": "p1"}]}]}) == {"erreurs": [], "avis": [], "mesures": {}}
    assert regles.controler(nouvelle, {"title": "un scénario de Bramble"})["erreurs"][0][0] == "forme"


def test_langues_remplacees_et_creation_jamais_a_moitie(nouvelle, monkeypatch):
    s = nouvelle
    assert poster(f"/api/sessions/{s.id}/reglages", {"langues": [{"code": "zz"}], "formats": ["inconnu"]}).status_code == 409
    assert [l["code"] for l in reglages.lire(s)["langues"]] == ["xx", "yy"]  # refusé : rien d'écrit
    with routeur.session(s):
        m.Destination.objects.create(langue="yy", reseau="youtube", jeton="chiffré")
    assert "chaîne reliée" in poster(f"/api/sessions/{s.id}/reglages", {"langues": [{"code": "xx"}]}).json()["detail"]
    assert poster(f"/api/sessions/{s.id}/reglages", {"langues": [{"code": "yy"}, {"code": "zz"}]}).status_code == 200
    assert [l["code"] for l in reglages.lire(s)["langues"]] == ["yy", "zz"]
    monkeypatch.setattr(reglages, "ecrire", lambda *a, **k: (_ for _ in ()).throw(Refus("format inconnu : F9")))
    with pytest.raises(Refus, match="F9"):
        reglages.creer("Ratée factice", [{"code": "xx"}])
    assert not Session.objects.filter(nom="Ratée factice").exists() and list((settings.DONNEES / "_corbeille").glob("ratee_factice_*"))


def test_reprendre_ni_archivee_ni_pas_finie(nouvelle):
    s = nouvelle
    assert "pas finie" in poster(f"/api/sessions/{s.id}/reprendre", {"nom": ""}).json()["detail"]
    reglages.ecrire(s, {"formats": ["essai"], "difference": "x"}, "RT")
    reglages.finir(s, "RT")
    assert poster(f"/api/sessions/{s.id}/archiver", {"nom": ""}).status_code == 200
    assert "archivée" in poster(f"/api/sessions/{s.id}/reprendre", {"nom": ""}).json()["detail"]
    poster(f"/api/sessions/{s.id}/desarchiver", {"nom": ""})
    assert poster(f"/api/sessions/{s.id}/reprendre", {"nom": ""}).status_code == 200


def test_une_video_des_faux_outils_jamais_sur_une_vraie_chaine(nouvelle, monkeypatch):
    from fabrique.publication import publication

    with routeur.session(nouvelle):
        v = m.Video.objects.create(titre="Pilote factice", nom="2099-01-01-pilote", script={}, recette={"reglages": {"langues": ["xx"]}})
        m.Morceau.objects.create(video=v, etape="voix", brique="voix", unite="", langue="", ordre=0, outil="faux_voix", etat="fini")
    assert calendrier.carte(nouvelle)["a_faire"] == 0  # la vidéo pilote se regarde, ne se publie pas
    monkeypatch.setattr(etat, "simulation", lambda: False)
    with pytest.raises(Refus, match="faux outils"):
        publication.approuver(nouvelle, v.id, "RT")


def test_partage_jamais_vers_l_image_d_un_autre(nouvelle):
    s = nouvelle
    autre = reglages.creer(f"Autre {s.nom}", [{"code": "xx"}])
    univers.ajouter(s, "personnage", "Léa", "", "RT")
    with routeur.session(s):
        p = m.Personnage.objects.get(nom="Léa")
        m.Reference.objects.create(personnage=p, fichier="univers/personnages/lea/face.png", date=timezone.now())
        m.Reference.objects.create(personnage=p, fichier="univers/personnages/lea/absente.png", date=timezone.now())
    for d, contenu in ((settings.SESSIONS / s.dossier, b"image de Lea"), (settings.SESSIONS / autre.dossier, b"image d'un autre")):
        (d / "univers" / "personnages" / "lea").mkdir(parents=True, exist_ok=True)
        (d / "univers" / "personnages" / "lea" / "face.png").write_bytes(contenu)
    univers.partager(s, "personnage", p.id, autre, "RT")
    refs = univers.lire(autre)["personnages"][0]["references"]
    assert [Path(r["chemin"]).read_bytes() for r in refs] == [b"image de Lea"] and refs[0]["chemin"].endswith("face_2.png")


def test_rattrapage_des_sessions_bramble_d_avant_j5(nouvelle):
    import importlib

    from django.apps import apps
    from django.db import connections

    mig = importlib.import_module("fabrique.session.migrations.0010_reglages_bramble")
    with routeur.session(nouvelle):
        m.Reglage.objects.create(cle="origine", valeur="bramble")
        m.Reglage.objects.filter(cle="difference").delete()
    mig.rattraper(apps, type("E", (), {"connection": connections[routeur.ouvrir(nouvelle)]})())
    d = reglages.lire(nouvelle)
    assert d["formats"] == ["F1"] and d["difference"].startswith("Chaque épisode") and d["assistant"] == "2"  # rien d'écrasé
