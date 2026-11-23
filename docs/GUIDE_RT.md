# Fabrique — le guide de RT

*Court, pour s'y retrouver. Les images sont les captures de référence de la fenêtre (`fabrique\tests\captures`), refaites à chaque version.*

## Installer, ouvrir, mettre à jour
- **Installer** : double-clic sur « Fabrique x.y.z - Installation » (dossier `FABRIQUE\versions`). Aucun mot de passe d'administrateur. Fabrique se range à côté de Bramble Studio et n'y touche jamais.
- **Ouvrir** : **Fabrique** dans le menu Démarrer (elle démarre aussi avec Windows). Une seule fenêtre, sombre ; aucune console. La croix range la fenêtre, le travail continue.
- **Mettre à jour** : Système → **Mettre à jour** quand une version est prête ; Fabrique se relance seule et montre « Quoi de neuf ». On avance seulement : pas de retour à une version d'avant.
- **Mode** : Système → Mode. En simulation, tout se joue avec de faux outils, rien ne sort du PC. En mode réel, rien ne part sans votre clic.

## Se déplacer
| Touche | Écran | Pour quoi |
|---|---|---|
| Ctrl+1 | Accueil | le mur des sessions, la file, ce qui attend votre clic ([capture](../fabrique/tests/captures/accueil.png)) |
| Ctrl+2 | Sessions | une session : Calendrier, Vidéos, Scripts, Univers, Formats, Destinations, Règles |
| Ctrl+3 | File | ce qui se fabrique, dans l'ordre ; Pause, Reprendre, Annuler ([capture](../fabrique/tests/captures/file.png)) |
| Ctrl+4 | Outils | les outils de chaque rôle (en service, candidat, retiré), installer un outil |
| Ctrl+5 | Banc | comparer deux outils à l'aveugle : vous votez ([capture](../fabrique/tests/captures/banc_vote.png)) |
| Ctrl+6 | Statistiques | vues, heures vues, temps de carte, votre temps, dépenses ; « quoi fabriquer ensuite » |
| Ctrl+9 | Système | mode, sauvegardes, mises à jour, clés, journal |
| Ctrl+0 | Assistant | une demande écrite → un plan chiffré ; « D'accord » → un brouillon |

## Les trois gestes (à vous seul)
1. **Fabriquer** : sur un script prêt (Session → Scripts ou Calendrier). Fabrique vérifie la carte : jamais pendant un rendu de Bramble Studio ; la vidéo attend son tour dans la File. Coupure de courant : elle reprend seule là où elle s'était arrêtée.
2. **Approuver** : Vidéo → Vérification ([capture](../fabrique/tests/captures/video.png)) : regarder, lire les défauts minutés ; un plan raté se coche puis **Refaire**. Tout va bien : **Approuver**, puis choisir parmi les trois titres et miniatures notés.
3. **Publier** : Vidéo → Publication ([capture](../fabrique/tests/captures/publication.png)) : non répertorié d'abord, créneau, miniature, playlist ; **Publier**. Pour les autres réseaux, un paquet prêt à poster. Depuis l'iPhone : la page de Fabrique (code à 6 chiffres) montre les vidéos à voir, approuver, publier.

## Une nouvelle session
- Accueil → **Nouvelle session**, ou demandez-la à l'assistant (Ctrl+0) puis dites « D'accord » : un brouillon arrive, en pause.
- Les étapes, dans l'ordre ([capture](../fabrique/tests/captures/nouvelle.png)) : langues, public, promesse ; format ; univers (personnages, lieux, image de référence validée, droits, style) ; destinations (une chaîne par langue) ; règles (ce qui change d'une vidéo à l'autre, durées, plafond de dépense) ; **Terminer** dit ce qui manque encore.
- **Vidéo pilote** : une vidéo d'essai en simulation, pour voir la session de bout en bout ; elle se regarde dans Vidéos.

## Formats
F1 vidéo longue (celle de Bramble) · F2 compilation · F3 courte verticale (tirée d'une longue, ou créée seule) · F4 voix off + images · F5 chanson avec karaoké · F6 présentateur virtuel. Chaque format est une recette ; changer l'outil d'un rôle se fait dans Outils, après un banc.

## Sauvegardes, export
- Une sauvegarde chaque soir, et au clic (Système → Sauvegardes) ; **Restaurer** remet l'état choisi (l'état d'avant est gardé à côté).
- Session → **Exporter** fait un fichier `.fabrique` (avec ou sans les vidéos) ; **Importer** le relit à l'identique, sur ce PC ou un autre.

## En cas de souci
- La fenêtre dit en une phrase ce qui bloque (carte prise par Bramble Studio, clé manquante, plafond atteint…). Rien n'est perdu : la File reprend.
- Système → Journal garde le détail pour la supervision.
