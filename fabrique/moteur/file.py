"""La file unique (plan § 5.4) : une tâche = la fabrication d'une vidéo d'une session (base du noyau, Tache), ou un banc à l'aveugle sur une
vidéo finie (moteur/bancs.py). Ordre : les sessions réelles avant
« Essais », puis la priorité de la session, puis l'ordre de mise en file (strict dans une session) ; une tâche en pause ou en erreur attend RT,
les suivantes passent. Une tâche lourde à la fois : à chaque tour, le noyau lance la première (« executer fabrication <id> », détachée : elle
survit à son arrêt) si la carte est libre (carte.py), sinon la tâche attend avec la raison et rien n'est lancé. Une tâche « en cours » dont
l'exécuteur est mort (coupure, PC éteint) est relancée : elle reprend au premier morceau non fini ; trois relances sans qu'un morceau finisse
(plantage) : erreur et alerte. L'exécuteur prend sa tâche d'un coup, dans la base (jamais deux sur la même vidéo) ; un geste de RT (pause,
annuler) passe avant un lancement. Seul RT met dans la file une vidéo d'une session réelle (Fabriquer) ; Claude seulement dans « Essais »."""
import functools
import logging
import os
import threading
from datetime import datetime, timedelta

from django.db import DatabaseError
from django.utils import timezone

from fabrique import dossiers, programme
from fabrique.garde import Refus
from fabrique.moteur import bancs, carte, execution
from fabrique.noyau import routeur, taches
from fabrique.noyau.models import Banc, Session, Tache, noter
from fabrique.session.models import Morceau

log = logging.getLogger(__name__)
ACTIVES = ("attente", "en_cours")
RELANCES = 3
PAUSE = "session en pause : elle partira à la reprise de la session"
suspendue = threading.Event()  # posé par le noyau pendant une restauration ou une mise à jour : rien n'est lancé


def mettre(s: Session, video_id: str, titre: str, acteur: str, banc: int = 0) -> Tache:
    if not s.essais and acteur != "RT":
        raise Refus("seul RT lance la fabrication d'une vidéo d'une session réelle (Fabriquer)" if not banc else "seul RT lance un banc sur une session réelle")
    t = Tache.objects.create(session_id=s.id, video_id=video_id, titre=titre, acteur=acteur, banc=banc)
    noter(acteur, "file", tache=t.id, quoi="mise en file", titre=titre)
    return t


def ordre() -> list[Tache]:
    """Les tâches actives des sessions qui ne sont pas en pause, dans l'ordre de la file."""
    sessions = {s.id: s for s in Session.objects.filter(pause=False)}
    actives = [t for t in Tache.objects.filter(etat__in=ACTIVES) if t.session_id in sessions]
    return sorted(actives, key=lambda t: (sessions[t.session_id].essais, -sessions[t.session_id].priorite, t.cree, t.id))


def vivant(pid: int) -> bool:
    return bool(pid) and programme.de_l_app(pid)


