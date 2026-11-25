"""L'API locale du noyau (django-ninja ; contrat OpenAPI tiré des schémas : /api/openapi.json). Quatre appelants, quatre droits (plan § 3.3) :
chaque route déclare son droit (@droit) ; les trois gestes (fabriquer, approuver, publier) n'existent que pour la fenêtre et l'iPhone, au clic
de RT. Aucune règle dans la fenêtre : tout ce qu'elle montre et fait passe par ici."""
import logging
import os
import shutil
import threading
from functools import wraps
from pathlib import Path
from typing import Literal

from django.conf import settings
from django.db import DatabaseError
from django.http import FileResponse, StreamingHttpResponse
from django.utils import timezone
from ninja import NinjaAPI
from ninja.errors import HttpError
from ninja.security import APIKeyCookie, HttpBearer

from fabrique import journaux, programme
from fabrique.garde import Refus
from fabrique.moteur import file
from fabrique.noyau import cles, echange, etat, evenements, interface, jetons, routeur, sauvegarde, schemas, taches, telephone, versions
from fabrique.noyau.models import Session, noter
from fabrique.session import models as m
from fabrique.session.models import Fiche

log = logging.getLogger(__name__)
GESTES = {"fabriquer", "approuver", "publier"}
DROITS = {
    "fenetre": {"voir", "sauvegarder", "restaurer", "mettre_a_jour", "cles", "arreter", "file", "refaire", "importer", "demander", "destinations", "relier",
                "retoucher", "paquets", "telephone", "sessions", "mode", "univers", "outils", "bancs", "voter", "temps", "assistant", "animatique", *GESTES},
    "iphone": {"voir", "destinations", "approuver", "publier", "paquets"},  # J4 : Tailscale + code à 6 chiffres
    "claude": {"voir", "importer", "deposer", "veille", "bancs"},  # « Fabrique.exe commande … » ; un banc : session « Essais » seulement (file.mettre)
    "assistant": {"voir", "estimer", "brouillon"},  # J11 : interne au noyau
}
ACTEURS = {"fenetre": "RT", "iphone": "RT", "claude": "claude", "assistant": "assistant"}


class Jeton(HttpBearer):
    def authenticate(self, request, token):
        return jetons.APPELANTS.get(token)  # l'appelant, ou None : 401


class Iphone(APIKeyCookie):
    """Le cookie de l'appareil (noyau/telephone.py) ; une requête qui change quelque chose porte aussi l'en-tête X-Fabrique."""
    param_name = telephone.COOKIE

    def authenticate(self, request, key):
        if key:
            telephone.hote(request)
        if telephone.reconnu(key) and (request.method in ("GET", "HEAD") or request.headers.get(telephone.ENTETE) == "iphone"):
            return "iphone"
        return None


class Fenetre(APIKeyCookie):
    """L'interface de la fenêtre (noyau/interface.py) : le jeton de la fenêtre en cookie, l'en-tête X-Fabrique pour une écriture."""
    param_name = interface.COOKIE

    def authenticate(self, request, key):
        return interface.appelant(request)


api = NinjaAPI(title=programme.NOM, version=settings.VERSION, auth=[Jeton(), Iphone(csrf=False), Fenetre(csrf=False)], docs_url=None)


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
    """Les sessions et, pour le mur de l'Accueil, la carte de chacune (une base illisible ne cache pas les autres)."""
    from fabrique.session import calendrier

    liste = []
    for s in Session.objects.order_by("cree"):
        d = {"id": s.id, "nom": s.nom, "dossier": s.dossier, "essais": s.essais, "pause": s.pause,
             "archivee": f"{timezone.localtime(s.archivee):%d/%m/%Y}" if s.archivee else ""}
        try:
            d |= calendrier.carte(s)
        except Exception:  # noqa: BLE001
            log.exception("carte de la session %s", s.nom)
        liste.append(d)
    return liste


@api.post("/sessions", response=schemas.SessionCreee)
@droit("sessions")
def nouvelle_session(request, corps: schemas.NouvelleSession):
    """Nouvelle session pas à pas, étape 1 : la session (de zéro ou d'un modèle), en pause jusqu'à la fin de l'assistant."""
    from fabrique.session import reglages

    s = reglages.creer(corps.nom, corps.langues, corps.public, corps.promesse, corps.modele, ACTEURS[request.auth])
    return {"message": f"Session « {s.nom} » créée (en pause jusqu'à la fin de l'assistant).", "id": s.id}


@api.get("/formats", response=list[schemas.Format])
@droit("voir")
def formats(request):
    from fabrique.session import reglages

    return reglages.catalogue()


@api.post("/estimation", response=schemas.Estimation)
@droit("estimer")
def estimer(request, corps: schemas.Estimer):
    """J11, assistant : n vidéos d'un format, d'après les médianes des vidéos finies de ce format dans toutes les sessions (temps des morceaux,
    carte, dépenses) ; rien n'est créé."""
    from statistics import median

    from fabrique.noyau.models import Depense
    from fabrique.publication import rendement
    from fabrique.session import reglages

    faites = []
    for s in Session.objects.all():
        try:
            with routeur.session(s):
                if s.essais:  # essais de construction : jamais une durée de vraie vidéo
                    continue
                for v in m.Video.objects.filter(recette__id=corps.format, essai=False).exclude(nom__endswith=f"-{reglages.PILOTE}").prefetch_related("morceaux"):
                    ms = list(v.morceaux.all())
                    if ms and all(x.etat == "fini" for x in ms):
                        faites.append((sum(x.secondes or 0 for x in ms) / 3600, rendement.carte_s(v) / 3600,
                                       sum(d.estime_eur if d.reel_eur is None else d.reel_eur for d in Depense.objects.filter(video_id=v.id))))
        except DatabaseError:  # une base illisible : les autres comptent
            continue
    n = corps.videos
    f, c, e = ([round(n * median(x[i] for x in faites), 2) for i in range(3)] if faites else (None, None, None))
    texte = (f"{f:g} h de fabrication, dont {c:g} h de carte, {e:.2f} € (médianes de {len(faites)} vidéo(s) {corps.format})".replace(".", ",")
             if faites else f"pas encore de vidéo {corps.format} finie : durée et coût inconnus")
    return {"format": corps.format, "videos": n, "connues": len(faites), "fabrication_h": f, "carte_h": c, "cout_eur": e, "texte": texte}


