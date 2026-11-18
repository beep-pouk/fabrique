"""Le moteur à recettes (J2), en simulation (faux outils, ffmpeg, sans carte) : recette d'essai de bout en bout ; exécuteur tué en plein
milieu puis repris sans rien perdre ; outil par défaut changé par une donnée, sans toucher au code ; refus quand Bramble Studio fabrique
(simulé) ; ordre de la file ; trois essais puis alerte ; outil payant (plafond, une nouvelle tentative, repli) ; recettes contrôlées ;
estimations par médiane."""
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client as Navigateur

from fabrique import garde, programme
from fabrique.garde import Refus
from fabrique.moteur import carte, execution, file, outils, recettes
from fabrique.noyau import bases, jetons, routeur, taches
from fabrique.noyau.models import Chrono, Depense, Parametre, Session, Tache
from fabrique.session.models import Langue, Morceau, Reglage

DEPOT = Path(__file__).parents[2]
SCRIPT = {"titre": "Le petit essai", "scenes": [{"id": "s1", "plans": [{"id": "p1", "texte": "Un renard dort."}, {"id": "p2", "texte": "La lune monte."}]},
                                                {"id": "s2", "plans": [{"id": "p1", "texte": "Le vent chante."}, {"id": "p2", "texte": "Bonne nuit."}]}]}
UN_PLAN = {"titre": "Un plan", "scenes": [{"id": "s1", "plans": [{"id": "p1", "texte": "Bonjour."}]}]}


def recette(**plus) -> dict:
    return {**recettes.lire("essai"), **plus}


def voix_seule(**plus) -> dict:
    return recette(**{"id": "voix", "etapes": [{"id": "voix", "brique": "voix", "par": "plan", "langue": True}], "reglages": {"langues": ["en"]}, **plus})


@pytest.fixture
def essais(monkeypatch):
    monkeypatch.setattr(execution, "PAUSE_S", 0)
    yield Session.objects.get(essais=True)
    Tache.objects.all().delete()
    Depense.objects.all().delete()
    taches.fichier("fabrication").unlink(missing_ok=True)
    for cle in ("outil.voix", "plafond_mois_eur"):
        Parametre.ecrire(cle, "")
    with routeur.session(Session.objects.get(essais=True)):
        Reglage.objects.all().delete()


@pytest.fixture
def fiches_en_plus(tmp_path, monkeypatch):
    """Un nouvel outil = une fiche de plus (dans une copie du dossier des fiches), sans une ligne de code."""
    d = tmp_path / "moteur"
    (d / "fiches").mkdir(parents=True)
    for f in (outils.ICI / "fiches").glob("*.json"):
        (d / "fiches" / f.name).write_bytes(f.read_bytes())

    def ajouter(id: str, **plus):
        fiche = {**json.loads((outils.ICI / "fiches" / "faux_voix.json").read_text(encoding="utf-8")), "id": id, "nom": id, **plus}
        (d / "fiches" / f"{id}.json").write_text(json.dumps(fiche), encoding="utf-8")
        outils.fiches.cache_clear()

    monkeypatch.setattr(outils, "ICI", d)
    outils.fiches.cache_clear()
    yield ajouter
    outils.fiches.cache_clear()


def fichiers(s: Session, video_id: str) -> Path:
    return settings.SESSIONS / s.dossier / "videos" / video_id


def morceaux(s: Session, video_id: str) -> list[Morceau]:
    with routeur.session(s):
        return list(Morceau.objects.filter(video_id=video_id).order_by("ordre"))


def test_recette_d_essai_de_bout_en_bout(essais):
    v = execution.preparer(essais, recette(), SCRIPT)
    assert len(morceaux(essais, v.id)) == 8 + 4 + 4 + 4 + 4 + 8 + 2 + 2 + 2  # voix et lèvres par plan et langue, musique par scène et langue…
    avant = execution.estimer(essais, v.id)
    t = file.mettre(essais, v.id, v.titre, "claude")
    assert file.executer(str(t.id)) == 0
    t.refresh_from_db()
    assert t.etat == "finie" and not t.alertes and taches.lire("fabrication")["etat"] == "faite"
    assert {m.etat for m in morceaux(essais, v.id)} == {"fini"} and execution.estimer(essais, v.id)["secondes"] == 0
    d = fichiers(essais, v.id)
    for langue in ("en", "fr"):
        rapport = json.loads((d / langue / "revue" / "video" / "rapport.json").read_text(encoding="utf-8"))
        assert rapport["duree_s"] == pytest.approx(4, abs=0.2) and rapport["defauts"] == []  # une seconde par plan
        assert (d / langue / "miniature" / "video" / "miniature.png").is_file()
        demande = json.loads((d / langue / "montage" / "video" / "demande.json").read_text(encoding="utf-8"))
        assert len(demande["entrees"]["animation"]) == 4 and all(f"{os.sep}{langue}{os.sep}" in f for f in demande["entrees"]["voix"])
    mots = json.loads((d / "fr" / "voix" / "s1" / "p2" / "resultat.json").read_text(encoding="utf-8"))["infos"]["mots"]
    assert [m["mot"] for m in mots] == ["La", "lune", "monte."]
    assert not list(d.rglob("*.tmp")) and Chrono.objects.filter(etape="montage", outil="faux_montage").count() >= 2
    assert avant["cout_eur"] == 0 and avant["secondes"] > 0


