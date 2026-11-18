"""Briques et outils (plan § 5.2). Une brique = un rôle et sa prise : estimer(fiche, demande) → Estimation, fabriquer(fiche, demande, dossier)
→ Resultat ; demande et résultat typés ici, rangés en JSON à côté des fichiers ; ce que chaque brique doit rendre (extension du fichier
principal, informations) est écrit dans briques.json et contrôlé après chaque morceau. Un outil = un adaptateur (module Python) + une fiche JSON
(fiches\\). Choix de l'outil : exception du plan, sinon défaut du format, de la session, du noyau (réglage « outil.<brique> »), sinon de la
brique (briques.json) ; en simulation, un vrai outil cède la place au faux de sa brique. Nouveau rôle = une ligne de briques.json ; nouvel
outil = une fiche et son module : le noyau ne change pas."""
import importlib
import json
import re
from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from fabrique.garde import Refus

ICI = Path(__file__).parent
BRIQUES: dict[str, dict] = json.loads((ICI / "briques.json").read_text(encoding="utf-8"))  # brique → {titre, defaut}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Besoins(Strict):
    carte_go: float = 0
    disque_go: float = 0


class Installation(Strict):
    """La recette d'installation d'un outil (moteur/installation.py), jouée cachée vers outils\\<id>\\<version>."""
    pas: list[dict] = []
    temoins: list[str] = Field(min_length=1)  # fichiers qui doivent exister dans le dossier de l'outil installé
    place_go: float = 0
    manuel: str = ""  # ce qui demande des droits administrateur : l'explication montrée à RT, sans pas


class Fiche(Strict):
    id: str = Field(pattern=r"^[a-z0-9_]{1,50}$")  # un nom de dossier (outils\<id>)
    nom: str
    roles: list[str] = Field(min_length=1)
    local: bool
    prix_unite_eur: float = 0
    unite: str = "appel"  # ce que le prix paie : « appel », « 1 000 caractères »…
    prix_date: str | None = None
    licence: str
    credit: str = ""
    besoins: Besoins
    langues: list[str] = []  # vide : toutes
    limites: str = ""
    version: str
    dernier_banc: str | None = None
    etat: Literal["en_service", "candidat", "retire"]
    faux: bool = False  # outil de simulation : sans carte, quelques secondes
    simulable: bool = False  # un vrai outil sans carte ni réseau (ffmpeg) : il sert tel quel en simulation
    module: str
    reglages: dict = {}
    installation: Installation | None = None  # absente : rien à installer (faux outil, service en ligne, outil partagé de Bramble Studio)
    cle: str = ""  # service en ligne : le nom de sa clé (noyau/cles.py), saisie par RT ; sans elle, l'outil ne sert pas

    @model_validator(mode="after")
    def simulable_sur(self):
        if self.simulable and not (self.local and not self.prix_unite_eur and not self.besoins.carte_go and not self.cle and not self.installation):
            raise ValueError("un outil « simulable » est local, gratuit, sans carte, sans clé ni installation (il sert tel quel en simulation)")
        return self

    @model_validator(mode="after")
    def version_sure(self):
        if self.installation and not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", self.version):
            raise ValueError("la version d'un outil à installer nomme son dossier : lettres, chiffres, point, tiret")
        return self


class Demande(Strict):
    brique: str
    etape: str
    unite: str  # « s1/p2 » (plan), « s1 » (scène), « » (vidéo)
    langue: str = ""  # « » : commun à toutes les langues
    texte: str = ""  # dans la langue du morceau (sa traduction, s'il en a une)
    consigne: dict = {}  # ce que la forme du script dit d'autre du morceau (voix-off : image, mouvement)
    entrees: dict[str, list[str]] = {}  # étape précédente → ses fichiers qui concernent ce morceau (chemins complets, le principal d'abord)
    sources: dict[str, str] = {}  # étape précédente → sa brique
    reglages: dict = {}  # ceux de la recette
    graine: int = 0
    session: str = ""  # le dossier de la session (son univers, ses réglages)
    script: str = ""  # le script de la vidéo, en fichier JSON
    atelier: str = ""  # le dossier de travail de la vidéo pour cette langue, gardé d'une étape à l'autre (outils qui font toute la vidéo d'un coup)


class Resultat(Strict):
    fichiers: list[str]  # dans le dossier du morceau
    duree_s: float | None = None
    infos: dict = {}  # par brique : mots horodatés (voix), défauts (contrôle), cout_eur réel (payant)…


class Estimation(Strict):
    secondes: float
    cout_eur: float = 0
    carte_go: float = 0


