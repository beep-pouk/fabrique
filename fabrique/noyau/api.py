"""L'API locale du noyau (django-ninja ; contrat OpenAPI tiré des schémas : /api/openapi.json). Quatre appelants, quatre droits (plan § 3.3) :
chaque route déclare son droit (@droit) ; les trois gestes (fabriquer, approuver, publier) n'existent que pour la fenêtre et l'iPhone, au clic
de RT. Aucune règle dans la fenêtre : tout ce qu'elle montre et fait passe par ici."""
import os
import shutil
from functools import wraps
from typing import Literal

from django.conf import settings
from django.http import FileResponse, StreamingHttpResponse
from ninja import NinjaAPI
from ninja.errors import HttpError
from ninja.security import APIKeyCookie, HttpBearer

from fabrique import journaux, programme
from fabrique.garde import Refus
from fabrique.moteur import file
from fabrique.noyau import cles, etat, evenements, jetons, routeur, sauvegarde, schemas, taches, telephone, versions
from fabrique.noyau.models import Session, noter
from fabrique.session import models as m
from fabrique.session.models import Fiche

GESTES = {"fabriquer", "approuver", "publier"}
DROITS = {
    "fenetre": {"voir", "sauvegarder", "restaurer", "mettre_a_jour", "cles", "arreter", "file", "refaire", "importer", "demander", "destinations", "relier",
                "retoucher", "paquets", "telephone", *GESTES},
    "iphone": {"voir", "destinations", "approuver", "publier", "paquets"},  # J4 : Tailscale + code à 6 chiffres
    "claude": {"voir", "importer", "deposer"},  # « Fabrique.exe commande … »
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


api = NinjaAPI(title=programme.NOM, version=settings.VERSION, auth=[Jeton(), Iphone(csrf=False)], docs_url=None)


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
                 "validee": bool((v := sc.versions.order_by("-numero").first()) and v.validee)} for sc in m.Script.objects.order_by("date_prevue", "code")]


@api.get("/sessions/{id}/scripts/{code}", response=schemas.ScriptDetail)
@droit("voir")
def script_(request, id: str, code: str):
    """Un script : ses versions, la plus récente (contenu, règles), sa planche (les plans qui seront fabriqués) et l'estimation de sa
    fabrication au format de la session (durée, coût), à relire avant « Fabriquer »."""
    from fabrique.moteur import execution, recettes
    from fabrique.moteur.f1 import refaire as f1

    s = session_(id)
    with routeur.session(s):
        sc = m.Script.objects.filter(code=code).first()
        if sc is None:
            raise HttpError(404, f"script inconnu : {code}")
        versions = list(sc.versions.order_by("-numero"))
        forme = (m.Reglage.objects.filter(cle="format").first() or m.Reglage(valeur="F1")).valeur
        traductions = sorted(t.code.split(".", 1)[1] for t in m.Script.objects.filter(code__startswith=f"{code}.") if t.versions.exists())
    contenu = versions[0].contenu if versions else {}
    try:
        recette = recettes.lire(forme)
        estimation = execution.estimer_script(s, recette, contenu)
    except Refus as e:
        recette, estimation = {}, {"secondes": 0, "cout_eur": 0, "carte_go": 0, "refus": str(e)}
    plans = f1.planche(contenu) if recette.get("script") == "scenario-bramble" else []
    return {"code": sc.code, "titre": sc.titre, "statut": sc.statut, "date_prevue": str(sc.date_prevue or ""),
            "versions": [{"numero": v.numero, "auteur": v.auteur, "date": v.date.isoformat(timespec="minutes"), "validee": v.validee} for v in versions],
            "contenu": contenu, "regles": versions[0].regles if versions else {}, "plans": plans, "estimation": estimation, "traductions": traductions}


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
    with routeur.session(session_(id)):
        return {"personnages": [{"nom": p.nom, "role": p.role, "statut": p.statut, "references": p.references.count()} for p in m.Personnage.objects.order_by("nom", "id")],
                "lieux": [{"nom": l.nom, "description": l.description} for l in m.Lieu.objects.order_by("nom")],
                "langues": [{"code": l.code, "nom": l.nom, "outil_voix": l.outil_voix, "voix_validee": l.voix_validee} for l in m.Langue.objects.order_by("ordre", "code")]}


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

    s = session_(id)
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
        forme = (m.Reglage.objects.filter(cle="format").first() or m.Reglage(valeur="F1")).valeur
        date = (sc.date_prevue or v.date.date()).isoformat()
        traductions = {}
        for langue in choisies:
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
    base = v.contenu.get("language") or recette["reglages"]["langues"][0]
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
    for mo in v.morceaux.filter(etat="fini", langue="", brique__in=("controle", "montage")).order_by("ordre"):
        r = execution.resultat(s, mo)
        if r is None:
            continue
        if mo.brique == "montage" and r.fichiers and r.fichiers[0].endswith(".mp4"):
            c["video"] = str(execution.dossier(s, mo) / r.fichiers[0])
        elif mo.brique == "controle" and r.infos.get("defauts") is not None:
            c["controles"].append(mo.etape)
            c["defauts"] += [{"source": mo.etape, **d} for d in r.infos["defauts"]]
            c["note"] = r.infos.get("note", c["note"])
    c["defauts"].sort(key=lambda d: (d["debut"] is None, d["debut"] or 0))
    c["mesure"] = bool(c["controles"]) and not v.morceaux.filter(langue="", brique="controle").exclude(etat="fini").exists()  # l'analyse dure des heures
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

    return {"message": publication.approuver(session_(id), video, ACTEURS[request.auth])}


@api.get("/sessions/{id}/videos/{video}/publications", response=list[schemas.Publication])
@droit("voir")
def publications(request, id: str, video: str):
    """L'aperçu complet de chaque langue (fenêtre, iPhone) : textes, chapitres, miniature, playlist, enfants, IA, créneau, chaîne, fautes, envoi."""
    from fabrique.publication import publication

    return publication.apercu(session_(id), video)


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

    return {"message": publication.choisir(session_(id), pub, ACTEURS[request.auth], corps.miniature, corps.playlist, corps.jour, corps.horaire)}


@api.post("/sessions/{id}/publications/{pub}/{action}", response=schemas.Message)
@droit("publier")
def publier(request, id: str, pub: int, action: Literal["publier", "reprendre", "annuler"]):
    """Geste de RT (fenêtre, iPhone) : Publier (l'envoi part en tâche détachée légère), Reprendre l'envoi après une erreur, Annuler avant le départ."""
    from fabrique.publication import publication

    return {"message": getattr(publication, action)(session_(id), pub, ACTEURS[request.auth])}


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
            raise Refus(f"la {o} est en cours : restaurer quand elle sera finie")
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
