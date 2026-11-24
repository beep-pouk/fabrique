"""Les schémas de l'API : le noyau répond avec eux (api.py, contrat OpenAPI), la fenêtre lit avec eux (fenetre/client.py). Pydantic seul :
la fenêtre les importe sans Django."""
from pydantic import BaseModel, Field


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
    assistant: str = ""  # où en est la nouvelle session (« 2 » à « 6 »), « fini », ou vide (session d'avant J5)
    videos: int = 0
    derniere: str = ""  # la dernière vidéo fabriquée
    a_faire: int = 0  # à approuver, à publier, en erreur
    prochain: str = ""  # « JJ/MM titre » : le prochain script daté pas encore publié
    rendement: str = ""  # vues des 28 derniers jours (relevé quotidien), vide sans relevé


class ReglagesSession(BaseModel):
    """Ce que la session dit d'elle-même (session/reglages.py)."""
    nom: str
    pause: bool
    public: str
    promesse: str
    style: str
    difference: str  # garde-fou YouTube : ce qui rend chaque vidéo différente (vide : « Fabriquer » refusé)
    objectif: str
    arret: str  # critère d'arrêt
    format: str  # celui de « Fabriquer »
    formats: list[str]
    assistant: str
    plafond_eur: float
    duree_min: float | None
    duree_max: float | None
    enfants: bool
    declaration_ia: bool
    ordre_strict: bool
    langues: list[dict]  # [{code, nom}]
    manque: list[str]  # ce qui manque pour finir la nouvelle session


class ChangerReglages(BaseModel):
    """Seuls les champs envoyés changent."""
    public: str | None = None
    promesse: str | None = None
    style: str | None = None
    difference: str | None = None
    objectif: str | None = None
    arret: str | None = None
    format: str | None = None
    formats: list[str] | None = None
    plafond_eur: float | None = None
    duree_min: float | None = None
    duree_max: float | None = None
    enfants: bool | None = None
    declaration_ia: bool | None = None
    ordre_strict: bool | None = None
    langues: list[dict] | None = None
    assistant: str | None = None  # l'étape où en est la nouvelle session (« 3 » à « 7 ») ; « fini » : seulement par « Terminer »


class NouvelleSession(BaseModel):
    nom: str
    langues: list[dict]  # [{code, nom}]
    public: str = ""
    promesse: str = ""
    modele: str = ""  # le nom de fichier d'un modèle de session ; vide : de zéro


class NouveauScript(BaseModel):
    titre: str = ""  # vide : celui de l'idée
    date: str = ""  # AAAA-MM-JJ ; vide : pas daté
    idee: int = 0  # l'idée dont il est tiré
    format: str = ""  # vide : celui de la session ; sinon un de ses formats (F2 compilation, F3 courte verticale…)


class ScriptCree(BaseModel):
    message: str
    code: str


class Date(BaseModel):
    date: str  # AAAA-MM-JJ ; vide : retiré du calendrier


class SessionCreee(BaseModel):
    message: str
    id: str


class Format(BaseModel):
    id: str
    nom: str
    version: int
    script: str
    etapes: list[dict]  # [{id, brique, par}]


class Modele(BaseModel):
    nom: str
    fichier: str


class ElementCalendrier(BaseModel):
    session: str
    session_nom: str
    code: str
    titre: str
    date: str  # AAAA-MM-JJ, vide : pas daté
    statut: str  # idee, script, prete, fabrication, a_verifier, approuvee, programmee, publiee, suivie, reportee
    statut_nom: str
    pret_vers: str  # « JJ/MM HH:MM » estimé, s'il est dans la file


class Idee(BaseModel):
    id: int
    titre: str
    resume: str
    source: str
    statut: str
    creee: str


class Estimer(BaseModel):
    format: str  # F1 à F6
    videos: int = Field(1, ge=1, le=100)


class Estimation(BaseModel):
    format: str
    videos: int
    connues: int  # vidéos finies de ce format, d'où viennent les médianes
    fabrication_h: float | None
    carte_h: float | None
    cout_eur: float | None
    texte: str


class DemandeAssistant(BaseModel):
    demande: str = Field(min_length=1, max_length=4000)
    historique: list[dict] = []  # [{role: user|assistant, content}]
    accord: bool = False  # « D'accord » de RT : les brouillons sont permis


class ReponseAssistant(BaseModel):
    message: str  # la réponse de l'assistant
    outils: list[dict]
    brouillons: list[str]
    historique: list[dict]


