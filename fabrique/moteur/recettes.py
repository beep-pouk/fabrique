"""Un format est une recette, une donnée (plan § 5.1) : contrôlée par un schéma versionné (« schema ») avant usage ; ses étapes se jouent dans
l'ordre, chacune « par » plan, scène ou vidéo, refaite pour chaque langue si « langue ». Chaque vidéo garde une copie de la recette qui l'a
faite (session/models.py, Video.recette). Recettes livrées : recettes\\<id>.json ; une autre se donne par son chemin (essai d'un nouveau
format). Le script d'une vidéo a sa forme, nommée par la recette (« scenes-plans-narrateur », « voix-off » : la même, plus par plan une
consigne d'image et un mouvement de caméra)."""
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
    langue: bool | Literal["autres"] = False  # vrai : refaite pour chaque langue ; « autres » : pour chaque langue sauf celle du script


class Recette(Strict):
    schema_: Literal[1] = Field(alias="schema")
    id: str
    nom: str
    version: int = Field(ge=1)
    reglages: Reglages
    script: Literal["scenes-plans-narrateur", "voix-off", "scenario-bramble", "compilation", "extrait"]
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
        if self.script not in PAR_PLAN and any(e.par != "video" for e in self.etapes):
            raise ValueError(f"un script « {self.script} » se fabrique par vidéo entière (par: video) : ses étapes font toute la vidéo d'un coup")
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
    description: str = ""  # textes de publication (titre : « titre »)
    tags: list[str] = []


class PlanVoixOff(Plan):
    texte: str = Field(min_length=1)  # ce que la voix dit sur ce plan
    image: str = Field(min_length=1)  # la consigne de l'image du plan
    mouvement: Literal["fixe", "avancee", "recul", "gauche", "droite"] = "avancee"  # la caméra sur l'image


class SceneVoixOff(Scene):
    plans: list[PlanVoixOff] = Field(min_length=1)


class ScriptVoixOff(Script):
    """F4 (et F3 créée seule) : une voix raconte, plan par plan, sur des images animées."""
    scenes: list[SceneVoixOff] = Field(min_length=1)


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


class Compilation(Strict):
    """F2 : l'introduction inédite (une vidéo finie de la session, faite par son propre format) puis les vidéos finies, dans l'ordre."""
    titre: str
    intro: str = Field(min_length=1)
    videos: list[str] = Field(min_length=2)
    description: str = ""
    tags: list[str] = []

    @model_validator(mode="after")
    def sans_doublon(self):
        if len({self.intro, *self.videos}) != 1 + len(self.videos):
            raise ValueError("une vidéo est citée deux fois (ou l'introduction est aussi parmi les vidéos)")
        return self


class Extrait(Strict):
    """F3 tirée d'une vidéo longue : un passage d'une vidéo finie de la session, 3 min au plus."""
    titre: str
    source: str = Field(min_length=1)
    debut_s: float = Field(ge=0)
    fin_s: float
    description: str = ""
    tags: list[str] = []

    @model_validator(mode="after")
    def court(self):
        if not 1 <= self.fin_s - self.debut_s <= 180:
            raise ValueError("un extrait dure de 1 s à 3 min")
        return self


FORMES = {"scenes-plans-narrateur": Script, "voix-off": ScriptVoixOff, "scenario-bramble": ScenarioBramble, "compilation": Compilation, "extrait": Extrait}
PAR_PLAN = ("scenes-plans-narrateur", "voix-off")  # les formes qui se fabriquent plan par plan


def recette(donnees: dict) -> Recette:
    if donnees.get("schema") != SCHEMA:
        raise Refus(f"recette refusée : schéma {donnees.get('schema')!r} inconnu (Fabrique lit le schéma {SCHEMA})")
    r = controler(Recette, donnees, "recette")
    for etape, outil in r.outils.items():
        outils.fiche(outil, next(e.brique for e in r.etapes if e.id == etape))
    return r


def script(donnees: dict, forme: str = "scenes-plans-narrateur") -> Script | ScenarioBramble:
    s = controler(FORMES[forme], donnees, "script")
    if forme not in PAR_PLAN:
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


def unites(s: Script, par: str) -> list[tuple[str, dict, str, dict]]:
    """(unité, exception d'outils, texte, consigne) de chaque morceau d'une étape « par » plan, scène ou vidéo ; la consigne d'un plan = ses
    champs propres à la forme (voix-off : image, mouvement)."""
    if par == "plan":
        return [(f"{sc.id}/{p.id}", p.outils, p.texte, p.model_dump(exclude={"id", "texte", "outils"})) for sc in s.scenes for p in sc.plans]
    if par == "scene":
        return [(sc.id, {}, " ".join(p.texte for p in sc.plans), {}) for sc in s.scenes]
    return [("", {}, s.titre, {})]
