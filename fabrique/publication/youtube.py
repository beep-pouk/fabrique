"""YouTube, par destination (une chaîne par langue d'une session), repris de Bramble Studio (core/youtube.py) : connexion OAuth « application
installée » (RFC 8252 : retour sur 127.0.0.1:<port libre>, PKCE S256), jeton de rafraîchissement chiffré par Windows dans la destination (base de
la session), jeton d'accès gardé en mémoire et renouvelé seul ; appels de l'API YouTube Data v3 par urllib. Même client Google que Bramble
Studio : <studio>\\OUTILS\\installation\\youtube_client_secret.json, lu seulement. Le client secret et les jetons ne sont jamais affichés,
journalisés, ni rendus par l'API : seul l'état (reliée, refusée le …, pas reliée) l'est. En simulation : le faux YouTube (faux_youtube.py) et
son faux client remplacent Google, et les destinations de la simulation sont à part (un vrai jeton ne part jamais vers le faux)."""
import base64
import hashlib
import html
import json
import logging
import secrets
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from django.conf import settings
from django.db import connections
from django.utils import timezone

from fabrique import dossiers, garde
from fabrique.garde import Refus
from fabrique.noyau import cles, etat, evenements, routeur
from fabrique.noyau.models import noter
from fabrique.session import models as m

log = logging.getLogger(__name__)
RESEAU = "youtube"
PORTEE = "https://www.googleapis.com/auth/youtube.force-ssl"  # videos.insert, thumbnails.set, playlistItems.insert, captions.insert, videos.list, playlists.list
PORTEES = " ".join((PORTEE, "https://www.googleapis.com/auth/yt-analytics.readonly", "https://www.googleapis.com/auth/youtube.readonly"))  # + statistiques (Bramble J7)
GOOGLE = {"auth": "https://accounts.google.com/o/oauth2/v2/auth", "token": "https://oauth2.googleapis.com/token", "api": "https://www.googleapis.com",
          "analytics": "https://youtubeanalytics.googleapis.com"}
SECRET = "youtube_client_secret.json"
ATTENTE_RETOUR_S = 300  # le serveur de retour attend RT 5 min sur la page Google
MARGE_S = 60  # un jeton d'accès qui expire dans moins d'une minute est renouvelé
_acces: dict[tuple, tuple[str, float]] = {}  # (session, langue, simulation) -> (jeton d'accès, expiration) : en mémoire seulement


class JetonRefuse(Refus):
    """Google refuse le jeton de rafraîchissement (invalid_grant) : RT doit relier la chaîne à nouveau depuis la fenêtre."""


class ErreurYoutube(Exception):
    """Réponse d'erreur de Google : le code HTTP et sa raison (« invalidPublishAt », « quotaExceeded »…), jamais la requête."""

    def __init__(self, statut: int, raison: str):
        super().__init__(f"YouTube a répondu {statut} ({raison})")
        self.statut, self.raison = statut, raison


def _faux():
    from fabrique.publication.faux_youtube import partage

    return partage(dossiers.port() + 2)  # port + 1 : la sonnette de la fenêtre


def urls() -> dict:
    return _faux().urls if etat.simulation() else GOOGLE


def chemin_secret() -> Path:
    return (garde.studio_bramble() or settings.RACINE.parent) / "OUTILS" / "installation" / SECRET


