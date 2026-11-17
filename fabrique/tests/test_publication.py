"""Publication, J4 étape 1 (noms factices, faux Google local, jamais le réseau) : relier la chaîne YouTube d'une langue de bout en bout, jeton de
rafraîchissement chiffré en base, jamais rendu par l'API ni journalisé ; renouvellement, refus de Google, droits, une destination par langue."""
import json
import logging
import time
import urllib.request

import pytest
from django.conf import settings
from django.test import Client as Navigateur

from fabrique.garde import Refus
from fabrique.noyau import bases, cles, etat, evenements, jetons, routeur
from fabrique.noyau.models import Journal, Session
from fabrique.publication import faux_youtube, youtube
from fabrique.session import models as m


@pytest.fixture
def faux(monkeypatch):
    f = faux_youtube.Faux().demarrer()
    monkeypatch.setattr(youtube, "_faux", lambda: f)
    youtube._acces.clear()
    yield f
    f.arreter()


@pytest.fixture
def session(request):
    s = bases.creer(f"Session {request.node.name}")
    with routeur.session(s):
        m.Langue.objects.create(code="xx", nom="Langue factice")
        m.Script.objects.create(code="s1e01", titre="Une histoire factice", langue="en", statut="scenario")
    return s


def entete(qui: str) -> dict:
    jetons.tirer(settings.DONNEES)
    jetons.APPELANTS["essai-iphone"] = "iphone"  # l'iPhone n'a pas encore son jeton
    return {"HTTP_AUTHORIZATION": f"Bearer {'essai-iphone' if qui == 'iphone' else jetons.lire(settings.DONNEES, qui)}"}


def lister(s, qui="fenetre") -> list[dict]:
    return Navigateur().get(f"/api/sessions/{s.id}/destinations", **entete(qui)).json()


def relier(s, langue="xx") -> str:
    """RT clique « Relier », puis accepte sur la page de Google : le navigateur suit la redirection vers le retour sur 127.0.0.1."""
    r = Navigateur().post(f"/api/sessions/{s.id}/destinations/{langue}/relier", **entete("fenetre"))
    assert r.status_code == 200, r.content
    with urllib.request.urlopen(r.json()["url"], timeout=20) as page:
        return page.read().decode("utf-8")


def test_relier_de_bout_en_bout_sans_jamais_rendre_ni_journaliser_le_jeton(session, faux, caplog):
    caplog.set_level(logging.DEBUG)
    assert [(d["langue"], d["etat"]) for d in lister(session)] == [("xx", "pas reliée"), ("en", "pas reliée")]
    assert "Chaîne reliée" in relier(session)
    lues = lister(session, "iphone")
    assert lues[0] == {"langue": "xx", "reseau": "youtube", "etat": "reliée", "reliee": True, "chaine": "Chaîne factice", "chaine_id": "UCfauxChaine",
                       "depuis": lues[0]["depuis"], "playlists": [{"id": i, "titre": t} for i, t in faux_youtube.PLAYLISTS]}
    assert lues[0]["depuis"] and lues[1]["etat"] == "pas reliée"
    demande = faux.appels_de("GET", "/o/oauth2/v2/auth")[0]["params"]
    assert demande["code_challenge_method"] == "S256" and demande["redirect_uri"].startswith("http://127.0.0.1:")
    with routeur.session(session):
        d = m.Destination.objects.get()
    rafraichi = cles.dechiffrer(d.jeton)
    assert rafraichi.startswith("faux-rafraichi-") and rafraichi not in d.jeton and d.simulation  # chiffré par Windows ; destination de la simulation
    secrets_ = [rafraichi, d.jeton, youtube._acces[(session.id, "xx", True)][0]]
    textes = [json.dumps(lues), json.dumps(list(Journal.objects.values_list("detail", flat=True))), caplog.text,
              *(f.read_text(encoding="utf-8", errors="replace") for f in settings.JOURNAUX.glob("*.log"))]
    assert not [x for x in secrets_ for t in textes if x in t]
    assert Journal.objects.filter(action="destination_reliee", acteur="RT").exists()


