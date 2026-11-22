"""Titres et miniatures (plan § 7.1, J11 ; cahier § K) : à l'approbation, jusqu'à trois variantes (titre, miniature) par publication, chacune
notée ; RT en choisit une, avant ou après la publication. Après la publication, la portée de la variante en ligne (impressions et taux de
clic du rapport « reach », relevé chaque jour, ou saisis par RT) ; quand son taux de clic reste sous la médiane de la chaîne après
MIN_IMPRESSIONS impressions, Fabrique propose la variante suivante (la mieux notée pas encore essayée) ; RT l'applique d'un clic.
Miniatures : celle du format, plus deux autres — F1 : deux autres illustrations au gabarit de F1 (repris de core/miniatures.py de Bramble
Studio) ; les autres formats : deux autres moments de la vidéo. Titres : celui du script et ses « titres » (jusqu'à deux, écrits par Claude ;
un scénario de F1 n'en a pas : ses variantes ne changent que la miniature). Marche aussi pour une vidéo « pour enfants » (rien n'y est lié)."""
import json
import math
from datetime import date
from pathlib import Path
from statistics import median

from django.conf import settings
from django.utils import timezone

from fabrique.garde import Refus
from fabrique.noyau import routeur
from fabrique.noyau.models import Session, noter
from fabrique.session import models as m

MIN_IMPRESSIONS = 1000
PETITE = (168, 94)  # une miniature dans une liste YouTube, sur un téléphone
TITRE_LU = 50  # caractères lus en entier sous une miniature, sur un téléphone


def note(image: Path, titre: str) -> tuple[float, list[str]]:
    """Note sur 10, mesurée (jamais un avis) : contraste et couleurs de la miniature réduite à la taille du téléphone, longueur du titre."""
    from PIL import Image, ImageStat

    im = Image.open(image).convert("RGB").resize(PETITE)
    contraste = min(1.0, ImageStat.Stat(im.convert("L")).stddev[0] / 64)
    rg = [r - g for r, g, _ in im.get_flattened_data()]
    yb = [(r + g) / 2 - b for r, g, b in im.get_flattened_data()]

    def moy_et(x):
        mu = sum(x) / len(x)
        return mu, math.sqrt(sum((v - mu) ** 2 for v in x) / len(x))

    (m_rg, e_rg), (m_yb, e_yb) = moy_et(rg), moy_et(yb)
    couleurs = min(1.0, (math.hypot(e_rg, e_yb) + 0.3 * math.hypot(m_rg, m_yb)) / 80)  # « colorfulness » de Hasler et Süsstrunk
    longueur = 1.0 if len(titre) <= TITRE_LU else max(0.0, 1 - (len(titre) - TITRE_LU) / TITRE_LU)
    return round(10 * (contraste + couleurs + longueur) / 3, 1), [f"contraste {contraste:.2f}".replace(".", ","), f"couleurs {couleurs:.2f}".replace(".", ","),
                                                                  f"titre de {len(titre)} caractères" + ("" if longueur == 1 else " (coupé sur téléphone)")]


