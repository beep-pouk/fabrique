# Fabrique — tâche de la session de code

*Écrit par la discussion PLATEFORME le 16/11/2026. Ce fichier porte toujours la tâche suivante ; le journal va dans `docs/REPRISE.md` (à créer, dernière section d'abord).*

## Jalon J1 — Socle

**Consigne complète** : `D:\StudioKids\PROJET\notes\plateforme\04_plan_technique.md` (**validé le 16/11**). Lire § 1, 2.8, 3, 4, 6, 7.1 (ligne J1), 9, 11, 12. Le cahier des charges (`03_cahier_des_charges.md`) seulement pour un doute.

**Technique fixée** : noyau Python 3.12 + Django 5.2 LTS + django-ninja + waitress + SQLite (WAL) ; fenêtre **Qt Quick (PySide6 + QML)**, lecteur Qt Multimedia ; tests pytest et pytest-qt sans fenêtre (`QT_QPA_PLATFORM=offscreen`) ; livraison reprise de Bramble Studio (lanceur natif en C, Python embarqué, Inno Setup portable, signature, mise à jour en un clic). PyInstaller n'est pas repris.

**Reprendre, ne pas réécrire** : le code de Bramble Studio (`D:\StudioKids\OUTILS\app`, lecture seule) est la source. Copier puis adapter, avec ses tests : `studio\core\dossiers.py` (modes installé / développement, bac à sable), `programme.py` (une seule fonction construit toute ligne de commande), `journaux.py`, `reglage.py`, `cles.py` (DPAPI), `sauvegarde.py`, `diagnostic.py`, `etat.py`, `mode.py` (simulation), `demarrage.py`, `signature.py`, l'instance unique et le chien de garde (`docs\ARCHITECTURE_APP.md`, § Processus) ; `lanceur\`, `installateur\bramble.iss`, `outils_dev\construire.py`, `signer.py`, `tester.py`, `verifier.py`, `recette_installation.py`. Pour trouver vite : graphify (consigne Windows dans `D:\StudioKids\AGENTS.md`, lecture seule). Pour la fenêtre Qt : `OUTILS\fabrique_maquettes\src\qtquick\` (`Main.qml`, `NOTES.md` : saut à une demi-image près, filtre du clavier, touche tenue).

### À faire

1. **Dépôt** `D:\StudioKids\OUTILS\fabrique` (ce dossier) : `git init`, branche `main`, `.gitattributes` (LF), `.gitignore` ; uv (`D:\StudioKids\OUTILS\uv\uv.exe`), `pyproject.toml` (seule source de la version, 0.1.0), `uv.lock` ; venv sur le dossier **réel** `OUTILS\uv\python\cpython-3.12.15-windows-x86_64-none` (jamais la jonction : WinError 448). Hook `pre-push` copié de `OUTILS\app\.git\hooks\pre-push` (refuse un nom d'ami). GitHub **privé** `beep-pouk/fabrique`, code seul : le créer s'il manque (`gh`) ; impossible → commits locaux et le dire dans REPRISE.
2. **Noyau** : base du noyau (`noyau.sqlite3`) et une base par session (`sessions\<session>\session.sqlite3`), aiguillage Django vers la session en cours, identifiants stables, aucun lien entre deux bases ; `migrer` (copie de chaque base dans `_old` d'abord). Sessions d'amorçage : « Essais » seulement (Bramble est importée à J3).
3. **API locale** (port 8790, développement 8800, bac à sable 8810) : contrat OpenAPI tiré de django-ninja, flux d'événements (SSE), jeton tiré à chaque lancement du noyau ; droits des quatre appelants (§ 3.3). Test : aucune commande, tâche automatique ni outil de l'assistant ne mène aux trois gestes. Test de contrat : la fenêtre et le noyau utilisent les mêmes schémas.
4. **Processus et sous-commandes** (§ 3.2) : `Fabrique.exe` (fenêtre, `--fond`), `noyau`, `executer`, `moteur`, `commande`, `diagnostic`, `migrer`, `relais`, `arreter`, `libre` ; instance unique (8791) ; la fenêtre relance le noyau s'il ne bat plus ; journal ; réglages ; `etat.json` et `etat.txt` ; simulation (le dépôt ne fabrique ni ne publie rien pour de vrai).
5. **Garde Bramble Studio** : aucune écriture sous `Bramble Studio\`, `DONNEES\`, `DEPOT\`, `PROJET\` (code + test) ; Bramble Studio reste lu seulement.
6. **Fenêtre** : coquille sombre (jetons du § 6.2), Accueil vide, Système (sauvegardes et restauration, mises à jour, journal, clés) ; icône de la zone de notification, notifications Windows, clavier ; tests pytest-qt sans fenêtre avec captures de référence, plus une capture à 125 %, 150 % et 2560 × 1440. Aucune règle dans la fenêtre : elle ne parle qu'à l'API.
7. **Sauvegarde** chaque soir à 23 h 30 dans le dossier de sauvegarde de RT, sous-dossier `fabrique\`, 30 jours ; restauration (l'état du moment part dans `_old`).
8. **Livraison** : `construire.py --publier` assemble `Fabrique.exe` (lanceur, identité `StudioKids.Fabrique`), le Python embarqué avec PySide6, l'installateur signé vers `D:\StudioKids\FABRIQUE\versions\` ; dossier de construction hors dépôt (`OUTILS\fabrique_construction\`). Mise à jour en un clic, jouée dans le bac à sable. Contrôles du banc sur le programme livré : sans console, sans droits administrateur, sans rien d'installé sur le chemin, aucune bibliothèque chargée hors de son dossier et de Windows.
9. **Recette du jalon** : `verifier.py --jalon J1` joue les critères : installé (bac à sable) à côté de Bramble Studio, **empreinte du dossier `Bramble Studio\` et de `DONNEES\` identique avant et après** ; fenêtre ouverte, fermée, relancée ; mise à jour jouée ; sauvegarde puis restauration ; tests verts. Rapport dans `docs\`, relu par la supervision.
10. **Fin** : `OUTILS\fabrique_maquettes` rangé dans `OUTILS\_old\2026-11_fabrique_maquettes\` (rien d'effacé) ; `docs\REPRISE.md` (fait, pièges, ce qui attend RT : cliquer l'installateur la première fois) ; commit, push.

### Interdits

- Toucher Bramble Studio : `OUTILS\app` (lecture seule), le programme installé, `DONNEES`, `DEPOT`, `PROJET`, les épisodes, YouTube.
- Installer quoi que ce soit chez RT (la première installation réelle de Fabrique est cliquée par RT), écrire le registre, créer une jonction ou un raccourci ; `tail -f` ou un `grep` qui reste ouvert ; saisir des identifiants ou des clés.
- Un nom, un texte ou un réglage réel du projet dans un fichier suivi (tests et docs : noms factices).
- Rien « pour plus tard » : seulement J1. Pas de moteur à recettes (J2), pas d'import de Bramble (J3).
- Rien sur la carte graphique ; rien pendant un rendu (Bramble est en pause, vérifier quand même `DONNEES\etat.json`).

**Limite d'usage** : à l'approche, commit, « à reprendre à … » dans `docs\REPRISE.md`, `/model claude-opus-5-5`, et poursuivre.
