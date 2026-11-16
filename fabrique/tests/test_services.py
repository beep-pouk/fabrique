"""Sauvegarde et restauration, tâche détachée, sauvegarde du soir, clés, état, mises à jour, journaux, diagnostic."""
import json
import os
import zipfile
from datetime import datetime, timedelta

import pytest
from django.conf import settings

from fabrique import journaux
from fabrique.garde import Refus
from fabrique.noyau import bases, cles, diagnostic, etat, routeur, sauvegarde, taches, versions
from fabrique.noyau.models import Journal, Parametre
from fabrique.session.models import Fiche


@pytest.fixture
def dossier(tmp_path):
    Parametre.ecrire("sauvegardes", str(tmp_path / "sauvegardes"))
    yield tmp_path / "sauvegardes"
    Parametre.ecrire("sauvegardes", "")


def test_sauvegarder_puis_restaurer(dossier):
    s = bases.creer("Sauvegardée")
    regles = settings.SESSIONS / s.dossier / "regles.json"
    regles.write_text('{"a": 1}', encoding="utf-8")
    with routeur.session(s):
        Fiche.objects.filter(id=s.id).update(nom="avant")
    z = sauvegarde.sauvegarder()
    with zipfile.ZipFile(z) as f:
        assert {"donnees/noyau.sqlite3", f"sessions/{s.dossier}/session.sqlite3", f"sessions/{s.dossier}/regles.json"} <= set(f.namelist())
    with routeur.session(s):
        Fiche.objects.filter(id=s.id).update(nom="après")
    Parametre.ecrire("temoin", "après")
    regles.write_text('{"a": 2}', encoding="utf-8")
    message = sauvegarde.restaurer(z.name)
    with routeur.session(s):
        assert Fiche.objects.get(id=s.id).nom == "avant"
    assert Parametre.lire("temoin") == "" and json.loads(regles.read_text(encoding="utf-8")) == {"a": 1}
    old = next((settings.DONNEES / "_old").glob("restauration_*"))
    assert json.loads((old / "sessions" / s.dossier / "regles.json").read_text(encoding="utf-8")) == {"a": 2} and "_old" in message
    assert (old / "donnees" / "noyau.sqlite3").is_file() and not (old / "_zip").exists()


def test_elaguer_trente_jours(tmp_path):
    maintenant = datetime(2026, 11, 16, 23, 30)
    for jours in (40, 31, 10, 0):
        (tmp_path / (maintenant - timedelta(days=jours)).strftime(sauvegarde.NOM)).write_bytes(b"")
    (tmp_path / "fabrique_autre.zip").write_bytes(b"")
    partis = sauvegarde.elaguer(tmp_path, maintenant)
    assert len(partis) == 2 and len(sauvegarde.lister(tmp_path)) == 2 and (tmp_path / "fabrique_autre.zip").exists()
    vieux = tmp_path / "seule"
    vieux.mkdir()
    (vieux / (maintenant - timedelta(days=90)).strftime(sauvegarde.NOM)).write_bytes(b"")
    assert sauvegarde.elaguer(vieux, maintenant) == []  # la plus récente reste toujours


def test_zip_hostile_ou_abime_refuse(dossier):
    dossier.mkdir(parents=True, exist_ok=True)
    nom = datetime(2026, 1, 1).strftime(sauvegarde.NOM)
    with zipfile.ZipFile(dossier / nom, "w") as z:
        z.writestr("sessions/x/../../../dehors.txt", "non")
    with pytest.raises(Refus, match="inattendus"):
        sauvegarde.restaurer(nom)
    (dossier / nom).write_bytes(b"pas un zip")
    with pytest.raises(Refus, match="abîmée"):
        sauvegarde.restaurer(nom)
    with pytest.raises(Refus, match="inconnue"):
        sauvegarde.restaurer("../" + nom)


