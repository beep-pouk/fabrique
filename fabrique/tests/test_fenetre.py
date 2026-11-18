"""La fenêtre, sans fenêtre visible (QT_QPA_PLATFORM=offscreen), sur des données fixes : parcours au clavier et à la souris, puis captures
comparées aux captures de référence (tests/captures : regardées par la supervision à chaque jalon), dont 125 %, 150 % et 2560 × 1440.
Référence absente : écrite, et le test échoue pour qu'elle soit regardée. FABRIQUE_CAPTURES=refaire les réécrit toutes."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Q_ARG, QObject, QPointF, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest

from fabrique.fenetre import main
from fabrique.fenetre.client import Client
from fabrique.tests.fixes import Transport

CAPTURES = Path(__file__).with_name("captures")
TOLERANCE = 0.002  # part des octets qui peuvent différer (lissage du texte)
LISTE = [("accueil", "accueil", "1280x800", "1"), ("sessions", "sessions", "1280x800", "1"), ("file", "file", "1280x800", "1"),
         ("calendrier", "sessions:calendrier", "1280x800", "1"), ("univers", "sessions:univers", "1280x800", "1"), ("formats", "sessions:formats", "1280x800", "1"),
         ("destinations", "sessions:destinations", "1280x800", "1"), ("regles", "sessions:regles", "1280x800", "1"), ("nouvelle", "nouvelle", "1280x800", "1"),
         ("nouvelle_5", "nouvelle:5", "1280x800", "1"), ("planche", "video:planche", "1280x800", "1"), ("suivi", "video:suivi", "1280x800", "1"),
         ("calendrier_150", "sessions:calendrier", "1920x1200", "1.5"), ("accueil_2560", "accueil", "2560x1440", "1"), ("video", "video", "1280x800", "1"), ("script", "script", "1280x800", "1"), ("script_ecriture", "script_ecriture", "1280x800", "1"), ("publication", "publication", "1280x800", "1"), ("systeme", "systeme", "1280x800", "1"), ("systeme_125", "systeme", "1600x1000", "1.25"),
         ("systeme_150", "systeme", "1920x1200", "1.5"), ("systeme_2560", "systeme", "2560x1440", "1")]


def valeur(f, nom):
    v = f.property(nom)
    return v.toVariant() if hasattr(v, "toVariant") else v


def element(f, nom, el=None):
    el = el or f.contentItem()
    if el.objectName() == nom:
        return el
    return next(filter(None, (element(f, nom, e) for e in el.childItems())), None)


def clic(f, nom):
    QTest.qWait(50)  # disposition refaite (un élément qui vient d'apparaître)
    el = element(f, nom)
    assert el is not None and el.isVisible(), nom
    QTest.mouseClick(f, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, el.mapToScene(QPointF(el.width() / 2, el.height() / 2)).toPoint())


def test_parcours(qtbot):
    t = Transport()
    moteur, pont, f = main.ouvrir(Client(transport=t))
    f.show()
    qtbot.waitUntil(lambda: valeur(f, "sante")["version"] == "0.1.0" and len(valeur(f, "cles")) == 3)
    assert f.property("ecran") == "accueil" and element(f, "ecran_accueil").isVisible()

    vus = []
    pont.aller.connect(vus.append)
    qtbot.waitUntil(lambda: len(valeur(f, "file")) == 3 and valeur(f, "machine")["disque_go"] == 85)
    QTest.keyClick(f, Qt.Key.Key_3, Qt.KeyboardModifier.ControlModifier)
    assert f.property("ecran") == "file" and element(f, "ecran_file").isVisible()
    clic(f, "reprendre_2")  # la tâche en erreur
    qtbot.waitUntil(lambda: ("/api/file/1/reprendre", None) in t.actions)
    QTest.keyPress(f, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)
    QTest.keyRelease(f, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)
    assert f.property("ecran") == "sessions"
    qtbot.waitUntil(lambda: len(valeur(f, "scripts")) == 2)
    clic(f, "script_0")  # le script : règles, planche, estimation, puis « Fabriquer »
    assert f.property("ecran") == "script"
    qtbot.waitUntil(lambda: len(valeur(f, "script")["plans"]) == 2)
    clic(f, "bouton_fabriquer")
    assert f.property("aFabriquer") == "s1e01"
    clic(f, "langue_xx")  # aussi en « xx » (sa traduction existe)
    clic(f, "confirmer_fabriquer")  # geste de RT : confirmé
    qtbot.waitUntil(lambda: ("/api/sessions/s1/scripts/s1e01/fabriquer", {"langues": ["xx"], "version": 2}) in t.actions)
    clic(f, "traduire_xx")  # une demande à Claude : déposée, la discussion la prend
    qtbot.waitUntil(lambda: ("/api/sessions/s1/scripts/s1e01/demander", {"quoi": "traduire", "langue": "xx"}) in t.actions)
    clic(f, "modifier_script")  # écrire scène par scène : les règles sont rejouées pendant la frappe, rien n'est enregistré avant le clic
    assert not element(f, "bouton_fabriquer").property("actif")
    champ = element(f, "champ_narration_1")
    champ.forceActiveFocus()
    QTest.keyClick(f, Qt.Key.Key_End, Qt.KeyboardModifier.ControlModifier)
    for lettre in " interdit":
        QTest.keyClick(f, lettre)
    qtbot.waitUntil(lambda: valeur(f, "controler")["erreurs"] == [["R-1", "mot interdit"]])
    assert [a for a in t.actions if a[0].endswith("/versions")] == []
    f.metaObject().invokeMethod(f, "ouvrirScript", Q_ARG("QVariant", "s1e02"))  # un autre script ouvert entre-temps : le texte tapé reste
    assert valeur(f, "brouillon") is None
    f.metaObject().invokeMethod(f, "ouvrirScript", Q_ARG("QVariant", "s1e01"))
    qtbot.waitUntil(lambda: valeur(f, "script")["contenu"] != {})
    assert valeur(f, "brouillon")["scenes"][1]["narration"] == "Bonne nuit, petit renard. interdit"
    clic(f, "enregistrer_version")
    qtbot.waitUntil(lambda: any(chemin.endswith("/versions") for chemin, _ in t.actions))
    contenu = next(c for chemin, c in t.actions if chemin == "/api/sessions/s1/scripts/s1e01/versions")["contenu"]
    assert contenu["scenes"][1]["narration"] == "Bonne nuit, petit renard. interdit" and contenu["scenes"][0] == valeur(f, "script")["contenu"]["scenes"][0]
    assert valeur(f, "brouillon") is None
    clic(f, "retour_scripts")
    clic(f, "onglet_videos")
    clic(f, "video_0")
    assert f.property("ecran") == "video"
    qtbot.waitUntil(lambda: len(valeur(f, "video")["plans"]) == 3)
    clic(f, "onglet_video_verification")
    assert "Note de Qwen : 5,7/10" in element(f, "note_controle").property("text") and element(f, "defaut_2").isVisible()
    clic(f, "plan_0")
    clic(f, "plan_2")
    clic(f, "plan_0")  # décoché
    clic(f, "plan_0")
    clic(f, "refaire_coches")
    qtbot.waitUntil(lambda: ("/api/sessions/s1/videos/v1/refaire", {"plans": [4, 1]}) in t.actions)
    assert valeur(f, "coches") == []
    clic(f, "onglet_video_publication")  # l'aperçu de chaque langue, Publier confirmé (geste de RT), paquets
    qtbot.waitUntil(lambda: len(valeur(f, "publications")) == 2 and len(valeur(f, "paquets")) == 2)
    assert not element(f, "bouton_approuver").isVisible() and not element(f, "publier_1").property("actif")  # langue sans chaîne reliée
    assert element(f, "titre_0").property("text") == "Le petit renard | Histoire factice"
    clic(f, "publier_0")
    assert f.property("aPublier") == 7 and not [a for a in t.actions if "/publications/" in a[0]]
    clic(f, "confirmer_publier_0")
    qtbot.waitUntil(lambda: ("/api/sessions/s1/publications/7/publier", None) in t.actions)
    assert f.property("aPublier") == -1
    pile = element(f, "onglet_publication").parentItem().parentItem().parentItem()  # le Flickable de la vidéo
    pile.setProperty("contentY", pile.property("contentHeight") - pile.height())
    clic(f, "copier_tiktok_1")
    assert element(f, "message").property("text") == "Texte copié."
    clic(f, "refaire_paquets")
    qtbot.waitUntil(lambda: ("/api/sessions/s1/videos/v1/paquets", None) in t.actions)
    clic(f, "retour_session")
    clic(f, "onglet_univers")
    assert f.property("onglet") == "univers"
    clic(f, "onglet_destinations")  # une chaîne par langue
    assert element(f, "releve").property("text") == "Statistiques relevées le 18/11 à 09:00 (chaque jour après 9 h)."
    clic(f, "relier_xx")
    qtbot.waitUntil(lambda: ("/api/sessions/s1/destinations/xx/relier", None) in t.actions)
    QTest.keyPress(f, Qt.Key.Key_4, Qt.KeyboardModifier.ControlModifier)
    QTest.keyPress(f, Qt.Key.Key_4, Qt.KeyboardModifier.ControlModifier)  # touche tenue : pas rejouée
    QTest.keyRelease(f, Qt.Key.Key_4, Qt.KeyboardModifier.ControlModifier)
    assert vus == ["file", "sessions", "systeme"] and f.property("ecran") == "systeme"

    clic(f, "bouton_sauvegarder")
    qtbot.waitUntil(lambda: ("/api/sauvegardes", None) in t.actions)
    qtbot.waitUntil(lambda: element(f, "message").property("text") == "fait : /api/sauvegardes")
    clic(f, "restaurer_0")
    clic(f, "confirmer_restaurer")
    qtbot.waitUntil(lambda: ("/api/sauvegardes/fabrique_2026-11-15_23h30m00.zip/restaurer", None) in t.actions)
    assert f.property("aRestaurer") == ""
    systeme = element(f, "ecran_systeme")
    systeme.setProperty("contentY", element(f, "bouton_code_telephone").mapToItem(systeme, QPointF(0, 0)).y() + systeme.property("contentY") - 250)  # Téléphone
    clic(f, "bouton_code_telephone")
    qtbot.waitUntil(lambda: element(f, "code_telephone").property("text") == "123 456")
    clic(f, "deconnecter_0")
    qtbot.waitUntil(lambda: ("/api/telephone/appareils/0123456789ab/deconnecter", None) in t.actions)
    assert element(f, "adresse_iphone").property("text").startswith("Tailscale est introuvable")  # les données fixes n'ont pas d'adresse
    systeme.setProperty("contentY", element(f, "bouton_mode").mapToItem(systeme, QPointF(0, 0)).y() + systeme.property("contentY") - 200)
    clic(f, "bouton_mode")  # passer en mode réel : confirmé (geste de RT)
    assert not [a for a in t.actions if a[0] == "/api/mode"]
    clic(f, "confirmer_mode")
    qtbot.waitUntil(lambda: ("/api/mode", {"reel": True}) in t.actions)

    systeme = element(f, "ecran_systeme")
    systeme.setProperty("contentY", systeme.property("contentHeight") - systeme.height())  # en bas de Système : les clés
    champ = element(f, "champ_gemini")
    champ.forceActiveFocus()
    for lettre in "cle-factice":  # keyClicks n'existe que pour les widgets
        QTest.keyClick(f, lettre)
    clic(f, "enregistrer_gemini")
    qtbot.waitUntil(lambda: ("/api/cles/gemini", {"valeur": "cle-factice"}) in t.actions)
    assert champ.property("text") == ""

    systeme.setProperty("contentY", 0)
    clic(f, "bouton_mettre_a_jour")
    qtbot.waitUntil(lambda: ("/api/versions/mettre-a-jour", None) in t.actions)
    pont.recu.emit("versions", {"installee": "0.1.0", "proposee": None, "nouveautes": [], "raison": "Fabrique est à jour"})  # rien de proposé
    qtbot.waitUntil(lambda: not element(f, "bouton_mettre_a_jour").isVisible())
    assert element(f, "version_proposee").property("text") == "Fabrique est à jour"
    QTest.keyClick(f, Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier)
    assert f.property("ecran") == "accueil"
    f.close()


def taper(f, nom, texte):
    champ = element(f, nom)
    champ.forceActiveFocus()
    QTest.keyClick(f, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)  # remplace ce qui y était
    for lettre in texte:
        QTest.keyClick(f, lettre)


def montrer(f, ecran, nom):
    """Fait défiler l'écran (un Flickable) jusqu'à l'élément."""
    e = element(f, ecran)
    e.setProperty("contentY", max(0, element(f, nom).mapToItem(e, QPointF(0, 0)).y() + e.property("contentY") - 200))


