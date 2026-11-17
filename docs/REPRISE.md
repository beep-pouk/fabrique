# Fabrique — reprise (journal des sessions de code)

*Dernière section d'abord. La tâche suivante est dans `docs/TACHE.md` (écrite par la supervision) ; le plan dans `PROJET\notes\plateforme\04_plan_technique.md`.
Aucun nom, texte ou réglage réel du projet dans un fichier suivi (tests et docs : noms factices).*

## 17/11/2026 — J2 (moteur à recettes) : en cours

*Session Code du PC (Opus 5.5), pilotée par la supervision. Fabrique n'est pas encore installée chez RT (`FABRIQUE\` n'a que `versions`) : contrôles d'installation passés. GitHub : création refusée par le garde-fou de Claude Code → `docs\QUESTIONS.md`, commits locaux.*

### Plan du jalon

- `fabrique\moteur\` : `recettes.py` (schéma versionné `"schema": 1`, pydantic, `plan_fixe_max_s` présent sans usage ; recette d'essai livrée), `briques.json` + `outils\*.json` (les 8 rôles de F1, leur outil par défaut ; fiches d'outils), `faux.py` (un faux outil par brique, ffmpeg, sans carte ; une 2e fausse voix ; un faux outil payant), `outils.py` (fiches, choix : plan → format → session → réglage du noyau → brique), `execution.py` (vidéo découpée en morceaux étape × unité × langue dans la base de la session ; joués étape par étape ; écrits dans `.tmp` puis renommés ; reprise au premier non fini ; 3 essais puis alerte ; payant : plafond 0 € par défaut, 1 nouvelle tentative, repli sur l'outil local, alerte ; chronos → médianes), `carte.py` (verrou : notre tâche lourde, `DONNEES\etat.json` de Bramble lu seulement, `nvidia-smi`), `file.py` (file unique dans la base du noyau : ordre strict par session, priorité entre sessions, pause, reprise, annulation ; le noyau lance `executer fabrication <id>`).
- Repris de Bramble Studio (lu seulement) : `core/pipeline/machine.py` (nvidia-smi, seuil 50 % de `core/pilotage.py`), lecture de son `etat.json` (`tache.episode`, `episode`), fichiers factices de `moteur/simulation.py` (ffmpeg lavfi), chronos de `core/temps.py`.
- `moteur <recette> <script>` (Claude) : un essai dans la session « Essais », mis dans la file.
- Preuve : `verifier.py --jalon J2` en vrais processus sur un dossier temporaire (noyau + file) : recette d'essai de bout en bout ; exécuteur tué en plein milieu puis repris (morceaux finis intacts, aucun `.tmp`) ; outil par défaut changé par une donnée, empreinte du code identique ; faux `etat.json` de Bramble « fabrique » → rien n'est lancé, puis libre → lancé ; suite verte.

## 16-17/11/2026 — J1 (socle) : fait, recette verte ; arrêt propre à la demande de RT (17/11, 0 h 20)

*Session Code du PC (Opus 5.5). Rien sur la carte graphique ; Bramble Studio (1.5.6, en marche, en pause) seulement lu.*

### Ce qui existe

- **Dépôt** `OUTILS\fabrique`, branche `main`, `.gitattributes` (LF), uv : `pyproject.toml` (seule source de la version, 0.1.0), `uv.lock`, venv `.venv` bâti sur le dossier réel `OUTILS\uv\python\cpython-3.12.15-windows-x86_64-none` (`uv venv --no-managed-python --python <vrai python.exe>`, `UV_PYTHON_INSTALL_DIR` pointé ailleurs). Hook `pre-push` copié de l'app (noms d'amis). Le dépôt racine ignore `OUTILS/fabrique/`, `OUTILS/fabrique_construction/` et `FABRIQUE/` par `.git\info\exclude`.
- **Paquet `fabrique\`** (repris de Bramble Studio, `OUTILS\app` lu seulement) :
  - `dossiers.py` (modes : installée = `<racine>\programme\app\fabrique` à côté de `runtime\python312.dll`, la racine est le dossier qui contient `programme` ; bac à sable = fichier `BAC_A_SABLE` ; développement = `FABRIQUE_RACINE` ou `<dépôt>\dev`), ports 8790 / 8800 / 8810 (+1 : sonnette de la fenêtre) ;
  - `garde.py` (aucune écriture sous `Bramble Studio`, `DONNEES`, `DEPOT`, `PROJET` du studio de Bramble — registre lu — ni à côté de la racine ; vérifiée au démarrage de chaque processus, avant toute écriture, et sur le dossier des sauvegardes) ;
  - `programme.py` (seule fabrique de lignes de commande, relais détaché, prise exclusive d'un port, processus de l'app reconnus par leur image), `journaux.py` (un journal par processus, secrets masqués, 14 jours), `__main__.py` (porte d'entrée : fenêtre `[--fond]`, `noyau`, `executer`, `moteur` (refus : J2), `commande` (Claude : `etat`, `sessions`), `diagnostic`, `migrer`, `relais`, `arreter`, `libre`) ;
  - `noyau\` : modèles (Session à identifiant stable, Parametre, Journal), `routeur.py` (aiguillage vers la base de la session en cours, `with routeur.session(s)`, aucun lien entre bases), `bases.py` (copie à chaud, `migrer` après copie de chaque base dans `donnees\_old`, session « Essais » d'amorçage), `api.py` (django-ninja, jetons, droits des quatre appelants, les trois gestes réservés à la fenêtre et à l'iPhone), `schemas.py` (pydantic seul : la fenêtre les importe), `jetons.py`, `evenements.py` (SSE, battement 15 s), `serveur.py` (processus du noyau : instance unique, migrations, boucle de fond : état chaque minute, sauvegarde du soir), `taches.py` (tâche détachée `executer sauvegarde`, état dans `donnees\taches\sauvegarde.json`), `sauvegarde.py` (zip daté, 30 jours, restauration avec l'état du moment dans `_old`), `etat.py` (`etat.json`, `etat.txt`, simulation), `cles.py` (DPAPI), `versions.py` (mise à jour en un clic), `diagnostic.py` ;
  - `session\` : la fiche de la session dans sa propre base ;
  - `fenetre\` : `main.py` (Qt Quick piloté en Python, icône de la zone de notification, notifications, sonnette, chien de garde du noyau, filtre du clavier), `Main.qml` (coquille sombre aux jetons du § 6.2 : Accueil vide, Système), `client.py` (client de l'API avec les schémas du noyau ; `arreter`).
- **Livraison** : `lanceur\` (Fabrique.exe, identité `StudioKids.Fabrique`), `installateur\fabrique.iss` (le dossier choisi est la racine, proposée `<studio>\FABRIQUE` ; programme dans `programme\`), `outils_dev\construire.py [--publier]`, `signer.py` (même certificat que Bramble Studio : aucun nouveau certificat), `tester.py`, `recette_installation.py`, `banc.py`, `verifier.py --jalon J1 [--publier]`.

### Vérifié

- Suite : 43 tests verts (`outils_dev\tester.py`), dont le parcours de la fenêtre sans fenêtre visible, la sonnette, et 5 captures de référence (`fabrique\tests\captures` : 100 %, 125 %, 150 %, 2560 × 1440) regardées une à une.
- **Recette J1 : tout vert, 16 points** (`python outils_dev\verifier.py --jalon J1 --publier`, 17/11 0 h 11 ; rapport `docs\VERIF_J1_PC.md`, non suivi) : construction vérifiée et publiée ; recette d'installation en bac à sable de bout en bout (refus, installation comme RT la première fois, lancement sans rien sur le chemin en 4,2 s, sauvegarde du soir rattrapée, contrôles du banc, fenêtre fermée / revenue / quittée / relancée, sauvegarde puis restauration, noyau tué puis relancé par la fenêtre en 30 s, programme jamais écrit, mise à jour 0.1.0 → 0.1.1, désinstallation : il ne reste que les données, aucune console) ; **dossier « Bramble Studio » identique avant et après** ; **« DONNEES » identique** hormis 4 fichiers que Bramble Studio réécrit lui-même en tournant (`etat.json`, `etat.txt`, `studio.db-shm`, `studio.db-wal`).
- Vraie fenêtre (plateforme Windows) regardée par capture sur un noyau de développement : nette, Cascadia Mono présente ; un défaut vu et corrigé (« Mettre à jour » visible sans version proposée).
- Publié : `D:\StudioKids\FABRIQUE\versions\Fabrique 0.1.0 - Installation.exe` + `versions.json`.
- Rangé : `OUTILS\fabrique_maquettes` → `OUTILS\_old\2026-11_fabrique_maquettes` (rien d'effacé ; commit local du dépôt racine, ces chemins seulement).
- Non vérifié : les notifications Windows à l'œil (codées, testées sans fenêtre), le son (aucun écran ne lit de vidéo à J1), un Windows neuf, l'échelle réglée dans Windows (simulée par `QT_SCALE_FACTOR`).

### Choix faits sans demander (les plus prudents)

- Pas de clé `HKCU\Software\Fabrique` : la racine se déduit de l'emplacement du programme (rien à lire, rien à écrire au registre hors de l'installateur).
- Signature : le certificat de Bramble Studio (« StudioKids (Bramble Studio) ») est réutilisé : créer un 2e certificat aurait écrit dans le magasin de RT.
- Sauvegardes : installée chez RT, dossier = réglage de Bramble Studio + `\fabrique` (base de Bramble ouverte immuable : ni verrou ni fichier écrit) ; en développement et en bac à sable, `<racine>\sauvegardes`. 30 jours = les zips de plus de 30 jours partent, le plus récent reste toujours.
- La sauvegarde du soir est due dès que la dernière date d'avant 23 h 30 passées : rattrapée au démarrage (aussi à la toute première installation).
- Restauration : toute la sauvegarde (noyau + sessions) ; restaurer une seule session arrive avec l'écran des sessions (J5).
- `moteur` répond « arrive au jalon J2 » ; `executer` ne connaît que `sauvegarde` ; Claude (`commande`) lit seulement (`etat`, `sessions`).
- Police des chiffres : Cascadia Mono si Windows l'a, sinon Consolas (les captures sans fenêtre utilisent Consolas : Qt n'y voit que `C:\Windows\Fonts`).
- La suite n'est pas rejouée par le Python assemblé (Bramble le faisait) : la recette d'installation fait tourner le vrai programme de bout en bout.
- Non repris pour J1 : « Faire confiance à la signature » (Système → À propos), le dépôt `FABRIQUE\depot`, la page iPhone (J4), l'assistant (J11), le tri des outils de développement de PySide6 dans le programme (≈ 30 Mo).

### Pièges rencontrés

- `Path.write_text` sous Windows écrit des fins de ligne CRLF : écrire en octets (`write_bytes`) ou repasser en LF avant de commiter (`git ls-files --eol`).
- Les heredocs de Git Bash et les chaînes de la commande mangent les antislashs : motifs d'expressions régulières par l'outil Edit.
- Sans fenêtre (`QT_QPA_PLATFORM=offscreen`), Qt ne trouve pas les polices de Windows : `QT_QPA_FONTDIR=C:\Windows\Fonts` ; rendu par le processeur (`QT_QUICK_BACKEND=software`) pour des captures stables.
- `QQmlApplicationEngine.rootObjects()[0]` n'est une `QQuickWindow` (avec `grabWindow`) que si `PySide6.QtQuick` est importé.
- `QImage.constBits()` pointe dans l'image : garder l'image convertie vivante pendant la lecture (sinon violation d'accès).
- Un appel du client avec un paramètre de chemin nommé comme son premier argument (`nom`) : premier argument positionnel seulement (`/`).
- Un signal émis par un fil Python vers une fonction anonyme peut s'exécuter dans ce fil : la sonnette passe par la méthode d'un objet du fil de la fenêtre (test).
- `_wmi.pyd` (module de Python) importe `vcruntime140_1.dll` sans l'avoir à côté de lui : Windows prenait sa copie ; elle est posée à côté de `Fabrique.exe`.
- L'antivirus (Kaspersky) injecte ses DLL dans tout processus : le contrôle des bibliothèques retire celles qu'un processus témoin de Windows (PowerShell) a aussi.
- Le bac de la session isole le registre et les raccourcis (voir `OUTILS\app\docs\REPRISE_APP.md`, 12/11) : la recette d'installation en bac à sable est sans effet chez RT.
- Bramble Studio en marche réécrit seul `DONNEES\etat.*`, sa base et ses journaux : la recette J1 les montre à part.

### Ce qui attend RT

1. **Installer Fabrique** (la première fois, son clic) : double-cliquer `D:\StudioKids\FABRIQUE\versions\Fabrique 0.1.0 - Installation.exe`, garder le dossier proposé (`D:\StudioKids\FABRIQUE`), cocher ou non « icône sur le Bureau » et « démarrer avec Windows », Installer. Windows peut avertir (signature maison) : « Informations complémentaires » → « Exécuter quand même ». Bramble Studio reste tel quel.
2. **Créer le dépôt GitHub privé `fabrique`** (compte `beep-pouk`, sans README) : `gh` n'est pas sur le PC et la consigne interdit de saisir des identifiants. Le dépôt local a déjà son `origin` : la session suivante fera `git push -u origin main`.

### À reprendre (demain)

- Pousser dès que le dépôt GitHub existe (`git fetch` puis `git push -u origin main`, le hook `pre-push` contrôle les noms).
- Après l'installation par RT : vérifier hors du bac (Système de Fabrique ; `D:\StudioKids\FABRIQUE\donnees\etat.txt`) que le noyau tourne, que la première sauvegarde est dans `C:\StudioKids\SAUVEGARDES\fabrique` (dossier lu dans le réglage de Bramble Studio), et que la fenêtre et ses notifications portent bien le nom « Fabrique ».
- Puis la tâche suivante de `docs\TACHE.md` (J2, écrite par la supervision).
