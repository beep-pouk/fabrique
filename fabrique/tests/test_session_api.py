"""L'API d'une session (noms factices) : scripts et versions, univers, vidéos, santé de la machine ; « Fabriquer » réservé à la fenêtre (RT)."""
import json
from pathlib import Path
from datetime import date, datetime, timezone

import pytest
from django.conf import settings
from django.test import Client as Navigateur

from fabrique.moteur import carte
from fabrique.noyau import bases, jetons, routeur
from fabrique.noyau.models import Tache
from fabrique.session import models as m

SCENARIO = {"format": 2, "title": "Une histoire factice", "scenes": [{"id": 1, "narration": "Il était une fois.", "image": "a quiet glade"}]}


@pytest.fixture
def session(request):
    s = bases.creer(f"Session {request.node.name}")
    with routeur.session(s):
        sc = m.Script.objects.create(code="s1e01", titre="Une histoire factice", langue="en", statut="scenario", date_prevue=date(2026, 12, 1))
        quand = datetime(2026, 11, 10, 21, 0, tzinfo=timezone.utc)
        m.VersionScript.objects.create(script=sc, numero=1, auteur="import", date=quand, contenu={**SCENARIO, "title": "Ancienne"}, validee=True)
        m.VersionScript.objects.create(script=sc, numero=2, auteur="RT", date=quand, contenu=SCENARIO, validee=False, regles={"erreurs": []})
        p = m.Personnage.objects.create(nom="Ami Un", role="ami")
        m.Reference.objects.create(personnage=p, fichier="univers/personnages/ami_un/reference.png", date=quand)
        m.Lieu.objects.create(nom="Clairière", description="calme")
        m.Langue.objects.create(code="xx", nom="Langue factice", outil_voix="outil_factice", voix_validee=True)
    d = settings.SESSIONS / s.dossier / "reglages"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text("{}", encoding="utf-8")
    yield s
    Tache.objects.all().delete()


def entete(qui: str) -> dict:
    jetons.tirer(settings.DONNEES)
    return {"HTTP_AUTHORIZATION": f"Bearer {jetons.lire(settings.DONNEES, qui)}"}


def test_scripts_univers_videos(session):
    n = Navigateur()
    assert n.get(f"/api/sessions/{session.id}/scripts", **entete("claude")).json() == [
        {"code": "s1e01", "titre": "Une histoire factice", "statut": "scenario", "date_prevue": "2026-12-01", "versions": 2, "validee": False}]
    d = n.get(f"/api/sessions/{session.id}/scripts/s1e01", **entete("fenetre")).json()
    assert [v["numero"] for v in d["versions"]] == [2, 1] and d["contenu"] == SCENARIO and d["regles"] == {"erreurs": []}
    assert n.get(f"/api/sessions/{session.id}/scripts/s9e99", **entete("fenetre")).status_code == 404
    u = n.get(f"/api/sessions/{session.id}/univers", **entete("fenetre")).json()
    assert u["personnages"] == [{"nom": "Ami Un", "role": "ami", "statut": "actif", "references": 1}] and u["langues"][0]["code"] == "xx"
    assert n.get(f"/api/sessions/{session.id}/videos", **entete("fenetre")).json() == []


def test_fabriquer_est_un_geste_de_rt(session, monkeypatch):
    n = Navigateur()
    chemin = f"/api/sessions/{session.id}/scripts/s1e01/fabriquer"
    assert n.post(chemin, **entete("claude")).status_code == 403
    r = n.post(chemin, **entete("fenetre"))
    assert r.status_code == 200 and "dans la file" in r.json()["message"], r.content
    t = Tache.objects.get()
    assert (t.acteur, t.session_id, t.titre) == ("RT", session.id, "Une histoire factice")
    v = n.get(f"/api/sessions/{session.id}/videos", **entete("fenetre")).json()
    assert len(v) == 1 and v[0]["nom"] == "2026-12-01-s1e01" and v[0]["recette"] == "F1 v1" and v[0]["progression"] == "0/9"
    with routeur.session(session):
        assert json.loads((settings.SESSIONS / session.dossier / "videos" / v[0]["id"] / "2026-12-01-s1e01.json").read_text(encoding="utf-8")) == SCENARIO


def test_machine(monkeypatch):
    monkeypatch.setattr(carte, "gpu", lambda: (9.0, 2355.0, 16384.0))
    monkeypatch.setattr(carte, "bramble", lambda maintenant: "")
    r = Navigateur().get("/api/machine", **entete("fenetre")).json()
    assert r["carte"] == "9 % · 2,3 / 16 Go" and r["carte_prise"] == "" and r["disque_go"] > 0


LINT = Path(r"D:\StudioKids\OUTILS\ecriture\lint.py")


@pytest.mark.skipif(not LINT.is_file(), reason="lint.py (outil d'écriture du projet) absent de ce PC")
def test_regles_en_direct_et_nouvelle_version(session):
    d = settings.SESSIONS / session.dossier / "univers"
    d.mkdir(parents=True, exist_ok=True)
    (d / "univers.json").write_text(json.dumps({"friends": {}, "places": {}}), encoding="utf-8")
    n = Navigateur()
    r = n.post(f"/api/sessions/{session.id}/scripts/s1e01/controler", {"contenu": SCENARIO}, content_type="application/json", **entete("claude"))
    assert r.status_code == 200 and set(r.json()) == {"erreurs", "avis", "mesures"}, r.content
    erreurs = r.json()["erreurs"]
    r = n.post(f"/api/sessions/{session.id}/scripts/s1e01/versions", {"contenu": SCENARIO}, content_type="application/json", **entete("claude"))
    assert r.status_code == 200 and "version 3 enregistrée" in r.json()["message"]
    with routeur.session(session):
        v = m.VersionScript.objects.get(script__code="s1e01", numero=3)
        assert (v.auteur, v.regles["erreurs"]) == ("claude", erreurs)
    if erreurs:  # un script factice si court enfreint les règles de longueur : « Fabriquer » refuse
        r = n.post(f"/api/sessions/{session.id}/scripts/s1e01/fabriquer", **entete("fenetre"))
        assert r.status_code == 409 and "erreur(s) des règles" in r.json()["detail"]
