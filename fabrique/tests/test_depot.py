"""Le dépôt des discussions Claude (noms factices) : une demande = un accusé ; seulement les droits de Claude (jamais un geste de RT) ; ce que RT
demande à Claude (écrire, traduire), et le retour d'une traduction."""
import json
from datetime import date, datetime, timezone

import pytest
from django.conf import settings

from fabrique.garde import Refus
from fabrique.noyau import bases, depot, routeur
from fabrique.noyau.models import Tache
from fabrique.session import models as m
from fabrique.session import regles

SCENARIO = {"format": 2, "title": "Une histoire factice", "scenes": [{"id": 1, "narration": "Il était une fois.", "image": "a quiet glade"}]}


@pytest.fixture
def session(monkeypatch, request):
    monkeypatch.setattr(regles, "controler", lambda s, contenu, code="": {"erreurs": [], "avis": [], "mesures": {}})  # lint.py : testé ailleurs
    s = bases.creer(f"Dépôt {request.node.name}")
    with routeur.session(s):
        sc = m.Script.objects.create(code="s1e01", titre="Une histoire factice", langue="en", statut="scenario", date_prevue=date(2026, 12, 1))
        m.VersionScript.objects.create(script=sc, numero=1, auteur="import", date=datetime(2026, 11, 10, tzinfo=timezone.utc), contenu=SCENARIO)
        m.Langue.objects.create(code="xx", nom="Langue factice")
    yield s
    Tache.objects.all().delete()


def deposer(nom: str, contenu):
    d = settings.RACINE / "depot"
    d.mkdir(parents=True, exist_ok=True)
    (d / nom).write_text(contenu if isinstance(contenu, str) else json.dumps(contenu), encoding="utf-8")


def accuse(nom: str) -> dict:
    return json.loads((settings.RACINE / "depot" / "faits" / nom).read_text(encoding="utf-8"))


def test_demandes_et_accuses(session):
    deposer("1.json", {"action": "script", "session": session.nom, "code": "s1e01", "contenu": {**SCENARIO, "title": "Réécrite"}})
    deposer("2.json", {"action": "essai", "script": {"titre": "Essai déposé", "scenes": [{"id": "s1", "plans": [{"id": "p1"}]}]}})
    deposer("3.json", "{ pas du json")
    deposer("4.json", {"action": "fabriquer", "session": session.id, "code": "s1e01"})  # un geste de RT : jamais par le dépôt
    deposer("5.json", {"action": "script", "session": "inconnue", "code": "s1e01", "contenu": {}})
    assert len(depot.traiter()) == 5 and not list((settings.RACINE / "depot").glob("*.json"))
    assert accuse("1.json")["resultat"] == "ok" and "version 2" in accuse("1.json")["message"] and "contenu" not in accuse("1.json")["demande"]
    assert accuse("2.json")["resultat"] == "ok" and Tache.objects.get().acteur == "claude"
    assert accuse("3.json")["resultat"] == "erreur" and accuse("4.json")["resultat"] == "erreur" and "inconnue" in accuse("4.json")["message"]
    assert accuse("5.json")["resultat"] == "refus"
    assert not Tache.objects.filter(session_id=session.id).exists()
    with routeur.session(session):
        assert m.Script.objects.get(code="s1e01").versions.order_by("-numero").first().auteur == "claude"


def test_rt_demande_a_claude_puis_la_traduction_revient(session):
    assert "nouvelle version" in depot.demander(session, "s1e01", "ecrire", "", "RT")
    assert "traduction en xx" in depot.demander(session, "s1e01", "traduire", "xx", "RT")
    d = json.loads((settings.RACINE / "depot" / "a_traduire" / "s1e01.xx.json").read_text(encoding="utf-8"))
    assert d["contenu"] == SCENARIO and d["langue"] == "xx" and '"code": "s1e01.xx"' in d["rendre"]
    assert (settings.RACINE / "depot" / "a_ecrire" / "s1e01.json").is_file()
    with pytest.raises(Refus, match="pas une langue"):
        depot.demander(session, "s1e01", "traduire", "zz", "RT")
    deposer("6.json", {"action": "script", "session": session.id, "code": "s1e01.xx", "contenu": {**SCENARIO, "title": "Titre traduit"}})
    depot.traiter()
    assert accuse("6.json")["resultat"] == "ok"
    with routeur.session(session):
        t = m.Script.objects.get(code="s1e01.xx")
        assert (t.langue, t.statut, t.titre, str(t.date_prevue)) == ("xx", "traduction", "Titre traduit", "2026-12-01")
