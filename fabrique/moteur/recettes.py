"""Un format est une recette, une donnée (plan § 5.1) : contrôlée par un schéma versionné (« schema ») avant usage ; ses étapes se jouent dans
l'ordre, chacune « par » plan, scène ou vidéo, refaite pour chaque langue si « langue ». Chaque vidéo garde une copie de la recette qui l'a
faite (session/models.py, Video.recette). Recettes livrées : recettes\\<id>.json ; une autre se donne par son chemin (essai d'un nouveau
format). Le script d'une vidéo a sa forme, nommée par la recette (« scenes-plans-narrateur », « voix-off » : la même, plus par plan une
consigne d'image et un mouvement de caméra ; « presentateur » : un personnage de l'univers parle face caméra, avec des inserts)."""
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


Mouvement = Literal["fixe", "avancee", "recul", "gauche", "droite"]  # la caméra sur une image


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
    script: Literal["scenes-plans-narrateur", "voix-off", "chanson", "presentateur", "scenario-bramble", "compilation", "extrait"]
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
    texte: str = Field(min_length=1, max_length=300)  # ce que la voix dit sur ce plan (une ou deux phrases : la voix lit mal au-delà)
    image: str = Field(min_length=1)  # la consigne de l'image du plan
    mouvement: Mouvement = "avancee"  # la caméra sur l'image


class SceneVoixOff(Scene):
    plans: list[PlanVoixOff] = Field(min_length=1)


class ScriptVoixOff(Script):
    """F4 (et F3 créée seule) : une voix raconte, plan par plan, sur des images animées."""
    scenes: list[SceneVoixOff] = Field(min_length=1)


class PlanPresentateur(Plan):
    texte: str = Field(min_length=1, max_length=300)  # ce que le présentateur dit sur ce plan
    vue: Literal["face", "insert"] = "face"  # face caméra (ses lèvres bougent), ou un insert : une image, sa voix continue
    image: str = ""  # la consigne de l'image d'un insert
    mouvement: Mouvement = "avancee"  # la caméra sur un insert

    @model_validator(mode="after")
    def insert_illustre(self):
        if self.vue == "insert" and not self.image.strip():
            raise ValueError("un insert a une consigne d'image")
        return self


class ScenePresentateur(Scene):
    plans: list[PlanPresentateur] = Field(min_length=1)


class ScriptPresentateur(Script):
    """F6 : un personnage de l'univers de la session parle face caméra, dans son décor, avec des inserts."""
    presentateur: str = Field(min_length=1, max_length=100)  # le nom d'un personnage de l'univers (sa référence validée garde son apparence)
    decor: str = Field(min_length=1)  # où il se tient, face caméra
    scenes: list[ScenePresentateur] = Field(min_length=1)

    @model_validator(mode="after")
    def face_camera(self):
        if not any(p.vue == "face" for sc in self.scenes for p in sc.plans):
            raise ValueError("un présentateur parle face caméra au moins une fois")
        return self


class Section(Strict):
    """Une partie de la chanson : ses paroles (une ligne par vers ; aucune pour une intro), son image et la caméra sur elle."""
    id: Nom
    type: Literal["intro", "couplet", "refrain", "pont", "fin"]
    paroles: list[Annotated[str, Field(pattern=r"^[^\[\]{}]*\S[^\[\]{}]*$", max_length=120)]] = []  # ni [ ] (balises du chant) ni { } (karaoké)
    image: str = Field(min_length=1)
    mouvement: Mouvement = "avancee"
    outils: dict[str, str] = {}  # exception de la section : étape → outil


class StyleMusique(Strict):
    tags: str = Field(min_length=1)  # genre, instruments, voix (« children's song, ukulele, female voice »)
    bpm: int = Field(100, ge=40, le=200)
    tonalite: str = Field("C major", pattern=r"^[A-G](#|b|-sharp|-flat)? (major|minor)$")  # les tonalités que le chant connaît


class Chanson(Strict):
    """F5 : une chanson (paroles par section, style de la musique), ses images animées et ses paroles calées (karaoké)."""
    titre: str
    description: str = ""
    tags: list[str] = []
    musique: StyleMusique
    sections: list[Section] = Field(min_length=1)

    @model_validator(mode="after")
    def chantee(self):
        if not any(s.paroles for s in self.sections):
            raise ValueError("une chanson a des paroles")
        if (s := duree_chantee(self.model_dump())) > DUREE_CHANSON_MAX:
            raise ValueError(f"paroles trop longues : environ {s:.0f} s à {self.musique.bpm} temps par minute, 4 min au plus")
        return self


TEMPS_PAR_LIGNE, TEMPS_SANS_PAROLES = 8, 16  # en temps : une ligne de comptine ≈ 2 mesures, une intro ou une fin ≈ 4
DUREE_CHANSON_MIN, DUREE_CHANSON_MAX = 60, 240


def duree_chantee(sc: dict) -> float:
    """La durée d'une chanson d'après ses lignes, ses sections sans paroles et son tempo (celle demandée au chant)."""
    return sum(TEMPS_PAR_LIGNE * len(s.get("paroles", [])) or TEMPS_SANS_PAROLES for s in sc["sections"]) * 60 / sc["musique"]["bpm"]


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


FORMES = {"scenes-plans-narrateur": Script, "voix-off": ScriptVoixOff, "chanson": Chanson, "presentateur": ScriptPresentateur, "scenario-bramble": ScenarioBramble,
          "compilation": Compilation, "extrait": Extrait}
PAR_PLAN = ("scenes-plans-narrateur", "voix-off", "chanson", "presentateur")  # les formes qui se fabriquent plan par plan (une section de chanson = un plan)


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
    plans, scenes = [u for u, *_ in unites(s, "plan")], [u for u, *_ in unites(s, "scene")]
    if len(set(plans)) != len(plans) or len(set(scenes)) != len(scenes):
        raise Refus("script refusé : deux scènes, deux plans d'une scène ou deux sections ont le même id")
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
    champs propres à la forme (voix-off : image, mouvement ; présentateur : vue, image, mouvement)."""
    if isinstance(s, Chanson):  # une section est un plan et une scène ; son texte : ses paroles
        return [(x.id, x.outils, "\n".join(x.paroles), x.model_dump(include={"type", "image", "mouvement"})) for x in s.sections] if par != "video" else [("", {}, s.titre, {})]
    if par == "plan":
        return [(f"{sc.id}/{p.id}", p.outils, p.texte, p.model_dump(exclude={"id", "texte", "outils"})) for sc in s.scenes for p in sc.plans]
    if par == "scene":
        return [(sc.id, {}, " ".join(p.texte for p in sc.plans), {}) for sc in s.scenes]
    return [("", {}, s.titre, {})]
