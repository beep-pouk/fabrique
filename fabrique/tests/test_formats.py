"""F2 et F3 (J7), en simulation : vidéos d'essai faites par les faux outils, puis une compilation (introduction et deux vidéos bout à bout,
chapitres, sous-titres décalés), un extrait vertical (1080 × 1920, sous-titres incrustés) et une courte verticale créée seule ; chacune passée
au contrôle technique sans défaut bloquant. Les outils de F2 et F3 sont réels (ffmpeg, sans carte) et servent tels quels en simulation."""
import json

import pytest

from fabrique.garde import Refus
from fabrique.moteur import execution, file, montages, recettes
from fabrique.tests.test_moteur import SCRIPT, essais, recette  # noqa: F401 — fixtures


def fabriquer(s, r: dict, script: dict) -> str:
    v = execution.preparer(s, r, script)
    t = file.mettre(s, v.id, v.titre, "claude")
    assert file.executer(str(t.id)) == 0, t
    return v.id


def rapport(s, video: str, langue: str = "en") -> dict:
    return json.loads((execution.settings.SESSIONS / s.dossier / "videos" / video / langue / "revue" / "video" / "rapport.json").read_text(encoding="utf-8"))


@pytest.fixture
def trois(essais):
    en = recette(reglages={**recettes.lire("essai")["reglages"], "langues": ["en"]})
    return [fabriquer(essais, en, {**SCRIPT, "titre": f"Vidéo {i}"}) for i in range(3)]


def test_compilation_bout_a_bout(essais, trois):
    intro, *videos = trois
    v = fabriquer(essais, recettes.lire("F2"), {"titre": "Trois histoires", "intro": intro, "videos": videos})
    finale = execution.finale(essais, v, "en")
    m = montages.mesure(finale)
    sources = [montages.mesure(execution.finale(essais, x, "en"))["duree_s"] for x in trois]
    assert m["duree_s"] == pytest.approx(sum(sources), abs=0.3) and (m["largeur"], m["hauteur"]) == (64, 36)
    r = json.loads((finale.parent / "resultat.json").read_text(encoding="utf-8"))
    assert [c["titre"] for c in r["infos"]["chapitres"]] == ["Introduction", "Vidéo 1", "Vidéo 2"] and r["infos"]["chapitres"][2]["debut"] == pytest.approx(sum(sources[:2]), abs=0.2)
    segs = montages.sous_titres(finale)
    debut2 = r["infos"]["chapitres"][1]["debut"]
    assert len(segs) >= 6 and min(x["start"] for x in segs if x["start"] >= debut2 - 0.01) == pytest.approx(debut2, abs=0.05)  # décalés : la partie 2 commence à sa place
    assert rapport(essais, v)["defauts"] == [] and (finale.parent.parent.parent / "miniature" / "video" / "miniature.jpg").is_file()


def test_extrait_vertical_sous_titres_incrustes(essais, trois):
    v = fabriquer(essais, recettes.lire("F3"), {"titre": "Un extrait", "source": trois[1], "debut_s": 1, "fin_s": 3})
    finale = execution.finale(essais, v, "en")
    m = montages.mesure(finale)
    r = json.loads((finale.parent / "resultat.json").read_text(encoding="utf-8"))
    assert (m["largeur"], m["hauteur"]) == (1080, 1920) and m["duree_s"] == pytest.approx(2, abs=0.2) and r["infos"]["incrustes"] >= 1
    assert rapport(essais, v)["defauts"] == [] and clair(finale, 0.3) > 1000  # du texte blanc dans l'image (la source est d'une couleur sombre unie)


def test_courte_verticale_creee_seule(essais):
    v = fabriquer(essais, recettes.lire("F3s"), VOIX_OFF)
    finale = execution.finale(essais, v, "en")
    m = montages.mesure(finale)
    assert (m["largeur"], m["hauteur"]) == (1080, 1920) and m["duree_s"] == pytest.approx(3 * 1.6, abs=0.2) and rapport(essais, v)["defauts"] == []
    assert clair(finale, 0.8) > 1000  # les sous-titres du montage par plan, incrustés