def miniatures_f1(s: Session, v: m.Video, d: Path, texte: str) -> list[Path]:
    """F1 : deux autres illustrations du plan (au tiers et aux deux tiers, sans celle de la scène de la miniature), au gabarit de F1."""
    from fabrique import dossiers, garde
    from fabrique.moteur.f1 import montage
    from fabrique.moteur.f1.outils import Lieux, Outils

    session = settings.SESSIONS / s.dossier
    if not (cfg := session / "reglages" / "config.json").is_file():
        return []
    lieux = Lieux(garde.studio_bramble() or dossiers.racine().parent, session)
    o = Outils(lieux)
    images = session / "videos" / v.id / "commun" / "atelier" / (v.nom or "video") / "images"
    exclu = f"plan_{int(v.script.get('thumbnail_scene') or 0):03d}.png"
    plans = sorted(p for p in images.glob("plan_*.png") if p.name != exclu)
    choix = sorted({len(plans) // 3, 2 * len(plans) // 3}) if len(plans) > 2 else range(len(plans))
    sorties = []
    for i, k in enumerate(choix, 2):
        if not (out := d / f"miniature_{i}.jpg").is_file():
            montage.dessiner(plans[k], texte, lieux.config(json.loads(cfg.read_text(encoding="utf-8"))).get("miniature", {}), o.police, o.poses / "welcome.png", out)
        sorties.append(out)
    return sorties


def miniatures_video(d: Path, video: Path, cadre: str) -> list[Path]:
    """Les autres formats : la vidéo à la moitié et aux deux tiers, au cadre de la miniature du format (paquets.cadre)."""
    from fabrique.publication import paquets  # ffmpeg par les aides de la publication : le code ne nomme aucun outil (test_moteur)

    mes = paquets.mesure(video)
    l, h = (1280, 720) if cadre == "16:9" else (720, 1280)
    sorties = []
    for i, part in ((2, 1 / 2), (3, 2 / 3)):
        if not (out := d / f"miniature_{i}.jpg").is_file():
            paquets.outil(paquets.exe("ffmpeg"), "-nostdin", "-y", "-v", "error", "-ss", f"{mes['duree_s'] * part:.3f}", "-i", video, "-filter_complex",
                            paquets.cadre(mes["largeur"], mes["hauteur"], l, h), "-frames:v", "1", "-q:v", "3", out)
        sorties.append(out)
    return sorties


def preparer(s: Session, pub: m.Publication, d: Path):
    """Les variantes d'une publication qu'on vient de préparer (dans « with routeur.session(s) ») : la sienne d'abord (titre et miniature
    posés par l'approbation), puis jusqu'à deux autres ; chacune notée. Une miniature impossible à faire ne bloque pas l'approbation."""
    from fabrique.moteur import execution

    v = pub.video
    script = v.script
    if (t := execution.traduction(s, v, pub.langue)).is_file():
        script = json.loads(t.read_text(encoding="utf-8"))
    autres_titres = [x.strip()[:100] for x in script.get("titres", []) if x.strip()][:2]
    try:
        if v.recette.get("script", "scenario-bramble") == "scenario-bramble":
            images = miniatures_f1(s, v, d, (script.get("thumbnail_text") or script.get("title") or v.titre).strip())
        else:
            images = miniatures_video(d, d / pub.fichier, (v.recette.get("reglages") or {}).get("cadre", "16:9"))
    except Exception as e:  # noqa: BLE001 — un outil d'image en panne : la miniature du format reste seule
        noter("noyau", "variantes", session=s.id, publication=pub.pk, erreur=str(e)[:300])
        images = []
    paires = [(pub.titre, pub.miniature)] + [(autres_titres[i] if i < len(autres_titres) else pub.titre, images[i].name if i < len(images) else pub.miniature)
                                             for i in range(max(len(images), len(autres_titres)))]  # un titre sans miniature de rechange garde celle du format
    pub.variantes = []
    for titre, mini in paires:
        try:
            n, raisons = note(d / mini, titre) if mini and (d / mini).is_file() else (None, ["pas de miniature"])
        except OSError:  # image illisible (Pillow) : notée « illisible », l'approbation continue
            n, raisons = None, ["miniature illisible"]
        pub.variantes.append({"titre": titre, "miniature": mini, "note": n, "raisons": raisons, "depuis": None, "portee": None})
    pub.variante = 0


def portee(pub: m.Publication, depuis: date | None, jusqu_a: date | None = None) -> tuple[int, float | None]:
    """Impressions et taux de clic (pondéré) de la publication entre deux jours (bornes comprises, ouvertes si None)."""
    q = m.StatistiqueJour.objects.filter(publication=pub, impressions__isnull=False)
    if depuis:
        q = q.filter(date__gte=depuis)
    if jusqu_a:
        q = q.filter(date__lte=jusqu_a)
    lignes = [(x.impressions, x.ctr) for x in q if x.ctr is not None]
    total = sum(i for i, _ in lignes)
    return total, (round(sum(i * c for i, c in lignes) / total, 2) if total else None)


def debut(pub: m.Publication) -> date | None:
    """Le jour depuis lequel la variante en ligne est mesurée : son changement, sinon la publication."""
    v = pub.variantes[pub.variante] if 0 <= pub.variante < len(pub.variantes) else {}
    if v.get("depuis"):
        return date.fromisoformat(v["depuis"])
    return timezone.localdate(pub.planifiee_le) if pub.planifiee_le else None


def proposition(pub: m.Publication) -> dict | None:
    """La variante à essayer ensuite, si la variante en ligne a eu au moins MIN_IMPRESSIONS impressions et un taux de clic sous la médiane
    des autres vidéos de sa chaîne (même langue, même mode) mesurées sur autant ; None sinon (dans « with routeur.session(s) »)."""
    if not pub.identifiant_youtube or len(pub.variantes) < 2:
        return None
    impressions, ctr = portee(pub, debut(pub))
    autres = [c for p in m.Publication.objects.filter(langue=pub.langue, simulation=pub.simulation).exclude(pk=pub.pk).exclude(identifiant_youtube="")
              for i, c in [portee(p, None)] if i >= MIN_IMPRESSIONS and c is not None]
    if impressions < MIN_IMPRESSIONS or ctr is None or not autres or ctr >= median(autres):
        return None
    restantes = [(x["note"] or 0, k) for k, x in enumerate(pub.variantes) if k != pub.variante and not x.get("depuis") and not x.get("jusqu_a")]  # jamais une variante déjà essayée
    if not restantes:
        return None
    k = max(restantes)[1]
    return {"variante": k, "raison": f"{ctr:g} % de clics sur {impressions} impressions, sous la médiane de la chaîne ({median(autres):g} %) : "
                                     f"essayer la variante {k + 1} (note {pub.variantes[k]['note']})".replace(".", ",")}


def titre_youtube(s: Session, pub: m.Publication, titre: str):
    """Le titre d'une vidéo déjà chez YouTube : videos.update exige tout le « snippet » (catégorie comprise) : lu, puis renvoyé avec le titre."""
    from fabrique.publication import youtube

    _, _, b = youtube.appeler(s, pub.langue, "GET", "/youtube/v3/videos", {"part": "snippet", "id": pub.identifiant_youtube})
    items = json.loads(b).get("items", [])
    if not items:
        raise Refus("vidéo introuvable chez YouTube (supprimée ?)")
    youtube.appeler(s, pub.langue, "PUT", "/youtube/v3/videos", {"part": "snippet"},
                    corps={"id": pub.identifiant_youtube, "snippet": {**items[0]["snippet"], "title": titre}})


def choisir(s: Session, pk: int, k: int, acteur: str) -> str:
    """RT choisit une variante : avant la publication, elle devient le titre (version suivante) et la miniature du brouillon ; après, elle
    part chez YouTube (miniature, puis titre s'il change) et sa portée se mesure depuis aujourd'hui (celle d'avant est gardée)."""
    from fabrique.publication import publication
    from fabrique.publication.youtube import ErreurYoutube

    with routeur.session(s):
        pub = publication._pub(pk)
        if not 0 <= k < len(pub.variantes):
            raise Refus(f"variante inconnue : {k + 1}")
        if k == pub.variante:
            return f"variante {k + 1} déjà posée"
        x = pub.variantes[k]
        en_ligne = bool(pub.identifiant_youtube) and pub.statut in ("planifiee", "non_repertoriee")
        if not en_ligne:
            publication.modifiable(pub)
        if en_ligne:
            try:  # rejouable : un refus en route laisse la base sur l'ancienne variante, le clic suivant refait les deux appels
                if x["titre"] != pub.titre:
                    titre_youtube(s, pub, x["titre"])
                pub.miniature = x["miniature"]
                if x["miniature"]:
                    publication._miniature(s, pub)
            except ErreurYoutube as e:
                raise Refus(f"YouTube a refusé le changement ({e}) : rien n'est noté, réessayer plus tard") from None
            aujourdhui = timezone.localdate()
            ancienne = pub.variantes[pub.variante]
            ancienne["portee"] = dict(zip(("impressions", "ctr"), portee(pub, debut(pub))))
            ancienne["jusqu_a"] = f"{aujourdhui}"
            x["depuis"] = f"{aujourdhui}"
        if x["titre"] != pub.titre:
            pub.versions = [*pub.versions, {"numero": len(pub.versions) + 1, "titre": x["titre"], "description": pub.description, "auteur": acteur,
                                            "date": publication._maintenant()}]
        pub.titre, pub.miniature, pub.variante = x["titre"], x["miniature"], k
        pub.save(update_fields=["titre", "miniature", "variante", "variantes", "versions"])
    noter(acteur, "variante", session=s.id, publication=pk, variante=k, en_ligne=en_ligne)
    return f"variante {k + 1} posée" + (" chez YouTube : sa portée se mesure depuis aujourd'hui" if en_ligne else "")
