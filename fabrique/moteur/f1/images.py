"""Nouveau moteur (J9b), étape images = etape_images de production.py et ce qu'elle appelle (espece, nommer, lieux, sans_outils, cast_pour,
refs_pour, en_hiver, tailles, bord_blanc, qwen_image, qwen_edit, verifier_image, noter_correction) : Qwen-Image pour un décor, Qwen-Image-Edit
2511 avec les références des amis, même consigne, même négatif, lexique et tailles de regles.json, tricots et lieux d'univers.json, graines
1000 + id + décalage de images/_graines.json, contrôle des illustrations (Gemini) s'il est actif. Différences voulues : le dossier, les réglages, les
outils, ComfyUI et le juge sont des paramètres ; les constantes de production.py qui nomment des amis (PRECIS, HIVER_DEPUIS) y sont lues dans son code,
sans l'exécuter, pour qu'aucun nom réel n'entre dans le dépôt de l'app. Écrit seulement dans le dossier (et, comme production.py, les références des
amis dans l'entrée de ComfyUI). Sans Django."""
import ast
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from fabrique.moteur.f1 import copies
from fabrique.moteur.f1.outils import Outils, composant

ANIMAUX = (r"\b(animals?|creatures?|famil(y|ies)|mother|father|baby|babies|cubs?|kits?|fox(es)?|owls?|birds?|mice|mouse|rabbits?|bunn(y|ies)|"
           r"deer|fawns?|hedgehogs?|squirrels?|badgers?|beetles?|bees?|bumblebees?|moths?|butterfl(y|ies)|bats?|frogs?|toads?|snails?|otters?|"
           r"hares?|robins?|wrens?|moles?|dormice|dormouse|ducks?|swans?|geese|goose|fish(es)?|ants?|ladybirds?|spiders?|worms?|voles?|stoats?|"
           r"weasels?|herons?|woodpeckers?|sparrows?|blackbirds?|insects?|fireflies)\b")
HIVER = re.compile(r"\b(grey|gray)\b[^.;]{0,25}\b(fur|coat)\b|\b(fur|coat)\b[^.;]{0,45}\b(grey|gray)\b", re.I)


def constantes_production(racine: Path) -> dict:
    """PRECIS (précisions d'espèce imposées à Qwen-Edit) et HIVER_DEPUIS (épisode dès lequel un ami est en pelage d'hiver), lus dans le code de
    textes du projet (copies.textes : hors du dépôt), sans l'exécuter."""
    arbre = ast.parse(copies.textes(racine).read_text(encoding="utf-8"))  # J10 : la copie hors dépôt de ses définitions
    out = {"PRECIS": {}, "HIVER_DEPUIS": {}}
    for n in arbre.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in out:
            out[n.targets[0].id] = ast.literal_eval(n.value)
    return out


def espece(desc: str) -> str:
    """'<Nom>, a small red squirrel with ...' -> 'a small red squirrel'."""
    m = re.match(r"^[^,]+,\s*(an? [^,]+?)(?:\s+with\b|,|$)", desc)
    return m.group(1) if m else ""


def tricots(univers: dict) -> dict:
    """Vêtement tricoté de chaque ami (univers.json), imposé dans la consigne de Qwen-Edit."""
    try:
        return {k: v.get("knit", "") + (" (knitted, on the two front paws only, hind feet bare)" if "mitten" in v.get("knit", "") else " (knitted)")
                for k, v in univers["friends"].items()}
    except Exception:  # noqa: BLE001 — comme production.py : sans univers.json, pas de tricot imposé
        return {}


