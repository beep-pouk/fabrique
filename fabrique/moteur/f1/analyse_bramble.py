"""Le contrôle de F1 : l'analyse que Bramble Studio lance après chaque rendu (core/verification.py, 1.5.6), jouée ici comme une étape de la
recette, sur la vidéo finale de l'atelier : analyser_video.py (sans carte, dans Linux : durée, son, images noires ou figées → alertes minutées,
planches), ANALYSER_QWEN.bat (Qwen regarde la vidéo par morceaux, note sur 10) et transcrire.bat (Whisper) — les scripts d'OUTILS\\analyse
tels quels, lancés comme Bramble les lance, chacun sauté si sa sortie existe (reprise). Défauts minutés = alertes + morceaux Qwen sous le seuil,
gravités de Bramble ; note = moyenne de Qwen. Pas joués ici : Gemini (le soir, en ligne, quota) et la relecture écrite à la main (RT coche
dans Vérification)."""
import json
import re
from pathlib import Path

from fabrique import dossiers, garde
from fabrique.moteur.f1.adaptateur import estimer, lier  # noqa: F401 — estimer : celui des étapes de Bramble (secondes de la fiche)
from fabrique.moteur.f1.outils import Lieux, Outils, composant, dans_wsl, wsl
from fabrique.moteur.outils import Demande, Fiche, Resultat

SEUIL_QWEN = 6.0  # = SEUIL_QWEN_DEFAUT de Bramble (son réglage « seuil_qwen » n'a jamais été changé)

# ---- lecture des fichiers d'analyse : repris de Bramble Studio (core/verification.py), à l'identique ----
TEMPS = re.compile(r"(\d+):(\d{2})(?::(\d{2}))?")
DUREE = re.compile(r"Durée : (\d+) min (\d+(?:[.,]\d+)?) s")  # = analyser_video.py : f"{duree / 60:.0f} min {duree % 60:04.1f} s"
ALERTE = re.compile(r"^- (.+?) à (\d+(?:\.\d+)?) s$")  # « - image figée 3.2 s à 1092.9 s » ; « - volume global … » sans heure


def _nombre(texte: str) -> float:
    return float(texte.replace(",", "."))


def lire_json(chemin: Path):
    return json.loads(chemin.read_text(encoding="utf-8-sig")) if chemin.is_file() else None


def mmss(s: float) -> str:
    return f"{int(s) // 60:02d}:{int(s) % 60:02d}"


def video(atelier: Path) -> Path | None:
    """La vidéo finale : le .mp4 le plus récent de final/ (pas ses sous-dossiers : parties pour Gemini)."""
    return max((atelier / "final").glob("*.mp4"), key=lambda p: p.stat().st_mtime, default=None)


def a_cote(v: Path, ext: str) -> Path:
    return v.with_name(v.stem + ext)


def dossier_analyse(v: Path) -> Path:
    """Le dossier d'analyser_video.py : analyse_<nom de la vidéo>, espaces remplacés par _."""
    return v.parent / f"analyse_{v.stem.replace(' ', '_')}"


def duree_rapport(texte: str) -> float | None:
    """« Durée : M min S s » d'analyser_video.py, qui ARRONDIT les minutes : une minute de moins dès que S dépasse 30 s ; ambigu : None."""
    m = DUREE.search(texte)
    if not m:
        return None
    minutes, s = int(m.group(1)), _nombre(m.group(2))
    if s == 30 and minutes:
        return None
    d = 60 * (minutes - (1 if s > 30 else 0)) + s
    return d if d >= 0 else None


def rapport(v: Path) -> dict | None:
    """analyse_<nom>/rapport.md : texte, durée, alertes de « ## Alertes » (sans heure pour le volume global ou la crête), planches."""
    f = dossier_analyse(v) / "rapport.md"
    if not f.is_file():
        return None
    texte = f.read_text(encoding="utf-8", errors="replace")
    alertes, dedans = [], False
    for l in texte.splitlines():
        if l.startswith("## "):
            dedans = l.startswith("## Alertes")
        elif dedans and l.startswith("- ") and l.strip() != "- aucune":
            a = ALERTE.match(l.strip())
            t = float(a.group(2)) if a else None
            alertes.append({"temps_s": t, "temps": mmss(t) if t is not None else "", "texte": (a.group(1) if a else l[2:]).strip()})
    planches = sorted(p.name for p in dossier_analyse(v).glob("*.jpg"))
    return {"texte": texte, "duree_s": duree_rapport(texte), "alertes": alertes, "planches": planches}


def _instant(valeur, defaut: float) -> float:
    if isinstance(valeur, (int, float)):
        return float(valeur)
    m = TEMPS.search(valeur) if isinstance(valeur, str) else None
    if not m:
        return defaut
    h, mn, s = (m.group(3) is not None and int(m.group(1))), int(m.group(2) if m.group(3) is not None else m.group(1)), int(m.group(3) or m.group(2))
    return float(h * 3600 + mn * 60 + s)


