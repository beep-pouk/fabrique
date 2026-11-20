"""F2 et F3 (J7), en simulation : vidéos d'essai faites par les faux outils, puis une compilation (introduction et deux vidéos bout à bout,
chapitres, sous-titres décalés), un extrait vertical (1080 × 1920, sous-titres incrustés) et une courte verticale créée seule ; chacune passée
au contrôle technique sans défaut bloquant. Les outils de F2 et F3 sont réels (ffmpeg, sans carte) et servent tels quels en simulation."""
import json
import time
from pathlib import Path

import pytest

from fabrique.garde import Refus
from fabrique.moteur import execution, file, montages, recettes
from fabrique.noyau.models import Chrono
from fabrique.tests.test_moteur import SCRIPT, essais, fiches_en_plus, recette  # noqa: F401 — fixtures


def fabriquer(s, r: dict, script: dict, acteur: str = "claude") -> str:
    v = execution.preparer(s, r, script)
    t = file.mettre(s, v.id, v.titre, acteur)
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
            r.infos["controle"] = {"score": {"arbres": 0.5, "neige": 0.85}.get(next((m for m in ("arbres", "neige") if m in d.texte), ""), 0.99),
                                   "entendu": "les zarbres", "seuil": 0.93}
        return r

    monkeypatch.setattr(faux, "fabriquer", whisper)
    v = fabriquer(essais, f4(plan_fixe_max_s=1), VOIX_OFF)
    defauts = rapport(essais, v)["defauts"]
    voix = [x for x in defauts if x.get("code") == "voix"]
    assert [(x["texte"].split(" : ")[0], x["gravite"]) for x in voix] == [("voix peu intelligible (s1/p1", "moyenne"), ("voix peu intelligible (s1/p2", "forte")]
    assert "zarbres" in voix[1]["texte"] and voix[1]["debut"] == pytest.approx(1.6)  # 0,5 : plus comprise (bloquant) ; 0,85 : un peu sous 0,93
    fixes = [x for x in defauts if x.get("code") == "plan_fixe"]  # une couleur unie ne bouge pas, même sous la caméra : mesuré par la revue de F1
    assert [x["debut"] for x in fixes] == pytest.approx([1.6], abs=0.05)  # le plan du milieu (les deux autres ont un fondu, qui bouge)
    assert all(x["gravite"] == "moyenne" for x in fixes)
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
    from fabrique.moteur import par_plan as plans

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


def test_publication_de_f2_f3_et_f4(request, monkeypatch):
    """« Approuver » une vidéo F4 (deux langues), une compilation et un extrait : le dossier final de chaque langue rempli comme celui de F1
    (vidéo finale, miniature, sous-titres, youtube.txt tiré du script : titre, description, chapitres de la compilation, tags)."""
    from fabrique.noyau import bases
    from fabrique.noyau.models import Tache
    from fabrique.publication import publication

    monkeypatch.setattr(execution, "PAUSE_S", 0)
    s = bases.creer(f"Session {request.node.name}")
    try:
        v = execution.preparer(s, f4(langues=["en", "xx"]), VOIX_OFF, traductions={"xx": VOIX_OFF_XX})
        t = file.mettre(s, v.id, v.titre, "RT")
        assert file.executer(str(t.id)) == 0
        with execution.routeur.session(s):
            from fabrique.session.models import Ressource

            Ressource.objects.create(type="voix", nom="Voix factice", licence="CC BY 4.0", credit="Voix factice (CC BY 4.0)")
        assert "brouillon(s) en, xx" in (r := publication.approuver(s, v.id, "RT")) and "CRÉDIT" not in r
        en, xx = publication.apercu(s, v.id)
        assert (en["titre"], en["description"], en["tags"]) == ("La forêt en hiver", "Un documentaire factice.\n\nVoix factice (CC BY 4.0)", ["forêt", "hiver"])
        assert (xx["titre"], xx["description"]) == ("Titre factice", "Description factice.\n\nVoix factice (CC BY 4.0)")
        for a in (en, xx):
            assert Path(a["video"]).is_file() and montages.mesure(Path(a["video"]))["largeur"] == 1920 and a["miniature"].endswith("miniature.jpg") and a["fautes"] == []
            assert not any("sans sous-titres" in x for x in a["avis"])
        assert "Phrase factice deux." in (Path(xx["video"]).parent / "sous_titres.srt").read_text(encoding="utf-8")
        assert "brouillons déjà prêts" in publication.approuver(s, v.id, "RT")  # rien de refait
        histoires = [fabriquer(s, recette(reglages={**recettes.lire("essai")["reglages"], "langues": ["en"]}), {**SCRIPT, "titre": f"Vidéo {i}"}, "RT") for i in range(3)]
        comp = fabriquer(s, recettes.lire("F2"), {"titre": "Trois histoires", "intro": histoires[0], "videos": histoires[1:], "tags": ["compilation"]}, "RT")
        publication.approuver(s, comp, "RT")
        (c,) = publication.apercu(s, comp)
        assert c["chapitres"] == ["00:00 Introduction", "00:04 Vidéo 1", "00:08 Vidéo 2"] and c["tags"] == ["compilation"] and c["titre"] == "Trois histoires"
        extrait = fabriquer(s, recettes.lire("F3"), {"titre": "Un extrait", "source": histoires[1], "debut_s": 1, "fin_s": 3}, "RT")
        publication.approuver(s, extrait, "RT")
        (e,) = publication.apercu(s, extrait)
        assert montages.mesure(Path(e["video"]))["hauteur"] == 1920 and e["miniature"].endswith("miniature.jpg") and e["description"] == "Voix factice (CC BY 4.0)"
    finally:
        Tache.objects.filter(session_id=s.id).delete()


