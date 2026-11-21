"""La page iPhone (J4) : code à 6 chiffres tiré par la fenêtre seulement (5 min, usage unique, 5 essais), jeton d'appareil en cookie HttpOnly,
Secure, SameSite=Strict, jamais en clair en base ; droits de l'iPhone ; en-tête exigé pour agir ; appareils listés et déconnectés depuis la
fenêtre ; la page servie à l'hôte de Tailscale avec ses en-têtes de sûreté. Noms factices."""
import json
from datetime import datetime, timedelta

import pytest
from django.conf import settings
from django.test import Client

from fabrique.noyau import jetons, telephone
from fabrique.noyau.models import Journal, Parametre

TS = {"HTTP_HOST": "pc-factice.tailnet-factice.ts.net", "HTTP_USER_AGENT": "Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X)"}


@pytest.fixture(autouse=True)
def propre():
    jetons.tirer(settings.DONNEES)
    Parametre.ecrire(telephone.CODE, "")
    Parametre.ecrire(telephone.APPAREILS, "")


def fenetre(methode, chemin, qui="fenetre"):
    h = {"HTTP_AUTHORIZATION": f"Bearer {jetons.lire(settings.DONNEES, qui)}"}
    return getattr(Client(), methode)(chemin, **h)


def code() -> str:
    r = fenetre("post", "/api/telephone/code")
    assert r.status_code == 200, r.content
    return r.json()["code"]


def connecter(iphone: Client, c: str):
    return iphone.post("/iphone/connexion", json.dumps({"code": c}), content_type="application/json")


def test_page_servie_a_tailscale_avec_ses_en_tetes():
    r = Client(**TS).get("/iphone/")
    assert r.status_code == 200 and b"Fabrique" in r.content and r["X-Frame-Options"] == "DENY" and r["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in r["Content-Security-Policy"] and r["Referrer-Policy"] == "no-referrer"
    assert b"innerHTML" not in r.content  # tout texte reçu de l'API reste du texte
    assert Client(HTTP_HOST="ailleurs.example.com").get("/iphone/").status_code == 400
    assert Client(**TS).get("/api/etat").status_code == 401  # rien sans le cookie


def test_code_jeton_et_droits_de_l_iphone():
    assert fenetre("post", "/api/telephone/code", "claude").status_code == 403
    c = code()
    assert len(c) == 6 and c.isdigit() and c not in json.dumps(list(Journal.objects.values_list("detail", flat=True)))
    iphone = Client(**TS)
    r = connecter(iphone, c)
    assert r.status_code == 200
    cookie = r.cookies[telephone.COOKIE]
    assert cookie["httponly"] and cookie["secure"] and cookie["samesite"] == "Strict" and int(cookie["max-age"]) == 365 * 24 * 3600
    assert cookie.value not in Parametre.lire(telephone.APPAREILS) and telephone.empreinte(cookie.value) in Parametre.lire(telephone.APPAREILS)
    assert connecter(Client(**TS), c).status_code == 403  # usage unique
    assert iphone.get("/api/etat").status_code == 200 and iphone.get("/api/sessions").status_code == 200
    # agir : l'en-tête X-Fabrique est exigé (un autre site ne peut pas le poser) ; puis les droits de l'iPhone seulement
    assert iphone.post("/api/sessions/inconnue/videos/v/approuver").status_code == 401
    h = {"HTTP_X_FABRIQUE": "iphone"}
    assert iphone.post("/api/sessions/inconnue/videos/v/approuver", **h).status_code in (404, 409)  # reconnu : la session inconnue est refusée ensuite
    for chemin in ("/api/telephone/code", "/api/sauvegardes", "/api/arreter", "/api/sessions/inconnue/videos/v/paquets"):
        assert iphone.post(chemin, **h).status_code == 403, chemin
    # la fenêtre liste l'appareil et le déconnecte : le cookie ne vaut plus rien
    a = fenetre("get", "/api/telephone/appareils").json()
    assert [x["appareil"] for x in a] == ["iPhone"] and len(a[0]["id"]) == 12
    assert fenetre("get", "/api/telephone/appareils", "claude").status_code == 403
    assert fenetre("post", f"/api/telephone/appareils/{a[0]['id']}/deconnecter").status_code == 200
    assert iphone.get("/api/etat").status_code == 401 and fenetre("get", "/api/telephone/appareils").json() == []


def test_cinq_essais_faux_annulent_le_code_et_il_expire():
    c = code()
    faux = f"{(int(c) + 1) % 10**6:06d}"
    for _ in range(telephone.ESSAIS):
        assert connecter(Client(**TS), faux).status_code == 403
    assert connecter(Client(**TS), c).status_code == 403  # annulé au 5e essai faux
    c = code()
    v = json.loads(Parametre.lire(telephone.CODE))
    Parametre.ecrire(telephone.CODE, json.dumps({**v, "expire": (datetime.now() - timedelta(seconds=1)).isoformat()}))
    assert connecter(Client(**TS), c).status_code == 403  # expiré
    c = code()
    iphone = Client(**TS)
    assert connecter(iphone, c).status_code == 200
    a = json.loads(Parametre.lire(telephone.APPAREILS))
    Parametre.ecrire(telephone.APPAREILS, json.dumps([{**a[0], "expire": (datetime.now() - timedelta(seconds=1)).isoformat()}]))
    assert iphone.get("/api/etat").status_code == 401  # un an passé
