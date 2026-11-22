"""J11, l'assistant (noms factices) : demande écrite → plan chiffré (lecture seule), puis brouillon après l'accord de RT ; ses outils passent
par les routes de l'API avec l'appelant « assistant » ; aucun ne mène à un des trois gestes."""
import inspect
import re

from django.conf import settings
from django.test import Client as Navigateur

from fabrique.noyau import api, assistant, bases, jetons
from fabrique.noyau.api import DROITS, GESTES
from fabrique.noyau.models import Journal, Session
from fabrique.tests.test_statistiques import delier, video  # noqa: F401 — delier : fixture autouse (chaînes factices déliées après chaque test)


def test_aucun_outil_de_l_assistant_ne_mene_a_un_geste():
    appelees = set(re.findall(r"api\.(\w+)\(_Appel\(\)", inspect.getsource(assistant)))
    assert appelees == {"sessions", "formats", "calendrier_", "statistiques", "estimer", "brouillon_session", "brouillon_video"}
    for nom in appelees:
        assert getattr(api, nom).droit in DROITS["assistant"] and getattr(api, nom).droit not in GESTES, nom
    assert {o["function"]["name"] for o in assistant.offerts(False)} & assistant.BROUILLONS == set()  # sans accord : lecture seule
    assert assistant.outil("brouillon_session", {"nom": "Refusée"}, accord=False) == "outil refusé : brouillon_session"
    assert assistant.outil("publier", {}, accord=True) == "outil refusé : publier"
    assert assistant.outil("calendrier", {"debut": "2099-01-01", "fin": "2099-01-31"}, accord=False).startswith("[")  # voir : le calendrier


def test_plan_chiffre_puis_brouillon_apres_accord(request):
    s = bases.creer(f"Assistant {request.node.name}")
    video(s, 1)  # une vidéo F1 finie : les médianes de l'estimation
    r = assistant.demander("Trois histoires du soir ?", [], accord=False)
    assert [o["outil"] for o in r["outils"]][:3] == ["sessions", "formats", "estimer"] and r["brouillons"] == []
    assert r["message"].startswith("Plan : 3 vidéos F1, ") and "h de carte" in r["message"]
    avant = Session.objects.count()
    r2 = assistant.demander("D'accord : prépare le brouillon de ce plan.", r["historique"], accord=True)
    assert r2["brouillons"] == ["brouillon_video"] and r2["message"].startswith("Brouillon prêt")
    assert Session.objects.count() == avant  # une idée au calendrier, pas de session
    assert Journal.objects.filter(acteur="assistant", action="idee").exists()  # une idée au calendrier de la première session, notée « assistant »
    r3 = assistant.demander("Une nouvelle session de comptines", [], accord=True)
    assert r3["brouillons"] == ["brouillon_session"] and Session.objects.count() == avant + 1


def test_routes_de_l_assistant():
    jetons.tirer(settings.DONNEES)
    entete = {"HTTP_AUTHORIZATION": f"Bearer {jetons.lire(settings.DONNEES, 'fenetre')}"}
    r = Navigateur().post("/api/assistant", {"demande": "Un plan ?", "historique": [], "accord": False}, content_type="application/json", **entete)
    assert r.status_code == 200 and r.json()["message"].startswith("Plan : ") and r.json()["brouillons"] == [], r.content
    claude = {"HTTP_AUTHORIZATION": f"Bearer {jetons.lire(settings.DONNEES, 'claude')}"}
    assert Navigateur().post("/api/assistant", {"demande": "x"}, content_type="application/json", **claude).status_code == 403
    assert Navigateur().post("/api/brouillons/session", {"nom": "x", "langues": []}, content_type="application/json", **entete).status_code == 403  # l'assistant seul
    r = Navigateur().post("/api/estimation", {"format": "F9", "videos": 2}, content_type="application/json", **entete)
    assert r.status_code == 403
    e = api.estimer(assistant._Appel(), api.schemas.Estimer(format="F9", videos=2))
    assert e["connues"] == 0 and "pas encore de vidéo F9 finie" in e["texte"]


def test_ranger_arrete_l_orphelin_et_cede_la_carte_a_bramble(monkeypatch):
    """Le llama-server d'un noyau précédent est arrêté au premier tour (son numéro gardé dans donnees) ; celui qui tourne s'arrête dès que
    Bramble Studio fabrique."""
    import subprocess
    import sys
    import time

    from fabrique.moteur import carte

    assistant._pid().write_text("999999", encoding="utf-8")
    assistant.ranger()
    assert not assistant._pid().exists()
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    monkeypatch.setitem(assistant._serveur, "processus", p)
    monkeypatch.setitem(assistant._serveur, "vu", time.monotonic())
    assistant.ranger()
    assert p.poll() is None  # carte libre, pas encore inactif : il reste
    monkeypatch.setattr(carte, "bramble", lambda maintenant: "Bramble Studio fabrique (un épisode)")
    assistant.ranger()
    assert p.wait(10) is not None and assistant._serveur["processus"] is None
