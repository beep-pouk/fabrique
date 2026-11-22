"""Publication (noms factices, faux Google local, jamais le réseau). J4 étape 1 : relier la chaîne YouTube d'une langue de bout en bout, jeton de
rafraîchissement chiffré en base, jamais rendu par l'API ni journalisé ; renouvellement, refus de Google, droits, une destination par langue.
J4 étape 2 : approuver (brouillons par langue), aperçu, publier (tâche détachée légère), envoi complet, coupure et processus tué puis reprise
sans 2e vidéo, double clic, non répertorié la première fois, langue sans chaîne, erreur en clair, droits."""
import hashlib
import json
import logging
import os
import threading
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest
from django.conf import settings
from django.db import connections
from django.test import Client as Navigateur

from fabrique import programme
from fabrique.garde import Refus
from fabrique.noyau import bases, cles, etat, evenements, jetons, routeur, serveur, taches
from fabrique.noyau.models import Journal, Session, Tache
from fabrique.publication import faux_youtube, paquets, publication, youtube
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


# ---- J4 étape 2 : approuver, publier, envoyer ----

MORCEAU = 256 * 1024
TAILLE = 5 * MORCEAU + 1000  # 6 morceaux
YOUTUBE_TXT = """TITRE :
Le petit renard | Histoire factice

DESCRIPTION :
Un petit renard cherche la lune.

00:00 Le terrier
01:10 La forêt
02:30 La lune

Crédits : voix et images factices.

TAGS :
renard, histoire du soir, essai
"""


class Tue(BaseException):
    """Le processus de la tâche tué net : rien après, ni except, ni état final."""


@pytest.fixture
def envois(monkeypatch):
    """La tâche « publication » n'est jamais lancée pour de vrai : les lancements sont notés, l'envoi est joué ici (publication.executer)."""
    lances = []
    monkeypatch.setattr(programme, "lancer_detache", lambda *a, **k: lances.append(a))
    monkeypatch.setattr(publication, "MORCEAU", MORCEAU)
    monkeypatch.setattr(publication, "PAUSE_S", 0)
    yield lances
    while x := paquets.suivante(set()):  # ni des paquets à faire
        with routeur.session(x[0]):
            m.Publication.objects.filter(pk=x[1]).update(paquets={"fini": True})
    while x := publication.suivante(set()):  # jamais un envoi laissé en file pour la boucle du noyau d'un autre test
        with routeur.session(x[0]):
            m.Publication.objects.filter(pk=x[1]).update(statut="erreur")
    taches.fichier("publication").unlink(missing_ok=True)
    taches.fichier("paquets").unlink(missing_ok=True)


def video_finie(s, nom="2099-12-01-s1e01", langues=("en", "xx")) -> str:
    """Une vidéo dont la fabrication est finie, et ses fichiers finaux (langue du script sous « commun »)."""
    with routeur.session(s):
        v = m.Video.objects.create(titre="Le petit renard", nom=nom, script={"title": "Le petit renard", "language": "en", "bqw": {"hero": "renard"}},
                                   recette={"id": "F1", "version": 2, "reglages": {"langues": list(langues)}, "etapes": []})
        m.Morceau.objects.create(video=v, etape="montage", brique="montage", unite="", langue="", ordre=0, outil="f1_montage", etat="fini")
    for langue in langues:
        d = settings.SESSIONS / s.dossier / "videos" / v.id / ("commun" if langue == "en" else langue) / "atelier" / nom / "final"
        d.mkdir(parents=True)
        (d / f"{nom}.mp4").write_bytes(os.urandom(TAILLE))
        (d / "miniature.jpg").write_bytes(b"\xff\xd8\xff miniature factice " + langue.encode())
        (d / "youtube.txt").write_bytes(YOUTUBE_TXT.encode("utf-8"))
        if langue == "en":
            segments = [{"start": 0, "end": 2.5, "text": "Un petit renard."}, {"start": 2.5, "end": 5, "text": "Bonne nuit."}]
            (d / f"{nom}.transcription.json").write_bytes(json.dumps({"segments": segments}).encode())
        else:
            (d / "sous_titres.srt").write_bytes(b"1\n00:00:00,000 --> 00:00:02,000\nUne phrase factice.\n")
    return v.id


def api(methode, chemin, qui="fenetre", corps=None):
    if methode == "get":
        return Navigateur().get(chemin, **entete(qui))
    return Navigateur().post(chemin, corps or {}, content_type="application/json", **entete(qui))


def approuver(s, v, qui="fenetre"):
    return api("post", f"/api/sessions/{s.id}/videos/{v}/approuver", qui)


def apercu(s, v, qui="fenetre") -> list[dict]:
    r = api("get", f"/api/sessions/{s.id}/videos/{v}/publications", qui)
    assert r.status_code == 200, r.content
    return r.json()


def agir(s, pk, action="publier", qui="fenetre"):
    return api("post", f"/api/sessions/{s.id}/publications/{pk}/{action}", qui)


def lire(s, pk) -> m.Publication:
    with routeur.session(s):
        return m.Publication.objects.select_related("video").get(pk=pk)


def fichier(s, p: m.Publication):
    return publication.final(s, p) / p.fichier


def empreinte(s, p: m.Publication) -> str:
    return hashlib.sha256(fichier(s, p).read_bytes()).hexdigest()


