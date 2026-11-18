"""Paquets prêts à poster (J4) : pour chaque autre réseau que YouTube (fiches dans reseaux.json : format, durées, poids, texte), la vidéo au
bon format, sa miniature et son texte, à poster à la main depuis le PC ou l'iPhone. Faits après « Approuver » par la tâche détachée légère
« paquets » (priorité basse, sans carte), une publication (vidéo × langue) après l'autre ; un processus tué reprend aux réseaux pas finis.
La vidéo d'un autre format est posée sur son propre fond flouté (jamais rognée : un personnage resterait coupé) ; plus longue que la fiche :
coupée en parties égales, chaque coupe au silence le plus proche (jamais au milieu d'une phrase), si elle en fait au plus « parties_max » ;
sinon pas de paquet, la raison en clair. Le texte (titre, description sans les chapitres de YouTube, mots-clés en hashtags) est fait à la
lecture : une retouche du titre compte aussitôt. Vérifiés par ffprobe à la fin de chaque fichier : format, durée, poids."""
import json
import logging
import math
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from django.db import DatabaseError

from fabrique import dossiers, programme
from fabrique.moteur.faux import programme as exe
from fabrique.noyau import routeur, taches
from fabrique.noyau.models import Session, noter
from fabrique.publication import publication
from fabrique.session import models as m

log = logging.getLogger(__name__)
FICHES = Path(__file__).with_name("reseaux.json")
FENETRE_SILENCE_S = 20  # une coupe cherche un silence à ± 20 s de sa place
AUDIO_KBPS = 128


def outil(*args, delai: int = 3 * 3600) -> str:
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=delai,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode:
        raise RuntimeError(f"{Path(str(args[0])).stem} : {(r.stderr or r.stdout).strip()[-300:]}")
    return r.stdout


def fiches() -> list[dict]:
    return json.loads(FICHES.read_text(encoding="utf-8"))["reseaux"]


def dossier(s: Session, pub: m.Publication) -> Path:
    return publication.final(s, pub).parent.parent.parent / "paquets"


