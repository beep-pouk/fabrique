"""Outils et bancs (J6), en simulation : installer, mettre à jour (à côté), retirer (corbeille), remettre ; banc à l'aveugle sur une vidéo de la
session « Essais » (file, juge, votes, verdict, adoption) : l'outil local en place remplacé par un autre, rien d'autre n'a bougé ; banc payant
sous plafond et refusé au-delà ; coupure en plein banc reprise sans rien refaire."""
import json

import pytest
from fabrique import programme
from fabrique.garde import Refus
from fabrique.moteur import bancs, execution, file, installation, outils
from fabrique.noyau import routeur, taches
from fabrique.noyau.models import Banc, Depense, Journal, Outil, Parametre, Tache
from fabrique.session.models import Morceau, Reglage
from django.conf import settings

from fabrique.tests.test_moteur import SCRIPT, essais, fiches_en_plus, voix_seule  # noqa: F401 — fixtures

CANDIDAT = "faux_voix_douce"


@pytest.fixture
def propre():
    yield
    import shutil

    shutil.rmtree(installation.racine(), ignore_errors=True)
    Outil.objects.all().delete()
    Banc.objects.all().delete()
    taches.fichier("installation").unlink(missing_ok=True)
    Parametre.ecrire("plafond_mois_eur", "")


def video_finie(s, recette=None) -> str:
    v = execution.preparer(s, recette or voix_seule(), SCRIPT)
    t = file.mettre(s, v.id, v.titre, "claude")
    assert file.executer(str(t.id)) == 0
    return v.id


def jouer_le_banc(b: Banc):
    t = Tache.objects.get(banc=b.id)
    assert file.executer(str(t.id)) == 0, Tache.objects.get(id=t.id).raison
    b.refresh_from_db()
    return b


def tables(s) -> dict:
    """Le contenu de toutes les tables (noyau et session), sauf le journal et l'état des outils."""
    from django.apps import apps

    contenu = {}
    for modele in apps.get_models():
        if modele.__name__ in ("Journal", "Outil", "Banc", "Tache"):
            continue
        base = "default" if modele._meta.app_label == "noyau" else routeur.ouvrir(s)
        contenu[modele.__name__] = sorted(json.dumps(x, sort_keys=True, default=str) for x in modele.objects.using(base).values())
    return contenu


def test_installer_mettre_a_jour_retirer_remettre(propre, fiches_en_plus, monkeypatch):
    f = outils.fiches()[CANDIDAT]
    assert installation.constat(f)["action"] == "installer" and outils.etat(f) == "candidat"
    lances = []
    monkeypatch.setattr(programme, "lancer_detache", lambda *a, journal: lances.append(a))
    assert "lancée" in installation.lancer(CANDIDAT, "RT") and lances == [("executer", "installation", CANDIDAT)]
    with pytest.raises(Refus, match="installation est en cours"):
        installation.lancer(CANDIDAT, "RT")  # lancée il y a moins d'une minute, pas encore de pid : comptée en cours
    taches.fichier("installation").unlink()
    assert installation.executer(CANDIDAT) == 0 and taches.lire("installation")["etat"] == "faite"
    assert (installation.dossier(f) / "poids" / "modele.json").is_file() and installation.constat(f)["etat"] == "installe"
    with pytest.raises(Refus, match="déjà installé"):
        installation.lancer(CANDIDAT, "RT")
    # une nouvelle version de la fiche (livrée avec une version du programme) : installée à côté, l'ancienne reste
    fiches_en_plus(CANDIDAT, **{**f.model_dump(exclude={"id"}), "version": "3"})
    g = outils.fiches()[CANDIDAT]
    assert installation.constat(g)["action"] == "mettre_a_jour" and installation.version_installee(g) == "2"
    assert installation.installer(CANDIDAT) == "" and installation.version_installee(g) == "3"
    assert (installation.racine() / CANDIDAT / "2" / "pret.txt").is_file() and (installation.racine() / CANDIDAT / "3" / "pret.txt").is_file()
    # retirer : état « retiré », fichiers rangés dans la corbeille, jamais effacés
    assert "retiré" in installation.retirer(CANDIDAT, "RT") and outils.etat(g) == "retire"
    assert not (installation.racine() / CANDIDAT).exists() and list((installation.racine() / "_corbeille").glob(f"{CANDIDAT}_*/3/pret.txt"))
    with pytest.raises(Refus, match="n'est pas en service"):
        outils.fiche(CANDIDAT, "voix")
    assert "candidat" in installation.remettre(CANDIDAT, "RT") and outils.etat(g) == "candidat"