class NouvelleIdee(BaseModel):
    titre: str
    resume: str = ""
    source: str = ""


class SuiviPublication(BaseModel):
    langue: str
    statut: str
    titre: str
    lien: str  # vide tant que la vidéo n'est pas chez YouTube
    vues: int
    heures: float
    abonnes: int
    jours: list[dict]  # [{date, vues}] des 28 derniers jours relevés


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
    format: str = ""  # le sien ; vide : celui de la session


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
    citees: list[dict] = []  # une compilation, un extrait : [{id, titre}] des vidéos citées, dans l'ordre


class RenduBramble(BaseModel):
    langue: str
    chemin: str


class RendusBramble(BaseModel):
    images: dict[int, str]  # plan (première scène) -> image rendue par Bramble
    videos: list[RenduBramble]  # la vidéo finie la plus récente par langue


class Reference(BaseModel):
    id: int
    chemin: str  # le fichier, chemin complet sur ce PC
    vue: str
    source: str
    validee: bool
    licence: str
    credit: str


class Personnage(BaseModel):
    id: int
    nom: str
    role: str
    statut: str
    description: str
    licence: str
    credit: str
    references: list[Reference]  # les validées d'abord


class Lieu(BaseModel):
    id: int
    nom: str
    description: str
    licence: str
    credit: str


class Ressource(BaseModel):
    id: int
    type: str  # musique, voix
    nom: str
    outil: str
    licence: str
    credit: str


class Langue(BaseModel):
    code: str
    nom: str
    outil_voix: str
    voix_validee: bool


class Univers(BaseModel):
    personnages: list[Personnage]
    lieux: list[Lieu]
    ressources: list[Ressource]
    langues: list[Langue]
    style: str


class Changement(BaseModel):
    date: str
    acteur: str
    quoi: str


class Element(BaseModel):
    type: str  # personnage, lieu, musique, voix
    nom: str
    description: str = ""
    role: str = ""


class Droits(BaseModel):
    licence: str
    credit: str


class ImportReference(BaseModel):
    fichier: str  # chemin complet d'une image sur ce PC (glisser-déposer) : copiée, jamais déplacée
    vue: str = ""


class Validation(BaseModel):
    validee: bool


class Partage(BaseModel):
    vers: str  # l'identifiant de l'autre session


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
    reste_s: float | None = None  # durée estimée de ce qui reste (chronos : médianes), pour l'écran File
    cout_eur: float | None = None
    pret_vers: str = ""  # « JJ/MM HH:MM »
    banc: int = 0  # un banc à l'aveugle plutôt qu'une fabrication


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
    variantes: list[dict] = []  # J11 : {titre, miniature (chemin complet), note, raisons, depuis, portee}
    variante: int = 0  # celle qui est posée
    proposition: dict | None = None  # J11 : {variante, raison} quand le taux de clic reste sous la médiane de la chaîne


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


class Mode(BaseModel):
    reel: bool


class CodeTelephone(BaseModel):
    code: str  # 6 chiffres
    expire: str  # HH:MM
    adresse: str = ""  # la page sur l'iPhone ; vide : Tailscale introuvable sur ce PC


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
    variante: int | None = None  # J11 : une variante (titre et miniature), avant ou après la publication


ScriptDetail.model_rebuild()  # la planche utilise PlanVideo, défini plus bas


class OutilFiche(BaseModel):
    """Une fiche de l'écran Outils (moteur/installation.py, registre)."""
    id: str
    nom: str
    local: bool
    prix: str  # « gratuit » ou « 0,09 € / 1 000 caractères (prix du …) »
    licence: str
    credit: str
    besoins: str
    langues: str
    limites: str
    version: str
    etat: str  # en_service, candidat, retire
    etat_nom: str
    installation: str  # en clair
    action: str  # installer, mettre_a_jour, ou vide
    simule: bool  # un faux outil (montré en simulation seulement)
    defaut: bool  # le défaut de la brique
    sessions: list[str]  # les sessions dont il est le défaut
    dernier_banc: str


class BriqueOutils(BaseModel):
    id: str
    titre: str
    defaut: str
    juges: list[dict]  # [{id, titre}] : ceux qu'un banc de cette brique peut prendre
    outils: list[OutilFiche]


class Outils(BaseModel):
    briques: list[BriqueOutils]
    installation: dict  # l'état de la tâche d'installation (donnees\taches\installation.json)