def test_approuver_prepare_un_brouillon_par_langue(session, faux, envois):
    relier(session, "en")
    v = video_finie(session)
    r = approuver(session, v, "iphone")
    assert r.status_code == 200 and "brouillon(s) en, xx" in r.json()["message"], r.content
    en, xx = apercu(session, v, "iphone")
    assert (en["langue"], en["statut"], xx["langue"], xx["statut"]) == ("en", "brouillon", "xx", "brouillon")
    assert en["titre"] == "Le petit renard | Histoire factice" and en["tags"] == ["renard", "histoire du soir", "essai"]
    assert en["description"].startswith("Un petit renard cherche la lune.") and "Crédits" in en["description"] and "TAGS" not in en["description"]
    assert en["chapitres"] == ["00:00 Le terrier", "01:10 La forêt", "02:30 La lune"] and en["avis"] == [] and en["fautes"] == []
    assert (en["playlist"], en["playlist_titre"], en["destination"], en["chaine"]) == ("PLfauxUn", "Histoires du renard", "reliée", "Chaîne factice")
    assert en["enfants"] and en["ia"] and en["non_repertorie"] and en["creneau"] == ""  # première publication de la chaîne
    assert en["miniature"].endswith("miniature.jpg") and en["miniatures"] == ["miniature.jpg"] and en["video"].endswith("2099-12-01-s1e01.mp4")
    assert en["variantes"][0]["titre"] == en["titre"] and en["variante"] == 0 and en["proposition"] is None  # J11 : la sienne d abord
    assert xx["playlist"] == "" and xx["destination"] == "pas reliée" and any("pas reliée" in a for a in xx["avis"])
    p = lire(session, en["id"])
    assert p.dossier == "commun" and lire(session, xx["id"]).dossier == "xx" and p.versions[0]["numero"] == 1
    assert f"{p.planifiee_le.astimezone(UTC):%Y-%m-%d %H:%M}" == "2099-12-01 17:30"  # le créneau du soir du jour prévu (18 h 30 à Paris)
    assert "brouillons déjà prêts" in approuver(session, v).json()["message"]  # une 2e fois : rien de refait
    assert Journal.objects.filter(action="approuver", acteur="RT").exists() and envois == []  # rien ne part avant « Publier »


def test_approuver_seulement_une_video_finie(session, faux, envois):
    v = video_finie(session)
    with routeur.session(session):
        m.Morceau.objects.filter(video_id=v).update(etat="attente")
    r = approuver(session, v)
    assert r.status_code == 409 and "pas finie" in r.json()["detail"]
    with routeur.session(session):
        m.Morceau.objects.filter(video_id=v).update(etat="fini")
    t = Tache.objects.create(session_id=session.id, video_id=v, titre="Le petit renard", acteur="RT")
    assert "dans la file" in approuver(session, v).json()["detail"]
    t.delete()
    assert "Essais" in approuver(Session.objects.get(essais=True), v).json()["detail"]


def test_publier_envoie_tout_et_non_repertorie_la_premiere_fois(session, faux, envois):
    relier(session, "en")
    premiere, seconde = video_finie(session, langues=("en",)), video_finie(session, "2099-12-02-s1e02", ("en",))
    approuver(session, premiere)
    approuver(session, seconde)
    a = apercu(session, premiere)[0]
    r = agir(session, a["id"])
    assert r.status_code == 200 and "en non répertorié" in r.json()["message"], r.content
    assert envois == [("executer", "publication")] and taches.occupe("publication") == "publication"  # comptée en cours pendant son démarrage
    assert lire(session, a["id"]).statut == "en_file"
    assert publication.executer() == 0 and taches.lire("publication")["etat"] == "faite"
    p = lire(session, a["id"])
    assert p.statut == "non_repertoriee" and p.envoi["fait"] == ["video", "sous_titres", "miniature"] and "session" not in p.envoi  # pas de playlist
    meta = faux.appels_de("POST", "/upload/youtube/v3/videos")[0]["corps"]
    assert meta["status"] == {"privacyStatus": "unlisted", "selfDeclaredMadeForKids": True, "containsSyntheticMedia": True}  # sans publishAt
    # la 2e de la même chaîne : privée, programmée, playlist, sous-titres, miniature
    b = apercu(session, seconde)[0]
    assert not b["non_repertorie"] and b["creneau"] == "02/12/2099 18:30"
    assert "en privé, publique le 02/12/2099 à 18:30" in agir(session, b["id"]).json()["message"]
    assert publication.executer() == 0
    p = lire(session, b["id"])
    assert p.statut == "planifiee" and p.envoi["fait"] == ["video", "playlist", "sous_titres", "miniature"] and "session" not in p.envoi
    meta = faux.appels_de("POST", "/upload/youtube/v3/videos")[1]["corps"]
    assert meta["status"] == {"privacyStatus": "private", "selfDeclaredMadeForKids": True, "containsSyntheticMedia": True, "publishAt": "2099-12-02T17:30:00Z"}
    assert meta["snippet"] == {"title": "Le petit renard | Histoire factice", "description": p.description, "tags": ["renard", "histoire du soir", "essai"],
                               "defaultLanguage": "en", "defaultAudioLanguage": "en"}
    with routeur.session(session):
        assert faux.videos[p.identifiant_youtube]["empreinte"] == empreinte(session, p)
    assert faux.elements[-1]["snippet"] == {"playlistId": "PLfauxUn", "resourceId": {"kind": "youtube#video", "videoId": p.identifiant_youtube}}
    piste = faux.sous_titres[-1]
    assert piste["snippet"]["videoId"] == p.identifiant_youtube and piste["snippet"]["language"] == "en" and "00:00:02,500 --> 00:00:05,000\nBonne nuit." in piste["texte"]
    assert faux.miniatures[p.identifiant_youtube] == b"\xff\xd8\xff miniature factice en"
    b = apercu(session, seconde, "iphone")[0]
    assert b["statut"] == "planifiee" and b["lien"] == f"https://youtu.be/{p.identifiant_youtube}" and b["envoi"].startswith("1,3 / 1,3 Mo")
    assert len(faux.videos) == 2 and len(envois) == 2