# ---- J8 : F4 voix off + images ----

VOIX_OFF = {"titre": "La forêt en hiver", "description": "Un documentaire factice.", "tags": ["forêt", "hiver"], "scenes": [
    {"id": "s1", "plans": [{"id": "p1", "texte": "La neige tombe.", "image": "a snowy forest", "mouvement": "avancee"},
                           {"id": "p2", "texte": "Les arbres dorment.", "image": "sleeping trees", "mouvement": "fixe"}]},
    {"id": "s2", "plans": [{"id": "p1", "texte": "Le printemps viendra.", "image": "a spring meadow", "mouvement": "gauche"}]}]}
VOIX_OFF_XX = {**VOIX_OFF, "titre": "Titre factice", "description": "Description factice.", "scenes": [
    {"id": "s1", "plans": [{**VOIX_OFF["scenes"][0]["plans"][0], "texte": "Phrase factice un."}, {**VOIX_OFF["scenes"][0]["plans"][1], "texte": "Phrase factice deux."}]},
    {"id": "s2", "plans": [{**VOIX_OFF["scenes"][1]["plans"][0], "texte": "Phrase factice trois."}]}]}


def f4(**reglages) -> dict:
    r = recettes.lire("F4")
    return {**r, "reglages": {**r["reglages"], "duree_s": [1, 60], **reglages}}  # les fausses voix durent 1 s


def morceau(s, video: str, etape: str, unite: str, langue: str = "") -> dict:
    d = execution.settings.SESSIONS / s.dossier / "videos" / video / (langue or "commun") / etape / unite
    return {f: json.loads((d / f"{f}.json").read_text(encoding="utf-8")) for f in ("demande", "resultat")}


def test_f4_voix_off_de_bout_en_bout_en_deux_langues(essais):
    v = execution.preparer(essais, f4(langues=["en", "xx"]), VOIX_OFF, traductions={"xx": VOIX_OFF_XX})
    t = file.mettre(essais, v.id, v.titre, "claude")
    assert file.executer(str(t.id)) == 0
    for langue, textes in (("en", ["La neige tombe.", "Les arbres dorment.", "Le printemps viendra."]), ("xx", ["Phrase factice un.", "Phrase factice deux.", "Phrase factice trois."])):
        finale = execution.finale(essais, v.id, langue)
        m = montages.mesure(finale)
        assert (m["largeur"], m["hauteur"], m["son"]) == (1920, 1080, True) and m["duree_s"] == pytest.approx(3 * 1.6, abs=0.1)  # chaque plan : sa voix + 0,6 s
        segs = montages.sous_titres(finale)
        assert [x["text"] for x in segs] == textes and [round(x["start"], 2) for x in segs] == [0, 1.6, 3.2]  # le texte dans la langue, au début de son plan
        assert rapport(essais, v.id, langue)["defauts"] == []
        assert morceau(essais, v.id, "voix", "s1/p2", langue)["demande"]["texte"] == textes[1]
    anim = morceau(essais, v.id, "animation", "s1/p2")
    assert anim["demande"]["consigne"] == {"image": "sleeping trees", "mouvement": "fixe"} and anim["resultat"]["infos"]["mouvement"] == "fixe"  # 1,6 s < 12 s
    clip = execution.settings.SESSIONS / essais.dossier / "videos" / v.id / "commun" / "animation" / "s1" / "p2" / "clip.mp4"
    assert montages.mesure(clip)["largeur"] == 1920 and montages.mesure(clip)["duree_s"] == pytest.approx(1.6, abs=0.05)  # la plus longue voix du plan + 0,6 s


