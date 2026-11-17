"""Banc des voix (10/11) : voix d'une langue par Qwen3-TTS 1.7B (Alibaba Qwen, Apache 2.0), Python du venv du composant « qwen_tts » :
outil « qwen3_tts » = clonage de la voix 1 (poids …\\qwen3_tts\\base ; reglages.ref_texte = texte de la référence) ;
outil « qwen3_design » = voix native décrite (poids …\\qwen3_tts\\design), convertie ensuite vers la voix 1 par vc_chatterbox.py.
python tts_qwen.py <jobs.json> (même lot que tts_chatterbox_mtl.py ; « outil » déduit de reglages : ref_texte → clonage)."""
import json
import sys

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

NOMS = {"es": "Spanish", "pt": "Portuguese", "fr": "French", "de": "German", "ja": "Japanese", "it": "Italian", "ko": "Korean"}
ACCENT = {"es": "Latin American Spanish", "pt": "Brazilian Portuguese", "fr": "standard French from France", "de": "standard German",
          "ja": "standard Tokyo Japanese", "it": "standard Italian", "ko": "standard Seoul Korean"}
DESC = ("A gentle, warm young woman, a native speaker of {a} with no foreign accent, reading a bedtime story to a small child: "
        "soft, slow, calm and soothing, clear articulation, smiling tone.")  # même description qu'au banc (banc_qwen_design.py)
c = json.load(open(sys.argv[1], encoding="utf-8"))
r = c.get("reglages", {})
clone = bool(r.get("ref_texte"))
m = Qwen3TTSModel.from_pretrained(c["poids"] + "\\qwen3_tts" + ("\\base" if clone else "\\design"), device_map="cuda:0", dtype=torch.bfloat16)
for j in c["jobs"]:
    l = j["langue"].split("-")[0]
    torch.manual_seed(j.get("seed", 42))
    if clone:
        wavs, sr = m.generate_voice_clone(text=j["text"], language=NOMS[l], ref_audio=c["ref"], ref_text=r["ref_texte"])
    else:
        wavs, sr = m.generate_voice_design(text=j["text"], language=NOMS[l], instruct=DESC.format(a=ACCENT[l]))
    sf.write(j["out"], wavs[0], sr)
    print("OK", j["out"], flush=True)
