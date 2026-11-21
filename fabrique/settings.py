"""Réglages Django du noyau. Une base du noyau (donnees\\noyau.sqlite3) ; la base de chaque session est branchée à la demande par
noyau/routeur.py (sessions\\<dossier>\\session.sqlite3). L'API locale, et une seule page : celle de
l'iPhone (noyau/telephone.py), jointe par `tailscale serve` (hôte *.ts.net)."""
import tomllib

from fabrique import dossiers

RACINE = dossiers.racine()
DONNEES = dossiers.donnees(RACINE)
SESSIONS = dossiers.sessions(RACINE)
JOURNAUX = DONNEES / "journaux"
VERSION = tomllib.loads((dossiers.CODE.parent / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]  # seule source

SECRET_KEY = "fabrique-api-locale"  # rien n'est signé : l'API se protège par jeton (noyau/jetons.py)
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost", ".ts.net"]
INSTALLED_APPS = ["fabrique.noyau", "fabrique.session"]
MIDDLEWARE = []
ROOT_URLCONF = "fabrique.urls"
BASE = {"ENGINE": "django.db.backends.sqlite3", "OPTIONS": {"init_command": "PRAGMA journal_mode=WAL;PRAGMA synchronous=NORMAL", "transaction_mode": "IMMEDIATE", "timeout": 20}}
DATABASES = {"default": {**BASE, "NAME": DONNEES / "noyau.sqlite3"}}
DATABASE_ROUTERS = ["fabrique.noyau.routeur.Routeur"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "Europe/Paris"
LANGUAGE_CODE = "fr"
LOGGING_CONFIG = None  # journaux.configurer s'en charge, un fichier par processus
