"""« Fabrique.exe [sous-commande] » et « python -m fabrique [sous-commande] » : la seule porte d'entrée (plan § 3.2).
Sans sous-commande (ou « --fond ») : la fenêtre. Sous-commandes : noyau, executer <tâche>, moteur, commande <action>, diagnostic, migrer,
relais <journal> <…>, arreter, libre."""
import json
import os
import sys

from fabrique import dossiers, garde, journaux, programme

SOUS_COMMANDES = ("noyau", "executer", "moteur", "commande", "diagnostic", "migrer", "relais", "arreter", "libre")
COMMANDES_CLAUDE = {"etat": "etat", "sessions": "sessions"}  # Claude lit seulement à J1 ; importer et déposer arrivent aux jalons J2 et J3


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


def main(argv: list[str] | None = None) -> int:
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
    if role == "moteur":
        print("Le moteur à recettes arrive au jalon J2 : rien n'est fabriqué.")
        return 2
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabrique.settings")
    import django

    django.setup()
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
