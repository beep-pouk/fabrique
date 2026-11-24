# Fabrique — tâche de la session de code (refonte du 24/11/2026)

*Écrit par la supervision (discussion APP) le 24/11/2026, 17 h. Remplace la tâche J2 → J12 (copie : `docs\_old\TACHE_J2_J12.md`) et rend caduc l'« À reprendre » du 23/11 dans REPRISE. Audit qui fonde cette tâche : doc « Fabrique — audit franc et plan de reprise » ; captures et planches sur le PC : `D:\StudioKids\PROJET\notes\audit_2411\` (à regarder avant de coder l'interface).*

## Décisions de RT (24/11)

- Fabrique 0.11 « ne vaut rien, même pas un brouillon » ; Bramble Studio, « prototype bâclé », est « infiniment meilleur ». RT veut un vrai outil professionnel : **la meilleure application de ce type au monde** (au niveau des meilleures payantes, et au-dessus). Qualité d'abord.
- **« Je veux surtout que le code avance »** : moins de documents et de recettes, plus de code qui se voit à l'écran.
- Interface : **« une vraie application, comme si je l'avais téléchargée sur le store »**.
- Vidéo : qualité d'abord ; pour gagner du temps de rendu, **plus d'images plutôt que moins d'animation** ; **aucune image ne reste plus de 15 s à l'écran** (règle dure, contrôlée automatiquement).
- **Carte graphique réservée aux rendus de Bramble.** Fabrique : seulement de **petits tests courts (15 min de carte au plus chacun), carte libre, jamais pendant un rendu**. Le veilleur de nuit est désarmé (`fabrique_construction\egalite\de_nuit_chaine.py` sort tout de suite) : ne jamais le réarmer ; aucun essai long ; plus de `recette_finale --fois 10` ni d'égalités de nuit.

## Garder, jeter, geler

- **Garder le socle** : noyau Django et son API locale, file unique qui cède toujours à Bramble, briques et recettes, sessions et données (scripts importés, univers), sauvegardes, mises à jour, installateur, réparation d'un programme abîmé, publication YouTube (une chaîne par langue), paquets réseaux, mode simulation, tests.
- **Jeter** toute l'interface actuelle (`fabrique\fenetre\Main.qml` et son client) et tout texte de développeur montré à RT (codes, « [MOTION] », « J6 », noms de réglages, chemins à taper). « Égalité avec Bramble » n'est plus un but : Fabrique doit faire mieux.
- **Geler F2 → F6** (compilation, courte verticale, voix off, chanson, présentateur) : cachés dans l'interface, code gardé, aucun travail dessus. Assistant, Banc, Statistiques : gardés dans le noyau, hors des écrans principaux pour l'instant.

## Étape 1 — Nouvelle interface (version 0.12)