@api.post("/brouillons/session", response=schemas.SessionCreee)
@droit("brouillon")
def brouillon_session(request, corps: schemas.NouvelleSession):
    """J11, assistant (après l'accord de RT) : une nouvelle session en pause à l'étape 1 ; RT la termine pas à pas."""
    from fabrique.session import reglages

    s = reglages.creer(corps.nom, corps.langues, corps.public, corps.promesse, "", ACTEURS[request.auth])
    return {"message": f"Brouillon de session « {s.nom} » (en pause : à terminer dans Sessions).", "id": s.id}


@api.post("/sessions/{id}/brouillons/video", response=schemas.Message)
@droit("brouillon")
def brouillon_video(request, id: str, corps: schemas.NouvelleIdee):
    """J11, assistant (après l'accord de RT) : une idée au calendrier de la session ; RT en fait un script, puis la fabrique."""
    from fabrique.session import calendrier

    if (s := session_(id)).essais or s.archivee:
        raise HttpError(409, f"« {s.nom} » est la session Essais ou est rangée : choisir une session en service")
    return {"message": calendrier.ajouter_idee(s, corps.titre, corps.resume, "assistant", ACTEURS[request.auth])}


@api.post("/assistant", response=schemas.ReponseAssistant)
@droit("assistant")
def assistant_(request, corps: schemas.DemandeAssistant):
    """J11 : le panneau de l'assistant (fenêtre seulement) ; un brouillon seulement avec « accord »."""
    from fabrique.noyau import assistant

    return assistant.demander(corps.demande, corps.historique, corps.accord)


@api.get("/modeles", response=list[schemas.Modele])
@droit("voir")
def modeles(request):
    return echange.modeles()


@api.get("/calendrier", response=list[schemas.ElementCalendrier])
@droit("voir")
def calendrier_(request, debut: str = "", fin: str = "", session: str = ""):
    """Le calendrier d'une session, ou de toutes (vue d'ensemble : sessions en service, sans « Essais »), entre deux dates (AAAA-MM-JJ)."""
    from datetime import date

    from fabrique.session import calendrier

    try:
        d, f = (date.fromisoformat(x) if x else None for x in (debut, fin))
    except ValueError:
        raise HttpError(400, "dates attendues en AAAA-MM-JJ") from None
    prets, lus = calendrier.prets_vers(), []
    for s in [session_(session)] if session else Session.objects.filter(essais=False, archivee__isnull=True).order_by("cree"):
        try:  # une base illisible ne cache pas les autres sessions
            lus += calendrier.lire(s, d, f, prets)
        except Exception:  # noqa: BLE001
            log.exception("calendrier de la session %s", s.nom)
    return lus


@api.post("/sessions/{id}/scripts", response=schemas.ScriptCree)
@droit("importer")
def creer_script(request, id: str, corps: schemas.NouveauScript):
    """Un script neuf, tiré d'une idée ou non, daté ou non (fenêtre ; Claude, qui l'écrit ensuite)."""
    from fabrique.session import calendrier

    code = calendrier.creer_script(session_(id), corps.titre, jour_(corps.date), corps.idee, ACTEURS[request.auth], corps.format)
    return {"message": f"Script {code} créé : « Demander à Claude » l'écrit.", "code": code}


@api.post("/sessions/{id}/scripts/{code}/dater", response=schemas.Message)
@droit("sessions")
def dater_script(request, id: str, code: str, corps: schemas.Date):
    from fabrique.session import calendrier

    return {"message": calendrier.dater_script(session_(id), code, jour_(corps.date), ACTEURS[request.auth])}


def jour_(texte: str):
    from datetime import date

    try:
        return date.fromisoformat(texte.strip()) if texte.strip() else None
    except ValueError:
        raise HttpError(400, f"date attendue en AAAA-MM-JJ : « {texte} »") from None


@api.post("/sessions/importer", response=schemas.Message)
@droit("sessions")
def importer_session(request, corps: schemas.Importer):
    """Fenêtre : une session exportée (.fabrique), ou une nouvelle session partie d'un modèle (son nom de fichier)."""
    modele = settings.RACINE / "modeles" / corps.fichier
    fichier = modele if Path(corps.fichier).name == corps.fichier and modele.is_file() else Path(corps.fichier)
    s = echange.importer(fichier, corps.nom, ACTEURS[request.auth])
    return {"message": f"Session « {s.nom} » créée depuis {fichier.name}."}


@api.get("/sessions/{id}", response=schemas.Fiche)
@droit("voir")
def fiche(request, id: str):
    s = session_(id)
    with routeur.session(s):
        f = Fiche.objects.get(id=s.id)
    return {"id": f.id, "nom": f.nom}


def session_(id: str) -> Session:
    s = Session.objects.filter(id=id).first()
    if s is None:
        raise HttpError(404, f"session inconnue : {id}")
    return s


@api.get("/sessions/{id}/scripts", response=list[schemas.Script])
@droit("voir")
def scripts(request, id: str):
    with routeur.session(session_(id)):
        return [{"code": sc.code, "titre": sc.titre, "statut": sc.statut, "date_prevue": str(sc.date_prevue or ""), "versions": sc.versions.count(),
                 "validee": bool((v := sc.versions.order_by("-numero").first()) and v.validee), "format": sc.details.get("format", ""),
                 "vignette": t if isinstance(t := (v.contenu if v else {}).get("thumbnail_scene"), int) else 0, "personnages": list((v.contenu if v else {}).get("cast") or {})}
                for sc in m.Script.objects.order_by("date_prevue", "code")]


@api.get("/sessions/{id}/scripts/{code}", response=schemas.ScriptDetail)
@droit("voir")
def script_(request, id: str, code: str):
    """Un script : ses versions, la plus récente (contenu, règles), sa planche (les plans qui seront fabriqués) et l'estimation de sa
    fabrication au format de la session (durée, coût), à relire avant « Fabriquer »."""
    from fabrique.moteur import execution, recettes
    from fabrique.moteur.f1 import refaire as f1
    from fabrique.session import calendrier

    s = session_(id)
    with routeur.session(s):
        sc = m.Script.objects.filter(code=code).first()
        if sc is None:
            raise HttpError(404, f"script inconnu : {code}")
        versions = list(sc.versions.order_by("-numero"))
        traductions = sorted(t.code.split(".", 1)[1] for t in m.Script.objects.filter(code__startswith=f"{code}.") if t.versions.exists())
    contenu = versions[0].contenu if versions else {}
    forme = calendrier.format_du_script(s, code)
    try:
        recette = recettes.lire(forme)
        estimation = execution.estimer_script(s, recette, contenu)
    except Refus as e:
        recette, estimation = {}, {"secondes": 0, "cout_eur": 0, "carte_go": 0, "refus": str(e)}
    plans = f1.planche(contenu) if recette.get("script") == "scenario-bramble" else []
    ids = [contenu.get("intro"), *contenu.get("videos", []), contenu.get("source")] if recette.get("script") in ("compilation", "extrait") else []
    with routeur.session(s):
        titres = dict(m.Video.objects.filter(id__in=[i for i in ids if i]).values_list("id", "titre"))
    citees = [{"id": i, "titre": titres.get(i, "vidéo inconnue")} for i in ids if i]
    return {"code": sc.code, "titre": sc.titre, "statut": sc.statut, "date_prevue": str(sc.date_prevue or ""),
            "versions": [{"numero": v.numero, "auteur": v.auteur, "date": v.date.isoformat(timespec="minutes"), "validee": v.validee} for v in versions],
            "contenu": contenu, "regles": versions[0].regles if versions else {}, "plans": plans, "estimation": estimation, "traductions": traductions,
            "citees": citees}


