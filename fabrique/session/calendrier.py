"""Calendrier et idées des sessions (cahier § E) : statut de chaque script calculé d'après les faits, ordre strict, créneaux estimés.
Repris de Bramble Studio : core/statuts.py (le statut ne descend jamais sous celui qu'imposent les faits), core/ordre.py (un script pas prêt
le jour J n'est jamais sauté : sa date et celles des suivants glissent, écarts gardés ; jamais une publication déjà confiée à YouTube),
core/creneaux.py (« prêt vers le … » : la file dans son ordre, durées estimées d'après les chronos, PC éteint de minuit à 7 h)."""
import logging
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from fabrique.garde import Refus
from fabrique.noyau import evenements, routeur
from fabrique.noyau.models import Journal, Parametre, Session, Tache, noter
from fabrique.session import models as m
from fabrique.session import reglages

STATUTS = [("idee", "idée"), ("script", "script"), ("prete", "prête"), ("fabrication", "en fabrication"), ("a_verifier", "à vérifier"),
           ("approuvee", "approuvée"), ("programmee", "programmée"), ("publiee", "publiée"), ("suivie", "suivie")]
ORDRE = [s for s, _ in STATUTS]
NOMS = dict(STATUTS) | {"reportee": "reportée"}
DE_BRAMBLE = {"idee": "idee", "fiche": "idee", "scenario": "script", "fabrique": "a_verifier", "verifie": "approuvee", "publie": "publiee"}
ACTIVES = ("attente", "en_cours", "pause", "erreur")
CONFIEES = ("en_file", "envoi", "planifiee", "non_repertoriee")  # déjà confiée à YouTube : sa date ne se change plus ici
EXTINCTION, RALLUMAGE = time(0, 0), time(7, 0)
log = logging.getLogger(__name__)


def videos_de(code: str):
    return m.Video.objects.filter(nom__endswith=f"-{code}")  # « <date>-<code> » (execution, F1)


def statut(sc: m.Script, actives: set[str], maintenant: datetime) -> str:
    """Le statut qu'imposent les faits, jamais sous celui gardé (import de Bramble)."""
    v = sc.versions.order_by("-numero").first()
    calc = "idee" if v is None else "script" if (v.regles or {}).get("erreurs") else "prete"
    vids = list(videos_de(sc.code))
    pubs = m.Publication.objects.filter(video__in=vids)
    if any(x.id in actives for x in vids):
        calc = "fabrication"
    elif m.StatistiqueJour.objects.filter(publication__in=pubs).exists():
        calc = "suivie"
    elif pubs.filter(statut="non_repertoriee").exists() or pubs.filter(statut="planifiee", planifiee_le__lte=maintenant).exists():
        calc = "publiee"
    elif pubs.filter(statut="planifiee").exists():
        calc = "programmee"
    elif pubs.exists():
        calc = "approuvee"
    elif any(not x.morceaux.exclude(etat="fini").exists() for x in vids):
        calc = "a_verifier"
    return max(calc, DE_BRAMBLE.get(sc.statut, sc.statut if sc.statut in ORDRE else "idee"), key=ORDRE.index)


def scripts_du_calendrier():
    """Les scripts à dater : ni traductions (« code.langue »), ni vidéo pilote."""
    return m.Script.objects.exclude(code__contains=".").exclude(code=reglages.PILOTE)


def reportes(s: Session) -> set[str]:
    return {d.get("code") for d in Journal.objects.filter(action="ordre_strict", detail__session=s.id).values_list("detail", flat=True)}


def actives(s: Session) -> set[str]:
    return set(Tache.objects.filter(session_id=s.id, etat__in=ACTIVES).values_list("video_id", flat=True))


def fiches(s: Session, debut: date | None, fin: date | None) -> list[dict]:
    """Les fiches du calendrier éditorial (Bramble importé) pas encore devenues un script : au calendrier comme des idées datées, avec leur
    saison et leur événement (événements de l'univers)."""
    with routeur.session(s):
        codes = set(m.Script.objects.values_list("code", flat=True))
        q = m.Prevision.objects.exclude(statut="refusee").filter(date__isnull=False)
        q = q.filter(date__gte=debut) if debut else q
        q = q.filter(date__lte=fin) if fin else q
        return [{"session": s.id, "session_nom": s.nom, "code": "", "date": str(p.date), "statut": "idee", "statut_nom": "fiche du calendrier éditorial", "pret_vers": "",
                 "titre": " · ".join(x for x in (p.details.get("type"), p.details.get("heros"), p.details.get("lieu"), p.details.get("saison"), p.details.get("evenement")) if x)
                          or "fiche"}
                for p in q.order_by("date", "id") if p.details.get("episode", "") not in codes]


