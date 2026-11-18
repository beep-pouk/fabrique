"""Exporter puis importer une session à l'identique (J5) ; un fichier abîmé, trafiqué ou qui sort de la session : rien d'importé. Noms factices."""
import json
import sqlite3
import zipfile
from contextlib import closing

import pytest
from django.conf import settings

from fabrique.garde import Refus
from fabrique.noyau import bases, echange, routeur
from fabrique.noyau.models import Session
from fabrique.session import models as m


def contenu(s: Session) -> dict:
    """Chaque table de la base de la session (sauf la fiche, qui porte l'identifiant de la session), lignes triées."""
    with closing(sqlite3.connect(routeur.chemin(s))) as c:
        tables = [t for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'session_%' AND name != 'session_fiche'")]
        return {t: sorted(map(repr, c.execute(f"SELECT * FROM {t}"))) for t in tables}


@pytest.fixture
def remplie(request):
    s = bases.creer(f"Exportée {request.node.name}")
    with routeur.session(s):
        m.Langue.objects.create(code="xx", nom="Langue factice")
        m.Script.objects.create(code="s1e01", titre="Une histoire factice", langue="xx", statut="scenario")
        m.Video.objects.create(titre="Le petit renard", nom="2099-12-01-s1e01", script={}, recette={})
    d = settings.SESSIONS / s.dossier
    (d / "univers" / "personnages").mkdir(parents=True)
    (d / "univers" / "univers.json").write_bytes(json.dumps({"nom": "Univers factice"}).encode())
    (d / "univers" / "personnages" / "renard é.png").write_bytes(b"\x89PNG faux " * 100)
    (d / "videos" / "v1" / "final").mkdir(parents=True)
    (d / "videos" / "v1" / "final" / "v.mp4").write_bytes(b"video factice")
    (d / "_old").mkdir()
    (d / "_old" / "vieux.txt").write_bytes(b"jamais exporte")
    return s


def test_exporter_puis_importer_a_l_identique(remplie):
    z = echange.exporter(remplie)
    with zipfile.ZipFile(z) as f:
        noms = set(f.namelist())
    assert noms == {"manifeste.json", "session.sqlite3", "univers/univers.json", "univers/personnages/renard é.png"}  # ni vidéos, ni _old
    s = echange.importer(z, nom=f"Réimportée {remplie.nom}")
    assert s.id != remplie.id and s.dossier != remplie.dossier and not s.essais
    assert contenu(s) == contenu(remplie)
    a, b = echange.fichiers(remplie, False), echange.fichiers(s, False)
    assert set(a) == set(b) and all(echange.empreinte(a[k]) == echange.empreinte(b[k]) for k in a)
    with routeur.session(s):
        assert list(m.Fiche.objects.values_list("id", "nom")) == [(s.id, s.nom)]
    with pytest.raises(Refus, match="s'appelle déjà"):
        echange.importer(z, nom=s.nom)
    avec = echange.exporter(remplie, videos=True)
    with zipfile.ZipFile(avec) as f:
        assert "videos/v1/final/v.mp4" in f.namelist()


def test_un_fichier_trafique_n_importe_rien(remplie, tmp_path):
    z = echange.exporter(remplie)
    avant = Session.objects.count()

    def refait(nom, change):
        sortie = tmp_path / nom
        with zipfile.ZipFile(z) as src, zipfile.ZipFile(sortie, "w") as dst:
            for i in src.infolist():
                dst.writestr(i, change(i.filename, src.read(i.filename)))
        return sortie

    trafique = refait("trafique.fabrique", lambda n, d: b"autre chose" if n == "univers/univers.json" else d)
    with pytest.raises(Refus, match="empreinte fausse"):
        echange.importer(trafique, nom="Trafiquée")
    assert Session.objects.count() == avant and not (settings.SESSIONS / "trafiquee").exists()
    assert any(p.name.startswith(".import_") for p in (settings.DONNEES / "_corbeille").iterdir())  # le dossier à moitié posé, rangé
    sortant = tmp_path / "sortant.fabrique"
    with zipfile.ZipFile(z) as src, zipfile.ZipFile(sortant, "w") as dst:
        for i in src.infolist():
            dst.writestr(i, src.read(i.filename))
        dst.writestr("../hors.txt", b"x")
    with pytest.raises(Refus, match="chemins inattendus"):
        echange.importer(sortant, nom="Sortante")
    (tmp_path / "abime.fabrique").write_bytes(b"pas un zip")
    with pytest.raises(Refus, match="illisible"):
        echange.importer(tmp_path / "abime.fabrique", nom="Abîmée")
    assert Session.objects.count() == avant


def test_la_session_essais_ne_s_exporte_pas():
    with pytest.raises(Refus):
        echange.exporter(Session.objects.get(essais=True))