def test_coupure_puis_reprise_sans_deuxieme_video(session, faux, envois):
    relier(session, "en")
    une, deux = video_finie(session, langues=("en",)), video_finie(session, "2099-12-02-s1e02", ("en",))
    for v in (une, deux):
        approuver(session, v)
    a, b = apercu(session, une)[0]["id"], apercu(session, deux)[0]["id"]
    agir(session, a)
    recu = 2 * MORCEAU + 1000
    faux.coupure = recu  # la connexion tombe au milieu du 3e morceau
    assert publication.executer() == 0
    p = lire(session, a)
    with routeur.session(session):
        assert p.statut == "non_repertoriee" and faux.videos[p.identifiant_youtube]["empreinte"] == empreinte(session, p)
    plages = [x["corps"]["Content-Range"] for x in faux.appels_de("PUT", "/upload/youtube/v3/videos")]
    assert f"bytes */{TAILLE}" in plages and f"bytes {recu}-{recu + MORCEAU - 1}/{TAILLE}" in plages  # reprise à l'octet reçu par YouTube
    # la seconde : tout arrive, mais la réponse se perd → YouTube dit qu'elle est là, jamais une 2e vidéo
    agir(session, b)
    faux.coupure = TAILLE
    assert publication.executer() == 0
    assert lire(session, b).statut == "planifiee" and len(faux.videos) == 2 and len(faux.appels_de("POST", "/upload/youtube/v3/videos")) == 2


def test_processus_tue_en_plein_envoi_reprend_a_l_octet_recu(session, faux, envois, monkeypatch):
    relier(session, "en")
    v = video_finie(session, langues=("en",))
    approuver(session, v)
    pk = apercu(session, v)[0]["id"]
    agir(session, pk)
    vrai = youtube.appeler

    def appeler(*a, **k):
        try:
            return vrai(*a, **k)
        except OSError:  # le processus est tué pendant l'envoi d'un morceau : YouTube en a reçu une partie
            raise Tue from None

    monkeypatch.setattr(youtube, "appeler", appeler)
    recu = 3 * MORCEAU + 4321
    faux.coupure = recu
    with pytest.raises(Tue):
        publication.executer()
    p = lire(session, pk)
    assert p.statut == "envoi" and p.envoi["session"] and p.envoi["octets"] == 3 * MORCEAU  # en base : les octets confirmés avant la coupure
    taches.ecrire("publication", {"etat": "en_cours", "pid": 4_000_000})  # son processus est mort
    monkeypatch.setattr(youtube, "appeler", vrai)
    publication.relancer()  # la boucle du noyau
    assert envois[-1] == ("executer", "publication") and len(envois) == 2
    assert publication.executer() == 0
    p = lire(session, pk)
    with routeur.session(session):
        assert faux.videos[p.identifiant_youtube]["empreinte"] == empreinte(session, p)
    assert p.statut == "non_repertoriee" and len(faux.appels_de("POST", "/upload/youtube/v3/videos")) == 1 and len(faux.videos) == 1
    plages = [x["corps"]["Content-Range"] for x in faux.appels_de("PUT", "/upload/youtube/v3/videos")]
    assert f"bytes {recu}-{recu + MORCEAU - 1}/{TAILLE}" in plages  # à l'octet que YouTube a reçu, pas à celui de la base
    publication.relancer()
    assert len(envois) == 2  # plus rien à envoyer : rien n'est relancé


def test_double_clic_puis_annuler(session, faux, envois):
    relier(session, "en")
    v = video_finie(session, langues=("en",))
    approuver(session, v)
    pk = apercu(session, v)[0]["id"]
    resultats, depart = [], threading.Barrier(2)

    def clic():
        depart.wait()
        try:
            resultats.append(publication.publier(session, pk, "RT"))
        except Refus as e:
            resultats.append(e)
        finally:
            connections.close_all()

    fils = [threading.Thread(target=clic) for _ in range(2)]
    for f in fils:
        f.start()
    for f in fils:
        f.join(30)
    assert sorted(type(r).__name__ for r in resultats) == ["Refus", "str"]
    assert str(next(r for r in resultats if isinstance(r, Refus))) == "déjà dans la file d'envoi"
    r = agir(session, pk, "publier", "iphone")
    assert r.status_code == 409 and r.json()["detail"] == "déjà dans la file d'envoi" and envois == [("executer", "publication")]
    assert "redevient un brouillon" in agir(session, pk, "annuler").json()["message"]
    assert lire(session, pk).statut == "brouillon" and publication.executer() == 0 and not faux.videos  # rien n'est parti


def test_langue_sans_chaine_brouillon_mais_envoi_refuse(session, faux, envois):
    relier(session, "en")
    v = video_finie(session)
    approuver(session, v)
    xx = apercu(session, v)[1]
    r = agir(session, xx["id"])
    assert r.status_code == 409 and "YouTube (xx) : chaîne pas reliée" in r.json()["detail"]
    assert lire(session, xx["id"]).statut == "brouillon" and envois == []


