"""Reprise de Bramble Studio (plan § 10) sur un faux studio (noms factices) : à blanc puis pour de vrai, base lue avec ses écritures encore dans
le wal, fichiers copiés à l'identique, rien d'écrit chez Bramble, rejouable tant que rien n'est fabriqué, jamais les secrets."""
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest
from django.conf import settings
from django.db import connections

from fabrique import garde
from fabrique.garde import Refus
from fabrique.noyau import routeur
from fabrique.noyau.models import Session
from fabrique.session import bramble
from fabrique.session import models as m

TABLES = {
    "core_chaine": "id integer primary key, nom text",
    "core_episode": "id integer primary key, code text, titre text, langue text, statut text, date_prevue text, fiche_id integer, compilation text, duree real, "
                    "mots integer, note_finale real, date_fabrique text, date_publie text",
    "core_scenarioversion": "id integer primary key, episode_id integer, numero integer, auteur text, date text, contenu text, validee bool, resultat_regles text",
    "core_personnage": "id integer primary key, nom text, role text, statut text, espece text, description text, vetements text, yeux text, date_statut text, "
                       "plafond_references integer",
    "core_lieu": "id integer primary key, nom text, description text",
    "core_fiche": "id integer primary key, date_prevue text, statut text, type text, evenement text, obstination text, fait_nature text, saison text, "
                  "heros_id integer, camee_id integer, lieu_id integer",
    "core_idee": "id integer primary key, titre text, resume text, source text, tags text, statut text, creee text",
    "core_reference": "id integer primary key, personnage_id integer, fichier text, vue text, source text, validee bool, verifiee bool, date text",
    "core_langue": "id integer primary key, code text, nom text, ordre integer, rtl bool, police text, voix_validee bool, outil_voix text, reglages_voix text, "
                   "raison text, note text, preselectionnee bool",
    "core_parametre": "cle text primary key, valeur text",
}
SCENARIO = {"format": 2, "title": "Une histoire factice", "scenes": [{"id": 1, "narration": "Il était une fois."}]}


def ecrire(chemin: Path, contenu):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(contenu if isinstance(contenu, bytes) else json.dumps(contenu).encode() if not isinstance(contenu, str) else contenu.encode())


@pytest.fixture
def studio(tmp_path, monkeypatch):
    s = tmp_path / "STUDIO"
    for rel, contenu in {"PROJET/notes/univers.json": {"friends": {"Ami Un": {}}}, "PROJET/notes/langues.json": {}, "PROJET/BIBLE.md": "# Bible factice",
                         "PROJET/personnages/ami_un/reference.png": b"\x89PNG un", "PROJET/personnages/ami_un/references_gemini/1_face.jpg": b"jpg",
                         "PROJET/personnages/narrateur/poses/accueil.png": b"\x89PNG pose", "PROJET/voix/narrateur.wav": b"RIFF",
                         "PROJET/tests/voix_langues/xx/ref.wav": b"RIFF xx", "PROJET/notes/plan_editorial.json": {}, "PROJET/notes/registre_editorial.json": {},
                         "PROJET/notes/fiches_a_venir.json": [], "OUTILS/production/config.json": {"style": "factice"}, "OUTILS/production/regles.json": {},
                         "OUTILS/production/regles/REGLES_IMAGE.md": "| I-01 | règle | x |", "OUTILS/production/regles/LISEZ_MOI.md": "pas une règle",
                         "DONNEES/moteur/production_textes.py": "TEXTE = 1\n",
                         "PROJET/scenarios/2026-01-01-s1e01.json": {**SCENARIO, "title": "Modifiée hors de l'app"}}.items():
        ecrire(s / rel, contenu)
    c = sqlite3.connect(s / "DONNEES" / "studio.db")
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA wal_autocheckpoint=0")
    for t, cols in TABLES.items():
        c.execute(f"create table {t} ({cols})")
    c.execute("insert into core_chaine values (1, 'Session Factice')")
    c.execute("insert into core_personnage values (1, 'Ami Un', 'ami', 'actif', 'renard', 'd', 'v', 'y', null, 3)")
    c.execute("insert into core_lieu values (1, 'Clairière', 'calme')")
    c.execute("insert into core_fiche values (1, '2026-12-01', 'acceptee', 'histoire', 'e', 'o', 'f', 'hiver', 1, null, 1)")
    c.execute("insert into core_episode values (1, 's1e01', 'Une histoire factice', 'en', 'scenario', '2026-12-01', 1, '[]', null, null, null, null, null)")
    c.execute("insert into core_scenarioversion values (1, 1, 1, 'import', '2026-11-10 21:03:44.123456', ?, 1, '{}')", (json.dumps(SCENARIO),))
    c.execute("insert into core_reference values (1, 1, 'PROJET/personnages/ami_un/references_gemini/1_face.jpg', 'face', 'gemini', 1, 0, '2026-11-01 10:00:00')")
    c.execute("insert into core_langue values (1, 'xx', 'Langue factice', 1, 0, '', 1, 'outil_factice', ?, 'r', null, 1)",
              (json.dumps({"ref": "PROJET/tests/voix_langues/xx/ref.wav", "t3": "modele/t3.safetensors"}),))
    c.executemany("insert into core_parametre values (?, ?)", [("depart_chaine", "2026-12-01"), ("composant_ffmpeg", "D:/ailleurs"), ("cle_gemini", "SECRET"),
                                                               ("youtube_chaine", "SECRET"), ("code_telephone", "123456")])
    c.commit()  # reste dans le wal : la connexion reste ouverte, rien n'est reporté dans la base
    assert (s / "DONNEES" / "studio.db-wal").stat().st_size > 0
    monkeypatch.setattr(garde, "studio_bramble", lambda: s)
    yield s
    c.close()
    for x in Session.objects.filter(nom="Session Factice"):  # chaque test part sans session importée
        connections[routeur.ouvrir(x)].close()
        shutil.rmtree(settings.SESSIONS / x.dossier, ignore_errors=True)
        x.delete()


