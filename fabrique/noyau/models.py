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
    action = models.CharField(max_length=50)
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
    cree = models.DateTimeField(auto_now_add=True)
    lancee = models.DateTimeField(null=True)
    fin = models.DateTimeField(null=True)


class Chrono(models.Model):
    """La durée d'un morceau fini, toutes sessions confondues : les estimations en prennent la médiane par étape et outil."""
    etape = models.CharField(max_length=50)
    outil = models.CharField(max_length=50)
    secondes = models.FloatField()
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["etape", "outil"])]


class Depense(models.Model):
    """Un appel d'outil payant : estimé avant l'appel, réel quand le service le donne."""
    date = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=32)
    outil = models.CharField(max_length=50)
    estime_eur = models.FloatField()
    reel_eur = models.FloatField(null=True)
