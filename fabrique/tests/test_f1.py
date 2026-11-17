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
    assert [e.id for e in r.etapes] == [*etape.ETAPES, "analyse", "langue"] and all(e.par == "video" for e in r.etapes)  # celles de Bramble Studio, puis son analyse
    assert r.etapes[-1].langue == "autres" and r.reglages.langues == ["en"]  # les versions de langue : celles choisies à « Fabriquer »
    assert all(not outils.fiches()[o].faux and outils.fiches()[o].module.startswith("fabrique.moteur.f1.") for o in r.outils.values())
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
    "__init__.py": (0, 2), "anim.py": (5, 6), "copies.py": (39, 5), "etape.py": (4, 4), "images.py": (2, 2), "outils.py": (11, 46), "langue.py": (9, 8),
    "production_copie/calques.py": (1, 1), "bramble.py": (0, 0), "montage.py": (0, 0), "musique.py": (0, 0), "voix.py": (0, 0),
    "production_copie/anime_calques.py": (0, 0), "production_copie/lipsync_batch.py": (0, 0), "production_copie/offload.py": (0, 0),
    "langue_texte.py": (0, 0), "tts_chatterbox_mtl.py": (0, 0), "tts_cosyvoice3.py": (0, 0), "tts_qwen.py": (0, 0), "tts_voxcpm_wsl.py": (0, 0),
    "vc_chatterbox.py": (0, 0), "whisper_langue_wsl.py": (0, 0),
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
    assert {p.relative_to(f1).as_posix() for p in f1.rglob("*.py")} == set(ECARTS) | {"adaptateur.py", "comfy.py", "refaire.py", "mouvement.py", "analyse_bramble.py"}


def test_le_moteur_f1_ne_lit_plus_rien_de_bramble():
    """Le moteur repris ne lit plus le projet de Bramble Studio : ni PROJET, ni ses données, ni Django ; ses outils partagés seulement."""
    for f in (Path(adaptateur.__file__).parent).rglob("*.py"):
        texte = f.read_text(encoding="utf-8")
        code = "\n".join(l for l in texte.splitlines() if not l.lstrip().startswith("#"))
        assert code.count('"PROJET"') == (f.name == "outils.py") and "DATA_DIR" not in code and "django" not in code, f  # outils.py : Lieux.config, qui le traduit en session
    assert garde.PROTEGES  # la garde reste celle de Fabrique : rien n'est écrit sous Bramble Studio


SCENES = {"thumbnail_scene": 4, "title": "Une histoire factice", "scenes": [
    {"id": 1, "narration": "a", "image": "a glade"}, {"id": 2, "narration": "b", "image": "same"}, {"id": 3, "narration": "c", "bramble": "accueil"},
    {"id": 4, "narration": "d", "image": "a pond"}]}
PIECES = ["images/plan_001.png", "calques/plan_001/fond.png", "clips/s001.mp4", "clips/s001_last.png", "clips/s002.mp4", "clips/s002_last.png", "montage/s001.mp4",
          "montage/s002.mp4", "montage/s003.mp4", "montage/s004.mp4", "bramble/s003.mp4", "images/plan_004.png", "final/Une histoire factice.mp4", "final/miniature.jpg",
          "final/Une histoire factice.qwen.json", "final/analyse_Une_histoire_factice/rapport.md"]


def atelier_plein(atelier: Path):
    for rel in PIECES:
        (atelier / rel).parent.mkdir(parents=True, exist_ok=True)
        (atelier / rel).write_bytes(b"x")


