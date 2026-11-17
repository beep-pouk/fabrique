"""J19 : copie de controle_voix_wsl.py des scripts d'analyse (non modifié) qui écoute DANS la langue de la version. Lancé dans WSL avec le Python du venv
LongCat (Whisper large-v3 déjà là) : python whisper_langue_wsl.py <lot.json> <dossier de Whisper> ; lot = [{"wav": "/mnt/d/...", "langue": "fr", ...}].
Écrit <lot>_resultat.json avec « entendu » pour chaque wav ; le score est calculé par l'app (moteur/langue_texte.py : écritures normalisées)."""
import json
import sys

import torch
from transformers import pipeline

asr = pipeline("automatic-speech-recognition", model=sys.argv[2], device=0, torch_dtype=torch.float16)
lot = json.load(open(sys.argv[1], encoding="utf-8"))
res = []
for j in lot:
    h = asr(j["wav"], generate_kwargs={"language": j["langue"].split("-")[0], "task": "transcribe"})["text"]
    res.append({**j, "entendu": h})
    print(j["wav"].split("/")[-1], flush=True)
json.dump(res, open(sys.argv[1].replace(".json", "_resultat.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
