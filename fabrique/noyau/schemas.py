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


class Script(BaseModel):
    code: str
    titre: str
    statut: str
    date_prevue: str  # AAAA-MM-JJ, vide : pas encore au calendrier
    versions: int
    validee: bool  # la dernière version est validée


class VersionScript(BaseModel):
    numero: int
    auteur: str
    date: str
    validee: bool


class ScriptDetail(BaseModel):
    code: str
    titre: str
    statut: str
    date_prevue: str
    versions: list[VersionScript]  # la plus récente d'abord
    contenu: dict  # celui de la plus récente
    regles: dict  # le résultat des règles de la plus récente
    plans: list["PlanVideo"]  # la planche : les plans qui seront fabriqués (F1)
    estimation: dict  # secondes, cout_eur, carte_go de sa fabrication au format de la session ; « refus » si le format ne peut pas le lire
    traductions: list[str]  # les langues où il est traduit : à choisir avant « Fabriquer »


class Personnage(BaseModel):
    nom: str
    role: str
    statut: str
    references: int


class Lieu(BaseModel):
    nom: str
    description: str


class Langue(BaseModel):
    code: str
    nom: str
    outil_voix: str
    voix_validee: bool


class Univers(BaseModel):
    personnages: list[Personnage]
    lieux: list[Lieu]
    langues: list[Langue]


class VideoListe(BaseModel):
    id: str
    titre: str
    nom: str
    recette: str  # « F1 v1 »
    progression: str  # morceaux finis / tous
    erreurs: int


class EtapeVideo(BaseModel):
    id: str
    brique: str
    finis: int
    total: int
    erreur: str  # la cause en clair d'un morceau en erreur, vide sinon
    outils: list[str]
    secondes: float  # chrono des morceaux finis


class PlanVideo(BaseModel):
    n: int  # id de la première scène du plan
    image: str  # ce que montre le plan (vide : scène où Bramble parle)
    scenes: list[int]
    bramble: bool


class Defaut(BaseModel):
    debut: float | None  # secondes dans la vidéo ; None : toute la vidéo (volume global)
    fin: float | None = None
    texte: str
    source: str = ""  # qui l'a vu : analyser_video, Qwen, mouvement…
    gravite: str = "moyenne"  # forte, moyenne, legere


class Controle(BaseModel):
    mesure: bool = False  # un contrôle a rendu ses défauts (sinon : rien de mesuré, jamais « aucun défaut »)
    note: float | None = None  # sur 10
    defauts: list[Defaut] = []
    video: str = ""  # la vidéo finale (chemin complet), pour le lecteur


class VideoDetail(BaseModel):
    id: str
    titre: str
    nom: str
    recette: str
    etapes: list[EtapeVideo]
    plans: list[PlanVideo]  # ce qui se coche dans Vérification (F1)
    script: dict
    controle: Controle = Controle()


class Langues(BaseModel):
    langues: list[str] = []  # les langues fabriquées en plus de celle du script
    version: int | None = None  # la version du script que RT a relue


class Demande(BaseModel):
    quoi: str  # « ecrire » (nouvelle version) ou « traduire »
    langue: str = ""  # pour une traduction


class Contenu(BaseModel):
    contenu: dict  # un script


class Regles(BaseModel):
    erreurs: list[list[str]]  # [code de la règle, texte] ; une erreur bloque « Fabriquer »
    avis: list[list[str]]
    mesures: dict


class Plans(BaseModel):
    plans: list[int]  # les plans cochés (id de leur première scène)


class Machine(BaseModel):
    carte: str  # « 9 % · 2,3 / 16 Go », ou « indisponible »
    disque_go: int
    carte_prise: str  # vide : une fabrication peut partir


class TacheFile(BaseModel):
    id: int
    titre: str
    session: str
    etat: str  # attente, en_cours, pause, finie, erreur, annulee
    raison: str  # pourquoi elle attend ou s'est arrêtée
    alertes: list[str]
    acteur: str
    progression: str  # morceaux finis / tous


ScriptDetail.model_rebuild()  # la planche utilise PlanVideo, défini plus bas
