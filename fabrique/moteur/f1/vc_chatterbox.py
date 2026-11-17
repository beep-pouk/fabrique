"""Banc des voix (10/11) : conversion de timbre vers la voix 1 par Chatterbox VC (Resemble AI, MIT), sur place, après une voix native.
Python du venv de Chatterbox : python vc_chatterbox.py <jobs.json> (même lot que tts_*.py ; cible = « ref », la voix 1 ; « reglages.vc » = s3gen)."""
import json
import pathlib
import sys

import torch
import torchaudio as ta
from chatterbox.mtl_tts import S3Gen
from chatterbox.vc import ChatterboxVC

c = json.load(open(sys.argv[1], encoding="utf-8"))
M = pathlib.Path(c["poids"]) / "chatterbox_mtl"
s3 = S3Gen(); k = s3.load_state_dict(torch.load(M / c["reglages"]["vc"], weights_only=True), strict=False); s3.to("cuda").eval()
assert set(k.missing_keys) <= {"tokenizer._mel_filters", "tokenizer.window"} and not k.unexpected_keys, k
vc = ChatterboxVC(s3, "cuda"); vc.set_target_voice(c["ref"])
for j in c["jobs"]:
    torch.manual_seed(j.get("seed", 42))
    ta.save(j["out"], vc.generate(j["out"]), vc.sr)
    print("OK", j["out"], flush=True)