def test_retirer_refuse_un_defaut_et_le_dernier_de_sa_brique(propre):
    with pytest.raises(Refus, match="défaut livré"):
        installation.retirer("faux_voix", "RT")
    du_format = next(iter(json.loads((outils.ICI / "recettes" / "F1.json").read_text(encoding="utf-8"))["outils"].values()))
    with pytest.raises(Refus, match="défaut du format F1"):
        installation.retirer(du_format, "RT")


def test_une_recette_qui_echoue_le_dit_et_garde_l_ancienne_version(propre, fiches_en_plus, tmp_path):
    source = tmp_path / "poids.bin"
    source.write_bytes(b"poids")
    pas = [{"telecharger": source.as_uri(), "vers": "poids.bin", "sha256": "0" * 64}]
    fiches_en_plus("outil_casse", etat="candidat", installation={"pas": pas, "temoins": ["poids.bin"]})
    assert "empreinte différente" in installation.installer("outil_casse") and installation.version_installee(outils.fiches()["outil_casse"]) == ""
    import hashlib

    fiches_en_plus("outil_casse", etat="candidat", installation={"pas": [{**pas[0], "sha256": hashlib.sha256(b"poids").hexdigest()}], "temoins": ["poids.bin"]})
    assert installation.installer("outil_casse") == "" and installation.constat(outils.fiches()["outil_casse"])["etat"] == "installe"


def test_banc_a_l_aveugle_puis_adoption_rien_d_autre_ne_bouge(essais, propre):
    video = video_finie(essais)
    with pytest.raises(Refus, match="n'est pas installé"):
        bancs.creer(essais, video, "voix", CANDIDAT, "simule", "claude")
    assert installation.installer(CANDIDAT) == ""
    with pytest.raises(Refus, match="déjà l'outil en place"):
        bancs.creer(essais, video, "voix", "faux_voix", "", "claude")
    with pytest.raises(Refus, match="ne note pas"):
        bancs.creer(essais, video, "voix", CANDIDAT, "whisper", "claude")  # en simulation : le juge simulé seulement
    b = bancs.creer(essais, video, "voix", CANDIDAT, "simule", "claude")
    assert (b.outil_a, b.outil_b, len(b.entrees)) == ("faux_voix", CANDIDAT, 4) and {e["gauche"] for e in b.entrees} <= {"a", "b"}
    assert file.lister()[0]["banc"] == b.id and file.lister()[0]["progression"] == "0/8"
    b = jouer_le_banc(b)
    assert b.etat == "a_voter" and len(b.notes) == 4 and bancs.faites(b) == 8
    assert all(execution.lu(bancs.sortie(b, i, c)).fichiers == ["voix.wav"] for i in range(4) for c in "ab")
    with pytest.raises(Refus, match="seul RT vote"):
        bancs.voter(b.id, 0, "gauche", "claude")
    for i, e in enumerate(b.entrees):  # RT préfère la nouvelle voix trois fois, une égalité (après s'être trompé une fois : il corrige)
        bancs.voter(b.id, i, "droite" if e["gauche"] == "b" else "gauche", "RT") if i == 0 else None
        assert "enregistré" in bancs.voter(b.id, i, "egal" if i == 3 else "gauche" if e["gauche"] == "b" else "droite", "RT")
    with pytest.raises(Refus, match="seul RT"):
        bancs.rendre(b.id, "claude")
    b.refresh_from_db()
    assert b.etat == "a_voter"  # le verdict attend « Rendre le verdict »
    bancs.rendre(b.id, "RT")
    b.refresh_from_db()
    assert b.etat == "fini" and b.verdict["gagnant"] == CANDIDAT and b.verdict["rt"] == {"b": 3, "egal": 1}
    assert json.loads((bancs.dossier(b) / "verdict.json").read_text(encoding="utf-8"))["verdict"]["gagnant"] == CANDIDAT
    assert "Fausse voix douce" in bancs.dernier(CANDIDAT)
    avant = tables(essais)
    with pytest.raises(Refus, match="seul RT"):
        bancs.adopter(b.id, "brique", "claude")
    assert "reste disponible" in bancs.adopter(b.id, "brique", "RT")
    apres = tables(essais)
    changees = {k for k in avant if avant[k] != apres[k]}
    assert changees == {"Parametre"} and set(apres["Parametre"]) - set(avant["Parametre"]) == {json.dumps({"cle": "outil.voix", "valeur": CANDIDAT}, sort_keys=True)}
    assert outils.etat(outils.fiches()[CANDIDAT]) == "en_service" and outils.etat(outils.fiches()["faux_voix"]) == "en_service"
    assert Journal.objects.filter(action="banc", acteur="RT", detail__quoi="adopté").exists()
    with pytest.raises(Refus, match="déjà adopté"):
        bancs.adopter(b.id, "session", "RT")
    # la vidéo suivante prend le nouvel outil ; les autres briques gardent le leur
    v = execution.preparer(essais, voix_seule(), SCRIPT)
    with routeur.session(essais):
        assert set(Morceau.objects.filter(video=v).values_list("outil", flat=True)) == {CANDIDAT}
    Parametre.ecrire("outil.voix", "")


