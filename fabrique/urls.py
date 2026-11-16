from django.urls import path

from fabrique.noyau.api import api

urlpatterns = [path("api/", api.urls)]
