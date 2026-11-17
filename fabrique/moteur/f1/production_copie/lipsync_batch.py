"""LongCat-Video-Avatar 1.5 en lot (un seul chargement des modeles pour tous les plans de Bramble).
Lance par torchrun dans le dossier de LongCat (Linux). Usage :
  torchrun --nproc_per_node=1 lipsync_batch.py --jobs jobs.json [--full]
jobs.json : [{"image": ".../welcome.png", "audio": ".../s001.wav", "out": ".../s001", "prompt": "..."}]
Chaque sortie est ecrite en <out>.mp4 ; un job deja fait (mp4 present) est saute.
"""
import os, sys, json, math, time, argparse, datetime
import numpy as np, PIL.Image, torch, torch.distributed as dist, librosa
from pathlib import Path
from transformers import AutoTokenizer, UMT5EncoderModel
from diffusers.utils import load_image
from longcat_video.pipeline_longcat_video_avatar import LongCatVideoAvatarPipeline
from longcat_video.modules.scheduling_flow_match_euler_discrete import FlowMatchEulerDiscreteScheduler
from longcat_video.modules.autoencoder_kl_wan import AutoencoderKLWan
from longcat_video.modules.avatar.longcat_video_dit_avatar import LongCatVideoAvatarTransformer3DModel
from longcat_video.context_parallel import context_parallel_util
from longcat_video.audio_process import get_audio_encoder, get_audio_feature_extractor
from longcat_video.audio_process.torch_utils import save_video_ffmpeg
from audio_separator.separator import Separator
sys.path.insert(0, os.environ.get("OFFLOAD_DIR", os.path.dirname(os.path.abspath(__file__))))
import offload, types, flash_attn

# --- Acceleration (banc du 11/10 : -23 %, qualite identique) : SageAttention 1 + FP8 (_scaled_mm) sur les Linear des blocs ---
def _sage(q, k, v, dropout_p=0.0, softmax_scale=None, causal=False, **kw):
    from sageattention import sageattn_qk_int8_pv_fp16_triton  # SageAttention 2.2 : la version auto plante sur la 4080 (11/10)
    return sageattn_qk_int8_pv_fp16_triton(q, k, v, tensor_layout="NHD", is_causal=causal, sm_scale=softmax_scale)
_F8 = torch.float8_e4m3fn
def _fp8_fwd(self, x):
    if x.dtype != torch.bfloat16 or x.shape[-1] % 16 or self.weight.shape[0] % 16:
        return torch.nn.functional.linear(x, self.weight, self.bias)
    shp = x.shape; x2 = x.reshape(-1, shp[-1])
    if x2.shape[0] % 16:
        return torch.nn.functional.linear(x, self.weight, self.bias)
    w = self.weight
    sx = (x2.abs().amax().float() / 448.0).clamp(min=1e-12); sw = (w.abs().amax().float() / 448.0).clamp(min=1e-12)
    b = self.bias.to(torch.bfloat16) if self.bias is not None else None
    y = torch._scaled_mm((x2 / sx).to(_F8), (w / sw).to(_F8).t(), scale_a=sx, scale_b=sw, bias=b, out_dtype=torch.bfloat16)
    return y.reshape(*shp[:-1], w.shape[0])
def accelerer(dit):
    if os.environ.get("NO_ACCEL") == "1":
        return
    flash_attn.flash_attn_func = _sage
    n = 0
    for blk in dit.blocks:
        for m in blk.modules():
            if isinstance(m, torch.nn.Linear) and m.in_features >= 1024:
                m.forward = types.MethodType(_fp8_fwd, m); n += 1
    print(f"[lipsync] acceleration : SageAttention + FP8 sur {n} Linear", flush=True)

NEG = ("Close-up, Bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, "
       "overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, "
       "poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, "
       "many people in the background, walking backwards")
CK = "./weights/LongCat-Video-Avatar-1.5"
BASE = os.path.join(CK, "..", "LongCat-Video")


