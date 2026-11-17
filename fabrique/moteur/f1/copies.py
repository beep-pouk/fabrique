"""Ce que le moteur garde de l'ancien production.py (retiré le 12/11/2026).
- moteur/production_copie/ : calques.py, anime_calques.py, lipsync_batch.py, offload.py — le code du moteur (calques 2,5D, Bramble qui parle),
  importé ou envoyé à Linux depuis là.
- Les textes du projet (prompts de LongCat, précisions d'espèce, pelage d'hiver, fond d'écran animé, textes YouTube) : ils nomment des amis, donc
  hors du dépôt. Fabrique (F1) : dans la session (moteur\\production_textes.py, copié par l'import de Bramble Studio), jamais refaits ici.
Importable sans Django."""
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent / "production_copie"


def textes(racine) -> Path:
    """Les textes du projet de la session (définitions lues par les étapes)."""
    f = racine.textes()
    if not f.is_file():
        raise RuntimeError(f"textes du projet introuvables ({f}) : la session n'a pas été importée de Bramble Studio")
    return f