def test_erreur_en_clair_alertee_puis_reprendre(session, faux, envois, monkeypatch):
    relier(session, "en")
    v = video_finie(session, langues=("en",))
    approuver(session, v)
    pk = apercu(session, v)[0]["id"]
    agir(session, pk)
    faux.refuser = True  # Google retire l'accès entre le clic et l'envoi
    youtube._acces.clear()
    assert publication.executer() == 1
    p = lire(session, pk)
    assert p.statut == "erreur" and "relier la chaîne" in p.envoi["erreur"]
    e = taches.lire("publication")
    assert e["etat"] == "erreur" and e["alertes"][0].startswith("« Le petit renard | Histoire factice » (en) : publication en erreur — YouTube : Google a refusé le jeton")
    assert e["alertes"][0] in etat.etat()["alertes"]
    vus = []  # la boucle du noyau la notifie (la fenêtre en fait une notification)
    monkeypatch.setattr(evenements, "publier", lambda t, **d: vus.append((t, d)))
    monkeypatch.setattr(serveur.file, "tour", lambda: "")
    monkeypatch.setattr(serveur.depot, "traiter", lambda: None)
    serveur.tour({"sauvegarde": taches.lire("sauvegarde"), "file": [], "publication": {"publication": {}, "paquets": taches.lire("paquets")}}, datetime.now())
    assert ("alerte", {"titre": "Publication", "message": e["alertes"][0]}) in vus
    assert apercu(session, v)[0]["erreur"] == p.envoi["erreur"]
    faux.refuser = False
    relier(session, "en")
    assert "envoi repris" in agir(session, pk, "reprendre", "iphone").json()["message"]
    assert publication.executer() == 0 and lire(session, pk).statut == "non_repertoriee"
    assert agir(session, pk, "reprendre").status_code == 409


def test_jamais_un_clic_de_la_simulation_vers_une_vraie_chaine(session, faux, envois, monkeypatch):
    relier(session, "en")
    v = video_finie(session, langues=("en",))
    approuver(session, v)
    pk = apercu(session, v)[0]["id"]
    agir(session, pk)
    monkeypatch.setattr(etat, "simulation", lambda: False)  # passée en réel entre le clic et l'envoi
    assert publication.executer() == 1 and "le mode a changé" in lire(session, pk).envoi["erreur"]
    assert not faux.appels_de("POST", "/upload/youtube/v3/videos")
    assert "redevient un brouillon" in agir(session, pk, "annuler").json()["message"]


def test_retoucher_choisir_et_droits(session, faux, envois):
    relier(session, "en")
    v = video_finie(session, langues=("en",))
    base = f"/api/sessions/{session.id}"
    assert approuver(session, v, "claude").status_code == 403
    approuver(session, v)
    pk = apercu(session, v, "claude")[0]["id"]  # Claude lit l'aperçu (droit « voir »), sans plus
    for qui in ("claude", "iphone"):  # retoucher et choisir : à la fenêtre seulement
        assert api("post", f"{base}/publications/{pk}/retoucher", qui, {"titre": "x", "description": "y"}).status_code == 403
        assert api("post", f"{base}/publications/{pk}/choisir", qui, {"playlist": ""}).status_code == 403
    for action in ("publier", "reprendre", "annuler"):
        assert agir(session, pk, action, "claude").status_code == 403
    for nom, cible in (("approuver", v), ("publier", pk), ("reprendre", pk)):
        with pytest.raises(Refus, match="seul RT"):
            getattr(publication, nom)(session, cible, "claude")
    r = api("post", f"{base}/publications/{pk}/retoucher", "fenetre", {"titre": "Un autre titre", "description": "Une autre description."})
    assert r.json()["message"] == "version 2 du titre et de la description"
    r = api("post", f"{base}/publications/{pk}/retoucher", "fenetre", {"titre": "Un <titre>", "description": ""})
    assert r.status_code == 409 and "refusés par YouTube" in r.json()["detail"]
    for choix, refus in (({"playlist": "PLinconnue"}, "playlist inconnue"), ({"miniature": "autre.jpg"}, "miniature inconnue"),
                         ({"miniature": "..\\youtube.txt"}, "miniature inconnue"), ({"jour": "2000-01-01", "horaire": "18:30"}, "passé")):
        r = api("post", f"{base}/publications/{pk}/choisir", "fenetre", choix)
        assert r.status_code == 409 and refus in r.json()["detail"], choix
    r = api("post", f"{base}/publications/{pk}/choisir", "fenetre", {"playlist": "PLfauxDeux", "jour": "2099-12-03", "horaire": "19:00"})
    assert r.json()["message"] == "choisi : playlist Histoires du hibou, créneau 03/12/2099 19:00"
    a = apercu(session, v)[0]
    assert (a["titre"], a["versions"], a["playlist_titre"]) == ("Un autre titre", 2, "Histoires du hibou")
    assert agir(session, pk, "publier", "iphone").status_code == 200 and publication.executer() == 0  # Publier : aussi depuis l'iPhone
    assert api("post", f"{base}/publications/{pk}/retoucher", "fenetre", {"titre": "x", "description": "y"}).status_code == 409  # parti


# ---- relevé quotidien des statistiques ----

from datetime import timedelta  # noqa: E402

from django.utils import timezone  # noqa: E402

from fabrique.noyau.models import Parametre  # noqa: E402
from fabrique.publication import statistiques  # noqa: E402


def publiee(s, langue="xx", ident="vidFaux1", jours=5, **k) -> m.Publication:
    with routeur.session(s):
        v = m.Video.objects.create(titre="Le petit renard", nom=f"2099-12-0{jours}-{ident}", script={}, recette={})
        return m.Publication.objects.create(video=v, langue=langue, dossier=langue, identifiant_youtube=ident, statut="planifiee", simulation=True,
                                            planifiee_le=timezone.now() - timedelta(days=jours), paquets={"fini": True}, **k)


