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
    pause: bool = False
    archivee: str = ""  # JJ/MM/AAAA ; vide : en service


class ActionSession(BaseModel):
    nom: str = ""  # dupliquer, modèle : le nom de la nouvelle
    videos: bool = False  # exporter : les vidéos aussi


class Importer(BaseModel):
    fichier: str  # un .fabrique (chemin complet) ou le nom de fichier d'un modèle
    nom: str = ""  # vide : celui du fichier


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
    releve: dict
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
    mesure: bool = False  # tous les contrôles sont finis et l'un au moins a rendu ses défauts (sinon : jamais « aucun défaut »)
    controles: list[str] = []  # les contrôles qui ont mesuré (revue, analyse…)
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


class Playlist(BaseModel):
    id: str
    titre: str


class Destination(BaseModel):
    """Où sont publiées les vidéos d'une langue de la session (jamais de jeton ici)."""
    langue: str
    reseau: str  # « youtube »
    etat: str  # « reliée », « refusée le JJ/MM/AAAA à HH:MM », « pas reliée »
    reliee: bool
    chaine: str  # le nom lu chez le réseau
    chaine_id: str
    depuis: str  # date de connexion
    playlists: list[Playlist]


class Lien(BaseModel):
    message: str
    url: str  # la page du réseau, à ouvrir dans le navigateur du PC


class Publication(BaseModel):
    """L'aperçu d'une publication (une langue d'une vidéo approuvée) : tout ce qui partira, et ce qui bloque « Publier »."""
    id: int
    langue: str
    statut: str  # brouillon, en_file, envoi, erreur, planifiee, non_repertoriee
    titre: str
    description: str  # chapitres et crédits compris
    tags: list[str]
    chapitres: list[str]  # les lignes « 00:00 … » lues dans la description
    playlist: str  # vide : aucune
    playlist_titre: str
    video: str  # chemins complets
    miniature: str  # vide : aucune
    miniatures: list[str]  # les images de final, à choisir
    enfants: bool  # « conçue pour les enfants »
    ia: bool  # déclaration IA (contenu synthétique)
    non_repertorie: bool  # première publication de la chaîne : part en non répertorié, sans créneau
    creneau: str  # JJ/MM/AAAA HH:MM (heure de Paris) ; vide en non répertorié
    destination: str  # état de la chaîne de la langue (« reliée », « pas reliée »…)
    chaine: str
    fautes: list[str]  # bloquent « Publier »
    avis: list[str]  # ne bloquent pas
    versions: int  # du titre et de la description
    lien: str  # la vidéo chez YouTube, une fois envoyée
    envoi: str  # octets confirmés, étapes faites
    erreur: str


class Paquet(BaseModel):
    """Un paquet prêt à poster : une langue d'une vidéo approuvée, pour un réseau (fiches dans publication/reseaux.json)."""
    publication: int
    langue: str
    reseau: str  # id de la fiche
    nom: str
    etat: str  # à faire, fait, impossible, erreur
    raison: str
    fichiers: list[dict]  # {nom, largeur, hauteur, duree_s, poids_mo}, une vidéo par partie
    miniature: str  # nom du fichier ; vide : aucune
    dossier: str  # chemin complet sur le PC
    textes: list[dict]  # {titre, texte}, un par partie
    fautes: list[str]  # écarts aux limites de la fiche (vide : conforme)


class CodeTelephone(BaseModel):
    code: str  # 6 chiffres
    expire: str  # HH:MM


class Appareil(BaseModel):
    id: str
    appareil: str
    depuis: str
    expire: str


class Retouche(BaseModel):
    titre: str
    description: str


class Choix(BaseModel):
    miniature: str = ""  # une image de final
    playlist: str | None = None  # None : inchangée ; « » : aucune
    jour: str = ""  # AAAA-MM-JJ
    horaire: str = ""  # HH:MM


ScriptDetail.model_rebuild()  # la planche utilise PlanVideo, défini plus bas
