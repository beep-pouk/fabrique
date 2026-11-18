"""Exécution d'une recette (plan § 5.3). « preparer » découpe la vidéo en morceaux (étape × unité × langue) rangés dans la base de la session,
l'outil de chacun choisi d'avance ; « jouer » les joue étape par étape (toutes les voix, puis toutes les images… : chaque modèle n'est chargé
qu'une fois par étape). Un morceau s'écrit dans <dossier>.tmp puis prend son nom : fini = gardé ; une coupure reprend au premier morceau non
fini. Trois échecs, puis arrêt avec la cause en clair. Outil payant (§ 5.5) : seulement sous les plafonds du mois et de la session (0 € au
départ), vérifiés avant chaque appel ; une seule nouvelle tentative, sinon repli sur l'outil local de la brique, avec une alerte. Chaque
morceau fini laisse son chrono ; « estimer » en prend la médiane par format, étape et outil."""
import hashlib
import json
import logging
from datetime import datetime
import shutil
import time
from pathlib import Path
from statistics import median

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from fabrique.garde import Refus
from fabrique.moteur import outils, recettes
from fabrique.noyau import routeur
from fabrique.noyau.models import Chrono, Depense, Parametre, Session
from fabrique.session.models import Morceau, Reglage, Video

log = logging.getLogger(__name__)
ESSAIS, ESSAIS_PAYANT = 3, 2  # un appel payant n'est retenté qu'une fois
PAUSE_S = 2.0  # entre deux essais : une panne passagère ne les brûle pas d'un coup
RESULTAT = "resultat.json"


class Echec(Exception):
    """Un morceau a épuisé ses essais : la cause en clair."""


def preparer(s: Session, recette: dict, script: dict, nom: str = "", traductions: dict | None = None) -> Video:
    """La vidéo et ses morceaux ; le script aussi en fichier (videos\\<id>\\<nom>.json : les outils de toute une vidéo le lisent), et ses
    traductions (<nom>.<langue>.json : celles qui ont servi, gardées avec la vidéo)."""
    R = recettes.recette(recette)
    S = recettes.script(script, R.script)
    for vid in ([S.intro, *S.videos] if R.script == "compilation" else [S.source] if R.script == "extrait" else []):
        with routeur.session(s):
            cite = Video.objects.filter(id=vid).first()
        if R.script == "compilation" and cite and (cite.recette.get("script") in ("compilation", "extrait") or (cite.recette.get("reglages") or {}).get("cadre") == "9:16"):
            raise Refus(f"« {cite.titre} » est une compilation ou une courte verticale : une compilation ne prend que des vidéos longues")
        for langue in R.reglages.langues:
            source = finale(s, vid, langue)  # chaque vidéo citée a sa vidéo finale dans chaque langue du format, sinon refus tout de suite
            if R.script == "extrait" and S.fin_s > (duree := sonde(source)):
                raise Refus(f"l'extrait va jusqu'à {S.fin_s:g} s, la vidéo source dure {duree:.1f} s")
    if R.script in recettes.PAR_PLAN:  # le texte d'un morceau est pris dans la traduction de sa langue : mêmes plans, sinon refus tout de suite
        for langue, contenu in (traductions or {}).items():
            if [u for u, *_ in recettes.unites(recettes.script(contenu, R.script), "plan")] != [u for u, *_ in recettes.unites(S, "plan")]:
                raise Refus(f"la traduction en « {langue} » n'a pas les mêmes scènes et plans que le script")
            if contenu.get("musique", script.get("musique")) != script.get("musique"):  # une chanson traduite garde son style, son tempo, sa tonalité
                raise Refus(f"la traduction en « {langue} » change la musique de la chanson : seules les paroles se traduisent")
    with routeur.session(s), transaction.atomic(using=routeur.ouvrir(s)):
        reglages = dict(Reglage.objects.values_list("cle", "valeur"))
        v = Video.objects.create(titre=S.titre, nom=nom, script=script, recette=recette)
        morceaux = decouper(R, S, reglages)
        if manque := [f"{f.nom} ({x})" for o in sorted({m.outil for m in morceaux}) for f in [outils.fiches()[o]] for x in f.exige
                      if not (settings.SESSIONS / s.dossier / x).is_file()]:
            raise Refus(f"« {s.nom} » n'a pas ce que demandent les outils de ce format : {', '.join(manque)}")
        if R.script in recettes.PAR_PLAN and (sans := sorted({m.langue for m in morceaux if m.langue not in ("", R.reglages.langues[0], *(traductions or {}))
                                                                 and not outils.fiches()[m.outil].faux})):
            raise Refus(f"pas de traduction en « {sans[0]} » : une voix réelle y lirait le texte de la langue du script")
        for m in morceaux:
            m.video = v
        Morceau.objects.bulk_create(morceaux)
    fichier_script(s, v).parent.mkdir(parents=True, exist_ok=True)
    fichier_script(s, v).write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
    for langue, contenu in (traductions or {}).items():
        traduction(s, v, langue).write_text(json.dumps(contenu, ensure_ascii=False, indent=1), encoding="utf-8")
    return v