def qwen(v: Path, duree_s: float | None) -> list[dict]:
    """Morceaux de <video>.qwen.json : nom, score, avis, début et fin (debut/duree du fichier, sinon découpe égale de la durée)."""
    try:
        d = lire_json(a_cote(v, ".qwen.json"))
    except ValueError:
        return []
    if not isinstance(d, dict):
        return []
    morceaux = [(nom, m) for nom, m in d.items() if isinstance(m, dict) and isinstance(m.get("score"), (int, float))]
    part, resultat = (duree_s or 0) / max(len(morceaux), 1), []
    for i, (nom, m) in enumerate(morceaux):  # qwen_video.py : clé « 0020.0 », score, defects [{t, severity, what}], debut, duree
        debut = _instant(m.get("debut"), i * part)
        fin = debut + float(m["duree"]) if isinstance(m.get("duree"), (int, float)) else (i + 1) * part
        avis = m.get("avis") or m.get("commentaire") or "; ".join(str(x.get("what", "")) for x in m.get("defects", []) if isinstance(x, dict) and x.get("what"))
        resultat.append({"nom": nom, "score": float(m["score"]), "avis": str(avis), "debut": debut, "fin": _instant(m.get("fin"), fin)})
    return resultat


def note_qwen(morceaux: list[dict]) -> float | None:
    return round(sum(m["score"] for m in morceaux) / len(morceaux), 1) if morceaux else None
# ---- fin de la reprise ----


def defauts(rap: dict | None, morceaux: list[dict]) -> list[dict]:
    """Comme defauts() de Bramble, sans la relecture écrite : alerte minutée = moyenne, sans heure (volume global) = légère ; morceau Qwen sous
    le seuil = moyenne, à plus de 2 points dessous = forte. Par temps, les alertes sans heure à la fin."""
    d = [{"debut": a["temps_s"], "fin": None, "code": "alerte", "source": "analyser_video", "gravite": "moyenne" if a["temps_s"] is not None else "legere",
          "texte": a["texte"]} for a in (rap or {}).get("alertes", [])]
    d += [{"debut": m["debut"], "fin": m["fin"], "code": "qwen", "source": "Qwen", "gravite": "forte" if m["score"] < SEUIL_QWEN - 2 else "moyenne",
           "texte": f"{m['nom']} : Qwen {m['score']:g}/10 (seuil {SEUIL_QWEN:g}) {m['avis']}".strip()} for m in morceaux if m["score"] < SEUIL_QWEN]
    return sorted(d, key=lambda x: (x["debut"] is None, x["debut"] or 0))


def commandes(lieux: Lieux, v: Path, script: Path) -> list[tuple[Path, list[str]]]:
    """(sortie attendue, commande) dans l'ordre de Bramble : analyser_video.py dans Linux avec le Python du pipeline (PIL compris, comme
    commandes_analyse), puis ANALYSER_QWEN.bat et transcrire.bat dans leur cmd (commandes_qwen) ; un .bat rend toujours 0 : la sortie fait foi."""
    analyse = composant(lieux, "analyse")
    python = dans_wsl("longcat", "venv/bin/python")
    lancer = f'exec {python} "$(wslpath -a "$0")" "$(wslpath -a "$1")" --scenario "$(wslpath -a "$2")"'
    return [(dossier_analyse(v) / "rapport.md", wsl(lancer) + [str(analyse / "analyser_video.py"), str(v), str(script)]),
            (a_cote(v, ".qwen.md"), ["cmd", "/c", "ANALYSER_QWEN.bat", str(v)]),
            (a_cote(v, ".transcription.json"), ["cmd", "/c", "transcrire.bat", str(v)])]


def fabriquer(fiche: Fiche, demande: Demande, dossier: Path) -> Resultat:
    atelier = Path(demande.atelier)
    garde.verifier(atelier)
    lieux = Lieux(garde.studio_bramble() or dossiers.racine().parent, Path(demande.session))
    v = video(atelier)
    if v is None:
        raise RuntimeError("aucune vidéo finale dans l'atelier : le montage n'a rien rendu")
    outils_ = Outils(lieux)
    for sortie, cmd in commandes(lieux, v, Path(demande.script)):
        if not sortie.is_file():
            outils_.run(cmd, cwd=str(composant(lieux, "analyse")))
            if not sortie.is_file():
                raise RuntimeError(f"{sortie.name} n'a pas été écrit ({cmd[2] if cmd[0] == 'cmd' else 'analyser_video.py'}) : son journal le dit")
    rap = rapport(v)
    morceaux = qwen(v, (rap or {}).get("duree_s") or outils_.duree(v))
    d, note = defauts(rap, morceaux), note_qwen(morceaux)
    fichiers = ["rapport.json"]
    for p in [dossier_analyse(v) / "rapport.md", *(dossier_analyse(v) / x for x in (rap or {}).get("planches", []))]:
        lier(p, dossier / "analyse" / p.name)
        fichiers.append(f"analyse/{p.name}")
    (dossier / "rapport.json").write_text(json.dumps({"note": note, "juge": "Qwen", "defauts": d, "analyse": "complete", "video": str(v)}, ensure_ascii=False),
                                         encoding="utf-8")
    return Resultat(fichiers=fichiers, duree_s=(rap or {}).get("duree_s"), infos={"defauts": d, "note": note})