def test_refaire_un_plan_range_ses_pieces_a_cote(tmp_path):
    from fabrique.moteur.f1 import refaire

    atelier_plein(tmp_path)
    r = refaire.preparer(tmp_path, SCENES, [1])
    assert r["etapes"] == ["images", "anim", "bramble", "montage", "revue", "analyse"]  # la miniature n'est pas faite de ce plan
    assert sorted(r["ranges"]) == sorted(["final/Une histoire factice.mp4", "final/Une histoire factice.qwen.json", "final/analyse_Une_histoire_factice", "images/plan_001.png", "calques/plan_001", "clips/s001.mp4", "clips/s001_last.png",
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
                     "miniature": "fini", "revue": "attente", "analyse": "attente"}  # seuls les morceaux qui dépendent du plan repartent
    assert list((settings.SESSIONS / essais.dossier / "videos" / v.id / "_refaits").glob("*/images/resultat.json"))  # l'avant, à côté
    t = Tache.objects.get(video_id=v.id)
    assert t.acteur == "RT" and t.etat == "attente"
    d = Navigateur().get(f"/api/sessions/{essais.id}/videos/{v.id}", **entete("fenetre")).json()
    assert [p["n"] for p in d["plans"]] == [1, 3, 4] and d["plans"][0]["scenes"] == [1, 2] and d["plans"][1]["bramble"]
    assert {e["id"]: (e["finis"], e["total"]) for e in d["etapes"]}["images"] == (0, 1) and d["recette"] == "F1 v1"
    r = Navigateur().post(chemin, {"plans": [1]}, content_type="application/json", **entete("fenetre"))
    assert r.status_code == 409 and "encore dans la file" in r.json()["detail"]
    Tache.objects.all().delete()
    execution.jouer(essais, v.id)
    with routeur.session(essais):
        assert {m.etat for m in Morceau.objects.filter(video=v)} == {"fini"}


def test_la_voix_de_reference_est_celle_de_la_session(tmp_path):
    from fabrique.moteur.f1.outils import Lieux

    lieux = Lieux(tmp_path / "STUDIO", tmp_path / "session")
    cfg = {"voix": {"ref_audio": str(tmp_path / "STUDIO" / "PROJET" / "voix" / "narrateur.wav"), "cfg": 0.5}, "style": "x"}
    assert lieux.config(cfg) == {"voix": {"ref_audio": str(tmp_path / "session" / "univers" / "voix" / "narrateur.wav"), "cfg": 0.5}, "style": "x"}
    assert lieux.config({"voix": {"ref_audio": "C:/ailleurs/voix.wav"}}) == {"voix": {"ref_audio": "C:/ailleurs/voix.wav"}}  # hors du projet : tel quel


def test_prise_f1_version_de_langue(essais, tmp_path, monkeypatch):
    from fabrique.moteur.f1 import langue
    from fabrique.session.models import Langue

    vus = {}

    def faire(lieux, script, cfg, langue_, ref, ecran, dossier, anglais_run):  # la version de langue de Bramble, simulée
        vus.update(script=Path(script).name, langue=langue_, anglais=anglais_run, atelier=dossier)
        (Path(dossier) / "final").mkdir(parents=True, exist_ok=True)
        (Path(dossier) / "final" / "Titre traduit.mp4").write_bytes(b"mp4")
        return 0

    monkeypatch.setattr(langue, "faire", faire)
    with routeur.session(essais):
        Langue.objects.update_or_create(code="xx", defaults={"nom": "Langue factice", "outil_voix": "outil_factice", "reglages_voix": {"cfg": 0.5}})
    session = settings.SESSIONS / essais.dossier
    (session / "reglages" / "config.json").write_text(json.dumps({"voix": {"ref_audio": "C:/voix.wav"}}), encoding="utf-8")
    video = tmp_path / "videos" / "v1"
    (video / "2026-01-01-s1e01.xx.json").parent.mkdir(parents=True)
    (video / "2026-01-01-s1e01.xx.json").write_text("{}", encoding="utf-8")
    d = outils.Demande(brique="montage", etape="langue", unite="", langue="xx", session=str(session), script=str(video / "2026-01-01-s1e01.json"),
                       atelier=str(video / "xx" / "atelier" / "2026-01-01-s1e01"))
    (tmp_path / "m").mkdir()
    r = adaptateur.fabriquer(outils.fiche("f1_langue", "montage"), d, tmp_path / "m")
    assert r.fichiers == ["final/Titre traduit.mp4"] and vus["script"] == "2026-01-01-s1e01.xx.json"
    assert vus["langue"] == {"code": "xx", "outil": "outil_factice", "reglages": {"cfg": 0.5}, "police": ""}
    assert vus["anglais"] == video / "commun" / "atelier" / "2026-01-01-s1e01"  # l'atelier de la langue du script
    (video / "2026-01-01-s1e01.xx.json").unlink()
    (tmp_path / "m2").mkdir()
    with pytest.raises(RuntimeError, match="traduction"):
        adaptateur.fabriquer(outils.fiche("f1_langue", "montage"), d, tmp_path / "m2")


def test_prise_f1_copie_les_textes_et_accepte_une_etape_sans_objet(essais, tmp_path, monkeypatch):
    def jouer(lieux, script, nom, cfg, dossier, ecran, fond):
        if nom == "voix":
            (Path(dossier) / "voix").mkdir(parents=True, exist_ok=True)
            (Path(dossier) / "voix" / "s001.wav").write_bytes(b"RIFF")
            (Path(dossier) / "voix" / "_controle.json").write_text("{}", encoding="utf-8")
        return 0  # lèvres : aucune scène où le narrateur parle, rien à faire

    monkeypatch.setattr(etape, "jouer", jouer)
    atelier = tmp_path / "atelier" / "2026-01-01-s1e01"
    d = outils.Demande(brique="voix", etape="voix", unite="", session=str(settings.SESSIONS / essais.dossier), script=str(tmp_path / "s.json"), atelier=str(atelier))
    (tmp_path / "m").mkdir()
    r = adaptateur.fabriquer(outils.fiche("f1_voix", "voix"), d, tmp_path / "m")
    assert r.fichiers == ["voix/s001.wav", "voix/_controle.json"] and r.infos["mots"] is None  # pas mesuré : jamais une liste vide trompeuse
    assert (tmp_path / "m" / "voix" / "s001.wav").stat().st_ino == (atelier / "voix" / "s001.wav").stat().st_ino  # le média : lié
    (atelier / "voix" / "_controle.json").write_text('{"refait": 1}', encoding="utf-8")  # le moteur réécrit ses textes sur place
    assert (tmp_path / "m" / "voix" / "_controle.json").read_text(encoding="utf-8") == "{}"  # le morceau garde le sien (copie)
    (tmp_path / "l").mkdir()
    r = adaptateur.fabriquer(outils.fiche("f1_levres", "levres"), d.model_copy(update={"brique": "levres"}), tmp_path / "l")
    assert r.fichiers == [] and r.infos["rien_a_faire"]
    outils.controler_resultat("levres", r, tmp_path / "l")  # accepté : sans objet
    with pytest.raises(RuntimeError, match="aucun fichier"):
        outils.controler_resultat("images", outils.Resultat(fichiers=[]), tmp_path / "l")


def test_refaire_rate_ne_bouge_rien(essais, monkeypatch):
    from fabrique.moteur.f1 import refaire

    v = execution.preparer(essais, recettes.lire("F1"), SCENES, nom="2026-01-01-s1e01")
    execution.jouer(essais, v.id)
    monkeypatch.setattr(refaire, "preparer", lambda *a, **k: (_ for _ in ()).throw(OSError("fichier ouvert")))  # l'atelier refuse de bouger
    with pytest.raises(Refus, match="rien n'a bougé"):
        execution.refaire(essais, v.id, [1], "RT")
    with routeur.session(essais):
        assert {m.etat for m in Morceau.objects.filter(video=v)} == {"fini"}
        assert all(execution.resultat(essais, m) for m in Morceau.objects.filter(video=v))  # chaque morceau à sa place


def test_estimation_f1_suit_la_longueur_du_script():
    d = outils.Demande(brique="images", etape="images", unite="", reglages={"scenes": 10})
    assert adaptateur.estimer(outils.fiche("f1_images", "images"), d).secondes == 770
    assert adaptateur.estimer(outils.fiche("f1_images", "images"), d.model_copy(update={"reglages": {"scenes": 74}})).secondes == 74 * 77
    assert adaptateur.estimer(outils.fiche("f1_miniature", "miniature"), d).secondes == 10  # une durée fixe


def test_revue_v2_trouve_les_plans_quasi_fixes_trop_longs(tmp_path):
    import subprocess

    from fabrique.moteur import faux
    from fabrique.moteur.f1 import mouvement

    ffmpeg = faux.programme("ffmpeg")
    video = tmp_path / "v.mp4"  # 15 s d'une image fixe, puis 6 s d'une image qui bouge
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x5c8048:s=160x90:d=15:r=12", "-f", "lavfi",
                    "-i", "testsrc=s=160x90:d=6:r=12", "-filter_complex", "[0][1]concat=n=2:v=1", "-pix_fmt", "yuv420p", str(video)], check=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    p = mouvement.plans(ffmpeg, video, 21.0)
    assert len(p) == 2 and p[0]["mouvement"] < mouvement.SEUIL < p[1]["mouvement"] and abs(p[0]["fin"] - 15) < 0.2
    d = mouvement.defauts(ffmpeg, video, 21.0, 12)
    assert len(d) == 1 and d[0]["debut"] == 0 and "15 s à l'écran" in d[0]["texte"]
    assert mouvement.defauts(ffmpeg, video, 21.0, 20) == []  # sous la limite : rien


