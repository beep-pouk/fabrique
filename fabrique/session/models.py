"""Base d'une session (sessions\\<dossier>\\session.sqlite3), lue et écrite seulement dans « with routeur.session(s) » : sa fiche, ses réglages,
ses vidéos et leurs morceaux (moteur/execution.py). L'univers, les scripts, le calendrier arrivent aux jalons suivants."""
from django.db import models

from fabrique.noyau.models import identifiant


class Fiche(models.Model):
    """L'identité de la session, gardée aussi dans sa propre base : un dossier de session se suffit à lui-même (export, restauration)."""
    id = models.CharField(primary_key=True, max_length=32)  # = noyau.Session.id
    nom = models.CharField(max_length=100)
    cree = models.DateTimeField(auto_now_add=True)


class Reglage(models.Model):
    """Réglages de la session : « outil.<brique> » (son outil par défaut), « plafond_eur » (outils payants, par mois)."""
    cle = models.CharField(primary_key=True, max_length=100)
    valeur = models.TextField(default="")


class Script(models.Model):
    """Un script de la session (repris de Bramble Studio : un épisode) ; le calendrier = sa date prévue et son statut."""
    id = models.CharField(primary_key=True, max_length=32, default=identifiant, editable=False)
    code = models.CharField(max_length=20, unique=True)
    titre = models.CharField(max_length=200)
    langue = models.CharField(max_length=10)
    statut = models.CharField(max_length=20)
    date_prevue = models.DateField(null=True)
    details = models.JSONField(default=dict)  # ce que la session d'origine savait de plus (compilation, durée, mots…)


class VersionScript(models.Model):
    script = models.ForeignKey(Script, on_delete=models.CASCADE, related_name="versions")
    numero = models.IntegerField()
    auteur = models.CharField(max_length=20)
    date = models.DateTimeField()
    contenu = models.JSONField()
    validee = models.BooleanField(default=False)
    regles = models.JSONField(default=dict)  # résultat des règles à l'enregistrement

    class Meta:
        constraints = [models.UniqueConstraint(fields=["script", "numero"], name="version_unique")]


class Prevision(models.Model):
    """Le calendrier éditorial : une fiche proposée ou acceptée (date, type, héros, lieu… dans « details »)."""
    date = models.DateField(null=True)
    statut = models.CharField(max_length=20)
    details = models.JSONField(default=dict)


class Idee(models.Model):
    titre = models.CharField(max_length=200)
    resume = models.TextField(default="")
    source = models.CharField(max_length=200, default="")
    tags = models.JSONField(default=list)
    statut = models.CharField(max_length=20, default="nouvelle")
    creee = models.DateTimeField()


class Personnage(models.Model):
    nom = models.CharField(max_length=100)
    role = models.CharField(max_length=50, default="")
    statut = models.CharField(max_length=20, default="actif")
    details = models.JSONField(default=dict)  # espèce, description, vêtements, yeux, date du statut, plafond de références


class Lieu(models.Model):
    nom = models.CharField(max_length=100)
    description = models.TextField(default="")


class Reference(models.Model):
    """Une image de référence d'un personnage ; le fichier est sous univers\\ de la session."""
    personnage = models.ForeignKey(Personnage, on_delete=models.CASCADE, related_name="references")
    fichier = models.CharField(max_length=500)
    vue = models.CharField(max_length=50, default="")
    source = models.CharField(max_length=100, default="")
    validee = models.BooleanField(default=False)
    verifiee = models.BooleanField(default=False)
    date = models.DateTimeField()


class Langue(models.Model):
    """Une langue de la session et sa voix (outil, réglages : chemins relatifs à la session ou au dossier des modèles)."""
    code = models.CharField(max_length=10, unique=True)
    nom = models.CharField(max_length=50)
    ordre = models.IntegerField(default=0)
    rtl = models.BooleanField(default=False)
    police = models.CharField(max_length=100, default="")
    voix_validee = models.BooleanField(default=False)
    outil_voix = models.CharField(max_length=50, default="")
    reglages_voix = models.JSONField(default=dict)
    raison = models.TextField(default="")
    note = models.TextField(default="")
    preselectionnee = models.BooleanField(default=False)


class Video(models.Model):
    """Une vidéo fabriquée : son script et la recette qui l'a faite (copiés tels quels : une recette changée ensuite ne la touche pas)."""
    id = models.CharField(primary_key=True, max_length=32, default=identifiant, editable=False)
    titre = models.CharField(max_length=200)
    nom = models.CharField(max_length=100, default="")  # nom de fichier du script (F1 : « <date>-<code> », comme Bramble Studio ; le code dit la saison)
    script = models.JSONField()
    recette = models.JSONField()
    cree = models.DateTimeField(auto_now_add=True)


