"""Modes et dossiers, garde Bramble Studio, lignes de commande, instance unique."""
import os
import sqlite3
from pathlib import Path

import pytest

from fabrique import __main__ as porte
from fabrique import dossiers, garde, programme
from fabrique.noyau import sauvegarde
from fabrique.noyau.models import Parametre

CODE = Path(dossiers.__file__).resolve().parent


def test_modes(tmp_path, monkeypatch):
    code = tmp_path / "programme" / "app" / "fabrique"
    code.mkdir(parents=True)
    assert dossiers.programme(code) is None
    (tmp_path / "programme" / "runtime").mkdir()
    (tmp_path / "programme" / "runtime" / "python312.dll").write_bytes(b"")
    assert dossiers.programme(code) == tmp_path / "programme" and not dossiers.bac(code)
    (tmp_path / "programme" / "BAC_A_SABLE").write_text("essai")
    assert dossiers.bac(code)
    monkeypatch.delenv("FABRIQUE_RACINE")
    assert dossiers.racine(code) == tmp_path  # installée : le dossier qui contient le programme
    assert dossiers.racine() == CODE.parent / "dev"  # le dépôt du code
    monkeypatch.delenv("FABRIQUE_PORT", raising=False)
    assert dossiers.port() == dossiers.PORT_DEV


def test_simulation_sauf_essai_reel_demande(monkeypatch):
    """Le dépôt du code reste en simulation ; un essai réel sur le PC demande les deux : FABRIQUE_REEL=1 et le réglage « simulation » à non."""
    from fabrique.noyau import etat

    Parametre.ecrire("simulation", "non")
    try:
        assert etat.simulation()  # le réglage seul ne suffit pas hors installation
        monkeypatch.setenv("FABRIQUE_REEL", "1")
        assert not etat.simulation()
        Parametre.ecrire("simulation", "oui")
        assert etat.simulation()
    finally:
        Parametre.ecrire("simulation", "oui")


def test_garde(tmp_path, monkeypatch):
    studio = tmp_path / "Studio"
    monkeypatch.setattr(garde, "studio_bramble", lambda: studio)
    for p in garde.PROTEGES:
        assert garde.protege(studio / p) and garde.protege(studio / p / "x" / "y") and garde.protege(studio / p.lower())  # Windows ignore la casse
        with pytest.raises(garde.Refus):
            garde.verifier(studio / p / "sauvegardes")
    assert not garde.protege(studio / "FABRIQUE" / "donnees") and not garde.protege(studio / "DONNEES_AUTRES")


def test_racine_posee_sur_le_studio_refusee_avant_toute_ecriture(tmp_path, monkeypatch):
    """Fabrique dont la racine serait le studio lui-même : son dossier « donnees » serait DONNEES de Bramble Studio."""
    studio = tmp_path / "Studio"
    monkeypatch.setenv("FABRIQUE_RACINE", str(studio))
    monkeypatch.setattr(garde, "studio_bramble", lambda: studio)
    assert porte.main(["libre"]) == 1
    assert not studio.exists()


def test_dossier_des_sauvegardes_dans_bramble_refuse(tmp_path, monkeypatch):
    monkeypatch.setattr(garde, "studio_bramble", lambda: tmp_path)
    Parametre.ecrire("sauvegardes", str(tmp_path / "DONNEES" / "copies"))
    try:
        with pytest.raises(garde.Refus):
            sauvegarde.dossier()
    finally:
        Parametre.ecrire("sauvegardes", "")


def test_reglage_de_bramble_lu_sans_rien_ecrire(tmp_path, monkeypatch):
    """Installée chez RT : le dossier des sauvegardes vient du réglage de Bramble Studio, sa base ouverte immuable (aucun fichier touché)."""
    base = tmp_path / "DONNEES" / "studio.db"
    base.parent.mkdir()
    with sqlite3.connect(base) as c:
        c.execute("pragma journal_mode=wal")
        c.execute("create table core_parametre (cle text, valeur text)")
        c.execute("insert into core_parametre values ('sauvegardes', ?)", (str(tmp_path / "SAUVEGARDES"),))
    c.close()
    avant = {f.name: (f.stat().st_mtime_ns, f.read_bytes()) for f in base.parent.iterdir()}
    assert sauvegarde.bramble() is None  # développement : jamais le réglage de Bramble Studio
    monkeypatch.setattr(dossiers, "programme", lambda code=None: tmp_path / "programme")
    monkeypatch.setattr(garde, "studio_bramble", lambda: tmp_path)
    assert sauvegarde.bramble() == tmp_path / "SAUVEGARDES" / "fabrique"
    assert {f.name: (f.stat().st_mtime_ns, f.read_bytes()) for f in base.parent.iterdir()} == avant


def test_commande(monkeypatch, tmp_path):
    assert programme.commande("noyau")[1:] == ["-m", "fabrique", "noyau"]
    monkeypatch.setattr(dossiers, "programme", lambda code=None: tmp_path)
    assert programme.commande("executer", "sauvegarde") == [str(tmp_path / "Fabrique.exe"), "executer", "sauvegarde"]


def test_variables_d_un_parent_python_effacees(monkeypatch, tmp_path):
    """Lancée par Bramble Studio, Fabrique hérite de ses variables : elle impose les siennes, pour elle et ses enfants (17/11)."""
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings")
    for v in programme.HERITEES:
        monkeypatch.setenv(v, str(tmp_path))
    programme.environnement()
    assert os.environ["DJANGO_SETTINGS_MODULE"] == "fabrique.settings" and not {v.upper() for v in programme.HERITEES} & {k.upper() for k in os.environ}


def test_une_seule_fabrique_de_lignes_de_commande():
    for f in CODE.rglob("*.py"):
        if "tests" in f.parts or f.name == "programme.py":
            continue
        texte = f.read_text(encoding="utf-8")
        assert "sys.executable" not in texte and '"-m", "fabrique"' not in texte, f


def test_instance_unique(libre_port):
    prise = programme.prendre_port(libre_port)
    try:
        with pytest.raises(OSError):
            programme.prendre_port(libre_port)
    finally:
        prise.close()


def test_tuer_seulement_un_processus_de_l_app():
    import os

    assert programme.de_l_app(os.getpid())  # développement : un interpréteur Python
    assert not programme.de_l_app(4)  # « System » de Windows
    assert not programme.de_l_app(0)
