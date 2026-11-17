"""Une étape d'un épisode par le moteur de l'app (« moteur --etape X <scénario> », une commande par étape dans la tâche) : dossier de rendu
PROJET/rendus/<nom du scénario>, verrou en_cours.lock (un seul rendu par épisode), fond d'écran animé coupé pendant l'étape, lignes de journal.txt
(session « === titre (fichier) : N scenes, M plans », « duree totale prevue », « --- etape X : N min », « === termine ») et de chrono.csv, ComfyUI
arrêté à la fin ; les lignes vont aussi sur la sortie (le journal de la tâche, d'où l'atelier lit la fin du rendu). Sans Django."""
import ast
import json
import subprocess
import time
from pathlib import Path

from fabrique.moteur.f1 import anim, bramble, copies, images, montage, musique, voix
from fabrique.moteur.f1.outils import Outils, charger, composant

ETAPES = ("voix", "poses", "images", "anim", "musique", "bramble", "montage", "miniature", "revue")
AVEC_DUREES = ("anim", "musique", "bramble", "montage", "miniature", "revue")  # = _etapes de production.py (« duree totale prevue »)


def code_production(racine, fonctions: list[str], constantes: tuple[str, ...] = (), **ns) -> dict:
    """Des fonctions (et constantes) des textes du projet (copies.textes : hors du dépôt, elles nomment des amis) compilées seules ; `ns` = ce
    qu'elles lisent d'autre."""
    arbre = ast.parse(copies.textes(racine).read_text(encoding="utf-8"))
    for n in arbre.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in constantes:
            ns[n.targets[0].id] = ast.literal_eval(n.value)
    corps = [n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name in fonctions]
    assert {n.name for n in corps} == set(fonctions), f"absent des textes du projet : {set(fonctions) - {n.name for n in corps}}"
    exec(compile(ast.Module(corps, type_ignores=[]), "production_textes.py", "exec"), ns)  # noqa: S102 — les textes du projet, joués à chaque rendu
    return ns


def fond_anime(racine, actif: bool) -> bool:
    """fond_anime de production.py (Lively coupé pendant un rendu, relancé à la fin s'il tournait)."""
    return code_production(racine, ["fond_anime"], subprocess=subprocess)["fond_anime"](actif)


def textes_youtube(racine, run: Path, data: dict, scenes: list[dict]):
    """L'étape revue après le retrait de production.py : final/youtube.txt (titre avec son suffixe, description, chapitres, crédits obligatoires, tags,
    lu par la publication) par ecrire_textes_youtube et chapitres de production.py ; sa page REVUE.html et ses APPROUVER.bat / REFAIRE.bat sont
    remplacés par l'écran Vérification de l'app."""
    (Path(run) / "final").mkdir(exist_ok=True)
    ns = code_production(racine, ["chapitres", "ecrire_textes_youtube"], ("SUFFIXE_TITRE", "TAGS_PARENTS"), RUN_DIR=Path(run))
    ns["ecrire_textes_youtube"](data, scenes)


MEDIAS = ("voix/*.wav", "clips/*.mp4", "bramble/*.mp4", "montage/*.mp4", "musique/*.wav")


def ranger_coupes(run: Path, o: Outils) -> list[str]:
    """Une étape coupée (Arrêter, extinction du PC) peut laisser un son ou une vidéo à moitié écrits, que l'étape suivante croirait faits (essai du
    13/11 : clip sans « moov atom », gardé par la reprise). Si la session d'avant n'a pas fini (« === termine »), les fichiers illisibles par ffprobe
    sont rangés dans _coupes/<heure>/ : ils seront refaits. Rien n'est effacé."""
    j = run / "journal.txt"
    sessions = [l for l in (j.read_text(encoding="utf-8", errors="replace").splitlines() if j.is_file() else []) if " === " in l]
    if not sessions or "=== termine" in sessions[-1]:
        return []
    ranges = []
    for f in sorted([p for motif in MEDIAS for p in run.glob(motif)] + list(run.glob("images/plan_*.png"))):
        try:
            if f.suffix == ".png":  # une image coupée en pleine écriture : l'étape images la croirait faite, anim échouerait dessus
                from PIL import Image
                try:
                    with Image.open(f) as im:
                        im.load()
                except OSError as e:  # PIL : fichier tronqué ou illisible
                    raise ValueError(f"image illisible : {e}") from e
            else:
                o.duree(f)
        except (RuntimeError, ValueError):
            vers = run / "_coupes" / time.strftime("%Y%m%d_%H%M%S") / f.relative_to(run)
            vers.parent.mkdir(parents=True, exist_ok=True)
            f.rename(vers)
            ranges.append(f.relative_to(run).as_posix())
    return ranges