def controler(modele, donnees, quoi: str):
    """Les données validées par leur schéma, sinon un refus qui dit où est l'erreur."""
    try:
        return modele.model_validate(donnees)
    except ValidationError as e:
        raise Refus(f"{quoi} refusé(e) : " + " ; ".join(f"{'.'.join(map(str, x['loc'])) or 'racine'} : {x['msg']}" for x in e.errors()[:5])) from None


@cache
def fiches() -> dict[str, Fiche]:
    lues = {f.stem: controler(Fiche, json.loads(f.read_text(encoding="utf-8")), f"fiche {f.name}") for f in sorted((ICI / "fiches").glob("*.json"))}
    for nom, f in lues.items():
        if f.id != nom or not set(f.roles) <= BRIQUES.keys():
            raise Refus(f"fiche {nom}.json : identifiant ou rôle inconnu")
    return lues


def etat(f: Fiche) -> str:
    """En service, candidat ou retiré : celui de la base du noyau (installer, retirer, adopter après un banc), sinon celui de la fiche."""
    from fabrique.noyau.models import Outil

    o = Outil.objects.filter(id=f.id).first()
    return (o and o.etat) or f.etat


def fiche(outil: str, brique: str, langue: str = "", en_service: bool = True) -> Fiche:
    """La fiche d'un outil de cette brique (et de cette langue), en service sauf pour un banc, sinon un refus en clair."""
    f = fiches().get(outil)
    if f is None or brique not in f.roles:
        raise Refus(f"l'outil « {outil} » n'existe pas pour la brique {brique}")
    if en_service and (e := etat(f)) != "en_service":
        raise Refus(f"l'outil {f.nom} n'est pas en service ({e})")
    if langue and f.langues and langue not in f.langues:
        raise Refus(f"l'outil {f.nom} ne parle pas la langue « {langue} » ({', '.join(f.langues)})")
    return f


def defauts(brique: str, de_la_session: dict) -> list[str]:
    from fabrique.noyau.models import Parametre

    from fabrique.noyau import etat

    reel = not etat.simulation()  # un faux outil adopté en simulation ne sert jamais en mode réel
    return [o for o in (de_la_session.get(f"outil.{brique}"), Parametre.lire(f"outil.{brique}")) if o and not (reel and o in fiches() and fiches()[o].faux)] + [BRIQUES[brique]["defaut"]]


def choisir(brique: str, etape: str, langue: str, du_plan: dict, du_format: dict, de_la_session: dict) -> str:
    from fabrique.noyau import etat

    f = fiche(du_plan.get(etape) or du_format.get(etape) or defauts(brique, de_la_session)[0], brique, langue)
    if etat.simulation() and not (f.faux or f.simulable):
        f = fiche(BRIQUES[brique]["simulation"], brique, langue)  # simulation : jamais un vrai outil
    return f.id


def local(brique: str, langue: str, de_la_session: dict) -> Fiche:
    """L'outil local de repli d'une brique : le premier local en service parmi ses défauts (session, noyau, brique), sinon parmi tous."""
    candidats = [*(fiches().get(o) for o in defauts(brique, de_la_session)), *fiches().values()]
    f = next((f for f in candidats if f and f.local and etat(f) == "en_service" and brique in f.roles and (not langue or not f.langues or langue in f.langues)), None)
    if f is None:
        raise Refus(f"aucun outil local en service pour la brique {brique}")
    return f


def controler_resultat(brique: str, r: Resultat, dossier: Path):
    """Ce que la brique doit rendre (briques.json) : des fichiers présents et non vides, le principal à la bonne extension, les informations dues."""
    b = BRIQUES[brique]
    if not r.fichiers and r.infos.get("rien_a_faire"):  # une étape sans objet pour cette vidéo (aucune scène où le narrateur parle)
        return
    if not r.fichiers:
        raise RuntimeError("l'outil n'a rendu aucun fichier")
    if vides := [f for f in r.fichiers if not (dossier / f).is_file() or not (dossier / f).stat().st_size]:
        raise RuntimeError(f"fichiers absents ou vides : {', '.join(vides)}")
    if Path(r.fichiers[0]).suffix.lower() not in b["sortie"]:
        raise RuntimeError(f"la brique {brique} attend un fichier {' ou '.join(b['sortie'])}, pas {r.fichiers[0]}")
    if manquent := [i for i in b["infos"] if i not in r.infos]:
        raise RuntimeError(f"informations manquantes : {', '.join(manquent)}")


def adaptateur(f: Fiche):
    return importlib.import_module(f.module)
