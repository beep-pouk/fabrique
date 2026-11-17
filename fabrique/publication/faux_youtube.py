"""Faux YouTube (tests et simulation), repris de Bramble Studio (moteur/faux_youtube.py) : un serveur HTTP local qui répond comme Google —
OAuth « application installée » avec PKCE (consentement simulé), chaîne et playlists de l'API YouTube Data v3. Rien ne part chez Google.
`appels` note chaque requête (sans l'en-tête d'autorisation ni les secrets) ; `refuser` = le jeton de rafraîchissement est refusé
(invalid_grant). Jetons « faux-acces-<expiration>-… » et « faux-rafraichi-… » : reconnus par n'importe quelle instance.
L'envoi de vidéos, miniatures, sous-titres et les statistiques du faux de Bramble arrivent avec la publication (J4, étape 2)."""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

CLIENT_ID = "faux-client.apps.googleusercontent.com"
CLIENT_SECRET = "FAUX-SECRET-simulation"
SECRET_SIMULE = {"installed": {"client_id": CLIENT_ID, "project_id": "faux-projet", "client_secret": CLIENT_SECRET, "redirect_uris": ["http://localhost"]}}
PORTEE = "https://www.googleapis.com/auth/youtube.force-ssl"
CHAINE = ("UCfauxChaine", "Chaîne factice")
PLAYLISTS = [("PLfauxUn", "Histoires du renard"), ("PLfauxDeux", "Histoires du hibou"), ("PLfauxTrois", "Compilations factices")]


class Faux(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = os.name != "nt"  # Windows : SO_REUSEADDR laisserait un 2e processus écouter le même port (deux faux) ; sans, son bind échoue → Distant

    def __init__(self, port: int = 0):
        super().__init__(("127.0.0.1", port), Requete)
        self.base = f"http://127.0.0.1:{self.server_address[1]}"
        self.verrou = threading.Lock()
        self.codes = {}
        self.appels = []
        self.refuser = False

    @property
    def urls(self) -> dict:
        return {"auth": f"{self.base}/o/oauth2/v2/auth", "token": f"{self.base}/token", "api": self.base}

    def demarrer(self) -> "Faux":
        threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.05}, name="faux-youtube", daemon=True).start()
        return self

    def arreter(self):
        self.shutdown()
        self.server_close()

    def appels_de(self, methode: str, chemin: str) -> list[dict]:
        return [a for a in self.appels if a["methode"] == methode and a["chemin"] == chemin]