@api.get("/sessions/{id}/scripts/{code}/bramble", response=schemas.RendusBramble)
@droit("voir")
def rendus_bramble(request, id: str, code: str, langue: str = "en"):
    """Ce que Bramble Studio a rendu pour ce script (images des plans, vidéos finies, voix de `langue` par scène), lu chez lui sans rien toucher."""
    from fabrique.session import bramble

    session_(id)
    return bramble.rendus(code, langue)


@api.get("/sessions/{id}/scripts/{code}/animatique", response=schemas.Animatique)
@droit("voir")
def animatique_(request, id: str, code: str, langue: str = "en"):
    """L'animatique de ce script en `langue` (moteur/animatique.py) : où en est son montage, sa vidéo, les repères des plans, les notes de RT."""
    from fabrique.moteur import animatique

    s = session_(id)
    animatique.contenu_du_script(s, code)  # un script connu : son code entre dans des noms de fichiers
    return animatique.etat(s, code, animatique.verifier_langue(langue))


@api.post("/sessions/{id}/scripts/{code}/animatique", response=schemas.Message)
@droit("animatique")
def monter_animatique(request, id: str, code: str, langue: str = "en"):
    """Monte l'animatique (images fixes de Bramble, voix de `langue`, musique) sur le processeur, en tâche détachée : quelques minutes."""
    from fabrique.moteur import animatique

    s = session_(id)
    animatique.contenu_du_script(s, code)
    return {"message": animatique.lancer(s, code, animatique.verifier_langue(langue), ACTEURS[request.auth])}


@api.post("/sessions/{id}/scripts/{code}/animatique/notes", response=schemas.Message)
@droit("animatique")
def noter_animatique(request, id: str, code: str, note: schemas.NoteAnimatique):
    from fabrique.moteur import animatique

    s = session_(id)
    animatique.contenu_du_script(s, code)
    animatique.noter_a(s, code, note.t, note.texte, note.langue)
    return {"message": "Note ajoutée."}


@api.post("/sessions/{id}/scripts/{code}/animatique/notes/{note}/retirer", response=schemas.Message)
@droit("animatique")
def retirer_note_animatique(request, id: str, code: str, note: str):
    from fabrique.moteur import animatique

    s = session_(id)
    animatique.contenu_du_script(s, code)
    animatique.retirer_note(s, code, note)
    return {"message": "Note retirée."}


@api.get("/sessions/{id}/scripts/{code}/comparaisons", response=list[schemas.Comparaison])
@droit("voir")
def comparaisons(request, id: str, code: str):
    """Les essais d'animation de ce script (étape 2), à côté de la même scène par Bramble Studio, le plus récent d'abord."""
    from fabrique.moteur import animatique, comparaison

    s = session_(id)
    animatique.contenu_du_script(s, code)
    return comparaison.lister(s, code)


@api.get("/bramble/en-cours", response=schemas.BrambleEnCours)
@droit("voir")
def bramble_en_cours(request):
    """Ce que Bramble Studio fabrique en ce moment, pour l'écran Fabrication (il a la carte : Fabrique attend son tour)."""
    from fabrique.session import bramble

    e = bramble.en_cours()
    return {"actif": bool(e), **(e or {})}


@api.get("/fichier", openapi_extra={"responses": {200: {"description": "le fichier"}}})
@droit("voir")
def fichier(request, chemin: str, largeur: int = 0):
    """Une image (réduite à `largeur`), un son ou une vidéo d'une session ou des rendus de Bramble ; rien d'autre sur le disque."""
    from fabrique.session import bramble

    f = Path(chemin).resolve()
    if not any(r and f.is_relative_to(r.resolve()) for r in (settings.SESSIONS, bramble.rendus_bramble())):
        raise HttpError(403, "fichier hors des sessions et des rendus")
    if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        return interface.image(f, largeur or None)
    return interface.media(request, f)


@api.post("/sessions/{id}/scripts/{code}/controler", response=schemas.Regles)
@droit("voir")
def controler(request, id: str, code: str, corps: schemas.Contenu):
    """Les règles de l'univers sur un script en cours d'écriture (rien n'est enregistré)."""
    from fabrique.session import regles

    return regles.controler(session_(id), corps.contenu, code)


@api.post("/sessions/{id}/scripts/{code}/versions", response=schemas.Message)
@droit("importer")
def nouvelle_version(request, id: str, code: str, corps: schemas.Contenu):
    """Une version de plus du script (rien d'existant n'est touché), avec le résultat des règles ; une erreur des règles bloque « Fabriquer »."""
    from fabrique.session import regles

    return {"message": regles.enregistrer(session_(id), code, corps.contenu, ACTEURS[request.auth])}


@api.post("/sessions/{id}/scripts/{code}/demander", response=schemas.Message)
@droit("demander")
def demander(request, id: str, code: str, corps: schemas.Demande):
    """RT demande à Claude d'écrire une nouvelle version du script, ou de le traduire : une demande dans le dépôt, que la discussion prend."""
    from fabrique.noyau import depot

    return {"message": depot.demander(session_(id), code, corps.quoi, corps.langue, ACTEURS[request.auth])}


@api.get("/sessions/{id}/univers", response=schemas.Univers)
@droit("voir")
def univers(request, id: str):
    from fabrique.session import univers as u

    return u.lire(session_(id))


@api.get("/sessions/{id}/historique", response=list[schemas.Changement])
@droit("voir")
def historique(request, id: str):
    from fabrique.session import univers as u

    return u.historique(session_(id))