def test_banc_gagne_par_l_outil_en_place_ou_sans_vainqueur_rien_a_adopter(essais, propre):
    video = video_finie(essais)
    installation.installer(CANDIDAT)
    b = jouer_le_banc(bancs.creer(essais, video, "voix", CANDIDAT, "", "claude"))
    assert b.notes == {}  # sans juge
    with pytest.raises(Refus, match="voter chaque entrée"):
        bancs.rendre(b.id, "RT")
    for i in range(len(b.entrees)):
        bancs.voter(b.id, i, "egal", "RT")
    bancs.rendre(b.id, "RT")
    b.refresh_from_db()
    assert b.verdict["gagnant"] == "" and "pas de vainqueur" in b.verdict["texte"]
    with pytest.raises(Refus, match="pas de vainqueur"):
        bancs.adopter(b.id, "session", "RT")


def test_juge_victoire_sans_ecart_non_comptee():
    b = Banc(outil_a="faux_voix", outil_b=CANDIDAT, juge="simule", votes={"0": "a", "1": "b", "2": "b"},
             notes={"0": {"a": 5.0, "b": 5.4}, "1": {"a": 4.0, "b": 6.0}, "2": {"a": 7.0, "b": 6.0}})
    v = bancs.verdict(b)
    assert v["juge"] == {"egal": 1, "b": 1, "a": 1} and v["juge_pour"] == "" and v["gagnant"] == CANDIDAT


def test_banc_payant_sous_plafond_puis_refuse_au_dela(essais, propre, fiches_en_plus):
    fiches_en_plus("faux_voix_en_ligne", local=False, prix_unite_eur=0.05, etat="candidat")
    video = video_finie(essais)
    with pytest.raises(Refus, match="plafond du mois est de 0,00 €"):
        bancs.creer(essais, video, "voix", "faux_voix_en_ligne", "", "claude")
    Parametre.ecrire("plafond_mois_eur", "1")
    with routeur.session(essais):
        Reglage.objects.update_or_create(cle="plafond_eur", defaults={"valeur": "1"})
    b = jouer_le_banc(bancs.creer(essais, video, "voix", "faux_voix_en_ligne", "", "claude"))
    depenses = Depense.objects.filter(outil="faux_voix_en_ligne")
    assert b.etat == "a_voter" and depenses.count() == 4 and all(d.reel_eur == d.estime_eur for d in depenses)
    assert sum(d.estime_eur for d in depenses) <= 1
    Parametre.ecrire("plafond_mois_eur", "0.3")  # déjà 4 appels de 0,05 € : un banc de plus dépasserait
    with pytest.raises(Refus, match="banc refusé"):
        bancs.creer(essais, video, "voix", "faux_voix_en_ligne", "", "claude")


def test_banc_coupe_reprend_sans_rien_refaire(essais, propre, monkeypatch):
    video = video_finie(essais)
    installation.installer(CANDIDAT)
    b = bancs.creer(essais, video, "voix", CANDIDAT, "simule", "claude")
    vraie = execution.produire
    faits = []

    def coupee(f, d, final):
        if len(faits) == 5:
            raise KeyboardInterrupt  # le PC s'éteint en plein banc
        faits.append(final)
        return vraie(f, d, final)

    monkeypatch.setattr(execution, "produire", coupee)
    with pytest.raises(KeyboardInterrupt):
        bancs.jouer(b.id)
    dates = {p: (p / execution.RESULTAT).stat().st_mtime_ns for p in faits}
    monkeypatch.setattr(execution, "produire", vraie)
    b = jouer_le_banc(b)
    assert b.etat == "a_voter" and bancs.faites(b) == 8 and {p: (p / execution.RESULTAT).stat().st_mtime_ns for p in faits} == dates


