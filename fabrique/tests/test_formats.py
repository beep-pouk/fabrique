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
    srt = (finale.parent / "video.srt").read_text(encoding="utf-8")
    assert "Un renard dort." in srt and srt.count("-->") >= 3
    assert rapport(essais, v)["defauts"] == [] and (finale.parent.parent.parent / "miniature" / "video" / "miniature.jpg").is_file()


def test_extrait_vertical_sous_titres_incrustes(essais, trois):
    v = fabriquer(essais, recettes.lire("F3"), {"titre": "Un extrait", "source": trois[1], "debut_s": 1, "fin_s": 3})
    finale = execution.finale(essais, v, "en")
    m = montages.mesure(finale)
    r = json.loads((finale.parent / "resultat.json").read_text(encoding="utf-8"))
    assert (m["largeur"], m["hauteur"]) == (1080, 1920) and m["duree_s"] == pytest.approx(2, abs=0.2) and r["infos"]["incrustes"] >= 1
    assert rapport(essais, v)["defauts"] == []


def test_courte_verticale_creee_seule(essais):
    v = fabriquer(essais, recettes.lire("F3s"), SCRIPT)
    m = montages.mesure(execution.finale(essais, v, "en"))
    assert (m["largeur"], m["hauteur"]) == (1080, 1920) and m["duree_s"] == pytest.approx(4, abs=0.3) and rapport(essais, v)["defauts"] == []


def test_refus_sans_video_finale_et_controle_bloquant(essais, trois):
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
