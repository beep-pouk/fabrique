"""L'API locale du noyau (django-ninja ; contrat OpenAPI tiré des schémas : /api/openapi.json). Quatre appelants, quatre droits (plan § 3.3) :
chaque route déclare son droit (@droit) ; les trois gestes (fabriquer, approuver, publier) n'existent que pour la fenêtre et l'iPhone, au clic
de RT. Aucune règle dans la fenêtre : tout ce qu'elle montre et fait passe par ici."""
import os
from functools import wraps
from typing import Literal

from django.conf import settings
from django.http import StreamingHttpResponse
from ninja import NinjaAPI
from ninja.errors import HttpError
from ninja.security import HttpBearer

from fabrique import journaux, programme
from fabrique.garde import Refus
from fabrique.moteur import file
from fabrique.noyau import cles, etat, evenements, jetons, routeur, sauvegarde, schemas, taches, versions
from fabrique.noyau.models import Session, noter
from fabrique.session.models import Fiche

GESTES = {"fabriquer", "approuver", "publier"}
DROITS = {
    "fenetre": {"voir", "sauvegarder", "restaurer", "mettre_a_jour", "cles", "arreter", "file", *GESTES},
    "iphone": {"voir", "approuver", "publier"},  # J4 : Tailscale + code à 6 chiffres
    "claude": {"voir", "importer", "deposer"},  # « Fabrique.exe commande … »
    "assistant": {"voir", "estimer", "brouillon"},  # J11 : interne au noyau
}
ACTEURS = {"fenetre": "RT", "iphone": "RT", "claude": "claude", "assistant": "assistant"}


class Jeton(HttpBearer):
    def authenticate(self, request, token):
        return jetons.APPELANTS.get(token)  # l'appelant, ou None : 401


api = NinjaAPI(title=programme.NOM, version=settings.VERSION, auth=Jeton(), docs_url=None)


def droit(nom: str):
    def deco(vue):
        @wraps(vue)
        def gardee(request, *a, **k):
            if nom not in DROITS[request.auth]:
                raise HttpError(403, f"{request.auth} : droit « {nom} » refusé")
            return vue(request, *a, **k)
        gardee.droit = nom
        return gardee
    return deco


@api.exception_handler(Refus)
def refus(request, e):
    return api.create_response(request, {"detail": str(e)}, status=409)


@api.get("/sante", response=schemas.Sante)
@droit("voir")
def sante(request):
    return {"nom": programme.titre(), "version": settings.VERSION, "mode": "simulation" if etat.simulation() else "réel", "appelant": request.auth, "pid": os.getpid()}


@api.get("/etat", response=schemas.Etat)
@droit("voir")
def lire_etat(request):
    return etat.etat()


@api.get("/sessions", response=list[schemas.Session])
@droit("voir")
def sessions(request):
    return [{"id": s.id, "nom": s.nom, "dossier": s.dossier, "essais": s.essais} for s in Session.objects.order_by("cree")]


@api.get("/sessions/{id}", response=schemas.Fiche)
@droit("voir")
def fiche(request, id: str):
    s = Session.objects.filter(id=id).first()
    if s is None:
        raise HttpError(404, f"session inconnue : {id}")
    with routeur.session(s):
        f = Fiche.objects.get(id=s.id)
    return {"id": f.id, "nom": f.nom}


@api.get("/evenements", openapi_extra={"responses": {200: {"description": "flux text/event-stream"}}})
@droit("voir")
def flux(request):
    r = StreamingHttpResponse(evenements.flux(), content_type="text/event-stream")
    r["Cache-Control"] = "no-cache"
    return r


@api.get("/journal", response=list[schemas.LigneJournal])
@droit("voir")
def journal(request):
    return journaux.recents(settings.JOURNAUX)


@api.get("/sauvegardes", response=schemas.Sauvegardes)
@droit("voir")
def sauvegardes(request):
    d = sauvegarde.dossier()
    return {"dossier": str(d), "derniere": taches.lire("sauvegarde"),
            "liste": [{"nom": z.name, "date": f"{sauvegarde.date(z):%d/%m/%Y %H:%M}", "taille_mo": round(z.stat().st_size / 1e6, 1)} for z in sauvegarde.lister(d)]}


@api.post("/sauvegardes", response=schemas.Message)
@droit("sauvegarder")
def sauvegarder(request):
    return {"message": taches.lancer("sauvegarde", ACTEURS[request.auth])}


@api.post("/sauvegardes/{nom}/restaurer", response=schemas.Message)
@droit("restaurer")
def restaurer(request, nom: str):
    if o := taches.occupe():
        raise Refus(f"la {o} est en cours : restaurer quand elle sera finie")
    message = sauvegarde.restaurer(nom)
    noter(ACTEURS[request.auth], "restauration", sauvegarde=nom)
    evenements.publier("restauration", message=message)
    return {"message": message}


@api.get("/versions", response=schemas.Versions)
@droit("voir")
def lire_versions(request):
    return versions.etat()


@api.post("/versions/mettre-a-jour", response=schemas.Message)
@droit("mettre_a_jour")
def mettre_a_jour(request):
    return {"message": versions.mettre_a_jour(ACTEURS[request.auth])}


@api.get("/cles", response=list[schemas.Cle])
@droit("voir")
def lire_cles(request):
    return cles.etat()


@api.post("/cles/{nom}", response=schemas.Message)
@droit("cles")
def enregistrer_cle(request, nom: str, corps: schemas.Valeur):
    return {"message": cles.enregistrer(nom, corps.valeur, ACTEURS[request.auth])}


@api.get("/file", response=list[schemas.TacheFile])
@droit("voir")
def lire_file(request):
    return file.lister()


@api.post("/file/{id}/{action}", response=schemas.Message)
@droit("file")
def agir_file(request, id: int, action: Literal["pause", "reprendre", "annuler"]):
    return {"message": file.agir(id, action, ACTEURS[request.auth])}


@api.post("/arreter", response=schemas.Message)
@droit("arreter")
def arreter(request):
    from fabrique.noyau import serveur

    serveur.quitter_bientot()
    return {"message": "le noyau s'arrête"}