@api.post("/sessions/{id}/univers/ajouter", response=schemas.Message)
@droit("univers")
def ajouter_element(request, id: str, corps: schemas.Element):
    from fabrique.session import univers as u

    return {"message": u.ajouter(session_(id), corps.type, corps.nom, corps.description, ACTEURS[request.auth], corps.role)}


@api.post("/sessions/{id}/univers/style", response=schemas.Message)
@droit("univers")
def ecrire_style(request, id: str, corps: schemas.Valeur):
    from fabrique.session import univers as u

    return {"message": u.ecrire_style(session_(id), corps.valeur, ACTEURS[request.auth])}


@api.post("/sessions/{id}/univers/{type}/{pk}/droits", response=schemas.Message)
@droit("univers")
def ecrire_droits(request, id: str, type: str, pk: int, corps: schemas.Droits):
    from fabrique.session import univers as u

    return {"message": u.ecrire_droits(session_(id), type, pk, corps.licence, corps.credit, ACTEURS[request.auth])}


@api.post("/sessions/{id}/univers/{type}/{pk}/partager", response=schemas.Message)
@droit("univers")
def partager(request, id: str, type: str, pk: int, corps: schemas.Partage):
    """Au clic de RT seulement : rien ne passe d'une session à l'autre sans qu'il le demande."""
    from fabrique.session import univers as u

    return {"message": u.partager(session_(id), type, pk, session_(corps.vers), ACTEURS[request.auth])}


@api.post("/sessions/{id}/references/{pk}/valider", response=schemas.Message)
@droit("univers")
def valider_reference(request, id: str, pk: int, corps: schemas.Validation):
    from fabrique.session import univers as u

    return {"message": u.valider(session_(id), pk, corps.validee, ACTEURS[request.auth])}


@api.post("/sessions/{id}/personnages/{pk}/references", response=schemas.Message)
@droit("importer")
def importer_reference(request, id: str, pk: int, corps: schemas.ImportReference):
    """Glisser-déposer dans la fenêtre, ou Claude : une image copiée dans l'univers, à valider par RT."""
    from fabrique.session import univers as u

    return {"message": u.importer_reference(session_(id), pk, corps.fichier, ACTEURS[request.auth], corps.vue)}


@api.get("/sessions/{id}/reglages", response=schemas.ReglagesSession)
@droit("voir")
def lire_reglages(request, id: str):
    from fabrique.session import reglages

    s = session_(id)
    return reglages.lire(s) | {"manque": reglages.manque(s)}


@api.post("/sessions/{id}/reglages", response=schemas.Message)
@droit("sessions")
def ecrire_reglages(request, id: str, corps: schemas.ChangerReglages):
    from fabrique.session import reglages

    s, champs = session_(id), corps.model_dump(exclude_unset=True)
    if (langues := champs.pop("langues", None)) is not None:
        reglages.controler_langues(langues)  # avant d'écrire quoi que ce soit
    message = reglages.ecrire(s, champs, ACTEURS[request.auth])
    if langues is not None:
        reglages.poser_langues(s, langues)
    return {"message": message}


@api.post("/sessions/{id}/finir", response=schemas.Message)
@droit("sessions")
def finir_session(request, id: str):
    from fabrique.session import reglages

    return {"message": reglages.finir(session_(id), ACTEURS[request.auth])}


@api.post("/sessions/{id}/pilote", response=schemas.Message)
@droit("sessions")
def pilote(request, id: str):
    """Étape 7 de la nouvelle session : la vidéo pilote en simulation (faux outils, rien ne sort du PC)."""
    from fabrique.session import reglages

    return {"message": reglages.pilote(session_(id), ACTEURS[request.auth])}


@api.get("/sessions/{id}/idees", response=list[schemas.Idee])
@droit("voir")
def idees(request, id: str):
    from fabrique.session import calendrier

    return calendrier.idees(session_(id))


@api.post("/sessions/{id}/idees", response=schemas.Message)
@droit("importer")
def ajouter_idee(request, id: str, corps: schemas.NouvelleIdee):
    """Ajout rapide (fenêtre) ou import par Claude."""
    from fabrique.session import calendrier

    return {"message": calendrier.ajouter_idee(session_(id), corps.titre, corps.resume, corps.source, ACTEURS[request.auth])}


@api.get("/sessions/{id}/videos", response=list[schemas.VideoListe])
@droit("voir")
def videos(request, id: str):
    with routeur.session(session_(id)):
        return [{"id": v.id, "titre": v.titre, "nom": v.nom, "recette": f"{v.recette.get('id')} v{v.recette.get('version')}",
                 "progression": f"{v.morceaux.filter(etat='fini').count()}/{v.morceaux.count()}", "erreurs": v.morceaux.filter(etat="erreur").count()}
                for v in m.Video.objects.order_by("-cree")]


@api.post("/sessions/{id}/scripts/{code}/fabriquer", response=schemas.Message)
@droit("fabriquer")
def fabriquer(request, id: str, code: str):
    """Geste de RT : la vidéo du script (dernière version) découpée selon le format de la session (réglage « format », F1 par défaut), dans
    les langues choisies avant le lancement (chacune a sa traduction : script « code.langue »), mise dans la file. La version fabriquée est
    celle que RT a relue (« version » : refus si une autre est arrivée depuis) ; les règles sont rejouées au clic ; jamais deux fois le même
    script en même temps."""
    from fabrique.moteur import execution, file, recettes
    from fabrique.noyau.models import Tache
    from fabrique.session import regles

    from fabrique.session import reglages

    s = session_(id)
    reglages.garde_fou(s)
    from fabrique.session import calendrier

    forme = calendrier.format_du_script(s, code)
    cite_des_videos = recettes.lire(forme)["script"] in ("compilation", "extrait")
    try:  # corps facultatif {"langues": [...]} : sans corps, la langue du script seule
        corps = request.body if request.content_type == "application/json" and request.body else b"{}"
        demande = schemas.Langues.model_validate_json(corps)
        choisies = list(dict.fromkeys(demande.langues))
    except ValueError as e:
        raise HttpError(400, f"langues illisibles : {e}") from None
    with routeur.session(s):
        sc = m.Script.objects.filter(code=code).first()
        if sc is None:
            raise HttpError(404, f"script inconnu : {code}")
        if not (v := sc.versions.order_by("-numero").first()):
            raise Refus(f"le script {code} n'a aucune version à fabriquer")
        if demande.version is not None and demande.version != v.numero:
            raise Refus(f"une version {v.numero} du script {code} est arrivée depuis la {demande.version} relue : la relire avant de fabriquer")
        date = (sc.date_prevue or v.date.date()).isoformat()
        traductions = {}
        for langue in choisies:
            if cite_des_videos:  # une compilation, un extrait : les vidéos citées existent dans la langue (contrôlé à la préparation), rien à traduire
                continue
            t = m.Script.objects.filter(code=f"{code}.{langue}").first()
            if t is None or not (tv := t.versions.order_by("-numero").first()):
                raise Refus(f"pas de traduction en « {langue} » pour {code} : la demander à Claude d'abord")
            traductions[langue] = tv.contenu
    if erreurs := regles.controler(s, v.contenu, code)["erreurs"]:
        raise Refus(f"le script {code} a {len(erreurs)} erreur(s) des règles de l'univers (version {v.numero}) : à corriger avant de fabriquer")
    nom = f"{date}-{sc.code}"
    with routeur.session(s):
        en_cours = set(m.Video.objects.filter(nom=nom).values_list("id", flat=True))
    if Tache.objects.filter(session_id=s.id, video_id__in=en_cours, etat__in=("attente", "en_cours", "pause")).exists():
        raise Refus(f"« {sc.titre} » est déjà dans la file")
    recette = recettes.lire(forme)
    base = v.contenu.get("language") or sc.langue or recette["reglages"]["langues"][0]
    recette["reglages"]["langues"] = list(dict.fromkeys([base, *choisies]))
    video = execution.preparer(s, recette, v.contenu, nom=nom, traductions=traductions)
    t = file.mettre(s, video.id, video.titre, ACTEURS[request.auth])
    e = execution.estimer(s, video.id)
    return {"message": f"« {video.titre} » dans la file (tâche {t.id}) : environ {round(e['secondes'] / 3600, 1)} h".replace(".", ",") + f", {execution.euros(e['cout_eur'])}"}


