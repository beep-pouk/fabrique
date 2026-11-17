"""Pilote ComfyUI (Windows) : demarrage, object_info, envoi d'un workflow API, attente, sorties.
Fabrique (F1) : repris d'OUTILS\\kit\\comfy.py ; le ComfyUI du studio (outil partagé, un seul serveur), son journal chez Fabrique, PowerShell
par son chemin et sans console (pour() avant tout usage)."""
import json, os, subprocess, sys, time, urllib.request, uuid, shutil
CUI = JOURNAL = None
URL = "http://127.0.0.1:8188"
POWERSHELL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")


def pour(lieux):
    """Le ComfyUI des outils partagés ; le journal dans donnees\\journaux de Fabrique. Rend ce module (comme Outils.module)."""
    global CUI, JOURNAL
    from fabrique import dossiers
    from fabrique.moteur.f1.outils import composant

    CUI, JOURNAL = str(composant(lieux, "comfyui")), dossiers.donnees() / "journaux" / "comfyui.log"
    return sys.modules[__name__]


def get(path):
    with urllib.request.urlopen(URL + path, timeout=30) as r: return json.loads(r.read())

def post(path, data):
    req = urllib.request.Request(URL + path, json.dumps(data).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode(errors="replace"))

def up():
    try: get("/system_stats"); return True
    except Exception: return False

def start(wait=600):
    if up(): return
    subprocess.Popen([CUI + r"\python_embeded\python.exe", "-s", r"ComfyUI\main.py", "--windows-standalone-build", "--disable-auto-launch"],
                     cwd=CUI, creationflags=subprocess.CREATE_NO_WINDOW,  # J14 : sans fenetre (regle de RT)
                     stdout=open(JOURNAL, "ab"), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    t = time.time()
    while time.time() - t < wait:
        if up(): return
        time.sleep(3)
    raise RuntimeError("ComfyUI n'a pas demarre")

class TachePerdue(RuntimeError):
    pass


def run(prompt, timeout=7200, essais=3):
    """Envoie un workflow, attend la fin, renvoie les sorties. Surveillance (18/10 : rendu bloque 6 h, ComfyUI
    plante ou fige) : si ComfyUI ne repond plus ou a perdu la tache, il est redemarre et la tache renvoyee."""
    for k in range(essais):
        try:
            return _run(prompt, timeout)
        except TachePerdue as e:
            print(f"[comfy] {e} -> redemarrage de ComfyUI ({k + 1}/{essais})", flush=True)
            stop(); start()
    raise RuntimeError("ComfyUI a perdu la tache plusieurs fois")


def _run(prompt, timeout):
    pid = post("/prompt", {"prompt": prompt, "client_id": str(uuid.uuid4())})["prompt_id"]
    t = time.time(); absent = 0; muet = 0
    while time.time() - t < timeout:
        try:
            h = get("/history/" + pid)
            q = get("/queue"); muet = 0
        except Exception:
            muet += 1
            if muet >= 24:      # 2 min sans reponse
                raise TachePerdue("ComfyUI ne repond plus")
            time.sleep(5); continue
        if pid not in h:
            enfile = any(x[1] == pid for x in q.get("queue_running", []) + q.get("queue_pending", []))
            absent = 0 if enfile else absent + 1
            if absent >= 12:    # 1 min ni en cours, ni en attente, ni fini
                raise TachePerdue("tache perdue par ComfyUI")
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                raise RuntimeError(json.dumps(st.get("messages", [])[-3:], ensure_ascii=False)[:4000])
            outs = []
            for node, o in h[pid].get("outputs", {}).items():
                for key in ("images", "gifs", "videos", "3d", "audio", "result"):
                    for f in o.get(key, []) if isinstance(o.get(key), list) else []:
                        if isinstance(f, dict) and "filename" in f:
                            outs.append(os.path.join(CUI, "ComfyUI", f.get("type", "output"), f.get("subfolder", ""), f["filename"]))
                        elif isinstance(f, str):
                            outs.append(f)
            return outs
        time.sleep(5)
    raise RuntimeError("delai depasse")

def stop():
    """Arrete ComfyUI (libere la carte graphique avant LongCat ou un entrainement)."""
    if not up():
        return
    try:
        post("/free", {"unload_models": True, "free_memory": True})
    except Exception:
        pass
    subprocess.run([POWERSHELL, "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*ComfyUI\\main.py*' } "
                    "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    t = time.time()
    while up() and time.time() - t < 60:
        time.sleep(2)

