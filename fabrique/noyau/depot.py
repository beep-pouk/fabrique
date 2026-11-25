"""Le dépôt des discussions Claude (plan § 3.3 et § 4.1 ; repris de Bramble Studio, worker/inbox.py) : un fichier JSON posé dans FABRIQUE\\depot
= une demande, traitée par le noyau à son tour suivant, accusé dans depot\\faits\\<même nom>.json ; un JSON invalide ou une action inconnue =
accusé d'erreur, jamais exécuté. Seulement ce que Claude a le droit de faire (§ 3.3) — jamais l'un des trois gestes de RT :
  {"action": "script", "session": "<nom ou id>", "code": "s1e05", "contenu": {…}}  → une version de plus du script (règles comprises)
  {"action": "essai", "recette": "essai", "script": {…}}                           → un essai dans la file de la session « Essais »
  {"action": "comparaison", "session": …, "code": "s1e01", "titre": …, "bramble": "<.mp4>", "fabrique": "<.mp4>", "plans": [{"debut", "duree"}…]}
                                                                                   → un essai d'animation à comparer (moteur/comparaison.py)
Dans l'autre sens, ce que RT demande à Claude (bouton de l'écran Script) : a_ecrire\\<code>.json, a_traduire\\<code>.<langue>.json."""
import json
import logging
from datetime import datetime
from pathlib import Path

from django.db.models import Q

from fabrique import dossiers, garde
from fabrique.garde import Refus
from fabrique.noyau import routeur
from fabrique.noyau.models import Session, noter
from fabrique.session import models as m

log = logging.getLogger(__name__)
ACTIONS = ("script", "essai", "comparaison")


def session_(cle) -> Session:
    s = Session.objects.filter(Q(id=str(cle)) | Q(nom=str(cle))).first()
    if s is None:
        raise Refus(f"session inconnue : {cle}")
    return s


def executer(demande: dict) -> str:
    from fabrique.moteur import execution, file, recettes
    from fabrique.session import regles

    if not isinstance(demande, dict) or not isinstance(demande.get("action"), str):
        raise ValueError("objet JSON avec une clé « action » attendu")
    if demande["action"] == "script":
        if not isinstance(demande.get("code"), str) or not isinstance(demande.get("contenu"), dict):
            raise ValueError("« code » (texte) et « contenu » (le script) attendus")
        return regles.enregistrer(session_(demande.get("session")), demande["code"], demande["contenu"], "claude")
    if demande["action"] == "essai":
        if not isinstance(demande.get("script"), dict):
            raise ValueError("« script » attendu")
        s = Session.objects.get(essais=True)
        v = execution.preparer(s, recettes.lire(str(demande.get("recette", "essai"))), demande["script"], nom=str(demande.get("nom", "")))
        t = file.mettre(s, v.id, v.titre, "claude")
        return f"« {v.titre} » dans la file de la session {s.nom} (tâche {t.id})"
    if demande["action"] == "comparaison":
        from fabrique.moteur import animatique, comparaison

        s = session_(demande.get("session"))
        animatique.contenu_du_script(s, str(demande.get("code")))  # un script connu : son code entre dans un nom de dossier
        return comparaison.deposer(s, str(demande["code"]), demande)
    raise ValueError(f"action inconnue : {demande['action']} (connues : {', '.join(ACTIONS)})")


