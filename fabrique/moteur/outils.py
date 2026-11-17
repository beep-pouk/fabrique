"""Briques et outils (plan § 5.2). Une brique = un rôle et sa prise : estimer(fiche, demande) → Estimation, fabriquer(fiche, demande, dossier)
→ Resultat ; demande et résultat typés ici, rangés en JSON à côté des fichiers. Un outil = un adaptateur (module Python) + une fiche JSON
(fiches\\). Choix de l'outil : exception du plan, sinon défaut du format, de la session, du noyau (réglage « outil.<brique> »), sinon de la
brique (briques.json). Nouveau rôle = une ligne de briques.json ; nouvel outil = une fiche et son module : le noyau ne change pas."""
import importlib
import json
from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fabrique.garde import Refus

ICI = Path(__file__).parent
BRIQUES: dict[str, dict] = json.loads((ICI / "briques.json").read_text(encoding="utf-8"))  # brique → {titre, defaut}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Besoins(Strict):
    carte_go: float = 0
    disque_go: float = 0


class Fiche(Strict):
    id: str
    nom: str
    roles: list[str] = Field(min_length=1)
    local: bool
    prix_unite_eur: float = 0
    prix_date: str | None = None
    licence: str
    credit: str = ""
    besoins: Besoins
    langues: list[str] = []  # vide : toutes
    limites: str = ""
    version: str
    dernier_banc: str | None = None
    etat: Literal["en_service", "candidat", "retire"]
    module: str
    reglages: dict = {}


class Demande(Strict):
    brique: str
    etape: str
    unite: str  # « s1/p2 » (plan), « s1 » (scène), « » (vidéo)
    langue: str = ""  # « » : commun à toutes les langues
    texte: str = ""
    entrees: dict[str, list[str]] = {}  # étape précédente → ses fichiers qui concernent ce morceau (chemins complets)
    reglages: dict = {}  # ceux de la recette
    graine: int = 0


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


def fiche(outil: str, brique: str) -> Fiche:
    """La fiche d'un outil en service pour cette brique, sinon un refus en clair."""
    f = fiches().get(outil)
    if f is None or brique not in f.roles:
        raise Refus(f"l'outil « {outil} » n'existe pas pour la brique {brique}")
    if f.etat != "en_service":
        raise Refus(f"l'outil {f.nom} n'est pas en service ({f.etat})")
    return f


def choisir(brique: str, etape: str, du_plan: dict, du_format: dict, de_la_session: dict) -> str:
    from fabrique.noyau.models import Parametre

    outil = (du_plan.get(etape) or du_format.get(etape) or de_la_session.get(f"outil.{brique}") or Parametre.lire(f"outil.{brique}")
             or BRIQUES[brique]["defaut"])
    return fiche(outil, brique).id


def local(brique: str) -> Fiche:
    """L'outil local de repli d'une brique : son défaut s'il est local, sinon le premier outil local en service."""
    candidats = [fiches().get(BRIQUES[brique]["defaut"]), *fiches().values()]
    f = next((f for f in candidats if f and f.local and f.etat == "en_service" and brique in f.roles), None)
    if f is None:
        raise Refus(f"aucun outil local en service pour la brique {brique}")
    return f


def adaptateur(f: Fiche):
    return importlib.import_module(f.module)
