"""Faux YouTube (tests et simulation), repris de Bramble Studio (moteur/faux_youtube.py) : un serveur HTTP local qui répond comme Google —
OAuth « application installée » avec PKCE (consentement simulé), chaîne et playlists de l'API YouTube Data v3, envoi « resumable » (session,
morceaux, état, 308 + Range, 201 final), miniature, élément de playlist, sous-titres (multipart/related). Rien ne part chez Google. Les
contrôles de l'API sont repris (titre ≤ 100 sans < >, description ≤ 5000 octets, tags ≤ 500, publishAt seulement en privé, booléens enfants
et IA, miniature ≤ 2 Mo) : une requête hors règle reçoit l'erreur de Google (code + « reason »).
`appels` note chaque requête (sans l'en-tête d'autorisation ni les secrets) ; `coupure` = nombre total d'octets reçus après lequel la
connexion d'un envoi est coupée sans réponse, une fois ; `refuser` = le jeton de rafraîchissement est refusé (invalid_grant). Jetons
« faux-acces-<expiration>-… » et « faux-rafraichi-… » : reconnus par n'importe quelle instance.
API YouTube Analytics v2 (reports.query, columnHeaders + rows, sur le même serveur, reprise du faux de Bramble) : la chaîne (sans filtre) ou une
vidéo (filters=video==ID), par jour ; `statistiques[vidéo ou CHAINE_STATS][jour]` = les chiffres que Google aurait (posés par les tests) ; une clé
absente : des chiffres réguliers jusqu'à l'avant-veille (retard de 48-72 h), pour que la simulation montre un relevé ; `analytics_refus` = 403
ou 429 → chaque reports.query est refusée (quota)."""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
from datetime import datetime, timedelta
from email import message_from_bytes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

CLIENT_ID = "faux-client.apps.googleusercontent.com"
CLIENT_SECRET = "FAUX-SECRET-simulation"
SECRET_SIMULE = {"installed": {"client_id": CLIENT_ID, "project_id": "faux-projet", "client_secret": CLIENT_SECRET, "redirect_uris": ["http://localhost"]}}
PORTEE = "https://www.googleapis.com/auth/youtube.force-ssl"
CHAINE = ("UCfauxChaine", "Chaîne factice")
PLAYLISTS = [("PLfauxUn", "Histoires du renard"), ("PLfauxDeux", "Histoires du hibou"), ("PLfauxTrois", "Compilations factices")]
MINIATURE_MAX = 2 * 1024 * 1024
METRIQUES = {"views": "INTEGER", "estimatedMinutesWatched": "INTEGER", "averageViewDuration": "INTEGER", "averageViewPercentage": "FLOAT",
             "subscribersGained": "INTEGER", "subscribersLost": "INTEGER"}
REFUS_ANALYTICS = {403: ("quotaExceeded", "The request cannot be completed because you have exceeded your quota."),
                   429: ("rateLimitExceeded", "Quota exceeded for quota metric 'Queries' and limit 'Queries per minute'.")}
CHAINE_STATS = ""  # clé des chiffres de la chaîne entière dans `statistiques`


def longueur_tags(tags: list[str]) -> int:
    """Règle de l'API : virgules comprises, guillemets comptés autour d'un tag qui contient une espace."""
    return sum(len(t) + 2 * (" " in t) for t in tags) + max(len(tags) - 1, 0)


