"""Exécution d'une recette (plan § 5.3). « preparer » découpe la vidéo en morceaux (étape × unité × langue) rangés dans la base de la session,
l'outil de chacun choisi d'avance ; « jouer » les joue étape par étape (toutes les voix, puis toutes les images… : chaque modèle n'est chargé
qu'une fois par étape). Un morceau s'écrit dans <dossier>.tmp puis prend son nom : fini = gardé ; une coupure reprend au premier morceau non
fini. Trois essais, puis arrêt avec la cause en clair. Outil payant (§ 5.5) : seulement sous les plafonds du mois et de la session (0 € au
départ), une seule nouvelle tentative, sinon repli sur l'outil local de la brique, avec une alerte. Chaque morceau fini laisse son chrono ;
« estimer » en prend la médiane par étape et outil."""
import hashlib
import logging
import shutil
import time
from pathlib import Path
from statistics import median

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from fabrique.moteur import outils, recettes
from fabrique.noyau import routeur
from fabrique.noyau.models import Chrono, Depense, Parametre, Session
from fabrique.session.models import Morceau, Reglage, Video

log = logging.getLogger(__name__)
ESSAIS, ESSAIS_PAYANT = 3, 2  # un appel payant n'est retenté qu'une fois
RESULTAT = "resultat.json"


class Echec(Exception):
    """Un morceau a épuisé ses essais : la cause en clair."""


def preparer(s: Session, recette: dict, script: dict) -> Video:
    R, S = recettes.recette(recette), recettes.script(script)
    with routeur.session(s), transaction.atomic(using=routeur.ouvrir(s)):
        reglages = dict(Reglage.objects.values_list("cle", "valeur"))
        v = Video.objects.create(titre=S.titre, script=script, recette=recette)
        morceaux = [Morceau(video=v, etape=e.id, brique=e.brique, unite=unite, langue=langue, outil=outils.choisir(e.brique, e.id, du_plan, R.outils, reglages))
                    for e in R.etapes for langue in (R.reglages.langues if e.langue else [""]) for unite, du_plan, _ in recettes.unites(S, e.par)]
        for i, m in enumerate(morceaux):
            m.ordre = i
        Morceau.objects.bulk_create(morceaux)
    return v


def dossier(s: Session, m: Morceau) -> Path:
    return settings.SESSIONS / s.dossier / "videos" / m.video_id / (m.langue or "commun") / m.etape / (m.unite or "video")


def couvre(a: str, b: str) -> bool:
    """Deux unités se recouvrent : la même, l'une contient l'autre (« s1 » et « s1/p2 »), ou l'une est la vidéo entière (« »)."""
    return not a or not b or a == b or a.startswith(b + "/") or b.startswith(a + "/")


def resultat(s: Session, m: Morceau) -> outils.Resultat:
    return outils.Resultat.model_validate_json((dossier(s, m) / RESULTAT).read_text(encoding="utf-8"))


def demande(s: Session, v: Video, R: recettes.Recette, S: recettes.Script, i: int, m: Morceau) -> outils.Demande:
    """Ce que le morceau reçoit : son texte et les fichiers des étapes précédentes qui le concernent (même unité, même langue ou commune)."""
    entrees: dict[str, list[str]] = {}
    for avant in R.etapes[:i]:
        for p in v.morceaux.filter(etape=avant.id, etat="fini").order_by("ordre"):
            if couvre(p.unite, m.unite) and (not p.langue or not m.langue or p.langue == m.langue):
                entrees.setdefault(avant.id, []).extend(str(dossier(s, p) / f) for f in resultat(s, p).fichiers)
    texte = next(t for u, _, t in recettes.unites(S, R.etapes[i].par) if u == m.unite)
    graine = int(hashlib.sha256(f"{v.id}/{m.etape}/{m.unite}/{m.langue}".encode()).hexdigest()[:8], 16)  # stable : refaire donne la même chose
    return outils.Demande(brique=m.brique, etape=m.etape, unite=m.unite, langue=m.langue, texte=texte, entrees=entrees,
                          reglages=R.reglages.model_dump(), graine=graine)


def depense_du_mois(**filtre) -> float:
    debut = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return sum(d.estime_eur if d.reel_eur is None else d.reel_eur for d in Depense.objects.filter(date__gte=debut, **filtre))


def refus_payant(s: Session, f: outils.Fiche, cout: float, reglages: dict) -> str:
    """Vide si l'appel payant tient sous le plafond du mois (réglage du noyau) et celui de la session ; sinon la raison, en clair."""
    for quoi, plafond, depense in (("du mois", float(Parametre.lire("plafond_mois_eur") or 0), depense_du_mois()),
                                   ("de la session", float(reglages.get("plafond_eur") or 0), depense_du_mois(session_id=s.id))):
        if plafond <= 0 or depense + cout > plafond:
            return f"{f.nom} est payant ({euros(cout)} l'appel) et le plafond {quoi} est de {euros(plafond)} ({euros(depense)} déjà dépensés)"
    return ""


