"""Client de l'API du noyau, pour la fenêtre et les sous-commandes (« arreter », « commande ») : il lit les réponses avec les schémas du noyau
(noyau/schemas.py), jamais recopiés ; tests/test_contrat.py vérifie que chaque appel existe tel quel dans le contrat OpenAPI. Sans Django ni Qt."""
import json
import socket
import string
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
    "machine": ("GET", "/api/machine", s.Machine),
    "scripts": ("GET", "/api/sessions/{id}/scripts", list[s.Script]),
    "script": ("GET", "/api/sessions/{id}/scripts/{code}", s.ScriptDetail),
    "rendus_bramble": ("GET", "/api/sessions/{id}/scripts/{code}/bramble", s.RendusBramble),
    "bramble_en_cours": ("GET", "/api/bramble/en-cours", s.BrambleEnCours),
    "comparaisons": ("GET", "/api/sessions/{id}/scripts/{code}/comparaisons", list[s.Comparaison]),
    "animatique": ("GET", "/api/sessions/{id}/scripts/{code}/animatique", s.Animatique),
    "monter_animatique": ("POST", "/api/sessions/{id}/scripts/{code}/animatique", s.Message),
    "noter_animatique": ("POST", "/api/sessions/{id}/scripts/{code}/animatique/notes", s.Message),
    "retirer_note_animatique": ("POST", "/api/sessions/{id}/scripts/{code}/animatique/notes/{note}/retirer", s.Message),
    "animation": ("GET", "/api/sessions/{id}/scripts/{code}/animation", s.Animation),
    "animer_plan": ("POST", "/api/sessions/{id}/scripts/{code}/animation", s.Message),
    "garder_essai": ("POST", "/api/sessions/{id}/scripts/{code}/animation/garder", s.Message),
    "univers": ("GET", "/api/sessions/{id}/univers", s.Univers),
    "videos": ("GET", "/api/sessions/{id}/videos", list[s.VideoListe]),
    "fabriquer": ("POST", "/api/sessions/{id}/scripts/{code}/fabriquer", s.Message),
    "refaire": ("POST", "/api/sessions/{id}/videos/{video}/refaire", s.Message),
    "video": ("GET", "/api/sessions/{id}/videos/{video}", s.VideoDetail),
    "controler": ("POST", "/api/sessions/{id}/scripts/{code}/controler", s.Regles),
    "nouvelle_version": ("POST", "/api/sessions/{id}/scripts/{code}/versions", s.Message),
    "demander": ("POST", "/api/sessions/{id}/scripts/{code}/demander", s.Message),
    "agir_file": ("POST", "/api/file/{id}/{action}", s.Message),
    "destinations": ("GET", "/api/sessions/{id}/destinations", list[s.Destination]),
    "relier": ("POST", "/api/sessions/{id}/destinations/{langue}/relier", s.Lien),
    "rafraichir": ("POST", "/api/sessions/{id}/destinations/{langue}/rafraichir", s.Message),
    "approuver": ("POST", "/api/sessions/{id}/videos/{video}/approuver", s.Message),
    "publications": ("GET", "/api/sessions/{id}/videos/{video}/publications", list[s.Publication]),
    "retoucher": ("POST", "/api/sessions/{id}/publications/{pub}/retoucher", s.Message),
    "choisir": ("POST", "/api/sessions/{id}/publications/{pub}/choisir", s.Message),
    "publier": ("POST", "/api/sessions/{id}/publications/{pub}/{action}", s.Message),  # action : publier, reprendre, annuler
    "paquets": ("GET", "/api/sessions/{id}/videos/{video}/paquets", list[s.Paquet]),
    "refaire_paquets": ("POST", "/api/sessions/{id}/videos/{video}/paquets", s.Message),
    "code_telephone": ("POST", "/api/telephone/code", s.CodeTelephone),
    "importer_session": ("POST", "/api/sessions/importer", s.Message),
    "agir_session": ("POST", "/api/sessions/{id}/{action}", s.Message),  # pause, reprendre, archiver, desarchiver, dupliquer, exporter, modele
    "changer_mode": ("POST", "/api/mode", s.Message),
    "nouvelle_session": ("POST", "/api/sessions", s.SessionCreee),
    "formats": ("GET", "/api/formats", list[s.Format]),
    "modeles": ("GET", "/api/modeles", list[s.Modele]),
    "calendrier": ("GET", "/api/calendrier", list[s.ElementCalendrier]),  # debut, fin, session : dans la requête
    "historique": ("GET", "/api/sessions/{id}/historique", list[s.Changement]),
    "ajouter_element": ("POST", "/api/sessions/{id}/univers/ajouter", s.Message),
    "ecrire_style": ("POST", "/api/sessions/{id}/univers/style", s.Message),
    "ecrire_droits": ("POST", "/api/sessions/{id}/univers/{type}/{pk}/droits", s.Message),
    "partager": ("POST", "/api/sessions/{id}/univers/{type}/{pk}/partager", s.Message),
    "valider_reference": ("POST", "/api/sessions/{id}/references/{pk}/valider", s.Message),
    "importer_reference": ("POST", "/api/sessions/{id}/personnages/{pk}/references", s.Message),
    "reglages": ("GET", "/api/sessions/{id}/reglages", s.ReglagesSession),
    "ecrire_reglages": ("POST", "/api/sessions/{id}/reglages", s.Message),
    "finir_session": ("POST", "/api/sessions/{id}/finir", s.Message),
    "pilote": ("POST", "/api/sessions/{id}/pilote", s.Message),
    "etape_suivante": ("POST", "/api/sessions/{id}/reglages", s.Message),  # « Suivant » de la nouvelle session : son propre nom (la fenêtre avance sur sa réponse)
    "creer_script": ("POST", "/api/sessions/{id}/scripts", s.ScriptCree),
    "dater_script": ("POST", "/api/sessions/{id}/scripts/{code}/dater", s.Message),
    "idees": ("GET", "/api/sessions/{id}/idees", list[s.Idee]),
    "ajouter_idee": ("POST", "/api/sessions/{id}/idees", s.Message),
    "suivi": ("GET", "/api/sessions/{id}/videos/{video}/suivi", list[s.SuiviPublication]),
    "appareils": ("GET", "/api/telephone/appareils", list[s.Appareil]),
    "statistiques": ("GET", "/api/statistiques", s.Statistiques),
    "statistiques_session": ("GET", "/api/sessions/{id}/statistiques", s.StatistiquesSession),
    "revenu": ("POST", "/api/sessions/{id}/publications/{pub}/revenu", s.Message),
    "portee": ("POST", "/api/sessions/{id}/publications/{pub}/portee", s.Message),
    "temps_rt": ("POST", "/api/sessions/{id}/temps", s.Message),
    "assistant": ("POST", "/api/assistant", s.ReponseAssistant),  # J11 : la réponse dans « message »
    "deconnecter": ("POST", "/api/telephone/appareils/{appareil}/deconnecter", s.Message),
    "outils": ("GET", "/api/outils", s.Outils),
    "agir_outil": ("POST", "/api/outils/{outil}/{action}", s.Message),  # installer (ou mettre à jour), retirer, remettre
    "depenses": ("GET", "/api/depenses", s.Depenses),
    "plafond": ("POST", "/api/depenses/plafond", s.Message),
    "bancs": ("GET", "/api/bancs", list[s.BancListe]),
    "nouveau_banc": ("POST", "/api/bancs", s.Message),
    "banc": ("GET", "/api/bancs/{id}", s.BancDetail),
    "voter": ("POST", "/api/bancs/{id}/voter", s.Message),
    "rendre_verdict": ("POST", "/api/bancs/{id}/verdict", s.Message),
    "adopter": ("POST", "/api/bancs/{id}/adopter", s.Message),
    "veille": ("GET", "/api/veille", list[s.CandidatVeille]),
    "verser_veille": ("POST", "/api/veille", s.Message),
    "statut_veille": ("POST", "/api/veille/{pk}/statut", s.Message),
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
            with urllib.request.urlopen(self._requete(methode, chemin, corps), timeout=900 if chemin == "/api/assistant" else 120) as r:  # gpt-oss : chargement et tours
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
        champs = {f for _, f, _, _ in string.Formatter().parse(chemin) if f}
        requete = {k: v for k, v in params.items() if k not in champs}  # le reste : dans la requête (calendrier : debut, fin, session)
        chemin = chemin.format(**{k: urllib.parse.quote(str(v), safe="") for k, v in params.items() if k in champs})
        lu = self.transport(methode, chemin + (f"?{urllib.parse.urlencode(requete)}" if requete else ""), corps)
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