def traiter(dossier: Path | None = None) -> list[Path]:
    """Chaque depot\\*.json (ordre des noms) traité, son accusé écrit ; rend les accusés. (= worker/inbox.traiter)"""
    dossier = garde.verifier(dossier or dossiers.depot())
    accuses = []
    for fichier in sorted(dossier.glob("*.json")) if dossier.is_dir() else []:
        accuse = {"fichier": fichier.name, "date": datetime.now().isoformat(timespec="seconds")}
        try:
            demande = json.loads(fichier.read_text(encoding="utf-8-sig"))
            accuse["demande"] = {k: v for k, v in demande.items() if k not in ("contenu", "script")} if isinstance(demande, dict) else str(demande)[:200]
            accuse.update(resultat="ok", message=executer(demande))
        except Refus as e:
            accuse.update(resultat="refus", message=str(e))
        except ValueError as e:  # JSON invalide ou forme inattendue : rien n'est exécuté
            accuse.update(resultat="erreur", message=f"demande invalide : {e}")
        except Exception as e:  # noqa: BLE001 — une demande qui plante est accusée, les autres passent
            log.exception("dépôt : %s", fichier.name)
            accuse.update(resultat="erreur", message=f"{type(e).__name__} : {e}")
        faits = dossier / "faits"
        faits.mkdir(parents=True, exist_ok=True)
        sortie = faits / fichier.name
        if sortie.exists():
            sortie = faits / f"{fichier.stem}_{datetime.now():%Y%m%d_%H%M%S}.json"
        sortie.write_text(json.dumps(accuse, ensure_ascii=False, indent=1), encoding="utf-8")
        fichier.unlink()
        noter("claude", "depot", fichier=fichier.name, resultat=accuse["resultat"])
        accuses.append(sortie)
    return accuses


def demander(s: Session, code: str, quoi: str, langue: str, acteur: str) -> str:
    """RT demande à Claude une nouvelle version (« ecrire ») ou une traduction (« traduire », `langue`) du script : la demande, avec le script le
    plus récent, posée dans depot\\a_ecrire\\ ou depot\\a_traduire\\ (une demande de même nom n'est jamais écrasée) ; Claude rend son travail par
    une demande « script »."""
    if quoi not in ("ecrire", "traduire") or (quoi == "traduire" and not langue):
        raise Refus("demande attendue : « ecrire », ou « traduire » avec une langue")
    from fabrique.moteur import recettes
    from fabrique.session import calendrier

    forme = calendrier.format_du_script(s, code)
    with routeur.session(s):
        sc = m.Script.objects.filter(code=code).first()
        if sc is None:
            raise Refus(f"script inconnu : {code}")
        v = sc.versions.order_by("-numero").first()
        if quoi == "traduire" and not m.Langue.objects.filter(code=langue).exists():
            raise Refus(f"la langue « {langue} » n'est pas une langue de la session")
        d = {"action": quoi, "session": s.nom, "session_id": s.id, "code": code, "titre": sc.titre, "langue": langue, "date_prevue": str(sc.date_prevue or ""),
             "version": v.numero if v else None, "contenu": v.contenu if v else None, "regles": v.regles if v else None, "demande_par": acteur,
             "date": datetime.now().isoformat(timespec="seconds"),
             "format": forme, "forme": (f := recettes.lire(forme)["script"]),  # une compilation ou un extrait cite des vidéos finies de la session :
             "schema": None if f == "scenario-bramble" else recettes.FORMES[f].model_json_schema(),  # ses champs ; Bramble : lint.py et format-scenario
             "videos_finies": [{"id": x.id, "titre": x.titre} for x in m.Video.objects.order_by("cree") if not x.morceaux.exclude(etat="fini").exists()],
             "rendre": f"un fichier JSON dans {dossiers.depot()} : {{\"action\": \"script\", \"session\": \"{s.nom}\", \"code\": \"{code}{'.' + langue if langue else ''}\", \"contenu\": …}}"}
    dossier = garde.verifier(dossiers.depot() / ("a_ecrire" if quoi == "ecrire" else "a_traduire"))
    dossier.mkdir(parents=True, exist_ok=True)
    nom = f"{code}.{langue}" if langue else code
    chemin = dossier / f"{nom}.json"
    if chemin.exists():
        chemin = dossier / f"{nom}_{datetime.now():%Y%m%d_%H%M%S}.json"
    chemin.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    noter(acteur, "demande_claude", session=s.id, script=code, quoi=quoi, langue=langue, fichier=chemin.name)
    return f"{code} : demande {'de nouvelle version' if quoi == 'ecrire' else 'de traduction en ' + langue} déposée pour Claude ({chemin.parent.name}\\{chemin.name})"