def test_tuee_en_plein_milieu_reprend_sans_rien_perdre(essais):
    v = execution.preparer(essais, recette(), SCRIPT)
    t = file.mettre(essais, v.id, v.titre, "claude")
    p = subprocess.Popen([sys.executable, "-m", "fabrique", "executer", "fabrication", str(t.id)], cwd=DEPOT, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        fin = time.monotonic() + 60
        while sum(m.etat == "fini" for m in morceaux(essais, v.id)) < 6 and time.monotonic() < fin and p.poll() is None:
            time.sleep(0.05)
        assert p.poll() is None, "l'exécuteur a fini avant d'être tué"
        assert taches.occupe("fabrication") == "fabrication" and carte.occupee() == "une fabrication est déjà en cours"
        programme.tuer(p.pid)
        p.wait(10)
    finally:
        p.kill()
    finis = {m.id: (fichiers(essais, v.id) / (m.langue or "commun") / m.etape / (m.unite or "video") / execution.RESULTAT) for m in morceaux(essais, v.id) if m.etat == "fini"}
    assert 6 <= len(finis) < 38 and not taches.occupe("fabrication")
    dates = {i: f.stat().st_mtime_ns for i, f in finis.items()}
    assert Tache.objects.get(id=t.id).etat == "en_cours" and file.ordre()[0].id == t.id  # le noyau la relancera
    assert file.executer(str(t.id)) == 0
    assert {m.etat for m in morceaux(essais, v.id)} == {"fini"} and not list(fichiers(essais, v.id).rglob("*.tmp"))
    assert {m.essais for m in morceaux(essais, v.id)} == {0}  # la coupure n'est pas un échec de l'outil
    assert {i: f.stat().st_mtime_ns for i, f in finis.items()} == dates  # rien de fini n'a été refait
    assert Tache.objects.get(id=t.id).etat == "finie"


def empreinte_du_code() -> str:
    h = hashlib.sha256()
    for f in sorted((DEPOT / "fabrique").rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts and "tests" not in f.parts and f.suffix in (".py", ".json", ".qml"):
            h.update(f.read_bytes())
    return h.hexdigest()


def test_aucun_outil_nomme_dans_le_code():
    """Le code ne connaît aucun outil : ni l'id d'une fiche, ni le module d'un adaptateur (hors l'adaptateur lui-même)."""
    noms = {f.id for f in outils.fiches().values()} | {f.module.rsplit(".", 1)[1] for f in outils.fiches().values()}
    for py in (DEPOT / "fabrique").rglob("*.py"):
        if "tests" not in py.parts and py.stem not in noms:
            texte = py.read_text(encoding="utf-8")
            assert not [n for n in noms if f'"{n}"' in texte or f"'{n}'" in texte or f"import {n}" in texte], py


def test_changer_l_outil_par_defaut_ne_change_aucun_code(essais, fiches_en_plus):
    code = empreinte_du_code()
    fiches_en_plus("voix_grave", faux=True, reglages={"hauteur_hz": 220})  # un nouvel outil : une fiche, rien d'autre

    def voix(rec, script=UN_PLAN):
        v = execution.preparer(essais, rec, script)
        execution.jouer(essais, v.id)
        m = morceaux(essais, v.id)[0]
        return m.outil, (fichiers(essais, v.id) / "en" / "voix" / "s1" / "p1" / "voix.wav").read_bytes()

    defaut, son = voix(voix_seule())
    Parametre.ecrire("outil.voix", "voix_grave")  # le défaut de la brique, réglé dans la base du noyau (écran Outils, verdict d'un banc)
    grave, son_grave = voix(voix_seule())
    assert (defaut, grave) == ("faux_voix", "voix_grave") and son != son_grave
    with routeur.session(essais):
        Reglage.objects.update_or_create(cle="outil.voix", defaults={"valeur": "faux_voix"})  # la session passe avant le noyau
    assert voix(voix_seule())[0] == "faux_voix"
    assert voix(voix_seule(outils={"voix": "voix_grave"}))[0] == "voix_grave"  # le format passe avant la session
    plan = {"titre": "Exception", "scenes": [{"id": "s1", "plans": [{"id": "p1", "texte": "x", "outils": {"voix": "faux_voix"}}]}]}
    assert voix(voix_seule(outils={"voix": "voix_grave"}), plan)[0] == "faux_voix"  # le plan passe avant tout
    fiches_en_plus("vraie_voix", faux=False, langues=["en"])
    Parametre.ecrire("outil.voix", "vraie_voix")
    with routeur.session(essais):
        Reglage.objects.filter(cle="outil.voix").delete()
    assert voix(voix_seule())[0] == "faux_voix"  # simulation : un vrai outil cède la place au faux de sa brique
    with pytest.raises(Refus, match="ne parle pas"):
        execution.preparer(essais, voix_seule(outils={"voix": "vraie_voix"}, reglages={"langues": ["fr"]}), UN_PLAN)
    assert empreinte_du_code() == code


def test_refus_quand_bramble_fabrique(essais, monkeypatch, tmp_path):
    monkeypatch.setattr(garde, "studios", lambda: {tmp_path})
    monkeypatch.setattr(carte, "gpu", lambda: None)
    lances = []
    v = execution.preparer(essais, voix_seule(), UN_PLAN)
    t = file.mettre(essais, v.id, v.titre, "claude")
    etat = tmp_path / "DONNEES" / "etat.json"
    etat.parent.mkdir()

    def bramble(heure: datetime, **e):
        etat.write_text(json.dumps({"heure": heure.isoformat(timespec="minutes"), "mode": "réel", **e}), encoding="utf-8")

    bramble(datetime.now(), tache={"nom": "EPISODE.bat", "episode": True}, episode={"code": "x"})
    raison = file.tour(lancer=lambda *a, **k: lances.append(a))
    assert raison.startswith("Bramble Studio fabrique") and not lances and Tache.objects.get(id=t.id).raison == raison
    bramble(datetime.now() - timedelta(hours=1), tache={"nom": "EPISODE.bat", "episode": True})  # état figé : Bramble Studio est arrêté
    assert carte.occupee() == ""
    etat.write_text('{"heure": "', encoding="utf-8")  # réécrit par Bramble Studio à cet instant
    assert carte.occupee() == "l'état de Bramble Studio est illisible pour l'instant"
    bramble(datetime.now(), tache={"nom": "AUTRE.bat", "episode": False}, episode=None)  # une tâche sans épisode : la carte dira si elle est lourde
    assert carte.occupee() == ""
    monkeypatch.setattr(carte, "gpu", lambda: (12.0, 9000.0, 16384.0))  # un modèle de langue chargé
    assert file.tour(lancer=lambda *a, **k: lances.append(a)) == "un autre programme occupe la carte" and not lances
    monkeypatch.setattr(carte, "gpu", lambda: (9.0, 2300.0, 16384.0))
    assert file.tour(lancer=lambda *a, **k: lances.append(a)) == "" and lances == [("executer", "fabrication", t.id)]
    t.refresh_from_db()
    assert t.etat == "en_cours" and t.raison == "" and taches.occupe("fabrication")  # lancée : le pid arrive avec l'exécuteur
    assert file.tour(lancer=lambda *a, **k: lances.append(a)) == "" and len(lances) == 1  # une seule à la fois


def test_ordre_de_la_file_pause_reprise_annulation(essais, monkeypatch):
    a, b = bases.creer("Réelle A"), bases.creer("Réelle B")
    Session.objects.filter(id=b.id).update(priorite=1)
    with pytest.raises(Refus, match="seul RT"):
        file.mettre(a, "v", "x", "claude")
    e1 = file.mettre(essais, "e1", "essai", "claude")
    a1, a2 = file.mettre(a, "a1", "A 1", "RT"), file.mettre(a, "a2", "A 2", "RT")
    b1 = file.mettre(b, "b1", "B 1", "RT")
    assert [t.id for t in file.ordre()] == [b1.id, a1.id, a2.id, e1.id]
    tues = []
    monkeypatch.setattr(programme, "tuer", tues.append)
    Tache.objects.filter(id=b1.id).update(etat="en_cours", executeur=12345)
    file.agir(b1.id, "pause", "RT")
    assert tues == [12345] and [t.id for t in file.ordre()] == [a1.id, a2.id, e1.id]
    Tache.objects.filter(id=a1.id).update(executeur=os.getpid())
    file.agir(a1.id, "pause", "RT")  # jamais le noyau lui-même (un pid réutilisé)
    file.agir(a1.id, "reprendre", "RT")
    assert tues == [12345]
    file.agir(b1.id, "reprendre", "RT")
    file.agir(a1.id, "annuler", "RT")
    assert [t.id for t in file.ordre()] == [b1.id, a2.id, e1.id]
    with pytest.raises(Refus, match="impossible"):
        file.agir(a1.id, "pause", "RT")
    n = Navigateur()
    jetons.tirer(settings.DONNEES)
    voir = lambda qui: {"HTTP_AUTHORIZATION": f"Bearer {jetons.lire(settings.DONNEES, qui)}"}  # noqa: E731
    assert [t["titre"] for t in n.get("/api/file", **voir("claude")).json()][:3] == ["B 1", "A 2", "essai"]
    assert n.post(f"/api/file/{a2.id}/pause", **voir("claude")).status_code == 403
    assert n.post(f"/api/file/{a2.id}/pause", **voir("fenetre")).json()["message"].endswith("mise en pause")


def test_trois_essais_puis_alerte(essais, monkeypatch):
    monkeypatch.setitem(outils.fiches()["faux_voix"].reglages, "en_panne", True)
    v = execution.preparer(essais, voix_seule(), UN_PLAN)
    t = file.mettre(essais, v.id, v.titre, "claude")
    assert file.executer(str(t.id)) == 1
    t.refresh_from_db()
    m = morceaux(essais, v.id)[0]
    assert t.etat == "erreur" and "a échoué 3 fois" in t.raison and "ne répond pas" in t.raison and t.alertes == [t.raison]
    assert (m.etat, m.essais) == ("erreur", 3)
    monkeypatch.delitem(outils.fiches()["faux_voix"].reglages, "en_panne")
    file.agir(t.id, "reprendre", "RT")
    assert file.executer(str(t.id)) == 0 and morceaux(essais, v.id)[0].etat == "fini"


def test_outil_payant_plafond_nouvelle_tentative_repli(essais, monkeypatch):
    payant = recette(outils={"images": "faux_images_en_ligne"}, reglages={"langues": ["en"]})
    v = execution.preparer(essais, payant, UN_PLAN)
    assert execution.estimer(essais, v.id)["cout_eur"] == 0  # plafond à 0 € : c'est l'outil local qui servira
    alertes = []
    execution.jouer(essais, v.id, alertes.append)  # plafond à 0 € : aucun outil payant ne sert
    assert {m.outil for m in morceaux(essais, v.id) if m.etape == "images"} == {"faux_images"} and not Depense.objects.exists()
    assert len(alertes) == 1 and "plafond du mois est de 0,00 €" in alertes[0] and "repli sur l'outil local Fausses images" in alertes[0]
    Parametre.ecrire("plafond_mois_eur", "1")
    with routeur.session(essais):
        Reglage.objects.update_or_create(cle="plafond_eur", defaults={"valeur": "1"})
    v = execution.preparer(essais, payant, UN_PLAN)
    assert execution.estimer(essais, v.id)["cout_eur"] == 0.04
    execution.jouer(essais, v.id, alertes.append)
    assert {m.outil for m in morceaux(essais, v.id) if m.etape == "images"} == {"faux_images_en_ligne"} and len(alertes) == 1
    assert Depense.objects.get().reel_eur == 0.04
    monkeypatch.setitem(outils.fiches()["faux_images_en_ligne"].reglages, "en_panne", True)
    v = execution.preparer(essais, payant, UN_PLAN)
    execution.jouer(essais, v.id, alertes.append)
    assert Depense.objects.count() == 3  # l'appel raté et sa seule nouvelle tentative, notés au prix estimé
    assert "a échoué 2 fois" in alertes[-1] and {m.outil for m in morceaux(essais, v.id) if m.etape == "images"} == {"faux_images"}
    Parametre.ecrire("plafond_mois_eur", "0.17")  # 0,12 € déjà engagés : un appel passe, sa nouvelle tentative dépasserait
    v = execution.preparer(essais, payant, UN_PLAN)
    execution.jouer(essais, v.id, alertes.append)
    assert Depense.objects.count() == 4 and "plafond du mois est de 0,17 € (0,16 € déjà dépensés)" in alertes[-1]


def test_recettes_et_scripts_controles():
    r = recettes.lire("essai")
    assert recettes.recette(r).reglages.plan_fixe_max_s is None
    for mauvaise, motif in ((recette(schema=2), "schéma 2 inconnu"), (recette(etapes=[{"id": "x", "brique": "danse", "par": "plan"}]), "brique inconnue"),
                            (recette(etapes=[{"id": "x", "brique": "voix", "par": "plan"}] * 2), "même id"),
                            (recette(outils={"voix": "inconnu"}), "n'existe pas"), (recette(outils={"absente": "faux_voix"}), "étapes absentes"),
                            (recette(couleur="rouge"), "couleur"), (recette(reglages={"langues": []}), "langues"),
                            (recette(reglages={"langues": ["en", "en"]}), "en double"), (recette(reglages={"langues": ["EN"]}), "langues"),
                            (recette(etapes=[{"id": "Voix", "brique": "voix", "par": "plan"}]), "etapes"),
                            (recette(etapes=[{"id": "con", "brique": "voix", "par": "plan"}]), "réservé")):
        with pytest.raises(Refus, match=motif):
            recettes.recette(mauvaise)
    with pytest.raises(Refus, match="même id"):
        recettes.script({"titre": "x", "scenes": [{"id": "s1", "plans": [{"id": "p1"}, {"id": "p1"}]}]})
    for mauvais in ("s 1", "S1", "nul"):  # Windows : ni espace, ni majuscule (« S1 » = « s1 »), ni nom réservé
        with pytest.raises(Refus, match="script"):
            recettes.script({"titre": "x", "scenes": [{"id": mauvais, "plans": [{"id": "p1"}]}]})
    assert {f.id for f in outils.fiches().values() if f.etat == "en_service"} >= {b["defaut"] for b in outils.BRIQUES.values()}
    assert all(outils.fiches()[b["simulation"]].faux or outils.fiches()[b["simulation"]].simulable for b in outils.BRIQUES.values())


def test_estimation_par_mediane(essais):
    v = execution.preparer(essais, voix_seule(reglages={"langues": ["en", "fr"]}), SCRIPT)
    Chrono.objects.filter(etape="voix").delete()
    for s in (1, 2, 100):
        Chrono.objects.create(recette="voix", etape="voix", outil="faux_voix", secondes=s)
    Chrono.objects.create(recette="autre", etape="voix", outil="faux_voix", secondes=1000)  # un autre format : d'autres durées
    assert execution.estimer(essais, v.id)["secondes"] == 8 * 2
    Chrono.objects.filter(etape="voix").delete()


def test_morceau_renomme_avant_la_coupure_pas_refait(essais):
    v = execution.preparer(essais, voix_seule(), UN_PLAN)
    execution.jouer(essais, v.id)
    m = morceaux(essais, v.id)[0]
    d = execution.dossier(essais, m)
    date = (d / execution.RESULTAT).stat().st_mtime_ns
    with routeur.session(essais):
        Morceau.objects.filter(id=m.id).update(etat="attente")  # renommé, mais la base pas encore à jour
    execution.jouer(essais, v.id)
    assert morceaux(essais, v.id)[0].etat == "fini" and (d / execution.RESULTAT).stat().st_mtime_ns == date
    (d / "voix.wav").unlink()  # un résultat sans son fichier (restauration, ménage) : refait
    with routeur.session(essais):
        Morceau.objects.filter(id=m.id).update(etat="attente")
    execution.jouer(essais, v.id)
    assert (d / "voix.wav").is_file() and (d / execution.RESULTAT).stat().st_mtime_ns != date


def test_un_outil_qui_ne_rend_rien_echoue(essais, monkeypatch):
    from fabrique.moteur import faux

    monkeypatch.setattr(faux, "fabriquer", lambda fiche, d, dossier: outils.Resultat(fichiers=["absent.wav"], infos={"mots": []}))
    v = execution.preparer(essais, voix_seule(), UN_PLAN)
    with pytest.raises(execution.Echec, match="absents ou vides"):
        execution.jouer(essais, v.id)


def test_plantage_en_boucle_arrete_apres_trois_relances(essais, monkeypatch):
    monkeypatch.setattr(carte, "occupee", lambda *a: "")
    v = execution.preparer(essais, voix_seule(), UN_PLAN)
    t = file.mettre(essais, v.id, v.titre, "claude")
    lances = []
    for _ in range(4):
        file.tour(lancer=lambda *a, **k: lances.append(a))
        taches.fichier("fabrication").unlink()  # l'exécuteur meurt sans finir un morceau
    t.refresh_from_db()
    assert len(lances) == 4 and (t.etat, t.relances) == ("en_cours", 3)
    file.tour(lancer=lambda *a, **k: lances.append(a))
    t.refresh_from_db()
    assert len(lances) == 4 and t.etat == "erreur" and "4 fois" in t.raison and t.alertes == [t.raison]


def test_pause_pendant_un_tour_rien_ne_part(essais, monkeypatch):
    v = execution.preparer(essais, voix_seule(), UN_PLAN)
    t = file.mettre(essais, v.id, v.titre, "claude")

    def rt_clique(*a):  # pendant que nvidia-smi répond
        file.agir(t.id, "pause", "RT")
        return ""

    monkeypatch.setattr(carte, "occupee", rt_clique)
    lances = []
    assert file.tour(lancer=lambda *a, **k: lances.append(a)) == "" and not lances and Tache.objects.get(id=t.id).etat == "pause"


def test_l_executeur_prend_sa_tache_et_verifie_la_carte(essais, fiches_en_plus, monkeypatch):
    fiches_en_plus("voix_lourde", faux=True, besoins={"carte_go": 6, "disque_go": 0})
    v = execution.preparer(essais, voix_seule(outils={"voix": "voix_lourde"}), UN_PLAN)
    t = file.mettre(essais, v.id, v.titre, "claude")
    monkeypatch.setattr(carte, "bramble", lambda maintenant: "Bramble Studio fabrique (X.bat)")
    assert file.executer(str(t.id)) == 3 and Tache.objects.get(id=t.id).raison.startswith("Bramble") and morceaux(essais, v.id)[0].etat == "attente"
    monkeypatch.setattr(carte, "bramble", lambda maintenant: "")
    monkeypatch.setattr(carte, "gpu", lambda: None)
    autre = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        Tache.objects.filter(id=t.id).update(executeur=autre.pid)  # un autre exécuteur, vivant, la tient
        assert file.executer(str(t.id)) == 3
    finally:
        autre.kill()
        autre.wait(10)
    assert file.executer(str(t.id)) == 0 and Tache.objects.get(id=t.id).executeur == os.getpid()


def test_commande_moteur(essais, tmp_path):
    script = tmp_path / "script.json"
    script.write_text(json.dumps(UN_PLAN), encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "fabrique", "moteur", "essai", str(script)], cwd=DEPOT, capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=120)
    assert r.returncode == 0 and "dans la file de la session Essais" in r.stdout, r.stdout + r.stderr
    t = Tache.objects.get()
    assert (t.acteur, t.etat, t.titre) == ("claude", "attente", "Un plan")
    with routeur.session(essais):
        assert {m.langue for m in Morceau.objects.filter(video_id=t.video_id)} == {"", "en", "fr"}
    (tmp_path / "script.de.json").write_text(json.dumps(UN_PLAN), encoding="utf-8")  # une traduction à côté : fabriquée aussi
    r = subprocess.run([sys.executable, "-m", "fabrique", "moteur", "essai", str(script)], cwd=DEPOT, capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=120)
    assert r.returncode == 1 and "« de » n'est pas une langue de la session Essais" in r.stdout  # refusée tout de suite
    with routeur.session(essais):
        Langue.objects.create(code="de", nom="Deutsch")
    r = subprocess.run([sys.executable, "-m", "fabrique", "moteur", "essai", str(script)], cwd=DEPOT, capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=120)
    t = Tache.objects.exclude(id=t.id).get()
    with routeur.session(essais):
        assert {m.langue for m in Morceau.objects.filter(video_id=t.video_id)} == {"", "en", "de"}  # comme « Fabriquer » : la langue du script et les traductions données
    assert list((settings.SESSIONS / essais.dossier / "videos" / t.video_id).glob("*.de.json"))
    r = subprocess.run([sys.executable, "-m", "fabrique", "moteur", "essai", str(tmp_path / "absent.json")], cwd=DEPOT, capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=120)
    assert r.returncode == 1 and "refusé" in r.stdout
