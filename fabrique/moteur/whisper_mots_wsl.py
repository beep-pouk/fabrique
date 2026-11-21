"""Les mots chantés et leur heure (F5, calage des paroles) : Whisper large-v3 du venv Linux de LongCat (déjà là, comme le contrôle des voix de F1),
horodatage par mot de transformers. Lancé dans WSL : python whisper_mots_wsl.py <son.wav> <langue> <dossier de Whisper> <sortie.json>.
Écrit [{mot, debut, fin}]."""
import json
import sys

import torch
from transformers import pipeline

asr = pipeline("automatic-speech-recognition", model=sys.argv[3], device=0, torch_dtype=torch.float16, chunk_length_s=30)
r = asr(sys.argv[1], return_timestamps="word", generate_kwargs={"language": sys.argv[2].split("-")[0], "task": "transcribe"})
mots = [{"mot": c["text"].strip(), "debut": c["timestamp"][0], "fin": c["timestamp"][1] if c["timestamp"][1] is not None else c["timestamp"][0]}
        for c in r["chunks"] if c["text"].strip() and c["timestamp"][0] is not None]
json.dump(mots, open(sys.argv[4], "w", encoding="utf-8"), ensure_ascii=False)