def test_banc_annule_avec_sa_tache(essais, propre):
    video = video_finie(essais)
    installation.installer(CANDIDAT)
    b = bancs.creer(essais, video, "voix", CANDIDAT, "", "claude")
    file.agir(Tache.objects.get(banc=b.id).id, "annuler", "RT")
    b.refresh_from_db()
    assert b.etat == "annule"


def test_api_des_outils_et_des_bancs(essais, propre, tmp_path):
    from django.test import Client as Navigateur

    from fabrique.noyau import jetons
    from fabrique.noyau.models import Candidat
    from django.conf import settings

    jetons.tirer(settings.DONNEES)
    n = Navigateur()
    h = lambda appelant: {"HTTP_AUTHORIZATION": f"Bearer {jetons.lire(settings.DONNEES, appelant)}"}  # noqa: E731
    post = lambda chemin, corps, qui="fenetre": n.post(chemin, corps, content_type="application/json", **h(qui))  # noqa: E731
    voix = next(b for b in n.get("/api/outils", **h("fenetre")).json()["briques"] if b["id"] == "voix")
    candidat = next(o for o in voix["outils"] if o["id"] == CANDIDAT)
    assert voix["defaut"] == "faux_voix" and voix["juges"] == [{"id": "simule", "titre": bancs.JUGES["simule"]["titre"]}]
    assert (candidat["etat"], candidat["action"], candidat["prix"]) == ("candidat", "installer", "gratuit")
    for chemin in (f"/api/outils/{CANDIDAT}/installer", "/api/depenses/plafond", "/api/bancs/1/voter", "/api/bancs/1/adopter"):
        assert post(chemin, {"valeur": 1, "entree": 0, "choix": "egal", "ou": "brique"}, "claude").status_code == 403, chemin
    assert post("/api/depenses/plafond", {"valeur": 2.5}).json()["message"].startswith("Plafond des outils payants : 2,50 €")
    assert n.get("/api/depenses", **h("fenetre")).json()["plafond_mois_eur"] == 2.5
    installation.installer(CANDIDAT)
    video = video_finie(essais)
    r = post("/api/bancs", {"session": essais.id, "video": video, "brique": "voix", "outil": CANDIDAT, "juge": "simule"})
    assert r.status_code == 200, r.json()
    b = jouer_le_banc(Banc.objects.get())
    d = n.get(f"/api/bancs/{b.id}", **h("fenetre")).json()
    assert d["etat"] == "a_voter" and all(l["qui"] is None and l["notes"] is None and l["gauche"] and l["droite"] for l in d["lignes"])  # à l'aveugle
    for l in d["lignes"]:
        post(f"/api/bancs/{b.id}/voter", {"entree": l["n"], "choix": "droite"})
    assert post(f"/api/bancs/{b.id}/verdict", {}, "claude").status_code == 403
    assert post(f"/api/bancs/{b.id}/verdict", {}).status_code == 200
    d = n.get(f"/api/bancs/{b.id}", **h("fenetre")).json()
    assert d["etat"] == "fini" and all(l["vote"] == "droite" and l["qui"] and l["notes"] for l in d["lignes"]) and d["verdict"]
    # veille : Claude verse les candidats du mois (« commande veille »), RT les classe
    (f := tmp_path / "veille.json").write_text(json.dumps({"candidats": [{"brique": "voix", "nom": "Voix candidate", "licence": "MIT", "commercial": True}]}), encoding="utf-8")
    from fabrique.moteur import veille

    assert veille.due()
    assert post("/api/veille", json.loads(f.read_text(encoding="utf-8")), "claude").status_code == 200 and not veille.due()
    assert post("/api/veille", {"candidats": [{"brique": "inconnue", "nom": "x"}]}, "claude").status_code == 409
    c = n.get("/api/veille", **h("fenetre")).json()
    assert [x["nom"] for x in c] == ["Voix candidate"] and c[0]["statut_nom"] == "nouveau"
    assert post(f"/api/veille/{c[0]['id']}/statut", {"valeur": "ecarte"}).status_code == 200 and Candidat.objects.get().statut == "ecarte"
    Candidat.objects.all().delete()
    Parametre.ecrire("veille_derniere", "")