- **Une vraie application de bureau** : fenêtre à elle (icône, barre de titre soignée, plein écran), installateur et mises à jour actuels ; aucun navigateur, adresse, terminal ni fenêtre noire visibles ; pas de menu « clic droit » de navigateur ni de sélection de texte parasite ; pas d'écran blanc au démarrage ; démarrage rapide ; hors ligne.
- **Technique (choix de la supervision)** : interface dessinée avec les outils du web — React + TypeScript + Vite, composants libres (Radix / shadcn/ui, icônes Lucide ; licences MIT/ISC, crédit dans `NOTICE.md`) — affichée dans une fenêtre **WebView2** (comme Bramble Studio ; le moteur web de Qt ne lit pas le H.264). Elle parle au noyau par l'API locale existante. Node seulement pour construire, installé dans `D:\StudioKids\OUTILS` ; le programme livré n'embarque que les fichiers construits.
- **Niveau visé** : au-dessus de Bramble Studio, au niveau de LTX Studio, CapCut ou DaVinci Resolve : thème sombre de studio, système de design (couleurs, typographie, espacements, composants), **des images partout** (vignettes d'épisodes, planche illustrée, fiches de personnages en images, image du plan en cours dans la file), aucun jargon, mise en page qui remplit l'écran agrandi, raccourcis clavier, animations discrètes. Charger la compétence de design (frontend-design) avant de dessiner.
- **Écrans** : Accueil (ce qui attend RT, en images) ; Session (épisodes en vignettes) ; Épisode (planche illustrée plan par plan : image, durée, texte dit, personnages ; lecteur vidéo) ; Personnages (fiches en images, voix à écouter) ; File (rendu en cours, image, temps restant) ; Système (socle existant, sans jargon).
- **Vraies données dès cette étape** : scripts déjà importés et images des rendus de Bramble (`D:\StudioKids\PROJET\rendus\…`, lecture seule) pour remplir planche et vignettes.
- **Accepté quand** : la supervision voit à l'écran, fenêtre agrandie, une application qu'on croirait achetée : aucune page vide ou texte de développeur, s1e01 en planche illustrée, personnages en images ; tests du socle verts.

## Plan complet (une version publiée à chaque étape, dans l'ordre où RT la verra)

1. Nouvelle interface sur les vraies données (0.12).
2. Première scène vraiment animée : 30 à 40 s de s1e01, personnages qui bougent, plans de 4 à 8 s, à côté de la même scène par Bramble, comparables dans Fabrique.
3. Animatique et lecteur : l'épisode entier en images fixes + voix + musique (rendu sur le processeur, quelques minutes), repères des plans, notes à la seconde.
4. Mise en scène : aucune image plus de 15 s, plans de 4 à 8 s, valeurs de plan variées, caméra, action qui suit le texte ; lèvres de Bramble.
5. Plan par plan : plusieurs essais par plan, refaire avec une consigne, comparer, garder le meilleur.
6. Personnages fidèles (fiches validées, contrôle sur chaque plan) et son fini (ambiance, niveau sonore constant, sous-titres).
7. Épisode d'essai de 3 min de bout en bout, fabriqué par morceaux de 15 min de carte ; langues qui reprennent images et animation sans rien refaire ; publication (socle).
8. Bascule : s1e01 complet seulement sur le clic « Fabriquer » de RT.

Étapes 1 et 2 menées en parallèle (un sous-agent interface, un sous-agent vidéo). **Si l'étape 2 plafonne** (moins de 8/10 au juge, visages ou pattes qui fondent) : l'écrire dans QUESTIONS (la supervision proposera à RT un banc contre un modèle en ligne payant) et garder les calques 2,5D pour les plans calmes, toujours 15 s au plus par image.

## Étape 2 — point de départ vidéo

- Outils déjà sur le PC, gagnants au banc : images Qwen-Image (+ Edit) ; animation **LTX-2.5 dev BF16 + LoRA distillée** dans ComfyUI (réglages et pièges : `OUTILS\production\regles\MANUEL_LTX.md`, `REGLES_VIDEO.md` ; V-21 : étage 1 à 960×544, sortie 1920×1088, ≈ 330 s par plan de 5 s) ; voix Chatterbox ; musique ACE-Step ; lèvres de Bramble (moteur actuel).
- Échec d'octobre (≈ 6/10) : une seule image → 30 s inventées. **À essayer** : plans de 4 à 8 s ; multi-plans natif de LTX-2.5 (personnages et décor gardés d'un plan à l'autre) ; première image fixée (dernière si utile) ; au plus 2 personnages qui bougent ; consigne de mouvement précise ; son de LTX coupé (nos voix et musique).
- Scène d'essai : une scène de s1e01 de 30 à 40 s, avec ses images existantes (rendus de Bramble, lecture seule) ; sorties hors dépôt dans `OUTILS\fabrique_construction\essais_anim\`.
- Juger : juge à l'aveugle « aspect dessin animé » (Gemini par la supervision, ou Qwen-VL local carte libre), mesures (durée moyenne des plans, part de mouvement, fidélité des personnages), vidéo côte à côte dans Fabrique pour RT.
- Avant chaque test : `D:\StudioKids\DONNEES\etat.json` sans tâche ni rendu, `nvidia-smi` sous 2 Go utilisés ; s'arrêter dès que Bramble démarre ; 15 min de carte au plus par test.

## Façon de travailler

- **Le code avance** : petits pas, commits fréquents, tests rapides du socle gardés verts ; plus de recettes interminables ni de longs rapports.
- Chaque étape finie : vue à l'écran par toi (capture de la fenêtre), relecture à froid courte par un sous-agent, version publiée dans `D:\StudioKids\FABRIQUE\versions`, puis une ligne « 0.x prête — quoi regarder : … » dans QUESTIONS (la supervision installe et montre à RT).
- Une vraie question : une ligne datée dans QUESTIONS (QCM, option recommandée en premier) ; avancer sur le reste en attendant.
- Fin de tour : commit, push, tête de REPRISE à jour (5 lignes au plus), puis `fin.txt` (CONTINUER / BLOQUE <raison> / FINI).
- S'inspirer du libre (règle du 17/11 : bibliothèque > code copié > idée ; licences permettant l'usage commercial ; crédit dans `NOTICE.md`).

## Interdits (inchangés)

- Toucher Bramble Studio : `OUTILS\app` (lecture seule), le programme installé, `DONNEES`, `DEPOT`, `PROJET`, ses épisodes, son YouTube.
- Les trois gestes de RT pour de vrai (Fabriquer un épisode réel, Approuver, Publier) ; rien de publié.
- Écrire le registre, créer une jonction ou un raccourci hors de l'installateur de Fabrique ; `tail -f` ou un `grep` qui reste ouvert ; saisir un identifiant ou une clé.
- Un nom, un texte ou un réglage réel du projet dans un fichier suivi (tests et docs : noms factices).
- Rien « pour plus tard » hors du plan.
- En français dans les docs ; aucune fenêtre visible chez RT (tout caché, comme Bramble Studio).