def test_f4_controle_voix_peu_intelligible_et_plan_fixe_trop_long(essais, monkeypatch):
    from fabrique.moteur import faux

    vrai = faux.fabriquer

    def whisper(fiche, d, dossier):  # Whisper comprend mal la voix d'un plan ; une couleur par plan (des coupes, comme de vraies images : clartés éloignées)
        if d.brique == "images":
            fiche = fiche.model_copy(update={"reglages": {**fiche.reglages, "couleur": {"s1/p1": "5c8048", "s1/p2": "e0e0e0", "s2/p1": "404040"}[d.unite]}})
        r = vrai(fiche, d, dossier)
        if d.brique == "voix":
            r.infos["controle"] = {"score": 0.5 if "arbres" in d.texte else 0.99, "entendu": "les zarbres", "seuil": 0.93}
        return r

    monkeypatch.setattr(faux, "fabriquer", whisper)
    v = fabriquer(essais, f4(plan_fixe_max_s=1), VOIX_OFF)
    defauts = rapport(essais, v)["defauts"]
    voix = [x for x in defauts if x.get("code") == "voix"]
    assert len(voix) == 1 and "s1/p2" in voix[0]["texte"] and "zarbres" in voix[0]["texte"] and voix[0]["debut"] == pytest.approx(1.6)
    fixes = [x for x in defauts if x.get("code") == "plan_fixe"]  # une couleur unie ne bouge pas, même sous la caméra : mesuré par la revue de F1
    assert [x["debut"] for x in fixes] == pytest.approx([1.6], abs=0.05)  # le plan du milieu (les deux autres ont un fondu, qui bouge)
    assert all(x["gravite"] == "moyenne" for x in defauts)
    assert morceau(essais, v, "animation", "s1/p2")["resultat"]["infos"]["mouvement"] == "avancee"  # « fixe » au-delà de la limite : jamais tenu


def test_f4_refus_de_la_forme_et_des_traductions(essais):
    sans_image = {**VOIX_OFF, "scenes": [{"id": "s1", "plans": [{"id": "p1", "texte": "Bonjour."}]}]}
    with pytest.raises(Refus, match="image"):
        execution.preparer(essais, f4(), sans_image)
    mauvais = {**VOIX_OFF, "scenes": [{"id": "s1", "plans": [{"id": "p1", "texte": "Bonjour.", "image": "x", "mouvement": "tourbillon"}]}]}
    with pytest.raises(Refus, match="mouvement"):
        execution.preparer(essais, f4(), mauvais)
    with pytest.raises(Refus, match="mêmes scènes et plans"):
        execution.preparer(essais, f4(langues=["en", "xx"]), VOIX_OFF, traductions={"xx": {**VOIX_OFF_XX, "scenes": VOIX_OFF_XX["scenes"][:1]}})


def test_f4_par_defaut_les_outils_reels_par_plan(essais):
    from fabrique.noyau import etat

    r = recettes.recette(recettes.lire("F4"))
    assert r.script == "voix-off" and r.reglages.plan_fixe_max_s == 12 and r.reglages.duree_s == (180, 900)
    with execution.routeur.session(essais):
        en_simulation = {m.etape: m.outil for m in execution.decouper(r, recettes.script(VOIX_OFF, "voix-off"), {})}
    assert en_simulation == {"voix": "faux_voix", "images": "faux_images", "animation": "plan_camera", "musique": "faux_musique", "montage": "plan_montage",
                             "miniature": "miniature_image", "revue": "controle_technique"}
    import pytest as _p
    with _p.MonkeyPatch.context() as mp:
        mp.setattr(etat, "simulation", lambda: False)
        with execution.routeur.session(essais):
            en_vrai = {m.etape: m.outil for m in execution.decouper(r, recettes.script(VOIX_OFF, "voix-off"), {})}
    assert en_vrai == {**en_simulation, "voix": "plan_voix", "images": "plan_images", "musique": "plan_musique"}


def test_camera_ampleur_et_mouvements():
    from fabrique.moteur import plans

    assert plans.camera("fixe", 10)[0] == "1" and plans.camera("avancee", 15)[0] == "1+0.15*on/375" and plans.camera("recul", 100)[0] == "1+0.4-0.4*on/2500"
    assert plans.camera("droite", 2)[1] == "(iw-iw/zoom)*on/50" and plans.camera("gauche", 2)[0] == "1+0.08"