@api.get("/sessions/{id}/videos/{video}", response=schemas.VideoDetail)
@droit("voir")
def video_(request, id: str, video: str):
    """Une vidéo : ses étapes (morceaux finis, en erreur, outil, durée), ses plans (ce qui se coche : F1), son script."""
    from fabrique.moteur.f1 import refaire as f1

    with routeur.session(session_(id)):
        v = m.Video.objects.filter(id=video).first()
        if v is None:
            raise HttpError(404, f"vidéo inconnue : {video}")
        etapes = []
        for e in v.recette.get("etapes", []):
            ms = list(v.morceaux.filter(etape=e["id"]))
            etapes.append({"id": e["id"], "brique": e["brique"], "finis": sum(x.etat == "fini" for x in ms), "total": len(ms),
                           "erreur": next((x.message for x in ms if x.etat == "erreur"), ""), "outils": sorted({x.outil for x in ms}),
                           "secondes": round(sum(x.secondes or 0 for x in ms), 1)})
        plans = f1.planche(v.script) if v.recette.get("script") == "scenario-bramble" else []
        return {"id": v.id, "titre": v.titre, "nom": v.nom, "recette": f"{v.recette.get('id')} v{v.recette.get('version')}", "etapes": etapes, "plans": plans,
                "script": v.script, "controle": controle(session_(id), v)}


def controle(s: Session, v) -> dict:
    """Ce que Vérification montre (langue du script) : les défauts minutés des contrôles finis, la note, la vidéo finale du montage ; « mesure »
    seulement quand tous sont finis."""
    from fabrique.moteur import execution

    c = {"mesure": False, "controles": [], "note": None, "defauts": [], "video": ""}
    base = v.script.get("language") or (v.recette.get("reglages") or {}).get("langues", [""])[0]  # langue du script : ses morceaux, ou les communs
    for mo in v.morceaux.filter(etat="fini", langue__in=("", base), brique__in=("controle", "montage", "assemblage", "verticale")).order_by("ordre"):
        r = execution.resultat(s, mo)
        if r is None:
            continue
        if mo.brique != "controle" and r.fichiers and r.fichiers[0].endswith(".mp4"):
            c["video"] = str(execution.dossier(s, mo) / r.fichiers[0])
        elif mo.brique == "controle" and r.infos.get("defauts") is not None:
            c["controles"].append(mo.etape)
            c["defauts"] += [{"source": mo.etape, **d} for d in r.infos["defauts"]]
            c["note"] = r.infos.get("note", c["note"])
    c["defauts"].sort(key=lambda d: (d["debut"] is None, d["debut"] or 0))
    c["mesure"] = bool(c["controles"]) and not v.morceaux.filter(langue__in=("", base), brique="controle").exclude(etat="fini").exists()  # l'analyse dure des heures
    return c


@api.post("/sessions/{id}/videos/{video}/refaire", response=schemas.Message)
@droit("refaire")
def refaire(request, id: str, video: str, corps: schemas.Plans):
    """« Je coche, Fabrique refait » : clic de RT dans Vérification."""
    from fabrique.moteur import execution

    return {"message": execution.refaire(session_(id), video, corps.plans, ACTEURS[request.auth])}


@api.get("/sessions/{id}/destinations", response=list[schemas.Destination])
@droit("destinations")
def destinations(request, id: str):
    """Où sont publiées les vidéos de chaque langue de la session : chaîne, état, playlists (lues au dernier « rafraîchir »)."""
    from fabrique.publication import youtube

    return youtube.lister(session_(id))


@api.post("/sessions/{id}/destinations/{langue}/relier", response=schemas.Lien)
@droit("relier")
def relier(request, id: str, langue: str):
    """RT relie la chaîne d'une langue : rend la page de Google, que la fenêtre ouvre dans le navigateur du PC ; le retour est attendu 5 min sur 127.0.0.1."""
    from fabrique.publication import youtube

    url, _ = youtube.connecter(session_(id), langue, ACTEURS[request.auth])
    return {"message": "Choisir la chaîne sur la page de Google ouverte dans le navigateur (5 min).", "url": url}


@api.post("/sessions/{id}/destinations/{langue}/rafraichir", response=schemas.Message)
@droit("relier")
def rafraichir(request, id: str, langue: str):
    from fabrique.publication import youtube

    try:
        lu = youtube.rafraichir(session_(id), langue)
    except (youtube.ErreurYoutube, OSError) as e:  # Google injoignable ou en erreur : dit à RT
        raise Refus(f"chaîne non lue : {e}") from None
    return {"message": f"Chaîne « {lu['chaine']} » : {len(lu['playlists'])} playlist(s) lue(s)."}