def lire(s: Session, debut: date | None = None, fin: date | None = None, prets_vers: dict | None = None) -> list[dict]:
    """Les scripts de la session (datés entre debut et fin, s'ils sont donnés ; sinon tous, les non datés à la fin), leur statut, « reporté »
    (l'ordre strict les a décalés et ils ne sont pas prêts), et « prêt vers le … » s'ils sont dans la file."""
    maintenant, act, rep = timezone.now(), actives(s), reportes(s)
    prets_vers = prets_vers if prets_vers is not None else {}
    items = []
    with routeur.session(s):
        q = scripts_du_calendrier()
        if debut:
            q = q.filter(date_prevue__gte=debut)
        if fin:
            q = q.filter(date_prevue__lte=fin)
        for sc in sorted(q, key=lambda x: (x.date_prevue is None, x.date_prevue or date.min, x.code)):
            st = statut(sc, act, maintenant)
            vid = next((x.id for x in videos_de(sc.code) if x.id in act), "")
            report = sc.code in rep and ORDRE.index(st) < ORDRE.index("approuvee")
            items.append({"session": s.id, "session_nom": s.nom, "code": sc.code, "titre": sc.titre, "date": str(sc.date_prevue or ""),
                          "statut": "reportee" if report else st, "statut_nom": NOMS["reportee" if report else st],
                          "pret_vers": f"{prets_vers[(s.id, vid)]['fin']:%d/%m %H:%M}" if (s.id, vid) in prets_vers else ""})
    return items + fiches(s, debut, fin)


def carte(s: Session) -> dict:
    """Le mur des sessions (Accueil) : vidéos, la dernière, ce qui attend RT, le prochain script daté, vues des 28 derniers jours."""
    from django.db.models import Sum

    aujourdhui, act = timezone.localdate(), actives(s)
    erreurs = Tache.objects.filter(session_id=s.id, etat="erreur").count()
    with routeur.session(s):
        derniere = m.Video.objects.order_by("-cree").first()
        finies = [v for v in m.Video.objects.filter(publications__isnull=True).exclude(nom__endswith=f"-{reglages.PILOTE}")
                  if v.id not in act and not v.morceaux.exclude(etat="fini").exists()]
        a_publier = m.Publication.objects.filter(statut="brouillon").values("video").distinct().count()
        a_faire = 0 if s.essais else erreurs + len(finies) + a_publier  # la session Essais ne publie jamais ; la vidéo pilote se regarde, ne se publie pas
        prochain = next((sc for sc in scripts_du_calendrier().filter(date_prevue__gte=aujourdhui).order_by("date_prevue", "code")
                         if ORDRE.index(statut(sc, act, timezone.now())) < ORDRE.index("publiee")), None)
        vues = m.StatistiqueJour.objects.filter(publication__isnull=True, date__gt=aujourdhui - timedelta(days=28)).aggregate(n=Sum("vues"))["n"]
        assistant = m.Reglage.objects.filter(cle="assistant").values_list("valeur", flat=True).first() or ""
        return {"videos": m.Video.objects.count(), "derniere": derniere.titre if derniere else "", "a_faire": a_faire, "assistant": assistant,
                "prochain": f"{prochain.date_prevue:%d/%m} {prochain.titre}" if prochain else "",
                "rendement": f"{vues:,} vues sur 28 jours".replace(",", " ") if vues is not None else ""}


# ---- créneaux estimés (core/creneaux.py) ----

def ajouter(depart: datetime, secondes: float) -> datetime:
    """`depart` + `secondes` de travail, le PC étant éteint de minuit à 7 h."""
    t, reste = depart, timedelta(seconds=secondes)
    while True:
        if t.time() < RALLUMAGE:
            t = t.replace(hour=RALLUMAGE.hour, minute=0, second=0, microsecond=0)
        minuit = datetime.combine(t.date() + timedelta(days=1), EXTINCTION, tzinfo=t.tzinfo)
        if t + reste <= minuit:
            return t + reste
        reste -= minuit - t
        t = minuit


_estimees: dict = {"quand": 0.0, "fin": {}}


