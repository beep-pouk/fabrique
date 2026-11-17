"""F1 v1 (le moteur de Bramble Studio repris) : la recette, sa simulation de bout en bout (faux outils), la prise qui joue une étape de Bramble
sur l'atelier de la vidéo puis lie ses sorties dans le morceau (étape simulée ici : les vraies tournent de nuit, carte libre)."""
import json
from pathlib import Path

import pytest
from django.conf import settings

from fabrique import garde
from fabrique.garde import Refus
from fabrique.moteur import execution, outils, recettes
from fabrique.moteur.f1 import adaptateur, etape
from fabrique.noyau import routeur
from fabrique.noyau.models import Session
from fabrique.session.models import Morceau

SCENARIO = {"format": 2, "title": "Une histoire factice", "scenes": [{"id": 1, "narration": "Il était une fois.", "image": "a quiet glade"},
                                                                      {"id": 2, "narration": "Bonne nuit.", "bramble": "accueil"}]}


@pytest.fixture
def essais():
    s = Session.objects.get(essais=True)
    d = settings.SESSIONS / s.dossier
    (d / "reglages").mkdir(parents=True, exist_ok=True)
    (d / "reglages" / "config.json").write_text(json.dumps({"style": "factice"}), encoding="utf-8")
    poses = d / "univers" / "personnages" / "bramble" / "poses"
    poses.mkdir(parents=True, exist_ok=True)
    (poses / "accueil.png").write_bytes(b"\x89PNG pose")
    return s


def test_recette_f1():
    r = recettes.recette(recettes.lire("F1"))
    assert [e.id for e in r.etapes] == list(etape.ETAPES) and all(e.par == "video" for e in r.etapes)  # les étapes de Bramble Studio, dans son ordre
    assert all(not outils.fiches()[o].faux and outils.fiches()[o].module == "fabrique.moteur.f1.adaptateur" for o in r.outils.values())
    with pytest.raises(Refus, match="par vidéo entière"):
        recettes.recette({**recettes.lire("F1"), "etapes": [{"id": "voix", "brique": "voix", "par": "plan"}], "outils": {}})


def test_f1_en_simulation_de_bout_en_bout(essais):
    v = execution.preparer(essais, recettes.lire("F1"), SCENARIO, nom="2026-01-01-s1e01")
    with routeur.session(essais):
        assert {m.outil for m in Morceau.objects.filter(video=v)} == {b["simulation"] for b in outils.BRIQUES.values()}  # simulation : jamais un vrai outil
    execution.jouer(essais, v.id)
    with routeur.session(essais):
        assert {m.etat for m in Morceau.objects.filter(video=v)} == {"fini"}
    assert json.loads(execution.fichier_script(essais, v).read_text(encoding="utf-8")) == SCENARIO


def test_prise_f1_lie_les_sorties_de_l_etape(essais, tmp_path, monkeypatch):
    joues = []

    def jouer(lieux, script, nom, cfg, dossier, ecran, fond):  # l'étape de Bramble simulée : elle écrit dans l'atelier comme la vraie
        joues.append((nom, Path(script).name, lieux.session, Path(dossier).name, cfg))
        if nom == "voix":
            for i in (1, 2):
                (Path(dossier) / "voix").mkdir(exist_ok=True)
                (Path(dossier) / "voix" / f"s{i:03d}.wav").write_bytes(b"RIFF")
        elif nom == "revue":
            (Path(dossier) / "final").mkdir(exist_ok=True)
            (Path(dossier) / "final" / "youtube.txt").write_text("TITRE", encoding="utf-8")
        ecran("--- etape faite")
        return 0

    monkeypatch.setattr(etape, "jouer", jouer)
    session = settings.SESSIONS / essais.dossier
    d = outils.Demande(brique="voix", etape="voix", unite="", session=str(session), script=str(tmp_path / "2026-01-01-s1e01.json"),
                       atelier=str(tmp_path / "atelier" / "2026-01-01-s1e01"))
    for nom, brique, attendus in (("f1_voix", "voix", ["voix/s001.wav", "voix/s002.wav"]), ("f1_poses", "images", ["univers/personnages/bramble/poses/accueil.png"]),
                                  ("f1_revue", "controle", ["rapport.json", "final/youtube.txt"])):
        morceau = tmp_path / nom
        morceau.mkdir()
        f = outils.fiche(nom, brique)
        r = adaptateur.fabriquer(f, d.model_copy(update={"brique": brique}), morceau)
        outils.controler_resultat(brique, r, morceau)  # le contrat de la brique
        assert r.fichiers == attendus and all((morceau / x).is_file() for x in attendus)
    assert joues[0][:4] == ("voix", "2026-01-01-s1e01.json", session, "2026-01-01-s1e01") and joues[0][4] == {"style": "factice"}
    assert (tmp_path / "f1_voix" / "voix" / "s001.wav").stat().st_ino == (tmp_path / "atelier" / "2026-01-01-s1e01" / "voix" / "s001.wav").stat().st_ino  # lien dur
    monkeypatch.setattr(etape, "jouer", lambda *a, ecran, **k: (ecran("Ce rendu tourne deja : on ne le lance pas deux fois."), 0)[1])
    (tmp_path / "encore").mkdir()
    with pytest.raises(RuntimeError, match="tourne deja"):
        adaptateur.fabriquer(outils.fiche("f1_voix", "voix"), d, tmp_path / "encore")


