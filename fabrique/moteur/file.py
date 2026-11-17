"""La file unique (plan § 5.4) : une tâche = la fabrication d'une vidéo d'une session (base du noyau, Tache). Ordre : les sessions réelles avant
« Essais », puis la priorité de la session, puis l'ordre de mise en file (strict dans une session) ; une tâche en pause ou en erreur attend RT,
les suivantes passent. Une tâche lourde à la fois : à chaque tour, le noyau lance la première (« executer fabrication <id> », détachée : elle
survit à son arrêt) si la carte est libre (carte.py), sinon la tâche attend avec la raison et rien n'est lancé. Une tâche « en cours » dont
l'exécuteur est mort (coupure, PC éteint) est relancée : elle reprend au premier morceau non fini. Seul RT met dans la file une vidéo d'une
session réelle (Fabriquer) ; Claude seulement dans « Essais »."""
import logging
import os
from datetime import datetime, timedelta

from django.utils import timezone

from fabrique import dossiers, programme
from fabrique.garde import Refus
from fabrique.moteur import carte, execution
from fabrique.noyau import routeur, taches
from fabrique.noyau.models import Session, Tache, noter
from fabrique.session.models import Morceau

log = logging.getLogger(__name__)
ACTIVES = ("attente", "en_cours")


def mettre(s: Session, video_id: str, titre: str, acteur: str) -> Tache:
    if not s.essais and acteur != "RT":
        raise Refus("seul RT lance la fabrication d'une vidéo d'une session réelle (Fabriquer)")
    t = Tache.objects.create(session_id=s.id, video_id=video_id, titre=titre, acteur=acteur)
    noter(acteur, "file", tache=t.id, quoi="mise en file", titre=titre)
    return t


def ordre() -> list[Tache]:
    sessions = {s.id: s for s in Session.objects.all()}
    actives = [t for t in Tache.objects.filter(etat__in=ACTIVES) if t.session_id in sessions]
    return sorted(actives, key=lambda t: (sessions[t.session_id].essais, -sessions[t.session_id].priorite, t.cree, t.id))


def tour(lancer=programme.lancer_detache) -> str:
    """Un tour du noyau : lance la première tâche si rien ne tourne et que la carte est libre ; rend la raison de l'attente (vide sinon)."""
    if taches.occupe("fabrication") or not (file := ordre()):
        return ""
    t = file[0]
    if raison := carte.occupee():
        if t.raison != raison:
            Tache.objects.filter(id=t.id).update(raison=raison)
        return raison
    Tache.objects.filter(id=t.id).update(etat="en_cours", raison="", lancee=timezone.now())
    taches.ecrire("fabrication", {"etat": "en_cours", "pid": 0, "tache": t.id, "lancee": datetime.now().isoformat(timespec="seconds")})
    lancer("executer", "fabrication", t.id, journal=dossiers.donnees() / "journaux" / "sortie_fabrication.log")
    noter("noyau", "file", tache=t.id, quoi="lancée" if t.etat == "attente" else "reprise")
    return ""


def alerter(tache_id: int, texte: str):
    t = Tache.objects.get(id=tache_id)
    if texte not in t.alertes:
        Tache.objects.filter(id=tache_id).update(alertes=[*t.alertes, texte])
        noter("moteur", "alerte", tache=tache_id, message=texte)
        log.warning("tâche %s : %s", tache_id, texte)


