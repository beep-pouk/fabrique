"""Base du noyau : sessions, réglages (clés chiffrées comprises), journal des actions. Aucun lien vers la base d'une session : une session est
désignée par son identifiant stable."""
import uuid

from django.db import models


def identifiant() -> str:
    return uuid.uuid4().hex


class Session(models.Model):
    id = models.CharField(primary_key=True, max_length=32, default=identifiant, editable=False)  # stable, jamais réutilisé
    nom = models.CharField(max_length=100, unique=True)
    dossier = models.CharField(max_length=100, unique=True)  # sous sessions\
    essais = models.BooleanField(default=False)  # session « Essais » : sans destination, seule à accepter les essais de construction
    priorite = models.IntegerField(default=0)  # dans la file, la plus haute d'abord (après les sessions réelles, « Essais » en dernier)
    cree = models.DateTimeField(auto_now_add=True)
    pause = models.BooleanField(default=False)  # rien de la session ne part dans la file (ce qui tourne finit)
    archivee = models.DateTimeField(null=True)  # rangée : en pause, hors du mur des sessions, jamais effacée


class Parametre(models.Model):
    cle = models.CharField(primary_key=True, max_length=100)
    valeur = models.TextField(default="")

    @classmethod
    def lire(cls, cle: str, defaut: str = "") -> str:
        p = cls.objects.filter(cle=cle).first()
        return p.valeur if p else defaut

    @classmethod
    def ecrire(cls, cle: str, valeur: str):
        cls.objects.update_or_create(cle=cle, defaults={"valeur": valeur})


class Journal(models.Model):
    """Qui a fait quoi : « RT » pour un clic de la fenêtre, « claude », « noyau » pour une tâche automatique."""
    date = models.DateTimeField(auto_now_add=True)
    acteur = models.CharField(max_length=20)
    action = models.CharField(max_length=50, db_index=True)  # l'ordre strict et l'historique d'une session y cherchent par action
    detail = models.JSONField(default=dict)


def noter(acteur: str, action: str, **detail):
    Journal.objects.create(acteur=acteur, action=action, detail=detail)


class Tache(models.Model):
    """La file unique (moteur/file.py) : la fabrication d'une vidéo d'une session, désignées par leurs identifiants stables."""
    ETATS = ("attente", "en_cours", "pause", "finie", "erreur", "annulee")
    session_id = models.CharField(max_length=32)
    video_id = models.CharField(max_length=32)
    titre = models.CharField(max_length=200)
    acteur = models.CharField(max_length=20)
    etat = models.CharField(max_length=10, default="attente")
    raison = models.CharField(max_length=500, default="")  # pourquoi elle attend (carte prise) ou s'est arrêtée, en clair
    alertes = models.JSONField(default=list)
    executeur = models.IntegerField(default=0)  # le pid de l'exécuteur qui la tient (pris d'un coup, en base : jamais deux à la fois)
    relances = models.IntegerField(default=0)  # relancée sans qu'un morceau ait fini depuis (plantage, coupures) : à 3, erreur
    banc = models.IntegerField(default=0)  # un banc à l'aveugle (moteur/bancs.py) sur une vidéo finie, au lieu de sa fabrication
    cree = models.DateTimeField(auto_now_add=True)
    lancee = models.DateTimeField(null=True)
    fin = models.DateTimeField(null=True)


class Chrono(models.Model):
    """La durée d'un morceau fini, toutes sessions confondues : les estimations en prennent la médiane par format, étape (donc unité : plan,
    scène ou vidéo) et outil."""
    recette = models.CharField(max_length=50)
    etape = models.CharField(max_length=50)
    outil = models.CharField(max_length=50)
    secondes = models.FloatField()
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["recette", "etape", "outil"])]


class Depense(models.Model):
    """Un appel d'outil payant : estimé avant l'appel, réel quand le service le donne."""
    date = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=32)
    video_id = models.CharField(max_length=32, default="")  # la vidéo fabriquée (ou mise au banc) : Statistiques, par vidéo
    outil = models.CharField(max_length=50)
    estime_eur = models.FloatField()
    reel_eur = models.FloatField(null=True)


class Outil(models.Model):
    """Ce qui change d'un outil après la livraison (sa fiche reste une donnée du programme, jamais réécrite) : son état, la version installée."""
    id = models.CharField(primary_key=True, max_length=50)  # celui de la fiche
    etat = models.CharField(max_length=12, default="")  # vide : celui de la fiche ; en service seulement après un banc gagné et l'accord de RT
    version = models.CharField(max_length=50, default="")  # installée dans outils\<id>\<version>


class Banc(models.Model):
    """Un banc à l'aveugle (moteur/bancs.py) : l'outil en place (a) contre un autre (b), sur les demandes de morceaux finis d'une vidéo."""
    ETATS = ("attente", "en_cours", "a_voter", "fini", "erreur", "annule")  # « a_voter » : votes modifiables jusqu'à « Rendre le verdict »
    brique = models.CharField(max_length=30)
    outil_a = models.CharField(max_length=50)
    outil_b = models.CharField(max_length=50)
    session_id = models.CharField(max_length=32)
    video_id = models.CharField(max_length=32)
    juge = models.CharField(max_length=30, default="")  # un seul par banc ; vide : sans juge
    acteur = models.CharField(max_length=20)
    etat = models.CharField(max_length=10, default="attente")
    raison = models.CharField(max_length=500, default="")
    entrees = models.JSONField(default=list)  # [{unite, langue, texte, demande (chemin), gauche: "a"|"b"}]
    notes = models.JSONField(default=dict)  # « i » → {a, b} : notes du juge, sur 10
    votes = models.JSONField(default=dict)  # « i » → "a", "b" ou "egal" (l'outil réel, jamais montré à RT avant le verdict)
    verdict = models.JSONField(default=dict)
    versions = models.JSONField(default=dict)  # « a », « b » → la version de chaque outil au banc : une autre version ne s'adopte pas sur ce verdict
    adopte = models.CharField(max_length=100, default="")  # « brique » ou « session » : où le vainqueur est devenu le défaut
    cree = models.DateTimeField(auto_now_add=True)
    fini = models.DateTimeField(null=True)


class Candidat(models.Model):
    """La veille mensuelle : un outil repéré (par Claude, recherche du mois), jamais en service sans banc."""
    date = models.DateField()
    brique = models.CharField(max_length=30)
    nom = models.CharField(max_length=100)
    source = models.CharField(max_length=300, default="")
    licence = models.CharField(max_length=200, default="")
    commercial = models.BooleanField(null=True)  # usage commercial permis (la chaîne est monétisée) ; None : à vérifier
    besoins = models.CharField(max_length=200, default="")
    avis = models.TextField(default="")
    statut = models.CharField(max_length=12, default="nouveau")  # nouveau, a_essayer, ecarte, essaye
