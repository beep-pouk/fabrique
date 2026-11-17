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


class Video(models.Model):
    """Une vidéo fabriquée : son script et la recette qui l'a faite (copiés tels quels : une recette changée ensuite ne la touche pas)."""
    id = models.CharField(primary_key=True, max_length=32, default=identifiant, editable=False)
    titre = models.CharField(max_length=200)
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
