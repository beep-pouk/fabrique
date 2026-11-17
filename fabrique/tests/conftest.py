"""Les tests jouent sur un dossier temporaire (jamais un vrai dossier FABRIQUE), en développement donc en simulation, sans fenêtre visible."""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

RACINE = Path(tempfile.mkdtemp(prefix="fabrique_tests_"))
os.environ["FABRIQUE_RACINE"] = str(RACINE)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"  # rendu par le processeur : captures identiques d'une fois à l'autre
os.environ["QT_QPA_FONTDIR"] = os.path.join(os.environ["WINDIR"], "Fonts")  # sans fenêtre, Qt ne trouve pas seul les polices de Windows
from fabrique import programme  # noqa: E402

programme.environnement()  # comme le programme : ni le DJANGO_SETTINGS_MODULE ni le PYTHONPATH d'un parent

import django  # noqa: E402

django.setup()

from fabrique.noyau import bases  # noqa: E402

bases.migrer()


@pytest.fixture(scope="session", autouse=True)
def menage():
    yield
    from django.db import connections

    connections.close_all()
    shutil.rmtree(RACINE, ignore_errors=True)


@pytest.fixture
def libre_port():
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