def test_tache_detachee_de_sauvegarde(dossier):
    assert taches.executer("sauvegarde") == 0
    e = taches.lire("sauvegarde")
    assert e["etat"] == "faite" and (dossier / e["fichier"]).is_file() and taches.occupe() == ""
    taches.ecrire("sauvegarde", {"etat": "en_cours", "pid": os.getpid()})
    assert taches.occupe() == "sauvegarde" and taches.executer("sauvegarde") == 3
    with pytest.raises(Refus):
        taches.lancer("sauvegarde", "RT")
    taches.ecrire("sauvegarde", {"etat": "en_cours", "pid": 999999})  # processus mort : ne compte plus
    assert taches.occupe() == ""
    assert taches.executer("inconnue") == 2


def test_sauvegarde_du_soir_due():
    d = lambda s: datetime.fromisoformat(s)  # noqa: E731
    assert taches.due("", d("2026-11-16T10:00"))  # jamais faite : rattrapage au démarrage
    assert not taches.due("2026-11-16T23:31", d("2026-11-17T10:00"))
    assert taches.due("2026-11-16T23:29", d("2026-11-16T23:35"))
    assert not taches.due("2026-11-16T23:35", d("2026-11-17T23:29"))
    assert taches.due("2026-11-15T23:35", d("2026-11-17T08:00"))


def test_cles_chiffrees_jamais_ecrites_en_clair():
    assert cles.enregistrer("gemini", " cle-de-test-123 ", "RT").startswith("Clé")
    assert cles.lire("gemini") == "cle-de-test-123"
    assert "cle-de-test-123" not in Parametre.lire("cle_gemini")
    assert "cle-de-test-123" not in json.dumps(list(Journal.objects.values("detail")))
    assert {c["nom"]: c["ou"] for c in cles.etat()}["gemini"] == "enregistrée"
    Parametre.ecrire("cle_ntfy", "illisible")
    assert {c["nom"]: c["ou"] for c in cles.etat()}["ntfy"].startswith("illisible")
    for nom, valeur in (("inconnue", "x"), ("gemini", "deux mots"), ("gemini", "")):
        with pytest.raises(Refus):
            cles.enregistrer(nom, valeur, "RT")


def test_etat_ecrit_pour_claude(monkeypatch):
    monkeypatch.setattr(etat, "SEUIL_DISQUE_GO", 10**9)
    e = etat.ecrire()
    lu = json.loads((settings.DONNEES / "etat.json").read_text(encoding="utf-8"))
    assert lu["mode"] == "simulation" and "Essais" in lu["sessions"] and lu["file"] == {"attente": [], "encours": None}
    assert lu["alertes"] and lu["alertes"][0].startswith("disque")
    assert (settings.DONNEES / "etat.txt").read_text(encoding="utf-8").startswith(f"[{datetime.now():%d/%m}") and e["texte"][-1].startswith("! disque")


def test_versions(tmp_path):
    (tmp_path / "f.exe").write_bytes(b"x")
    (tmp_path / "versions.json").write_text(json.dumps([{"version": "9.0.0", "fichier": "f.exe"}, {"version": "abc", "fichier": "f.exe"},
                                                        {"version": "9.1.0", "fichier": "../f.exe"}, {"version": "8.0.0", "fichier": "absent.exe"}]))
    assert [v["version"] for v in versions.catalogue(tmp_path)] == ["9.0.0"]
    assert versions.raison(None) == "en développement, pas de mise à jour"
    with pytest.raises(Refus):
        versions.mettre_a_jour("RT")


def test_journaux_masques_et_relus(tmp_path):
    (tmp_path / "noyau.log").write_text("2026-11-16 10:00:00,1 WARNING x : jeton ya29.abc-def secret\n2026-11-16 10:00:01,2 INFO x : rien\n", encoding="utf-8")
    r = journaux.recents(tmp_path)
    assert len(r) == 1 and "[masqué]" in r[0]["message"] and "ya29" not in r[0]["message"] and r[0]["niveau"] == "à surveiller"
    vieux = tmp_path / "vieux.log"
    vieux.write_text("")
    os.utime(vieux, (0, 0))
    assert journaux.elaguer(tmp_path) == 1 and not vieux.exists()


def test_diagnostic(monkeypatch):
    lignes = []
    monkeypatch.setattr(diagnostic.Client, "repond", lambda self: True)
    assert diagnostic.jouer(lignes.append) == 0
    assert any("base donnees/noyau.sqlite3" in l for l in lignes) and all(l.startswith("ok") for l in lignes)
