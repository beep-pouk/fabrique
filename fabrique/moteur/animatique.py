"""L'animatique (étape 3 du plan du 24/11) : l'épisode entier en images fixes, avec ses voix et sa musique, monté sur le processeur en quelques
minutes pour juger le rythme avant toute animation. Montage de F1 (moteur/f1/montage.py) : mêmes durées à l'écran que la vidéo finie (voix + pause +
tenue + silences du pack son), même mixage de la musique ; seule la taille de l'image change (aperçu). Images, voix et musique : celles que Bramble
Studio a rendues pour ce script (lues seulement). Sortie dans la session : animatiques\\<code>.<langue>\\ (la vidéo, plans.json : les repères des
plans, mesurés sur les segments montés) ; les notes de RT, à la seconde : animatiques\\<code>.notes.json. Une animatique à la fois (tâche détachée
« executer animatique »)."""
import json
import logging
import os
import re
import shutil
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from django.conf import settings

from fabrique import dossiers, garde, programme
from fabrique.garde import Refus

log = logging.getLogger(__name__)
TACHE = "animatique"
APERCU = {"largeur": 1280, "hauteur": 720}  # le rythme et le son sont ceux de la vidéo finie ; 4 fois moins de pixels à encoder
LANGUE = re.compile(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,4})?")
CODE = re.compile(r"[\w-]+(\.[A-Za-z0-9-]+)?")  # le code d'un script entre dans des noms de fichiers : ni séparateur ni « .. »
NOTE_MAX = 500
FFMPEG_MAX_S = 900  # un ffmpeg bloqué ne garde pas la tâche « en cours » (elle bloquerait la mise à jour et la restauration)
_notes = threading.Lock()


def dossier(s) -> Path:
    return garde.verifier(settings.SESSIONS / s.dossier / "animatiques")


def verifier_langue(langue: str) -> str:
    if not LANGUE.fullmatch(langue):
        raise Refus(f"langue inconnue : {langue[:20]}")
    return langue


def contenu_du_script(s, code: str) -> dict:
    """Le contenu de la dernière version du script `code` ; refus si le code n'a pas la forme d'un code de script ou s'il est inconnu."""
    from fabrique.noyau import routeur
    from fabrique.session import models as m

    if not CODE.fullmatch(code):
        raise Refus(f"script inconnu : {code[:40]}")
    with routeur.session(s):
        sc = m.Script.objects.filter(code=code).first()
        v = sc.versions.order_by("-numero").first() if sc else None
    if v is None:
        raise Refus(f"script inconnu : {code}")
    return v.contenu