def test_parcours_j5(qtbot):
    """Mur des sessions, nouvelle session pas à pas jusqu'à la vidéo pilote, calendrier et idées, univers, formats, règles, vie de la session,
    Planche et Suivi d'une vidéo (noms factices)."""
    t = Transport()
    moteur, pont, f = main.ouvrir(Client(transport=t))
    f.setProperty("jourFixe", "2026-11-18")
    f.show()
    qtbot.waitUntil(lambda: len(valeur(f, "sessions")) == 3 and len(valeur(f, "formats")) == 2)
    assert "1 234 vues" in str([element(f, "carte_0").childItems()[0].childItems()[i].property("text") for i in range(6)])
    clic(f, "carte_1")  # une nouvelle session pas finie : l'assistant reprend à son étape
    assert f.property("ecran") == "nouvelle" and valeur(f, "nouvelle")["etape"] == 5 and f.property("session") == "s3"
    QTest.keyClick(f, Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier)

    clic(f, "bouton_nouvelle_session")
    assert f.property("ecran") == "nouvelle" and valeur(f, "nouvelle")["etape"] == 1
    assert not element(f, "creer_session").property("actif")
    taper(f, "nouvelle_nom", "Nouvelle factice")
    taper(f, "nouvelle_langues", "xx, YY")
    clic(f, "modele_0")
    clic(f, "creer_session")
    qtbot.waitUntil(lambda: valeur(f, "nouvelle")["etape"] == 2)
    assert ("/api/sessions", {"nom": "Nouvelle factice", "public": "", "promesse": "", "modele": "modele_factice.fabrique",
                              "langues": [{"code": "xx", "nom": ""}, {"code": "yy", "nom": ""}]}) in t.actions
    qtbot.waitUntil(lambda: valeur(f, "reglages")["formats"] == ["F1"])
    clic(f, "nouvelle_format_essai")
    qtbot.waitUntil(lambda: ("/api/sessions/s1/reglages", {"formats": ["F1", "essai"]}) in t.actions)
    assert valeur(f, "nouvelle")["etape"] == 2  # choisir un format n'avance pas l'assistant
    for etape in (2, 3, 4):
        clic(f, f"suivant_{etape}")
        qtbot.waitUntil(lambda: valeur(f, "nouvelle")["etape"] == etape + 1)
    assert ("/api/sessions/s1/reglages", {"assistant": "4", "style": "aquarelle douce"}) in t.actions
    taper(f, "nouvelle_duree_max", "20")  # la durée minimale vient des réglages (12)
    clic(f, "suivant_5")
    qtbot.waitUntil(lambda: valeur(f, "nouvelle")["etape"] == 6)
    assert ("/api/sessions/s1/reglages", {"assistant": "6", "difference": "un ami et un lieu différents à chaque histoire", "duree_min": 12, "duree_max": 20}) in t.actions
    clic(f, "terminer_session")
    qtbot.waitUntil(lambda: valeur(f, "nouvelle")["etape"] == 7)
    assert ("/api/sessions/s1/finir", None) in t.actions
    clic(f, "lancer_pilote")
    qtbot.waitUntil(lambda: ("/api/sessions/s1/pilote", None) in t.actions)

    QTest.keyClick(f, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)
    clic(f, "onglet_calendrier")
    f.setProperty("calJour", "2026-12-01")
    f.metaObject().invokeMethod(f, "chargerCal")
    qtbot.waitUntil(lambda: len(valeur(f, "calendrier")) == 6)
    assert element(f, "titre_calendrier").property("text") == "décembre 2026" and element(f, "jour_2026-11-30").isVisible()
    clic(f, "cal_semaine")
    assert element(f, "titre_calendrier").property("text") == "semaine du 30 novembre" and element(f, "jour_2026-12-06").isVisible()
    clic(f, "cal_apres")
    assert f.property("calJour") == "2026-12-08" and element(f, "titre_calendrier").property("text") == "semaine du 7 décembre"
    clic(f, "cal_mois")
    clic(f, "cal_avant")
    assert element(f, "titre_calendrier").property("text") == "novembre 2026"
    clic(f, "cal_tout")
    assert f.property("calTout")
    clic(f, "cal_tout")
    montrer(f, "defile_session", "champ_idee")
    taper(f, "champ_idee", "Un hibou")
    clic(f, "ajouter_idee")
    qtbot.waitUntil(lambda: ("/api/sessions/s1/idees", {"titre": "Un hibou", "resume": "", "source": ""}) in t.actions)

    clic(f, "onglet_univers")
    qtbot.waitUntil(lambda: len(valeur(f, "univers")["personnages"]) == 2)
    clic(f, "reference_1_1")  # un clic valide l'image
    qtbot.waitUntil(lambda: ("/api/sessions/s1/references/2/valider", {"validee": True}) in t.actions)
    montrer(f, "defile_session", "chemin_reference_1")
    taper(f, "chemin_reference_1", "D:/images/renard.png")
    clic(f, "ajouter_reference_1")  # sans souris : le chemin d'une image
    qtbot.waitUntil(lambda: ("/api/sessions/s1/personnages/1/references", {"fichier": "D:/images/renard.png", "vue": ""}) in t.actions)
    montrer(f, "defile_session", "credit_personnage_1")
    taper(f, "credit_personnage_1", "Illustratrice Factice")
    clic(f, "droits_personnage_1")
    qtbot.waitUntil(lambda: ("/api/sessions/s1/univers/personnage/1/droits", {"licence": "image générée", "credit": "Illustratrice Factice"}) in t.actions)
    clic(f, "partager_personnage_1")
    montrer(f, "defile_session", "partager_vers_0")
    clic(f, "partager_vers_0")  # la seule autre session réelle
    qtbot.waitUntil(lambda: ("/api/sessions/s1/univers/personnage/1/partager", {"vers": "s3"}) in t.actions)

    clic(f, "onglet_formats")
    clic(f, "utiliser_essai")
    qtbot.waitUntil(lambda: ("/api/sessions/s1/reglages", {"formats": ["F1", "essai"]}) in [a for a in t.actions][-1:])
    clic(f, "onglet_regles")
    clic(f, "enregistrer_regles")
    qtbot.waitUntil(lambda: any(c and c.get("plafond_eur") == 0 and c.get("duree_max") == 18 for _, c in t.actions))
    clic(f, "regle_ordre")
    qtbot.waitUntil(lambda: ("/api/sessions/s1/reglages", {"ordre_strict": False}) in t.actions)
    montrer(f, "defile_session", "session_pause")
    clic(f, "session_pause")
    qtbot.waitUntil(lambda: ("/api/sessions/s1/pause", {"nom": ""}) in t.actions)
    montrer(f, "defile_session", "nom_copie")
    taper(f, "nom_copie", "Copie factice")
    clic(f, "session_modele")
    qtbot.waitUntil(lambda: ("/api/sessions/s1/modele", {"nom": "Copie factice"}) in t.actions)

    clic(f, "onglet_videos")
    clic(f, "video_0")
    clic(f, "onglet_video_planche")
    clic(f, "onglet_video_suivi")
    qtbot.waitUntil(lambda: len(valeur(f, "suivi")) == 1 and valeur(f, "suivi")[0]["vues"] == 1234)
    f.close()


