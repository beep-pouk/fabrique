from django.urls import path

from fabrique.noyau import telephone
from fabrique.noyau.api import api

urlpatterns = [path("api/", api.urls), path("iphone/", telephone.page), path("iphone/connexion", telephone.connexion)]
