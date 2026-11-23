# Fabrique — démarrage d'une session de travail

*Pour une session de code ou la supervision. La supervision le recopie dans `PROJET\notes` (on n'y écrit pas d'ici).*

## Où est quoi
- **Code** : `OUTILS\fabrique` (dépôt `fabrique`, branche `main` ; plus de branches de jalon depuis J11). Tâche : `docs\TACHE.md` ; journal : `docs\REPRISE.md` (dernière section d'abord) ; questions et réponses : `docs\QUESTIONS.md` ; guide de RT : `docs\GUIDE_RT.md`.
- **Installation réelle de RT** : `<studio>\FABRIQUE\` (`programme`, `donnees`, `sessions`, `versions` = installateurs publiés). Lecture seule pour une session de code.
- **Racine des essais réels** (hors dépôt) : `OUTILS\fabrique_construction\egalite\FABRIQUE` ; histoires d'essai : `fabrique_construction\essais` ; rapports `egalite\ESSAI_*.json`, `RAPPORT.json` ; veilleur de nuit `egalite\de_nuit_chaine.py` (journal `de_nuit_chaine.log`).
- **Plan validé** : `PROJET\notes\plateforme\04_plan_technique.md` (§ 7.1 jalons, § 9 vérifications) ; cahier `03_cahier_des_charges.md` (§ 12 : les 12 critères de « fini »).

## Commandes (Python du dépôt : `OUTILS\fabrique\.venv\Scripts\python.exe`, jamais le PATH)
| Quoi | Commande |
|---|---|
| tests | `python outils_dev\tester.py` |
| recette d'un jalon | `python outils_dev\verifier.py --jalon Jn [--publier]` → `docs\VERIF_Jn_PC.md` |
| recette « fini » | `python outils_dev\recette_finale.py [--fois 10] [--publier] [--sans-construction]` → `docs\VERIF_FINI_PC.md` |
| construire, publier une version | `python outils_dev\construire.py --publier` (la version vient de `pyproject.toml` ; « Quoi de neuf » : `fabrique\nouveautes.json`) |
| essais réels (de nuit) | `essai_long.py <histoire>`, `essai_formats.py F4 <script> …`, `egalite.py --carte langue --temoin`, `essai_assistant.py` |

## Règles qui coûtent cher si on les oublie
- **La carte** : rien de lourd quand `DONNEES\etat.json` de Bramble Studio montre une tâche ou un rendu. La file de Fabrique attend la carte même pour de faux outils : une recette lancée pendant un rendu de Bramble reste rouge (« toujours pas après 300 s ») sans que le code soit en cause.
- **Variables héritées** : Fabrique retire celles d'un parent (`programme.HERITEES` : Python, `DJANGO_SETTINGS_MODULE`, `NoDefaultCurrentDirectoryInExePath` posée par Claude Code). Un nouveau piège de ce genre s'ajoute là, pas au cas par cas.
- **Veilleur de nuit** : meurt avec le PC ; le réarmer caché et détaché (`pythonw.exe de_nuit_chaine.py` dans `egalite`) ; une étape réussie (« code 0 » au journal) n'est pas refaite ; essais coupés repris là où ils en étaient.
- **Recette finale** : ses passages verts s'additionnent d'un lancement à l'autre sur le même commit, dépôt propre (`fabrique_construction\recette_finale.json`) ; un rouge remet à zéro ; carte prise : arrêt sans compter.
- **Interdits** : toucher Bramble Studio (programme, `DONNEES`, `DEPOT`, `PROJET`, ses épisodes, son YouTube) ; les trois gestes de RT (Fabriquer un épisode réel, Approuver, Publier) ; un nom, texte ou réglage réel du projet dans un fichier suivi ; saisir une clé ; écrire le registre.
- Fin de session : commit, push, REPRISE à jour, une ligne dans `OUTILS\agents\sup\fabrique\fin.txt` (CONTINUER, BLOQUE <raison>, FINI).
