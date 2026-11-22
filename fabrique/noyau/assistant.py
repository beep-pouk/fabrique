"""Assistant (plan § 3.3, § 7.1 J11) : une demande écrite de RT → un plan chiffré (lecture seule), puis, après son « D'accord », un brouillon
de session (nouvelle session en pause à l'étape 1) ou de vidéo (une idée au calendrier). Ses outils sont des routes de l'API appelées avec
l'appelant « assistant » : le même contrôle des droits que la fenêtre (voir, estimer, brouillon), jamais un des trois gestes. Les outils de
brouillon ne lui sont offerts qu'avec l'accord de RT. Moteur : gpt-oss par llama-server de llama.cpp (API compatible OpenAI, appels
d'outils), démarré à la demande quand la carte est libre, arrêté au bout de INACTIF ou dès que la file veut la carte ; en simulation, un faux
moteur scénarisé (aucun programme lancé). Rien n'est gardé entre deux demandes : la fenêtre renvoie l'historique (textes seulement)."""
import json
import logging
import subprocess
import time
import urllib.request
from pathlib import Path


from fabrique import dossiers, garde
from fabrique.garde import Refus
from fabrique.noyau import etat

log = logging.getLogger(__name__)
PORT = 8792
INACTIF = 600  # secondes sans demande : llama-server arrêté, la carte rendue
TOURS = 8  # appels d'outils au plus par demande
MODELE = Path(r"C:\StudioKids\modeles\llm\gpt-oss-120b-MXFP4.gguf")  # shortcut: le 120b en dur (banc du moteur en attente, QUESTIONS 20/11 23 h 35) ; une fiche d'outil quand le banc aura tranché
CONSIGNE = ("Tu es l'assistant de Fabrique, l'atelier vidéo de RT. Réponds en français, court. À une demande, consulte les sessions, les formats "
            "et les estimations, puis propose un plan chiffré (vidéos, format, durée de fabrication, heures de carte, coût). Tu ne fabriques, "
            "n'approuves et ne publies jamais : RT le fait. Les brouillons (session ou vidéo) ne se préparent qu'après son accord. "
            "Chaque durée, heure de carte ou coût vient d'un outil (estimer) : jamais un chiffre inventé ; s'il est inconnu, dis-le.")


class _Appel:
    """La requête vue par une route : l'appelant « assistant » (droits voir, estimer, brouillon)."""
    auth = "assistant"
    method = "POST"
    headers: dict = {}


def _vues():
    from fabrique.noyau import api, schemas

    return {
        "sessions": (lambda a: api.sessions(_Appel()), "Les sessions (nom, id, état, langues).", {}),
        "formats": (lambda a: api.formats(_Appel()), "Les formats du catalogue (F1 à F6 : forme, durée).", {}),
        "calendrier": (lambda a: api.calendrier_(_Appel(), **{k: str(a[k]) for k in ("debut", "fin", "session") if k in a}),
                       "Le calendrier (vidéos datées, statut) entre deux jours AAAA-MM-JJ, d'une session ou de toutes.",
                       {"debut": {"type": "string"}, "fin": {"type": "string"}, "session": {"type": "string"}}),
        "statistiques": (lambda a: api.statistiques(_Appel()), "Ce qui rend le mieux (« quoi fabriquer ensuite »), par session et par chaîne.", {}),
        "estimer": (lambda a: api.estimer(_Appel(), schemas.Estimer(**a)), "Durée de fabrication, heures de carte et coût de n vidéos d'un format, "
                    "d'après les vidéos déjà faites.", {"format": {"type": "string"}, "videos": {"type": "integer"}}),
        "brouillon_session": (lambda a: api.brouillon_session(_Appel(), schemas.NouvelleSession(**a)), "Brouillon de session (en pause, RT la termine).",
                              {"nom": {"type": "string"}, "langues": {"type": "array", "items": {"type": "object", "properties": {"code": {"type": "string"}, "nom": {"type": "string"}}}}, "public": {"type": "string"},
                               "promesse": {"type": "string"}}),
        "brouillon_video": (lambda a: api.brouillon_video(_Appel(), a.pop("session"), schemas.NouvelleIdee(**a)), "Brouillon de vidéo : une idée au "
                            "calendrier d'une session.", {"session": {"type": "string"}, "titre": {"type": "string"}, "resume": {"type": "string"}}),
    }


