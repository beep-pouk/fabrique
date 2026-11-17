"""Client de l'API du noyau, pour la fenêtre et les sous-commandes (« arreter », « commande ») : il lit les réponses avec les schémas du noyau
(noyau/schemas.py), jamais recopiés ; tests/test_contrat.py vérifie que chaque appel existe tel quel dans le contrat OpenAPI. Sans Django ni Qt."""
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from pydantic import TypeAdapter

from fabrique import dossiers
from fabrique.noyau import jetons
from fabrique.noyau import schemas as s

APPELS = {  # nom -> (méthode, chemin, schéma de la réponse)
    "sante": ("GET", "/api/sante", s.Sante),
    "etat": ("GET", "/api/etat", s.Etat),
    "sessions": ("GET", "/api/sessions", list[s.Session]),
    "fiche": ("GET", "/api/sessions/{id}", s.Fiche),
    "journal": ("GET", "/api/journal", list[s.LigneJournal]),
    "sauvegardes": ("GET", "/api/sauvegardes", s.Sauvegardes),
    "sauvegarder": ("POST", "/api/sauvegardes", s.Message),
    "restaurer": ("POST", "/api/sauvegardes/{nom}/restaurer", s.Message),
    "versions": ("GET", "/api/versions", s.Versions),
    "mettre_a_jour": ("POST", "/api/versions/mettre-a-jour", s.Message),
    "cles": ("GET", "/api/cles", list[s.Cle]),
    "enregistrer_cle": ("POST", "/api/cles/{nom}", s.Message),
    "arreter": ("POST", "/api/arreter", s.Message),
    "file": ("GET", "/api/file", list[s.TacheFile]),
    "agir_file": ("POST", "/api/file/{id}/{action}", s.Message),
}


class ErreurApi(Exception):
    """Un refus du noyau (message pour RT)."""


class Client:
    def __init__(self, appelant: str = "fenetre", port: int | None = None, donnees: Path | None = None, transport=None):
        self.appelant, self.port, self.donnees = appelant, port or dossiers.port(), donnees or dossiers.donnees()
        self.transport = transport or self._http

    def _requete(self, methode: str, chemin: str, corps=None) -> urllib.request.Request:
        donnees = json.dumps(corps).encode() if corps is not None else b"" if methode == "POST" else None
        return urllib.request.Request(f"http://127.0.0.1:{self.port}{chemin}", data=donnees, method=methode,
                                      headers={"Authorization": f"Bearer {jetons.lire(self.donnees, self.appelant)}", "Content-Type": "application/json"})

    def _http(self, methode: str, chemin: str, corps=None):
        try:
            with urllib.request.urlopen(self._requete(methode, chemin, corps), timeout=120) as r:
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read()).get("detail", e.reason)
            except ValueError:
                detail = e.reason
            raise ErreurApi(detail if isinstance(detail, str) else str(detail)) from None

    def appeler(self, appel: str, corps=None, /, **params):
        methode, chemin, schema = APPELS[appel]
        t = TypeAdapter(schema)
        lu = self.transport(methode, chemin.format(**{k: urllib.parse.quote(str(v), safe="") for k, v in params.items()}), corps)
        return t.dump_python(t.validate_python(lu), mode="json")

    def repond(self) -> bool:
        try:
            self.appeler("sante")
            return True
        except (OSError, ErreurApi):
            return False

    def evenements(self):
        """Le flux du noyau : (type, données) ; s'arrête quand la connexion tombe (OSError)."""
        with urllib.request.urlopen(self._requete("GET", "/api/evenements"), timeout=60) as r:  # le noyau bat toutes les 15 s
            type_ = "message"
            for brut in r:
                ligne = brut.decode("utf-8").rstrip("\r\n")
                if ligne.startswith("event: "):
                    type_ = ligne[7:]
                elif ligne.startswith("data: "):
                    yield type_, json.loads(ligne[6:])
                    type_ = "message"


def sonner(message: str, port: int | None = None) -> bool:
    """La sonnette de la fenêtre (port de l'API + 1) : « montrer » ou « quitter ». False : aucune fenêtre n'écoute."""
    try:
        with socket.create_connection(("127.0.0.1", (port or dossiers.port()) + 1), timeout=2) as c:
            c.sendall(message.encode() + b"\n")
        return True
    except OSError:
        return False


def ouvert(port: int) -> bool:
    with socket.socket() as c:
        c.settimeout(0.5)
        return c.connect_ex(("127.0.0.1", port)) == 0


def arreter(ecrire=print, patience: float = 15) -> bool:
    """Arrêt propre de tout (installateur, désinstallateur, recettes) : la fenêtre par sa sonnette, le noyau par l'API ; ce qui reste est
    terminé (s'il est bien de l'app). Une sauvegarde en cours continue : elle est détachée."""
    from fabrique import programme

    port = dossiers.port()
    sonner("quitter", port)
    try:
        Client("fenetre", port).appeler("arreter")
    except (OSError, ErreurApi):
        pass
    fin = time.monotonic() + patience
    while (ouvert(port) or ouvert(port + 1)) and time.monotonic() < fin:
        time.sleep(0.25)
    for role in ("noyau", "fenetre"):
        try:
            programme.tuer(int((dossiers.donnees() / f"{role}.pid").read_text()))
        except (OSError, ValueError):
            pass
    fini = not (ouvert(port) or ouvert(port + 1))
    ecrire("Fabrique est arrêtée." if fini else "Fabrique répond encore.")
    return fini