def gc():
    torch.cuda.empty_cache(); torch.cuda.ipc_collect()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--jobs", required=True); ap.add_argument("--full", action="store_true")
    a = ap.parse_args()
    jobs = [j for j in json.load(open(a.jobs, encoding="utf-8")) if not os.path.exists(j["out"] + ".mp4")]
    print(f"[lipsync] {len(jobs)} plan(s) a faire", flush=True)
    if not jobs:
        return
    distill = not a.full
    steps, tg, ag = (int(os.environ.get('LONGCAT_STEPS', 4)), 1.0, 1.0) if distill else (50, 4.0, 4.0)  # 4 pas : banc du 11/10, rendu quasi identique a 8
    fps, stride, nf, ncf = 25, 1, 93, 13
    rank = int(os.environ.get("RANK", 0)); torch.cuda.set_device(0)
    dist.init_process_group(backend="nccl", timeout=datetime.timedelta(hours=24))
    context_parallel_util.init_context_parallel(context_parallel_size=1, global_rank=0, world_size=1)
    cp_split = context_parallel_util.get_optimal_split(1)
    tok = AutoTokenizer.from_pretrained(BASE, subfolder="tokenizer", torch_dtype=torch.bfloat16)
    te = UMT5EncoderModel.from_pretrained(BASE, subfolder="text_encoder", torch_dtype=torch.bfloat16)
    vae = AutoencoderKLWan.from_pretrained(BASE, subfolder="vae", torch_dtype=torch.bfloat16)
    sch = FlowMatchEulerDiscreteScheduler.from_pretrained(CK, subfolder="scheduler", torch_dtype=torch.bfloat16)
    dit = LongCatVideoAvatarTransformer3DModel.from_pretrained(CK, subfolder="base_model", cp_split_hw=cp_split, torch_dtype=torch.bfloat16)
    if distill:
        dit.load_lora(os.path.join(CK, "lora", "dmd_lora.safetensors"), "dmd", multiplier=1.0, lora_network_dim=128, lora_network_alpha=64)
        dit.enable_loras(["dmd"])
    wpath = os.path.join(CK, "whisper-large-v3")
    aenc = get_audio_encoder(wpath, "avatar-v1.5").to(0)
    afe = get_audio_feature_extractor(wpath, "avatar-v1.5")
    tmpd = Path("./audio_temp_file"); tmpd.mkdir(exist_ok=True)
    sep = Separator(output_dir=tmpd / "vocals", output_single_stem="vocals", model_file_dir=os.path.join(CK, "vocal_separator"))
    sep.load_model("Kim_Vocal_2.onnx")
    pipe = LongCatVideoAvatarPipeline(tokenizer=tok, text_encoder=te, vae=vae, scheduler=sch, dit=dit,
                                      audio_encoder=aenc, audio_feature_extractor=afe, model_type="avatar-v1.5")
    offload.setup(pipe, 0)
    accelerer(dit)
    _org_sig = pipe.get_timesteps_sigmas
    def _sig(sampling_steps, use_distill=False):  # sous-ensemble regulier des 8 sigmas de la distillation DMD
        full = _org_sig(8, use_distill=use_distill)
        if use_distill and sampling_steps < len(full):
            ix = np.round(np.linspace(0, len(full) - 1, sampling_steps)).astype(int)
            return full[torch.from_numpy(ix)]
        return _org_sig(sampling_steps, use_distill=use_distill)
    pipe.get_timesteps_sigmas = _sig
    idx = torch.arange(5) - 2
    for j in jobs:
        t0 = time.time()
        outs = sep.separate(j["audio"])
        voc = (tmpd / "vocals" / outs[0]).resolve().as_posix() if outs else j["audio"]
        speech, sr = librosa.load(voc, sr=16000)
        dur = len(speech) / sr
        nseg = max(1, math.ceil((dur * fps - nf) / (nf - ncf)) + 1)
        need = nf / fps + (nseg - 1) * (nf - ncf) / fps
        pad = math.ceil((need - dur) * sr)
        if pad > 0:
            speech = np.append(speech, [0.0] * pad)
        pipe.audio_encoder.to(0)
        emb = pipe.get_audio_embedding(speech, fps=fps * stride, device=0, sample_rate=sr, model_type="avatar-v1.5")
        pipe.audio_encoder.to("cpu"); gc()
        g = torch.Generator(device=0); g.manual_seed(42)
        s0 = 0
        ci = torch.clamp(torch.arange(s0, s0 + stride * nf, stride).unsqueeze(1) + idx.unsqueeze(0), 0, emb.shape[0] - 1)
        out, lat = pipe.generate_ai2v(image=load_image(j["image"]), prompt=j["prompt"], negative_prompt=NEG, resolution=j.get("resolution", "480p"),
                                      num_frames=nf, num_inference_steps=steps, text_guidance_scale=tg, audio_guidance_scale=ag,
                                      output_type="both", generator=g, audio_emb=emb[ci][None, ...].to(0), use_distill=distill)
        frames = [PIL.Image.fromarray((out[0][i] * 255).astype(np.uint8)) for i in range(out[0].shape[0])]
        allf, cur, ref = list(frames), frames, lat[:, :, :1].clone()
        W, H = frames[0].size
        for k in range(1, nseg):
            s0 += stride * (nf - ncf)
            ci = torch.clamp(torch.arange(s0, s0 + stride * nf, stride).unsqueeze(1) + idx.unsqueeze(0), 0, emb.shape[0] - 1)
            out, lat = pipe.generate_avc(video=cur, video_latent=lat, prompt=j["prompt"], negative_prompt=NEG, height=H, width=W,
                                         num_frames=nf, num_cond_frames=ncf, num_inference_steps=steps, text_guidance_scale=tg,
                                         audio_guidance_scale=ag, generator=g, output_type="both", use_kv_cache=True,
                                         offload_kv_cache=True, enhance_hf=not distill, audio_emb=emb[ci][None, ...].to(0),
                                         ref_latent=ref, ref_img_index=10, mask_frame_range=3, use_distill=distill)
            new = [PIL.Image.fromarray((out[0][i] * 255).astype(np.uint8)) for i in range(out[0].shape[0])]
            allf.extend(new[ncf:]); cur = new
            gc()
        save_video_ffmpeg(torch.from_numpy(np.array(allf)), j["out"], j["audio"], fps=fps, quality=5)
        if voc != j["audio"] and os.path.exists(voc):
            os.remove(voc)
        print(f"[lipsync] OK {j['out']}.mp4  {dur:.1f}s audio, {nseg} segment(s), {time.time()-t0:.0f}s", flush=True)
        gc()


if __name__ == "__main__":
    main()
