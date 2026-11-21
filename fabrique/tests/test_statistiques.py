"""J11, statistiques et « quoi fabriquer ensuite » (noms factices) : chiffres par vidéo (heures vues, carte, temps de RT, dépenses, revenus),
totaux par session et par chaîne, classement par chaîne, saisie des revenus et de la portée, temps de RT envoyé par la fenêtre, droits."""
from datetime import timedelta

import pytest
from django.conf import settings
from django.test import Client as Navigateur
from django.utils import timezone

from fabrique.garde import Refus
from fabrique.noyau import bases, etat, jetons, routeur
from fabrique.noyau.models import Depense
from fabrique.publication import rendement
from fabrique.session import models as m


def entete(qui: str) -> dict:
    jetons.tirer(settings.DONNEES)
    return {"HTTP_AUTHORIZATION": f"Bearer {jetons.lire(settings.DONNEES, qui)}"}


def video(s, n: int, fmt="F1", jours=10, heures=3.0, langues=("en",), carte=(3600, 1800)) -> m.Video:
    """Une vidéo publiée il y a `jours` jours : images (carte, commune) et voix (carte, par langue) chronométrées, montage sans carte."""
    with routeur.session(s):
        v = m.Video.objects.create(titre=f"Vidéo factice {n}", nom=f"2099-01-0{n}-s1e0{n}", script={}, recette={"id": fmt})
        m.Morceau.objects.create(video=v, etape="images", brique="images", unite="", langue="", ordre=0, outil="f1_images", etat="fini", secondes=carte[0])
        m.Morceau.objects.create(video=v, etape="montage", brique="montage", unite="", langue="", ordre=2, outil="f1_montage", etat="fini", secondes=600)
        for i, langue in enumerate(langues):
            m.Morceau.objects.create(video=v, etape="voix", brique="voix", unite="", langue=langue, ordre=1, outil="f1_voix", etat="fini", secondes=carte[1])
            d = m.Destination.objects.get_or_create(langue=langue, reseau="youtube", simulation=etat.simulation(), defaults={"jeton": "chiffré factice"})[0]
            p = m.Publication.objects.create(video=v, langue=langue, dossier=langue, identifiant_youtube=f"vid{n}{langue}", statut="planifiee",
                                             planifiee_le=timezone.now() - timedelta(days=jours), simulation=etat.simulation())
            m.StatistiqueJour.objects.create(destination=d, publication=p, date=timezone.localdate() - timedelta(days=1), vues=100, heures=heures / (i + 1),
                                             retention=40, impressions=1000, ctr=4.0)
        return v


@pytest.fixture(autouse=True)
def delier():
    """Après chaque test : les chaînes factices déliées (jeton vide), sinon le relevé quotidien des autres fichiers de tests les lirait."""
    yield
    from fabrique.noyau.models import Session

    for s in Session.objects.all():
        with routeur.session(s):
            m.Destination.objects.filter(jeton="chiffré factice").update(jeton="")


@pytest.fixture
def chiffres(request):
    """Deux sessions : « Alpha » (F1, 3 vidéos anciennes et une récente, en et xx), « Bêta » (F4, 3 vidéos qui rendent moins), « Gamma » (une seule)."""
    a, b, g = (bases.creer(f"Stats {x} {request.node.name}") for x in ("Alpha", "Bêta", "Gamma"))
    va = [video(a, n, langues=("en", "xx")) for n in (1, 2, 3)] + [video(a, 4, jours=2)]
    for n in (1, 2, 3):
        video(b, n, fmt="F4", heures=1.0, carte=(3600, 0))
    video(g, 1, heures=50.0)
    with routeur.session(a):
        m.TempsRT.objects.create(cle=f"video:{va[0].id}", date=timezone.localdate(), secondes=120)
        m.TempsRT.objects.create(cle="script:s1e01", date=timezone.localdate(), secondes=60)
        m.Publication.objects.filter(video=va[0], langue="en").update(revenu_eur=0.5)
        m.StatistiqueJour.objects.create(destination=m.Destination.objects.get(langue="en"), date=timezone.localdate() - timedelta(days=2), vues=7, heures=0.5)
    Depense.objects.create(session_id=a.id, video_id=va[0].id, outil="faux_voix_en_ligne", estime_eur=1.0, reel_eur=1.2)
    Depense.objects.create(session_id=a.id, video_id=va[0].id, outil="faux_voix_en_ligne", estime_eur=0.3)
    return a, b, g, va


def test_chiffres_par_video_et_par_session(chiffres):
    a, b, g, va = chiffres
    s = rendement.session(a)
    v1 = next(x for x in s["videos"] if x["id"] == va[0].id)
    # carte : images (1 h) + deux voix (0,5 h chacune), le montage ne compte pas ; RT : 2 min sur la vidéo + 1 min sur son script
    assert (v1["carte_h"], v1["rt_min"], v1["depenses_eur"], v1["revenu_eur"]) == (2.0, 3.0, 1.5, 0.5)
    assert (v1["vues"], v1["heures"], v1["impressions"], v1["ctr"], v1["langues"]) == (200, 4.5, 2000, 4.0, ["en", "xx"])
    assert v1["par_heure_carte"] == 2.25 and v1["par_minute_rt"] == 1.5 and v1["publiee_le"]
    assert [x["id"] for x in s["videos"]][0] == va[3].id  # la plus récente en tête
    (d_en,) = [d for d in s["destinations"] if d["langue"] == "en"]
    assert d_en["vues_28j"] == 7 and d_en["jours"] == [{"date": f"{timezone.localdate() - timedelta(days=2):%d/%m}", "vues": 7}]
    r = rendement.resume(a)
    assert (r["videos"], r["publiees"], r["carte_h"], r["revenu_eur"]) == (4, 4, 2.0 * 3 + 1.5, 0.5)