def stats(s, pub=None) -> dict:
    with routeur.session(s):
        return {f"{x.date}": (x.vues, x.abonnes) for x in m.StatistiqueJour.objects.filter(publication=pub).order_by("date")}


def test_releve_quotidien_chaine_et_videos_publiees(session, faux, monkeypatch):
    relier(session)
    pub = publiee(session)
    publiee(session, ident="vidEssai", non_repertorie=True)  # un essai non répertorié : jamais relevé
    assert Session.objects.filter(essais=True).count() == 1  # la session Essais (jamais relevée) : une seule, toujours
    j = [f"{timezone.localdate() - timedelta(days=n)}" for n in range(6, -1, -1)]
    faux.statistiques = {faux_youtube.CHAINE_STATS: {d: {"views": 10 + i, "subscribersGained": 1} for i, d in enumerate(j[:-2])},
                         "vidFaux1": {d: {"views": 3, "estimatedMinutesWatched": 90} for d in j[1:-2]}}
    faux.travaux["job1"] = {"id": "job1", "reportTypeId": "channel_reach_basic_a1"}  # J11, portée : un rapport « reach » par jour, CSV
    faux.portee = {"vidFaux1": (1000, 0.05), "vidAutre": (10, 0.5)}
    taches.fichier("releve").unlink(missing_ok=True)
    Parametre.ecrire("releve_jour", "")
    assert statistiques.executer() == 0
    e = taches.lire("releve")
    assert e["etat"] == "fait" and f"{session.nom} (xx) : chaîne 5 jour(s), 1 vidéo(s) 4 jour(s), portée 3 jour(s)" in e["faits"] and not [f for f in e["faits"] if "Essais" in f]
    assert stats(session) == {d: (10 + i, 1) for i, d in enumerate(j[:-2])} and set(stats(session, pub)) == set(j[1:-2])
    with routeur.session(session):
        assert m.StatistiqueJour.objects.get(publication=pub, date=j[1]).heures == 1.5
    assert Parametre.lire("releve_jour") == f"{timezone.localdate()}" and not statistiques.du(datetime.now().replace(hour=23))
    filtres = [a["params"].get("filters", "") for a in faux.appels_de("GET", "/v2/reports")]
    assert filtres[-2:] == ["", "video==vidFaux1"] and "video==vidEssai" not in filtres and faux.appels_de("GET", "/youtube/v3/channels")  # l'API Data aussi : le projet Google reste actif
    # le lendemain : les 3 derniers jours connus relus, un chiffre corrigé par YouTube remplace l'ancien
    faux.statistiques[faux_youtube.CHAINE_STATS][j[4]] = {"views": 99}
    ligne = lambda: next(f for f in taches.lire("releve")["faits"] if f.startswith(f"{session.nom} (xx)"))  # noqa: E731
    assert statistiques.executer() == 0 and ligne().endswith("portée 0 jour(s)")  # rapports « reach » déjà lus : pas relus
    assert faux.appels_de("GET", "/v2/reports")[-2]["params"]["startDate"] == j[2] and stats(session)[j[4]] == (99, 0)
    with routeur.session(session):
        x = m.StatistiqueJour.objects.get(publication=pub, date=timezone.localdate() - timedelta(days=2))
        assert (x.impressions, x.ctr, x.vues) == (1000, 5.0, 3)  # lignes additionnées, taux pondéré ; les vues de l'API Analytics gardées
    faux.travaux.clear()  # pas de travail « reach » chez YouTube : créé au relevé suivant
    assert statistiques.executer() == 0 and [t["reportTypeId"] for t in faux.travaux.values()] == ["channel_reach_basic_a1"]


def test_releve_refuse_par_le_quota_puis_reessai(session, faux, monkeypatch):
    relier(session)
    faux.analytics_refus = 403
    Parametre.ecrire("releve_jour", "")
    assert statistiques.executer() == 1
    e = taches.lire("releve")
    assert e["etat"] == "erreur" and f"relevé des statistiques de {session.nom} (xx) reporté : YouTube a répondu 403 (quotaExceeded)" in e["alertes"]
    assert any("relevé des statistiques" in a for a in etat.etat()["alertes"])
    dix = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    taches.ecrire("releve", {**e, "fin": dix.isoformat()})
    assert not statistiques.du(dix + timedelta(minutes=30)) and statistiques.du(dix + timedelta(minutes=61))
    faux.analytics_refus = None
    assert statistiques.executer() == 0 and taches.lire("releve")["etat"] == "fait"


def test_releve_lance_par_le_noyau_une_fois_par_jour_installe_seulement(monkeypatch):
    lances = []
    monkeypatch.setattr(statistiques, "lancer", lambda acteur: lances.append(acteur))
    monkeypatch.setattr(taches, "lancer", lambda *a: None)
    monkeypatch.setattr(taches, "occupe", lambda *a: "")
    Parametre.ecrire("releve_jour", "")
    taches.fichier("releve").unlink(missing_ok=True)
    matin, midi = datetime.now().replace(hour=8, minute=59), datetime.now().replace(hour=12)
    serveur.tour({}, midi)
    assert lances == []  # le dépôt du code : jamais
    monkeypatch.setattr(programme, "installee", lambda: True)
    serveur.tour({}, matin)
    assert lances == []
    serveur.tour({}, midi)
    assert lances == ["noyau"]
    Parametre.ecrire("releve_jour", f"{midi.date()}")
    serveur.tour({}, midi.replace(hour=13))
    assert lances == ["noyau"]


