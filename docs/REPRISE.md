# Fabrique — reprise (journal des sessions de code)

*Dernière section d'abord. La tâche suivante est dans `docs/TACHE.md` (écrite par la supervision) ; le plan dans `PROJET\notes\plateforme\04_plan_technique.md`.
Aucun nom, texte ou réglage réel du projet dans un fichier suivi (tests et docs : noms factices).*

## 17/11/2026 — J3 (Bramble refabrique, F1) : en cours

### Plan du jalon (par étapes, un commit chacune)

1. **Import de Bramble** (`commande importer-bramble`, à blanc puis pour de vrai ; droit « importer ») : base de Bramble copiée par l'API de sauvegarde de SQLite sur une connexion `mode=ro` (WAL compris), fichiers copiés jamais déplacés, rapport chiffré avec empreintes avant/après, rejouable tant que la session n'a rien fabriqué. Base de session : scripts et versions (+ date prévue, statut = calendrier), idées, personnages, lieux, références, langues et leurs voix ; fichiers sous `sessions\<s>\univers\` (univers.json, personnages, voix, langues.json), `regles\` (REGLES_*.md, regles.json), `reglages\` (config.json), `moteur\production_textes.py`, `calendrier\` (plan et registre éditoriaux).
2. **F1 v1** : le moteur de Bramble (`OUTILS\app\studio\moteur`, lu seulement) repris dans `fabrique\moteur\f1\`, ses lectures « racine » remplacées par les dossiers de la session et un registre d'outils partagés à Fabrique (`kit\comfy.py` repris : journal chez Fabrique) ; un adaptateur par brique qui joue une étape de Bramble sur la vidéo (`par: video`, entrées liées en liens durs, outils réels déclarés « reprend » : le `.tmp` n'est pas effacé à la reprise) ; recette `F1` v1 (mêmes étapes, réglages, graines).
3. **Égalité sans carte** (niveau consigne, ComfyUI simulé, comme Bramble le 11/11) : le moteur original de Bramble, importé en lecture depuis `OUTILS\app`, et F1 de Fabrique sur la même copie d'entrée → consignes, commandes, fichiers identiques ; test.
4. **Écrans** : Accueil (file, santé, « À faire »), Session (Vidéos, Scripts avec règles en direct et demandes à Claude, Univers en lecture), Vidéo (Script, Planche, Fabrication, Vérification avec « je coche, Fabrique refait ») ; captures.
5. **De nuit, carte libre** (jamais pendant un rendu) : égalité réelle étape par étape contre le rendu de référence (`PROJET\rendus\…_refaire_1`, lu seulement) ; essai pleine longueur (histoire d'essai, jamais publiée), analysé, corrigé par un « refaire », repris après une coupure, durée mesurée ; F1 v2 (`plan_fixe_max_s`).
- Preuve : `verifier.py --jalon J3`.

### Fait (17/11, au fil de l'eau)

- **Étape 1 — import** (`fabrique\session\bramble.py`, `commande importer-bramble [--pour-de-vrai]`, tests `test_import.py` sur un faux studio) : à blanc sur le vrai Bramble le 17/11 20 h 28 : 11 épisodes, 20 versions, 40 fiches de calendrier, 0 idée, 37 personnages (18 en double dans sa base : repris tels quels), 17 lieux, 292 références, 10 langues ; 589 fichiers, 1,17 Go ; sa base jamais ouverte sur place (db + wal copiés). Pas encore importé pour de vrai (Fabrique n'est pas installée chez RT ; l'import réel se fera dans son installation, ou dans `dev\` pour les essais).
- **Étape 2 — F1 v1** (`fabrique\moteur\f1\`) : le moteur de Bramble copié tel quel (commit à part), puis adapté : `outils.Lieux` (studio = outils partagés, session = univers, personnages, textes, règles), `outils_partages.json` (17 outils de son registre, sans « livré » : sous `OUTILS` du studio), `comfy.py` (journal `donnees\journaux\comfyui.log`, PowerShell par son chemin et sans console), `copies.textes` = `moteur\production_textes.py` de la session (jamais refait), atelier toujours explicite (jamais `PROJET\rendus`) ; `adaptateur.py` (une étape de Bramble par morceau, atelier `videos\<id>\<langue>\atelier\<date>-<code>` gardé d'une étape à l'autre — le code dans le nom sert à la saison —, sorties liées en liens durs, fond d'écran de RT jamais touché) ; 9 fiches `f1_*` ; recette `F1` v1 (forme de script `scenario-bramble`, étapes par vidéo, langue de base seulement) ; Pillow 13.0.0 (celle de Bramble).
- **Preuve côté code** (`test_f1.py`) : chaque écart avec le moteur de Bramble est compté par fichier (voix, musique, montage, lèvres, calques animés : zéro ligne changée) ; un écart de plus fait échouer la suite.
- Limites connues de F1 v1 : la voix ne rend pas de mots horodatés (liste vide) ; le contrôle (`revue`) écrit les textes YouTube et un rapport sans défaut (l'analyse arrive avec l'écran Vérification) ; une vidéo sans scène où Bramble parle échouerait au contrat des lèvres ; versions de langue (`langue.py`) pas encore reprises.

## 17/11/2026 — J2 (moteur à recettes) : fait, recette verte (23 points), 0.2.0 publiée

*Session Code du PC (Opus 5.5), pilotée par la supervision. Fabrique n'est pas encore installée chez RT (`FABRIQUE\` n'a que `versions`) : contrôles d'installation passés. GitHub : création refusée par le garde-fou de Claude Code → `docs\QUESTIONS.md` ; réponse de la supervision : **C**, commits locaux, **aucune commande Git vers le réseau** (`ls-remote`, `fetch`, `push`) tant qu'elle ne l'a pas écrit (la fenêtre « git credential helper selector » est apparue chez RT pendant la tentative).*

### Ce qui existe (J2)

- `fabrique\moteur\` :
  - `recettes.py` : schéma pydantic versionné (`"schema": 1`, refus clair d'un autre), réglages (dont `plan_fixe_max_s`, présent, sans usage avant J3), étapes `par` plan / scène / vidéo, `langue` ; forme de script « scenes-plans-narrateur » (scènes → plans, texte, exception d'outils par plan) ; ids en minuscules, sans nom réservé de Windows ; `recettes\essai.json` (les 9 étapes de F1, faux outils, en + fr) ; une recette se donne par son id (livrée) ou par un chemin `.json` (essai d'un nouveau format).
  - `briques.json` : les 8 rôles de F1, défaut, outil de simulation, contrat de sortie (extension du fichier principal, informations dues : mots horodatés pour la voix, défauts pour le contrôle) contrôlé après chaque morceau.
  - `outils.py` : fiches (`fiches\*.json`, champs du § 5.2 + `faux`), `Demande` / `Resultat` / `Estimation` typés et rangés en JSON à côté des fichiers ; choix : plan → format → session (`outil.<brique>`) → noyau (réglage `outil.<brique>`) → brique ; en simulation un vrai outil cède la place au faux de sa brique ; langues des fiches respectées ; repli local = premier local parmi les défauts (session, noyau, brique).
  - `faux.py` : un faux outil par brique (ffmpeg lavfi, fractions de seconde, sans carte) + `faux_images_en_ligne` (payant, 0,04 € l'appel, « en_panne » posé par les tests).
  - `execution.py` : `preparer` (morceaux étape × unité × langue dans la base de la session, outil choisi d'avance, recette et script copiés dans la vidéo), `jouer` (étape par étape ; `.tmp` puis renommage patient ; un résultat sans ses fichiers est refait ; trois échecs — une coupure n'en est pas un — puis `Echec` en clair, pause de 2 s entre deux ; payant : plafonds du mois (réglage `plafond_mois_eur`) et de la session (`plafond_eur`) vérifiés avant chaque appel, 0 € au départ, une nouvelle tentative, puis repli local et alerte ; chaque appel noté dans `Depense`), `estimer` (médiane des chronos par format, étape, outil ; coût avec les outils qui serviront vraiment).
  - `carte.py` : notre tâche lourde ; `DONNEES\etat.json` de Bramble Studio lu seulement (épisode en cours ; état de plus de 15 min ignoré ; récent mais illisible = attente) ; `nvidia-smi` (≥ 50 % ou la moitié de la mémoire prise ; muet = non bloquant).
  - `file.py` : file unique (`Tache`, base du noyau) : sessions réelles avant « Essais », priorité de session, ordre de mise en file ; pause / reprendre / annuler (API, fenêtre seule) ; le noyau lance `executer fabrication <id>` (détaché) quand la carte est libre, sinon la raison s'affiche ; exécuteur pris en base d'un coup (jamais deux) ; relance d'une tâche dont l'exécuteur est mort (reprise), trois relances sans morceau fini = erreur et alerte ; un geste de RT pendant un tour l'emporte ; suspendue pendant une restauration ou une mise à jour.
- Noyau : `Tache`, `Chrono`, `Depense`, `Session.priorite` (migration `noyau 0002`) ; session : `Reglage`, `Video`, `Morceau` (`session 0002`) ; `taches.py` connaît la tâche `fabrication` (état dans `donnees\taches\fabrication.json` : `libre`, restauration et mise à jour la voient ; la sauvegarde passe à côté, en priorité basse) ; `etat.json` montre la file, sa raison d'attente et ses alertes ; API `GET /file` (voir), `POST /file/{id}/{pause|reprendre|annuler}` (droit `file`, fenêtre) ; client : `file`, `agir_file`.
- `Fabrique.exe moteur <recette> <script.json>` (Claude) : essai dans la session « Essais » seulement, estimation affichée, mis dans la file ; `commande file` (Claude lit la file). Seul « RT » met une vidéo d'une session réelle dans la file (`file.mettre`, refus sinon).
- `outils_dev\verifier.py --jalon J2` : moteur en vrais processus sur un dossier temporaire (voir « Vérifié »), puis la construction et la recette d'installation de J1, qui joue aussi un essai de recette par le programme installé (étape 6 bis).
- Version **0.2.0** (`pyproject.toml`, `uv.lock`, `nouveautes.json`).

### Relecture à froid (sous-agent, 21 points) : corrigé / écarté

- Corrigé : geste de RT écrasé par un lancement (mises à jour conditionnelles) ; relance sans fin d'un exécuteur qui plante (compteur `relances`, remis à 0 à chaque morceau fini) ; état de Bramble illisible pris pour « libre » ; exécuteur lancé à la main sans verrou (il revérifie Bramble et la carte quand sa vidéo demande la carte) ; nettoyage du `.tmp` hors essai, renommage refusé par un antivirus, essais enchaînés sans pause ; nouvelle tentative payante au-delà du plafond ; repli qui ignorait le défaut local de RT ; résultat vide accepté (contrat de sortie par brique) ; simulation qui aurait pris un vrai outil ; ids sensibles à la casse et noms réservés de Windows ; chronos sans format ; file en panne qui arrêtait la boucle du noyau ; écriture de `fabrication.json` refusée par un lecteur ; deux exécuteurs sur une vidéo (prise en base) ; lancement pendant une restauration ou une mise à jour ; fichiers du moteur dans la sauvegarde (et un résultat restauré sans son média, désormais refait) ; test « aucun code » qui ne prouvait rien (fiche ajoutée dans une copie, balayage : aucun outil nommé dans le code) ; recette : processus vraiment tué, reprise lue au journal, pause d'un exécuteur vivant ; raison d'attente stable ; langues des fiches ; coût estimé trompeur à plafond 0 ; priorité basse de la sauvegarde.
- Écarté, avec la raison :
  - « Toute tâche de Bramble occupe la carte » : sa file joue aussi des tâches légères et le pilote de la supervision (`SUP_PILOTE.bat`, en continu) ; ses tâches lourdes sans épisode (analyses) sont vues par `nvidia-smi` (utilisation ou mémoire).
  - Une classe Python par brique : le contrat de chaque brique est une donnée (`briques.json`) contrôlée après chaque morceau ; les vrais adaptateurs de J3 diront s'il faut plus. Le signal « fin d'étape, libérer la carte » arrive avec ComfyUI (J3).
  - Chrono « par unité » : la médiane est par format, étape et outil ; l'étape fixe l'unité (plan, scène, vidéo).
  - Pid réutilisé par un autre `Fabrique.exe` : le noyau ne se tue jamais lui-même ; le reste est rare (même parade que Bramble Studio).

### Choix faits sans demander

- Ordre « strict dans une session » : une tâche en pause ou en erreur attend RT, les suivantes de la même session passent (sinon une vidéo en pause bloque toute la session) ; l'ordre de publication reste celui du calendrier (J4-J5).
- Les recettes livrées vivent dans le code (`moteur\recettes`) ; `FABRIQUE\formats` et la table des versions de recettes arrivent avec l'écran des formats (J5-J7). Chaque vidéo garde déjà sa copie de recette.
- Plafond payant « par mois et par session » : un plafond mensuel de Fabrique (réglage du noyau) **et** un plafond mensuel par session (réglage de la session), tous deux à 0 € au départ.
- Une fabrication est toujours une tâche lourde (le verrou joue aussi en simulation, c'est ce que la simulation montre) ; l'exécuteur ne revérifie la carte que si sa vidéo en demande (faux outils : non).
- Carte « prise par un autre programme » : utilisation ≥ 50 % (seuil de Bramble Studio) **ou** la moitié de la mémoire prise (un modèle de langue chargé, comme l'agent local de la supervision).
- La migration `noyau 0002` a été refaite avant toute publication (jamais installée nulle part).

### Vérifié

- Suite : **58 tests verts** (`outils_dev\tester.py`), dont 16 du moteur.
- **Recette J2 : tout vert, 23 points** (`python outils_dev\verifier.py --jalon J2 --publier`, 17/11 20 h 09, 4 min ; rapport `docs\VERIF_J2_PC.md`, non suivi) : refus quand Bramble Studio fabrique (état simulé : rien lancé en 8 s) ; recette d'essai de bout en bout dès la carte libre (38/38 morceaux, une vidéo par langue contrôlée) ; exécuteur tué en plein milieu (processus disparu, 8/38 sur le disque) puis relancé seul par le noyau (« reprise » au journal), morceaux déjà faits intacts, aucun `.tmp` ; pause par la fenêtre d'un exécuteur vivant, rien ne repart, puis « reprendre » ; tests du moteur ; construction 0.2.0 et recette d'installation en bac à sable (dont un essai de recette par le programme installé, 15/15) ; dossier « Bramble Studio » identique ; « DONNEES » identique hors 6 fichiers réécrits par Bramble Studio lui-même (dont une tâche `SUP_PUSH_FABRIQUE` de la supervision dans sa file).
- Publié : `D:\StudioKids\FABRIQUE\versions\Fabrique 0.2.0 - Installation.exe` + `versions.json` (0.1.0 rangée dans `versions\_old` par `construire.py`).
- Non vérifié : aucun vrai outil ni la carte (J3) ; la vraie verrou Bramble « épisode en cours » n'a été vu que simulé (Bramble en pause) ; nvidia-smi réel lu par la recette sans jamais bloquer (carte libre).

### Ce qui attend RT

- Rien de nouveau : installer Fabrique (désormais `Fabrique 0.2.0 - Installation.exe`, même geste qu'à J1) ; créer le dépôt GitHub vide (la supervision dira quand pousser).

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
