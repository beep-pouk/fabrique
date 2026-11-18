"""Ce que la session dit d'elle-même (cahier § 7.1, écrit à sa création, changé dans Session → Formats et Règles) : identité, formats, style,
règles (dont le garde-fou YouTube : ce qui rend chaque vidéo différente), objectif, critère d'arrêt, plafond. Gardé dans ses réglages (sa
base : un dossier de session se suffit à lui-même). Et la nouvelle session pas à pas (formulaires ; l'assistant viendra à J11), jusqu'à sa
vidéo pilote en simulation (faux outils, même en mode réel)."""
import json
import re

from django.conf import settings
from django.utils import timezone

from fabrique.garde import Refus
from fabrique.moteur import recettes
from fabrique.noyau import bases, routeur
from fabrique.noyau.models import Session, noter
from fabrique.session import models as m

TEXTES = ("public", "promesse", "style", "difference", "objectif", "arret", "format", "assistant")
NOMBRES = ("plafond_eur", "duree_min", "duree_max")
OUI_NON = {"enfants": True, "declaration_ia": True, "ordre_strict": True}
LANGUE = re.compile(r"^[a-z]{2,3}(-[a-z0-9]+)?$")
PILOTE = "pilote"


def catalogue() -> list[dict]:
    """Les formats livrés (recettes), avec leurs étapes."""
    lus = []
    for f in sorted(recettes.LIVREES.glob("*.json")):
        r = recettes.lire(f)
        lus.append({"id": r["id"], "nom": r["nom"], "version": r["version"], "script": r["script"],
                    "etapes": [{"id": e["id"], "brique": e["brique"], "par": e["par"]} for e in r["etapes"]]})
    return lus


def lire(s: Session) -> dict:
    with routeur.session(s):
        brut = dict(m.Reglage.objects.values_list("cle", "valeur"))
        langues = [{"code": l.code, "nom": l.nom} for l in m.Langue.objects.order_by("ordre", "code")]
    d = {k: brut.get(k, "") for k in TEXTES}
    d |= {k: float(brut[k]) if brut.get(k) not in (None, "") else (0.0 if k == "plafond_eur" else None) for k in NOMBRES}
    d |= {k: brut[k] == "oui" if k in brut else v for k, v in OUI_NON.items()}
    d["formats"] = json.loads(brut.get("formats") or "[]")
    d["format"] = d["format"] or (d["formats"][0] if d["formats"] else "F1")  # « format » : celui de « Fabriquer » (F1 avant J5)
    return d | {"langues": langues, "nom": s.nom, "pause": s.pause}


def ecrire(s: Session, champs: dict, acteur: str) -> str:
    """Les champs donnés seulement, contrôlés ; rend le message pour RT."""
    actuel = lire(s)
    nouveau = {**actuel, **champs}
    ids = {f["id"] for f in catalogue()}
    if inconnus := [f for f in nouveau["formats"] if f not in ids]:
        raise Refus(f"format inconnu : {', '.join(inconnus)}")
    if nouveau["formats"] and nouveau["format"] not in nouveau["formats"]:
        if "format" in champs:
            raise Refus(f"le format {nouveau['format']} n'est pas parmi ceux de la session")
        nouveau["format"] = nouveau["formats"][0]
    if nouveau["format"] not in ids:
        raise Refus(f"format inconnu : {nouveau['format']}")
    if "difference" in champs and not nouveau["difference"].strip():
        raise Refus("dire ce qui rend chaque vidéo différente (histoire, personnages) : YouTube écarte le « contenu en série sur gabarit »")
    if any(nouveau[k] is not None and nouveau[k] < 0 for k in NOMBRES):
        raise Refus("une durée ou un plafond ne peut pas être négatif")
    if nouveau["duree_min"] is not None and nouveau["duree_max"] is not None and nouveau["duree_min"] > nouveau["duree_max"]:
        raise Refus("la durée minimale dépasse la durée maximale")
    valeurs = {}
    for k in champs:
        if k in TEXTES:
            valeurs[k] = str(nouveau[k]).strip()
        elif k in NOMBRES:
            valeurs[k] = "" if nouveau[k] is None else repr(float(nouveau[k]))
        elif k in OUI_NON:
            valeurs[k] = "oui" if nouveau[k] else "non"
        elif k == "formats":
            valeurs[k] = json.dumps(nouveau[k])
            valeurs["format"] = nouveau["format"]
    with routeur.session(s):
        for k, v in valeurs.items():
            m.Reglage.objects.update_or_create(cle=k, defaults={"valeur": v})
    if valeurs:
        noter(acteur, "reglages", session=s.id, champs=sorted(valeurs))
    return f"« {s.nom} » : {len(valeurs)} réglage(s) enregistré(s)."


def controler_langues(langues: list[dict]):
    if not langues:
        raise Refus("au moins une langue")
    for l in langues:
        if not LANGUE.match(l.get("code", "")):
            raise Refus(f"code de langue illisible : « {l.get('code', '')} » (deux ou trois lettres, ex. « en »)")
    if len({l["code"] for l in langues}) != len(langues):
        raise Refus("une langue est en double")


def poser_langues(s: Session, langues: list[dict]):
    controler_langues(langues)
    with routeur.session(s):
        for i, l in enumerate(langues):
            m.Langue.objects.update_or_create(code=l["code"], defaults={"nom": l.get("nom") or l["code"], "ordre": i})