# ---- paquets prêts à poster ----

FICHES_ESSAI = [
    {"id": "vertical", "nom": "Réseau vertical", "largeur": 180, "hauteur": 320, "duree_min_s": 3, "duree_max_s": 9, "parties_max": 3, "poids_max_mo": 5,
     "texte_max": 120, "titre_max": 0, "hashtags_max": 2},
    {"id": "large", "nom": "Réseau large", "largeur": 320, "hauteur": 180, "duree_min_s": 1, "duree_max_s": 60, "parties_max": 1, "poids_max_mo": 5,
     "texte_max": 5000, "titre_max": 0, "hashtags_max": 5},
    {"id": "court", "nom": "Réseau court", "largeur": 180, "hauteur": 320, "duree_min_s": 1, "duree_max_s": 5, "parties_max": 1, "poids_max_mo": 5,
     "texte_max": 100, "titre_max": 0, "hashtags_max": 1},
    {"id": "epingle", "nom": "Réseau à titre", "largeur": 200, "hauteur": 300, "duree_min_s": 1, "duree_max_s": 30, "parties_max": 1, "poids_max_mo": 5,
     "texte_max": 40, "titre_max": 10, "hashtags_max": 1}]


def ffmpeg(*args):
    from fabrique.moteur.faux import lancer, programme as exe

    lancer(exe("ffmpeg"), "-y", "-v", "error", *args)


def vraie_video(f, secondes=20):
    """16:9, un son coupé de silences de 0,6 s toutes les 7 s (milieux à 7,3 et 14,3 s : les coupes attendues)."""
    ffmpeg("-f", "lavfi", "-i", f"testsrc2=s=320x180:r=12:d={secondes}", "-f", "lavfi", "-i", f"aevalsrc=0.4*sin(2*PI*330*t)*gte(mod(t\\,7)\\,0.6):s=22050:d={secondes}",
           "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", f)


def test_paquets_conformes_aux_fiches_parties_aux_silences_et_reprise(session, faux, envois, monkeypatch):
    monkeypatch.setattr(paquets, "fiches", lambda: FICHES_ESSAI)
    v = video_finie(session, langues=("en",))
    assert approuver(session, v).status_code == 200
    pub = apercu(session, v)[0]
    vraie_video(pub["video"])
    ffmpeg("-f", "lavfi", "-i", "color=c=orange:s=640x360", "-frames:v", "1", pub["miniature"])
    assert paquets.suivante(set())[1] == pub["id"]
    assert paquets.executer() == 0 and taches.lire("paquets")["etat"] == "faits" and paquets.suivante(set()) is None
    r = api("get", f"/api/sessions/{session.id}/videos/{v}/paquets", "iphone")
    assert r.status_code == 200
    p = {x["reseau"]: x for x in r.json()}
    assert [x["etat"] for x in p.values()] == ["fait", "fait", "impossible", "fait"] and not [x for x in p.values() if x["fautes"]]
    assert p["court"]["raison"].startswith("vidéo de 0.3 min : Réseau court prend ") and "déclinaison courte" in p["court"]["raison"]
    parties = p["vertical"]["fichiers"]
    assert [(x["largeur"], x["hauteur"]) for x in parties] == [(180, 320)] * 3 and all(x["duree_s"] <= 9 for x in parties)
    assert abs(parties[0]["duree_s"] - 7.3) < 0.2 and abs(parties[0]["duree_s"] + parties[1]["duree_s"] - 14.3) < 0.3  # coupées aux silences
    assert abs(sum(x["duree_s"] for x in parties) - 20) < 0.5
    assert [(x["largeur"], x["hauteur"]) for x in p["large"]["fichiers"]] == [(320, 180)] and p["large"]["miniature"] == "miniature.jpg"
    mi = paquets.mesure(Path(p["vertical"]["dossier"]) / "miniature.jpg")
    assert (mi["largeur"], mi["hauteur"]) == (180, 320)
    # les textes : titre (n/3) en tête, sans les lignes de chapitres, hashtags limités, coupés aux limites de la fiche
    t = p["vertical"]["textes"]
    assert len(t) == 3 and t[0]["texte"].startswith("Le petit renard | Histoire factice (1/3)\n\n") and t[0]["texte"].endswith("\n\n#renard #histoiredusoir")
    assert all(len(x["texte"]) <= 120 and "00:00" not in x["texte"] and "02:30" not in x["texte"] for x in t)
    e = p["epingle"]["textes"][0]
    assert e["titre"] == "Le petit r" and len(e["texte"]) <= 40 and e["texte"].endswith("#renard") and "…" in e["texte"]
    assert "Crédits : voix et images factices." in p["large"]["textes"][0]["texte"]
    # un fichier du paquet : à l'iPhone et à la fenêtre ; jamais à Claude, jamais un autre nom
    nom = parties[1]["nom"]
    url = f"/api/sessions/{session.id}/publications/{pub['id']}/paquets/vertical/"
    r = api("get", url + nom, "iphone")
    assert r.status_code == 200 and b"".join(r.streaming_content) == (Path(p["vertical"]["dossier"]) / nom).read_bytes()
    assert api("get", url + nom, "claude").status_code == 403 and api("get", f"/api/sessions/{session.id}/videos/{v}/paquets", "claude").status_code == 403
    for autre in ("..%2F..%2Fyoutube.txt", "inconnu.mp4", "miniature.tmp.jpg"):
        assert api("get", url + autre, "iphone").status_code in (404, 409), autre
    # processus tué après un réseau : la reprise ne refait que les autres
    large = Path(p["large"]["dossier"]) / p["large"]["fichiers"][0]["nom"]
    avant = large.stat().st_mtime_ns
    with routeur.session(session):
        m.Publication.objects.filter(pk=pub["id"]).update(paquets={"large": lire(session, pub["id"]).paquets["large"]})
    assert paquets.executer() == 0 and large.stat().st_mtime_ns == avant and lire(session, pub["id"]).paquets["vertical"]["etat"] == "fait"
    # refaire : la fenêtre seulement
    assert api("post", f"/api/sessions/{session.id}/videos/{v}/paquets", "iphone").status_code == 403
    assert "à refaire" in api("post", f"/api/sessions/{session.id}/videos/{v}/paquets").json()["message"] and paquets.suivante(set())