def mesure(f: Path) -> dict:
    """Largeur, hauteur, durée (s), poids (Mo) lus par ffprobe."""
    r = json.loads(outil(exe("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", f))
    return {"largeur": r["streams"][0]["width"], "hauteur": r["streams"][0]["height"], "duree_s": round(float(r["format"].get("duration", 0)), 2),
            "poids_mo": round(f.stat().st_size / 1e6, 2)}


def silences(video: Path) -> list[float]:
    """Le milieu de chaque silence d'au moins 0,4 s (narration : entre deux phrases)."""
    r = subprocess.run([exe("ffmpeg"), "-hide_banner", "-nostats", "-i", str(video), "-vn", "-af", "silencedetect=noise=-35dB:d=0.4", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    debuts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    fins = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return [(a + b) / 2 for a, b in zip(debuts, fins)]


def entre_phrases(video: Path) -> list[float]:
    """Le milieu entre deux phrases de la transcription de l'analyse (une musique sous la narration cache les silences au mixage)."""
    segs = publication.segments(video)
    return [(float(a["end"]) + float(b["start"])) / 2 for a, b in zip(segs, segs[1:])]


def coupes(duree: float, n: int, calmes: list[float], maxi: float) -> list[float]:
    """Bornes de n parties à peu près égales, chaque coupe au silence le plus proche de sa place (± FENETRE_SILENCE_S) sans dépasser `maxi` par partie."""
    bornes = [0.0]
    for k in range(1, n):
        cible = duree * k / n
        proches = [c for c in calmes if abs(c - cible) <= FENETRE_SILENCE_S and max(bornes[-1], duree - (n - k) * maxi) < c <= bornes[-1] + maxi]
        bornes.append(min(proches, key=lambda c: abs(c - cible)) if proches else min(cible, bornes[-1] + maxi))
    if duree - bornes[-1] > maxi:  # les silences ont trop tiré vers le début : parties égales
        bornes = [duree * k / n for k in range(n)]
    return [*bornes, duree]


def cadre(l: int, h: int, largeur: int, hauteur: int) -> str:
    """Filtre ffmpeg : même format → mise à l'échelle ; sinon l'image entière sur son propre fond flouté."""
    if not (l and h):
        raise RuntimeError(f"image illisible ({l}×{h})")
    if abs(l / h - largeur / hauteur) < 0.01:
        return f"scale={largeur}:{hauteur},setsar=1"
    return (f"split[a][b];[a]scale={largeur}:{hauteur}:force_original_aspect_ratio=increase,crop={largeur}:{hauteur},boxblur=20:2[fond];"
            f"[b]scale={largeur}:{hauteur}:force_original_aspect_ratio=decrease[av];[fond][av]overlay=(W-w)/2:(H-h)/2,setsar=1")


def faire_reseau(source: Path, info: dict, fiche: dict, vers: Path, miniature: Path | None, calmes) -> dict:
    """Le paquet d'un réseau : vidéo(s) et miniature dans vers ; rend son état (fait, impossible) et ses fichiers mesurés."""
    duree, maxi = info["duree_s"], fiche["duree_max_s"]
    n = math.ceil(duree / maxi)
    if duree < fiche["duree_min_s"]:
        return {"etat": "impossible", "raison": f"vidéo de {duree:.0f} s : {fiche['nom']} en veut au moins {fiche['duree_min_s']} s"}
    if n > fiche["parties_max"]:
        return {"etat": "impossible", "raison": f"vidéo de {duree / 60:.1f} min : {fiche['nom']} prend {maxi / 60:g} min au plus"
                + (f" ({fiche['parties_max']} parties au plus)" if fiche["parties_max"] > 1 else "") + " — la déclinaison courte s'en chargera"}
    vers.mkdir(parents=True, exist_ok=True)
    bornes = coupes(duree, n, calmes() if n > 1 else [], maxi)
    l, h = fiche["largeur"], fiche["hauteur"]
    fichiers = []
    for i, (a, b) in enumerate(zip(bornes, bornes[1:]), 1):
        f = vers / (f"{source.stem}_{fiche['id']}" + (f"_partie_{i}" if n > 1 else "") + ".mp4")
        kbps = min(5000, int(fiche["poids_max_mo"] * 8000 * 0.9 / max(b - a, 1)) - AUDIO_KBPS)  # 10 % de marge sous le poids ; 5 Mbit/s suffisent à des pastels
        tmp = f.with_suffix(".tmp.mp4")
        outil(exe("ffmpeg"), "-y", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", source, "-filter_complex", cadre(info["largeur"], info["hauteur"], l, h),
              "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-b:v", f"{kbps}k", "-maxrate", f"{kbps}k", "-bufsize", f"{2 * kbps}k",
              "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k", "-movflags", "+faststart", tmp)
        os.replace(tmp, f)
        fichiers.append({"nom": f.name, **mesure(f)})
    if miniature and miniature.is_file():
        mi, tmp = vers / "miniature.jpg", vers / "miniature.tmp.jpg"
        r = json.loads(outil(exe("ffprobe"), "-v", "error", "-show_entries", "stream=width,height", "-of", "json", miniature))["streams"][0]
        outil(exe("ffmpeg"), "-y", "-v", "error", "-i", miniature, "-filter_complex", cadre(r["width"], r["height"], l, h), "-frames:v", "1", "-q:v", "3", tmp)
        os.replace(tmp, mi)
    f = fautes(fichiers, fiche)
    return {"etat": "non conforme" if f else "fait", "fichiers": fichiers, "miniature": "miniature.jpg" if miniature and miniature.is_file() else "", "fautes": f}


def fautes(fichiers: list[dict], fiche: dict) -> list[str]:
    """Ce qu'un fichier aurait de non conforme à la fiche (le contrôle de la recette : vide)."""
    f = []
    for x in fichiers:
        f += [f"{x['nom']} : {x['largeur']}×{x['hauteur']} au lieu de {fiche['largeur']}×{fiche['hauteur']}"] if (x["largeur"], x["hauteur"]) != (fiche["largeur"], fiche["hauteur"]) else []
        f += [f"{x['nom']} : {x['duree_s']} s, plus que {fiche['duree_max_s']} s"] if x["duree_s"] > fiche["duree_max_s"] + 0.5 else []
        f += [f"{x['nom']} : {x['poids_mo']} Mo, plus que {fiche['poids_max_mo']} Mo"] if x["poids_mo"] > fiche["poids_max_mo"] else []
    return f


def texte(pub: m.Publication, fiche: dict, partie: int = 0, parties: int = 1) -> dict:
    """Titre (si le réseau a ce champ) et texte : titre, description sans les lignes de chapitres, hashtags ; coupés aux limites de la fiche."""
    chap = {l for _, l in publication.chapitres(pub.description)}
    corps = re.sub(r"\n{3,}", "\n\n", "\n".join(l for l in pub.description.splitlines() if l.strip() not in chap)).strip()
    tags = " ".join("#" + re.sub(r"\W", "", t) for t in pub.tags[:fiche["hashtags_max"]] if re.sub(r"\W", "", t))
    numero = f" ({partie}/{parties})" if parties > 1 else ""
    titre = (pub.titre + numero)[:fiche["titre_max"]] if fiche["titre_max"] else ""
    tete = "" if titre else pub.titre + numero
    place = fiche["texte_max"] - len(tags) - (2 if tags else 0)
    t = "\n\n".join(x for x in (tete, corps) if x)
    if len(t) > place:
        t = t[:max(place - 1, 0)].rsplit(" ", 1)[0].rstrip() + "…"
    return {"titre": titre, "texte": "\n\n".join(x for x in (t, tags) if x)}


def faire(s: Session, pk: int) -> list[str]:
    """Les paquets pas encore faits d'une publication ; rend les alertes (un réseau en panne n'arrête pas les autres)."""
    with routeur.session(s):
        pub = m.Publication.objects.select_related("video").get(pk=pk)
    source, alertes, faits = publication.final(s, pub) / pub.fichier, [], {**pub.paquets, "_en_cours": True}
    with routeur.session(s):
        m.Publication.objects.filter(pk=pk).update(paquets=faits)
    info = mesure(source)
    cache = {}
    calmes = lambda: cache.setdefault("c", sorted(entre_phrases(source) + silences(source)))  # noqa: E731 — une fois, seulement si une vidéo est coupée
    for fiche in fiches():
        if faits.get(fiche["id"], {}).get("etat") in ("fait", "non conforme", "impossible"):
            continue
        try:
            faits[fiche["id"]] = faire_reseau(source, info, fiche, dossier(s, pub) / fiche["id"], publication.final(s, pub) / pub.miniature if pub.miniature else None, calmes)
        except Exception as e:  # noqa: BLE001 — dit à RT, les autres réseaux continuent
            log.exception("paquet %s de la publication %s", fiche["id"], pk)
            faits[fiche["id"]] = {"etat": "erreur", "raison": str(e)[:300]}
            alertes.append(f"paquet {fiche['nom']} de « {pub.titre} » ({pub.langue}) : {str(e)[:200]}")
        with routeur.session(s):  # « Refaire les paquets » pendant ce temps (marque effacée) : le travail en cours n'écrit pas par-dessus
            if not m.Publication.objects.filter(pk=pk, paquets__has_key="_en_cours").update(paquets=faits):
                return alertes
    faits.pop("_en_cours")
    with routeur.session(s):
        m.Publication.objects.filter(pk=pk, paquets__has_key="_en_cours").update(paquets={**faits, "fini": True})
    return alertes


def suivante(faites: set) -> tuple[Session, int] | None:
    for s in Session.objects.filter(essais=False).order_by("cree"):
        try:
            with routeur.session(s):
                pk = (m.Publication.objects.exclude(paquets__has_key="fini").exclude(pk__in=[p for i, p in faites if i == s.id])
                      .order_by("pk").values_list("pk", flat=True).first())
        except DatabaseError:
            continue
        if pk:
            return s, pk
    return None


def lancer(acteur: str):
    if taches.occupe("paquets"):
        return
    taches.ecrire("paquets", {"etat": "en_cours", "pid": 0, "lancee": datetime.now().isoformat(timespec="seconds")})
    programme.lancer_detache("executer", "paquets", journal=dossiers.donnees() / "journaux" / "sortie_paquets.log")
    noter(acteur, "paquets", quoi="lancés")


def relancer():
    """Boucle du noyau : des paquets à faire (approuvée, ou processus tué) et rien ne les fait."""
    if not taches.occupe("paquets") and suivante(set()):
        lancer("noyau")


def executer() -> int:
    e = taches.lire("paquets")
    if int(e.get("pid", 0)) not in (0, os.getpid()) and taches.vivante(e):
        print("les paquets sont déjà en cours")
        return 3
    taches.priorite_basse()  # ffmpeg hérite de la priorité basse : une fabrication à côté n'est pas ralentie
    taches.ecrire("paquets", {"etat": "en_cours", "pid": os.getpid(), "debut": datetime.now().isoformat(timespec="seconds")})
    faites, alertes = set(), []
    while suite := suivante(faites):
        faites.add((suite[0].id, suite[1]))
        try:
            alertes += faire(*suite)
        except Exception as x:  # noqa: BLE001 — vidéo illisible, base : la publication suivante continue
            log.exception("paquets de la publication %s", suite[1])
            alertes.append(f"paquets de la publication {suite[1]} : {str(x)[:200]}")
            with routeur.session(suite[0]):
                m.Publication.objects.filter(pk=suite[1]).update(paquets={"fini": True, "erreur": str(x)[:300]})
    taches.ecrire("paquets", {"etat": "erreur" if alertes else "faits", "fin": datetime.now().isoformat(timespec="seconds"),
                              "message": " ; ".join(alertes)[:300], "alertes": alertes, "publications": len(faites)})
    print(f"paquets : {len(faites)} publication(s), {len(alertes)} alerte(s)")
    return 1 if alertes else 0


def lister(s: Session, video_id: str) -> list[dict]:
    """Pour la fenêtre et l'iPhone : par langue et par réseau, l'état, les fichiers, la miniature et le texte (fait à la lecture)."""
    with routeur.session(s):
        pubs = list(m.Publication.objects.filter(video_id=video_id).select_related("video").order_by("pk"))
    lignes = []
    for pub in pubs:
        for fiche in fiches():
            p = pub.paquets.get(fiche["id"]) or {"etat": "erreur" if pub.paquets.get("erreur") else "à faire", "raison": pub.paquets.get("erreur", "")}
            n = len(p.get("fichiers", []))
            lignes.append({"publication": pub.pk, "langue": pub.langue, "reseau": fiche["id"], "nom": fiche["nom"], "etat": p["etat"], "raison": p.get("raison", ""),
                           "fichiers": p.get("fichiers", []), "miniature": p.get("miniature", ""), "dossier": str(dossier(s, pub) / fiche["id"]),
                           "textes": [texte(pub, fiche, i, n) for i in range(1, n + 1)] if n > 1 else [texte(pub, fiche)], "fautes": p.get("fautes", [])})
    return lignes


def fichier(s: Session, pk: int, reseau: str, nom: str) -> Path:
    """Un fichier d'un paquet fait (vidéo ou miniature) ; refus pour tout autre nom (jamais un chemin hors du paquet)."""
    from fabrique.garde import Refus

    with routeur.session(s):
        pub = m.Publication.objects.select_related("video").filter(pk=pk).first()
    p = pub.paquets.get(reseau) if pub else None
    p = p if isinstance(p, dict) else {}
    if p.get("etat") not in ("fait", "non conforme") or nom not in [f["nom"] for f in p["fichiers"]] + ([p["miniature"]] if p.get("miniature") else []):
        raise Refus(f"paquet {reseau} : pas de fichier « {nom} »")
    return dossier(s, pub) / reseau / nom
