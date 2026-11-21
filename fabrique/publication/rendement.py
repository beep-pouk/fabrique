"""Statistiques et « quoi fabriquer ensuite » (plan § 7.1, J11 ; cahier § K) : par vidéo, les chiffres de YouTube (relevé quotidien de J4,
rapports « reach » : impressions et taux de clic), le temps de carte (morceaux finis dont l'outil demande la carte), le temps de RT (mesuré
par la fenêtre, TempsRT), les dépenses (outils payants) et les revenus (saisis par RT) ; totaux par session et par destination. Le classement
« quoi fabriquer ensuite » compte par chaîne (une par langue : chacune passe seule la barre de monétisation) : heures vues pour une heure de
carte (la ressource que les sessions se partagent), puis pour une minute de RT, puis revenu. Totaux pondérés repris de Bramble Studio
(core/statistiques.py)."""
from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from fabrique.garde import Refus
from fabrique.moteur import outils
from fabrique.noyau import routeur
from fabrique.noyau.models import Depense, Session
from fabrique.session import models as m

MIN_VIDEOS, MIN_JOURS = 3, 7  # en dessous : « pas assez de chiffres » (une vidéo de moins d'une semaine n'a presque rien de relevé)
JOURS = 28


def pondere(stats: list, champ: str, poids: str = "vues") -> float | None:
    """Moyenne pondérée (rétention par les vues, taux de clic par les impressions) ; None sans poids."""
    paires = [(getattr(s, champ), getattr(s, poids)) for s in stats if getattr(s, champ) is not None and getattr(s, poids)]
    total = sum(p for _, p in paires)
    return round(sum(x * p for x, p in paires) / total, 2) if total else None


def totaux(stats: list) -> dict:
    return {"vues": sum(s.vues for s in stats), "heures": round(sum(s.heures for s in stats), 2), "abonnes": sum(s.abonnes - s.abonnes_perdus for s in stats),
            "retention": pondere(stats, "retention"), "impressions": sum(s.impressions or 0 for s in stats), "ctr": pondere(stats, "ctr", "impressions")}


def code_script(v: m.Video) -> str:
    """« <date>-<code> » (execution, calendrier.videos_de) → le code du script ; sinon le nom tel quel."""
    morceaux = v.nom.split("-", 3)
    return morceaux[3] if len(morceaux) == 4 else v.nom


def carte_s(v: m.Video, langue: str | None = None) -> float:
    """Les secondes de carte de la vidéo (de ses étapes communes et de celles d'une langue, si `langue`) : un outil en lot met tout son temps
    sur son premier morceau, les suivants presque rien — la somme reste juste."""
    fiches = outils.fiches()
    return sum(x.secondes or 0 for x in v.morceaux.filter(etat="fini") if (f := fiches.get(x.outil)) and f.besoins.carte_go > 0
               and (langue is None or x.langue in ("", langue)))


def rt_s(v: m.Video) -> float:
    from django.db.models import Sum

    return m.TempsRT.objects.filter(cle__in=[f"video:{v.id}", f"script:{code_script(v)}"]).aggregate(n=Sum("secondes"))["n"] or 0.0


def publiee_le(pubs: list) -> object:
    jours = [timezone.localdate(p.planifiee_le) for p in pubs if p.identifiant_youtube and p.planifiee_le]
    return min(jours, default=None)


def video(v: m.Video, depenses: dict[str, float]) -> dict:
    """Une ligne de Statistiques → Vidéos (dans « with routeur.session(s) »)."""
    pubs = list(v.publications.all())
    stats = list(m.StatistiqueJour.objects.filter(publication__in=pubs))
    carte_h, rt_min = carte_s(v) / 3600, rt_s(v) / 60
    t = totaux(stats)
    revenus = [p.revenu_eur for p in pubs if p.revenu_eur is not None]
    jour = publiee_le(pubs)
    return {"id": v.id, "titre": v.titre, "format": v.recette.get("id", ""), "langues": sorted(p.langue for p in pubs if p.identifiant_youtube),
            "publiee_le": f"{jour:%d/%m/%Y}" if jour else "", **t, "carte_h": round(carte_h, 2), "rt_min": round(rt_min, 1),
            "depenses_eur": round(depenses.get(v.id, 0.0), 2), "revenu_eur": round(sum(revenus), 2) if revenus else None,
            "par_heure_carte": round(t["heures"] / carte_h, 2) if carte_h else None, "par_minute_rt": round(t["heures"] / rt_min, 3) if rt_min else None,
            "publications": [{"id": p.id, "langue": p.langue, "revenu_eur": p.revenu_eur} for p in pubs if p.identifiant_youtube]}


def depenses_par_video(s: Session) -> dict[str, float]:
    par: dict[str, float] = {}
    for d in Depense.objects.filter(session_id=s.id).exclude(video_id=""):
        par[d.video_id] = par.get(d.video_id, 0.0) + (d.estime_eur if d.reel_eur is None else d.reel_eur)
    return par


