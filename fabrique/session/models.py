"""Base d'une session (sessions\\<dossier>\\session.sqlite3), lue et écrite seulement dans « with routeur.session(s) ». J1 : sa fiche ;
l'univers, les vidéos, les scripts arrivent aux jalons suivants."""
from django.db import models


class Fiche(models.Model):
    """L'identité de la session, gardée aussi dans sa propre base : un dossier de session se suffit à lui-même (export, restauration)."""
    id = models.CharField(primary_key=True, max_length=32)  # = noyau.Session.id
    nom = models.CharField(max_length=100)
    cree = models.DateTimeField(auto_now_add=True)