def euros(x: float) -> str:
    return f"{x:.2f}".replace(".", ",") + " €"


def repli(m: Morceau, raison: str, alerter) -> outils.Fiche:
    f = outils.local(m.brique)
    alerter(f"{raison} : repli sur l'outil local {f.nom}")
    m.outil, m.essais = f.id, 0
    m.save(update_fields=["outil", "essais"])
    return f


def jouer_morceau(s: Session, v: Video, R: recettes.Recette, S: recettes.Script, i: int, m: Morceau, reglages: dict, alerter):
    final = dossier(s, m)
    if (final / RESULTAT).is_file():  # renommé juste avant une coupure : fini
        m.etat = "fini"
        m.save(update_fields=["etat"])
        return
    d = demande(s, v, R, S, i, m)
    f = outils.fiche(m.outil, m.brique)
    if not f.local and (raison := refus_payant(s, f, outils.adaptateur(f).estimer(f, d).cout_eur, reglages)):
        f = repli(m, raison, alerter)
    tmp = final.with_name(final.name + ".tmp")
    while True:
        m.essais += 1
        m.save(update_fields=["essais"])
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        depense = None if f.local else Depense.objects.create(session_id=s.id, outil=f.id, estime_eur=outils.adaptateur(f).estimer(f, d).cout_eur)
        debut = time.monotonic()
        try:
            r = outils.adaptateur(f).fabriquer(f, d, tmp)
            (tmp / "demande.json").write_text(d.model_dump_json(indent=1), encoding="utf-8")
            (tmp / RESULTAT).write_text(r.model_dump_json(indent=1), encoding="utf-8")
            tmp.rename(final)
            break
        except Exception as e:  # noqa: BLE001 — l'outil peut tout lever : essai suivant, repli, ou arrêt avec la cause
            log.warning("%s %s %s, essai %s : %s", m.etape, m.unite or "vidéo", m.langue or "commun", m.essais, e)
            m.message = f"{f.nom} : {e}"[:500]
            m.save(update_fields=["message"])
            if m.essais < (ESSAIS if f.local else ESSAIS_PAYANT):
                continue
            if not f.local:
                f = repli(m, f"{f.nom} a échoué {m.essais} fois ({e})", alerter)
                continue
            m.etat = "erreur"
            m.save(update_fields=["etat"])
            raise Echec(f"étape {m.etape}, {m.unite or 'vidéo'}{f' ({m.langue})' if m.langue else ''} : {f.nom} a échoué {m.essais} fois — {e}") from e
    secondes = time.monotonic() - debut
    if depense:
        depense.reel_eur = r.infos.get("cout_eur")
        depense.save(update_fields=["reel_eur"])
    Chrono.objects.create(etape=m.etape, outil=f.id, secondes=secondes)
    m.etat, m.secondes, m.message = "fini", secondes, ""
    m.save(update_fields=["etat", "secondes", "message"])


def jouer(s: Session, video_id: str, alerter=lambda texte: None):
    """Joue ce qui reste de la vidéo, étape par étape ; Echec si un morceau épuise ses essais."""
    with routeur.session(s):
        v = Video.objects.get(id=video_id)
        R, S = recettes.Recette.model_validate(v.recette), recettes.Script.model_validate(v.script)
        reglages = dict(Reglage.objects.values_list("cle", "valeur"))
        for i, e in enumerate(R.etapes):
            for m in v.morceaux.filter(etape=e.id).exclude(etat="fini").order_by("ordre"):
                jouer_morceau(s, v, R, S, i, m, reglages, alerter)


def estimer(s: Session, video_id: str) -> dict:
    """Ce qui reste à faire : durée (médiane des chronos par étape et outil, sinon l'estimation de l'outil), coût (prix des fiches × quantités),
    mémoire de carte la plus haute demandée."""
    secondes = cout = carte = 0.0
    medianes: dict[tuple[str, str], float | None] = {}
    with routeur.session(s):
        v = Video.objects.get(id=video_id)
        for m in v.morceaux.exclude(etat="fini"):
            f = outils.fiches()[m.outil]
            e = outils.adaptateur(f).estimer(f, outils.Demande(brique=m.brique, etape=m.etape, unite=m.unite, langue=m.langue))
            if (m.etape, f.id) not in medianes:
                chronos = list(Chrono.objects.filter(etape=m.etape, outil=f.id).order_by("-date").values_list("secondes", flat=True)[:50])
                medianes[(m.etape, f.id)] = median(chronos) if chronos else None
            secondes += medianes[(m.etape, f.id)] or e.secondes
            cout, carte = cout + e.cout_eur, max(carte, e.carte_go)
    return {"secondes": round(secondes, 1), "cout_eur": round(cout, 2), "carte_go": carte}
