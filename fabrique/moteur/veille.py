"""Veille mensuelle des outils (cahier § 4 et D, reprise de la veille de Bramble) : Claude cherche chaque mois les nouveaux outils de chaque
brique et verse ce qu'il a trouvé (« commande veille <fichier.json> ») ; la liste des candidats est gardée en base et montrée dans l'écran
Outils. Un candidat n'entre jamais en service sans banc : il faut d'abord son adaptateur (une version du programme), puis un banc gagné.
Un mois sans veille : « à faire » dans etat.json, pour Claude."""
from datetime import date, timedelta

from fabrique.garde import Refus
from fabrique.moteur import outils
from fabrique.noyau.models import Candidat, Parametre, noter
from fabrique.noyau.schemas import Veille

MOIS = timedelta(days=31)
STATUTS = {"nouveau": "nouveau", "a_essayer": "à essayer", "ecarte": "écarté", "essaye": "passé au banc"}


def verser(v: Veille, acteur: str) -> str:
    """Les candidats du mois ; un outil déjà repéré pour la même brique est mis à jour, jamais doublé."""
    if inconnues := {c.brique for c in v.candidats} - outils.BRIQUES.keys():
        raise Refus(f"brique inconnue : {', '.join(sorted(inconnues))} (connues : {', '.join(outils.BRIQUES)})")
    for c in v.candidats:
        Candidat.objects.update_or_create(brique=c.brique, nom=c.nom, defaults={**c.model_dump(exclude={"brique", "nom"}), "date": date.today()})
    Parametre.ecrire("veille_derniere", date.today().isoformat())
    noter(acteur, "veille", candidats=len(v.candidats))
    return f"Veille du {date.today():%d/%m/%Y} : {len(v.candidats)} candidat(s) versé(s)."


def due(aujourdhui: date | None = None) -> bool:
    try:
        return (aujourdhui or date.today()) - date.fromisoformat(Parametre.lire("veille_derniere")) >= MOIS
    except ValueError:
        return True


def statut(pk: int, valeur: str, acteur: str) -> str:
    if valeur not in STATUTS:
        raise Refus(f"statut attendu : {', '.join(STATUTS)}")
    if not Candidat.objects.filter(pk=pk).update(statut=valeur):
        raise Refus("candidat inconnu")
    noter(acteur, "veille", candidat=pk, statut=valeur)
    return f"Candidat : {STATUTS[valeur]}."