def test_renouvellement_puis_refus_de_google(session, faux, monkeypatch):
    relier(session)
    alertes = []
    monkeypatch.setattr(evenements, "publier", lambda t, **d: alertes.append((t, d)))
    premier = youtube.jeton(session, "xx")
    assert youtube.jeton(session, "xx") == premier  # gardé en mémoire tant qu'il vaut
    youtube._acces[(session.id, "xx", True)] = (premier, time.time() + 30)  # expire dans 30 s : renouvelé
    assert youtube.jeton(session, "xx") != premier and faux.appels_de("POST", "/token")[-1]["corps"] == {"grant_type": "refresh_token"}
    n = Navigateur()
    r = n.post(f"/api/sessions/{session.id}/destinations/xx/rafraichir", **entete("fenetre"))
    assert r.status_code == 200 and r.json()["message"] == "Chaîne « Chaîne factice » : 3 playlist(s) lue(s)."
    faux.refuser = True
    youtube._acces.clear()
    with pytest.raises(youtube.JetonRefuse):
        youtube.jeton(session, "xx")
    assert [t for t, _ in alertes] == ["alerte"] and "relier" in alertes[0][1]["message"]
    demandes = len(faux.appels_de("POST", "/token"))
    r = n.post(f"/api/sessions/{session.id}/destinations/xx/rafraichir", **entete("fenetre"))
    assert r.status_code == 409 and "relier" in r.json()["detail"]
    assert len(faux.appels_de("POST", "/token")) == demandes  # déjà refusé : Google n'est plus sollicité
    d = lister(session)[0]
    assert d["etat"].startswith("refusée le ") and not d["reliee"]
    faux.refuser = False
    relier(session)  # relier efface le refus
    assert lister(session)[0]["etat"] == "reliée"


def test_droits_jamais_claude(session, faux):
    n, base = Navigateur(), f"/api/sessions/{session.id}/destinations"
    assert n.get(base, **entete("claude")).status_code == 403
    assert n.get(base, **entete("iphone")).status_code == 200
    for qui in ("claude", "iphone"):
        assert n.post(f"{base}/xx/relier", **entete(qui)).status_code == 403
        assert n.post(f"{base}/xx/rafraichir", **entete(qui)).status_code == 403
    r = n.post(f"{base}/zz/relier", **entete("fenetre"))
    assert r.status_code == 409 and "« zz »" in r.json()["detail"]
    r = n.post(f"{base}/xx/rafraichir", **entete("fenetre"))
    assert r.status_code == 409 and "pas reliée" in r.json()["detail"]
    essais = Session.objects.get(essais=True)
    r = n.post(f"/api/sessions/{essais.id}/destinations/xx/relier", **entete("fenetre"))
    assert r.status_code == 409 and "Essais" in r.json()["detail"] and lister(essais) == []


def test_une_destination_par_langue_et_par_mode(session, faux, monkeypatch):
    relier(session)
    relier(session)
    relier(session, "en")
    with routeur.session(session):
        assert sorted(m.Destination.objects.values_list("langue", flat=True)) == ["en", "xx"]
    monkeypatch.setattr(etat, "simulation", lambda: False)  # les chaînes reliées en simulation ne servent jamais en vrai
    assert [d["etat"] for d in youtube.lister(session)] == ["pas reliée", "pas reliée"]


def test_client_secret_application_de_bureau(tmp_path, monkeypatch):
    assert youtube.chemin_secret().parts[-3:] == ("OUTILS", "installation", "youtube_client_secret.json")  # celui de Bramble Studio, jamais lu ici
    monkeypatch.setattr(etat, "simulation", lambda: False)
    f = tmp_path / youtube.SECRET
    monkeypatch.setattr(youtube, "chemin_secret", lambda: f)
    with pytest.raises(Refus, match="absent"):
        youtube.secret()
    f.write_text(json.dumps({"web": {"client_id": "x", "client_secret": "y"}}), encoding="utf-8")
    with pytest.raises(Refus, match="Application de bureau"):
        youtube.secret()
    f.write_text(json.dumps({"installed": {"client_id": "x", "client_secret": "y"}}), encoding="utf-8")
    assert youtube.secret()["client_id"] == "x"