def tour(lancer=programme.lancer_detache) -> str:
    """Un tour du noyau : lance la première tâche si rien ne tourne et que la carte est libre ; rend la raison de l'attente (vide sinon)."""
    Tache.objects.filter(etat="attente", session_id__in=Session.objects.filter(pause=True).values("id")).exclude(raison=PAUSE).update(raison=PAUSE)
    if suspendue.is_set() or taches.occupe("fabrication") or not (file := ordre()):
        return ""
    t = file[0]
    if vivant(t.executeur):  # elle tourne (son état de fichier est en retard)
        return ""
    if raison := carte.occupee():
        if t.raison != raison:
            Tache.objects.filter(id=t.id, etat__in=ACTIVES).update(raison=raison)
        return raison
    relance = t.etat == "en_cours"
    if relance and t.relances >= RELANCES:
        raison = f"l'exécuteur s'est arrêté {t.relances + 1} fois sans finir un morceau (plantage ou coupures) : détail dans le journal"
        if Tache.objects.filter(id=t.id, etat="en_cours").update(etat="erreur", raison=raison, fin=timezone.now()):
            Banc.objects.filter(id=t.banc, etat__in=("attente", "en_cours")).update(etat="erreur", raison=raison)
            alerter(t.id, raison)
        return ""
    if not Tache.objects.filter(id=t.id, etat=t.etat, executeur=t.executeur).update(etat="en_cours", raison="", lancee=timezone.now(), executeur=0,
                                                                                   relances=t.relances + relance):
        return ""  # RT l'a mise en pause ou annulée pendant ce tour
    taches.ecrire("fabrication", {"etat": "en_cours", "pid": 0, "tache": t.id, "lancee": datetime.now().isoformat(timespec="seconds")})
    lancer("executer", "fabrication", t.id, journal=dossiers.donnees() / "journaux" / "sortie_fabrication.log")
    noter("noyau", "file", tache=t.id, quoi="reprise" if relance else "lancée")
    return ""


def alerter(tache_id: int, texte: str):
    t = Tache.objects.get(id=tache_id)
    if texte not in t.alertes:
        Tache.objects.filter(id=tache_id).update(alertes=[*t.alertes, texte])
        noter("moteur", "alerte", tache=tache_id, message=texte)
        log.warning("tâche %s : %s", tache_id, texte)


def executer(tache_id: str = "") -> int:
    """« executer fabrication <id> » : prend la tâche (refus si un autre exécuteur vivant la tient, ou si la carte qu'elle demande est prise),
    joue ce qui reste de la vidéo ; l'état de la tâche dans la base et dans donnees\\taches\\fabrication.json."""
    t = Tache.objects.filter(id=int(tache_id) if tache_id.isdigit() else 0).first()
    if t is None or t.etat not in ACTIVES:
        print(f"rien à fabriquer pour la tâche « {tache_id} »")
        return 2
    s = Session.objects.get(id=t.session_id)
    if (bancs.estimer(Banc.objects.get(id=t.banc)) if t.banc else execution.estimer(s, t.video_id))["carte_go"] and (
            raison := carte.bramble(datetime.now()) or carte.autre_programme()):
        Tache.objects.filter(id=t.id, etat__in=ACTIVES).update(raison=raison)
        print(f"la carte est prise : {raison}")
        return 3
    if vivant(t.executeur) and t.executeur != os.getpid():
        print("un autre exécuteur tient cette tâche")
        return 3
    if not Tache.objects.filter(id=t.id, etat__in=ACTIVES, executeur=t.executeur).update(executeur=os.getpid(), etat="en_cours", raison="",
                                                                                         lancee=t.lancee or timezone.now()):
        print("la tâche a changé entre-temps (pause, annulation, autre exécuteur)")
        return 3
    taches.ecrire("fabrication", {"etat": "en_cours", "pid": os.getpid(), "tache": t.id, "debut": datetime.now().isoformat(timespec="seconds")})
    etat, raison = "finie", ""
    try:
        (functools.partial(bancs.jouer, t.banc) if t.banc else functools.partial(execution.jouer, s, t.video_id))(
            alerter=lambda texte: alerter(t.id, texte), progres=lambda: Tache.objects.filter(id=t.id, relances__gt=0).update(relances=0))
    except execution.Echec as x:
        etat, raison = "erreur", str(x)
    except Exception as x:  # noqa: BLE001 — dite à RT (état de la tâche), le détail dans le journal
        log.exception("fabrication %s", t.id)
        etat, raison = "erreur", f"erreur imprévue : {x}"
    Tache.objects.filter(id=t.id, etat="en_cours", executeur=os.getpid()).update(etat=etat, raison=raison[:500], fin=timezone.now())  # en pause ou annulée entre-temps : laissée
    if t.banc and etat == "erreur":
        Banc.objects.filter(id=t.banc, etat__in=("attente", "en_cours")).update(etat="erreur", raison=raison[:500])
    if raison:
        alerter(t.id, raison)
    taches.ecrire("fabrication", {"etat": "faite" if etat == "finie" else "erreur", "tache": t.id, "fin": datetime.now().isoformat(timespec="seconds"), "message": raison[:300]})
    print(f"tâche {t.id} : {etat}{f' — {raison}' if raison else ''}")
    return 0 if etat == "finie" else 1


