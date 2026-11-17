"""Les schémas de l'API : le noyau répond avec eux (api.py, contrat OpenAPI), la fenêtre lit avec eux (fenetre/client.py). Pydantic seul :
la fenêtre les importe sans Django."""
from pydantic import BaseModel


class Message(BaseModel):
    message: str


class Sante(BaseModel):
    nom: str
    version: str
    mode: str
    appelant: str
    pid: int


class Session(BaseModel):
    id: str
    nom: str
    dossier: str
    essais: bool


class Fiche(BaseModel):
    """Lue dans la base de la session elle-même."""
    id: str
    nom: str


class Etat(BaseModel):
    heure: str
    version: str
    mode: str
    noyau: dict
    sessions: list[str]
    file: dict
    sauvegarde: dict
    alertes: list[str]
    texte: list[str]


class LigneJournal(BaseModel):
    date: str
    niveau: str
    source: str
    message: str


class Sauvegarde(BaseModel):
    nom: str
    date: str
    taille_mo: float


class Sauvegardes(BaseModel):
    dossier: str
    liste: list[Sauvegarde]
    derniere: dict  # la dernière sauvegarde lancée : etat (en_cours, faite, erreur), fin, fichier, message


class Versions(BaseModel):
    installee: str
    proposee: str | None
    nouveautes: list[str]
    raison: str  # vide : « Mettre à jour » est possible


class Cle(BaseModel):
    nom: str
    titre: str
    ou: str
    ok: bool


class Valeur(BaseModel):
    valeur: str


class TacheFile(BaseModel):
    id: int
    titre: str
    session: str
    etat: str  # attente, en_cours, pause, finie, erreur, annulee
    raison: str  # pourquoi elle attend ou s'est arrêtée
    alertes: list[str]
    acteur: str
    progression: str  # morceaux finis / tous
