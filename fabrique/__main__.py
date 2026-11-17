"""« Fabrique.exe [sous-commande] » et « python -m fabrique [sous-commande] » : la seule porte d'entrée (plan § 3.2).
Sans sous-commande (ou « --fond ») : la fenêtre. Sous-commandes : noyau, executer <tâche>, moteur, commande <action>, diagnostic, migrer,
relais <journal> <…>, arreter, libre."""
import json
import sys

from fabrique import dossiers, garde, journaux, programme

SOUS_COMMANDES = ("noyau", "executer", "moteur", "commande", "diagnostic", "migrer", "relais", "arreter", "libre")
COMMANDES_CLAUDE = {"etat": "etat", "sessions": "sessions", "file": "file"}  # Claude lit ; ses essais passent par « moteur » ; importer arrive à J3


def sortie_sans_console(dossier):
    """Sans console (lanceur natif, pythonw), stdout et stderr sont None : ils vont dans journaux\\sortie.log, en UTF-8."""
    programme.SANS_CONSOLE = sys.stdout is None
    if sys.stdout is None or sys.stderr is None:
        dossier.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(dossier / "sortie.log", "a", encoding="utf-8", buffering=1)
    for flux in (sys.stdout, sys.stderr):
        if not flux.isatty() and hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)


def commande(args: list[str]) -> int:
    from fabrique.fenetre.client import Client, ErreurApi

    if not args or args[0] not in COMMANDES_CLAUDE:
        print(f"commande attendue : {', '.join(COMMANDES_CLAUDE)}")
        return 2
    try:
        print(json.dumps(Client("claude").appeler(COMMANDES_CLAUDE[args[0]]), ensure_ascii=False, indent=1))
    except (OSError, ErreurApi) as e:
        print(f"le noyau ne répond pas ou refuse : {e}")
        return 1
    return 0


def moteur(args: list[str]) -> int:
    """« moteur <recette (id ou .json)> <script.json> » : un essai de construction (Claude), toujours dans la session « Essais » : la vidéo est
    découpée en morceaux et mise dans la file ; le noyau la lance quand la carte est libre."""
    from django.core.exceptions import ObjectDoesNotExist
    from django.db import DatabaseError

    from fabrique.garde import Refus
    from fabrique.moteur import carte, execution, file, recettes
    from fabrique.noyau.models import Session

    if len(args) != 2:
        print("usage : moteur <recette (id ou fichier .json)> <script.json>")
        return 2
    try:
        recette = recettes.lire(args[0])
        with open(args[1], encoding="utf-8") as f:
            script = json.load(f)
        s = Session.objects.get(essais=True)
        v = execution.preparer(s, recette, script)
        t = file.mettre(s, v.id, v.titre, "claude")
    except (ObjectDoesNotExist, DatabaseError):
        print("refusé : les bases de Fabrique ne sont pas prêtes (lancer Fabrique une fois)")
        return 1
    except (Refus, OSError, ValueError) as e:
        print(f"refusé : {e}")
        return 1
    e = execution.estimer(s, v.id)
    raison = carte.occupee()
    print(f"« {v.titre} » (recette {recette['id']} v{recette['version']}) dans la file de la session {s.nom} : tâche {t.id}, vidéo {v.id} ; "
          f"estimé {e['secondes']:.0f} s, {execution.euros(e['cout_eur'])}.\n"
          + (f"Rien n'est lancé pour l'instant : {raison} ; elle partira quand la carte sera libre." if raison else "Le noyau la lance à son prochain tour."))
    return 0


def main(argv: list[str] | None = None) -> int:
    programme.environnement()
    args = list(sys.argv[1:] if argv is None else argv)
    role = args[0] if args and args[0] in SOUS_COMMANDES else "fenetre"
    try:
        for d in (dossiers.donnees(), dossiers.sessions(), dossiers.versions()):
            garde.verifier(d)  # avant toute écriture
    except garde.Refus as e:
        programme.SANS_CONSOLE = sys.stdout is None
        programme.boite(f"{programme.titre()} n'a pas démarré : {e}.")
        print(e, file=sys.stderr or sys.__stderr__)
        return 1
    sortie_sans_console(dossiers.donnees() / "journaux")
    if role == "relais":
        return programme.relais(*args[1:])
    journaux.configurer(dossiers.donnees() / "journaux", role)
    if role == "fenetre":
        from fabrique.fenetre import main as fenetre

        return fenetre.lancer(fond="--fond" in args)
    if role == "arreter":
        from fabrique.fenetre.client import arreter

        return 0 if arreter() else 1
    if role == "libre":  # pour l'installateur : 3 quand une tâche tourne
        from fabrique.noyau import taches

        return 3 if taches.occupe() else 0
    if role == "commande":
        return commande(args[1:])
    import django

    django.setup()
    if role == "moteur":
        return moteur(args[1:])
    if role == "noyau":
        from fabrique.noyau import serveur

        return serveur.noyau()
    if role == "migrer":
        from fabrique.noyau import bases

        copie = bases.migrer()
        print(f"Bases à jour{f' ; copies dans {copie}' if copie else ''}.")
        return 0
    if role == "executer":
        from fabrique.noyau import taches

        return taches.executer(*args[1:])
    from fabrique.noyau import diagnostic

    return diagnostic.jouer()


if __name__ == "__main__":
    sys.exit(main())