def prets_vers(maintenant: datetime | None = None) -> dict[tuple[str, str], dict]:
    """{(session, vidéo) : {fin (heure estimée où elle sera finie), secondes et cout_eur restants}}, pour chaque tâche active dans l'ordre
    de la file (chronos : médianes). Gardé 10 s : la fenêtre et la page iPhone le demandent à chaque rafraîchissement."""
    import time as horloge

    from fabrique.moteur import bancs, execution, file
    from fabrique.noyau.models import Banc

    if maintenant is None and horloge.monotonic() - _estimees["quand"] < 10:
        return _estimees["fin"]
    t, fin = maintenant or timezone.localtime(), {}
    sessions = {s.id: s for s in Session.objects.all()}
    for tache in file.ordre():
        if (s := sessions.get(tache.session_id)) is None:
            continue
        try:
            e = bancs.estimer(Banc.objects.get(id=tache.banc)) if tache.banc else execution.estimer(s, tache.video_id)
        except Exception:  # noqa: BLE001 — une vidéo illisible n'empêche pas d'estimer les autres
            log.exception("estimation de la vidéo %s", tache.video_id)
            continue
        t = ajouter(t, e["secondes"])
        fin[(s.id, f"banc{tache.banc}" if tache.banc else tache.video_id)] = {"fin": t, "secondes": e["secondes"], "cout_eur": e["cout_eur"]}
    if maintenant is None:
        _estimees.update(quand=horloge.monotonic(), fin=fin)
    return fin


# ---- ordre strict (core/ordre.py) ----

def bloque(code: str) -> bool:
    """Déjà confiée à YouTube (envoyée, même en erreur depuis) : sa date ne se change plus ici."""
    pubs = m.Publication.objects.filter(video__in=videos_de(code))
    return pubs.filter(statut__in=CONFIEES).exists() or pubs.exclude(identifiant_youtube="").exists()


def dater(sc: m.Script, jour: date):
    """La date du script, et le créneau des brouillons de publication de ses vidéos (pas encore confiés à YouTube)."""
    from fabrique.publication.publication import creneau

    sc.date_prevue = jour
    sc.save(update_fields=["date_prevue"])
    for p in m.Publication.objects.filter(video__in=videos_de(sc.code), statut="brouillon"):
        p.planifiee_le = creneau(jour)
        p.save(update_fields=["planifiee_le"])


def recalculer(s: Session, aujourdhui: date | None = None, acteur: str = "noyau") -> list[str]:
    """Décale ce qui doit l'être ; rend une phrase par changement. Réglage « ordre strict » éteint : rien ne bouge."""
    if not reglages.lire(s)["ordre_strict"]:
        return []
    aujourdhui = aujourdhui or timezone.localdate()
    maintenant, act = timezone.now(), actives(s)
    faits, prec_avant, prec_apres = [], None, None
    with routeur.session(s):
        scripts = sorted(scripts_du_calendrier().filter(date_prevue__isnull=False), key=lambda x: (x.date_prevue, x.code))
        for sc in scripts:
            st = statut(sc, act, maintenant)
            if ORDRE.index(st) >= ORDRE.index("publiee"):
                continue
            avant = voulu = sc.date_prevue
            if ORDRE.index(st) < ORDRE.index("approuvee") and voulu <= aujourdhui:
                voulu = aujourdhui + timedelta(days=1)  # pas prêt le jour J : au plus tôt demain
            if prec_apres is not None:
                ecart = max((avant - prec_avant).days, 1)  # écart d'origine gardé, jamais le même jour ni avant le précédent
                voulu = max(voulu, prec_apres + timedelta(days=ecart))
            if voulu != avant:
                if bloque(sc.code):
                    texte = (f"« {sc.titre} » est déjà confiée à YouTube pour le {avant:%d/%m/%Y} alors que la vidéo d'avant n'est pas prête : "
                             "l'ordre serait cassé. À changer à la main (rien n'a été touché sur YouTube).")
                    if not Journal.objects.filter(action="alerte_ordre", detail__session=s.id, detail__code=sc.code, detail__date=str(avant)).exists():
                        noter(acteur, "alerte_ordre", session=s.id, code=sc.code, date=str(avant), message=texte)  # une fois par date
                        evenements.publier("alerte", titre="Ordre strict", message=texte)
                    voulu = avant
                else:
                    dater(sc, voulu)
                    noter(acteur, "ordre_strict", session=s.id, code=sc.code, de=str(avant), vers=str(voulu),
                          motif="pas prête" if ORDRE.index(st) < ORDRE.index("approuvee") else "la vidéo d'avant n'est pas prête")
                    faits.append(f"{sc.code} : {avant:%d/%m/%Y} → {voulu:%d/%m/%Y}")
            prec_avant, prec_apres = avant, voulu
    return faits