@api.post("/sessions/{id}/videos/{video}/approuver", response=schemas.Message)
@droit("approuver")
def approuver(request, id: str, video: str):
    """Geste de RT (fenêtre, iPhone) : la vidéo finie reçoit un brouillon de publication par langue, à relire avant « Publier »."""
    from fabrique.publication import publication

    r = {"message": publication.approuver(session_(id), video, ACTEURS[request.auth])}
    noter(ACTEURS[request.auth], "geste", quoi="approuver", appelant=request.auth, session=id, video=video)  # d'où (fenêtre ou iPhone) : la recette J4 le lit
    return r


@api.get("/sessions/{id}/videos/{video}/publications", response=list[schemas.Publication])
@droit("voir")
def publications(request, id: str, video: str):
    """L'aperçu complet de chaque langue (fenêtre, iPhone) : textes, chapitres, miniature, playlist, enfants, IA, créneau, chaîne, fautes, envoi."""
    from fabrique.publication import publication

    return publication.apercu(session_(id), video)


@api.get("/sessions/{id}/videos/{video}/suivi", response=list[schemas.SuiviPublication])
@droit("voir")
def suivi(request, id: str, video: str):
    """Vidéo → Suivi : chaque langue publiée, ses chiffres cumulés et ses 28 derniers jours relevés (relevé quotidien de J4)."""
    from django.db.models import Sum

    with routeur.session(session_(id)):
        v = m.Video.objects.filter(id=video).first()
        if v is None:
            raise HttpError(404, f"vidéo inconnue : {video}")
        liste = []
        for p in v.publications.order_by("langue"):
            st = p.statistiques.all()
            total = st.aggregate(vues=Sum("vues"), heures=Sum("heures"), abonnes=Sum("abonnes"))
            liste.append({"langue": p.langue, "statut": p.statut, "titre": p.titre, "lien": f"https://youtu.be/{p.identifiant_youtube}" if p.identifiant_youtube else "",
                          "vues": total["vues"] or 0, "heures": round(total["heures"] or 0, 1), "abonnes": total["abonnes"] or 0,
                          "jours": [{"date": f"{x.date:%d/%m}", "vues": x.vues} for x in st.order_by("-date")[:28]][::-1]})
        return liste


@api.get("/sessions/{id}/videos/{video}/paquets", response=list[schemas.Paquet])
@droit("paquets")
def lister_paquets(request, id: str, video: str):
    """Les paquets prêts à poster de chaque langue et de chaque réseau (fenêtre, iPhone) : état, fichiers mesurés, miniature, textes."""
    from fabrique.publication import paquets

    return paquets.lister(session_(id), video)


@api.post("/sessions/{id}/videos/{video}/paquets", response=schemas.Message)
@droit("retoucher")
def refaire_paquets(request, id: str, video: str):
    """Fenêtre : refaire les paquets de la vidéo (après une erreur, ou une vidéo finale changée) ; la boucle du noyau les lance."""
    s = session_(id)
    with routeur.session(s):
        n = m.Publication.objects.filter(video_id=video).update(paquets={})
    noter(ACTEURS[request.auth], "paquets", session=id, video=video, quoi="refaire")
    return {"message": f"paquets de {n} langue(s) à refaire : ils partent dans un instant" if n else "aucune publication : approuver d'abord la vidéo"}


@api.get("/sessions/{id}/publications/{pub}/paquets/{reseau}/{nom}", openapi_extra={"responses": {200: {"description": "le fichier"}}})
@droit("paquets")
def fichier_paquet(request, id: str, pub: int, reseau: str, nom: str):
    """Un fichier d'un paquet (vidéo ou miniature), à enregistrer sur l'iPhone ; seulement un fichier listé du paquet."""
    from fabrique.publication import paquets

    return FileResponse(paquets.fichier(session_(id), pub, reseau, nom).open("rb"), as_attachment=True, filename=nom)


@api.post("/sessions/{id}/publications/{pub}/retoucher", response=schemas.Message)
@droit("retoucher")
def retoucher(request, id: str, pub: int, corps: schemas.Retouche):
    from fabrique.publication import publication

    return {"message": publication.retoucher(session_(id), pub, corps.titre, corps.description, ACTEURS[request.auth])}


@api.post("/sessions/{id}/publications/{pub}/choisir", response=schemas.Message)
@droit("retoucher")
def choisir(request, id: str, pub: int, corps: schemas.Choix):
    from fabrique.publication import publication

    if corps.variante is not None:  # J11 : aussi après la publication (titre et miniature changés chez YouTube)
        from fabrique.publication import variantes

        return {"message": variantes.choisir(session_(id), pub, corps.variante, ACTEURS[request.auth])}
    return {"message": publication.choisir(session_(id), pub, ACTEURS[request.auth], corps.miniature, corps.playlist, corps.jour, corps.horaire)}


@api.post("/sessions/{id}/publications/{pub}/revenu", response=schemas.Message)
@droit("retoucher")
def revenu(request, id: str, pub: int, corps: schemas.Revenu):
    """Statistiques : le revenu d'une publication, saisi par RT (aucune chaîne n'est monétisée aujourd'hui)."""
    s = session_(id)
    with routeur.session(s):
        if not m.Publication.objects.filter(id=pub).update(revenu_eur=corps.revenu_eur):
            raise HttpError(404, f"publication inconnue : {pub}")
    noter(ACTEURS[request.auth], "revenu", session=id, publication=pub, revenu_eur=corps.revenu_eur)
    return {"message": "revenu effacé" if corps.revenu_eur is None else f"revenu : {corps.revenu_eur:.2f} €"}


@api.post("/sessions/{id}/publications/{pub}/portee", response=schemas.Message)
@droit("retoucher")
def portee(request, id: str, pub: int, corps: schemas.Portee):
    """Statistiques : impressions et taux de clic d'un jour, saisis par RT quand le rapport « reach » de YouTube manque (plan § 8.4)."""
    from datetime import date as jour

    s = session_(id)
    try:
        d = jour.fromisoformat(corps.date)
    except ValueError:
        raise HttpError(422, f"date illisible : {corps.date}") from None
    with routeur.session(s):
        p = m.Publication.objects.filter(id=pub).exclude(identifiant_youtube="").first()
        if p is None:
            raise Refus("cette publication n'est pas chez YouTube : rien à mesurer")
        d_ = m.Destination.objects.filter(langue=p.langue, simulation=p.simulation).exclude(jeton="").first()
        if d_ is None:
            raise Refus(f"aucune chaîne reliée pour « {p.langue} »")
        m.StatistiqueJour.objects.update_or_create(destination=d_, publication=p, date=d, defaults={"impressions": corps.impressions, "ctr": corps.ctr})
    noter(ACTEURS[request.auth], "portee", session=id, publication=pub, date=corps.date)
    return {"message": f"{corps.impressions} impressions, {corps.ctr:g} % de clics le {d:%d/%m}"}


