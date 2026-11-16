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