def clair(video, t: float) -> int:
    """Le nombre de pixels presque blancs de l'image à t secondes."""
    from PIL import Image

    from fabrique.moteur.faux import lancer, programme

    png = video.with_name("image.png")
    lancer(programme("ffmpeg"), "-v", "error", "-y", "-ss", f"{t}", "-i", video, "-frames:v", "1", png)
    with Image.open(png) as im:
        return sum(im.convert("L").histogram()[201:])


def test_refus_de_ce_qu_une_compilation_ou_un_extrait_ne_peut_pas_citer(essais, trois):
    with pytest.raises(Refus, match="citée deux fois"):
        execution.preparer(essais, recettes.lire("F2"), {"titre": "x", "intro": trois[0], "videos": [trois[1], trois[0]]})
    with pytest.raises(Refus, match="dure"):
        execution.preparer(essais, recettes.lire("F3"), {"titre": "x", "source": trois[0], "debut_s": 0, "fin_s": 60})
    extrait = fabriquer(essais, recettes.lire("F3"), {"titre": "Un extrait", "source": trois[0], "debut_s": 0, "fin_s": 2})
    with pytest.raises(Refus, match="une compilation ne prend que des vidéos longues"):
        execution.preparer(essais, recettes.lire("F2"), {"titre": "x", "intro": trois[0], "videos": [trois[1], extrait]})
    pas_finie = execution.preparer(essais, recette(reglages={**recettes.lire("essai")["reglages"], "langues": ["en"]}), SCRIPT)
    with pytest.raises(Refus, match="pas finie"):
        execution.finale(essais, pas_finie.id)


def test_refus_sans_video_finale_et_defaut_fort(essais, trois):
    voix = recette(id="voix", etapes=[{"id": "voix", "brique": "voix", "par": "plan", "langue": True}], reglages={"langues": ["en"]})
    sans_montage = fabriquer(essais, voix, SCRIPT)
    with pytest.raises(Refus, match="pas de vidéo finale"):
        execution.preparer(essais, recettes.lire("F2"), {"titre": "x", "intro": sans_montage, "videos": trois[:2]})
    with pytest.raises(Refus, match="pas de vidéo finale en fr"):
        execution.preparer(essais, {**recettes.lire("F3"), "reglages": {**recettes.lire("F3")["reglages"], "langues": ["fr"]}},
                           {"titre": "x", "source": trois[0], "debut_s": 0, "fin_s": 2})
    with pytest.raises(Refus, match="de 1 s à 3 min"):
        execution.preparer(essais, recettes.lire("F3"), {"titre": "x", "source": trois[0], "debut_s": 0, "fin_s": 400})
    trop_court = {**recettes.lire("F2"), "reglages": {**recettes.lire("F2")["reglages"], "duree_s": [600, 7200]}}
    v = fabriquer(essais, trop_court, {"titre": "Trop courte", "intro": trois[0], "videos": trois[1:]})
    assert [d["gravite"] for d in rapport(essais, v)["defauts"]] == ["forte"] and "hors des bornes" in rapport(essais, v)["defauts"][0]["texte"]


def test_format_propre_a_un_script(essais):
    from fabrique.noyau import routeur
    from fabrique.session import calendrier, reglages
    from fabrique.session.models import Reglage

    try:
        with pytest.raises(Refus, match="pas parmi ceux de la session"):
            calendrier.creer_script(essais, "Une compilation", None, 0, "claude", "F2")
        reglages.ecrire(essais, {"formats": ["essai", "F2"]}, "RT")
        code = calendrier.creer_script(essais, "Une compilation", None, 0, "claude", "F2")
        autre = calendrier.creer_script(essais, "Une histoire", None, 0, "claude")
        assert calendrier.format_du_script(essais, code) == "F2" and calendrier.format_du_script(essais, autre) == "essai"
    finally:
        with routeur.session(essais):
            Reglage.objects.filter(cle__in=("formats", "format")).delete()