def faire(s, code: str, langue: str, contenu: dict, avancer=lambda fait, tout: None) -> Path:
    """Monte l'animatique de `code` en `langue` ; rend la vidéo. Refus si une voix manque ou si aucune image n'est rendue."""
    from fabrique.moteur.f1 import montage
    from fabrique.moteur.f1.outils import Lieux, Outils, ids_entiers
    from fabrique.moteur.f1.refaire import planche
    from fabrique.session import bramble

    scenes = [dict(sc) for sc in contenu.get("scenes", [])]
    if not scenes:
        raise Refus("ce script n'a pas encore de scènes")
    ids_entiers(scenes, code)
    r = bramble.rendus(code, langue)
    if manque := [sc["id"] for sc in scenes if sc["id"] not in r["voix"]]:
        raise Refus(f"les voix en {langue} ne sont pas encore faites pour {len(manque)} scène(s) (la première : {manque[0]})")
    images = {int(n): Path(f) for n, f in r["images"].items()}
    if not images:
        raise Refus("aucune image n'est encore rendue pour ce script")
    session = settings.SESSIONS / s.dossier
    sortie = dossier(s) / f"{code}.{langue}"
    travail = sortie / "_travail"
    shutil.rmtree(travail, ignore_errors=True)
    try:
        (travail / "voix").mkdir(parents=True)
        (travail / "montage").mkdir()
        for sc in scenes:
            shutil.copy2(r["voix"][sc["id"]], travail / "voix" / f"s{sc['id']:03d}.wav")
        if r.get("musique"):
            shutil.copy2(r["musique"], travail / "musique.wav")
        o = Outils(Lieux(garde.studio_bramble() or dossiers.racine().parent, session))
        run = o.run
        o.run = lambda cmd, **kw: run(cmd, timeout=FFMPEG_MAX_S, **kw)
        plans = planche(contenu)
        par_scene = {i: images[p["n"]] for p in plans if p["n"] in images for i in p["scenes"]}
        precedente = images[min(images)]
        for i, sc in enumerate(scenes):  # une scène sans image rendue garde celle d'avant, comme la planche ; une scène de Bramble : sa pose
            precedente = par_scene.get(sc["id"], precedente)
            pose = o.poses / f"{sc['bramble']}.png" if sc.get("bramble") else None
            sc["_source"] = str(pose if pose and pose.is_file() else precedente)
            sc["_ep_debut"], sc["_ep_fin"] = i == 0, i == len(scenes) - 1
        cfg = json.loads((session / "reglages" / "config.json").read_text(encoding="utf-8"))
        cfg = {**cfg, "sortie": {**cfg["sortie"], **APERCU}, "montage": {}}  # ni étalonnage ni grain : un aperçu
        m = montage.Montage(travail, cfg, o)
        total = m.durees(scenes)
        for k, sc in enumerate(scenes):
            segment = travail / "montage" / f"s{sc['id']:03d}.mp4"
            m.segment(sc, segment)
            sc["_reel"] = o.duree(segment)  # les images entières et le son arrondissent : la frise suit la vidéo, pas la théorie
            avancer(k + 1, len(scenes) + 1)
        fini = m.monter({"title": "animatique"}, scenes)
        plan_de = {i: p["n"] for p in plans for i in p["scenes"]}
        reperes, t = [], 0.0  # dans l'ordre des scènes : un plan coupé par une réplique de Bramble fait deux passages à l'écran
        for sc in scenes:
            n = plan_de.get(sc["id"], sc["id"])
            if reperes and reperes[-1]["n"] == n:
                reperes[-1]["duree"] += sc["_reel"]
            else:
                reperes.append({"n": n, "debut": t, "duree": sc["_reel"]})
            t += sc["_reel"]
        reperes = [{**r, "debut": round(r["debut"], 3), "duree": round(r["duree"], 3)} for r in reperes]
        video = sortie / f"animatique_{datetime.now():%Y%m%d_%H%M%S}.mp4"  # un nom neuf : l'ancienne peut être en lecture dans la fenêtre
        os.replace(fini, video)
        (sortie / "plans.json").write_text(json.dumps({"video": video.name, "date": datetime.now().isoformat(timespec="minutes"), "total": round(total, 3),
                                                       "fin": round(o.duree(video), 3), "plans": reperes}, ensure_ascii=False), encoding="utf-8")
    finally:
        shutil.rmtree(travail, ignore_errors=True)  # le montage ne reprend rien : rien à garder, même après un échec
    for f in sortie.glob("animatique_*.mp4"):
        if f != video:
            try:
                f.unlink()
            except OSError:  # en lecture dans la fenêtre : retirée au prochain montage
                pass
    return video


def lancer(s, code: str, langue: str, acteur: str) -> str:
    from fabrique.noyau import taches
    from fabrique.noyau.models import noter

    if taches.occupe(TACHE):
        raise Refus("une animatique est déjà en train de se monter : relancer celle-ci quand elle sera finie")
    taches.ecrire(TACHE, {"etat": "en_cours", "pid": 0, "lancee": datetime.now().isoformat(timespec="seconds"), "session": s.id, "code": code, "langue": langue})
    programme.lancer_detache("executer", TACHE, s.id, code, langue, journal=dossiers.donnees() / "journaux" / "sortie_animatique.log")
    noter(acteur, TACHE, session=s.id, code=code, langue=langue)
    return "L'animatique se monte : quelques minutes."


def executer(session_id: str = "", code: str = "", langue: str = "") -> int:
    from fabrique.noyau import taches
    from fabrique.noyau.models import Session

    e0 = taches.lire(TACHE)
    if int(e0.get("pid", 0)) not in (0, os.getpid()) and taches.vivante(e0):
        print("une animatique est déjà en cours")
        return 3
    taches.priorite_basse()  # sur le processeur, à côté d'un rendu (ffmpeg en hérite)
    e = {"etat": "en_cours", "pid": os.getpid(), "lancee": datetime.now().isoformat(timespec="seconds"), "session": session_id, "code": code, "langue": langue}
    taches.ecrire(TACHE, e)
    try:
        s = Session.objects.get(id=session_id)
        video = faire(s, code, verifier_langue(langue), contenu_du_script(s, code), avancer=lambda f, t: taches.ecrire(TACHE, {**e, "fait": f, "tout": t}))
    except Exception as x:  # noqa: BLE001 — dite à RT (écran Épisode), le détail dans le journal
        log.exception("animatique ratée")
        taches.ecrire(TACHE, {**e, "etat": "erreur", "fin": datetime.now().isoformat(timespec="seconds"),
                              "message": str(x)[:300] if isinstance(x, (Refus, ValueError)) else "le montage a échoué (détail dans le journal de Fabrique)"})
        return 1
    taches.ecrire(TACHE, {**e, "etat": "faite", "fin": datetime.now().isoformat(timespec="seconds")})
    print(f"animatique faite : {video}")
    return 0


