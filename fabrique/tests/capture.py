"""Une capture de la fenêtre sur les données fixes, sans fenêtre visible : python -m fabrique.tests.capture <png> <écran>[:<onglet>] <largeur>x<hauteur> <échelle>
Un processus par capture : l'échelle (QT_SCALE_FACTOR) se pose avant la création de l'application. Lancé par tests/test_fenetre.py. Jour fixe
(18/11/2026, calendrier de décembre) : une capture ne change pas avec la date."""
import os
import sys

if __name__ == "__main__":
    png, ecran, taille, echelle = sys.argv[1:5]
    os.environ.update({"QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software", "QT_QPA_FONTDIR": os.path.join(os.environ["WINDIR"], "Fonts"), "QT_SCALE_FACTOR": echelle})
    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from fabrique.fenetre import main
    from fabrique.fenetre.client import Client
    from fabrique.tests.fixes import Transport

    app = QApplication(sys.argv[:1])
    moteur, pont, f = main.ouvrir(Client(transport=Transport()))
    largeur, hauteur = (int(n) for n in taille.split("x"))
    f.resize(round(largeur / float(echelle)), round(hauteur / float(echelle)))  # taille en pixels de l'écran
    f.setProperty("jourFixe", "2026-11-18")
    f.setProperty("calJour", "2026-12-01")
    f.show()
    ecran, _, onglet = ecran.partition(":")
    if ecran == "sessions" and onglet:
        f.setProperty("onglet", onglet)
    if ecran == "nouvelle" and onglet:
        f.setProperty("nouvelle", {"etape": int(onglet)})
    pont.aller.emit({"script_ecriture": "script", "publication": "video"}.get(ecran, ecran))
    if ecran == "video" and onglet:  # la vidéo des données fixes, à l'onglet donné
        from PySide6.QtCore import Q_ARG, QMetaObject

        QTimer.singleShot(300, lambda: (QMetaObject.invokeMethod(f, "ouvrirVideo", Q_ARG("QVariant", "v1")), f.setProperty("ongletVideo", onglet)))
    if ecran == "video" and not onglet:  # la vidéo des données fixes, onglet Vérification, un plan coché
        from PySide6.QtCore import Q_ARG, QMetaObject

        QTimer.singleShot(300, lambda: (QMetaObject.invokeMethod(f, "ouvrirVideo", Q_ARG("QVariant", "v1")), f.setProperty("ongletVideo", "verification"),
                                        f.setProperty("coches", [1])))
    if ecran == "publication":  # la même vidéo, onglet Publication : aperçu de deux langues, paquets
        from PySide6.QtCore import Q_ARG, QMetaObject

        QTimer.singleShot(300, lambda: (QMetaObject.invokeMethod(f, "ouvrirVideo", Q_ARG("QVariant", "v1")), f.setProperty("ongletVideo", "publication")))
    if ecran == "banc" and onglet:  # un banc des données fixes ouvert : 1 à voter, 2 au verdict rendu
        from PySide6.QtCore import Q_ARG, QMetaObject

        QTimer.singleShot(300, lambda: QMetaObject.invokeMethod(f, "ouvrirBanc", Q_ARG("QVariant", int(onglet))))
    if ecran.startswith("script"):  # « script_ecriture » : le même script, en cours d'écriture
        from PySide6.QtCore import Q_ARG, QMetaObject

        QTimer.singleShot(300, lambda: QMetaObject.invokeMethod(f, "ouvrirScript", Q_ARG("QVariant", "s1e01")))
        if ecran == "script_ecriture":
            QTimer.singleShot(900, lambda: QMetaObject.invokeMethod(f, "ecrire"))
    boucle = QEventLoop()
    QTimer.singleShot(1500, boucle.quit)  # réponses fixes arrivées, animations finies
    boucle.exec()
    QCoreApplication.processEvents()
    if not f.grabWindow().save(png):
        sys.exit(f"capture non écrite : {png}")
