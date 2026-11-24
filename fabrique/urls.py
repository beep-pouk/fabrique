from django.urls import path, re_path

from fabrique.noyau import interface, telephone
from fabrique.noyau.api import api

urlpatterns = [path("api/", api.urls), path("iphone/", telephone.page), path("iphone/connexion", telephone.connexion),
               path("fenetre/entree", interface.entree), path("", interface.page), re_path(r"^(?P<chemin>assets/.+|[^/]+\.(?:svg|png|ico|woff2))$", interface.page)]
