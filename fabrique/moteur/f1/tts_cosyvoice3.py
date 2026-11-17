"""Banc des voix (10/11) : voix d'une langue par Fun-CosyVoice3 0.5B (Alibaba FunAudioLLM, Apache 2.0), mode « cross-lingual » (la voix 1 clonée
sans son texte anglais), japonais en katakana (consigne du modèle). Python : venv du composant « cosyvoice », code dans son dossier CosyVoice,
poids <poids>\\cosyvoice3. python tts_cosyvoice3.py <jobs.json> (même lot que tts_chatterbox_mtl.py)."""
import json
import pathlib
import sys

C = pathlib.Path.cwd() / "CosyVoice"  # lancé depuis le dossier du composant « cosyvoice »
sys.path += [str(C), str(C / "third_party" / "Matcha-TTS")]
import torch  # noqa: E402
import torchaudio  # noqa: E402
from cosyvoice.cli.cosyvoice import AutoModel  # noqa: E402

c = json.load(open(sys.argv[1], encoding="utf-8"))
m = AutoModel(model_dir=str(pathlib.Path(c["poids"]) / "cosyvoice3"))
for j in c["jobs"]:
    texte = j["text"]
    if j["langue"] == "ja":
        import pykakasi
        texte = "".join(x["kana"] for x in pykakasi.kakasi().convert(texte))
    torch.manual_seed(j.get("seed", 42))
    w = torch.cat([x["tts_speech"] for x in m.inference_cross_lingual("You are a helpful assistant.<|endofprompt|>" + texte, c.get("ref_gen", c["ref"]), stream=False)], dim=1)
    torchaudio.save(j["out"], w, m.sample_rate)
    print("OK", j["out"], flush=True)