def test_video_pilote_au_format_voix_off(request):
    from fabrique.noyau.models import Tache
    from fabrique.session import reglages

    s = reglages.creer(f"Session {request.node.name}", [{"code": "xx", "nom": "Langue factice"}])
    try:
        reglages.ecrire(s, {"formats": ["F4"], "difference": "un lieu différent chaque fois", "style": "aquarelle douce"}, "RT")
        reglages.finir(s, "RT")
        s.refresh_from_db()
        assert "dans la file" in reglages.pilote(s, "RT")
        with execution.routeur.session(s):
            v = execution.Video.objects.get(id=Tache.objects.get(session_id=s.id).video_id)
            assert v.recette["id"] == "F4" and all(p["image"] and p["mouvement"] for sc in v.script["scenes"] for p in sc["plans"])
            assert {m.outil for m in v.morceaux.all()} <= {f"faux_{b}" for b in ("voix", "images", "animation", "musique", "montage", "miniature", "controle")}
    finally:
        Tache.objects.filter(session_id=s.id).delete()


def test_f4_en_mode_reel_outils_de_la_carte_simules(essais, monkeypatch):
    """F4 en mode réel, de bout en bout, les modèles simulés au plus près (Chatterbox, Whisper, l'outil de voix de la langue, Qwen-Image,
    ComfyUI, ACE-Step) : chaque étape de la carte fait toute sa langue d'un coup (un lot, un démarrage de ComfyUI), chaque morceau lie le sien ;
    le score de Whisper va au contrôle ; une coupure reprend aux fichiers manquants."""
    from fabrique.moteur.f1 import adaptateur, comfy, images, langue, musique, voix
    from fabrique.moteur.faux import lancer, programme
    from fabrique.noyau import etat

    monkeypatch.setattr(etat, "simulation", lambda: False)
    reglages = execution.settings.SESSIONS / essais.dossier / "reglages"
    reglages.mkdir(exist_ok=True)
    (reglages / "config.json").write_text(json.dumps({"style": "style factice", "negatif_image": "x", "voix": {"ref_audio": "ref.wav", "ref_text": "x"},
                                                      "images": {"largeur": 64, "hauteur": 32, "pas": 1, "cfg": 1, "shift": 1}}), encoding="utf-8")
    appels = {"voix": [], "langue": [], "image": [], "start": 0, "stop": 0, "musique": []}

    def dire(o, dossier, scenes, cfg, *a, **k):
        for s in scenes:
            if not (w := Path(dossier) / "voix" / f"s{s['id']:03d}.wav").exists():
                lancer(programme("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=300:duration={1 + s['id'] / 10}", w)
        fait = {str(s["id"]): {"score": 0.5 if s["id"] == 2 else 0.99, "entendu": s["narration"]} for s in scenes}
        (Path(dossier) / "voix" / "_controle.json").write_text(json.dumps(fait), encoding="utf-8")  # comme f1 : le contrôle de Whisper, à côté des voix
        return fait

    monkeypatch.setattr(voix, "faire", lambda o, d, sc, cfg: appels["voix"].append(len(sc)) or dire(o, d, sc, cfg))
    monkeypatch.setattr(langue, "voix", lambda o, d, sc, l, ref, log=print: appels["langue"].append((l["code"], ref)) or dire(o, d, sc, None))
    monkeypatch.setattr(adaptateur, "langue_de", lambda session, code: {"code": code})

    def qwen(self, prompt, out, seed, w=None, h=None, **k):
        appels["image"].append((prompt, seed, w, h))
        lancer(programme("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", f"color=c=0x{seed % 1000 * 70:06x}:s={w}x{h}", "-frames:v", "1", out)

    monkeypatch.setattr(images.Images, "qwen_image", qwen)
    monkeypatch.setattr(comfy, "start", lambda *a, **k: appels.__setitem__("start", appels["start"] + 1))
    monkeypatch.setattr(comfy, "stop", lambda *a, **k: appels.__setitem__("stop", appels["stop"] + 1))

    def composer(o, dossier, data, total, cfg):
        appels["musique"].append(round(total, 2))
        lancer(programme("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=200:duration={total}", out := Path(dossier) / "musique.wav")
        return out

    monkeypatch.setattr(musique, "faire", composer)
    try:
        with pytest.raises(Refus, match="pas de traduction en « xx »"):
            execution.preparer(essais, f4(langues=["en", "xx"]), VOIX_OFF)
        chronos = Chrono.objects.filter(recette="F4", etape="voix").count()
        v = execution.preparer(essais, f4(langues=["en", "xx"]), VOIX_OFF, traductions={"xx": VOIX_OFF_XX})
        with execution.routeur.session(essais):
            assert {m.outil for m in v.morceaux.all()} >= {"plan_voix", "plan_images", "plan_musique", "plan_camera", "plan_montage"}
        execution.jouer(essais, v.id)
        assert appels["voix"] == [3] and appels["langue"] == [("xx", "ref.wav")]  # un lot par langue (Whisper compris), au premier morceau
        assert [x[1] for x in appels["image"]] == [1001, 1002, 1003] and appels["start"] == 1 and appels["stop"] == 2  # arrêté après les images et après la musique
        assert appels["image"][1][0] == "style factice, sleeping trees, filling the whole frame, wide 16:9 composition" and appels["image"][0][2:] == (64, 32)
        assert appels["musique"] == [pytest.approx(1.1 + 1.2 + 1.3 + 3 * 0.6, abs=0.05)]  # une musique commune, à la durée de la plus longue langue
        assert Chrono.objects.filter(recette="F4", etape="voix").count() - chronos == 2  # un chrono par lot (divisé par ses voix), aucun pour un morceau qui lie
        for langue_ in ("en", "xx"):
            m = montages.mesure(execution.finale(essais, v.id, langue_))
            assert m["duree_s"] == pytest.approx(1.7 + 1.8 + 1.9, abs=0.1) and m["son"]
            d = rapport(essais, v.id, langue_)["defauts"]
            assert [(x["code"], x["debut"]) for x in d] == [("voix", pytest.approx(1.7, abs=0.05))]  # le plan s1/p2, minuté
        assert morceau(essais, v.id, "voix", "s1/p2", "xx")["resultat"]["infos"]["controle"] == {"score": 0.5, "entendu": "Phrase factice deux.", "seuil": langue.SEUIL}
        # coupure : une image et son morceau perdus, refaits seuls
        base = execution.settings.SESSIONS / essais.dossier / "videos" / v.id / "commun"
        import shutil

        shutil.rmtree(base / "images" / "s2" / "p1")
        (base / "atelier" / "video" / "images" / "plan_003.png").unlink()
        with execution.routeur.session(essais):
            execution.Morceau.objects.filter(video_id=v.id, etape="images", unite="s2/p1").update(etat="attente")
        execution.jouer(essais, v.id)
        assert [x[1] for x in appels["image"]] == [1001, 1002, 1003, 1003] and appels["start"] == 2
    finally:
        (reglages / "config.json").unlink()
    with pytest.raises(Refus, match="n'a pas ce que demandent les outils de ce format"):  # une session sans les réglages des outils réels : refus d'emblée
        execution.preparer(essais, f4(), VOIX_OFF)


def test_lot_coupe_son_dernier_fichier_range_et_refait(tmp_path):
    from fabrique.moteur import par_plan

    d = tmp_path / "voix"
    with par_plan.lot(d, ["s*.wav"]):
        (d / "s001.wav").write_bytes(b"entier")
    assert not (d / "_lot_en_cours").exists()
    with pytest.raises(KeyboardInterrupt):  # coupé en plein lot : le marqueur reste
        with par_plan.lot(d, ["s*.wav"]):
            (d / "s002.wav").write_bytes(b"entier")
            (d / "s003.wav").write_bytes(b"a moi")
            raise KeyboardInterrupt
    import os

    os.utime(d / "s003.wav", (time.time() + 5, time.time() + 5))  # écrit en dernier
    with par_plan.lot(d, ["s*.wav"]):
        assert sorted(f.name for f in d.glob("s*.wav")) == ["s001.wav", "s002.wav"]  # le dernier écrit rangé, le reste gardé
    assert [f.name for f in (d / "_coupes").rglob("*.wav")] == ["s003.wav"]


def test_demande_d_ecriture_dit_les_champs_de_la_forme(essais):
    from fabrique.noyau import depot, routeur
    from fabrique.session import calendrier, reglages
    from fabrique.session.models import Reglage

    try:
        reglages.ecrire(essais, {"formats": ["F4"]}, "RT")
        code = calendrier.creer_script(essais, "Un documentaire", None, 0, "claude", "F4")
        depot.demander(essais, code, "ecrire", "", "RT")
        d = json.loads(next((execution.settings.RACINE / "depot" / "a_ecrire").glob(f"{code}*.json")).read_text(encoding="utf-8"))
        plan = d["schema"]["$defs"]["PlanVoixOff"]
        assert d["forme"] == "voix-off" and {"texte", "image"} <= set(plan["required"])
        assert plan["properties"]["mouvement"]["enum"] == ["fixe", "avancee", "recul", "gauche", "droite"]
    finally:
        with routeur.session(essais):
            Reglage.objects.filter(cle__in=("formats", "format")).delete()


# ---- J9 : F5 chanson, comptine ----

CHANSON = {"titre": "La comptine factice", "description": "Une comptine factice.", "tags": ["comptine"],
           "musique": {"tags": "children's song, ukulele", "bpm": 100, "tonalite": "B-flat major"}, "sections": [
               {"id": "s1", "type": "intro", "image": "a sunny meadow"},
               {"id": "s2", "type": "couplet", "paroles": ["Petit lapin dans le pré", "saute saute sans arrêt"], "image": "a rabbit jumping", "mouvement": "droite"},
               {"id": "s3", "type": "refrain", "paroles": ["Bonne nuit petit lapin"], "image": "a rabbit asleep", "mouvement": "fixe"}]}


def f5(**reglages) -> dict:
    r = recettes.lire("F5")
    return {**r, "reglages": {**r["reglages"], "duree_s": [1, 60], **reglages}}  # le faux chant dure 2 s par section


def test_f5_chanson_de_bout_en_bout_karaoke_incruste(essais):
    v = fabriquer(essais, f5(), CHANSON)
    finale = execution.finale(essais, v, "en")
    m = montages.mesure(finale)
    assert (m["largeur"], m["hauteur"], m["son"]) == (1920, 1080, True) and m["duree_s"] == pytest.approx(6, abs=0.1)  # la chanson entière
    r = json.loads((finale.parent / "resultat.json").read_text(encoding="utf-8"))
    assert [(p["unite"], p["debut"]) for p in r["infos"]["plans"]] == [("s1", 0), ("s2", 1.7), ("s3", 3.7)]  # une section commence juste avant son 1er mot
    ass = (finale.parent / "karaoke.ass").read_text(encoding="utf-8")
    assert r["infos"]["incrustes"] == 3 and "{\\k" in ass and "Bonne nuit petit lapin" not in ass and "{\\k" + "50}Bonne" in ass  # un mot surligné à son moment
    assert [x["text"] for x in montages.sous_titres(finale)] == ["Petit lapin dans le pré", "saute saute sans arrêt", "Bonne nuit petit lapin"]
    assert clair(finale, 2.2) > 1000 and rapport(essais, v)["defauts"] == []
    anim = morceau(essais, v, "animation", "s3")
    assert anim["demande"]["consigne"] == {"type": "refrain", "image": "a rabbit asleep", "mouvement": "fixe"} and anim["resultat"]["duree_s"] == pytest.approx(2.3, abs=0.05)


def test_f5_paroles_peu_comprises_et_refus(essais, monkeypatch):
    from fabrique.moteur import faux

    vrai = faux.fabriquer

    def mal_chante(fiche, d, dossier):
        r = vrai(fiche, d, dossier)
        if d.brique == "chant":
            r.infos["compris"] = 0.2
        return r

    monkeypatch.setattr(faux, "fabriquer", mal_chante)
    v = fabriquer(essais, f5(), CHANSON)
    assert [(x["code"], x["gravite"]) for x in rapport(essais, v)["defauts"]] == [("paroles", "forte")]
    with pytest.raises(Refus, match="une chanson a des paroles"):
        execution.preparer(essais, f5(), {**CHANSON, "sections": [CHANSON["sections"][0]]})
    with pytest.raises(Refus, match="sections ont le même id"):
        execution.preparer(essais, f5(), {**CHANSON, "sections": [CHANSON["sections"][1], CHANSON["sections"][1]]})
    for mauvais, motif in (({"paroles": ["un {\\b1} gras"]}, "paroles"), ({"paroles": ["[Chorus] caché"]}, "paroles"), ({"paroles": ["   "]}, "paroles")):
        with pytest.raises(Refus, match=motif):
            execution.preparer(essais, f5(), {**CHANSON, "sections": [{**CHANSON["sections"][1], **mauvais}]})
    with pytest.raises(Refus, match="tonalite"):
        execution.preparer(essais, f5(), {**CHANSON, "musique": {**CHANSON["musique"], "tonalite": "G-sharp mineur"}})
    with pytest.raises(Refus, match="paroles trop longues"):
        execution.preparer(essais, f5(), {**CHANSON, "sections": [{**CHANSON["sections"][1], "id": f"s{i}", "paroles": ["une ligne"] * 10} for i in range(8)]})
    with pytest.raises(Refus, match="change la musique"):
        execution.preparer(essais, f5(langues=["en", "xx"]), CHANSON, traductions={"xx": {**CHANSON, "musique": {**CHANSON["musique"], "bpm": 140}}})


def test_f5_en_mode_reel_ace_step_et_whisper_simules(essais, monkeypatch):
    """Le chant réel, ComfyUI et Whisper simulés au plus près : le flux de F1 reçoit les paroles balisées, le style et la langue ; ComfyUI est
    arrêté avant Whisper ; les mots entendus calent les paroles (un mot manqué placé entre ses voisins) ; les sections prennent leurs bornes."""
    from fabrique.moteur import par_section
    from fabrique.moteur.f1 import comfy
    from fabrique.moteur.faux import lancer, programme
    from fabrique.noyau import etat

    monkeypatch.setattr(etat, "simulation", lambda: False)
    reglages = execution.settings.SESSIONS / essais.dossier / "reglages"
    reglages.mkdir(exist_ok=True)
    (reglages / "config.json").write_text(json.dumps({"style": "style factice", "images": {"largeur": 64, "hauteur": 32, "pas": 1, "cfg": 1, "shift": 1}}), encoding="utf-8")
    vu = {"etats": []}

    def run(prompt, timeout=0):
        vu["consigne"] = prompt["4"]["inputs"]
        lancer(programme("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=12", out := Path(execution.settings.RACINE) / "ace.wav")
        return [str(out)]

    monkeypatch.setattr(comfy, "start", lambda *a, **k: vu["etats"].append("start"))
    monkeypatch.setattr(comfy, "stop", lambda *a, **k: vu["etats"].append("stop"))
    monkeypatch.setattr(comfy, "run", run)

    vrai_run = par_section.subprocess.run

    def whisper(cmd, **k):  # Whisper entend le couplet sauf « dans », et pas le refrain ; le reste (ffmpeg) passe
        if cmd[0] != "wsl":
            return vrai_run(cmd, **k)
        vu["etats"].append("whisper")
        sortie = cmd[-1].split()[-1].strip("'")
        fichier = Path(sortie[5].upper() + ":" + sortie[6:]) if sortie.startswith("/mnt/") else Path(sortie)
        mots = [("petit", 3.0), ("lapin", 3.5), ("le", 4.5), ("pré", 5.0), ("saute", 6.0), ("saute", 6.5), ("sans", 7.0), ("arrêt", 7.5)]
        fichier.write_text(json.dumps([{"mot": m, "debut": a, "fin": a + 0.4} for m, a in mots]), encoding="utf-8")

    monkeypatch.setattr(par_section.subprocess, "run", whisper)
    from fabrique.moteur.f1 import images

    monkeypatch.setattr(images.Images, "qwen_image", lambda self, prompt, out, seed, w=None, h=None, **k: lancer(
        programme("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x406080:s={w}x{h}", "-frames:v", "1", out))
    try:
        v = execution.preparer(essais, f5(), CHANSON).id
        execution.jouer(essais, v)  # sans la file : son verrou de carte lirait la vraie carte
        c = morceau(essais, v, "chant", "video", "en")["resultat"]["infos"]
        assert vu["consigne"]["lyrics"] == "[Intro]\n\n[Verse]\nPetit lapin dans le pré\nsaute saute sans arrêt\n\n[Chorus]\nBonne nuit petit lapin"
        assert (vu["consigne"]["tags"], vu["consigne"]["bpm"], vu["consigne"]["keyscale"], vu["consigne"]["language"]) == ("children's song, ukulele", 100, "Bb major", "en")
        assert vu["consigne"]["duration"] == pytest.approx(60.0) and c["essais"] == 1  # 3 lignes et une intro au tempo (24 s) : une minute au moins
        assert vu["etats"][:3] == ["start", "stop", "whisper"]  # la carte libérée avant Whisper
        assert c["compris"] == pytest.approx(8 / 13, abs=0.01) and [m["debut"] for m in c["mots"][:4]] == [3.0, 3.5, 3.9, 4.5]
        assert c["sections"] == [{"id": "s1", "debut": 0.0, "fin": 2.7}, {"id": "s2", "debut": 2.7, "fin": 7.6}, {"id": "s3", "debut": 7.6, "fin": 12.0}]
        assert montages.mesure(execution.finale(essais, v, "en"))["duree_s"] == pytest.approx(12, abs=0.1)
    finally:
        (reglages / "config.json").unlink()


def test_video_pilote_au_format_chanson(request):
    from fabrique.noyau.models import Tache
    from fabrique.session import reglages

    s = reglages.creer(f"Session {request.node.name}", [{"code": "xx", "nom": "Langue factice"}], promesse="une comptine calme")
    try:
        reglages.ecrire(s, {"formats": ["F5"], "difference": "un animal différent", "style": "aquarelle douce"}, "RT")
        reglages.finir(s, "RT")
        s.refresh_from_db()
        assert "dans la file" in reglages.pilote(s, "RT")
        with execution.routeur.session(s):
            v = execution.Video.objects.get(id=Tache.objects.get(session_id=s.id).video_id)
            assert v.recette["id"] == "F5" and recettes.script(v.script, "chanson").sections[1].paroles == ["une comptine calme"]
    finally:
        Tache.objects.filter(session_id=s.id).delete()


def test_banc_du_chant_premiere_etape_de_la_recette(essais, fiches_en_plus):
    v = fabriquer(essais, f5(), CHANSON)
    fiches_en_plus("faux_chant_doux", roles=["chant"], reglages={"hauteur_hz": 330})
    from fabrique.moteur import bancs

    b = bancs.creer(essais, v, "chant", "faux_chant_doux", "", "claude")
    assert (b.outil_a, b.outil_b, len(b.entrees)) == ("faux_chant", "faux_chant_doux", 1)  # une chanson, une entrée : RT écoute les deux
    with pytest.raises(Refus, match="vidéo entière"):  # le montage dépend des étapes d'avant : jamais au banc
        bancs.creer(essais, v, "montage", "faux_montage", "", "claude")


def test_f5_chant_refait_si_whisper_comprend_trop_peu_et_whisper_en_panne(essais, monkeypatch, tmp_path):
    """Une chanson dont Whisper retrouve trop peu de paroles est refaite avec une autre graine, la meilleure gardée ; Whisper en panne : pas
    de nouvel essai, et le contrôle le dit (pas « mal chantée »)."""
    from fabrique.moteur import par_section
    from fabrique.moteur.f1 import comfy
    from fabrique.moteur.faux import lancer, programme

    reglages = execution.settings.SESSIONS / essais.dossier / "reglages"
    reglages.mkdir(exist_ok=True)
    (reglages / "config.json").write_text(json.dumps({"style": "x"}), encoding="utf-8")
    graines, entendre = [], {"mots": []}

    def run(prompt, timeout=0):
        graines.append(prompt["4"]["inputs"]["seed"])
        lancer(programme("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=duration=8", out := tmp_path / f"ace{len(graines)}.wav")
        return [str(out)]

    monkeypatch.setattr(comfy, "start", lambda *a, **k: None)
    monkeypatch.setattr(comfy, "stop", lambda *a, **k: None)
    monkeypatch.setattr(comfy, "run", run)
    monkeypatch.setattr(par_section, "ecouter", lambda wav, langue: (entendre["mots"].pop(0), "") if entendre["mots"] else ([], "transformers : erreur factice"))
    d = execution.outils.Demande(brique="chant", etape="chant", unite="", langue="en", graine=7, session=str(execution.settings.SESSIONS / essais.dossier),
                                 script=str(tmp_path / "chanson.json"), reglages={})
    (tmp_path / "chanson.json").write_text(json.dumps(CHANSON), encoding="utf-8")
    fiche = execution.outils.fiches()["chant_acestep"]
    try:
        entendre["mots"] = [[{"mot": "petit", "debut": 1, "fin": 1.3}], [{"mot": m, "debut": i, "fin": i + 0.3} for i, m in enumerate("petit lapin dans le pré saute saute sans".split(), 1)]]
        (d1 := tmp_path / "un").mkdir()
        r = par_section.chant(fiche, d, d1)
        assert graines == [7, 1007] and r.infos["essais"] == 2 and r.infos["compris"] == pytest.approx(8 / 13, abs=0.01) and (d1 / "chanson.wav").is_file()
        assert sorted(f.name for f in d1.iterdir()) == ["chanson.wav"]  # l'essai écarté effacé
        (d2 := tmp_path / "deux").mkdir()
        r = par_section.chant(fiche, d, d2)
        assert len(graines) == 3 and r.infos["entendus"] == 0 and r.infos["whisper_erreur"] == "transformers : erreur factice"
        dc = d.model_copy(update={"brique": "controle", "entrees": {"chant": [str(d2 / "chanson.wav")]}, "sources": {"chant": "chant"}})
        (d2 / "resultat.json").write_text(r.model_dump_json(), encoding="utf-8")
        assert [x["texte"] for x in montages.paroles_peu_comprises(dc)] == ["Whisper n'a pas pu écouter la chanson (transformers : erreur factice) : karaoké réparti au jugé"]
    finally:
        (reglages / "config.json").unlink()


def test_calage_et_karaoke_auto_verification():
    """L'auto-vérification de paroles.py : calage (têtes et queues manquées collées aux mots retrouvés), bornes des sections muettes partagées,
    karaoké surligné à l'heure et sans chevauchement de lignes, écritures non latines, échappement des accolades."""
    import subprocess
    import sys

    r = subprocess.run([sys.executable, "-m", "fabrique.moteur.paroles"], capture_output=True, text=True, cwd=Path(__file__).parents[2])
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stderr


# ---- J10 : F6 présentateur virtuel ----

PRESENTATEUR = {"titre": "Les saisons factices", "description": "Une présentation factice.", "tags": ["saisons"], "presentateur": "pia factice",
                "decor": "a cosy reading corner", "scenes": [
                    {"id": "s1", "plans": [{"id": "p1", "texte": "Bonjour à tous."},
                                           {"id": "p2", "texte": "Voici la neige.", "vue": "insert", "image": "a snowy forest", "mouvement": "gauche"}]},
                    {"id": "s2", "plans": [{"id": "p1", "texte": "À bientôt.", "vue": "face"}]}]}


def f6(**reglages) -> dict:
    r = recettes.lire("F6")
    return {**r, "reglages": {**r["reglages"], "duree_s": [1, 60], **reglages}}  # les fausses voix durent 1 s


def personnage(s, nom: str) -> int:
    """Un personnage de l'univers, son image de référence importée et validée (comme RT dans Session → Univers) ; l'id de la référence."""
    from fabrique.session import univers
    from fabrique.session.models import Personnage
    from fabrique.tests.fixes import REFERENCE

    univers.ajouter(s, "personnage", nom, "un personnage factice", "RT")
    with execution.routeur.session(s):
        p = Personnage.objects.get(nom=nom)
    univers.importer_reference(s, p.id, REFERENCE, "RT")
    with execution.routeur.session(s):
        ref = p.references.get().id
    univers.valider(s, ref, True, "RT")
    return ref


@pytest.fixture
def presentatrice(essais):
    import shutil

    from fabrique.session import univers
    from fabrique.session.models import Personnage

    yield personnage(essais, "Pia Factice")
    with execution.routeur.session(essais):
        Personnage.objects.filter(nom__iexact="pia factice").delete()
    shutil.rmtree(univers.racine(essais) / "univers" / "personnages" / univers.slug("Pia Factice"), ignore_errors=True)


def test_f6_presentateur_de_bout_en_bout(essais, presentatrice):
    from fabrique.tests.fixes import REFERENCE

    v = fabriquer(essais, f6(), PRESENTATEUR)
    finale = execution.finale(essais, v, "en")
    m = montages.mesure(finale)
    assert (m["largeur"], m["hauteur"], m["son"]) == (1920, 1080, True) and m["duree_s"] == pytest.approx(3 * 1.6, abs=0.1)  # chaque plan : sa voix + 0,6 s
    assert [x["text"] for x in montages.sous_titres(finale)] == ["Bonjour à tous.", "Voici la neige.", "À bientôt."] and rapport(essais, v)["defauts"] == []
    assert (execution.settings.SESSIONS / essais.dossier / "videos" / v / "_presentateur.png").read_bytes() == Path(REFERENCE).read_bytes()  # gardée avec la vidéo
    assert morceau(essais, v, "levres", "s1/p2", "en")["demande"]["consigne"] == {"vue": "insert", "image": "a snowy forest", "mouvement": "gauche"}
    assert morceau(essais, v, "levres", "s1/p1", "en")["demande"]["consigne"]["vue"] == "face"
    with execution.routeur.session(essais):
        assert {m.etape: m.outil for m in execution.Morceau.objects.filter(video_id=v)} == {
            "voix": "faux_voix", "images": "faux_images", "levres": "faux_levres", "montage": "plan_montage", "miniature": "miniature_image", "revue": "controle_technique"}


def test_f6_refus_de_la_forme_et_du_presentateur(essais, presentatrice):
    from fabrique.session import univers

    univers.ajouter(essais, "personnage", "PIA FACTICE", "la même, sans référence (comme l'import de Bramble Studio)", "RT")
    assert execution.preparer(essais, f6(), PRESENTATEUR).titre == PRESENTATEUR["titre"]  # la fiche qui a une référence validée
    with pytest.raises(Refus, match="n'est pas un personnage"):
        execution.preparer(essais, f6(), {**PRESENTATEUR, "presentateur": "Personne"})
    with pytest.raises(Refus, match="face caméra au moins une fois"):
        execution.preparer(essais, f6(), {**PRESENTATEUR, "scenes": [{"id": "s1", "plans": [PRESENTATEUR["scenes"][0]["plans"][1]]}]})
    with pytest.raises(Refus, match="consigne d'image"):
        execution.preparer(essais, f6(), {**PRESENTATEUR, "scenes": [{"id": "s1", "plans": [{"id": "p1", "texte": "Regardez.", "vue": "insert"}]}]})
    univers.valider(essais, presentatrice, False, "RT")
    with pytest.raises(Refus, match="pas d'image de référence validée"):
        execution.preparer(essais, f6(), PRESENTATEUR)
    r = recettes.recette(recettes.lire("F6"))
    assert r.script == "presentateur" and r.reglages.duree_s == (60, 900) and "musique" not in [e.brique for e in r.etapes]  # cahier § 5 : pas de musique


def test_f6_presentateur_fige_bloquant(essais, presentatrice, monkeypatch):
    from fabrique.moteur import faux

    vrai = faux.fabriquer

    def fige(fiche, d, dossier):  # les lèvres du dernier plan ne bougent pas (mouvement mesuré par l'outil réel)
        r = vrai(fiche, d, dossier)
        if d.brique == "levres" and d.consigne.get("vue") == "face":
            r.infos.update(vue="face", mouvement=0.05 if d.unite == "s2/p1" else 0.6)
        return r

    monkeypatch.setattr(faux, "fabriquer", fige)
    v = fabriquer(essais, f6(), PRESENTATEUR)
    (x,) = [x for x in rapport(essais, v)["defauts"] if x.get("code") == "presentateur"]
    assert x["gravite"] == "forte" and x["debut"] == pytest.approx(3.2, abs=0.05) and "s2/p1" in x["texte"]


def test_f6_en_mode_reel_qwen_edit_et_longcat_simules(essais, presentatrice, monkeypatch):
    """F6 en mode réel, les modèles simulés au plus près (Chatterbox et Whisper, Qwen-Image et Qwen-Image-Edit, ComfyUI, LongCat dans Linux) :
    une image cadrée face caméra d'après la référence copiée avec la vidéo, pour tous les plans face ; un lot LongCat par langue ; l'insert
    filmé par la caméra ; le mouvement des lèvres mesuré ; une coupure ne refait que le plan perdu."""
    import shlex
    import shutil
    import subprocess

    from fabrique.moteur import par_plan
    from fabrique.moteur.f1 import comfy, images, voix
    from fabrique.moteur.faux import lancer, programme
    from fabrique.noyau import etat

    monkeypatch.setattr(etat, "simulation", lambda: False)
    reglages = execution.settings.SESSIONS / essais.dossier / "reglages"
    reglages.mkdir(exist_ok=True)
    (reglages / "config.json").write_text(json.dumps({"style": "style factice", "negatif_image": "x", "voix": {"ref_audio": "ref.wav", "ref_text": "x"},
                                                      "images": {"largeur": 64, "hauteur": 32, "pas": 1, "cfg": 1, "shift": 1}}), encoding="utf-8")
    appels = {"image": [], "edit": [], "longcat": [], "stop": 0}

    def dire(o, dossier, scenes, cfg, *a, **k):
        for s in scenes:
            lancer(programme("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=300:duration={1 + s['id'] / 10}", Path(dossier) / "voix" / f"s{s['id']:03d}.wav")
        (Path(dossier) / "voix" / "_controle.json").write_text(json.dumps({str(s["id"]): {"score": 0.99, "entendu": s["narration"]} for s in scenes}), encoding="utf-8")

    def qwen(self, prompt, out, seed, w=None, h=None, **k):
        appels["image"].append((prompt, seed))
        lancer(programme("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", f"color=c=0x406080:s={w}x{h}", "-frames:v", "1", out)

    def edit(self, prompt, refs, out, seed, w=None, h=None, **k):
        appels["edit"].append((prompt, [Path(r).name for r in refs], seed, w, h))
        lancer(programme("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", f"color=c=0x806040:s={w}x{h}", "-frames:v", "1", out)

    def windows(p: str) -> Path:
        return Path(p[5].upper() + ":/" + p[7:])

    vrai_run = par_plan.subprocess.run

    def longcat(cmd, *a, **k):  # le lot de lipsync_batch.py : un clip qui bouge par plan, à la durée de sa voix
        if cmd[0] != "wsl":
            return vrai_run(cmd, *a, **k)
        jobs = json.loads(windows(shlex.split(cmd[-1].split("--jobs ")[1])[0]).read_text(encoding="utf-8"))
        appels["longcat"].append(jobs)
        for j in jobs:
            lancer(programme("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", f"testsrc=s=64x36:r=25:d={par_plan.duree(windows(j['audio'])):.2f}",
                   "-pix_fmt", "yuv420p", windows(j["out"] + ".mp4"))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(voix, "faire", dire)
    monkeypatch.setattr(images.Images, "qwen_image", qwen)
    monkeypatch.setattr(images.Images, "qwen_edit", edit)
    monkeypatch.setattr(comfy, "start", lambda *a, **k: None)
    monkeypatch.setattr(comfy, "stop", lambda *a, **k: appels.__setitem__("stop", appels["stop"] + 1))
    monkeypatch.setattr(par_plan.subprocess, "run", longcat)
    try:
        v = execution.preparer(essais, f6(), PRESENTATEUR)
        with execution.routeur.session(essais):
            assert {m.etape: m.outil for m in v.morceaux.all()} == {"voix": "plan_voix", "images": "plan_images", "levres": "plan_levres", "montage": "plan_montage",
                                                                   "miniature": "miniature_image", "revue": "controle_technique"}
        execution.jouer(essais, v.id)
        (prompt, refs, graine, w, h), = appels["edit"]  # une image cadrée pour les deux plans face, d'après la référence copiée avec la vidéo
        assert refs == ["_presentateur.png"] and (graine, w, h) == (7, 64, 32) and "pia factice from Picture 1" in prompt and "a cosy reading corner" in prompt
        assert [g for _, g in appels["image"]] == [1002]  # l'insert seul
        (lot,) = appels["longcat"]  # un lot pour la langue : les deux plans face
        assert [Path(j["out"]).name for j in lot] == ["s001", "s003"] and all(j["image"].endswith("/image.png") and "pia factice talks" in j["prompt"] for j in lot)
        assert lot[1]["audio"].endswith("/voix/s2/p1/voix.wav") and appels["stop"] >= 2  # ComfyUI arrêté après les images et avant LongCat
        assert morceau(essais, v.id, "levres", "s1/p1", "en")["resultat"]["infos"]["lot"] == 2 and morceau(essais, v.id, "levres", "s2/p1", "en")["resultat"]["infos"]["lot"] == 0
        assert morceau(essais, v.id, "levres", "s2/p1", "en")["resultat"]["infos"]["mouvement"] > 0.2  # mesuré : il bouge
        assert morceau(essais, v.id, "levres", "s1/p2", "en")["resultat"]["infos"]["mouvement"] == "gauche"  # l'insert : la caméra
        m = montages.mesure(execution.finale(essais, v.id, "en"))
        assert m["duree_s"] == pytest.approx(1.7 + 1.8 + 1.9, abs=0.1) and m["son"] and rapport(essais, v.id)["defauts"] == []
        # coupure : le clip du dernier plan perdu, refait seul
        base = execution.settings.SESSIONS / essais.dossier / "videos" / v.id / "en"
        shutil.rmtree(base / "levres" / "s2" / "p1")
        (base / "atelier" / "video" / "levres" / "s003.mp4").unlink()
        with execution.routeur.session(essais):
            execution.Morceau.objects.filter(video_id=v.id, etape="levres", unite="s2/p1").update(etat="attente")
        execution.jouer(essais, v.id)
        assert [Path(j["out"]).name for j in appels["longcat"][1]] == ["s003"] and len(appels["edit"]) == 1
    finally:
        (reglages / "config.json").unlink()


def test_video_pilote_au_format_presentateur(request):
    from fabrique.noyau.models import Tache
    from fabrique.session import reglages

    s = reglages.creer(f"Session {request.node.name}", [{"code": "xx", "nom": "Langue factice"}], promesse="découvrir les saisons")
    try:
        reglages.ecrire(s, {"formats": ["F6"], "difference": "une saison différente", "style": "aquarelle douce"}, "RT")
        reglages.finir(s, "RT")
        s.refresh_from_db()
        with pytest.raises(Refus, match="demande un présentateur"):
            reglages.pilote(s, "RT")
        personnage(s, "Pia Factice")
        assert "dans la file" in reglages.pilote(s, "RT")
        with execution.routeur.session(s):
            v = execution.Video.objects.get(id=Tache.objects.get(session_id=s.id).video_id)
            sc = recettes.script(v.script, "presentateur")
            assert v.recette["id"] == "F6" and sc.presentateur == "Pia Factice" and [p.vue for x in sc.scenes for p in x.plans] == ["face", "insert", "face"]
    finally:
        Tache.objects.filter(session_id=s.id).delete()