def creer(nom: str, langues: list[dict], public: str = "", promesse: str = "", modele: str = "", acteur: str = "RT") -> Session:
    """Étape 1 de la nouvelle session : la session (vide, ou partie d'un modèle), en pause jusqu'à la fin de l'assistant."""
    from fabrique.noyau import echange

    nom = nom.strip()
    if not nom:
        raise Refus("un nom est attendu")
    if Session.objects.filter(nom=nom).exists():
        raise Refus(f"une session s'appelle déjà « {nom} »")
    controler_langues(langues)  # avant : jamais une session à moitié créée
    if modele:
        fichier = settings.RACINE / "modeles" / modele
        if fichier.name != modele or not fichier.is_file():
            raise Refus(f"modèle introuvable : {modele}")
        s = echange.importer(fichier, nom, acteur)
    else:
        s = bases.creer(nom)
    Session.objects.filter(id=s.id).update(pause=True)
    s.refresh_from_db()
    poser_langues(s, langues)
    with routeur.session(s):
        m.Reglage.objects.update_or_create(cle="assistant", defaults={"valeur": "2"})
    ecrire(s, {"public": public, "promesse": promesse}, acteur)
    noter(acteur, "session", session=s.id, quoi="creer", modele=modele)
    return s


def manque(s: Session) -> list[str]:
    """Ce qui manque pour finir la nouvelle session (et pour fabriquer)."""
    d = lire(s)
    return [texte for ok, texte in ((d["langues"], "une langue"), (d["formats"], "un format"),
                                    (d["difference"].strip(), "ce qui rend chaque vidéo différente (Règles)")) if not ok]


def finir(s: Session, acteur: str) -> str:
    if trous := manque(s):
        raise Refus(f"il manque encore : {', '.join(trous)}")
    with routeur.session(s):
        m.Reglage.objects.update_or_create(cle="assistant", defaults={"valeur": "fini"})
    Session.objects.filter(id=s.id).update(pause=False)
    noter(acteur, "session", session=s.id, quoi="finir")
    return f"« {s.nom} » est prête : la vidéo pilote peut partir en simulation."


def garde_fou(s: Session):
    """Avant « Fabriquer » : la session dit ce qui rend chaque vidéo différente (sauf « Essais »)."""
    if not s.essais and not lire(s)["difference"].strip():
        raise Refus(f"« {s.nom} » ne dit pas encore ce qui rend chaque vidéo différente (Session → Règles) : "
                    "garde-fou contre le « contenu en série sur gabarit » que YouTube écarte")


def script_pilote(d: dict) -> dict:
    texte = d["promesse"] or d["public"] or d["nom"]
    return {"titre": f"Vidéo pilote — {d['nom']}"[:200], "scenes": [
        {"id": "s1", "plans": [{"id": "p1", "texte": texte}, {"id": "p2", "texte": d["style"] or texte}]},
        {"id": "s2", "plans": [{"id": "p1", "texte": d["difference"] or texte}]}]}


def pilote(s: Session, acteur: str) -> str:
    """Étape 7 : la vidéo pilote en simulation (chaque étape sur le faux outil de sa brique, même en mode réel), mise dans la file ; elle se
    regarde ensuite dans Vidéos. « En vrai » = « Fabriquer » un script, plus tard, au clic de RT."""
    from fabrique.moteur import execution, file, outils
    from fabrique.noyau.models import Tache

    if s.essais:
        raise Refus("la session « Essais » n'a pas de vidéo pilote")
    if s.pause:
        raise Refus(f"« {s.nom} » est en pause (rien ne part dans la file) : finir la nouvelle session, ou la reprendre, d'abord")
    if trous := manque(s):
        raise Refus(f"il manque encore : {', '.join(trous)}")
    d = lire(s)
    recette = recettes.lire(d["format"])
    if recette["script"] != "scenes-plans-narrateur":
        raise Refus(f"le format {d['format']} se fabrique d'un script complet de la session : sa vidéo pilote = « Fabriquer » un de ses scripts")
    recette["reglages"]["langues"] = [l["code"] for l in d["langues"]]
    recette["outils"] = {e["id"]: outils.BRIQUES[e["brique"]]["simulation"] for e in recette["etapes"]}
    contenu = script_pilote(d)
    with routeur.session(s):
        if Tache.objects.filter(session_id=s.id, video_id__in=list(m.Video.objects.filter(nom__endswith=f"-{PILOTE}").values_list("id", flat=True)),
                                etat__in=("attente", "en_cours", "pause")).exists():
            raise Refus("la vidéo pilote est déjà dans la file")
        sc, _ = m.Script.objects.get_or_create(code=PILOTE, defaults={"titre": contenu["titre"], "langue": d["langues"][0]["code"], "statut": "idee"})
        n = (sc.versions.order_by("-numero").values_list("numero", flat=True).first() or 0) + 1
        m.VersionScript.objects.create(script=sc, numero=n, auteur="noyau", date=timezone.now(), contenu=contenu)
    v = execution.preparer(s, recette, contenu, nom=f"{timezone.localdate()}-{PILOTE}")
    t = file.mettre(s, v.id, v.titre, acteur)
    noter(acteur, "pilote", session=s.id, video=v.id)
    return f"Vidéo pilote dans la file (tâche {t.id}), en simulation : faux outils, quelques secondes par étape."
