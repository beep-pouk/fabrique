"""J19 : voix d'une langue par Chatterbox Multilingual (Resemble AI, MIT), lancé par le Python du venv de Chatterbox :
python tts_chatterbox_mtl.py <jobs.json> ; jobs = {"ref": voix 1, "ref_gen": voix clonée (voix 1 ou référence native retenue au banc), "reglages": {"t3": …, "s3": …}, "jobs": [{text, out, seed,
langue, exaggeration, cfg}]}. Poids dans <poids>\\chatterbox_mtl (« poids » du lot = composant « poids_voix » ; le modèle et la version retenus par le banc des voix)."""
import json
import pathlib
import sys

import torch
import torchaudio as ta
from chatterbox.mtl_tts import S3Gen, T3, T3Config, ChatterboxMultilingualTTS, MTLTokenizer, VoiceEncoder
from safetensors.torch import load_file

c = json.load(open(sys.argv[1], encoding="utf-8"))
M = pathlib.Path(c["poids"]) / "chatterbox_mtl"
r = c.get("reglages", {})
ve = VoiceEncoder(); ve.load_state_dict(torch.load(M / "chatterbox" / "ve.pt", weights_only=True)); ve.to("cuda").eval()
s3 = S3Gen(); k = s3.load_state_dict(torch.load(M / r.get("s3", "chatterbox/s3gen_v3.pt"), weights_only=True), strict=False); s3.to("cuda").eval()
assert set(k.missing_keys) <= {"tokenizer._mel_filters", "tokenizer.window"} and not k.unexpected_keys, k  # V3 : tampons recalculés à la construction
t3 = T3(T3Config.multilingual())
st = load_file(M / r.get("t3", "chatterbox/t3_mtl23ls_v3.safetensors"))
t3.load_state_dict(st["model"][0] if "model" in st else st); t3.to("cuda").eval()
m = ChatterboxMultilingualTTS(t3, s3, ve, MTLTokenizer(str(M / "chatterbox" / "grapheme_mtl_merged_expanded_v1.json")), "cuda")
for j in c["jobs"]:
    torch.manual_seed(j.get("seed", 42))
    w = m.generate(j["text"], language_id=j["langue"].split("-")[0], audio_prompt_path=c.get("ref_gen", c["ref"]), exaggeration=j.get("exaggeration", 0.3), cfg_weight=j.get("cfg", 0.3))
    ta.save(j["out"], w, m.sr)
    print("OK", j["out"], flush=True)