@pytest.fixture
def faux_service(libre_port):
    """Un faux ElevenLabs local : retient chaque requête, répond 0,5 s de son et le minutage de chaque caractère, ou un refus."""
    import base64
    import http.server
    import threading

    recues, reponse = [], {"code": 200}

    class Service(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            recues.append({"chemin": self.path, "cle": self.headers.get("xi-api-key"), **corps})
            if reponse["code"] != 200:
                self.send_response(reponse["code"])
                self.end_headers()
                self.wfile.write(b'{"detail": {"status": "invalid_api_key", "message": "cle refusee"}}')
                return
            texte = corps["text"]
            t = [i * 0.05 for i in range(len(texte))]
            donnees = {"audio_base64": base64.b64encode(b"\x00\x01" * 12000).decode(),
                       "alignment": {"characters": list(texte), "character_start_times_seconds": t, "character_end_times_seconds": [x + 0.05 for x in t]}}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("x-character-count", str(len(texte)))
            self.end_headers()
            self.wfile.write(json.dumps(donnees).encode())

        def log_message(self, *a):
            pass

    serveur = http.server.HTTPServer(("127.0.0.1", libre_port), Service)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{libre_port}/v1/text-to-speech/{{voix}}/with-timestamps", recues, reponse
    serveur.shutdown()


def test_voix_en_ligne_reelle_contre_un_faux_service(faux_service, fiches_en_plus, tmp_path):
    from fabrique.noyau import cles

    adresse, recues, reponse = faux_service
    vraie = json.loads((outils.ICI / "fiches" / "elevenlabs_voix.json").read_text(encoding="utf-8"))
    fiches_en_plus("elevenlabs_voix", **{**{k: v for k, v in vraie.items() if k != "id"}, "reglages": {**vraie["reglages"], "adresse": adresse}})
    f = outils.fiches()["elevenlabs_voix"]
    d = outils.Demande(brique="voix", etape="voix", unite="s1/p1", langue="fr", texte="Un renard dort.", graine=7)
    Parametre.ecrire("cle_elevenlabs", "")
    with pytest.raises(RuntimeError, match="clé ElevenLabs absente"):
        outils.adaptateur(f).fabriquer(f, d, tmp_path)
    cles.enregistrer("elevenlabs", "cle-factice-123", "RT")
    try:
        assert outils.adaptateur(f).estimer(f, d).cout_eur == pytest.approx(0.09 * 15 / 1000, abs=1e-4)
        r = outils.adaptateur(f).fabriquer(f, d, tmp_path)
        outils.controler_resultat("voix", r, tmp_path)
        assert recues[0]["cle"] == "cle-factice-123" and recues[0]["text"] == "Un renard dort." and recues[0]["chemin"].startswith(f"/v1/text-to-speech/{vraie['reglages']['voix_id']}/")
        assert [m["mot"] for m in r.infos["mots"]] == ["Un", "renard", "dort."] and r.infos["mots"][1]["debut"] == pytest.approx(0.15)
        assert r.duree_s == pytest.approx(0.5) and r.infos["caracteres"] == 15 and r.infos["cout_eur"] == pytest.approx(0.09 * 15 / 1000, abs=1e-4)
        reponse["code"] = 401
        with pytest.raises(RuntimeError, match=r"ElevenLabs a refusé \(401\)") as e:
            outils.adaptateur(f).fabriquer(f, d, tmp_path)
        assert "cle-factice-123" not in str(e.value)
    finally:
        Parametre.ecrire("cle_elevenlabs", "")



def test_votes_simultanes_jamais_perdus(essais, propre):
    from concurrent.futures import ThreadPoolExecutor

    from django.db import connections

    installation.installer(CANDIDAT)
    b = jouer_le_banc(bancs.creer(essais, video_finie(essais), "voix", CANDIDAT, "", "claude"))

    def voter(i):
        try:
            return bancs.voter(b.id, i, "gauche", "RT")
        finally:
            connections.close_all()

    with ThreadPoolExecutor(4) as x:
        list(x.map(voter, range(4)))
    b.refresh_from_db()
    assert len(b.votes) == 4


def test_banc_refuse_une_etape_faite_video_entiere_et_ne_touche_pas_la_video(essais, propre):
    installation.installer(CANDIDAT)
    entiere = voix_seule(etapes=[{"id": "images", "brique": "images", "par": "plan"}, {"id": "voix", "brique": "voix", "par": "video", "langue": True}])  # après une autre étape
    with pytest.raises(Refus, match="vidéo entière"):
        bancs.creer(essais, video_finie(essais, entiere), "voix", CANDIDAT, "", "claude")
    video = video_finie(essais)
    avant = {p: p.stat().st_mtime_ns for p in (settings.SESSIONS / essais.dossier / "videos" / video).rglob("*")}
    b = jouer_le_banc(bancs.creer(essais, video, "voix", CANDIDAT, "", "claude"))
    assert {p: p.stat().st_mtime_ns for p in (settings.SESSIONS / essais.dossier / "videos" / video).rglob("*")} == avant
    assert {p.name for p in bancs.dossier(b).glob("*/*") if p.is_dir()} == {"gauche", "droite"}  # le chemin ne dit pas quel outil
    with pytest.raises(Refus, match="déjà en cours"):
        bancs.creer(essais, video, "voix", CANDIDAT, "", "claude")


def test_retirer_ou_mettre_a_jour_un_outil_attendu_refuse_puis_adoption_revérifiée(essais, propre, fiches_en_plus):
    installation.installer(CANDIDAT)
    b = jouer_le_banc(bancs.creer(essais, video_finie(essais), "voix", CANDIDAT, "", "claude"))
    with pytest.raises(Refus, match=f"le banc {b.id} attend encore"):
        installation.retirer(CANDIDAT, "RT")
    f = outils.fiches()[CANDIDAT]
    fiches_en_plus(CANDIDAT, **{**f.model_dump(exclude={"id"}), "version": "3"})
    assert f"le banc {b.id} attend encore" in installation.refus(outils.fiches()[CANDIDAT])
    for i, e in enumerate(b.entrees):
        bancs.voter(b.id, i, "gauche" if e["gauche"] == "b" else "droite", "RT")
    bancs.rendre(b.id, "RT")
    assert installation.installer(CANDIDAT) == ""  # verdict rendu : la version 3 s'installe
    with pytest.raises(Refus, match="changé de version"):
        bancs.adopter(b.id, "brique", "RT")  # la version 3 n'est jamais passée au banc
    installation.retirer(CANDIDAT, "RT")
    with pytest.raises(Refus, match="retiré"):
        bancs.adopter(b.id, "session", "RT")


def test_recette_d_installation_confinee(propre, fiches_en_plus):
    fiches_en_plus("outil_evade", etat="candidat", installation={"pas": [{"dossier": "../../evade"}], "temoins": ["x"]})
    assert "sort du dossier" in installation.installer("outil_evade") and not (installation.racine() / "evade").exists()
    with pytest.raises(Exception, match="version"):
        outils.Fiche.model_validate({**outils.fiches()["outil_evade"].model_dump(), "version": "../2"})


def test_un_faux_outil_adopte_en_simulation_ne_sert_pas_en_mode_reel(monkeypatch):
    from fabrique.noyau import etat

    Parametre.ecrire("outil.voix", CANDIDAT)
    try:
        assert outils.defauts("voix", {})[0] == CANDIDAT
        monkeypatch.setattr(etat, "simulation", lambda: False)
        assert outils.defauts("voix", {}) == ["faux_voix"]
    finally:
        Parametre.ecrire("outil.voix", "")


def test_veille_mensuelle_au_mois_du_calendrier():
    from datetime import date

    from fabrique.moteur import veille

    Parametre.ecrire("veille_derniere", "2027-01-31")
    try:
        assert not veille.due(date(2027, 1, 31)) and veille.due(date(2027, 2, 1))
    finally:
        Parametre.ecrire("veille_derniere", "")


def test_juge_en_echec_dit_et_banc_suit_sa_tache(essais, propre, monkeypatch):
    installation.installer(CANDIDAT)
    b = bancs.creer(essais, video_finie(essais), "voix", CANDIDAT, "simule", "claude")
    t = Tache.objects.get(banc=b.id)
    file.agir(t.id, "pause", "RT")
    b.refresh_from_db()
    assert (b.etat, b.raison) == ("attente", "tâche en pause dans la file")
    file.agir(t.id, "reprendre", "RT")

    def en_panne(juge, lot):
        raise RuntimeError("Whisper n'a pas répondu")

    monkeypatch.setattr(bancs, "notes_du_juge", en_panne)
    b = jouer_le_banc(b)
    assert b.etat == "a_voter" and "le juge n'a pas pu noter" in b.raison and b.notes == {}
    for i in range(len(b.entrees)):
        bancs.voter(b.id, i, "egal", "RT")
    bancs.rendre(b.id, "RT")
    b.refresh_from_db()
    assert "sans note du juge" in b.verdict["texte"] and "sans écart" not in b.verdict["texte"]
