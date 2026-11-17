"""Un format est une recette, une donnée (plan § 5.1) : contrôlée par un schéma versionné (« schema ») avant usage ; ses étapes se jouent dans
l'ordre, chacune « par » plan, scène ou vidéo, refaite pour chaque langue si « langue ». Chaque vidéo garde une copie de la recette qui l'a
faite (session/models.py, Video.recette). Recettes livrées : recettes\\<id>.json ; une autre se donne par son chemin (essai d'un nouveau
format). Le script d'une vidéo a sa forme, nommée par la recette (« scenes-plans-narrateur »)."""
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from fabrique.garde import Refus
from fabrique.moteur import outils
from fabrique.moteur.outils import Strict, controler

SCHEMA = 1
LIVREES = Path(__file__).parent / "recettes"
RESERVES = {"con", "prn", "aux", "nul", *(f"{p}{i}" for p in ("com", "lpt") for i in range(10))}  # noms interdits par Windows


def pas_reserve(nom: str) -> str:
    if nom in RESERVES:
        raise ValueError(f"« {nom} » est un nom réservé par Windows")
    return nom


# des noms de dossiers : minuscules seulement (Windows ne distingue pas « P1 » de « p1 »)
Nom = Annotated[str, Field(pattern=r"^[a-z0-9_-]{1,40}$"), AfterValidator(pas_reserve)]
Langue = Annotated[str, Field(pattern=r"^[a-z]{2,3}(-[a-z0-9]+)?$"), AfterValidator(pas_reserve)]


class Reglages(Strict):
    duree_s: tuple[int, int] | None = None
    cadre: str = "16:9"
    langues: list[Langue] = Field(min_length=1)
    sous_titres: Literal["fichier", "incrustes", "aucun"] = "fichier"
    enfants: bool = True
    declaration_ia: bool = True
    plan_fixe_max_s: float | None = None  # durée maximale à l'écran d'une image sans vrai mouvement : valeur et usage à J3 (F1 v2)


class Etape(Strict):
    id: Nom
    brique: str
    par: Literal["plan", "scene", "video"]
    langue: bool = False


class Recette(Strict):
    schema_: Literal[1] = Field(alias="schema")
    id: str
    nom: str
    version: int = Field(ge=1)
    reglages: Reglages
    script: Literal["scenes-plans-narrateur", "scenario-bramble"]
    etapes: list[Etape] = Field(min_length=1)
    controles: str = ""
    outils: dict[str, str] = {}  # défaut du format : étape → outil

    @model_validator(mode="after")
    def coherente(self):
        ids = [e.id for e in self.etapes]
        if len(set(ids)) != len(ids) or len(set(self.reglages.langues)) != len(self.reglages.langues):
            raise ValueError("deux étapes ont le même id, ou une langue est en double")
        if inconnues := [e.brique for e in self.etapes if e.brique not in outils.BRIQUES]:
            raise ValueError(f"brique inconnue : {', '.join(inconnues)}")
        if etrangeres := set(self.outils) - set(ids):
            raise ValueError(f"outils pour des étapes absentes : {', '.join(sorted(etrangeres))}")
        if self.script == "scenario-bramble" and any(e.par != "video" for e in self.etapes):
            raise ValueError("un scénario de Bramble Studio se fabrique par vidéo entière (par: video) : ses étapes font tous les plans d'un coup")
        return self


class Plan(Strict):
    id: Nom
    texte: str = ""
    outils: dict[str, str] = {}  # exception du plan : étape → outil


class Scene(Strict):
    id: Nom
    plans: list[Plan] = Field(min_length=1)


class Script(Strict):
    titre: str
    scenes: list[Scene] = Field(min_length=1)


class SceneBramble(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int


class ScenarioBramble(BaseModel):
    """Un scénario de Bramble Studio (format 2) : contrôlé en entier par OUTILS\\ecriture\\schema.py à chaque étape de F1 ; ici l'essentiel."""
    model_config = ConfigDict(extra="allow")
    title: str
    scenes: list[SceneBramble] = Field(min_length=1)

    @property
    def titre(self) -> str:
        return self.title


FORMES = {"scenes-plans-narrateur": Script, "scenario-bramble": ScenarioBramble}


def recette(donnees: dict) -> Recette:
    if donnees.get("schema") != SCHEMA:
        raise Refus(f"recette refusée : schéma {donnees.get('schema')!r} inconnu (Fabrique lit le schéma {SCHEMA})")
    r = controler(Recette, donnees, "recette")
    for etape, outil in r.outils.items():
        outils.fiche(outil, next(e.brique for e in r.etapes if e.id == etape))
    return r


def script(donnees: dict, forme: str = "scenes-plans-narrateur") -> Script | ScenarioBramble:
    s = controler(FORMES[forme], donnees, "script")
    if forme != "scenes-plans-narrateur":
        return s
    ids = [(sc.id, p.id) for sc in s.scenes for p in sc.plans]
    if len(set(ids)) != len(ids) or len({sc.id for sc in s.scenes}) != len(s.scenes):
        raise Refus("script refusé : deux scènes ou deux plans d'une scène ont le même id")
    return s


def lire(source: str | Path) -> dict:
    """Une recette livrée (par son id) ou un fichier ; rendue telle quelle après contrôle."""
    chemin = Path(source) if Path(source).suffix == ".json" else LIVREES / f"{source}.json"
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refus(f"recette illisible ({chemin.name}) : {e}") from None
    recette(donnees)
    return donnees


def unites(s: Script, par: str) -> list[tuple[str, dict, str]]:
    """(unité, exception d'outils, texte) de chaque morceau d'une étape « par » plan, scène ou vidéo."""
    if par == "plan":
        return [(f"{sc.id}/{p.id}", p.outils, p.texte) for sc in s.scenes for p in sc.plans]
    if par == "scene":
        return [(sc.id, {}, " ".join(p.texte for p in sc.plans)) for sc in s.scenes]
    return [("", {}, s.titre)]