class Depenses(BaseModel):
    plafond_mois_eur: float
    depense_mois_eur: float
    lignes: list[dict]  # [{date, session, outil, estime_eur, reel_eur}], les plus récentes d'abord


class Nombre(BaseModel):
    valeur: float


class NouveauBanc(BaseModel):
    session: str
    video: str
    brique: str
    outil: str  # celui qui se mesure à l'outil en place
    juge: str = ""


class BancListe(BaseModel):
    id: int
    brique: str
    session: str
    video: str
    etat: str  # attente, en_cours, a_voter, fini, erreur, annule
    etat_nom: str
    outils: str  # « en place contre candidat »
    juge: str
    entrees: int
    votes: int
    verdict: str
    raison: str
    cree: str


class BancDetail(BancListe):
    """Avant le verdict : ni le nom des outils de chaque côté, ni les notes du juge."""
    lignes: list[dict]  # [{n, texte, langue, gauche: [fichiers], droite: [fichiers], vote, notes: {gauche, droite} | None, qui: {gauche, droite} | None}]
    gagnant: str
    adopte: str
    peut_adopter: bool


class Vote(BaseModel):
    entree: int
    choix: str  # gauche, droite, egal


class Adopter(BaseModel):
    ou: str  # brique, session


class CandidatVeille(BaseModel):
    id: int
    date: str
    brique: str
    nom: str
    source: str
    licence: str
    commercial: bool | None
    besoins: str
    avis: str
    statut: str
    statut_nom: str


class Repere(BaseModel):
    """Un outil repéré par la veille du mois (Claude)."""
    brique: str
    nom: str = Field(min_length=1, max_length=100)
    source: str = Field(default="", max_length=300)
    licence: str = Field(default="", max_length=200)
    commercial: bool | None = None  # usage commercial permis ; None : à vérifier
    besoins: str = Field(default="", max_length=200)
    avis: str = ""


class Veille(BaseModel):
    candidats: list[Repere] = Field(min_length=1)


class StatVideo(BaseModel):
    """J11, Statistiques → Vidéos : une vidéo de la session (publication/rendement.py)."""
    id: str
    titre: str
    format: str
    langues: list[str]  # celles qui sont chez YouTube
    publiee_le: str
    vues: int
    heures: float
    abonnes: int
    retention: float | None
    impressions: int
    ctr: float | None  # %
    carte_h: float
    rt_min: float
    depenses_eur: float
    revenu_eur: float | None
    par_heure_carte: float | None  # heures vues pour une heure de carte
    par_minute_rt: float | None
    publications: list[dict]  # [{id, langue, revenu_eur}] : la saisie des revenus


class StatDestination(BaseModel):
    langue: str
    reseau: str
    chaine: str
    vues: int
    heures: float
    abonnes: int
    retention: float | None
    impressions: int
    ctr: float | None
    vues_28j: int
    heures_28j: float
    jours: list[dict]  # [{date, vues}]


class StatistiquesSession(BaseModel):
    videos: list[StatVideo]
    destinations: list[StatDestination]


class ResumeSession(BaseModel):
    id: str
    nom: str
    videos: int
    publiees: int
    vues: int
    heures: float
    carte_h: float
    rt_min: float
    depenses_eur: float
    revenu_eur: float | None
    par_heure_carte: float | None
    par_minute_rt: float | None


class Ensuite(BaseModel):
    """Un groupe de « quoi fabriquer ensuite » : session × format × chaîne (langue)."""
    session: str
    session_id: str
    format: str
    langue: str
    videos: int  # publiées depuis au moins 7 jours
    recentes: int
    heures: float
    carte_h: float
    rt_min: float
    revenu_eur: float | None
    par_heure_carte: float | None
    par_minute_rt: float | None
    assez: bool  # assez de chiffres pour être classé


class Statistiques(BaseModel):
    sessions: list[ResumeSession]
    ensuite: list[Ensuite]


class Revenu(BaseModel):
    revenu_eur: float | None = Field(default=None, ge=0)  # None : effacer


class Portee(BaseModel):
    """Les impressions et le taux de clic d'un jour, saisis par RT quand le rapport « reach » manque."""
    date: str  # AAAA-MM-JJ
    impressions: int = Field(ge=0)
    ctr: float = Field(ge=0, le=100)


class TempsRT(BaseModel):
    cle: str  # « video:<id> » ou « script:<code> »
    secondes: float
