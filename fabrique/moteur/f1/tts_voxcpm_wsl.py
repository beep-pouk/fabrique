"""J19 : voix d'une langue par VoxCPM2 (OpenBMB, Apache 2.0, installé dans Linux : composant « voxcpm »), clonage de la même référence que l'anglais.
Linux : HF_HOME=<cache> <voxcpm>/bin/python tts_voxcpm_wsl.py <jobs.json> (même format que tts_chatterbox_mtl.py)."""
import json
import sys

import soundfile as sf
from voxcpm import VoxCPM

w = lambda p: "/mnt/" + p[0].lower() + p[2:].replace("\\", "/") if len(p) > 1 and p[1] == ":" else p  # chemins Windows du lot
c = json.load(open(sys.argv[1], encoding="utf-8"))
r = c.get("reglages", {})
m = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
for j in c["jobs"]:
    wav = m.generate(text=j["text"], reference_wav_path=w(c["ref"]), cfg_value=r.get("cfg_value", 2.0), inference_timesteps=r.get("pas", 10), seed=j.get("seed", 42))
    sf.write(w(j["out"]), wav, m.tts_model.sample_rate)
    print("OK", j["out"], flush=True)