class Requete(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 30

    def log_message(self, *args):
        pass

    def _corps(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _repondre(self, code: int, corps=None, entetes: dict | None = None):
        donnees = b"" if corps is None else json.dumps(corps).encode("utf-8")
        self.send_response(code)
        for k, v in (entetes or {}).items():
            self.send_header(k, v)
        if corps is not None:
            self.send_header("Content-Type", "application/json; charset=UTF-8")
        self.send_header("Content-Length", str(len(donnees)))
        self.end_headers()
        self.wfile.write(donnees)

    def _erreur(self, code: int, raison: str, message: str):
        statut = {400: "INVALID_ARGUMENT", 401: "UNAUTHENTICATED", 403: "PERMISSION_DENIED", 404: "NOT_FOUND"}.get(code, "UNKNOWN")
        self._repondre(code, {"error": {"code": code, "message": message, "errors": [{"message": message, "domain": "youtube", "reason": raison}], "status": statut}})

    def _noter(self, params: dict, corps=None):
        with self.server.verrou:
            self.server.appels.append({"methode": self.command, "chemin": urlparse(self.path).path, "params": params, "corps": corps})

    def _autorise(self) -> bool:
        """Bearer « faux-acces-<expiration epoch>-… » pas encore expiré, sinon 401 comme Google."""
        jeton = self.headers.get("Authorization", "").removeprefix("Bearer ")
        morceaux = jeton.split("-")
        if jeton.startswith("faux-acces-") and len(morceaux) > 3 and morceaux[2].isdigit() and int(morceaux[2]) > time.time():
            return True
        self._erreur(401, "authError", "Request had invalid authentication credentials.")
        return False

    # ---- OAuth ----

    def _autoriser(self, p: dict):
        """Page de consentement : RT « accepte » tout de suite → 302 vers le retour 127.0.0.1 avec code et state."""
        if p.get("client_id") != CLIENT_ID or p.get("response_type") != "code" or p.get("code_challenge_method") != "S256" or not p.get("code_challenge") \
                or not p.get("redirect_uri", "").startswith("http://127.0.0.1:") or PORTEE not in p.get("scope", "").split():
            return self._erreur(400, "invalid_request", "Erreur 400 : invalid_request")
        code = "faux-code-" + secrets.token_urlsafe(12)
        with self.server.verrou:
            self.server.codes[code] = {"defi": p["code_challenge"], "redirect_uri": p["redirect_uri"], "scope": p["scope"]}
        self.send_response(302)
        self.send_header("Location", p["redirect_uri"] + "?" + urlencode({"state": p.get("state", ""), "code": code, "scope": PORTEE}))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _jeton(self, p: dict):
        def oauth_erreur(raison, texte):
            self._repondre(400, {"error": raison, "error_description": texte})

        if p.get("client_id") != CLIENT_ID or p.get("client_secret") != CLIENT_SECRET:
            return self._repondre(401, {"error": "invalid_client", "error_description": "Unauthorized"})
        acces = {"access_token": f"faux-acces-{int(time.time()) + 3599}-{secrets.token_urlsafe(16)}", "expires_in": 3599, "scope": PORTEE, "token_type": "Bearer"}
        if p.get("grant_type") == "authorization_code":
            with self.server.verrou:
                code = self.server.codes.pop(p.get("code", ""), None)  # un code ne sert qu'une fois
            verifie = code and base64.urlsafe_b64encode(hashlib.sha256(p.get("code_verifier", "").encode()).digest()).rstrip(b"=").decode() == code["defi"]
            if not verifie or code["redirect_uri"] != p.get("redirect_uri"):
                return oauth_erreur("invalid_grant", "Malformed auth code.")
            return self._repondre(200, {**acces, "scope": code["scope"], "refresh_token": "faux-rafraichi-" + secrets.token_urlsafe(24)})  # les portées accordées
        if p.get("grant_type") == "refresh_token":
            if self.server.refuser or not p.get("refresh_token", "").startswith("faux-rafraichi-"):
                return oauth_erreur("invalid_grant", "Token has been expired or revoked.")
            return self._repondre(200, acces)
        oauth_erreur("unsupported_grant_type", "Invalid grant_type")

    # ---- chaîne et playlists ----

    def _playlists(self, p: dict):
        """Pages de maxResults (5 par défaut, comme l'API), pageToken = rang du premier élément."""
        if "snippet" not in p.get("part", "").split(","):
            return self._erreur(400, "required", "Required parameter: part")
        n, debut = int(p.get("maxResults", 5)), int(p.get("pageToken", 0))
        items = [{"kind": "youtube#playlist", "id": i, "snippet": {"title": t, "channelId": CHAINE[0]}} for i, t in PLAYLISTS[debut:debut + n]]
        page = {"kind": "youtube#playlistListResponse", "items": items, "pageInfo": {"totalResults": len(PLAYLISTS), "resultsPerPage": n}}
        if debut + n < len(PLAYLISTS):
            page["nextPageToken"] = str(debut + n)
        self._repondre(200, page)

    # ---- routes ----

    def do_GET(self):
        chemin, p = urlparse(self.path).path, {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        self._noter(p)
        if chemin == "/o/oauth2/v2/auth":
            return self._autoriser(p)
        if not self._autorise():
            return
        if chemin == "/youtube/v3/playlists" and p.get("mine") == "true":
            return self._playlists(p)
        if chemin == "/youtube/v3/channels" and p.get("mine") == "true":
            return self._repondre(200, {"kind": "youtube#channelListResponse", "items": [{"kind": "youtube#channel", "id": CHAINE[0], "snippet": {"title": CHAINE[1]}}]})
        self._erreur(404, "notFound", "Not Found")

    def do_POST(self):
        if urlparse(self.path).path == "/token":
            donnees = {k: v[0] for k, v in parse_qs(self._corps().decode()).items()}
            self._noter({}, {"grant_type": donnees.get("grant_type", "")})  # jamais les secrets
            return self._jeton(donnees)
        self._corps()
        if self._autorise():
            self._erreur(404, "notFound", "Not Found")


_partage = None


def partage(port: int) -> "Faux | Distant":
    """Le faux de la simulation sur 127.0.0.1:<port>, commun aux processus de Fabrique : démarré par le premier qui en a besoin."""
    global _partage
    if _partage is None:
        try:
            _partage = Faux(port).demarrer()
        except OSError:  # déjà lancé par un autre processus
            _partage = Distant(f"http://127.0.0.1:{port}")
    return _partage


class Distant:
    """Le faux lancé par un autre processus : seulement ses adresses."""

    def __init__(self, base: str):
        self.base = base

    urls = Faux.urls
