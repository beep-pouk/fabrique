"""Ce que le moteur garde de l'ancien production.py (retiré le 12/11/2026).
- moteur/production_copie/ : calques.py, anime_calques.py, lipsync_batch.py, offload.py — le code du moteur (calques 2,5D, Bramble qui parle),
  importé ou envoyé à Linux depuis là.
- Les textes du projet (prompts de LongCat, précisions d'espèce, pelage d'hiver, fond d'écran animé, textes YouTube) : ils nomment des amis, donc
  hors du dépôt, dans <données>/moteur/production_textes.py. Sur un PC où ce fichier manque, il est fait une fois depuis le production.py du
  dossier des réglages de fabrication, s'il y est encore ; sinon l'erreur dit quoi copier.
Importable sans Django."""
import ast
from pathlib import Path

from fabrique.moteur.f1.outils import composant

DOSSIER = Path(__file__).resolve().parent / "production_copie"
TEXTES = ("LIPSYNC_ACTION", "prompt_longcat", "PRECIS", "HIVER_DEPUIS", "fond_anime", "SUFFIXE_TITRE", "TAGS_PARENTS", "chapitres", "ecrire_textes_youtube")


def _nom(n) -> str:
    if isinstance(n, ast.FunctionDef):
        return n.name
    if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
        return n.targets[0].id
    return ""


def morceaux(source: str) -> list[str]:
    """Le texte exact, dans l'ordre du fichier, de chaque définition de TEXTES (une seule fois chacune)."""
    vus, out = set(), []
    for n in ast.parse(source).body:
        if _nom(n) in TEXTES and _nom(n) not in vus:
            vus.add(_nom(n))
            out.append(ast.get_source_segment(source, n))
    return out


def textes(racine, donnees=None) -> Path:
    """<données>/moteur/production_textes.py : les textes du projet (définitions de TEXTES).
    `donnees` : le dossier des données de l'app, à donner pour un appel sans Django."""
    if donnees is None:
        from django.conf import settings  # tardif : ce module reste importable par un Python sans Django (celui de ComfyUI : moteur/anim.py)

        donnees = settings.DATA_DIR
    f = Path(donnees) / "moteur" / "production_textes.py"
    if not f.is_file():
        origine = composant(racine, "production", "production.py")
        if not origine.is_file():
            raise RuntimeError(f"textes du projet introuvables : copier production_textes.py d'un autre PC dans {f.parent} (ni lui ni {origine} ne sont là)")
        source = origine.read_text(encoding="utf-8")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("# Textes du projet lus par le moteur de l'app (moteur/copies.py) ; hors git : ils nomment des amis.\n\n"
                     + "\n\n\n".join(morceaux(source)) + "\n", encoding="utf-8")
    return f
