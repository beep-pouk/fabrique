"""Relevé quotidien des statistiques YouTube (plan § 7.1 J4 et § 8.5), repris de Bramble Studio (core/statistiques.py), par destination : chaque
jour après HEURE (rattrapé au démarrage), la tâche détachée légère « releve » lit, pour chaque destination reliée du mode en cours de chaque
session réelle, la chaîne et ses playlists (deux appels de l'API Data : ils gardent aussi le projet Google actif), puis les chiffres par jour
(reports.query de l'API Analytics) de la chaîne entière et de chacune de ses vidéos publiées (pas les non répertoriées, qui sont des essais).
Les chiffres de YouTube arrivent avec 48 à 72 h de retard : les RETARD_JOURS derniers jours connus sont relus et corrigés ; sinon les HISTOIRE_JOURS jours
avant la liaison (chaîne : chiffres dès le premier relevé) ou depuis la veille du créneau (vidéo) ; un PC éteint plusieurs jours rattrape tout. Un refus (quota, réseau, jeton) n'arrête pas les autres
destinations : il est dit dans l'état de la tâche (alerte), et le relevé est réessayé une heure plus tard. En lecture seule chez YouTube."""
import json
import logging
import os
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from django.db import DatabaseError
from django.utils import timezone

from fabrique import dossiers, programme
from fabrique.garde import Refus
from fabrique.noyau import routeur, taches
from fabrique.noyau.models import Parametre, Session, noter
from fabrique.publication import youtube
from fabrique.session import models as m

log = logging.getLogger(__name__)
METRIQUES = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost"
RETARD_JOURS = 3
HISTOIRE_JOURS = 28  # la fenêtre par défaut de YouTube Studio
HEURE = (9, 0)
REESSAI = timedelta(hours=1)


def du(maintenant: datetime) -> bool:
    """Pas encore réussi aujourd'hui, l'heure passée, et pas d'échec de moins d'une heure."""
    if maintenant < maintenant.replace(hour=HEURE[0], minute=HEURE[1], second=0, microsecond=0) or Parametre.lire("releve_jour") == f"{maintenant.date()}":
        return False
    e = taches.lire("releve")
    try:
        return not (e.get("etat") == "erreur" and maintenant - datetime.fromisoformat(e["fin"]) < REESSAI)
    except (KeyError, ValueError):
        return True


def lancer(acteur: str):
    taches.ecrire("releve", {"etat": "en_cours", "pid": 0, "lancee": datetime.now().isoformat(timespec="seconds")})
    programme.lancer_detache("executer", "releve", journal=dossiers.donnees() / "journaux" / "sortie_releve.log")
    noter(acteur, "releve", quoi="lancé")


def debut(deja, depuis: date, aujourd_hui: date) -> date:
    dernier = deja.order_by("-date").values_list("date", flat=True).first()
    return max(depuis, dernier - timedelta(days=RETARD_JOURS - 1)) if dernier else min(depuis, aujourd_hui)


def enregistrer(d: m.Destination, pub: m.Publication | None, reponse: dict) -> int:
    """Les lignes d'un reports.query (columnHeaders + rows) → un StatistiqueJour par jour, créé ou corrigé (dans « with routeur.session(s) »)."""
    noms = [c["name"] for c in reponse.get("columnHeaders", [])]
    for ligne in reponse.get("rows", []):
        r = dict(zip(noms, ligne))
        m.StatistiqueJour.objects.update_or_create(destination=d, publication=pub, date=date.fromisoformat(r["day"]), defaults={
            "vues": int(r.get("views", 0)), "heures": float(r.get("estimatedMinutesWatched", 0)) / 60, "duree_moyenne": r.get("averageViewDuration"),
            "retention": r.get("averageViewPercentage"), "abonnes": int(r.get("subscribersGained", 0)), "abonnes_perdus": int(r.get("subscribersLost", 0))})
    return len(reponse.get("rows", []))


def rapport(s: Session, d: m.Destination, pub: m.Publication | None, aujourd_hui: date) -> int:
    depuis = timezone.localdate(pub.planifiee_le) - timedelta(days=1) if pub else timezone.localdate(d.reliee) - timedelta(days=HISTOIRE_JOURS)  # jours de l'API à l'heure du Pacifique
    with routeur.session(s):
        premier = debut(m.StatistiqueJour.objects.filter(destination=d, publication=pub), depuis, aujourd_hui)
    if premier > aujourd_hui:  # une vidéo programmée plus tard
        return 0
    params = {"ids": "channel==MINE", "startDate": f"{premier}", "endDate": f"{aujourd_hui}", "metrics": METRIQUES, "dimensions": "day",
              **({"filters": f"video=={pub.identifiant_youtube}"} if pub else {})}
    _, _, corps = youtube.appeler(s, d.langue, "GET", url=youtube.urls()["analytics"] + "/v2/reports?" + urlencode(params))
    with routeur.session(s):
        return enregistrer(d, pub, json.loads(corps))


def relever(aujourd_hui: date | None = None) -> tuple[list[str], list[str]]:
    """Le relevé de toutes les destinations reliées ; rend (fait, alertes)."""
    aujourd_hui = aujourd_hui or timezone.localdate()
    faits, alertes = [], []
    for s in Session.objects.filter(essais=False).order_by("cree"):
        try:
            with routeur.session(s):
                dests = list(youtube._destinations().exclude(jeton="").filter(refusee=None))
        except DatabaseError as e:
            alertes.append(f"{s.nom} : base illisible ({e})")
            continue
        for d in dests:
            try:
                youtube.rafraichir(s, d.langue)
                with routeur.session(s):
                    pubs = list(m.Publication.objects.filter(langue=d.langue, simulation=d.simulation, non_repertorie=False).exclude(identifiant_youtube="")
                                .exclude(planifiee_le=None))
                jours = rapport(s, d, None, aujourd_hui)
                videos = sum(rapport(s, d, p, aujourd_hui) for p in pubs)
                faits.append(f"{s.nom} ({d.langue}) : chaîne {jours} jour(s), {len(pubs)} vidéo(s) {videos} jour(s)")
            except Exception as e:  # noqa: BLE001 — quota, réseau, jeton : les autres destinations continuent, réessai dans une heure
                (log.warning if isinstance(e, (Refus, youtube.ErreurYoutube, OSError, ValueError, KeyError)) else log.exception)("relevé %s (%s) : %s", s.nom, d.langue, e)
                alertes.append(f"relevé des statistiques de {s.nom} ({d.langue}) reporté : {e}")
    return faits, alertes


def executer() -> int:
    """« executer releve » : état dans donnees\\taches\\releve.json (la boucle du noyau notifie une erreur)."""
    if taches.occupe("releve") and int(taches.lire("releve").get("pid", 0)) not in (0, os.getpid()):
        print("le relevé est déjà en cours")
        return 3
    taches.priorite_basse()
    taches.ecrire("releve", {"etat": "en_cours", "pid": os.getpid(), "debut": datetime.now().isoformat(timespec="seconds")})
    faits, alertes = relever()
    if not alertes:
        Parametre.ecrire("releve_jour", f"{timezone.localdate()}")
    taches.ecrire("releve", {"etat": "erreur" if alertes else "fait", "fin": datetime.now().isoformat(timespec="seconds"), "faits": faits,
                             "message": " ; ".join(alertes)[:300], "alertes": alertes})
    noter("noyau", "releve", quoi="fait" if not alertes else "reporté", destinations=len(faits) + len(alertes))
    print("\n".join(faits + alertes) or "relevé : aucune chaîne reliée")
    return 1 if alertes else 0