def langues(R: recettes.Recette, S, e: recettes.Etape) -> list[str]:
    """Les langues d'une étape : « » (commune), toutes celles de la recette, ou toutes sauf celle du script (« autres »)."""
    if e.langue == "autres":
        return [l for l in R.reglages.langues if l != (getattr(S, "language", None) or R.reglages.langues[0])]
    return R.reglages.langues if e.langue else [""]


def decouper(R: recettes.Recette, S, reglages: dict) -> list[Morceau]:
    """Les morceaux (pas encore enregistrés) : étape × unité × langue, l'outil de chacun choisi."""
    morceaux = [Morceau(etape=e.id, brique=e.brique, unite=unite, langue=langue, outil=outils.choisir(e.brique, e.id, langue, du_plan, R.outils, reglages))
                for e in R.etapes for langue in langues(R, S, e) for unite, du_plan, *_ in recettes.unites(S, e.par)]
    for i, m in enumerate(morceaux):
        m.ordre = i
    return morceaux


def fichier_script(s: Session, v: Video) -> Path:
    return settings.SESSIONS / s.dossier / "videos" / v.id / f"{v.nom or 'script'}.json"


def traduction(s: Session, v: Video, langue: str) -> Path:
    f = fichier_script(s, v)
    return f.with_name(f"{f.stem}.{langue}.json")


def dossier(s: Session, m: Morceau) -> Path:
    return settings.SESSIONS / s.dossier / "videos" / m.video_id / (m.langue or "commun") / m.etape / (m.unite or "video")


def couvre(a: str, b: str) -> bool:
    """Deux unités se recouvrent : la même, l'une contient l'autre (« s1 » et « s1/p2 »), ou l'une est la vidéo entière (« »)."""
    return not a or not b or a == b or a.startswith(b + "/") or b.startswith(a + "/")


def resultat(s: Session, m: Morceau) -> outils.Resultat | None:
    """Le résultat d'un morceau dont tous les fichiers sont là ; None sinon."""
    return lu(dossier(s, m))


