"""Base du noyau et bases de session : aiguillage, identifiants stables, aucun lien entre deux bases, « migrer »."""
import pytest
from django.conf import settings
from django.db import IntegrityError

from fabrique.noyau import bases, routeur
from fabrique.noyau.models import Session
from fabrique.session.models import Fiche


def test_aiguillage_vers_la_session_en_cours():
    a, b = bases.creer("Aiguillage A"), bases.creer("Aiguillage B")
    assert routeur.chemin(a) != routeur.chemin(b) and routeur.chemin(a).is_file()
    with routeur.session(a):
        assert Fiche.objects.get().nom == "Aiguillage A"
        Fiche.objects.create(id="seulement_a", nom="dans A")
    with routeur.session(b):
        assert list(Fiche.objects.values_list("id", flat=True)) == [b.id]
        with routeur.session(a):  # imbriquée : la plus proche gagne, puis on revient
            assert Fiche.objects.filter(id="seulement_a").exists()
        assert not Fiche.objects.filter(id="seulement_a").exists()


def test_sans_session_en_cours_refus():
    with pytest.raises(RuntimeError):
        Fiche.objects.count()


def test_identifiants_stables_et_dossiers():
    s = bases.creer("Été à Noël !")
    assert len(s.id) == 32 and s.dossier == "ete_a_noel"
    assert bases.creer("Ete a Noel").dossier == "ete_a_noel_2"  # même dossier : un autre, jamais le même
    with pytest.raises(IntegrityError):
        Session.objects.create(nom="Été à Noël !", dossier="autre")


def test_aucun_lien_entre_deux_bases():
    s = bases.creer("Lien")
    with routeur.session(s):
        fiche = Fiche.objects.get()
    assert not routeur.Routeur().allow_relation(s, fiche)
    assert not routeur.Routeur().allow_migrate("default", "session") and not routeur.Routeur().allow_migrate("session_x", "noyau")


def test_migrer_copie_chaque_base_d_abord():
    s = bases.creer("Migrer")
    copie = bases.migrer()
    assert (copie / "donnees" / "noyau.sqlite3").is_file() and (copie / "sessions" / s.dossier / "session.sqlite3").is_file()
    assert copie.parent == settings.DONNEES / "_old"
    assert Session.objects.filter(essais=True).count() == 1  # une seule session d'amorçage, « Essais »
    assert not bases.en_attente()