def test_quoi_fabriquer_ensuite_par_chaine(chiffres):
    a, b, g, va = chiffres
    lignes = [x for x in rendement.ensuite() if x["session_id"] in (a.id, b.id, g.id)]
    cles = [(x["session"], x["format"], x["langue"], x["assez"]) for x in lignes]
    # Alpha en : 3 × 3 h vues pour 3 × 1,5 h de carte (images + voix en) = 2 h/h ; Alpha xx : 3 × 1,5 h pour 4,5 h = 1 h/h ; Bêta : 3 × 1 h pour 3 h
    # (sa voix ne prend pas la carte) = 1 h/h, moins de RT mesuré ; Gamma : une seule vidéo, pas assez de chiffres malgré ses 50 h
    assert cles == [(a.nom, "F1", "en", True), (a.nom, "F1", "xx", True), (b.nom, "F4", "en", True), (g.nom, "F1", "en", False)]
    assert lignes[0]["par_heure_carte"] == 2.0 and lignes[0]["recentes"] == 1 and lignes[0]["videos"] == 3 and lignes[0]["revenu_eur"] == 0.5


def test_temps_de_rt_et_saisies_par_l_api(chiffres):
    a, b, g, va = chiffres
    n = Navigateur()
    url = f"/api/sessions/{a.id}"
    for _ in range(2):
        assert n.post(f"{url}/temps", {"cle": f"video:{va[1].id}", "secondes": 60}, content_type="application/json", **entete("fenetre")).status_code == 200
    with routeur.session(a):
        assert m.TempsRT.objects.get(cle=f"video:{va[1].id}").secondes == 120
    with pytest.raises(Refus):
        rendement.noter_temps(a, "n'importe quoi", 60)
    assert n.post(f"{url}/temps", {"cle": f"video:{va[1].id}", "secondes": 60}, content_type="application/json", **entete("claude")).status_code == 403
    with routeur.session(a):
        pub = m.Publication.objects.get(video=va[1], langue="en").id
    assert n.post(f"{url}/publications/{pub}/revenu", {"revenu_eur": 2.5}, content_type="application/json", **entete("claude")).status_code == 403
    assert n.post(f"{url}/publications/{pub}/revenu", {"revenu_eur": 2.5}, content_type="application/json", **entete("fenetre")).status_code == 200
    jour = f"{timezone.localdate() - timedelta(days=3)}"
    r = n.post(f"{url}/publications/{pub}/portee", {"date": jour, "impressions": 500, "ctr": 6.5}, content_type="application/json", **entete("fenetre"))
    assert r.status_code == 200, r.content
    s = n.get(f"{url}/statistiques", **entete("fenetre")).json()
    v2 = next(x for x in s["videos"] if x["id"] == va[1].id)
    assert v2["revenu_eur"] == 2.5 and v2["rt_min"] == 2.0 and v2["impressions"] == 2500 and v2["ctr"] == 4.5  # (1000 × 4 + 1000 × 4 + 500 × 6,5) / 2500
    tout = n.get("/api/statistiques", **entete("fenetre")).json()
    assert {x["nom"] for x in tout["sessions"]} >= {a.nom, b.nom} and tout["ensuite"]


def test_variantes_notees_proposees_et_choisies(tmp_path, request):
    """J11, titres et miniatures : note mesurée (contraste, couleurs, longueur du titre) ; proposition quand le taux de clic reste sous la
    médiane de la chaîne après MIN_IMPRESSIONS ; choix avant la publication = nouvelle version du titre."""
    from PIL import Image, ImageDraw

    from fabrique.publication import variantes

    terne, vive = tmp_path / "terne.png", tmp_path / "vive.png"
    Image.new("RGB", (1280, 720), (128, 128, 128)).save(terne)
    im = Image.new("RGB", (1280, 720), (250, 200, 0))
    ImageDraw.Draw(im).rectangle((0, 0, 640, 720), fill=(20, 40, 200))
    im.save(vive)
    assert variantes.note(vive, "Titre court")[0] > variantes.note(terne, "Titre court")[0]
    assert variantes.note(vive, "x" * 90)[0] < variantes.note(vive, "Titre court")[0]

    s = bases.creer(f"Variantes {request.node.name}")
    autres = [video(s, n) for n in (1, 2)]  # 1 000 impressions à 4 % chacune : la médiane de la chaîne
    v = video(s, 3)
    with routeur.session(s):
        for a in autres:
            m.StatistiqueJour.objects.filter(publication__video=a).update(impressions=2000)
        pub = m.Publication.objects.get(video=v)
        pub.variantes = [{"titre": "Titre A", "miniature": "", "note": 5.0, "raisons": [], "depuis": None, "portee": None},
                         {"titre": "Titre B", "miniature": "", "note": 7.0, "raisons": [], "depuis": None, "portee": None}]
        pub.save()
        assert variantes.proposition(pub) is None  # 1 000 impressions à 4 % : pas sous la médiane
        m.StatistiqueJour.objects.filter(publication=pub).update(impressions=1500, ctr=2.0)
        assert variantes.proposition(pub)["variante"] == 1
        pub.statut, pub.identifiant_youtube, pub.titre, pub.versions = "brouillon", "", "Titre A", [{"numero": 1, "titre": "Titre A"}]
        pub.save()
    assert variantes.choisir(s, pub.pk, 1, "rt") == "variante 2 posée"
    with routeur.session(s):
        pub.refresh_from_db()
        assert (pub.titre, pub.variante, len(pub.versions)) == ("Titre B", 1, 2)
    with pytest.raises(Refus):
        variantes.choisir(s, pub.pk, 5, "rt")