def executer(tache_id: str = "") -> int:
    """« executer fabrication <id> » : joue ce qui reste de la vidéo ; l'état de la tâche dans la base et dans donnees\\taches\\fabrication.json."""
    t = Tache.objects.filter(id=int(tache_id) if tache_id.isdigit() else 0).first()
    if t is None or t.etat not in ACTIVES:
        print(f"rien à fabriquer pour la tâche « {tache_id} »")
        return 2
    e = taches.lire("fabrication")
    if e.get("pid") not in (None, 0, os.getpid()) and taches.vivante(e):
        print("une fabrication tourne déjà")
        return 3
    taches.ecrire("fabrication", {"etat": "en_cours", "pid": os.getpid(), "tache": t.id, "debut": datetime.now().isoformat(timespec="seconds")})
    Tache.objects.filter(id=t.id).update(etat="en_cours", raison="", lancee=t.lancee or timezone.now())
    etat, raison = "finie", ""
    try:
        execution.jouer(Session.objects.get(id=t.session_id), t.video_id, alerter=lambda texte: alerter(t.id, texte))
    except execution.Echec as x:
        etat, raison = "erreur", str(x)
    except Exception as x:  # noqa: BLE001 — dite à RT (état de la tâche), le détail dans le journal
        log.exception("fabrication %s", t.id)
        etat, raison = "erreur", f"erreur imprévue : {x}"
    Tache.objects.filter(id=t.id, etat="en_cours").update(etat=etat, raison=raison[:500], fin=timezone.now())  # en pause ou annulée entre-temps : laissée
    if raison:
        alerter(t.id, raison)
    taches.ecrire("fabrication", {"etat": "faite" if etat == "finie" else "erreur", "tache": t.id, "fin": datetime.now().isoformat(timespec="seconds"), "message": raison[:300]})
    print(f"tâche {t.id} : {etat}{f' — {raison}' if raison else ''}")
    return 0 if etat == "finie" else 1


def arreter_executeur(t: Tache):
    """« Arrêter » tue l'arbre de l'exécuteur de cette tâche (après le changement d'état : il ne relance rien)."""
    e = taches.lire("fabrication")
    if e.get("tache") == t.id and e.get("pid") and taches.vivante(e):
        programme.tuer(int(e["pid"]))


def agir(tache_id: int, action: str, acteur: str) -> str:
    t = Tache.objects.filter(id=tache_id).first()
    if t is None:
        raise Refus(f"tâche inconnue : {tache_id}")
    permis = {"pause": ACTIVES, "reprendre": ("pause", "erreur"), "annuler": (*ACTIVES, "pause", "erreur")}
    if action not in permis:
        raise Refus(f"action inconnue : {action}")
    if t.etat not in permis[action]:
        raise Refus(f"« {t.titre} » est {t.etat.replace('_', ' ')} : impossible de {action}")
    if action == "reprendre":
        s = Session.objects.get(id=t.session_id)
        with routeur.session(s):
            Morceau.objects.filter(video_id=t.video_id, etat="erreur").update(etat="attente", essais=0)
    etat = {"pause": "pause", "reprendre": "attente", "annuler": "annulee"}[action]
    Tache.objects.filter(id=t.id).update(etat=etat, raison="", fin=timezone.now() if etat == "annulee" else None)
    if action != "reprendre":
        arreter_executeur(t)
    noter(acteur, "file", tache=t.id, quoi=action)
    return {"pause": f"« {t.titre} » mise en pause", "reprendre": f"« {t.titre} » reprendra à son tour",
            "annuler": f"« {t.titre} » annulée (les morceaux déjà faits restent dans la session)"}[action]


def lister() -> list[dict]:
    """La file pour la fenêtre et etat.json : les tâches actives dans l'ordre, puis celles en pause ou en erreur, puis les finies et annulées
    de la dernière semaine. Progression (morceaux finis / tous) de chacune."""
    sessions = {s.id: s for s in Session.objects.all()}
    autres = Tache.objects.filter(etat__in=("pause", "erreur")).order_by("cree")
    passees = Tache.objects.filter(etat__in=("finie", "annulee"), fin__gte=timezone.now() - timedelta(days=7)).order_by("-fin")[:20]
    resultat = []
    for t in [*ordre(), *autres, *passees]:
        s = sessions.get(t.session_id)
        if s is None:
            continue
        with routeur.session(s):
            morceaux = Morceau.objects.filter(video_id=t.video_id)
            finis, total = morceaux.filter(etat="fini").count(), morceaux.count()
        resultat.append({"id": t.id, "titre": t.titre, "session": s.nom, "etat": t.etat, "raison": t.raison, "alertes": t.alertes,
                         "acteur": t.acteur, "progression": f"{finis}/{total}"})
    return resultat