def test_paquet_en_erreur_alerte_et_les_autres_reseaux_continuent(session, faux, envois, monkeypatch):
    monkeypatch.setattr(paquets, "fiches", lambda: [FICHES_ESSAI[1], {**FICHES_ESSAI[1], "id": "casse", "nom": "Réseau cassé", "largeur": -5}])
    v = video_finie(session, langues=("en",))
    approuver(session, v)
    vraie_video(apercu(session, v)[0]["video"], 4)
    ffmpeg("-f", "lavfi", "-i", "color=c=orange:s=640x360", "-frames:v", "1", apercu(session, v)[0]["miniature"])
    assert paquets.executer() == 1
    p = {x["reseau"]: x for x in paquets.lister(session, v)}
    assert p["large"]["etat"] == "fait" and p["casse"]["etat"] == "erreur" and p["casse"]["raison"]
    a = taches.lire("paquets")["alertes"]
    assert len(a) == 1 and a[0].startswith("paquet Réseau cassé de « Le petit renard | Histoire factice » (en) : ") and a[0] in etat.etat()["alertes"]


def test_coupes_aux_silences():
    assert paquets.coupes(20, 3, [0.3, 7.3, 14.3], 9) == [0.0, 7.3, 14.3, 20]
    assert paquets.coupes(20, 2, [], 10) == [0.0, 10.0, 20]  # sans silence : parties égales
    b = paquets.coupes(30, 2, [3.0], 16)  # un silence trop tôt (la 2e partie dépasserait 16 s) : ignoré
    assert b == [0.0, 15.0, 30] and all(y - x <= 16 for x, y in zip(b, b[1:]))


# ---- vidéo d'essai copiée pour les gestes de RT (recette J4) ----

def test_copie_d_essai_toujours_non_repertoriee_et_marquee(session, faux, envois):
    essais = Session.objects.get(essais=True)
    with routeur.session(essais):
        m.Langue.objects.get_or_create(code="xx", defaults={"nom": "Langue factice"})
    source = video_finie(essais, nom="2099-12-09-essai", langues=("en",))
    cible = Session.objects.filter(essais=False).order_by("cree").first()
    message = publication.copier_essai(source, "PC")
    copie = message.split("(vidéo ")[1].split(")")[0]
    with routeur.session(cible):
        v = m.Video.objects.get(id=copie)
        assert v.essai and v.titre == "ESSAI PC — Le petit renard" and v.morceaux.filter(etat="fini").count() == 1
    finals = list((settings.SESSIONS / cible.dossier / "videos" / copie).rglob("final"))
    assert len(finals) == 1 and (finals[0] / "2099-12-09-essai.mp4").is_file() and not list((settings.SESSIONS / cible.dossier / "videos" / copie).rglob("transcription"))
    with pytest.raises(Refus):
        publication.copier_essai("inconnue", "PC")
    # dans la session réelle : une publication déjà partie n'y change rien, la copie d'essai part en non répertorié, titre marqué
    with routeur.session(cible):  # la première session réelle de la base des tests vient d'un autre test : sa langue posée ici
        m.Langue.objects.get_or_create(code="en", defaults={"nom": "Anglais"})
    relier(cible, "en")
    with routeur.session(cible):
        autre = m.Video.objects.create(titre="Déjà publiée", nom="2099-12-10-x", script={}, recette={})
        m.Publication.objects.create(video=autre, langue="en", dossier="commun", statut="planifiee", simulation=True, identifiant_youtube="dejaFaux", paquets={"fini": True})
    assert approuver(cible, copie).status_code == 200
    p = apercu(cible, copie)[0]
    assert p["titre"].startswith("ESSAI — ") and p["non_repertorie"] and p["creneau"] == ""
    assert agir(cible, p["id"]).status_code == 200 and publication.executer() == 0
    assert lire(cible, p["id"]).statut == "non_repertoriee" and faux.appels_de("POST", "/upload/youtube/v3/videos")[-1]["corps"]["status"]["privacyStatus"] == "unlisted"


# ---- corrections de la relecture à froid de J4 ----