def secret() -> dict:
    """client_id et client_secret du fichier téléchargé dans la console Google (« application de bureau » : clé installed) ; en simulation, le faux."""
    if etat.simulation():
        from fabrique.publication.faux_youtube import SECRET_SIMULE

        return SECRET_SIMULE["installed"]
    try:
        d = json.loads(chemin_secret().read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise Refus(f"YouTube : {SECRET} absent ou illisible dans OUTILS\\installation du studio (voir le guide « Connexion YouTube »)") from None
    s = (d.get("installed") or {}) if isinstance(d, dict) else {}
    if not s.get("client_id") or not s.get("client_secret"):  # un client « Application Web » refuserait le retour sur 127.0.0.1:<port libre>
        raise Refus(f"YouTube : {SECRET} n'est pas un client « Application de bureau » (guide « Connexion YouTube », étape 5)")
    return s


# ---- destinations ----

def _destinations():
    """Celles du mode en cours (dans « with routeur.session(s) »)."""
    return m.Destination.objects.filter(reseau=RESEAU, simulation=etat.simulation())


def langues(s) -> list[str]:
    """Les langues de la session : ses voix, puis celles de ses scripts."""
    with routeur.session(s):
        return list(dict.fromkeys([*m.Langue.objects.order_by("ordre", "code").values_list("code", flat=True),
                                   *m.Script.objects.order_by("langue").values_list("langue", flat=True)]))


def lister(s) -> list[dict]:
    """Une ligne par langue de la session (et par destination déjà reliée), sans aucun secret ; aucune pour la session « Essais »."""
    if s.essais:
        return []
    with routeur.session(s):
        faites = {d.langue: d for d in _destinations()}
    lignes = []
    for langue in dict.fromkeys([*langues(s), *faites]):
        d = faites.get(langue) or m.Destination(langue=langue, reseau=RESEAU)
        texte = "pas reliée" if not d.jeton else f"refusée le {timezone.localtime(d.refusee):%d/%m/%Y à %H:%M}" if d.refusee else "reliée"
        lignes.append({"langue": langue, "reseau": RESEAU, "etat": texte, "reliee": texte == "reliée", "chaine": d.chaine, "chaine_id": d.chaine_id,
                       "depuis": f"{timezone.localtime(d.reliee):%d/%m/%Y %H:%M}" if d.reliee else "", "playlists": d.playlists})
    return lignes


# ---- échanges OAuth ----

def _raison(e: urllib.error.HTTPError) -> str:
    """La raison donnée par Google (OAuth : « error » ; API : errors[0].reason), sinon le texte du code HTTP."""
    try:
        d = json.loads(e.read() or b"{}")
    except ValueError:
        d = {}
    erreur = d.get("error")
    if isinstance(erreur, str):
        return erreur
    if isinstance(erreur, dict):
        return ((erreur.get("errors") or [{}])[0].get("reason")) or erreur.get("status") or str(e.reason)
    return str(e.reason)


def _poster_jeton(donnees: dict) -> dict:
    requete = urllib.request.Request(urls()["token"], data=urlencode(donnees).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urllib.request.urlopen(requete, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raison = _raison(e)
        if raison == "invalid_grant":
            raise JetonRefuse("YouTube : Google a refusé le jeton (invalid_grant) — relier la chaîne à nouveau depuis la fenêtre") from None
        raise ErreurYoutube(e.code, raison) from None  # from None : rien de la requête (secrets) dans la trace


def _garder(s, langue: str, r: dict):
    _acces[(s.id, langue, etat.simulation())] = (r["access_token"], time.time() + int(r.get("expires_in", 3600)))


def echanger(s, langue: str, code: str, verifier: str, redirect: str, acteur: str):
    """Code d'autorisation + verifier PKCE → jetons ; le jeton de rafraîchissement chiffré dans la destination ; puis la chaîne et ses playlists."""
    sec = secret()
    r = _poster_jeton({"code": code, "client_id": sec["client_id"], "client_secret": sec["client_secret"], "redirect_uri": redirect,
                       "grant_type": "authorization_code", "code_verifier": verifier})
    if not r.get("refresh_token"):
        raise ErreurYoutube(200, "pas de refresh_token (retirer l'accès de Fabrique dans le compte Google, puis relier)")
    with routeur.session(s):
        m.Destination.objects.update_or_create(langue=langue, reseau=RESEAU, simulation=etat.simulation(),
                                               defaults={"jeton": cles.chiffrer(r["refresh_token"]), "reliee": timezone.now(), "refusee": None})
    _garder(s, langue, r)
    noter(acteur, "destination_reliee", session=s.id, langue=langue, reseau=RESEAU, simulation=etat.simulation())
    if "yt-analytics.readonly" not in r.get("scope", PORTEES):  # Google laisse décocher une autorisation : le relevé échouerait chaque heure
        evenements.publier("alerte", titre="Publication", message=f"YouTube ({langue}) : les statistiques n'ont pas été autorisées — relier à nouveau en cochant tout")
    log.info("YouTube relié : session %s, langue %s (simulation=%s)", s.id, langue, etat.simulation())
    try:
        rafraichir(s, langue)
    except (Refus, ErreurYoutube, OSError) as e:  # la connexion est faite ; la chaîne se relit aussi par « rafraîchir »
        log.warning("chaîne YouTube non lue (langue %s) : %s", langue, e)


def _refusee(s, langue: str):
    with routeur.session(s):
        _destinations().filter(langue=langue).update(refusee=timezone.now())
    texte = f"YouTube ({langue}) : Google a refusé le jeton — relier la chaîne à nouveau depuis la fenêtre"
    log.warning("%s (session %s)", texte, s.id)
    noter("noyau", "destination_refusee", session=s.id, langue=langue, reseau=RESEAU)
    evenements.publier("alerte", titre="Publication", message=texte)


def jeton(s, langue: str) -> str:
    """Jeton d'accès valable, renouvelé par le jeton de rafraîchissement s'il expire ; refus de Google → état « refusée » + alerte."""
    cle = (s.id, langue, etat.simulation())
    if (a := _acces.get(cle)) and a[1] - MARGE_S > time.time():
        return a[0]
    with routeur.session(s):
        d = _destinations().filter(langue=langue).first()
    if d is None or not d.jeton:
        raise Refus(f"YouTube ({langue}) : chaîne pas reliée — la relier depuis la fenêtre (PC)")
    if d.refusee:  # déjà refusé : pas de nouvelle demande à chaque appel (relier l'efface)
        raise JetonRefuse(f"YouTube ({langue}) : jeton refusé par Google, relier la chaîne à nouveau depuis la fenêtre")
    if not (rafraichi := cles.dechiffrer(d.jeton)):
        raise Refus(f"YouTube ({langue}) : jeton illisible sur ce PC (base venue d'un autre PC ou compte) — relier la chaîne à nouveau")
    sec = secret()
    try:
        r = _poster_jeton({"client_id": sec["client_id"], "client_secret": sec["client_secret"], "refresh_token": rafraichi, "grant_type": "refresh_token"})
    except JetonRefuse:
        _refusee(s, langue)
        raise
    _garder(s, langue, r)
    if r.get("refresh_token"):  # Google peut en donner un nouveau : le garder
        with routeur.session(s):
            _destinations().filter(langue=langue).update(jeton=cles.chiffrer(r["refresh_token"]))
    return r["access_token"]


# ---- connexion guidée : retour sur 127.0.0.1 ----

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Fabrique — YouTube</title></head>
<body style="font-family:system-ui;background:#1e2422;color:#e8e4d8;padding:2em"><h1>{titre}</h1><p>{texte}</p></body></html>"""


class _Retour(BaseHTTPRequestHandler):
    timeout = 10  # une connexion ouverte sans requête (préconnexion du navigateur) ne bloque pas l'attente

    def log_message(self, *args):
        pass

    def do_GET(self):
        a = self.server.attente
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        if q.get("state") != a["state"]:  # favicon, autre onglet, rejeu : pas ce retour-là
            return self._page(400, "Retour inattendu", "Relancer « Relier » depuis Fabrique.")
        if "error" in q or "code" not in q:
            a["resultat"] = f"refusé sur la page Google ({q.get('error', 'sans code')})"
            return self._page(200, "Chaîne non reliée", f"Google a répondu : {q.get('error', 'sans code')}. Relancer « Relier » depuis Fabrique.")
        try:
            echanger(a["session"], a["langue"], q["code"], a["verifier"], a["redirect"], a["acteur"])
            a["resultat"] = "ok"
            self._page(200, "Chaîne reliée", "Fabrique publiera sur cette chaîne. Cette page peut être fermée.")
        except (Refus, ErreurYoutube, OSError) as e:
            a["resultat"] = str(e)
            log.warning("connexion YouTube (langue %s) : %s", a["langue"], e)
            self._page(200, "Chaîne non reliée", str(e))

    def _page(self, code: int, titre: str, texte: str):
        corps = PAGE.format(titre=html.escape(titre), texte=html.escape(texte)).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)


def _attendre(serveur: HTTPServer):
    fin = time.monotonic() + ATTENTE_RETOUR_S
    try:
        while serveur.attente["resultat"] is None and time.monotonic() < fin:
            serveur.handle_request()
    finally:
        serveur.server_close()
        connections.close_all()  # ce fil a ses propres connexions aux bases


def connecter(s, langue: str, acteur: str) -> tuple[str, threading.Thread]:
    """URL de la page d'autorisation de Google (à ouvrir dans le navigateur du PC) et le fil qui attend le retour sur 127.0.0.1:<port libre>
    (5 min, une seule réponse). Refus si la langue n'est pas de la session ou si le client secret manque."""
    if s.essais:
        raise Refus("la session « Essais » ne publie jamais : aucune chaîne à relier")
    if langue not in langues(s):
        raise Refus(f"la langue « {langue} » n'est pas une langue de la session")
    sec = secret()
    verifier = secrets.token_urlsafe(64)
    defi = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    serveur = HTTPServer(("127.0.0.1", 0), _Retour)
    serveur.timeout = 1
    redirect = f"http://127.0.0.1:{serveur.server_port}/"
    serveur.attente = {"state": secrets.token_urlsafe(24), "verifier": verifier, "redirect": redirect, "acteur": acteur, "session": s, "langue": langue, "resultat": None}
    fil = threading.Thread(target=_attendre, args=(serveur,), name="retour-oauth", daemon=True)
    fil.start()
    noter(acteur, "destination_connexion", session=s.id, langue=langue, reseau=RESEAU)
    url = urls()["auth"] + "?" + urlencode({"client_id": sec["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": PORTEES, "code_challenge": defi,
                                           "code_challenge_method": "S256", "state": serveur.attente["state"], "access_type": "offline", "prompt": "consent"})
    return url, fil


# ---- API ----

def appeler(s, langue: str, methode: str, chemin: str = "", params: dict | None = None, corps=None, donnees: bytes | None = None, type_: str = "",
            entetes: dict | None = None, url: str = "", delai: int = 120):
    """Requête authentifiée vers l'API Data pour la chaîne de la destination ; renvoie (statut, en-têtes, corps) pour 2xx et 308 (envoi
    incomplet) ; ErreurYoutube sinon. Les erreurs réseau (coupure) remontent telles quelles."""
    url = url or urls()["api"] + chemin + ("?" + urlencode(params) if params else "")
    h = {"Authorization": f"Bearer {jeton(s, langue)}", **(entetes or {})}
    if corps is not None:
        donnees, h["Content-Type"] = json.dumps(corps).encode("utf-8"), "application/json; charset=UTF-8"
    elif type_:
        h["Content-Type"] = type_
    requete = urllib.request.Request(url, data=donnees, headers=h, method=methode)
    try:
        with urllib.request.urlopen(requete, timeout=delai) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        if e.code == 308:  # « Resume Incomplete » : pas une redirection
            return 308, e.headers, b""
        raise ErreurYoutube(e.code, _raison(e)) from None


def rafraichir(s, langue: str) -> dict:
    """La chaîne (id, nom) et ses playlists, lues chez YouTube et gardées dans la destination : aucun écran n'appelle YouTube en s'affichant.
    shortcut: une page de 50 playlists ; ajouter pageToken si une chaîne en a plus de 50."""
    _, _, b = appeler(s, langue, "GET", "/youtube/v3/playlists", {"part": "snippet", "mine": "true", "maxResults": 50})
    playlists = [{"id": p["id"], "titre": p["snippet"]["title"]} for p in json.loads(b).get("items", [])]
    _, _, b = appeler(s, langue, "GET", "/youtube/v3/channels", {"part": "snippet", "mine": "true"})
    c = next(iter(json.loads(b).get("items", [])), {})
    lu = {"chaine_id": c.get("id", ""), "chaine": (c.get("snippet") or {}).get("title", ""), "playlists": playlists}
    with routeur.session(s):
        _destinations().filter(langue=langue).update(**lu)
    return lu