def etat(s, code: str, langue: str) -> dict:
    """Pour l'écran Épisode : où en est l'animatique de `code` en `langue`, sa vidéo et ses repères s'il y en a une, les notes de RT."""
    from fabrique.noyau import taches

    sortie = dossier(s) / f"{code}.{langue}"
    t = taches.lire(TACHE)
    ici = (t.get("session"), t.get("code"), t.get("langue")) == (s.id, code, langue)
    try:
        p = json.loads((sortie / "plans.json").read_text(encoding="utf-8"))
        p = p if (sortie / p["video"]).is_file() else {}
    except (OSError, ValueError, KeyError, TypeError):
        p = {}
    vivante = taches.vivante(t)
    en_cours, morte = ici and vivante, ici and t.get("etat") == "en_cours" and not vivante
    message = "le montage s'est arrêté sans finir (détail dans le journal de Fabrique)" if morte else t.get("message", "") if ici else ""
    return {"etat": "en_cours" if en_cours else "erreur" if ici and (morte or t.get("etat") == "erreur") else "faite" if p else "absente",
            "message": message, "fait": t.get("fait", 0) if en_cours else 0, "tout": t.get("tout", 0) if en_cours else 0,
            "autre": bool(vivante and not ici), "video": str(sortie / p["video"]) if p else "", "date": p.get("date", ""),
            "fin": p.get("fin", 0.0), "plans": p.get("plans", []), "notes": lire_notes(s, code)}


def _fichier_notes(s, code: str) -> Path:
    return dossier(s) / f"{code}.notes.json"


def lire_notes(s, code: str, strict: bool = False) -> list[dict]:
    """Les notes du script ; `strict` (avant d'écrire) : un fichier illisible est refusé au lieu d'être pris pour vide (il serait écrasé)."""
    try:
        return json.loads(_fichier_notes(s, code).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError):
        if strict:
            raise Refus("les notes de ce script sont illisibles : rien n'est écrit (fichier .notes.json des animatiques)") from None
        return []


def noter_a(s, code: str, t: float, texte: str, langue: str) -> list[dict]:
    texte = " ".join(texte.split())
    if not texte:
        raise Refus("la note est vide")
    if len(texte) > NOTE_MAX:
        raise Refus(f"la note dépasse {NOTE_MAX} caractères")
    if not (0 <= t < 24 * 3600):
        raise Refus("moment de la note hors de la vidéo")
    with _notes:
        notes = lire_notes(s, code, strict=True)
        notes.append({"id": uuid.uuid4().hex[:12], "t": round(t, 1), "texte": texte, "langue": verifier_langue(langue),
                      "date": datetime.now().isoformat(timespec="minutes")})
        notes.sort(key=lambda n: n["t"])
        _ecrire_notes(s, code, notes)
    return notes


def retirer_note(s, code: str, note: str) -> list[dict]:
    """Retire la note `note` (son identifiant : un double clic ne retire jamais la voisine)."""
    with _notes:
        notes = lire_notes(s, code, strict=True)
        reste = [n for n in notes if n.get("id") != note]
        if len(reste) == len(notes):
            raise Refus("note inconnue (déjà retirée ?)")
        _ecrire_notes(s, code, reste)
    return reste


def _ecrire_notes(s, code: str, notes: list[dict]):
    f = _fichier_notes(s, code)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(notes, ensure_ascii=False, indent=1), encoding="utf-8")
    for i in range(10):  # Windows : un lecteur (sauvegarde du soir) tient le fichier un instant
        try:
            tmp.replace(f)
            return
        except PermissionError:
            if i == 9:
                raise
            time.sleep(0.1)
