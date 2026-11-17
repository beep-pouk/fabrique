# Fabrique — tâche de la session de code

*Écrit par la supervision (discussion APP) le 17/11/2026. Remplace la tâche J1 (faite, recette verte 16 points ; texte dans l'historique git). **RT a confié le pilotage complet du chantier à la supervision (17/11)** : « efficace et qualitatif ». La supervision lance cette session elle-même (Claude Code du PC, sans fenêtre) et la relance ; elle lit `docs\REPRISE.md` et `docs\QUESTIONS.md` à chaque contrôle.*

## Mode : enchaîner les jalons J2 → J12 sans attendre de nouveau prompt

Consigne complète de chaque jalon : le plan **validé** `D:\StudioKids\PROJET\notes\plateforme\04_plan_technique.md` — § 7.1 (la ligne du jalon : contenu et « Accepté quand ») et les § qu'elle touche ; § 3, 4, 5 (architecture, données, moteur), § 6 (fenêtre), § 9 (vérifications), § 12 (risques). Le cahier (`03_cahier_des_charges.md`) seulement pour un doute.

Pour chaque jalon, dans l'ordre :

1. **Plan du jalon** en tête de `docs\REPRISE.md` (5 à 10 lignes : ce qui sera fait, ce qui sera repris de Bramble Studio, comment l'acceptation sera prouvée).
2. **Code** par petites étapes, tests à chaque changement (§ 9). Reprendre le code de Bramble Studio (`OUTILS\app`, lecture seule) plutôt que réécrire ; le trouver avec graphify (consigne Windows dans `D:\StudioKids\AGENTS.md`). Commit à chaque étape qui tient debout.
3. **Relecture à froid** avant de déclarer le jalon fini : un sous-agent relit le diff du jalon avec l'obligation de trouver des erreurs ou des manques face au plan ; corriger ce qui est juste, noter ce qui est écarté et pourquoi.
4. **Recette** : `python outils_dev\verifier.py --jalon Jn` joue les critères « Accepté quand » ; rapport `docs\VERIF_Jn_PC.md`. Tout vert → version publiée si le jalon change le programme livré, commit, push, REPRISE (fait, vérifié, choix faits sans demander, pièges, non vérifié) → **jalon suivant aussitôt**. Rouge → corriger la cause et rejouer ; jamais de jalon suivant sur du rouge.

**Arrêts permis, seulement :**
- **Un geste de RT** prévu au § 7.3 (relier les chaînes et cliquer « Publier » à J4, voter aux bancs, cliquer « Fabriquer » à J12) ou **une vraie question** : l'écrire dans `docs\QUESTIONS.md` (une ligne datée, en QCM, option recommandée en premier), **avancer sur tout ce qui n'en dépend pas**, et ne s'arrêter que si plus rien n'avance. La supervision répond dans ce fichier (ligne « Réponse : »).
- **La limite d'usage** : commit, « à reprendre à … » en tête de `docs\REPRISE.md`, puis s'arrêter. La supervision relance.

## S'inspirer de l'open source (demande de RT, 17/11 22 h 43)

Avant de concevoir une brique, un écran ou un flux, **regarder comment les meilleurs logiciels libres l'ont fait** et reprendre ce qui est éprouvé plutôt que réinventer. Ordre de préférence : 1) une bibliothèque libre installée par uv (la plus solide, licence permissive) ; 2) du code copié et adapté ; 3) seulement l'idée. Code cloné pour lecture dans `OUTILS\fabrique_construction\references\` (hors dépôt), lu avec graphify ou grep, jamais exécuté sans raison.

- **Licences** : MIT, BSD, Apache, Unlicense → copie permise, avec crédit dans `NOTICE.md` (projet, licence, fichier d'origine, version). GPL, AGPL → s'en inspirer ; copier seulement en le notant dans `NOTICE.md` (Fabrique reste privée). Modèles d'IA : **la chaîne est monétisée = usage commercial** → refuser tout modèle ou poids « non commercial » (et leurs dépendances, ex. certains détecteurs de visage). Vérifier chaque licence sur le dépôt d'origine au moment de copier.
- **À regarder, par jalon** (licences à revérifier) :
  - Fenêtre (tous les jalons) : Shotcut (Qt/QML + moteur MLT, GPL), Kdenlive (Qt, GPL) : lecteur, raccourcis, file des rendus, vérification image par image.
  - J3 (F1 v2, plans quasi fixes) : PySceneDetect (BSD) et auto-editor (Unlicense) pour mesurer coupes et mouvement ; MoviePy (MIT) pour les cadrages tirés d'une même image.
  - Moteur, recettes, file : ComfyUI (GPL, file et cache de ses graphes) ; MoneyPrinterTurbo (MIT) et ShortGPT (MIT) : chaîne script → voix → sous-titres → montage, API REST, langage de montage décrit en JSON.
  - J4 publication et paquets : Mixpost Lite (MIT) et Postiz (licence à vérifier) : connexion aux réseaux, formats et limites par réseau, programmation, reprise après coupure ; exemples officiels de l'API YouTube (Google).
  - J7 et J8 (courtes verticales, voix off + images, sous-titres mot à mot) : WhisperX (BSD) ou stable-ts (MIT), MoneyPrinterTurbo (styles de sous-titres, recadrage 9:16).
  - J9 chanson : ACE-Step (Apache), YuE, DiffRhythm — au banc à l'aveugle, licences des poids vérifiées.
  - J10 présentateur : LatentSync (Apache), MuseTalk (MIT), EchoMimic — au banc, licences des poids vérifiées.
- Noter dans REPRISE ce qui a été repris, d'où, et ce que cela a évité d'écrire. Rester mesuré : regarder vite, ne pas lire des projets entiers (l'usage de la semaine est compté).

## Urgent (trouvé par la supervision le 17/11 à 20 h, à faire avant de continuer)

- **Fabrique installée chez RT ne démarre pas son noyau** : `D:\StudioKids\FABRIQUE\donnees\journaux\sortie_noyau.log` → `ModuleNotFoundError: No module named 'config'`. Cause : lancée depuis un processus de Bramble Studio, Fabrique hérite de `DJANGO_SETTINGS_MODULE=config.settings`, et `__main__.py` (l. 102), `wsgi.py` et `conftest.py` font `setdefault`. Corriger à la racine : Fabrique impose ses propres variables (`DJANGO_SETTINGS_MODULE`, et retire `PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP`, `VIRTUAL_ENV`… héritées) pour elle et pour chaque processus qu'elle lance ; test + point de recette « lancée depuis un parent qui porte des variables de Bramble Studio ». Puis version 0.1.1 publiée et **mise à jour de l'installation réelle de RT** (bouton « Mettre à jour » de Fabrique, ou installateur en silence par-dessus) ; contrôler hors du bac : noyau en marche, `donnees\etat.txt`, première sauvegarde dans le dossier de sauvegarde de RT `\fabrique`, nom « Fabrique » sur la fenêtre et les notifications. Après la relance de 19 h 51 par la supervision (`Fabrique.exe arreter`, puis lancement propre), un `Fabrique.exe` tourne sans noyau ni journal : comprendre pourquoi (instance unique ? fenêtre sans chien de garde ?) et corriger.
- **GitHub** : fait (17/11, 20 h 40 : dépôt créé par RT, `main` poussé, `credential.helper manager` réglé dans le dépôt). Pousser à chaque jalon.

## Tout de suite (avant J2) — fait le 17/11 sauf GitHub

1. **GitHub** : le dépôt privé `beep-pouk/fabrique` n'existe pas encore. RT autorise (17/11) à le créer par l'API REST de GitHub (`POST https://api.github.com/user/repos`, `{"name":"fabrique","private":true}`) avec le jeton que Git a déjà enregistré pour github.com (`git credential fill`), **sans jamais l'afficher, l'écrire dans un fichier ni le journaliser**. Puis `git push -u origin main` (le hook `pre-push` contrôle les noms). Impossible → une ligne dans QUESTIONS.md, commits locaux, et continuer.
2. **Installation réelle** : la supervision installe Fabrique 0.1.0 chez RT (installateur, à l'écran). Si `D:\StudioKids\FABRIQUE\programme\` existe : faire les contrôles « À reprendre » de la REPRISE J1 (noyau en marche, première sauvegarde dans le dossier de sauvegarde de RT `\fabrique`, nom « Fabrique » sur la fenêtre et les notifications). Sinon : passer, la supervision le fera.

## Jalon en cours : J2 — Moteur à recettes

Plan § 5 (5.1 à 5.5) et ligne J2 du § 7.1. **Accepté quand** : en simulation, une recette d'essai passe de bout en bout ; tuée en plein milieu, elle reprend sans rien perdre ; changer l'outil par défaut ne change aucun code (test) ; refus quand Bramble Studio fabrique (simulé).

Points d'attention :
- Faux outils pour chaque brique (ffmpeg, quelques secondes, sans carte) ; **aucun outil réel ni carte graphique à J2**.
- Briques et prises : les rôles de F1 d'abord (voix, images, animation, musique, lèvres, montage, miniature, contrôle). Schéma des recettes versionné ; chaque vidéo garde la version qui l'a faite. Le réglage `plan_fixe_max_s` existe dans le schéma (sa valeur et son usage arrivent à J3, F1 v2).
- Verrou de carte : lire `DONNEES\etat.json` de Bramble Studio **sans y écrire** ; `nvidia-smi` ; tâches légères à côté. Les tests simulent « Bramble fabrique ».
- Outils en ligne : un faux outil payant (coût estimé, plafond à 0 € par défaut, une seule nouvelle tentative, repli sur l'outil local, alerte en clair).
- Morceaux écrits à côté puis renommés ; reprise au premier morceau non fini ; trois essais puis alerte ; chronos → estimations (médianes).

Ensuite : J3 (Bramble refabrique, F1 ; égalité et essais réels **de nuit, carte libre, jamais pendant un rendu**), J4 (publication), puis J5 → J12, dans l'ordre du § 7.1.

## Interdits (inchangés)

- Toucher Bramble Studio : `OUTILS\app` (lecture seule), le programme installé, `DONNEES`, `DEPOT`, `PROJET`, ses épisodes, son YouTube.
- Les trois gestes de RT pour de vrai (Fabriquer un épisode réel, Approuver, Publier) ; rien de publié.
- Écrire le registre, créer une jonction ou un raccourci hors de l'installateur de Fabrique ; `tail -f` ou un `grep` qui reste ouvert ; saisir un identifiant ou une clé.
- Un nom, un texte ou un réglage réel du projet dans un fichier suivi (tests et docs : noms factices).
- Rien « pour plus tard » hors du plan.
- En français dans les docs ; aucune fenêtre visible chez RT (tout caché, comme Bramble Studio).
