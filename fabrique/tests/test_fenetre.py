"""La fenêtre, sans fenêtre visible (QT_QPA_PLATFORM=offscreen), sur des données fixes : parcours au clavier et à la souris, puis captures
comparées aux captures de référence (tests/captures : regardées par la supervision à chaque jalon), dont 125 %, 150 % et 2560 × 1440.
Référence absente : écrite, et le test échoue pour qu'elle soit regardée. FABRIQUE_CAPTURES=refaire les réécrit toutes."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest

from fabrique.fenetre import main
from fabrique.fenetre.client import Client
from fabrique.tests.fixes import Transport

CAPTURES = Path(__file__).with_name("captures")
TOLERANCE = 0.002  # part des octets qui peuvent différer (lissage du texte)
LISTE = [("accueil", "accueil", "1280x800", "1"), ("sessions", "sessions", "1280x800", "1"), ("video", "video", "1280x800", "1"), ("systeme", "systeme", "1280x800", "1"), ("systeme_125", "systeme", "1600x1000", "1.25"),
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
    clic(f, "reprendre_2")  # la tâche en erreur
    qtbot.waitUntil(lambda: ("/api/file/1/reprendre", None) in t.actions)
    QTest.keyPress(f, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)
    QTest.keyRelease(f, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)
    assert f.property("ecran") == "sessions"
    qtbot.waitUntil(lambda: len(valeur(f, "scripts")) == 2)
    clic(f, "fabriquer_0")
    assert f.property("aFabriquer") == "s1e01"
    clic(f, "confirmer_fabriquer")  # geste de RT : confirmé
    qtbot.waitUntil(lambda: ("/api/sessions/s1/scripts/s1e01/fabriquer", None) in t.actions)
    clic(f, "onglet_videos")
    clic(f, "video_0")
    assert f.property("ecran") == "video"
    qtbot.waitUntil(lambda: len(valeur(f, "video")["plans"]) == 3)
    clic(f, "onglet_video_verification")
    clic(f, "plan_0")
    clic(f, "plan_2")
    clic(f, "plan_0")  # décoché
    clic(f, "plan_0")
    clic(f, "refaire_coches")
    qtbot.waitUntil(lambda: ("/api/sessions/s1/videos/v1/refaire", {"plans": [4, 1]}) in t.actions)
    assert valeur(f, "coches") == []
    clic(f, "retour_session")
    clic(f, "onglet_univers")
    assert f.property("onglet") == "univers"
    QTest.keyPress(f, Qt.Key.Key_3, Qt.KeyboardModifier.ControlModifier)
    QTest.keyPress(f, Qt.Key.Key_3, Qt.KeyboardModifier.ControlModifier)  # touche tenue : pas rejouée
    QTest.keyRelease(f, Qt.Key.Key_3, Qt.KeyboardModifier.ControlModifier)
    assert vus == ["sessions", "systeme"] and f.property("ecran") == "systeme"

    clic(f, "bouton_sauvegarder")
    qtbot.waitUntil(lambda: ("/api/sauvegardes", None) in t.actions)
    qtbot.waitUntil(lambda: element(f, "message").property("text") == "fait : /api/sauvegardes")
    clic(f, "restaurer_0")
    clic(f, "confirmer_restaurer")
    qtbot.waitUntil(lambda: ("/api/sauvegardes/fabrique_2026-11-15_23h30m00.zip/restaurer", None) in t.actions)
    assert f.property("aRestaurer") == ""

    systeme = element(f, "ecran_systeme")
    systeme.setProperty("contentY", systeme.property("contentHeight") - systeme.height())  # en bas de Système : les clés
    champ = element(f, "champ_gemini")
    champ.forceActiveFocus()
    for lettre in "cle-factice":  # keyClicks n'existe que pour les widgets
        QTest.keyClick(f, lettre)
    clic(f, "enregistrer_gemini")
    qtbot.waitUntil(lambda: ("/api/cles/gemini", {"valeur": "cle-factice"}) in t.actions)
    assert champ.property("text") == ""

    clic(f, "bouton_mettre_a_jour")
    qtbot.waitUntil(lambda: ("/api/versions/mettre-a-jour", None) in t.actions)
    pont.recu.emit("versions", {"installee": "0.1.0", "proposee": None, "nouveautes": [], "raison": "Fabrique est à jour"})  # rien de proposé
    qtbot.waitUntil(lambda: not element(f, "bouton_mettre_a_jour").isVisible())
    assert element(f, "version_proposee").property("text") == "Fabrique est à jour"
    QTest.keyClick(f, Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier)
    assert f.property("ecran") == "accueil"
    f.close()


def test_notifications_de_la_sauvegarde(qtbot):
    dites = []
    moteur, pont, f = main.ouvrir(Client(transport=Transport()), lambda *a: dites.append(a))
    pont.evenement.emit("sauvegarde", {"etat": "faite", "fichier": "z.zip"})
    pont.evenement.emit("sauvegarde", {"etat": "erreur", "message": "disque plein"})
    pont.evenement.emit("sauvegarde", {"etat": "en_cours"})
    assert dites == [("Sauvegarde faite", "z.zip"), ("La sauvegarde a raté", "disque plein", True)]


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
