# Fabrique — reprise (journal des sessions de code)

*Dernière section d'abord. La tâche suivante est dans `docs/TACHE.md` (écrite par la supervision) ; le plan dans `PROJET\notes\plateforme\04_plan_technique.md`.
Aucun nom, texte ou réglage réel du projet dans un fichier suivi (tests et docs : noms factices).*

## 16-17/11/2026 — J1 (socle)

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

*(rempli en fin de session)*

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

*(rempli en fin de session)*