def agir(tache_id: int, action: str, acteur: str) -> str:
    """Pause, reprendre, annuler (RT) : l'état change d'abord (un lancement en cours n'aboutit plus), puis l'exécuteur est arrêté (son arbre)."""
    t = Tache.objects.filter(id=tache_id).first()
    if t is None:
        raise Refus(f"tâche inconnue : {tache_id}")
    permis = {"pause": ACTIVES, "reprendre": ("pause", "erreur"), "annuler": (*ACTIVES, "pause", "erreur")}
    if action not in permis:
        raise Refus(f"action inconnue : {action}")
    etat = {"pause": "pause", "reprendre": "attente", "annuler": "annulee"}[action]
    if not Tache.objects.filter(id=t.id, etat__in=permis[action]).update(etat=etat, raison="", relances=0, fin=timezone.now() if etat == "annulee" else None):
        raise Refus(f"« {t.titre} » est {Tache.objects.get(id=t.id).etat.replace('_', ' ')} : impossible de {action}")
    if t.banc:
        Banc.objects.filter(id=t.banc, etat__in=("attente", "en_cours", "erreur")).update(
            etat={"annuler": "annule", "pause": "attente", "reprendre": "attente"}[action], raison="tâche en pause dans la file" if action == "pause" else "")
    if action == "reprendre":
        if not t.banc:  # un banc ne touche jamais aux morceaux de la vidéo qu'il rejoue
            with routeur.session(Session.objects.get(id=t.session_id)):
                Morceau.objects.filter(video_id=t.video_id, etat="erreur").update(etat="attente", essais=0)
    elif (pid := Tache.objects.get(id=t.id).executeur) and pid != os.getpid():  # jamais le noyau lui-même (pid réutilisé)
        programme.tuer(pid)
    noter(acteur, "file", tache=t.id, quoi=action)
    return {"pause": f"« {t.titre} » mise en pause", "reprendre": f"« {t.titre} » reprendra à son tour",
            "annuler": f"« {t.titre} » annulée (les morceaux déjà faits restent dans la session)"}[action]


def lister() -> list[dict]:
    """La file pour la fenêtre et etat.json : les tâches actives dans l'ordre, puis celles en pause ou en erreur, puis les finies et annulées
    de la dernière semaine. Progression (morceaux finis / tous) de chacune ; une session illisible ne bloque pas les autres."""
    sessions = {s.id: s for s in Session.objects.all()}
    autres = Tache.objects.filter(etat__in=("pause", "erreur")).order_by("cree")
    passees = Tache.objects.filter(etat__in=("finie", "annulee"), fin__gte=timezone.now() - timedelta(days=7)).order_by("-fin")[:20]
    resultat = []
    for t in [*ordre(), *autres, *passees]:
        s = sessions.get(t.session_id)
        if s is None:
            continue
        try:
            if t.banc:
                b = Banc.objects.get(id=t.banc)
                progression = f"{bancs.faites(b)}/{2 * len(b.entrees)}"
            else:
                with routeur.session(s):
                    morceaux = Morceau.objects.filter(video_id=t.video_id)
                    progression = f"{morceaux.filter(etat='fini').count()}/{morceaux.count()}"
        except DatabaseError:
            progression = "base de la session illisible"
        resultat.append({"id": t.id, "titre": t.titre, "session": s.nom, "etat": t.etat, "banc": t.banc, "raison": t.raison, "alertes": t.alertes,
                         "acteur": t.acteur, "progression": progression})
    return resultat
