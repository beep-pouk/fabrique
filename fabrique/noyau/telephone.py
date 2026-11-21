"""Le téléphone de RT (page iPhone, plan § 3.3), repris de Bramble Studio (core/telephone.py) : la fenêtre tire un code à 6 chiffres, valable
5 min, à usage unique (5 essais faux : annulé) ; la page /iphone/ (servie par le noyau, jointe par `tailscale serve` en HTTPS) l'échange
contre un jeton d'appareil valable un an, posé en cookie HttpOnly, Secure, SameSite=Strict (un cookie posé par le serveur n'est pas effacé
par Safari après 7 jours sans visite, contrairement au stockage de la page). En base, seulement l'empreinte (sha256) du jeton. Avec ce
cookie, l'appelant est « iphone » (droits d'api.DROITS : voir, approuver, publier, paquets) ; une requête qui change quelque chose porte
aussi l'en-tête X-Fabrique (un autre site ne peut pas le poser sans que le noyau l'autorise : jamais). Appareils listés et déconnectés
depuis la fenêtre."""
import hashlib
import json
import os
import secrets
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from fabrique.noyau.models import Parametre, noter

CODE, APPAREILS, COOKIE, ENTETE = "code_telephone", "appareils", "fabrique_iphone", "X-Fabrique"
DUREE = timedelta(minutes=5)
ESSAIS = 5
VIE = timedelta(days=365)
PAGE = Path(__file__).with_name("iphone.html")
PORT_TAILSCALE = 8443  # « tailscale serve --bg --https=8443 http://127.0.0.1:8790 » : le port 443 sert déjà Bramble Studio
SURETE = {"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff",
          "Content-Security-Policy": "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self'; frame-ancestors 'none'"}


def _code() -> dict | None:
    try:
        c = json.loads(Parametre.lire(CODE) or "null")
    except ValueError:
        return None
    return c if c and datetime.fromisoformat(c["expire"]) > datetime.now() else None


def adresse() -> str:
    """L'adresse de la page sur l'iPhone (nom MagicDNS de ce PC, lu par « tailscale status --json », 3 s au plus) ; vide sans Tailscale."""
    exe = shutil.which("tailscale") or str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tailscale" / "tailscale.exe")
    try:
        r = subprocess.run([exe, "status", "--json"], capture_output=True, text=True, encoding="utf-8", timeout=3, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        nom = json.loads(r.stdout)["Self"]["DNSName"].rstrip(".")
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return ""
    return f"https://{nom}:{PORT_TAILSCALE}/iphone/" if nom else ""


def nouveau_code(acteur: str) -> dict:
    """Un nouveau code remplace l'ancien ; le code lui-même n'est jamais journalisé."""
    c = {"code": f"{secrets.randbelow(10**6):06d}", "expire": (datetime.now() + DUREE).isoformat(timespec="seconds"), "essais": 0}
    Parametre.ecrire(CODE, json.dumps(c))
    noter(acteur, "code_telephone", valable_jusqu_a=c["expire"])
    return {"code": c["code"], "expire": f"{datetime.fromisoformat(c['expire']):%H:%M}", "adresse": adresse()}


def essayer(saisi: str) -> bool:
    """Bon code → consommé ; mauvais → un essai de moins, au 5e le code est annulé."""
    c = _code()
    saisi = "".join(ch for ch in (saisi or "") if ch.isdigit())
    if c is None:
        return False
    if len(saisi) == 6 and secrets.compare_digest(saisi, c["code"]):
        Parametre.ecrire(CODE, "")
        return True
    c["essais"] += 1
    Parametre.ecrire(CODE, "" if c["essais"] >= ESSAIS else json.dumps(c))
    return False


def empreinte(jeton: str) -> str:
    return hashlib.sha256(jeton.encode()).hexdigest()


def _lire() -> list[dict]:
    try:
        return [a for a in json.loads(Parametre.lire(APPAREILS) or "[]") if datetime.fromisoformat(a["expire"]) > datetime.now()]
    except (ValueError, KeyError, TypeError):
        return []


def nom_appareil(agent: str) -> str:
    return next((nom for mot, nom in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Téléphone Android"), ("Macintosh", "Mac"), ("Windows", "PC Windows"))
                 if mot in (agent or "")), "Appareil")


def connecter(agent: str) -> str:
    jeton = secrets.token_urlsafe(32)
    a = {"empreinte": empreinte(jeton), "appareil": nom_appareil(agent), "depuis": f"{datetime.now():%d/%m/%Y %H:%M}",
         "expire": (datetime.now() + VIE).isoformat(timespec="seconds")}
    Parametre.ecrire(APPAREILS, json.dumps([*_lire(), a]))
    noter("RT", "telephone_connecte", appareil=a["appareil"])
    return jeton


def reconnu(jeton: str | None) -> bool:
    return bool(jeton) and any(secrets.compare_digest(a["empreinte"], empreinte(jeton)) for a in _lire())


def appareils() -> list[dict]:
    """Pour la fenêtre : jamais l'empreinte entière (12 caractères suffisent à désigner l'appareil)."""
    return [{"id": a["empreinte"][:12], "appareil": a["appareil"], "depuis": a["depuis"], "expire": f"{datetime.fromisoformat(a['expire']):%d/%m/%Y}"} for a in _lire()]


def deconnecter(id_: str, acteur: str) -> bool:
    gardes = [a for a in _lire() if not a["empreinte"].startswith(id_ or "-")]
    if len(gardes) == len(_lire()):
        return False
    Parametre.ecrire(APPAREILS, json.dumps(gardes))
    noter(acteur, "appareil_deconnecte")
    return True


# ---- la page et la connexion (sans jeton : c'est ici qu'on l'obtient) ----

def hote(request):
    """Refus (400) d'un hôte hors d'ALLOWED_HOSTS : sans intergiciel, Django ne le contrôle qu'à la demande (une page jointe par un nom piégé
    qui pointerait sur 127.0.0.1)."""
    request.get_host()


def _surete(r: HttpResponse) -> HttpResponse:
    for k, v in SURETE.items():
        r[k] = v
    return r


@require_GET
def page(request):
    hote(request)
    return _surete(HttpResponse(PAGE.read_bytes(), content_type="text/html; charset=utf-8"))


@require_POST
def connexion(request):
    hote(request)
    try:
        code = json.loads(request.body or b"{}").get("code", "")
    except (ValueError, AttributeError):
        code = ""
    if not essayer(str(code)):
        return _surete(JsonResponse({"detail": "code faux ou expiré : en tirer un nouveau dans la fenêtre de Fabrique (Système → Téléphone)"}, status=403))
    r = _surete(JsonResponse({"message": "téléphone connecté pour un an"}))
    r.set_cookie(COOKIE, connecter(request.headers.get("User-Agent", "")), max_age=int(VIE.total_seconds()), secure=True, httponly=True, samesite="Strict")
    return r