@api.post("/sessions/{id}/publications/{pub}/{action}", response=schemas.Message)
@droit("publier")
def publier(request, id: str, pub: int, action: Literal["publier", "reprendre", "annuler"]):
    """Geste de RT (fenêtre, iPhone) : Publier (l'envoi part en tâche détachée légère), Reprendre l'envoi après une erreur, Annuler avant le départ."""
    from fabrique.publication import publication

    r = {"message": getattr(publication, action)(session_(id), pub, ACTEURS[request.auth])}
    noter(ACTEURS[request.auth], "geste", quoi=action, appelant=request.auth, session=id, publication=pub)
    return r


@api.post("/mode", response=schemas.Message)
@droit("mode")
def changer_mode(request, corps: schemas.Mode):
    """Fenêtre : passer en mode réel ou revenir en simulation (clic de RT, confirmé)."""
    return {"message": etat.changer(corps.reel, ACTEURS[request.auth])}


@api.post("/telephone/code", response=schemas.CodeTelephone)
@droit("telephone")
def code_telephone(request):
    """Fenêtre : un code à 6 chiffres (5 min, usage unique) à taper sur la page iPhone."""
    return telephone.nouveau_code(ACTEURS[request.auth])


@api.get("/telephone/appareils", response=list[schemas.Appareil])
@droit("telephone")
def appareils(request):
    return telephone.appareils()


@api.post("/telephone/appareils/{appareil}/deconnecter", response=schemas.Message)
@droit("telephone")
def deconnecter(request, appareil: str):
    if not telephone.deconnecter(appareil, ACTEURS[request.auth]):
        raise Refus("appareil inconnu (déjà déconnecté ?)")
    return {"message": "appareil déconnecté : il lui faudra un nouveau code"}


@api.get("/machine", response=schemas.Machine)
@droit("voir")
def machine(request):
    from fabrique.moteur import carte

    g = carte.gpu()
    return {"carte": f"{g[0]:.0f} % · {g[1] / 1024:.1f} / {g[2] / 1024:.0f} Go".replace(".", ",") if g else "indisponible",
            "disque_go": round(shutil.disk_usage(settings.RACINE).free / 1e9), "carte_prise": carte.occupee()}


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
    file.suspendue.set()  # d'abord : la file ne lance plus rien pendant que les bases sont remplacées
    try:
        if o := taches.occupe():
            raise Refus(f"{taches.la(o)} est en cours : restaurer quand elle sera finie")
        message = sauvegarde.restaurer(nom)
    finally:
        file.suspendue.clear()
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
    file.suspendue.set()  # l'app va se fermer : plus rien n'est lancé
    try:
        return {"message": versions.mettre_a_jour(ACTEURS[request.auth])}
    except Exception:
        file.suspendue.clear()
        raise


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
    """La file, avec pour chaque tâche active ce qui reste (durée, coût) et l'heure où elle sera finie (écran File)."""
    from fabrique.noyau.models import Tache
    from fabrique.session import calendrier

    prets, liste = calendrier.prets_vers(), file.lister()
    for t in liste:
        tache = Tache.objects.get(id=t["id"])
        if e := prets.get((tache.session_id, f"banc{tache.banc}" if tache.banc else tache.video_id)):
            t |= {"reste_s": e["secondes"], "cout_eur": e["cout_eur"], "pret_vers": f"{e['fin']:%d/%m %H:%M}"}
    return liste


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


@api.get("/outils", response=schemas.Outils)
@droit("voir")
def outils_(request):
    from fabrique.moteur import installation

    return {"briques": installation.registre(etat.simulation()), "installation": taches.lire("installation")}


@api.post("/outils/{outil}/{action}", response=schemas.Message)
@droit("outils")
def agir_outil(request, outil: str, action: Literal["installer", "retirer", "remettre"]):
    """Fenêtre : installer (ou mettre à jour), retirer, remettre parmi les candidats ; jamais mettre en service (seulement après un banc)."""
    from fabrique.moteur import installation

    qui = ACTEURS[request.auth]
    return {"message": {"installer": installation.lancer, "retirer": installation.retirer, "remettre": installation.remettre}[action](outil, qui)}


@api.get("/depenses", response=schemas.Depenses)
@droit("voir")
def depenses(request):
    from fabrique.moteur import execution
    from fabrique.noyau.models import Depense, Parametre

    noms = dict(Session.objects.values_list("id", "nom"))
    lignes = [{"date": f"{timezone.localtime(d.date):%d/%m/%Y %H:%M}", "session": noms.get(d.session_id, ""), "outil": d.outil, "estime_eur": d.estime_eur,
               "reel_eur": d.reel_eur} for d in Depense.objects.order_by("-date")[:200]]
    return {"plafond_mois_eur": float(Parametre.lire("plafond_mois_eur") or 0), "depense_mois_eur": round(execution.depense_du_mois(), 2), "lignes": lignes}


@api.post("/depenses/plafond", response=schemas.Message)
@droit("outils")
def plafond(request, corps: schemas.Nombre):
    from fabrique.moteur import execution
    from fabrique.noyau.models import Parametre

    if not 0 <= corps.valeur <= 10000:
        raise Refus("plafond attendu : entre 0 et 10 000 € par mois")
    Parametre.ecrire("plafond_mois_eur", f"{corps.valeur:g}")
    noter(ACTEURS[request.auth], "plafond", mois_eur=corps.valeur)
    return {"message": f"Plafond des outils payants : {execution.euros(corps.valeur)} par mois" + (" (aucun outil payant ne servira)." if not corps.valeur else ".")}


@api.get("/bancs", response=list[schemas.BancListe])
@droit("voir")
def bancs_(request):
    from fabrique.moteur import bancs
    from fabrique.noyau.models import Banc

    return [bancs.resume(b) for b in Banc.objects.order_by("-cree")[:100]]


@api.post("/bancs", response=schemas.Message)
@droit("bancs")
def nouveau_banc(request, corps: schemas.NouveauBanc):
    from fabrique.moteur import bancs

    from fabrique.moteur import execution

    b = bancs.creer(session_(corps.session), corps.video, corps.brique, corps.outil, corps.juge, ACTEURS[request.auth])
    e = bancs.estimer(b)
    return {"message": f"Banc {b.id} dans la file : {len(b.entrees)} entrée(s), deux outils, environ {max(1, round(e['secondes'] / 60))} min et "
                       f"{execution.euros(e['cout_eur'])}. Vous voterez à l'aveugle quand il sera prêt."}