def test_prise_f1_revue_v2_rend_les_defauts(essais, tmp_path, monkeypatch):
    import subprocess

    from fabrique.moteur import faux

    atelier = tmp_path / "atelier" / "2026-01-01-s1e01"
    (atelier / "final").mkdir(parents=True)
    subprocess.run([faux.programme("ffmpeg"), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x5c8048:s=160x90:d=15:r=12", "-pix_fmt", "yuv420p",
                    str(atelier / "final" / "Titre.mp4")], check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    (atelier / "final" / "youtube.txt").write_text("TITRE", encoding="utf-8")
    monkeypatch.setattr(etape, "jouer", lambda *a, **k: 0)
    d = outils.Demande(brique="controle", etape="revue", unite="", session=str(settings.SESSIONS / essais.dossier), script=str(tmp_path / "s.json"),
                       atelier=str(atelier), reglages={"plan_fixe_max_s": 12})
    (tmp_path / "m").mkdir()
    r = adaptateur.fabriquer(outils.fiche("f1_revue", "controle"), d, tmp_path / "m")
    assert len(r.infos["defauts"]) == 1 and "plan quasi fixe trop long" in r.infos["defauts"][0]["texte"]
    assert json.loads((tmp_path / "m" / "rapport.json").read_text(encoding="utf-8"))["analyse"] == "mouvement"
    (tmp_path / "m1").mkdir()
    r = adaptateur.fabriquer(outils.fiche("f1_revue", "controle"), d.model_copy(update={"reglages": {"plan_fixe_max_s": None}}), tmp_path / "m1")
    assert r.infos["defauts"] is None  # F1 v1 : pas mesuré


RAPPORT_MD = """# Analyse de Titre.mp4

- Durée : 1 min 05.0 s ; 160×90 ; 12.00 i/s ; son : oui

## Alertes
- volume global -20.1 LUFS (cible -14)
- image figée 4.0 s à 12.5 s

## Fichiers à regarder
- planche_01.jpg
"""


def test_prise_f1_analyse_rend_note_et_defauts_minutes(essais, tmp_path, monkeypatch):
    """L'analyse de Bramble (scripts d'OUTILS/analyse, joués dans l'atelier) : sautés quand leur sortie existe (reprise), lus comme Bramble les lit."""
    from fabrique.moteur.f1 import analyse_bramble as analyse
    from fabrique.moteur.f1.outils import Outils

    final = tmp_path / "atelier" / "2026-01-01-s1e01" / "final"
    (final / "analyse_Titre").mkdir(parents=True)
    (final / "Titre.mp4").write_bytes(b"mp4")
    (final / "analyse_Titre" / "rapport.md").write_text(RAPPORT_MD, encoding="utf-8")
    (final / "analyse_Titre" / "planche_01.jpg").write_bytes(b"jpg")
    (final / "Titre.qwen.json").write_text(json.dumps({"0000.0": {"score": 8, "defects": [], "debut": 0, "duree": 20},
                                                         "0020.0": {"score": 3.5, "defects": [{"t": 4, "what": "une patte glisse"}], "debut": 20, "duree": 20},
                                                         "0040.0": {"score": 5.5, "defects": [], "debut": 40, "duree": 25}}), encoding="utf-8")
    joues = []
    monkeypatch.setattr(Outils, "run", lambda self, cmd, **kw: joues.append(cmd) or "")
    d = outils.Demande(brique="controle", etape="analyse", unite="", session=str(settings.SESSIONS / essais.dossier), script=str(tmp_path / "s.json"),
                       atelier=str(final.parent))
    (tmp_path / "m").mkdir()
    with pytest.raises(RuntimeError, match=r"Titre\.qwen\.md n'a pas été écrit \(ANALYSER_QWEN\.bat\)"):
        analyse.fabriquer(outils.fiche("f1_analyse", "controle"), d, tmp_path / "m")  # le .bat rend 0 sans rien écrire : la sortie fait foi
    assert len(joues) == 1 and joues[0][:3] == ["cmd", "/c", "ANALYSER_QWEN.bat"]  # analyser_video.py sauté : son rapport existe
    (final / "Titre.qwen.md").write_text("fini", encoding="utf-8")
    (final / "Titre.transcription.json").write_text("{}", encoding="utf-8")
    r = analyse.fabriquer(outils.fiche("f1_analyse", "controle"), d, tmp_path / "m")
    outils.controler_resultat("controle", r, tmp_path / "m")
    assert r.infos["note"] == 5.7 and r.duree_s == 65.0
    assert [(x["debut"], x["source"], x["gravite"]) for x in r.infos["defauts"]] == [(12.5, "analyser_video", "moyenne"), (20, "Qwen", "forte"),
                                                                                   (40, "Qwen", "moyenne"), (None, "analyser_video", "legere")]
    assert "une patte glisse" in r.infos["defauts"][1]["texte"] and r.fichiers == ["rapport.json", "analyse/rapport.md", "analyse/planche_01.jpg"]
    lu = json.loads((tmp_path / "m" / "rapport.json").read_text(encoding="utf-8"))
    assert lu["note"] == 5.7 and lu["analyse"] == "complete" and lu["video"].endswith("Titre.mp4")
    cmd = analyse.commandes(analyse.Lieux(tmp_path, tmp_path), final / "Titre.mp4", tmp_path / "s.json")[0][1]
    assert cmd[:2] == ["wsl", "-d"] and "--scenario" in cmd[-4] and cmd[-3].endswith("analyser_video.py")  # chemins en arguments, jamais dans le texte de bash
