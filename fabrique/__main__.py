"""« Fabrique.exe [sous-commande] » et « python -m fabrique [sous-commande] » : la seule porte d'entrée (plan § 3.2).
Sans sous-commande (ou « --fond ») : la fenêtre. Sous-commandes : noyau, executer <tâche>, moteur, commande <action>, diagnostic, migrer,
relais <journal> <…>, arreter, libre."""
import glob
import json
import sys
from pathlib import Path

from fabrique import dossiers, garde, journaux, programme

SOUS_COMMANDES = ("noyau", "executer", "moteur", "commande", "diagnostic", "migrer", "relais", "arreter", "libre")
COMMANDES_CLAUDE = {"etat": "etat", "sessions": "sessions", "file": "file"}  # Claude lit ; ses essais : « moteur » ; « importer-bramble » : dans le processus


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

    fichiers = {"script": 4, "veille": 2}  # « script <id de session> <code> <fichier.json> » : une version de plus, règles comprises ; « veille <fichier.json> »
    if args[:1] and args[0] in fichiers and len(args) == fichiers[args[0]]:
        try:
            with open(args[-1], encoding="utf-8") as f:
                contenu = json.load(f)
            if args[0] == "veille":
                print(Client("claude").appeler("verser_veille", contenu)["message"])
            else:
                print(Client("claude").appeler("nouvelle_version", {"contenu": contenu}, id=args[1], code=args[2])["message"])
        except (OSError, ValueError, ErreurApi) as e:
            print(f"refusé : {e}")
            return 1
        return 0
    envois = {"idee": ("ajouter_idee", lambda a: {"titre": a[1], "resume": " ".join(a[2:]), "source": "claude"}, 2),  # « idee <session> <titre> [résumé] »
              "reference": ("importer_reference", lambda a: {"fichier": a[2]}, 3),  # « reference <session> <personnage> <image> » : à valider par RT
              "nouveau-script": ("creer_script", lambda a: {"titre": a[1], "date": a[2] if len(a) > 2 else "", "format": a[3] if len(a) > 3 else ""}, 2)}  # « nouveau-script <session> <titre> [date] [format] »
    if args[:1] == ["banc"] and len(args) in (5, 6):  # « banc <session Essais> <vidéo> <brique> <outil> [juge] » : préparé de nuit, RT vote
        try:
            print(Client("claude").appeler("nouveau_banc", {"session": args[1], "video": args[2], "brique": args[3], "outil": args[4],
                                                            "juge": args[5] if len(args) == 6 else ""})["message"])
        except (OSError, ErreurApi) as e:
            print(f"refusé : {e}")
            return 1
        return 0
    if args[:1] and args[0] in envois and len(args) > envois[args[0]][2]:
        appel, corps, _ = envois[args[0]]
        try:
            print(Client("claude").appeler(appel, corps(args[1:]), id=args[1], **({"pk": args[2]} if args[0] == "reference" else {}))["message"])
        except (OSError, ErreurApi) as e:
            print(f"refusé : {e}")
            return 1
        return 0
    if not args or args[0] not in COMMANDES_CLAUDE:
        print(f"commande attendue : {', '.join(COMMANDES_CLAUDE)}, script <session> <code> <fichier.json>, idee <session> <titre> [résumé], nouveau-script <session> <titre> [AAAA-MM-JJ] [format], "
              "reference <session> <personnage> <image>, veille <fichier.json> (candidats du mois), banc <session Essais> <vidéo> <brique> <outil> [juge], "
              "importer-bramble [--pour-de-vrai], "
              "copier-essai <vidéo> <suffixe>")
        return 2
    try:
        print(json.dumps(Client("claude").appeler(COMMANDES_CLAUDE[args[0]]), ensure_ascii=False, indent=1))
    except (OSError, ErreurApi) as e:
        print(f"le noyau ne répond pas ou refuse : {e}")
        return 1
    return 0


def moteur(args: list[str]) -> int:
    """« moteur <recette (id ou .json)> <script.json> » : un essai de construction (Claude), toujours dans la session « Essais » : la vidéo est
    découpée en morceaux et mise dans la file ; le noyau la lance quand la carte est libre. Les traductions posées à côté du script
    (« histoire.fr.json ») sont fabriquées aussi, comme les langues cochées à « Fabriquer »."""
    from django.core.exceptions import ObjectDoesNotExist
    from django.db import DatabaseError

    from fabrique.garde import Refus
    from fabrique.moteur import carte, execution, file, recettes
    from fabrique.noyau import routeur
    from fabrique.noyau.models import Session
    from fabrique.session.models import Langue

    if len(args) != 2:
        print("usage : moteur <recette (id ou fichier .json)> <script.json>")
        return 2
    try:
        recette = recettes.lire(args[0])
        with open(args[1], encoding="utf-8") as f:
            script = json.load(f)
        base = Path(args[1])
        traductions = {f.name[len(base.stem) + 1:-5]: json.loads(f.read_text(encoding="utf-8")) for f in base.parent.glob(f"{glob.escape(base.stem)}.*.json")}
        s = Session.objects.get(essais=True)
        if traductions:
            with routeur.session(s):  # refusée tout de suite, pas après des heures à l'étape « langue »
                connues = set(Langue.objects.values_list("code", flat=True))
            if inconnues := sorted(set(traductions) - connues):
                raise Refus(f"{base.stem}.{inconnues[0]}.json : « {inconnues[0]} » n'est pas une langue de la session Essais")
            recette["reglages"]["langues"] = list(dict.fromkeys([script.get("language") or recette["reglages"]["langues"][0], *traductions]))
        v = execution.preparer(s, recette, script, traductions=traductions)
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


def importer(args: list[str]) -> int:
    """« commande importer-bramble [--pour-de-vrai] » (Claude) : Bramble Studio en session n° 1 ; à blanc d'abord (le rapport seulement)."""
    from django.db import DatabaseError

    from fabrique.garde import Refus
    from fabrique.session import bramble

    try:
        r = bramble.importer(pour_de_vrai="--pour-de-vrai" in args)
    except (Refus, OSError, DatabaseError) as e:
        print(f"refusé : {e}")
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["a_blanc"] or (r["copies_identiques"] and r["source_intacte"]) else 1


def copier_essai(args: list[str]) -> int:
    """« commande copier-essai <vidéo de la session Essais> <suffixe> » (Claude) : la copie à publier par RT en non répertorié (recette J4)."""
    from django.db import DatabaseError

    from fabrique.garde import Refus
    from fabrique.publication import publication

    if len(args) != 2:
        print("usage : commande copier-essai <vidéo de la session Essais> <suffixe>")
        return 2
    try:
        print(publication.copier_essai(*args))
    except (Refus, OSError, DatabaseError) as e:
        print(f"refusé : {e}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    programme.environnement()
    args = list(sys.argv[1:] if argv is None else argv)
    role = args[0] if args and args[0] in SOUS_COMMANDES else "fenetre"
    try:
        for d in (dossiers.donnees(), dossiers.sessions(), dossiers.versions(), dossiers.depot()):
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
    if role == "commande" and args[1:2] not in (["importer-bramble"], ["copier-essai"]):
        return commande(args[1:])
    import django

    django.setup()
    if role == "moteur":
        return moteur(args[1:])
    if role == "commande" and args[1] == "copier-essai":
        return copier_essai(args[2:])
    if role == "commande":
        return importer(args[2:])
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