def test_notifications_de_la_sauvegarde(qtbot):
    dites = []
    moteur, pont, f = main.ouvrir(Client(transport=Transport()), lambda *a: dites.append(a))
    pont.evenement.emit("sauvegarde", {"etat": "faite", "fichier": "z.zip"})
    pont.evenement.emit("sauvegarde", {"etat": "erreur", "message": "disque plein"})
    pont.evenement.emit("sauvegarde", {"etat": "en_cours"})
    pont.evenement.emit("alerte", {"titre": "Publication", "message": "jeton refusé"})
    assert dites == [("Sauvegarde faite", "z.zip"), ("La sauvegarde a raté", "disque plein", True), ("Publication", "jeton refusé", True)]


def differe(a: QImage, b: QImage) -> float:
    if a.size() != b.size():
        return 1.0
    a, b = a.convertToFormat(QImage.Format.Format_RGBA8888), b.convertToFormat(QImage.Format.Format_RGBA8888)  # gardées : constBits pointe dedans
    x, y = bytes(a.constBits()), bytes(b.constBits())
    return 0.0 if x == y else sum(p != q for p, q in zip(x, y)) / len(x)


@pytest.mark.parametrize("nom,ecran,taille,echelle", LISTE)
def test_captures(tmp_path, nom, ecran, taille, echelle):
    png = tmp_path / f"{nom}.png"
    r = subprocess.run([sys.executable, "-m", "fabrique.tests.capture", png, ecran, taille, echelle], capture_output=True, text=True, timeout=120,
                       cwd=Path(__file__).parents[2])
    assert r.returncode == 0 and png.is_file(), r.stderr[-2000:]
    image = QImage(str(png))
    assert f"{image.width()}x{image.height()}" == taille
    reference = CAPTURES / f"{nom}.png"
    if os.environ.get("FABRIQUE_CAPTURES") == "refaire" or not reference.is_file():
        reference.write_bytes(png.read_bytes())
        pytest.fail(f"capture de référence écrite, à regarder : {reference}")
    assert differe(image, QImage(str(reference))) <= TOLERANCE, f"{nom} a changé : comparer {png} et {reference}"