def empreinte(d: Path) -> dict:
    return {f.relative_to(d).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(d.rglob("*")) if f.is_file() and not f.name.endswith("-shm")}


def test_a_blanc_puis_pour_de_vrai(studio):
    avant = empreinte(studio)
    r = bramble.importer()
    assert r["a_blanc"] and r["session"] == "Session Factice" and not Session.objects.filter(nom="Session Factice").exists()
    assert r["base"] == {"episodes": 1, "versions": 1, "fiches": 1, "idees": 0, "personnages": 1, "lieux": 1, "references": 1, "langues": 1}
    assert r["fichiers"]["nombre"] == 15  # 11 fichiers et dossiers de la liste (dont 3 fichiers de personnages), la règle, la voix de référence de la langue
    r = bramble.importer(pour_de_vrai=True, acteur="RT")
    assert r["copies_identiques"] and r["source_intacte"] and empreinte(studio) == avant  # rien n'a bougé chez Bramble Studio
    s = Session.objects.get(nom="Session Factice")
    d = settings.SESSIONS / s.dossier
    assert (d / "univers" / "personnages" / "ami_un" / "reference.png").read_bytes() == b"\x89PNG un" and (d / "regles" / "REGLES_IMAGE.md").is_file()
    assert not (d / "regles" / "LISEZ_MOI.md").exists() and (d / "moteur" / "production_textes.py").is_file()
    assert json.loads((d / "reglages" / "parametres_bramble.json").read_text(encoding="utf-8")) == {"depart_chaine": "2026-12-01", "composant_ffmpeg": "D:/ailleurs"}
    with routeur.session(s):
        sc = m.Script.objects.get(code="s1e01")
        assert str(sc.date_prevue) == "2026-12-01" and [v.auteur for v in sc.versions.order_by("numero")] == ["import", "fichier"]  # le fichier modifié hors de l'app
        assert m.Reference.objects.get().fichier == "univers/personnages/ami_un/references_gemini/1_face.jpg"
        l = m.Langue.objects.get(code="xx")
        assert l.reglages_voix == {"ref": "univers/voix_langues/xx/ref.wav", "t3": "modele/t3.safetensors"} and (d / l.reglages_voix["ref"]).is_file()
        assert m.Prevision.objects.get().details["heros"] == "Ami Un" and m.Prevision.objects.get().details["episode"] == "s1e01"
    assert json.loads((d / "import_bramble.json").read_text(encoding="utf-8"))["copies_identiques"]


def test_rejouable_tant_que_rien_n_est_fabrique(studio):
    bramble.importer(pour_de_vrai=True)
    s = Session.objects.get(nom="Session Factice")
    bramble.importer(pour_de_vrai=True)
    s2 = Session.objects.get(nom="Session Factice")
    assert s2.id != s.id and list((settings.DONNEES / "_old").glob(f"import_*/{s.dossier}/session.sqlite3"))
    with routeur.session(s2):
        m.Video.objects.create(titre="x", script={}, recette={})
    with pytest.raises(Refus, match="déjà fabriqué"):
        bramble.importer(pour_de_vrai=True)
    with routeur.session(s2):
        m.Reglage.objects.filter(cle="origine").delete()
    with pytest.raises(Refus, match="ne vient pas de l'import"):
        bramble.importer(pour_de_vrai=True)


def test_sans_bramble_refus(monkeypatch):
    monkeypatch.setattr(garde, "studio_bramble", lambda: None)
    with pytest.raises(Refus, match="introuvable"):
        bramble.importer()


def test_un_import_rate_ne_bloque_rien(studio):
    c = sqlite3.connect(studio / "DONNEES" / "studio.db")
    c.execute("insert into core_reference values (2, 99, 'PROJET/personnages/x.png', 'face', 'gemini', 1, 0, '2026-11-01 10:00:00')")  # orpheline
    c.commit()
    with pytest.raises(Refus, match="inattendues"):
        bramble.importer(pour_de_vrai=True)
    assert not Session.objects.filter(nom="Session Factice").exists() and list((settings.DONNEES / "_old").glob("import_rate_*"))
    c.execute("delete from core_reference where id = 2")
    c.commit()
    c.close()
    assert bramble.importer(pour_de_vrai=True)["copies_identiques"]  # rejouable


def test_rejeu_refuse_si_des_versions_ont_ete_ecrites(studio):
    from datetime import datetime, timezone

    bramble.importer(pour_de_vrai=True)
    s = Session.objects.get(nom="Session Factice")
    with routeur.session(s):
        m.VersionScript.objects.create(script=m.Script.objects.get(code="s1e01"), numero=9, auteur="RT", date=datetime.now(timezone.utc), contenu={})
    with pytest.raises(Refus, match="écrite"):
        bramble.importer(pour_de_vrai=True)
