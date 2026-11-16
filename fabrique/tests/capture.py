"""Une capture de la fenêtre sur les données fixes, sans fenêtre visible : python -m fabrique.tests.capture <png> <écran> <largeur>x<hauteur> <échelle>
Un processus par capture : l'échelle (QT_SCALE_FACTOR) se pose avant la création de l'application. Lancé par tests/test_fenetre.py."""
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
    f.show()
    pont.aller.emit(ecran)
    boucle = QEventLoop()
    QTimer.singleShot(1500, boucle.quit)  # réponses fixes arrivées, animations finies
    boucle.exec()
    QCoreApplication.processEvents()
    if not f.grabWindow().save(png):
        sys.exit(f"capture non écrite : {png}")