BRAMBLE = Path(r"D:\StudioKids\OUTILS\app\studio\moteur")  # le code de Bramble Studio (lu seulement), sur le PC
ECARTS = {  # fichier → (lignes retirées, ajoutées) face à Bramble Studio, importations mises à part ; tout le reste est son code, à l'identique
    "__init__.py": (0, 2), "anim.py": (5, 6), "copies.py": (39, 5), "etape.py": (4, 4), "images.py": (2, 2), "outils.py": (11, 35),
    "production_copie/calques.py": (1, 1), "bramble.py": (0, 0), "montage.py": (0, 0), "musique.py": (0, 0), "voix.py": (0, 0),
    "production_copie/anime_calques.py": (0, 0), "production_copie/lipsync_batch.py": (0, 0), "production_copie/offload.py": (0, 0),
}


@pytest.mark.skipif(not BRAMBLE.is_dir(), reason="code de Bramble Studio absent de ce PC")
def test_f1_est_le_moteur_de_bramble_a_quelques_lignes_pres():
    """Preuve d'égalité, côté code : chaque écart avec le moteur de Bramble Studio est compté (seulement où il lit le projet : la session à la
    place) ; un écart de plus fait échouer ce test, à relire et à prouver."""
    import difflib

    f1 = Path(adaptateur.__file__).parent
    for rel, attendu in ECARTS.items():
        a = (BRAMBLE / rel).read_text(encoding="utf-8").splitlines()
        b = (f1 / rel).read_text(encoding="utf-8").replace("fabrique.moteur.f1", "moteur").splitlines()
        d = list(difflib.ndiff(a, b))
        assert (sum(l.startswith("- ") for l in d), sum(l.startswith("+ ") for l in d)) == attendu, rel
    assert {p.relative_to(f1).as_posix() for p in f1.rglob("*.py")} == set(ECARTS) | {"adaptateur.py", "comfy.py", "refaire.py"}


def test_le_moteur_f1_ne_lit_plus_rien_de_bramble():
    """Le moteur repris ne lit plus le projet de Bramble Studio : ni PROJET, ni ses données, ni Django ; ses outils partagés seulement."""
    for f in (Path(adaptateur.__file__).parent).rglob("*.py"):
        texte = f.read_text(encoding="utf-8")
        code = "\n".join(l for l in texte.splitlines() if not l.lstrip().startswith("#"))
        assert '"PROJET"' not in code and "DATA_DIR" not in code and "django" not in code, f
    assert garde.PROTEGES  # la garde reste celle de Fabrique : rien n'est écrit sous Bramble Studio


SCENES = {"thumbnail_scene": 4, "title": "Une histoire factice", "scenes": [
    {"id": 1, "narration": "a", "image": "a glade"}, {"id": 2, "narration": "b", "image": "same"}, {"id": 3, "narration": "c", "bramble": "accueil"},
    {"id": 4, "narration": "d", "image": "a pond"}]}
PIECES = ["images/plan_001.png", "calques/plan_001/fond.png", "clips/s001.mp4", "clips/s001_last.png", "clips/s002.mp4", "clips/s002_last.png", "montage/s001.mp4",
          "montage/s002.mp4", "montage/s003.mp4", "montage/s004.mp4", "bramble/s003.mp4", "images/plan_004.png", "final/Une histoire factice.mp4", "final/miniature.jpg"]