def lu(d: Path) -> outils.Resultat | None:
    try:
        r = outils.Resultat.model_validate_json((d / RESULTAT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return r if all((d / f).is_file() for f in r.fichiers) else None


def demande(s: Session, v: Video, R: recettes.Recette, S: recettes.Script, i: int, m: Morceau) -> outils.Demande:
    """Ce que le morceau reçoit : son texte et les fichiers des étapes précédentes qui le concernent (même unité, même langue ou commune)."""
    entrees: dict[str, list[str]] = {}
    for avant in R.etapes[:i]:
        for p in v.morceaux.filter(etape=avant.id, etat="fini").order_by("ordre"):
            if couvre(p.unite, m.unite) and (not p.langue or not m.langue or p.langue == m.langue):
                entrees.setdefault(avant.id, []).extend(str(dossier(s, p) / f) for f in resultat(s, p).fichiers)
    if m.langue and R.script in recettes.PAR_PLAN and (t := traduction(s, v, m.langue)).is_file():  # le texte dans la langue du morceau
        S = recettes.script(json.loads(t.read_text(encoding="utf-8")), R.script)
    texte, consigne = next((t, c) for u, _, t, c in recettes.unites(S, R.etapes[i].par) if u == m.unite)
    graine = int(hashlib.sha256(f"{v.id}/{m.etape}/{m.unite}/{m.langue}".encode()).hexdigest()[:8], 16)  # stable : refaire donne la même chose
    return outils.Demande(brique=m.brique, etape=m.etape, unite=m.unite, langue=m.langue, texte=texte, consigne=consigne, entrees=entrees,
                          sources={e.id: e.brique for e in R.etapes[:i]}, reglages=R.reglages.model_dump(), graine=graine,
                          session=str(settings.SESSIONS / s.dossier), script=str(fichier_script(s, v)),
                          atelier=str(settings.SESSIONS / s.dossier / "videos" / v.id / (m.langue or "commun") / "atelier" / (v.nom or "video")))


def finale(s: Session, video_id: str, langue: str = "") -> Path:
    """La vidéo finale d'une vidéo de la session dans `langue` (vide : celle du script) : le fichier .mp4 principal du dernier morceau fini de la
    brique montage pour cette langue, ou du montage commun quand c'est la langue du script ; sinon un refus en clair."""
    with routeur.session(s):
        v = Video.objects.filter(id=video_id).first()
        if v is None:
            raise Refus(f"vidéo inconnue dans « {s.nom} » : {video_id}")
        base = v.script.get("language") or (v.recette.get("reglages") or {}).get("langues", [""])[0]
        langue = langue or base
        if v.morceaux.exclude(etat="fini").exists():
            raise Refus(f"« {v.titre} » n'est pas finie (morceaux à faire ou en erreur) : la finir d'abord")
        for m in v.morceaux.filter(brique__in=("montage", "assemblage", "verticale"), etat="fini").order_by("-ordre"):
            if m.langue == langue or (not m.langue and langue == base):
                d = dossier(s, m)
                if (r := resultat(s, m)) and (mp4 := [d / f for f in r.fichiers if f.lower().endswith(".mp4")]):
                    return max(mp4, key=lambda f: f.stat().st_mtime)  # la plus récente, comme la publication (un titre changé laisse l'ancienne)
    raise Refus(f"« {v.titre} » n'a pas de vidéo finale en {langue} : la fabriquer d'abord")


def sonde(video: Path) -> float:
    """La durée d'une vidéo (ffprobe)."""
    from fabrique.publication import paquets

    return paquets.mesure(video)["duree_s"]


def depense_du_mois(**filtre) -> float:
    debut = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return sum(d.estime_eur if d.reel_eur is None else d.reel_eur for d in Depense.objects.filter(date__gte=debut, **filtre))


def refus_payant(s: Session, f: outils.Fiche, cout: float, reglages: dict, pour: str = "l'appel") -> str:
    """Vide si la dépense tient sous le plafond du mois (réglage du noyau) et celui de la session ; sinon la raison, en clair."""
    for quoi, plafond, depense in (("du mois", float(Parametre.lire("plafond_mois_eur") or 0), depense_du_mois()),
                                   ("de la session", float(reglages.get("plafond_eur") or 0), depense_du_mois(session_id=s.id))):
        if plafond <= 0 or depense + cout > plafond:
            return f"{f.nom} est payant ({euros(cout)} {pour}) et le plafond {quoi} est de {euros(plafond)} ({euros(depense)} déjà dépensés)"
    return ""


def euros(x: float) -> str:
    return f"{x:.2f}".replace(".", ",") + " €"


def repli(m: Morceau, raison: str, reglages: dict, alerter) -> outils.Fiche:
    f = outils.local(m.brique, m.langue, reglages)
    alerter(f"{raison} : repli sur l'outil local {f.nom}")
    m.outil, m.essais = f.id, 0
    m.save(update_fields=["outil", "essais"])
    return f


def renommer(tmp: Path, final: Path):
    """Le .tmp prend son nom ; sous Windows, un antivirus ou l'indexation tiennent parfois un fichier neuf un instant."""
    for i in range(5):
        try:
            tmp.rename(final)
            return
        except PermissionError:
            if i == 4:
                raise
            time.sleep(0.5)


def produire(f: outils.Fiche, d: outils.Demande, final: Path) -> outils.Resultat:
    """Un essai de l'outil : il écrit dans <final>.tmp, son résultat est contrôlé, rangé à côté de sa demande, puis le dossier prend son nom."""
    tmp = final.with_name(final.name + ".tmp")
    if final.exists():  # sans résultat complet : abîmé, refait
        shutil.rmtree(final)
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    r = outils.adaptateur(f).fabriquer(f, d, tmp)
    outils.controler_resultat(d.brique, r, tmp)
    (tmp / "demande.json").write_text(d.model_dump_json(indent=1), encoding="utf-8")
    (tmp / RESULTAT).write_text(r.model_dump_json(indent=1), encoding="utf-8")
    renommer(tmp, final)
    return r


def jouer_morceau(s: Session, v: Video, R: recettes.Recette, S: recettes.Script, i: int, m: Morceau, reglages: dict, alerter):
    final = dossier(s, m)
    if resultat(s, m):  # renommé juste avant une coupure : fini
        m.etat = "fini"
        m.save(update_fields=["etat"])
        return
    d = demande(s, v, R, S, i, m)
    f = outils.fiche(m.outil, m.brique, m.langue)
    while True:
        if not f.local and (raison := refus_payant(s, f, outils.adaptateur(f).estimer(f, d).cout_eur, reglages)):
            f = repli(m, raison, reglages, alerter)
        depense = None
        try:
            if not f.local:
                depense = Depense.objects.create(session_id=s.id, outil=f.id, estime_eur=outils.adaptateur(f).estimer(f, d).cout_eur)
            debut = time.monotonic()
            r = produire(f, d, final)
            break
        except Exception as e:  # noqa: BLE001 — l'outil peut tout lever : essai suivant, repli, ou arrêt avec la cause
            m.essais += 1  # seuls les échecs comptent : une coupure en plein morceau n'en est pas un
            log.warning("%s %s %s, échec %s : %s", m.etape, m.unite or "vidéo", m.langue or "commun", m.essais, e)
            m.message = f"{f.nom} : {e}"[:500]
            m.save(update_fields=["essais", "message"])
            if m.essais < (ESSAIS if f.local else ESSAIS_PAYANT):
                time.sleep(PAUSE_S)
                continue
            if not f.local:
                f = repli(m, f"{f.nom} a échoué {m.essais} fois ({e})", reglages, alerter)
                continue
            m.etat = "erreur"
            m.save(update_fields=["etat"])
            raise Echec(f"étape {m.etape}, {m.unite or 'vidéo'}{f' ({m.langue})' if m.langue else ''} : {f.nom} a échoué {m.essais} fois — {e}") from e
    secondes = time.monotonic() - debut
    if depense:
        depense.reel_eur = r.infos.get("cout_eur")
        depense.save(update_fields=["reel_eur"])
    if (lot := r.infos.get("lot")) != 0:  # un outil en lot (toute la langue au premier morceau) : son temps par fichier fait ; 0 : rien calculé ici
        Chrono.objects.create(recette=R.id, etape=m.etape, outil=f.id,
                              secondes=secondes / (lot or 1) / (max(1, len(getattr(S, "scenes", []))) if not m.unite else 1))  # vidéo entière : par scène
    m.etat, m.secondes, m.message = "fini", secondes, ""
    m.save(update_fields=["etat", "secondes", "message"])


def jouer(s: Session, video_id: str, alerter=lambda texte: None, progres=lambda: None):
    """Joue ce qui reste de la vidéo, étape par étape ; `progres()` après chaque morceau fini ; Echec si un morceau épuise ses essais."""
    with routeur.session(s):
        v = Video.objects.get(id=video_id)
        R = recettes.Recette.model_validate(v.recette)
        S = recettes.script(v.script, R.script)
        reglages = dict(Reglage.objects.values_list("cle", "valeur"))
        for i, e in enumerate(R.etapes):
            for m in v.morceaux.filter(etape=e.id).exclude(etat="fini").order_by("ordre"):
                jouer_morceau(s, v, R, S, i, m, reglages, alerter)
                progres()


def refaire(s: Session, video_id: str, plans: list[int], acteur: str) -> str:
    """« Je coche, Fabrique refait » (plan § 5.3), pour une vidéo de F1 : les pièces des plans cochés rangées à côté dans l'atelier (f1/refaire.py),
    les morceaux des étapes qui en dépendent repartent (leur dossier d'avant rangé dans videos\\<id>\\_refaits), la vidéo revient dans la file ;
    seules les pièces manquantes sont refaites."""
    from fabrique.moteur import file
    from fabrique.moteur.f1 import refaire as f1
    from fabrique.noyau.models import Tache

    if Tache.objects.filter(session_id=s.id, video_id=video_id, banc=0, etat__in=("attente", "en_cours", "pause")).exists():
        raise Refus("cette vidéo est encore dans la file : refaire quand elle est finie")
    with routeur.session(s):
        v = Video.objects.filter(id=video_id).first()
        if v is None:
            raise Refus(f"vidéo inconnue : {video_id}")
        if v.recette.get("script") != "scenario-bramble":
            raise Refus("refaire un plan : seulement pour une vidéo du format F1 à ce jalon")
        if v.publications.filter(statut__in=("en_file", "envoi")).exists():
            raise Refus("un envoi de cette vidéo vers YouTube est en cours : refaire une fois l'envoi fini ou annulé")
        envoyee = v.publications.exclude(identifiant_youtube="").exists()
        base = settings.SESSIONS / s.dossier / "videos" / v.id
        _, a_refaire, _ = f1.etapes(v.script, plans)  # les plans contrôlés avant que rien ne bouge
        a_refaire += ["langue"]  # chaque version de langue reprend les visuels de la langue du script : refaite avec eux
        langues = [a for d in sorted(base.iterdir()) if d.name not in ("commun", "_refaits") and (a := d / "atelier" / (v.nom or "video")).is_dir()]
        quand = datetime.now()
        morceaux, horodatage, ranges, rangees = list(v.morceaux.filter(etape__in=a_refaire)), f"{quand:%Y%m%d_%H%M%S_%f}", [], []
        try:  # les morceaux d'abord, puis les pièces des ateliers ; au premier échec, tout revient : jamais une vidéo à moitié remise à faire
            for m in morceaux:
                if (d := dossier(s, m)).exists():
                    (cible := base / "_refaits" / horodatage / f"{m.etape}{'.' + m.langue if m.langue else ''}").parent.mkdir(parents=True, exist_ok=True)
                    d.rename(cible)
                    ranges.append((cible, d))
            for a in langues:
                rangees.append((a, f1.ranger_langue(a, v.script, plans, horodatage)))
            r = f1.preparer(base / "commun" / "atelier" / (v.nom or "video"), v.script, plans, quand=quand)
        except (OSError, Refus) as e:
            for a, rels in reversed(rangees):
                f1.remettre(a, rels, horodatage)
            for cible, d in reversed(ranges):
                cible.rename(d)
            raise e if isinstance(e, Refus) else Refus(f"un fichier de la vidéo est ouvert ailleurs ({e.__class__.__name__}) : rien n'a bougé, réessayer") from e
        for m in morceaux:
            m.etat, m.essais, m.message = "attente", 0, ""
            m.save(update_fields=["etat", "essais", "message"])
        v.publications.update(paquets={"fini": True, "erreur": "vidéo refaite : « Refaire les paquets » une fois la nouvelle vidéo finie"})
    t = file.mettre(s, v.id, v.titre, acteur)
    return (f"« {v.titre} » : plans {r['plans']} à refaire ({', '.join(r['etapes'])}) — {len(r['ranges'])} pièce(s) rangée(s) à côté, tâche {t.id} dans la file"
            + (" ; déjà envoyée sur YouTube : la vidéo en ligne reste l'ancienne" if envoyee else ""))


def estimer(s: Session, video_id: str) -> dict:
    """Ce qui reste à faire d'une vidéo (voir estimer_morceaux)."""
    with routeur.session(s):
        v = Video.objects.get(id=video_id)
        return estimer_morceaux(s, v.recette["id"], list(v.morceaux.exclude(etat="fini")), dict(Reglage.objects.values_list("cle", "valeur")),
                                len(v.script.get("scenes", [])))


def estimer_script(s: Session, recette: dict, script: dict) -> dict:
    """Avant « Fabriquer » : ce que la vidéo de ce script demanderait (rien n'est créé)."""
    R = recettes.recette(recette)
    with routeur.session(s):
        reglages = dict(Reglage.objects.values_list("cle", "valeur"))
        return estimer_morceaux(s, R.id, decouper(R, recettes.script(script, R.script), reglages), reglages, len(script.get("scenes", [])))


def estimer_morceaux(s: Session, recette_id: str, morceaux: list[Morceau], reglages: dict, scenes: int = 0) -> dict:
    """Avec les outils qui serviront vraiment (un payant au-delà des plafonds cède la place à l'outil local) : durée (médiane des chronos par
    format, étape et outil, sinon l'estimation de l'outil), coût (prix des fiches × quantités), mémoire de carte la plus haute demandée."""
    secondes = cout = carte = 0.0
    medianes: dict[tuple[str, str], float | None] = {}
    for m in morceaux:
        d = outils.Demande(brique=m.brique, etape=m.etape, unite=m.unite, langue=m.langue, reglages={"scenes": scenes})
        f = outils.fiches()[m.outil]
        e = outils.adaptateur(f).estimer(f, d)
        if not f.local and refus_payant(s, f, e.cout_eur + cout, reglages):
            f = outils.local(m.brique, m.langue, reglages)
            e = outils.adaptateur(f).estimer(f, d)
        if (m.etape, f.id) not in medianes:
            chronos = list(Chrono.objects.filter(recette=recette_id, etape=m.etape, outil=f.id).order_by("-date").values_list("secondes", flat=True)[:50])
            medianes[(m.etape, f.id)] = median(chronos) if chronos else None
        par = scenes if not m.unite else 1  # les chronos d'une vidéo entière sont rangés par scène
        secondes += e.secondes if medianes[(m.etape, f.id)] is None else medianes[(m.etape, f.id)] * max(1, par)
        cout, carte = cout + e.cout_eur, max(carte, e.carte_go)
    return {"secondes": round(secondes, 1), "cout_eur": round(cout, 2), "carte_go": carte}