@api.get("/bancs/{id}", response=schemas.BancDetail)
@droit("voir")
def banc_(request, id: int):
    from fabrique.moteur import bancs
    from fabrique.noyau.models import Banc

    b = Banc.objects.filter(id=id).first()
    if b is None:
        raise Refus(f"banc inconnu : {id}")
    return bancs.detail(b)


@api.post("/bancs/{id}/voter", response=schemas.Message)
@droit("voter")
def voter(request, id: int, corps: schemas.Vote):
    from fabrique.moteur import bancs

    return {"message": bancs.voter(id, corps.entree, corps.choix, ACTEURS[request.auth])}


@api.post("/bancs/{id}/verdict", response=schemas.Message)
@droit("voter")
def rendre_verdict(request, id: int):
    from fabrique.moteur import bancs

    return {"message": bancs.rendre(id, ACTEURS[request.auth])}


@api.post("/bancs/{id}/adopter", response=schemas.Message)
@droit("outils")
def adopter(request, id: int, corps: schemas.Adopter):
    from fabrique.moteur import bancs

    return {"message": bancs.adopter(id, corps.ou, ACTEURS[request.auth])}


@api.get("/veille", response=list[schemas.CandidatVeille])
@droit("voir")
def veille_(request):
    from fabrique.moteur import veille
    from fabrique.noyau.models import Candidat

    return [{**{k: getattr(c, k) for k in ("id", "brique", "nom", "source", "licence", "commercial", "besoins", "avis", "statut")},
             "date": f"{c.date:%d/%m/%Y}", "statut_nom": veille.STATUTS[c.statut]} for c in Candidat.objects.order_by("-date", "brique", "nom")]


@api.post("/veille", response=schemas.Message)
@droit("veille")
def verser_veille(request, corps: schemas.Veille):
    from fabrique.moteur import veille

    return {"message": veille.verser(corps, ACTEURS[request.auth])}


@api.post("/veille/{pk}/statut", response=schemas.Message)
@droit("outils")
def statut_veille(request, pk: int, corps: schemas.Valeur):
    from fabrique.moteur import veille

    return {"message": veille.statut(pk, corps.valeur, ACTEURS[request.auth])}


def exporter_en_fond(s: Session, videos: bool, qui: str):
    """Un export (des Go avec les vidéos) ne tient pas dans une requête : il se fait à côté, la fenêtre est prévenue à la fin."""
    try:
        z = echange.exporter(s, videos, qui)
        evenements.publier("info", titre="Session exportée", message=str(z))
    except Exception as e:  # noqa: BLE001
        log.exception("export de %s", s.nom)
        evenements.publier("alerte", titre="Export raté", message=f"« {s.nom} » : {e}")
    finally:
        from django.db import connections

        connections.close_all()


# en dernier : « /sessions/{id}/{action} » prendrait sinon les chemins des routes plus précises (destinations…)
@api.get("/statistiques", response=schemas.Statistiques)
@droit("voir")
def statistiques(request):
    """Statistiques → Sessions et « quoi fabriquer ensuite » (J11) ; une base illisible ne cache pas les autres sessions."""
    from fabrique.publication import rendement

    sessions_ = []
    for s in Session.objects.filter(essais=False, archivee__isnull=True).order_by("nom"):
        try:
            sessions_.append(rendement.resume(s))
        except Exception:  # noqa: BLE001
            log.exception("statistiques de la session %s", s.nom)
    return {"sessions": sessions_, "ensuite": rendement.ensuite()}


@api.get("/sessions/{id}/statistiques", response=schemas.StatistiquesSession)
@droit("voir")
def statistiques_session(request, id: str):
    from fabrique.publication import rendement

    return rendement.session(session_(id))


@api.post("/sessions/{id}/temps", response=schemas.Message)
@droit("temps")
def temps_rt(request, id: str, corps: schemas.TempsRT):
    """La fenêtre, chaque minute passée par RT sur une vidéo ou sur son script (J11)."""
    from fabrique.publication import rendement

    rendement.noter_temps(session_(id), corps.cle, corps.secondes)
    return {"message": "noté"}


@api.post("/sessions/{id}/{action}", response=schemas.Message)
@droit("sessions")
def agir_session(request, id: str, action: Literal["pause", "reprendre", "archiver", "desarchiver", "dupliquer", "exporter", "modele"], corps: schemas.ActionSession):
    """Fenêtre : la vie d'une session (pause, archive, copie, export, modèle) ; jamais la session « Essais »."""
    s, qui = session_(id), ACTEURS[request.auth]
    if s.essais:
        raise Refus("la session « Essais » ne se met pas en pause, ne s'archive, ne se copie ni ne s'exporte")
    if action in ("dupliquer", "modele") and not corps.nom.strip():
        raise Refus("un nom est attendu")
    if action == "dupliquer":
        return {"message": f"Copie « {echange.dupliquer(s, corps.nom.strip(), qui).nom} » créée (sans ses comptes : relier ses chaînes)."}
    if action == "modele":
        return {"message": f"Modèle enregistré : {echange.exporter(s, False, qui, modele=corps.nom.strip())}"}
    if action == "exporter":
        threading.Thread(target=exporter_en_fond, args=(s, corps.videos, qui), name="export", daemon=True).start()
        return {"message": f"Export de « {s.nom} » lancé{' avec ses vidéos finales' if corps.videos else ''} : une notification dira où il est."}
    if action == "reprendre" and s.archivee:
        raise Refus(f"« {s.nom} » est archivée : la sortir des archives d'abord")
    if action == "reprendre":
        from fabrique.session import reglages

        if reglages.lire(s)["assistant"] not in ("", "fini"):
            raise Refus(f"« {s.nom} » est une nouvelle session pas finie : la finir (« Terminer ») d'abord")
    champs = {"pause": {"pause": True}, "reprendre": {"pause": False}, "archiver": {"pause": True, "archivee": timezone.now()},
              "desarchiver": {"archivee": None}}[action]
    Session.objects.filter(id=s.id).update(**champs)
    noter(qui, "session", session=s.id, quoi=action)
    return {"message": {"pause": f"« {s.nom} » en pause : rien d'elle ne part dans la file.", "reprendre": f"« {s.nom} » reprend.",
                        "archiver": f"« {s.nom} » archivée (en pause, rien d'effacé).", "desarchiver": f"« {s.nom} » sortie des archives (toujours en pause)."}[action]}