class Morceau(models.Model):
    """Étape × unité (plan « s1/p2 », scène « s1 », vidéo « ») × langue (« » : commun à toutes) ; fini = son dossier existe sous son nom."""
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="morceaux")
    etape = models.CharField(max_length=50)
    brique = models.CharField(max_length=50)
    unite = models.CharField(max_length=100)
    langue = models.CharField(max_length=10)
    ordre = models.IntegerField()
    outil = models.CharField(max_length=50)
    etat = models.CharField(max_length=10, default="attente")  # attente, fini, erreur
    essais = models.IntegerField(default=0)
    secondes = models.FloatField(null=True)
    message = models.CharField(max_length=500, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["video", "etape", "unite", "langue"], name="morceau_unique")]


class Destination(models.Model):
    """Où sont publiées les vidéos d'une langue : une par langue et par réseau (J4 : « youtube »), et à part en simulation (le faux YouTube :
    jamais un vrai jeton, et une vraie chaîne jamais marquée refusée par le faux). Le jeton de rafraîchissement est chiffré par Windows
    (noyau/cles.py) : jamais en clair, jamais rendu par l'API, jamais journalisé."""
    langue = models.CharField(max_length=10)
    reseau = models.CharField(max_length=20)
    simulation = models.BooleanField(default=False)
    chaine_id = models.CharField(max_length=100, default="")  # lus chez le réseau
    chaine = models.CharField(max_length=200, default="")
    playlists = models.JSONField(default=list)  # [{"id", "titre"}]
    jeton = models.TextField(default="")  # chiffré ; vide : pas reliée
    reliee = models.DateTimeField(null=True)  # date de connexion
    refusee = models.DateTimeField(null=True)  # le réseau a refusé le jeton (invalid_grant) : à relier

    class Meta:
        constraints = [models.UniqueConstraint(fields=["langue", "reseau", "simulation"], name="destination_unique")]


class Publication(models.Model):
    """Une vidéo × une langue (celle du script : ses fichiers sous « commun », puis chaque version de langue), envoyée sur la destination de
    sa langue (une langue sans chaîne reliée : brouillon possible, envoi refusé). Repris de Bramble Studio (core/models.Publication) : textes
    retouchés en versions (jamais écrasées), envoi reprenable suivi dans « envoi » (session d'envoi le temps de l'envoi, octets confirmés,
    étapes faites)."""
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="publications")
    langue = models.CharField(max_length=10)
    dossier = models.CharField(max_length=10)  # « commun » (langue du script) ou la langue : videos\<id>\<dossier>\atelier\<nom>\final
    fichier = models.CharField(max_length=200, default="")  # la vidéo, dans final
    miniature = models.CharField(max_length=200, default="")  # dans final ; vide : aucune
    titre = models.CharField(max_length=100, default="")
    description = models.TextField(default="")
    tags = models.JSONField(default=list)
    playlist = models.CharField(max_length=100, default="")
    enfants = models.BooleanField(default=True)  # « conçue pour les enfants »
    ia = models.BooleanField(default=True)  # déclaration IA (containsSyntheticMedia)
    planifiee_le = models.DateTimeField(null=True)  # le créneau (publishAt)
    non_repertorie = models.BooleanField(default=False)  # première publication de sa destination : non répertoriée, sans publishAt
    simulation = models.BooleanField(default=False)  # envoyée au faux YouTube (posé au clic « Publier »)
    statut = models.CharField(max_length=20, default="brouillon")  # brouillon, en_file, envoi, erreur, planifiee, non_repertoriee
    identifiant_youtube = models.CharField(max_length=50, default="")
    envoi = models.JSONField(default=dict)
    versions = models.JSONField(default=list)  # [{numero, titre, description, auteur, date}]

    class Meta:
        constraints = [models.UniqueConstraint(fields=["video", "langue"], name="publication_unique")]


class StatistiqueJour(models.Model):
    """Un jour d'une chaîne (publication vide) ou d'une de ses vidéos chez YouTube (reports.query de l'API Analytics : chiffres en retard de
    48 à 72 h, relus et corrigés au relevé suivant). Repris de Bramble Studio (core/models.StatistiqueJour), par destination."""
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name="statistiques")
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, null=True, related_name="statistiques")
    date = models.DateField()
    vues = models.PositiveIntegerField(default=0)
    heures = models.FloatField(default=0)
    duree_moyenne = models.FloatField(null=True)
    retention = models.FloatField(null=True)  # % vu
    abonnes = models.IntegerField(default=0)  # gagnés
    abonnes_perdus = models.IntegerField(default=0)