class Faux(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = os.name != "nt"  # Windows : SO_REUSEADDR laisserait un 2e processus écouter le même port (deux faux) ; sans, son bind échoue → Distant

    def __init__(self, port: int = 0):
        super().__init__(("127.0.0.1", port), Requete)
        self.base = f"http://127.0.0.1:{self.server_address[1]}"
        self.verrou = threading.Lock()
        self.codes, self.sessions, self.videos, self.miniatures, self.elements, self.sous_titres = {}, {}, {}, {}, [], []
        self.appels = []
        self.coupure = None
        self.refuser = False
        self.statistiques = {}  # {vidéo ou CHAINE_STATS: {AAAA-MM-JJ: {métrique: valeur}}}
        self.analytics_refus = None
        self.travaux, self.portee = {}, {}  # API Reporting : travaux créés ; {vidéo: (impressions, taux de clic 0-1)} des rapports « reach »

    @property
    def urls(self) -> dict:
        return {"auth": f"{self.base}/o/oauth2/v2/auth", "token": f"{self.base}/token", "api": self.base, "analytics": self.base, "reporting": self.base}

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

    # ---- vidéos ----

    def _controle_video(self, v: dict) -> tuple[str, str] | None:
        """(reason, message) de l'erreur que Google renverrait pour ces métadonnées, None si elles passent."""
        sn, st = v.get("snippet") or {}, v.get("status") or {}
        titre, description, tags = sn.get("title", ""), sn.get("description", ""), sn.get("tags", [])
        if not titre.strip() or len(titre) > 100 or "<" in titre or ">" in titre:
            return "invalidTitle", "The request metadata specifies an invalid video title."
        if len(description.encode("utf-8")) > 5000 or "<" in description or ">" in description:
            return "invalidDescription", "The request metadata specifies an invalid video description."
        if not isinstance(tags, list) or longueur_tags(tags) > 500:
            return "invalidTags", "The request metadata specifies invalid video keywords."
        if st.get("privacyStatus") not in ("public", "private", "unlisted"):
            return "invalidVideoMetadata", "The request metadata is invalid."
        if "publishAt" in st:  # une date passée est acceptée : la vidéo est publiée tout de suite (doc de status.publishAt)
            try:
                datetime.fromisoformat(st["publishAt"].replace("Z", "+00:00"))
            except (TypeError, ValueError, AttributeError):
                return "invalidPublishAt", "The request metadata specifies an invalid scheduled publishing time."
            if st["privacyStatus"] != "private":
                return "invalidPublishAt", "The request metadata specifies an invalid scheduled publishing time."
        if any(k in st and not isinstance(st[k], bool) for k in ("selfDeclaredMadeForKids", "containsSyntheticMedia")):
            return "invalidVideoMetadata", "The request metadata is invalid."
        return None

    def _session(self, p: dict):
        corps = json.loads(self._corps() or b"{}")
        self._noter(p, corps)
        if p.get("uploadType") != "resumable" or not {"snippet", "status"} <= set(p.get("part", "").split(",")):
            return self._erreur(400, "badRequest", "Bad Request")
        if faute := self._controle_video(corps):
            return self._erreur(400, *faute)
        taille = self.headers.get("X-Upload-Content-Length", "")
        if not taille.isdigit():
            return self._erreur(400, "badRequest", "X-Upload-Content-Length manquant")
        ident = secrets.token_urlsafe(18)
        with self.server.verrou:
            self.server.sessions[ident] = {"meta": corps, "taille": int(taille), "recu": bytearray(), "video": None}
        self._repondre(200, None, {"Location": f"{self.server.base}/upload/youtube/v3/videos?uploadType=resumable&upload_id={ident}&part={p['part']}"})

    def _envoi(self, p: dict):
        s = self.server.sessions.get(p.get("upload_id", ""))
        plage = self.headers.get("Content-Range", "")
        self._noter({k: v for k, v in p.items() if k != "upload_id"}, {"Content-Range": plage, "Content-Length": self.headers.get("Content-Length", "0")})
        if s is None:
            self._corps()
            return self._erreur(404, "notFound", "Upload session not found")
        if s["video"]:
            self._corps()
            return self._repondre(200, self.server.videos[s["video"]]["ressource"])
        recu = len(s["recu"])
        if plage.startswith("bytes */"):
            return self._repondre(308, None, {"Range": f"bytes=0-{recu - 1}"} if recu else {})
        try:
            a, reste = plage.removeprefix("bytes ").split("-")
            b, total = (int(x) for x in reste.split("/"))
            a = int(a)
        except ValueError:
            self._corps()
            return self._erreur(400, "badRequest", "Content-Range invalide")
        n = int(self.headers.get("Content-Length") or 0)
        if a != recu or total != s["taille"] or b - a + 1 != n:
            self._corps()
            return self._erreur(400, "badRequest", "Content-Range ne suit pas les octets reçus")
        coupure = self.server.coupure
        coupe = coupure is not None and recu + n >= coupure  # la connexion tombe une fois `coupure` octets reçus : ce qui est arrivé reste
        s["recu"] += self.rfile.read(min(n, max(coupure - recu, 0)) if coupe else n)
        if len(s["recu"]) >= s["taille"]:
            ident = secrets.token_urlsafe(8)[:11]
            ressource = {"kind": "youtube#video", "id": ident, "snippet": {**s["meta"]["snippet"], "channelId": CHAINE[0]},
                         "status": {**s["meta"]["status"], "uploadStatus": "uploaded"}}
            with self.server.verrou:
                self.server.videos[ident] = {"ressource": ressource, "empreinte": hashlib.sha256(s["recu"]).hexdigest(), "taille": len(s["recu"])}
                s["video"] = ident
        if coupe:  # pas de réponse (même si tout est arrivé : la réponse se perd)
            self.server.coupure = None
            self.close_connection = True
            return
        if s["video"]:
            return self._repondre(201, self.server.videos[s["video"]]["ressource"])
        self._repondre(308, None, {"Range": f"bytes=0-{len(s['recu']) - 1}"})

    # ---- miniature, playlist, sous-titres ----

    def _miniature(self, p: dict):
        donnees = self._corps()
        self._noter(p, {"octets": len(donnees)})
        if p.get("videoId") not in self.server.videos:
            return self._erreur(404, "videoNotFound", "The video that you are trying to update cannot be found.")
        if self.headers.get("Content-Type", "").split(";")[0] not in ("image/jpeg", "image/png", "application/octet-stream"):
            return self._erreur(400, "invalidImage", "The thumbnail image file you provided is invalid.")
        if len(donnees) > MINIATURE_MAX:
            return self._erreur(400, "mediaBodyTooBig", "The thumbnail image file is too big.")
        with self.server.verrou:
            self.server.miniatures[p["videoId"]] = donnees
        url = f"{self.server.base}/vi/{p['videoId']}/maxresdefault.jpg"
        self._repondre(200, {"kind": "youtube#thumbnailSetResponse", "items": [{"default": {"url": url, "width": 120, "height": 90}, "maxres": {"url": url, "width": 1280, "height": 720}}]})

    def _element(self, p: dict):
        corps = json.loads(self._corps() or b"{}")
        self._noter(p, corps)
        if "snippet" not in p.get("part", "").split(","):
            return self._erreur(400, "required", "Required parameter: part")
        sn = corps.get("snippet") or {}
        if sn.get("playlistId") not in {i for i, _ in PLAYLISTS}:
            return self._erreur(404, "playlistNotFound", "The playlist identified with the request's playlistId parameter cannot be found.")
        if (sn.get("resourceId") or {}).get("kind") != "youtube#video" or sn["resourceId"].get("videoId") not in self.server.videos:
            return self._erreur(404, "videoNotFound", "The video that you are trying to add to the playlist cannot be found.")
        element = {"kind": "youtube#playlistItem", "id": "faux-element-" + secrets.token_urlsafe(8), "snippet": sn}
        with self.server.verrou:
            self.server.elements.append(element)
        self._repondre(200, element)

    def _sous_titres(self, p: dict):
        type_ = self.headers.get("Content-Type", "")
        message = message_from_bytes(f"Content-Type: {type_}\r\n\r\n".encode() + self._corps())
        parties = message.get_payload() if message.is_multipart() else []
        meta = json.loads(parties[0].get_payload(decode=True)) if parties else {}
        texte = parties[1].get_payload(decode=True).decode("utf-8", "replace") if len(parties) > 1 else ""
        self._noter(p, {"meta": meta, "texte": texte})
        sn = meta.get("snippet") or {}
        if "snippet" not in p.get("part", "").split(","):
            return self._erreur(400, "required", "Required parameter: part")
        if p.get("uploadType") != "multipart" or not type_.startswith("multipart/related") or len(parties) != 2:
            return self._erreur(400, "badRequest", "Bad Request")
        if not all(sn.get(k) for k in ("videoId", "language", "name")):
            return self._erreur(400, "invalidMetadata", "The request contains invalid metadata values.")
        if sn["videoId"] not in self.server.videos:
            return self._erreur(404, "videoNotFound", "The video identified by the videoId parameter could not be found.")
        if "-->" not in texte:
            return self._erreur(400, "invalidCaptionTrack", "The caption track could not be processed.")
        if any((x["snippet"]["videoId"], x["snippet"]["language"], x["snippet"]["name"]) == (sn["videoId"], sn["language"], sn["name"]) for x in self.server.sous_titres):
            return self._erreur(409, "captionExists", "The specified caption track already exists.")
        piste = {"kind": "youtube#caption", "id": "faux-piste-" + secrets.token_urlsafe(8), "snippet": {**sn, "trackKind": "standard", "status": "serving"}}
        with self.server.verrou:
            self.server.sous_titres.append({**piste, "texte": texte})
        self._repondre(200, piste)

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

    # ---- statistiques (API YouTube Analytics v2) ----

    def _rapport(self, p: dict):
        if self.server.analytics_refus:
            return self._erreur(self.server.analytics_refus, *REFUS_ANALYTICS[self.server.analytics_refus])
        metriques = p.get("metrics", "").split(",")
        filtre = p.get("filters", "")
        video = filtre[len("video=="):] if filtre.startswith("video==") else None
        try:
            debut, fin = (datetime.strptime(p[k], "%Y-%m-%d").date() for k in ("startDate", "endDate"))
        except (KeyError, ValueError):
            return self._erreur(400, "badRequest", "startDate et endDate (AAAA-MM-JJ) obligatoires")
        if p.get("ids") != "channel==MINE" or p.get("dimensions") != "day" or (filtre and not video) or any(m not in METRIQUES for m in metriques) or debut > fin:
            return self._erreur(400, "badRequest", "Requête Analytics invalide (ids, dimensions, filters, metrics)")
        cle = video or CHAINE_STATS
        jours = self.server.statistiques[cle] if cle in self.server.statistiques else {
            f"{j}": {m: (7 * j.day + len(m)) % 50 + 1 for m in METRIQUES} for j in (debut + timedelta(n) for n in range((fin - debut).days + 1))
            if j <= datetime.now().date() - timedelta(days=2)}
        rows = [[j, *(jours[j].get(m, 0) for m in metriques)] for j in sorted(jours) if f"{debut}" <= j <= f"{fin}"]
        entetes = [{"name": "day", "columnType": "DIMENSION", "dataType": "STRING"}] + [{"name": m, "columnType": "METRIC", "dataType": METRIQUES[m]} for m in metriques]
        self._repondre(200, {"kind": "youtubeAnalytics#resultTable", "columnHeaders": entetes, **({"rows": rows} if rows else {})})  # sans donnée : pas de clé rows (comme l'API)

    # ---- portée (API YouTube Reporting : travail « channel_reach_basic_a1 », un rapport CSV par jour) ----

    def _rapports_portee(self, travail: str):
        if travail not in self.server.travaux:
            return self._erreur(404, "notFound", "Job not found")
        jours = [datetime.now().date() - timedelta(days=n) for n in (4, 3, 2)]
        self._repondre(200, {"reports": [{"id": f"r{j:%Y%m%d}", "jobId": travail, "startTime": f"{j}T07:00:00Z", "endTime": f"{j + timedelta(1)}T07:00:00Z",
                                          "downloadUrl": f"{self.server.base}/v1/media/{travail}/{j:%Y%m%d}"} for j in jours]})

    def _csv_portee(self, jour: str):
        lignes = ["date,channel_id,video_id,live_or_on_demand,subscribed_status,country_code,video_thumbnail_impressions,video_thumbnail_impressions_ctr"]
        for v, (i, c) in self.server.portee.items():  # deux lignes par vidéo (abonnés ou non) : Fabrique les additionne
            lignes += [f"{jour},{CHAINE[0]},{v},on_demand,subscribed,FR,{i // 2},{c}", f"{jour},{CHAINE[0]},{v},on_demand,not_subscribed,US,{i - i // 2},{c}"]
        donnees = ("\n".join(lignes) + "\n").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Length", str(len(donnees)))
        self.end_headers()
        self.wfile.write(donnees)

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
        if chemin == "/v2/reports":
            return self._rapport(p)
        if chemin == "/v1/jobs":
            return self._repondre(200, {"jobs": list(self.server.travaux.values())} if self.server.travaux else {})
        if chemin.startswith("/v1/jobs/") and chemin.endswith("/reports"):
            return self._rapports_portee(chemin.split("/")[3])
        if chemin.startswith("/v1/media/"):
            return self._csv_portee(chemin.rsplit("/", 1)[1])
        self._erreur(404, "notFound", "Not Found")

    def do_POST(self):
        chemin, p = urlparse(self.path).path, {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        if chemin == "/token":
            donnees = {k: v[0] for k, v in parse_qs(self._corps().decode()).items()}
            self._noter({}, {"grant_type": donnees.get("grant_type", "")})  # jamais les secrets
            return self._jeton(donnees)
        if not self._autorise():
            self._corps()
            return
        if chemin == "/v1/jobs":
            corps = json.loads(self._corps() or b"{}")
            t = {"id": f"job{len(self.server.travaux) + 1}", "reportTypeId": corps.get("reportTypeId", ""), "name": corps.get("name", "")}
            self.server.travaux[t["id"]] = t
            return self._repondre(200, t)
        routes = {"/upload/youtube/v3/videos": self._session, "/upload/youtube/v3/thumbnails/set": self._miniature, "/youtube/v3/playlistItems": self._element,
                  "/upload/youtube/v3/captions": self._sous_titres}
        if chemin in routes:
            return routes[chemin](p)
        self._corps()
        self._erreur(404, "notFound", "Not Found")

    def do_PUT(self):
        chemin, p = urlparse(self.path).path, {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        if not self._autorise():
            self._corps()
            return
        if chemin == "/upload/youtube/v3/videos":
            return self._envoi(p)
        self._corps()
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