def test_sonnette_traitee_dans_le_fil_de_la_fenetre(qtbot):
    import threading

    vus = []
    s = main.Sonnette(lambda: vus.append(("montrer", threading.current_thread())), lambda: vus.append(("quitter", threading.current_thread())))
    for message in ("montrer", "quitter"):
        t = threading.Thread(target=s.recue.emit, args=(message,))
        t.start()
        t.join()
    qtbot.waitUntil(lambda: len(vus) == 2)
    assert vus == [("montrer", threading.main_thread()), ("quitter", threading.main_thread())]


def test_le_lecteur_va_au_moment_d_un_defaut(qtbot, tmp_path):
    """Vérification : un clic sur un défaut minuté amène le vrai lecteur (Qt Multimedia, sans fenêtre visible) à son moment."""
    from fabrique.moteur import faux

    film = tmp_path / "Titre.mp4"
    subprocess.run([faux.programme("ffmpeg"), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=160x90:d=6:r=25", "-pix_fmt", "yuv420p", str(film)],
                   check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    t = Transport()
    moteur, pont, f = main.ouvrir(Client(transport=t))
    f.show()
    qtbot.waitUntil(lambda: len(valeur(f, "scripts")) == 2)  # premiers chargements finis : plus rien ne remplace la vidéo donnée ici
    f.setProperty("ongletVideo", "verification")
    f.setProperty("ecran", "video")
    pont.recu.emit("video", {"id": "v1", "titre": "Titre", "nom": "n", "recette": "F1 v1", "etapes": [], "plans": [], "script": {},
                             "controle": {"mesure": True, "note": None, "video": str(film), "defauts": [{"debut": 3.0, "fin": None, "texte": "image figée", "source": "s", "gravite": "moyenne"}]}})
    lecteur = f.findChild(QObject, "lecteur")
    qtbot.waitUntil(lambda: lecteur.property("duration") > 5000, timeout=10000)
    clic(f, "defaut_0")
    qtbot.waitUntil(lambda: abs(lecteur.property("position") - 3020) < 50, timeout=5000)
    clic(f, "frise")  # un clic au milieu de la frise : au milieu de la vidéo
    qtbot.waitUntil(lambda: abs(lecteur.property("position") - lecteur.property("duration") / 2) < 300, timeout=5000)
    f.setProperty("coches", [2])
    clic(f, "refaire_coches")  # le lecteur lâche la vidéo avant l'envoi (Windows refuse de déplacer un fichier ouvert)
    assert lecteur.property("source").isEmpty() and not [a for a in t.actions if a[0].endswith("/refaire")]
    qtbot.waitUntil(lambda: any(chemin.endswith("/videos/v1/refaire") and c == {"plans": [2]} for chemin, c in t.actions))
    film.rename(film.with_name("range.mp4"))  # Windows le laisse déplacer : le lecteur l'a bien lâché
    f.close()