def atelier_plein(atelier: Path):
    for rel in PIECES:
        (atelier / rel).parent.mkdir(parents=True, exist_ok=True)
        (atelier / rel).write_bytes(b"x")


def test_refaire_un_plan_range_ses_pieces_a_cote(tmp_path):
    from fabrique.moteur.f1 import refaire

    atelier_plein(tmp_path)
    r = refaire.preparer(tmp_path, SCENES, [1])
    assert r["etapes"] == ["images", "anim", "bramble", "montage", "revue"]  # la miniature n'est pas faite de ce plan
    assert sorted(r["ranges"]) == sorted(["final/Une histoire factice.mp4", "images/plan_001.png", "calques/plan_001", "clips/s001.mp4", "clips/s001_last.png",
                                          "clips/s002.mp4", "clips/s002_last.png", "montage/s001.mp4", "montage/s002.mp4"])
    avant = tmp_path / "_refaits" / r["horodatage"]
    assert (avant / "images" / "plan_001.png").is_file() and not (tmp_path / "images" / "plan_001.png").exists()  # l'avant reste à côté
    assert (tmp_path / "images" / "plan_004.png").is_file() and (tmp_path / "montage" / "s003.mp4").is_file()  # le reste ne bouge pas
    assert json.loads((tmp_path / "images" / "_graines.json").read_text(encoding="utf-8")) == {"1": 1}
    r = refaire.preparer(tmp_path, SCENES, [4, 3])
    assert "miniature" in r["etapes"] and "final/miniature.jpg" in r["ranges"] and "bramble/s003.mp4" in r["ranges"]
    assert json.loads((tmp_path / "images" / "_graines.json").read_text(encoding="utf-8")) == {"1": 1, "4": 1}  # la scène de Bramble n'a pas d'image
    with pytest.raises(Refus, match="inconnu"):
        refaire.preparer(tmp_path, SCENES, [2])  # une scène « same » n'est pas un plan
    with pytest.raises(Refus, match="aucun plan"):
        refaire.preparer(tmp_path, SCENES, [])


def test_je_coche_fabrique_refait(essais):
    from django.test import Client as Navigateur

    from fabrique.noyau import jetons
    from fabrique.noyau.models import Tache

    v = execution.preparer(essais, recettes.lire("F1"), SCENES, nom="2026-01-01-s1e01")
    execution.jouer(essais, v.id)
    atelier = settings.SESSIONS / essais.dossier / "videos" / v.id / "commun" / "atelier" / "2026-01-01-s1e01"
    atelier_plein(atelier)
    jetons.tirer(settings.DONNEES)
    chemin = f"/api/sessions/{essais.id}/videos/{v.id}/refaire"
    entete = lambda qui: {"HTTP_AUTHORIZATION": f"Bearer {jetons.lire(settings.DONNEES, qui)}"}  # noqa: E731
    assert Navigateur().post(chemin, {"plans": [1]}, content_type="application/json", **entete("claude")).status_code == 403
    r = Navigateur().post(chemin, {"plans": [1]}, content_type="application/json", **entete("fenetre"))
    assert r.status_code == 200 and "plans [1] à refaire" in r.json()["message"], r.content
    with routeur.session(essais):
        etats = {m.etape: m.etat for m in Morceau.objects.filter(video=v)}
    assert etats == {"voix": "fini", "poses": "fini", "images": "attente", "anim": "attente", "musique": "fini", "bramble": "attente", "montage": "attente",
                     "miniature": "fini", "revue": "attente"}  # seuls les morceaux qui dépendent du plan repartent
    assert list((settings.SESSIONS / essais.dossier / "videos" / v.id / "_refaits").glob("*/images/resultat.json"))  # l'avant, à côté
    t = Tache.objects.get(video_id=v.id)
    assert t.acteur == "RT" and t.etat == "attente"
    r = Navigateur().post(chemin, {"plans": [1]}, content_type="application/json", **entete("fenetre"))
    assert r.status_code == 409 and "encore dans la file" in r.json()["detail"]
    Tache.objects.all().delete()
    execution.jouer(essais, v.id)
    with routeur.session(essais):
        assert {m.etat for m in Morceau.objects.filter(video=v)} == {"fini"}