BROUILLONS = {"brouillon_session", "brouillon_video"}


def offerts(accord: bool) -> list[dict]:
    return [{"type": "function", "function": {"name": n, "description": d, "parameters": {"type": "object", "properties": p}}}
            for n, (_, d, p) in _vues().items() if accord or n not in BROUILLONS]


def outil(nom: str, arguments: dict, accord: bool) -> str:
    """Joue un outil ; une erreur (droit refusé, refus du noyau, argument faux) revient au moteur en texte, jamais en exception."""
    if nom not in _vues() or (nom in BROUILLONS and not accord):
        return f"outil refusé : {nom}"
    try:
        r = _vues()[nom][0](dict(arguments))
    except Exception as e:  # noqa: BLE001 — argument manquant, refus, base illisible : toujours au moteur en texte
        return f"refusé : {e}"
    texte = _json(r)
    while len(texte) > 6000 and isinstance(r, list) and len(r) > 1:  # une liste trop longue : ses premiers éléments, en JSON valide
        r = r[: len(r) // 2]
        texte = _json(r)
    return texte[:6000]


def _json(r) -> str:
    return json.dumps(r, ensure_ascii=False, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o))


def faux(messages: list[dict], outils_: list[dict]) -> dict:
    """Le moteur de la simulation : sessions et formats, puis une estimation, puis (accord) un brouillon, puis la réponse ; aucun programme."""
    noms = {o["function"]["name"] for o in outils_}
    faits = {m["name"]: m["content"] for m in messages if m["role"] == "tool"}
    demande = next(m["content"] for m in reversed(messages) if m["role"] == "user")
    if "formats" not in faits:
        return {"role": "assistant", "content": "", "tool_calls": [_appel("sessions", {}), _appel("formats", {})]}
    format_ = next((f["id"] for f in json.loads(faits["formats"]) if f["id"] in demande), "F1")  # le format nommé dans la demande
    if "estimer" not in faits:
        return {"role": "assistant", "content": "", "tool_calls": [_appel("estimer", {"format": format_, "videos": 3})]}
    if BROUILLONS & noms and not BROUILLONS & set(faits):
        sessions = json.loads(faits["sessions"])
        if "session" in demande.lower() or not sessions:
            return {"role": "assistant", "content": "", "tool_calls": [_appel("brouillon_session", {"nom": "Brouillon de l'assistant", "langues": [{"code": "en", "nom": "Anglais"}]})]}
        return {"role": "assistant", "content": "", "tool_calls": [_appel("brouillon_video", {"session": next((x["id"] for x in sessions if not x.get("essais")), sessions[0]["id"]),
                                                                                           "titre": "Idée de l'assistant"})]}
    e = json.loads(faits["estimer"]) if faits["estimer"].startswith("{") else {}
    texte = (f"Plan : 3 vidéos {format_}, {e.get('texte', 'pas encore de chiffres')}." if not BROUILLONS & set(faits)
             else "Brouillon prêt : " + next(faits[n] for n in BROUILLONS if n in faits))
    return {"role": "assistant", "content": texte}


def _appel(nom: str, arguments: dict) -> dict:
    return {"id": f"faux_{nom}", "type": "function", "function": {"name": nom, "arguments": json.dumps(arguments, ensure_ascii=False)}}


_serveur: dict = {"processus": None, "vu": 0.0}


