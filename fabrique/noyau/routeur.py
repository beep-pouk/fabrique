"""Aiguillage des bases : les modèles de l'application « session » vont dans la base de la session en cours, tout le reste dans la base du
noyau. La session en cours est posée par « with session(s) » (une variable de contexte : chaque fil de l'API a la sienne) ; sans elle, la
lecture d'une base de session est refusée. Jamais de lien entre deux bases."""
import contextvars
from contextlib import contextmanager

from django.conf import settings
from django.db import connections

_courante = contextvars.ContextVar("session", default=None)
PREFIXE = "session_"


def chemin(s):
    return settings.SESSIONS / s.dossier / "session.sqlite3"


def ouvrir(s) -> str:
    """Branche la base de la session (même réglage que celle du noyau, autre fichier) ; rend son alias."""
    alias = PREFIXE + s.id
    if alias not in connections.settings:
        connections.settings[alias] = {**connections.settings["default"], "NAME": str(chemin(s))}
    return alias


@contextmanager
def session(s):
    jeton = _courante.set(ouvrir(s))
    try:
        yield
    finally:
        _courante.reset(jeton)


class Routeur:
    def db_for_read(self, model, **_):
        if model._meta.app_label != "session":
            return "default"
        if (alias := _courante.get()) is None:
            raise RuntimeError("aucune session en cours : la base d'une session se lit dans « with routeur.session(s) »")
        return alias

    db_for_write = db_for_read

    def allow_relation(self, a, b, **_):
        return a._state.db == b._state.db

    def allow_migrate(self, db, app_label, **_):
        return (app_label == "session") == db.startswith(PREFIXE)
