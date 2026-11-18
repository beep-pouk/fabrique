"""Règles de l'univers d'une session (plan § 6.1 : règles vérifiées par le noyau pendant la frappe ; cahier F « une erreur bloque la
fabrication ») : OUTILS\\ecriture\\lint.py, l'outil du projet partagé avec Bramble Studio, importé tel quel (rien d'écrit à côté, repris de
Bramble Studio core/controle.py), appelé sur l'univers de la SESSION et ses autres scripts (lint.lint(sc, univers, saison, autres, cfg) : une
fonction pure ; sa lecture de PROJET n'est jamais utilisée). Saison et réglages d'écriture : absents du projet aujourd'hui (None, comme lint)."""
import importlib.util
import json
import sys

from django.conf import settings

from fabrique import dossiers, garde
from fabrique.garde import Refus
from fabrique.moteur.f1.outils import Lieux, composant
from fabrique.noyau import routeur
from fabrique.noyau.models import Session
from fabrique.session import models as m

VOISINS = ("lint", "schema")
_modules: dict[tuple, object] = {}


class Indisponible(Refus):
    """lint.py introuvable ou en panne : rien ne peut être validé tant que ça dure."""


def charger():
    """lint.py des outils partagés (importé depuis son dossier pour qu'il trouve schema.py), rechargé s'il a changé. (= controle.charger)"""
    chemin = composant(Lieux(garde.studio_bramble() or dossiers.racine().parent, "."), "ecriture", "lint.py")
    if not chemin.is_file():
        raise Indisponible(f"lint.py introuvable : {chemin}")
    cle = (chemin.resolve(), chemin.stat().st_mtime)
    if cle not in _modules:
        gardes = {n: sys.modules.pop(n) for n in VOISINS if n in sys.modules}
        sys.path.insert(0, str(chemin.parent))
        bytecode, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        try:
            spec = importlib.util.spec_from_file_location("lint", chemin)
            module = importlib.util.module_from_spec(spec)
            sys.modules["lint"] = module
            spec.loader.exec_module(module)
        except Exception as e:  # noqa: BLE001 — un lint.py cassé est signalé, pas masqué
            raise Indisponible(f"lint.py inchargeable : {type(e).__name__} : {e}") from e
        finally:
            sys.dont_write_bytecode = bytecode
            sys.path.remove(str(chemin.parent))
            for n in VOISINS:
                sys.modules.pop(n, None)
            sys.modules.update(gardes)
        _modules[cle] = module
    return _modules[cle]


def controler(s: Session, contenu: dict, code: str = "") -> dict:
    """{erreurs, avis, mesures} du script `contenu` (le script `code` de la session, ou un nouveau), face à l'univers et aux autres scripts.
    Un format dont le script n'est pas un scénario de Bramble : sa forme seulement (schéma de la recette ; cahier F, forme propre au format)."""
    from fabrique.moteur import recettes
    from fabrique.session import reglages

    forme = recettes.lire(reglages.lire(s)["format"])["script"]
    if forme != "scenario-bramble":
        try:
            recettes.script(contenu, forme)
            return {"erreurs": [], "avis": [], "mesures": {}}
        except Refus as e:
            return {"erreurs": [["forme", str(e)]], "avis": [], "mesures": {}}
    lint = charger()
    f = settings.SESSIONS / s.dossier / "univers" / "univers.json"
    if not f.is_file():
        raise Indisponible("la session n'a pas d'univers (univers\\univers.json) : règles indisponibles")
    numero = (contenu.get("bqw") or {}).get("episode")
    with routeur.session(s):
        autres = {}
        for sc in m.Script.objects.exclude(code=code):
            if (v := sc.versions.order_by("-numero").first()) and not (numero is not None and (v.contenu.get("bqw") or {}).get("episode") == numero):
                autres[f"{sc.code}.json"] = v.contenu
    try:
        erreurs, avis, mesures = lint.lint(contenu, json.loads(f.read_text(encoding="utf-8")), None, autres, None)
    except Exception as e:  # noqa: BLE001
        raise Indisponible(f"lint.py a planté : {type(e).__name__} : {e}") from e
    return {"erreurs": [[c, t] for c, t in erreurs], "avis": [[c, t] for c, t in avis], "mesures": dict(mesures)}


def enregistrer(s: Session, code: str, contenu: dict, acteur: str) -> str:
    """Une version de plus du script (rien d'existant n'est touché), avec le résultat des règles ; une erreur des règles bloque « Fabriquer »."""
    from django.utils import timezone

    from fabrique.noyau.models import noter

    r = controler(s, contenu, code)
    with routeur.session(s):
        sc = m.Script.objects.filter(code=code).first()
        if sc is None and "." in code and (base := m.Script.objects.filter(code=code.split(".")[0]).first()):  # une traduction : « s1e05.fr »
            sc = m.Script.objects.create(code=code, titre=contenu.get("title") or base.titre, langue=code.split(".", 1)[1], statut="traduction",
                                         date_prevue=base.date_prevue)
        if sc is None:
            raise Refus(f"script inconnu : {code}")
        numero = (sc.versions.order_by("-numero").values_list("numero", flat=True).first() or 0) + 1
        m.VersionScript.objects.create(script=sc, numero=numero, auteur=acteur, date=timezone.now(), contenu=contenu, regles=r)
    noter(acteur, "version_script", session=s.id, script=code, numero=numero, erreurs=len(r["erreurs"]))
    return f"{code} : version {numero} enregistrée — {len(r['erreurs'])} erreur(s), {len(r['avis'])} avis"