def _llama(messages: list[dict], outils_: list[dict]) -> dict:
    """gpt-oss par llama-server, démarré s'il ne tourne pas (carte libre seulement : jamais pendant un rendu)."""
    from datetime import datetime

    from fabrique.moteur import carte

    p = _serveur["processus"]
    if p is not None and p.poll() is None and (raison := carte.bramble(datetime.now())):  # un rendu de Bramble a commencé depuis
        ranger(True)
        raise Refus(f"la carte est prise ({raison}) : l'assistant répondra après")
    if p is None or p.poll() is not None:
        if raison := carte.occupee():
            raise Refus(f"la carte est prise ({raison}) : l'assistant répondra après")
        exe = (garde.studio_bramble() or dossiers.racine().parent) / "OUTILS" / "llamacpp" / "bin" / "llama-server.exe"
        if not exe.is_file() or not MODELE.is_file():
            raise Refus("moteur de l'assistant absent (llama-server ou modèle gpt-oss)")
        journal = (dossiers.donnees() / "journaux" / "assistant.log").open("ab")
        p = _serveur["processus"] = subprocess.Popen([str(exe), "-m", str(MODELE), "--port", str(PORT), "-c", "32000", "--jinja", "-fa", "on"],
                                                      stdout=journal, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        _pid().write_text(str(p.pid), encoding="utf-8")  # un noyau qui redémarre arrête celui-ci (orphelin) : il tient la carte et ~60 Go
        for _ in range(300):  # le 120b se charge en une à deux minutes
            try:
                if json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=5).read()).get("status") == "ok":
                    break
            except OSError:
                pass
            if p.poll() is not None:
                raise Refus("moteur de l'assistant arrêté au démarrage (journaux\\assistant.log)")
            time.sleep(1)
    _serveur["vu"] = time.monotonic()
    corps = json.dumps({"messages": messages, "tools": outils_, "temperature": 0.2}).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", data=corps, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["choices"][0]["message"]


def _pid() -> Path:
    return dossiers.donnees() / "assistant.pid"


def ranger(file_veut_la_carte: bool = False):
    """Boucle du noyau : llama-server arrêté après INACTIF, ou tout de suite quand la file attend la carte ou que Bramble Studio fabrique (les
    rendus passent avant) ; celui d'un noyau précédent (orphelin) arrêté au premier tour."""
    from datetime import datetime

    from fabrique.moteur import carte

    p = _serveur["processus"]
    if p is None and _pid().is_file():
        subprocess.run(["taskkill", "/PID", _pid().read_text(encoding="utf-8").strip(), "/FI", "IMAGENAME eq llama-server.exe", "/T", "/F"], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)  # le filtre : jamais un autre programme qui aurait repris ce numéro
        _pid().unlink(missing_ok=True)
    if p is not None and p.poll() is None and (file_veut_la_carte or time.monotonic() - _serveur["vu"] > INACTIF or carte.bramble(datetime.now())):
        p.terminate()
        _serveur["processus"] = None
        _pid().unlink(missing_ok=True)


def demander(demande: str, historique: list[dict], accord: bool) -> dict:
    """Une demande de RT (avec l'historique des textes) → la réponse, les outils joués et les brouillons faits."""
    moteur = faux if etat.simulation() else _llama
    messages = [{"role": "system", "content": CONSIGNE}, *[{"role": h["role"], "content": h["content"]} for h in historique if h.get("role") in ("user", "assistant")],
                {"role": "user", "content": demande}]
    outils_, joues = offerts(accord), []
    for _ in range(TOURS):
        r = moteur(messages, outils_)
        messages.append({"role": "assistant", "content": r.get("content") or "", **({"tool_calls": r["tool_calls"]} if r.get("tool_calls") else {})})
        if not r.get("tool_calls"):
            break
        for c in r["tool_calls"]:
            try:
                arguments = json.loads(c["function"].get("arguments") or "{}")
            except ValueError:
                arguments = {}
            faits = [j["outil"] for j in joues if j["outil"] in BROUILLONS and not j["resultat"].startswith(("refusé", "outil refusé"))]
            resultat = outil(c["function"]["name"], arguments, accord and not faits)  # un seul brouillon par « D'accord »
            joues.append({"outil": c["function"]["name"], "resultat": resultat[:300]})
            messages.append({"role": "tool", "tool_call_id": c.get("id", ""), "name": c["function"]["name"], "content": resultat})
    faits = [j["outil"] for j in joues if j["outil"] in BROUILLONS and not j["resultat"].startswith(("refusé", "outil refusé"))]
    reponse = (messages[-1]["content"] if messages[-1]["role"] == "assistant" and messages[-1]["content"]
               else "Je n'ai pas fini : reformulez la demande." + (" Brouillon déjà fait." if faits else ""))
    return {"message": reponse, "outils": joues, "brouillons": faits,
            "historique": [*historique, {"role": "user", "content": demande}, {"role": "assistant", "content": reponse}]}