def jouer(racine, scenario, etape: str, cfg: dict, dossier=None, ecran=print, fond=fond_anime) -> int:
    """L'étape `etape` du scénario par le nouveau moteur, dans PROJET/rendus/<nom> (ou `dossier` : copie de test). 0 si faite ou déjà en cours
    ailleurs (comme production.py) ; une erreur arrête l'étape (exception : « || exit /b 1 » arrête le .bat)."""
    if etape not in ETAPES:
        raise ValueError(f"étape inconnue du nouveau moteur : {etape} (connues : {', '.join(ETAPES)})")
    scenario, cfg = Path(scenario), racine.config(cfg)  # Fabrique : la voix de référence de la session
    run = Path(dossier)  # Fabrique : toujours l'atelier de la vidéo (jamais PROJET\rendus)
    run.mkdir(parents=True, exist_ok=True)
    verrou = open(run / "en_cours.lock", "a+")  # noqa: SIM115 — gardé ouvert (verrouillé) jusqu'à la fin de l'étape, comme production.py
    def log(*a):  # = log de production.py : heure, console en ASCII (console Windows), journal.txt en UTF-8
        msg = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
        ecran(msg.encode("ascii", "replace").decode())
        with open(run / "journal.txt", "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    try:
        try:
            import msvcrt
            msvcrt.locking(verrou.fileno(), msvcrt.LK_NBLCK, 1)
        except ImportError:
            pass
        except OSError:
            ecran("Ce rendu tourne deja : on ne le lance pas deux fois.")
            return 0

        o = Outils(racine)
        data, scenes, plans = charger(o, scenario)
        coupes = ranger_coupes(run, o)
        log(f"=== {data['title']} ({scenario.name}) : {len(scenes)} scenes, {len(plans)} plans")
        if coupes:
            log(f"reprise : {len(coupes)} fichier(s) coupe(s) par l'arret range(s) dans _coupes, a refaire : {', '.join(coupes[:5])}")
        lively = fond(racine, False)
        try:
            t = time.time()
            m = montage.Montage(run, cfg, o)
            if etape in AVEC_DUREES:
                tot = m.durees(scenes)
                log(f"duree totale prevue : {tot / 60:.1f} min")
            if etape == "voix":
                voix.faire(o, run, scenes, cfg)
            elif etape == "poses":  # = etape_poses : les poses se font avec Gemini, jamais ici
                todo = [p for p in sorted({s["bramble"] for s in scenes if s.get("bramble")}) if not (o.poses / f"{p}.png").exists()]
                if todo:
                    raise RuntimeError(f"poses de Bramble manquantes : {todo} -> a faire avec Gemini dans univers/personnages/bramble/poses/ de la session")
                log("poses : deja faites")
            elif etape == "images":
                lus = [json.loads(f.read_text(encoding="utf-8")) for f in (racine.regles(), racine.univers())]
                im = images.Images(run, cfg, o, lus[0], lus[1], images.constantes_production(racine))
                im.log = log
                im.faire(data, scenes, plans)
            elif etape == "anim":
                anim.lancer(racine, run, scenario, cfg, log=log)
            elif etape == "musique":
                musique.faire(o, run, data, tot + m.son_pack().get("queue_s", 0), cfg)
            elif etape == "bramble":
                bramble.faire(racine, run, scenes, cfg, log=log)
            elif etape == "montage":
                m.monter(data, scenes)
            elif etape == "miniature":
                montage.miniature(run, data, scenes, cfg, o)
            elif etape == "revue":
                textes_youtube(racine, run, data, scenes)
                log("revue : textes YouTube ecrits (la page de revue = ecran Verification de l'app)")
            minutes = (time.time() - t) / 60
            log(f"--- etape {etape} : {minutes:.1f} min")
            with open(run / "chrono.csv", "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M')};{etape};{minutes:.1f}\n")
            o.module("kit", "comfy").stop()
            log("=== termine")
            return 0
        finally:
            if lively:
                fond(racine, True)
    except Exception as e:  # l'étape s'arrête : dit dans le journal du rendu (l'Accueil ne la croit plus en cours), puis l'erreur remonte au .bat
        log(f"=== arrete : etape {etape} en erreur ({type(e).__name__} : {e})"[:400])
        try:
            Outils(racine).module("kit", "comfy").stop()  # carte graphique libérée : ComfyUI ne reste pas chargé après une étape en erreur
        except Exception as e2:  # noqa: BLE001 — l'erreur de l'étape reste celle qu'on remonte
            log(f"arret de ComfyUI impossible : {e2}"[:200])
        raise
    finally:
        verrou.close()