def une_fois_par_jour(aujourdhui: date | None = None) -> list[str]:
    """Boucle du noyau : un recalcul par jour et par session en service (les dates ne bougent qu'au changement de jour ou de statut)."""
    aujourdhui = aujourdhui or timezone.localdate()
    faits = []
    for s in Session.objects.filter(essais=False, archivee__isnull=True):
        cle = f"ordre_strict_le.{s.id}"
        if Parametre.lire(cle) != aujourdhui.isoformat():
            try:  # une session illisible n'arrête pas les autres ; retentée demain
                faits += recalculer(s, aujourdhui)
            except Exception:  # noqa: BLE001
                log.exception("ordre strict de la session %s", s.nom)
            Parametre.ecrire(cle, aujourdhui.isoformat())
    return faits


# ---- idées ----

def idees(s: Session) -> list[dict]:
    with routeur.session(s):
        return [{"id": i.id, "titre": i.titre, "resume": i.resume, "source": i.source, "statut": i.statut, "creee": f"{timezone.localtime(i.creee):%d/%m/%Y}"}
                for i in m.Idee.objects.order_by("-creee", "-id")]


def creer_script(s: Session, titre: str, jour: date | None, idee: int, acteur: str, format_: str = "") -> str:
    """Un script neuf (sans version : Claude l'écrit, ou « commande script »), daté ou non, tiré d'une idée ou non, d'un des formats de la
    session (vide : le sien) ; son code « eNN » est le premier libre. Rend son code."""
    from fabrique.session import reglages

    if format_ and format_ not in (formats := reglages.lire(s)["formats"]):
        raise Refus(f"le format {format_} n'est pas parmi ceux de la session ({', '.join(formats)}) : l'ajouter dans l'onglet Formats d'abord")
    with routeur.session(s):
        i = m.Idee.objects.filter(id=idee).first() if idee else None
        if idee and i is None:
            raise Refus(f"idée inconnue : {idee}")
        titre = (titre.strip() or (i.titre if i else ""))[:200]
        if not titre:
            raise Refus("un titre est attendu")
        codes, n = set(m.Script.objects.values_list("code", flat=True)), 1
        while f"e{n:02d}" in codes:
            n += 1
        langue = m.Langue.objects.order_by("ordre", "code").values_list("code", flat=True).first() or "en"
        sc = m.Script.objects.create(code=f"e{n:02d}", titre=titre, langue=langue, statut="idee", date_prevue=jour,
                                     details={**({"idee": i.id, "resume": i.resume} if i else {}), **({"format": format_} if format_ else {})})
        if i:
            i.statut = "convertie"
            i.save(update_fields=["statut"])
    noter(acteur, "script_cree", session=s.id, code=sc.code, idee=idee)
    return sc.code


def format_du_script(s: Session, code: str) -> str:
    """Le format d'un script : le sien (F2, F3…), sinon celui de la session (F1 par défaut)."""
    from fabrique.session import reglages

    with routeur.session(s):
        sc = m.Script.objects.filter(code=code.split(".")[0]).first() if code else None  # « e05.fr » : la traduction de « e05 »
    return (sc and sc.details.get("format")) or reglages.lire(s)["format"] or "F1"


def dater_script(s: Session, code: str, jour: date | None, acteur: str) -> str:
    """RT date (ou retire du calendrier) un script ; jamais une vidéo déjà confiée à YouTube ou publiée."""
    with routeur.session(s):
        sc = scripts_du_calendrier().filter(code=code).first()
        if sc is None:
            raise Refus(f"script inconnu : {code}")
        if bloque(code):
            raise Refus(f"« {sc.titre} » est déjà confiée à YouTube : sa date se change chez YouTube")
        avant = sc.date_prevue
        dater(sc, jour) if jour else m.Script.objects.filter(id=sc.id).update(date_prevue=None)
    noter(acteur, "script_date", session=s.id, code=code, de=str(avant or ""), vers=str(jour or ""))
    return f"« {sc.titre} » : {f'prévue le {jour:%d/%m/%Y}' if jour else 'retirée du calendrier'}."


def ajouter_idee(s: Session, titre: str, resume: str, source: str, acteur: str) -> str:
    if not titre.strip():
        raise Refus("une idée a au moins un titre")
    with routeur.session(s):
        m.Idee.objects.create(titre=titre.strip()[:200], resume=resume.strip(), source=source.strip()[:200] or acteur, creee=timezone.now())
    noter(acteur, "idee", session=s.id, titre=titre.strip()[:200])
    return f"Idée ajoutée à « {s.nom} »."

