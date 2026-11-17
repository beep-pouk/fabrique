# Offload par blocs pour LongCat-Video-Avatar sur GPU 16 Go
import os, types, torch

def _pin(t):
    if os.environ.get("NO_PIN") == "1":
        return t
    try:
        return t.pin_memory()
    except Exception as e:
        print("[offload] pin impossible:", e); os.environ["NO_PIN"] = "1"; return t

def merge_loras(dit):
    """Fusionne les LoRA actives (ex. DMD) dans les poids : moins de VRAM, plus rapide."""
    if not getattr(dit, "lora_dict", None): return
    import torch
    n = 0
    for key in list(getattr(dit, "active_loras", [])) or list(dit.lora_dict.keys()):
        for l in dit.lora_dict[key].loras:
            name = l.lora_name.replace("lora___lorahyphen___", "").replace("___lorahyphen___", ".")
            mod = dit._get_module_by_name(name)
            down = l.lora_down.weight.float().cpu()
            sc = float(l.multiplier) * float(l.alpha_scale)
            if hasattr(l.lora_up, "blocks"):
                r = down.shape[0] // len(l.lora_up.blocks)
                delta = torch.cat([b.weight.float().cpu() @ down[j*r:(j+1)*r] for j, b in enumerate(l.lora_up.blocks)], 0)
            else:
                delta = l.lora_up.weight.float().cpu() @ down
            w = mod.weight
            w.data = (w.data.float() + sc * delta.to(w.device)).to(w.dtype)
            n += 1
    dit.disable_all_loras()
    dit.lora_dict = {}
    print(f"[offload] {n} LoRA fusionnees dans les poids")

def setup(pipe, dev):
    dit = pipe.dit
    merge_loras(dit)
    dev = torch.device("cuda", dev) if isinstance(dev, int) else torch.device(dev)
    # 1) tout sauf les blocs -> GPU
    for name, child in dit.named_children():
        if name != "blocks":
            child.to(dev)
    for n, p in list(dit._parameters.items()):
        if p is not None: p.data = p.data.to(dev)
    for n, b in list(dit._buffers.items()):
        if b is not None: dit._buffers[n] = b.to(dev)
    # 2) LoRA (petites) -> GPU
    for net in getattr(dit, "lora_dict", {}).values():
        for l in net.loras: l.to(dev)
    # 3) blocs : poids en RAM epinglee, charges a la volee avec prefetch
    blocks = dit.blocks; n = len(blocks)
    plist = []
    for blk in blocks:
        ps = []
        for t in list(blk.parameters()) + list(blk.buffers()):
            t.data = _pin(t.data.contiguous()); t._cpu = t.data; ps.append(t)
        plist.append(ps)
    copy = torch.cuda.Stream(dev); ev = {}
    STOP = os.environ.get("STOP_FILE", "")  # posé par moteur/bramble.py (kit du studio)
    shapes0 = [(t.shape, t.dtype) for t in plist[0]]
    same = all([(t.shape, t.dtype) for t in ps] == shapes0 for ps in plist)
    print(f"[offload] tampons fixes: {same}")
    if same:
        # double tampon fixe sur GPU : aucune allocation pendant le calcul
        slots = [[torch.empty(sh, dtype=dt, device=dev) for sh, dt in shapes0] for _ in range(2)]
        done = [None, None]
        def load(i):
            if i in ev: return
            s = i % 2
            with torch.cuda.stream(copy):
                if done[s] is not None: copy.wait_event(done[s])
                for t, buf in zip(plist[i], slots[s]):
                    buf.copy_(t._cpu, non_blocking=True); t.data = buf
                e = torch.cuda.Event(); e.record(copy)
            ev[i] = e
        def pre(i):
            def h(mod, args):
                if i == 0 and os.path.exists(STOP):
                    raise SystemExit("[offload] arret demande (STOP_LIPSYNC)")
                load(i)
                torch.cuda.current_stream(dev).wait_event(ev[i])
                load((i + 1) % n)
            return h
        def post(i):
            def h(mod, args, out):
                e = torch.cuda.Event(); e.record(torch.cuda.current_stream(dev)); done[i % 2] = e
                for t in plist[i]: t.data = t._cpu
                ev.pop(i, None)
            return h
    else:
        def load(i):
            if i in ev: return
            with torch.cuda.stream(copy):
                for t in plist[i]:
                    t.data = t._cpu.to(dev, non_blocking=True)
                e = torch.cuda.Event(); e.record(copy)
            ev[i] = e
        def pre(i):
            def h(mod, args):
                load(i)
                cur = torch.cuda.current_stream(dev); cur.wait_event(ev[i])
                for t in plist[i]: t.data.record_stream(cur)
                load((i + 1) % n)
            return h
        def post(i):
            def h(mod, args, out):
                for t in plist[i]: t.data = t._cpu
                ev.pop(i, None)
            return h
    for i, blk in enumerate(blocks):
        blk.register_forward_pre_hook(pre(i)); blk.register_forward_hook(post(i))
    # 4) encodeur texte : garde en RAM, monte sur le GPU le temps d'encoder (129 s sur CPU -> quelques s), + cache
    #    (meme prompt pour tous les plans de Bramble et tous les segments)
    te = pipe.text_encoder
    te.to("cpu")
    for p_ in te.parameters():
        p_.data = _pin(p_.data)
    org = te.forward
    cache = {}
    def te_fwd(self, input_ids=None, attention_mask=None, *a, **k):
        key = (input_ids.cpu().numpy().tobytes(), None if attention_mask is None else attention_mask.cpu().numpy().tobytes())
        if key not in cache:
            with torch.no_grad():
                if os.environ.get("TE_CPU") == "1":
                    o = org(input_ids.cpu(), attention_mask.cpu() if attention_mask is not None else None, *a, **k)
                else:
                    for p_ in te.parameters(): p_._cpu = p_.data; p_.data = p_.data.to(dev, non_blocking=True)
                    for b_ in te.buffers(): b_.data = b_.data.to(dev)
                    o = org(input_ids.to(dev), attention_mask.to(dev) if attention_mask is not None else None, *a, **k)
                    for p_ in te.parameters(): p_.data = p_._cpu
                    torch.cuda.empty_cache()
            cache[key] = o.last_hidden_state.detach().to(dev)
        return types.SimpleNamespace(last_hidden_state=cache[key])
    te.forward = types.MethodType(te_fwd, te)
    # 5) VAE -> GPU
    pipe.vae.to(dev)
    pipe.device = dev
    torch.cuda.empty_cache()
    print(f"[offload] pret: {n} blocs offloades, VRAM {torch.cuda.memory_allocated(dev)/2**30:.1f} Go")
    return pipe