class Images:
    def __init__(self, dossier: Path, cfg: dict, outils: Outils, regles: dict, univers: dict, constantes: dict, comfy=None, juge=None):
        self.dossier, self.cfg, self.o, self.regles, self.univers = Path(dossier), cfg, outils, regles or {}, univers or {}
        self.precis, self.hiver_depuis = constantes.get("PRECIS", {}), constantes.get("HIVER_DEPUIS", {})
        self.tricot = tricots(self.univers)
        self.comfy = comfy or outils.module("kit", "comfy")
        self.juge = juge or self.verifier_image
        self.journal: list[str] = []
        self._lieux = None

    def log(self, *a):
        self.journal.append(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a))

    # ---- texte ----

    def sans_outils(self, texte: str) -> str:
        """Lexique unique des images (regles.json -> lexique_image) : mots que Qwen dessine mal -> mots sûrs."""
        for r in self.regles.get("lexique_image", []):
            texte = re.sub(r[0], r[1], texte, count=r[2] if len(r) > 2 else 0, flags=re.I)
        return texte

    def lieux(self, texte: str) -> str:
        """1re mention d'un lieu nommé -> sa description (univers.json), si config.json -> images.lieux."""
        if not self.cfg["images"].get("lieux"):
            return texte
        if self._lieux is None:
            try:
                self._lieux = [v["en"] for v in self.univers["places"].values()]
            except Exception:  # noqa: BLE001
                self._lieux = []
        for en in self._lieux:
            nom = en.split(",")[0]
            court = nom[4:] if nom.lower().startswith("the ") else nom
            if court.lower() in texte.lower() and en[len(nom):].lower() not in texte.lower():
                texte = re.sub(r"\b(the )?" + re.escape(court) + r"\b", lambda m, nom=nom, en=en: f"{nom} ({en[len(nom):].strip(' ,')})",
                               texte, count=1, flags=re.I)
        return texte

    def nommer(self, texte: str, cast: dict) -> str:
        """Chaque nom devient 'Nom the <espèce>' pour que le modèle ne dessine jamais un enfant humain."""
        texte = self.sans_outils(self.lieux(texte))
        for n, d in cast.items():
            sp = espece(d)
            if sp:
                sp = re.sub(r"^an? ", "", sp)
                texte = re.sub(r"\b" + re.escape(n) + r"\b(?!\s+the\b)", f"{n} the {sp}", texte, count=1)
        return texte

    @staticmethod
    def cast_pour(texte: str, cast: dict) -> list[str]:
        return [d for n, d in cast.items() if re.search(r"\b" + re.escape(n) + r"\b", texte)]

    def en_hiver(self, n: str, texte: str) -> bool:
        """Vrai si l'image montre l'ami en pelage d'hiver et qu'une reference_hiver.png existe."""
        if not (self.o.racine / "PROJET" / "personnages" / n.lower() / "reference_hiver.png").exists():
            return False
        m = re.search(r"s\d+e(\d+)", self.dossier.name)
        if m and n in self.hiver_depuis and int(m.group(1)) >= self.hiver_depuis[n]:
            return True
        return bool(HIVER.search(texte)) and not re.search(r"\bfew\b[^,.;]{0,20}\b(grey|gray)\b", texte, re.I)

    def tailles(self, noms: list[str]) -> str:
        """Phrase de tailles relatives (regles.json -> tailles) pour les personnages d'une même image."""
        T = self.regles.get("tailles", {}); n = [x for x in noms if x in T]
        if len(n) < 2: return ""
        g = max(n, key=T.get)
        return " ".join(f"Real sizes: {x} is tiny next to {g}; the whole body of {x} is no bigger than the {'paw' if T[g] - T[x] >= 3 else 'head'} of {g}."
                        for x in n if T[g] - T[x] >= 2)

    def refs_pour(self, texte: str, cast: dict) -> list[tuple[str, Path]]:
        r = []
        for n in cast:
            p = self.o.racine / "PROJET" / "personnages" / n.lower() / ("reference_hiver.png" if self.en_hiver(n, texte) else "reference.png")
            if re.search(r"\b" + re.escape(n) + r"\b", texte) and p.exists():
                r.append((n, p))
        return r

    @staticmethod
    def bord_blanc(path: Path) -> bool:
        """Vrai si l'image a un cadre ou des marges claires (effet autocollant de Qwen-Image)."""
        from PIL import Image
        im = Image.open(path).convert("L")
        w, h = im.size
        b = max(4, w // 60)
        zones = [im.crop((0, 0, w, b)), im.crop((0, h - b, w, h)), im.crop((0, 0, b, h)), im.crop((w - b, 0, w, h))]
        moy = [sum(z.getdata()) / (z.size[0] * z.size[1]) for z in zones]
        return sum(m > 200 for m in moy) >= 2

    # ---- ComfyUI ----

    def qwen_image(self, prompt: str, out_path: Path, seed: int, lora=None, lora_force=1.0, w=None, h=None, neg=None):
        ic = self.cfg["images"]; w = w or ic["largeur"]; h = h or ic["hauteur"]
        L = lambda n, i=0: [str(n), i]
        model = L(1)
        P = {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_bf16.safetensors", "weight_dtype": "default"}},
            "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b.safetensors", "type": "qwen_image", "device": "default"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": L(2), "text": prompt}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": L(2), "text": neg or self.cfg["negatif_image"]}},
        }
        if lora:
            P["9"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": L(1), "lora_name": lora, "strength_model": lora_force}}
            model = L(9)
        P.update({
            "6": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": model, "shift": ic["shift"]}},
            "7": {"class_type": "EmptySD3LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
            "8": {"class_type": "KSampler", "inputs": {"model": L(6), "positive": L(4), "negative": L(5), "latent_image": L(7), "seed": seed,
                                                      "steps": ic["pas"], "cfg": ic["cfg"], "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
            "10": {"class_type": "VAEDecode", "inputs": {"samples": L(8), "vae": L(3)}},
            "11": {"class_type": "SaveImage", "inputs": {"images": L(10), "filename_prefix": "prod/img"}},
        })
        outs = self.comfy.run(P, timeout=3600)
        shutil.move(outs[0], out_path)

    def qwen_edit(self, prompt: str, refs: list[Path], out_path: Path, seed: int, w=None, h=None, negatif=None, pas=None):
        """Qwen-Image-Edit 2511 : nouvelle illustration où les personnages gardent l'apparence de leur image de référence."""
        ic = self.cfg["images"]; w = w or ic["largeur"]; h = h or ic["hauteur"]; pas = pas or ic["pas"]
        L = lambda n, i=0: [str(n), i]
        P = {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_edit_2511_bf16.safetensors", "weight_dtype": "default"}},
            "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b.safetensors", "type": "qwen_image", "device": "default"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        }
        pos = {"clip": L(2), "vae": L(3), "prompt": prompt}
        neg = {"clip": L(2), "vae": L(3), "prompt": negatif or self.cfg["negatif_image"]}
        for k, r in enumerate(refs[:3], 1):
            name = f"prod_ref{k}.png"
            shutil.copy(r, Path(self.comfy.CUI) / "ComfyUI" / "input" / name)
            P[str(30 + k)] = {"class_type": "LoadImage", "inputs": {"image": name}}
            P[str(40 + k)] = {"class_type": "FluxKontextImageScale", "inputs": {"image": L(30 + k)}}
            pos[f"image{k}"] = L(40 + k); neg[f"image{k}"] = L(40 + k)
        P.update({
            "7": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": pos},
            "8": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": neg},
            "9": {"class_type": "FluxKontextMultiReferenceLatentMethod", "inputs": {"conditioning": L(7), "reference_latents_method": "index_timestep_zero"}},
            "10": {"class_type": "FluxKontextMultiReferenceLatentMethod", "inputs": {"conditioning": L(8), "reference_latents_method": "index_timestep_zero"}},
            "11": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": L(1), "shift": ic["shift"]}},
            "12": {"class_type": "CFGNorm", "inputs": {"model": L(11), "strength": 1.0, "pre_cfg": False}},
            "13": {"class_type": "EmptySD3LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
            "14": {"class_type": "KSampler", "inputs": {"model": L(12), "positive": L(9), "negative": L(10), "latent_image": L(13), "seed": seed,
                   "steps": pas, "cfg": ic["cfg"], "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
            "15": {"class_type": "VAEDecode", "inputs": {"samples": L(14), "vae": L(3)}},
            "16": {"class_type": "SaveImage", "inputs": {"images": L(15), "filename_prefix": "prod/edit"}},
        })
        outs = self.comfy.run(P, timeout=3600)
        shutil.move(outs[0], out_path)

    # ---- contrôle ----

    def verifier_image(self, img: Path, s: dict, data: dict) -> dict:
        """Gemini contrôle l'illustration (venv d'analyse, gemini_image.py) ; ok si la clé ou Gemini manque (le rendu n'est jamais bloqué)."""
        c = lambda cle, *rel: composant(self.o.racine, cle, *rel)  # noqa: E731
        if not c("cles", "gemini_api_key.txt").exists() or not self.cfg.get("controle_images", True):
            return {"ok": True}
        cast = data.get("cast", {})
        pers = {n: (d.replace("soft fawn-brown fur", "thick soft grey winter fur") if self.en_hiver(n, s["image"]) else d)
                   + (f" (garment: {self.tricot[n]})" if self.tricot.get(n) else "") for n, d in cast.items() if re.search(r"\b" + re.escape(n) + r"\b", s["image"])}
        cf = self.dossier / "images" / "_consigne.json"
        json.dump({"scene": s["image"], "personnages": pers}, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
        env = dict(os.environ)  # = production.py, qui pose ces variables à son import : modèle du contrôle, consigne corrigée par le juge
        if self.cfg.get("controle_modele"):
            env["AGY_MODELE"] = self.cfg["controle_modele"]
        if self.cfg.get("correction") == "reecriture":
            env["CORRECTION"] = "1"
        try:
            r = subprocess.run([str(c("analyse", "venv", "Scripts", "python.exe")), str(c("analyse", "gemini_image.py")), str(img), str(cf)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            v = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception as e:  # noqa: BLE001 — comme production.py : un contrôle en panne laisse passer l'image
            v = {"ok": True, "erreur": str(e)[:100]}
        jf = self.dossier / "images" / "_controle.json"
        tout = json.load(open(jf, encoding="utf-8")) if jf.exists() else {}
        tout.setdefault(str(s["id"]), []).append(v); json.dump(tout, open(jf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return v

    def noter_correction(self, typ, cle, avant, apres, problemes):
        """Journal des corrections intelligentes : <dossier>/corrections.json."""
        f = self.dossier / "corrections.json"
        try:
            j = json.load(open(f, encoding="utf-8")) if f.exists() else []
            j.append({"type": typ, "cle": str(cle), "avant": avant, "apres": apres, "problemes": problemes, "heure": time.strftime("%H:%M")})
            json.dump(j, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except Exception:  # noqa: BLE001
            pass

    # ---- étape ----

    def faire(self, data: dict, scenes: list[dict], plans: list[tuple[int, int]]):
        """= etape_images : images/plan_NNN.png des plans qui n'en ont pas (première scène de chaque plan, Bramble mis à part)."""
        CFG = self.cfg
        d = self.dossier / "images"; d.mkdir(exist_ok=True)
        todo = []
        for k, (i0, i1) in enumerate(plans):
            s = scenes[i0]
            if s.get("bramble"):
                continue
            out = d / f"plan_{s['id']:03d}.png"
            if not out.exists():
                todo.append((s, out))
        if not todo:
            self.log("images : deja faites"); return
        self.comfy.start()
        gf = d / "_graines.json"
        graines = json.load(open(gf, encoding="utf-8")) if gf.exists() else {}
        precis_tous = {**self.precis, **CFG["images"].get("precis_plus", {})}
        for n, (s, out) in enumerate(todo, 1):
            t_plan = time.time()  # durée par plan dans le journal : l'Accueil en tire le temps restant (rendu.DUREE_IMAGE)
            cast = self.cast_pour(s["image"], data.get("cast", {}))
            refs = self.refs_pour(s["image"], data.get("cast", {}))
            g0 = 1000 + s["id"] + int(graines.get(str(s["id"]), 0))
            autres = []
            if refs and len(refs) >= 2 and CFG["images"].get("sequentiel"):
                refs = sorted(refs, key=lambda r: re.search(r"\b" + re.escape(r[0]) + r"\b", s["image"]).start())
                refs, autres = refs[:1], refs[1:]
            if refs:
                noms = " and ".join(n for n, _ in refs)
                precis = " ".join(precis_tous[n] for n, _ in refs if n in precis_tous)
                if CFG["images"].get("taille"):
                    precis = (precis + " " + self.tailles([n for n, _ in refs])).strip()
                tricot = " ".join(f"{n} is clearly wearing the {self.tricot[n]} seen in the reference image, and no other clothing."
                                  for n, _ in refs if self.tricot.get(n))
                prompt = (f"Create a new children's picture-book illustration: {self.nommer(s['image'], data.get('cast', {}))}. {noms} must look exactly like the "
                          f"character{'s' if len(refs) > 1 else ''} in the reference image{'s' if len(refs) > 1 else ''} "
                          f"(same species, colours, proportions and knitted garment). {tricot} {precis} Animals only: no humans or human figures anywhere, not even tiny in the distance; animals never hold tools, they use their paws. Wide 16:9 full-bleed composition. Style: {CFG.get('style_histoire', CFG['style'])}.")
                if len(refs) > 3:
                    self.log(f"images : plan {s['id']} : {len(refs)} personnages, Qwen-Edit n'en voit que 3 ({', '.join(n for n, _ in refs[3:])} sans reference)")
                if CFG["images"].get("consigne") == "picture":
                    refs = sorted(refs, key=lambda r: re.search(r"\b" + re.escape(r[0]) + r"\b", s["image"]).start())[:3]
                    qui = " ".join(f"{n} is exactly the character from Picture {k} (same species, colours, proportions and face), "
                                   f"wearing only the {self.tricot.get(n, 'same clothing')} from Picture {k}." for k, (n, _) in enumerate(refs, 1))
                    cadre = "" if re.search(r"\b(wide view|in the distance|far away|tiny)\b", s["image"], re.I) else \
                        f" Medium shot: {refs[0][0]} is large in the frame, about half of the image height."
                    prompt = (f"Create a new children's picture-book illustration: {self.nommer(s['image'], data.get('cast', {})).rstrip('.')}. {qui}{cadre} {precis} "
                              + "Animals only:" + prompt.split("Animals only:", 1)[1])
                self.qwen_edit(prompt, [p for _, p in refs], out, seed=g0, negatif=CFG.get("negatif_histoire"))
                for j, (n2, p2) in enumerate(autres, 2):
                    pr2 = (f"Picture 1 is a finished children's picture-book illustration. Replace {n2} in Picture 1 with exactly the character "
                           f"from Picture 2 (same species, colours, proportions and face), wearing only the {self.tricot.get(n2, 'same clothing')} from Picture 2. "
                           f"{n2} stays in the same place and pose as in Picture 1. {self.tailles([refs[0][0], n2])} "
                           f"{precis_tous.get(n2, '')} Keep everything else exactly the same as Picture 1: "
                           f"{refs[0][0]} unchanged with only its own knitted garment, same background, same light, same framing, same gouache style.")
                    self.qwen_edit(re.sub(r"\s+", " ", pr2), [out, p2], out, seed=g0 + 17 * j, negatif=CFG.get("negatif_histoire"))
            else:
                if cast:
                    vide = []
                elif re.search(ANIMAUX, s["image"], re.I):
                    vide = []
                else:
                    vide = ["a peaceful empty natural landscape"]
                prompt = ", ".join([CFG.get("style_histoire", CFG["style"]), self.nommer(s["image"], data.get("cast", {}))] + cast + vide +
                                   (["animals only"] if cast else []) + ["gouache painting filling the whole frame, wide 16:9 composition"])
                for essai in range(4):
                    self.qwen_image(prompt, out, seed=g0 + 100 * essai, neg=CFG.get("negatif_histoire"))
                    if not self.bord_blanc(out):
                        break
                    self.log(f"images : plan {s['id']} avec cadre blanc, nouvel essai")
            texte_scene = s["image"]
            nb = CFG.get("controle_images_essais", 3); meilleur = (-1.0, None)
            for essai in range(1, nb + 1):
                v = self.juge(out, s, data)
                if v.get("ok", True):
                    break
                try: note = float(v.get("note", -1))
                except (TypeError, ValueError): note = -1.0
                if essai == nb:
                    if meilleur[1] and meilleur[0] > note:
                        shutil.copyfile(meilleur[1], out); self.log(f"images : plan {s['id']} meilleur essai garde ({meilleur[1].name}, note {meilleur[0]:g} > {note:g})")
                    break
                self.log(f"images : plan {s['id']} refuse par Gemini ({'; '.join(v.get('problemes', []))[:180]}) -> nouvel essai")
                nv = v.get("consigne_corrigee") if CFG.get("correction") == "reecriture" else None
                if nv:
                    c_d = data.get("cast", {}); avant = self.nommer(texte_scene, c_d).rstrip(".")
                    if avant in prompt:
                        prompt = prompt.replace(avant, self.nommer(nv, c_d).rstrip("."))
                        self.noter_correction("image", s["id"], texte_scene, nv, v.get("problemes", [])); texte_scene = nv
                        self.log(f"images : plan {s['id']} consigne corrigee : {nv[:140]}")
                (d / "_refus").mkdir(exist_ok=True); shutil.move(str(out), str(d / "_refus" / f"plan_{s['id']:03d}_{essai}.png"))
                if note > meilleur[0]: meilleur = (note, d / "_refus" / f"plan_{s['id']:03d}_{essai}.png")
                if refs:
                    self.qwen_edit(prompt, [p for _, p in refs], out, seed=g0 + 333 * essai, negatif=CFG.get("negatif_histoire"))
                else:
                    self.qwen_image(prompt, out, seed=g0 + 333 * essai, neg=CFG.get("negatif_histoire"))
            self.log(f"images : {n}/{len(todo)} plan {s['id']} ({time.time() - t_plan:.0f}s)")