def test_passer_en_mode_reel_clic_de_rt_refuse_pendant_un_envoi(session, faux, envois):
    from fabrique.noyau.models import Parametre

    assert api("post", "/api/mode", "claude", {"reel": True}).status_code == 403
    assert api("post", "/api/mode", "iphone", {"reel": True}).status_code == 403
    relier(session, "en")
    v = video_finie(session, langues=("en",))
    approuver(session, v)
    pk = apercu(session, v)[0]["id"]
    assert agir(session, pk).status_code == 200  # en file d'envoi
    r = api("post", "/api/mode", "fenetre", {"reel": True})
    assert r.status_code == 409 and Parametre.lire("simulation", "oui") == "oui"
    taches.fichier("publication").unlink(missing_ok=True)  # la tâche d'envoi (jamais lancée ici) n'est plus comptée en démarrage
    r = api("post", "/api/mode", "fenetre", {"reel": True})
    assert r.status_code == 409 and "envoi" in r.json()["detail"]
    assert agir(session, pk, "annuler").status_code == 200
    r = api("post", "/api/mode", "fenetre", {"reel": True})
    assert r.status_code == 200 and Parametre.lire("simulation") == "non" and Journal.objects.filter(action="mode", acteur="RT").exists()
    assert api("post", "/api/mode", "fenetre", {"reel": False}).status_code == 200 and Parametre.lire("simulation") == "oui"


def test_creneau_trop_proche_pendant_l_envoi(session, faux, envois, monkeypatch):
    relier(session, "en")
    for nom in ("2099-12-01-s1e01", "2099-12-02-s1e02"):  # la 2e de la chaîne : privée, programmée
        v = video_finie(session, nom=nom, langues=("en",))
        approuver(session, v)
        pk = apercu(session, v)[0]["id"]
        assert agir(session, pk).status_code == 200
    garder = publication._sauver

    def tard(pub):  # après le premier morceau, le créneau n'est plus qu'à une minute (envoi lent)
        if pub.envoi.get("octets"):
            pub.planifiee_le = timezone.now() + timedelta(minutes=1)
        garder(pub)

    monkeypatch.setattr(publication, "_sauver", tard)
    assert publication.executer() == 1
    p = lire(session, pk)
    assert p.statut == "erreur" and "créneau trop proche" in p.envoi["erreur"] and not p.identifiant_youtube


def test_coupes_entre_deux_phrases_de_la_transcription(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"")
    (tmp_path / "v.transcription.json").write_bytes(json.dumps({"segments": [{"start": 0, "end": 6.8, "text": "Une."}, {"start": 7.4, "end": 13, "text": "Deux."},
                                                                             {"start": 14, "end": 19, "text": "Trois."}]}).encode())
    assert paquets.entre_phrases(video) == [7.1, 13.5]
    assert paquets.coupes(20, 3, paquets.entre_phrases(video), 9) == [0.0, 7.1, 13.5, 20]


def test_refaire_les_paquets_pendant_leur_travail(session, faux, envois, monkeypatch):
    monkeypatch.setattr(paquets, "fiches", lambda: FICHES_ESSAI[1:2] + [{**FICHES_ESSAI[1], "id": "autre", "nom": "Autre réseau"}])
    v = video_finie(session, langues=("en",))
    approuver(session, v)
    pk = apercu(session, v)[0]["id"]
    vrai = paquets.faire_reseau

    def puis_refaire(*a, **k):
        r = vrai(*a, **k)
        assert api("post", f"/api/sessions/{session.id}/videos/{v}/paquets").status_code == 200  # RT clique pendant le travail
        return r

    monkeypatch.setattr(paquets, "faire_reseau", puis_refaire)
    vraie_video(apercu(session, v)[0]["video"], 4)
    ffmpeg("-f", "lavfi", "-i", "color=c=orange:s=640x360", "-frames:v", "1", apercu(session, v)[0]["miniature"])
    paquets.faire(session, pk)
    assert lire(session, pk).paquets == {}  # le travail en cours n'a rien écrit par-dessus : tout est à refaire
    monkeypatch.setattr(paquets, "faire_reseau", vrai)
    assert paquets.suivante(set()) == (session, pk) and paquets.executer() == 0
    assert {r: x["etat"] for r, x in lire(session, pk).paquets.items() if r != "fini"} == {"large": "fait", "autre": "fait"}


def test_variante_choisie_apres_publication_change_le_titre_chez_youtube(session, faux, monkeypatch):
    """J11 : une vidéo en ligne → videos.update (snippet entier, catégorie comprise) ; un refus de YouTube est dit en clair, rien n'est noté,
    et le clic suivant refait le changement."""
    from fabrique.publication import variantes

    relier(session)
    faux.videos["vidFaux1"] = {"ressource": {"kind": "youtube#video", "id": "vidFaux1", "snippet": {"title": "Titre A", "categoryId": "22"}}}
    pub = publiee(session, titre="Titre A", variantes=[{"titre": "Titre A", "miniature": "", "note": 5.0, "raisons": [], "depuis": None, "portee": None},
                                                       {"titre": "Titre B", "miniature": "", "note": 7.0, "raisons": [], "depuis": None, "portee": None}])
    with monkeypatch.context() as mp:
        mp.setattr(youtube, "appeler", lambda *a, **k: (_ for _ in ()).throw(youtube.ErreurYoutube(403, "quotaExceeded")))
        with pytest.raises(Refus, match="YouTube a refusé"):
            variantes.choisir(session, pub.pk, 1, "rt")
    assert faux.videos["vidFaux1"]["ressource"]["snippet"]["title"] == "Titre A" and lire(session, pub.pk).variante == 0
    assert variantes.choisir(session, pub.pk, 1, "rt").startswith("variante 2 posée chez YouTube")
    p = lire(session, pub.pk)
    assert faux.videos["vidFaux1"]["ressource"]["snippet"] == {"title": "Titre B", "categoryId": "22", "channelId": faux_youtube.CHAINE[0]}
    assert (p.titre, p.variante, p.variantes[1]["depuis"], p.variantes[0]["jusqu_a"]) == ("Titre B", 1, f"{timezone.localdate()}", f"{timezone.localdate()}")