def destinations(s: Session, aujourdhui=None) -> list[dict]:
    """Chaque chaîne reliée de la session (mode en cours) : ses chiffres d'ensemble et ses 28 derniers jours (vues par jour)."""
    from fabrique.noyau import etat

    aujourdhui = aujourdhui or timezone.localdate()
    with routeur.session(s):
        lignes = []
        for d in m.Destination.objects.filter(simulation=etat.simulation()).exclude(jeton="").order_by("langue"):
            stats = list(m.StatistiqueJour.objects.filter(destination=d, publication__isnull=True).order_by("date"))
            recents = [x for x in stats if x.date > aujourdhui - timedelta(days=JOURS)]
            lignes.append({"langue": d.langue, "reseau": d.reseau, "chaine": d.chaine, **totaux(stats), "vues_28j": sum(x.vues for x in recents),
                           "heures_28j": round(sum(x.heures for x in recents), 2), "jours": [{"date": f"{x.date:%d/%m}", "vues": x.vues} for x in recents]})
        return lignes


def session(s: Session) -> dict:
    """Statistiques d'une session : ses vidéos (la plus récente en tête, sans la vidéo pilote ni les copies d'essai) et ses destinations."""
    from fabrique.session import reglages

    depenses = depenses_par_video(s)
    with routeur.session(s):
        videos = [video(v, depenses) for v in m.Video.objects.exclude(nom__endswith=f"-{reglages.PILOTE}").exclude(essai=True).order_by("-cree")]
    return {"videos": videos, "destinations": destinations(s)}


def resume(s: Session) -> dict:
    """Une ligne de Statistiques → Sessions : totaux de ses vidéos."""
    v = session(s)["videos"]
    heures, carte_h, rt_min = sum(x["heures"] for x in v), sum(x["carte_h"] for x in v), sum(x["rt_min"] for x in v)
    revenus = [x["revenu_eur"] for x in v if x["revenu_eur"] is not None]
    return {"id": s.id, "nom": s.nom, "videos": len(v), "publiees": sum(1 for x in v if x["langues"]), "vues": sum(x["vues"] for x in v),
            "heures": round(heures, 2), "carte_h": round(carte_h, 2), "rt_min": round(rt_min, 1), "depenses_eur": round(sum(x["depenses_eur"] for x in v), 2),
            "revenu_eur": round(sum(revenus), 2) if revenus else None, "par_heure_carte": round(heures / carte_h, 2) if carte_h else None,
            "par_minute_rt": round(heures / rt_min, 3) if rt_min else None}


def ensuite(aujourdhui=None) -> list[dict]:
    """« Quoi fabriquer ensuite » : un groupe par session, format et chaîne (langue), sur ses vidéos publiées depuis au moins MIN_JOURS jours :
    heures vues de cette langue pour une heure de carte (étapes communes et celles de la langue : ce que coûte une vidéo de plus pour cette
    chaîne), pour une minute de RT, revenu. Les groupes chiffrés d'abord (le meilleur en tête), puis ceux qui n'ont pas assez de chiffres.
    shortcut: heures vues cumulées depuis la publication (une vidéo ancienne pèse plus) ; passer aux 28 premiers jours de chaque vidéo
    quand le catalogue aura plusieurs mois."""
    aujourdhui = aujourdhui or timezone.localdate()
    groupes: dict[tuple, dict] = {}
    for s in Session.objects.filter(essais=False, archivee__isnull=True).order_by("nom"):
        with routeur.session(s):
            for p in m.Publication.objects.exclude(identifiant_youtube="").exclude(video__essai=True).select_related("video"):
                g = groupes.setdefault((s.nom, p.video.recette.get("id", ""), p.langue), {
                    "session": s.nom, "session_id": s.id, "format": p.video.recette.get("id", ""), "langue": p.langue, "videos": 0, "heures": 0.0,
                    "carte_h": 0.0, "rt_min": 0.0, "revenu_eur": None, "recentes": 0})
                if not p.planifiee_le or (aujourdhui - timezone.localdate(p.planifiee_le)).days < MIN_JOURS:
                    g["recentes"] += 1
                    continue
                g["videos"] += 1
                g["heures"] += sum(x.heures for x in p.statistiques.all())
                g["carte_h"] += carte_s(p.video, p.langue) / 3600
                g["rt_min"] += rt_s(p.video) / 60
                if p.revenu_eur is not None:
                    g["revenu_eur"] = (g["revenu_eur"] or 0) + p.revenu_eur
    lignes = []
    for g in groupes.values():
        g["par_heure_carte"] = round(g["heures"] / g["carte_h"], 2) if g["carte_h"] else None
        g["par_minute_rt"] = round(g["heures"] / g["rt_min"], 3) if g["rt_min"] else None
        g["assez"] = g["videos"] >= MIN_VIDEOS and g["par_heure_carte"] is not None
        g["heures"], g["carte_h"], g["rt_min"] = round(g["heures"], 2), round(g["carte_h"], 2), round(g["rt_min"], 1)
        lignes.append(g)
    return sorted(lignes, key=lambda g: (not g["assez"], -(g["par_heure_carte"] or 0), -(g["par_minute_rt"] or 0), -(g["revenu_eur"] or 0), g["session"]))


def noter_temps(s: Session, cle: str, secondes: float):
    """Ajoute du temps de RT à une vidéo ou à un script (la fenêtre l'envoie chaque minute)."""
    if not (cle.startswith("video:") or cle.startswith("script:")) or not 0 < secondes <= 120:
        raise Refus("temps de RT : « video:<id> » ou « script:<code> », de 1 à 120 s")
    with routeur.session(s):
        t, _ = m.TempsRT.objects.get_or_create(cle=cle[:120], date=timezone.localdate())
        m.TempsRT.objects.filter(id=t.id).update(secondes=F("secondes") + secondes)
