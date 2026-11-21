"""API locale : jetons, droits des quatre appelants, les trois gestes hors de portée de Claude et de l'assistant, contrat commun avec la
fenêtre, flux d'événements."""
import threading

import pytest
from django.conf import settings
from django.test import Client as Navigateur

from fabrique import __main__ as porte
from fabrique.fenetre import client as cl
from fabrique.noyau import api, bases, evenements, jetons, serveur, taches
from fabrique.noyau.api import DROITS, GESTES


@pytest.fixture
def jeton():
    jetons.tirer(settings.DONNEES)
    return lambda appelant: {"HTTP_AUTHORIZATION": f"Bearer {jetons.lire(settings.DONNEES, appelant)}"}


def operations():
    for _, routeur in api.api._routers:
        for chemin, vue in routeur.path_operations.items():
            for op in vue.operations:
                yield chemin, op


def test_sans_jeton_rien(jeton):
    assert Navigateur().get("/api/etat").status_code == 401
    assert Navigateur().get("/api/etat", HTTP_AUTHORIZATION="Bearer faux").status_code == 401


def test_claude_lit_mais_n_agit_pas(jeton):
    n = Navigateur()
    assert n.get("/api/sessions", **jeton("claude")).status_code == 200
    assert n.get("/api/etat", **jeton("claude")).json()["mode"] == "simulation"
    for chemin in ("/api/sauvegardes", "/api/sauvegardes/x.zip/restaurer", "/api/versions/mettre-a-jour", "/api/cles/gemini", "/api/arreter"):
        r = n.post(chemin, {"valeur": "k"}, content_type="application/json", **jeton("claude"))
        assert r.status_code == 403, chemin


def test_la_fenetre_lit_une_session_dans_sa_propre_base(jeton):
    s = bases.creer("Lue par l'API")
    r = Navigateur().get(f"/api/sessions/{s.id}", **jeton("fenetre"))
    assert r.json() == {"id": s.id, "nom": "Lue par l'API"}
    assert Navigateur().get("/api/sessions/inconnue", **jeton("fenetre")).status_code == 404


def test_un_refus_est_dit(jeton):
    r = Navigateur().post("/api/sauvegardes/inconnue.zip/restaurer", **jeton("fenetre"))
    assert r.status_code == 409 and "inconnue" in r.json()["detail"]
    r = Navigateur().post("/api/versions/mettre-a-jour", **jeton("fenetre"))
    assert r.status_code == 409 and "développement" in r.json()["detail"]


def test_chaque_route_declare_un_droit_connu():
    connus = set().union(*DROITS.values())
    vues = list(operations())
    assert len(vues) >= 13
    for chemin, op in vues:
        assert getattr(op.view_func, "droit", None) in connus, chemin


def test_les_trois_gestes_jamais_pour_claude_ni_l_assistant():
    assert GESTES <= DROITS["fenetre"]
    assert DROITS["iphone"] & GESTES == {"approuver", "publier"}  # Fabriquer en vrai : au PC seulement
    for appelant in ("claude", "assistant"):
        assert not DROITS[appelant] & GESTES
    # aucune commande de Claude ne mène à une route qui demande un geste (ni à une écriture à J1)
    droits = {(op.methods[0], "/api/" + chemin.lstrip("/")): op.view_func.droit for chemin, op in operations()}
    for nom in porte.COMMANDES_CLAUDE.values():
        methode, chemin, _ = cl.APPELS[nom]
        assert droits[(methode, chemin)] in DROITS["claude"]
    # aucune tâche automatique ni détachée n'est un geste ; la boucle du noyau ne lance que la sauvegarde, et ne relance qu'un envoi déjà
    # lancé par RT : « en_file » n'est posé que par Publier et Reprendre, refusés à tout autre acteur que RT
    assert not set(taches.TACHES) & GESTES
    import inspect
    import re

    from fabrique.garde import Refus
    from fabrique.publication import publication

    with open(serveur.__file__, encoding="utf-8") as f:
        source = f.read()
    assert re.findall(r'taches\.lancer\("(\w+)"', source) == ["sauvegarde"] and re.findall(r"(?<![/\w])publication\.(\w+)", source) == ["relancer"]  # appelée ou passée à la boucle
    poseurs = {n for n, fn in inspect.getmembers(publication, inspect.isfunction) if fn.__module__ == publication.__name__ and 'statut="en_file"' in inspect.getsource(fn)}
    assert poseurs == {"publier", "reprendre"}
    for nom in poseurs:
        with pytest.raises(Refus, match="seul RT"):
            getattr(publication, nom)(None, 1, "assistant")


def test_la_fenetre_et_le_noyau_parlent_le_meme_contrat():
    doc = api.api.get_openapi_schema()
    for nom, (methode, chemin, schema) in cl.APPELS.items():
        op = doc["paths"][chemin][methode.lower()]
        reponse = op["responses"][200]["content"]["application/json"]["schema"]
        attendu = getattr(schema, "__args__", (None,))[0] or schema
        ref = reponse.get("items", reponse)["$ref"]
        assert ref == f"#/components/schemas/{attendu.__name__}", nom
        assert ("items" in reponse) == hasattr(schema, "__args__"), nom
    corps = doc["paths"]["/api/cles/{nom}"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert corps == {"$ref": "#/components/schemas/Valeur"}
    clients = {(m, c) for m, c, _ in cl.APPELS.values()} | {("GET", "/api/evenements"), ("GET", "/api/sessions/{id}/publications/{pub}/paquets/{reseau}/{nom}")}  # fichier : l'iPhone
    clients |= {("POST", "/api/estimation"), ("POST", "/api/brouillons/session"), ("POST", "/api/sessions/{id}/brouillons/video")}  # les outils de l'assistant (noyau)
    assert {(m.upper(), c) for c, ops in doc["paths"].items() for m in ops} == clients  # aucune route que la fenêtre ignore


def test_flux_d_evenements(libre_port, jeton):
    from waitress import create_server

    from fabrique.wsgi import application

    s = create_server(application, host="127.0.0.1", port=libre_port, threads=4)
    threading.Thread(target=s.run, daemon=True).start()
    fini = threading.Event()

    def publier():
        while not fini.wait(0.2):  # tant que l'abonnement n'est pas vu
            evenements.publier("essai", n=1)
    threading.Thread(target=publier, daemon=True).start()
    try:
        type_, d = next(cl.Client(port=libre_port).evenements())
        assert type_ == "essai" and d["n"] == 1
    finally:
        fini.set()
        s.close()


def test_tour_du_noyau_publie_et_ecrit_l_etat(monkeypatch):
    vus = []
    monkeypatch.setattr(evenements, "publier", lambda t, **d: vus.append(t))
    from datetime import datetime

    vu = serveur.tour({}, datetime.now())
    assert vus == ["etat"] and (settings.DONNEES / "etat.json").is_file()
    taches.ecrire("sauvegarde", {"etat": "faite", "fin": "x"})
    serveur.tour(vu, datetime.now())
    assert vus[1:] == ["sauvegarde", "etat"]
