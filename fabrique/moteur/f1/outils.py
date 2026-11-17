"""Ce que le nouveau moteur (J9) partage avec production.py : les outils du PC (ffmpeg / ffprobe d'OUTILS\\ffmpeg, poses de Bramble, papier,
police), le lanceur de commandes (chaque commande notée pour les tests d'égalité), les modules d'OUTILS importés en lecture (rien d'écrit, pas de
__pycache__) et le chargement du scénario (= charger de production.py, avec le vrai schema.py d'OUTILS\\ecriture). Sans Django : importable par le
Python de production.py.
Fabrique (F1) : « racine » est un Lieux : les outils partagés sous le dossier du studio (lus seulement) et le projet (personnages, univers.json,
textes, règles) dans la session."""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

_REGISTRE = json.loads(Path(__file__).with_name("outils_partages.json").read_text(encoding="utf-8"))
COMPOSANTS = {c["cle"]: c for c in _REGISTRE["composants"]}


class Lieux:
    """Où F1 lit : `studio` (os.fspath : la « racine » du moteur de Bramble, pour ses outils partagés) et `session` (le projet repris)."""

    def __init__(self, studio, session):
        self.studio, self.session = Path(studio), Path(session)

    def __fspath__(self) -> str:
        return str(self.studio)

    def univers(self) -> Path:
        return self.session / "univers" / "univers.json"

    def personnages(self) -> Path:
        return self.session / "univers" / "personnages"

    def textes(self) -> Path:
        return self.session / "moteur" / "production_textes.py"

    def regles(self) -> Path:
        return self.session / "reglages" / "regles.json"


def composant(racine, cle: str, *relatif) -> Path:
    """Où est un outil partagé (outils_partages.json) sur ce PC, puis `relatif` dedans : sous le dossier du studio, ou absolu. Sans Django : lu
    aussi par le Python de ComfyUI (anim.py)."""
    c = COMPOSANTS[cle]
    return (Path(c["chemin"]) if c["ou"] == "absolu" else Path(racine) / c["chemin"]).joinpath(*relatif)


def wsl(commande: str) -> list[str]:
    """Une commande bash jouée dans la distribution Linux de l'app."""
    return ["wsl", "-d", _REGISTRE["wsl_distribution"], "-u", "root", "--exec", "bash", "-c", commande]


def dans_wsl(cle: str, *relatif: str) -> str:
    """Le chemin d'un composant de Linux, dans la distribution."""
    return "/".join([COMPOSANTS[cle]["chemin"], *relatif])


class Outils:
    def __init__(self, racine: Lieux):
        self.racine = racine
        exe = lambda nom: str(p) if (p := composant(racine, "ffmpeg", f"{nom}.exe")).is_file() else (shutil.which(nom) or nom)  # noqa: E731 — PATH : tests sous Linux
        self.ffmpeg, self.ffprobe = exe("ffmpeg"), exe("ffprobe")
        self.poses = racine.personnages() / "bramble" / "poses"
        self.papier = composant(racine, "production", "papier.png")
        self.police = composant(racine, "polices", "Fredoka.ttf")
        self.python = composant(racine, "comfyui", "python_embeded", "python.exe")  # celui des calques (ses numpy, scipy, Pillow)
        self.commandes: list[list[str]] = []

    def run(self, cmd, **kw) -> str:
        """= run de production.py (erreur si la commande échoue), la commande notée ; sans fenêtre de console (le worker tourne sans console)."""
        cmd = [str(c) for c in cmd]
        self.commandes.append(cmd)
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), **kw)
        if r.returncode != 0:
            raise RuntimeError(f"echec : {' '.join(cmd)[:300]}\n{(r.stderr or r.stdout)[-3000:]}")
        return r.stdout

    def duree(self, chemin) -> float:
        return float(self.run([self.ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(chemin)]).strip())

    def module(self, cle: str, nom: str):
        """<nom>.py du composant `cle` (kit, scripts d'écriture) importé tel quel, sans rien écrire à côté (sys.dont_write_bytecode)."""
        if (cle, nom) == ("kit", "comfy"):  # Fabrique : le lanceur de ComfyUI repris (comfy.py), son journal chez elle, jamais sous OUTILS
            from fabrique.moteur.f1 import comfy

            return comfy.pour(self.racine)
        chemin = composant(self.racine, cle, f"{nom}.py")
        spec = importlib.util.spec_from_file_location(f"outils_{cle}_{nom}", chemin)
        m = importlib.util.module_from_spec(spec)
        bytecode, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        try:
            spec.loader.exec_module(m)
        finally:
            sys.dont_write_bytecode = bytecode
        return m


class ComfySimule:
    """ComfyUI simulé (niveau « consigne » des tests d'égalité) : note chaque consigne, rend une copie de l'image donnée ; références copiées dans
    <dossier>/_comfy/ComfyUI/input (jamais dans le vrai ComfyUI)."""

    def __init__(self, dossier: Path, fausse: Path):
        self.CUI, self.fausse, self.consignes, self.entrees = str(Path(dossier) / "_comfy"), Path(fausse), [], []
        (Path(self.CUI) / "ComfyUI" / "input").mkdir(parents=True, exist_ok=True)

    def start(self, *a, **k):
        pass

    def run(self, prompt, **kw):
        self.consignes.append(json.loads(json.dumps(prompt)))
        e = Path(self.CUI) / "ComfyUI" / "input"  # md5 des références à chaque consigne : prod_ref1.png… sont écrasées d'un plan à l'autre
        self.entrees.append({f.name: hashlib.md5(f.read_bytes()).hexdigest() for f in sorted(e.iterdir()) if f.is_file()})
        p = Path(self.CUI) / f"sortie_{len(self.consignes)}.png"
        shutil.copy(self.fausse, p)
        return [str(p)]


def ids_entiers(scenes: list[dict], nom: str):
    """Les fichiers d'une scène portent son numéro (s003.wav) : un identifiant en texte ("3") est refusé en clair, avant toute fabrication."""
    if mauvais := [s["id"] for s in scenes if type(s["id"]) is not int]:
        raise ValueError(f"{nom} : l'identifiant d'une scène (\"id\") doit être un nombre entier, sans guillemets (trouvé : {mauvais[:3]})")


def charger(outils: Outils, chemin: Path) -> tuple[dict, list[dict], list[tuple[int, int]]]:
    """= charger de production.py : scénario validé par schema.py, plans (scènes consécutives qui montrent la même chose), fondu au noir au tout début
    et à la toute fin."""
    schema = outils.module("ecriture", "schema")
    data = json.load(open(chemin, encoding="utf-8"))
    schema.validate(data)
    scenes = data["scenes"]
    ids_entiers(scenes, Path(chemin).name)
    plans = schema.shots(scenes)
    for k, (i0, i1) in enumerate(plans):
        for i in range(i0, i1 + 1):
            scenes[i]["_plan"] = k
            scenes[i]["_premier"] = i == i0
            scenes[i]["_dernier"] = i == i1
    for i, sc in enumerate(scenes):
        sc["_ep_debut"] = i == 0
        sc["_ep_fin"] = i == len(scenes) - 1
    return data, scenes, plans
