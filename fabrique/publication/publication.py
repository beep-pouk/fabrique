"""Publication YouTube d'une vidéo finie (J4, étape 2), reprise de Bramble Studio (core/publication.py). « Approuver » (geste de RT) prépare un
brouillon par langue depuis les fichiers finaux de la vidéo (videos\\<id>\\<commun ou langue>\\atelier\\<nom>\\final : la vidéo, youtube.txt
— titre, description avec chapitres et crédits, tags —, miniature.jpg, sous_titres.srt ou, pour la langue du script, la transcription de
l'analyse), la playlist proposée (celle du héros) et le créneau du soir. Chaque retouche du titre ou de la description = une version de plus.
« Publier » (geste de RT) : contrôles, chaîne de la langue reliée, puis la tâche détachée légère « publication » (noyau/taches.py, jamais
dans la file de la carte) envoie en « resumable » : session YouTube gardée le temps de l'envoi seulement, octets confirmés en base après
chaque morceau (un processus tué reprend à l'octet que YouTube a reçu, jamais une 2e vidéo), puis playlist, sous-titres et miniature, chacune
faite une fois. La première publication d'une destination part en non répertorié (sans publishAt) ; les suivantes en privé avec publishAt.
Un échec : publication en erreur, alerte en clair, « Reprendre l'envoi »."""
import http.client
import io
import json
import logging
import os
import re
import secrets
import threading
import time
from datetime import UTC, datetime, time as heure, timedelta
from pathlib import Path

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone

from fabrique import dossiers, programme
from fabrique.garde import Refus
from fabrique.noyau import etat, routeur, taches
from fabrique.noyau.models import Session, Tache, noter
from fabrique.session import reglages
from fabrique.publication import youtube
from fabrique.publication.faux_youtube import longueur_tags
from fabrique.session import models as m

log = logging.getLogger(__name__)
SOIR = heure(18, 30)  # le créneau du soir proposé
MARGE_MIN = 15  # un créneau doit être au moins 15 min dans le futur au moment du clic
MORCEAU = 8 * 1024 * 1024  # multiple de 256 Kio (règle de l'envoi « resumable »)
ESSAIS = 8  # coupures ou erreurs 5xx de suite (sans octet de plus confirmé) avant l'erreur
PAUSE_S = 15  # attente avant un nouvel essai : 15 s, 30 s, 1 min… (× 2) ; les tests la mettent à 0
EN_COURS = ("en_file", "envoi")  # posés par « Publier » ou « Reprendre » (RT) seulement : ce que la tâche envoie
CHAPITRE = re.compile(r"^\s*\(?(\d{1,2}:\d{2}(?::\d{2})?)\)?\s+\S")
IMAGES = (".jpg", ".jpeg", ".png")
MODE = "le mode a changé depuis « Publier » (simulation ou réel) : revenir à ce mode pour finir ou annuler l'envoi"
_verrou = threading.Lock()


# ---- fichiers, textes et contrôles ----

def final(s: Session, pub: m.Publication) -> Path:
    v = pub.video
    return settings.SESSIONS / s.dossier / "videos" / v.id / pub.dossier / "atelier" / (v.nom or "video") / "final"


def youtube_txt(chemin: Path) -> dict | None:
    """final\\youtube.txt : « TITRE : », « DESCRIPTION : » (plusieurs paragraphes), « TAGS : » (séparés par des virgules) ; None s'il manque."""
    if not chemin.is_file():
        return None
    parties, partie = {"TITRE": [], "DESCRIPTION": [], "TAGS": []}, None
    for l in chemin.read_text(encoding="utf-8-sig").splitlines():
        tete, deux_points, reste = l.partition(":")
        if deux_points and tete.strip() in parties:
            partie = parties[tete.strip()]
            l = reste
        if partie is not None:
            partie.append(l)
    return {"titre": " ".join(x.strip() for x in parties["TITRE"] if x.strip()), "description": "\n".join(parties["DESCRIPTION"]).strip(),
            "tags": [t.strip() for t in " ".join(parties["TAGS"]).split(",") if t.strip()]}


def chapitres(description: str) -> list[tuple[int, str]]:
    """(secondes, ligne) des lignes « 00:00 Titre » de la description."""
    return [(sum(int(x) * 60 ** i for i, x in enumerate(reversed(c.group(1).split(":")))), l.strip()) for l in description.splitlines() if (c := CHAPITRE.match(l))]


def avis_chapitres(ch: list[tuple[int, str]]) -> list[str]:
    """Règles de YouTube pour que les chapitres apparaissent (non bloquant) : le 1er à 00:00, au moins 3, au moins 10 s chacun."""
    if not ch:
        return ["aucun chapitre lu dans la description"]
    a = [] if ch[0][0] == 0 else ["le premier chapitre doit commencer à 00:00"]
    a += [] if len(ch) >= 3 else [f"{len(ch)} chapitre(s) : YouTube en veut au moins 3"]
    a += [f"chapitre trop court avant « {l} » (moins de 10 s)" for (t1, _), (t2, l) in zip(ch, ch[1:]) if t2 - t1 < 10]
    return a


def fautes_texte(titre: str, description: str) -> list[str]:
    f = [] if titre.strip() else ["titre vide"]
    f += [f"titre trop long ({len(titre)} caractères, 100 au plus)"] if len(titre) > 100 else []
    f += [f"description trop longue ({len(description.encode('utf-8'))} octets, 5000 au plus)"] if len(description.encode("utf-8")) > 5000 else []
    f += [f"{nom} : les caractères < et > sont refusés par YouTube" for nom, t in (("titre", titre), ("description", description)) if "<" in t or ">" in t]
    return f


def fautes(s: Session, pub: m.Publication) -> list[str]:
    """Ce qui bloque « Publier » (YouTube refuserait l'envoi)."""
    f = fautes_texte(pub.titre, pub.description)
    f += [f"tags trop longs ({longueur_tags(pub.tags)} caractères, 500 au plus)"] if longueur_tags(pub.tags) > 500 else []
    f += [f"tag « {t} » : les caractères < et > sont refusés par YouTube" for t in pub.tags if "<" in t or ">" in t]
    d = final(s, pub)
    f += [] if pub.fichier and (d / pub.fichier).is_file() else [f"vidéo absente : {d / pub.fichier}"]
    mi = d / pub.miniature
    f += [f"miniature trop lourde ({mi.stat().st_size // 1024} Ko, 2 Mo au plus)"] if pub.miniature and mi.is_file() and mi.stat().st_size > 2 * 1024 * 1024 else []
    return f


def segments(video: Path) -> list[dict]:
    """Segments de <vidéo>.transcription.json (l'analyse) : « segments » (Whisper : start / end / text), ou « mots » (t / fin / mot) regroupés en
    sous-titres (fin de phrase, 42 caractères ou 6 s) ; vide s'il manque ou s'il est illisible."""
    try:
        d = json.loads(video.with_name(video.stem + ".transcription.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(d, dict):
        return []
    if "segments" in d or "mots" not in d:
        return d.get("segments") or []
    segs, mots = [], []
    for x in d["mots"]:
        mots.append(x)
        texte = " ".join(str(y.get("mot", "")) for y in mots).strip()
        if texte[-1:] in ".!?" or len(texte) >= 42 or float(x.get("fin") or x["t"]) - float(mots[0]["t"]) >= 6:
            segs.append({"start": float(mots[0]["t"]), "end": float(x.get("fin") or x["t"]), "text": texte})
            mots = []
    if mots:
        segs.append({"start": float(mots[0]["t"]), "end": float(mots[-1].get("fin") or mots[-1]["t"]), "text": " ".join(str(y.get("mot", "")) for y in mots).strip()})
    return segs


def srt(segs: list[dict]) -> str:
    def t(sec: float) -> str:
        ms = round(sec * 1000)
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    lignes = [(x["start"], x["end"], str(x["text"]).strip()) for x in segs if str(x.get("text", "")).strip()]
    return "\n".join(f"{i}\n{t(a)} --> {t(b)}\n{texte}\n" for i, (a, b, texte) in enumerate(lignes, 1))


def sous_titres(s: Session, pub: m.Publication) -> str:
    """Le SRT de la langue : final\\sous_titres.srt (versions de langue), sinon la transcription de la vidéo par l'analyse (langue du script)."""
    d = final(s, pub)
    if (f := d / "sous_titres.srt").is_file():
        return f.read_text(encoding="utf-8-sig").strip()
    return srt(segments(d / pub.fichier))


# ---- créneau, playlist, brouillons ----

def creneau(jour=None, maintenant: datetime | None = None) -> datetime:
    """Le créneau du soir du jour prévu, ou le prochain soir à venir s'il est passé (heure de Paris)."""
    maintenant = maintenant or timezone.now()
    jour = jour or timezone.localdate(maintenant)
    while (t := timezone.make_aware(datetime.combine(jour, SOIR))) < maintenant + timedelta(minutes=MARGE_MIN):
        jour += timedelta(days=1)
    return t


def playlist_proposee(script: dict, playlists: list[dict]) -> str:
    """La playlist de la chaîne dont le titre contient le héros du script ; vide sinon."""
    cle = ((script.get("bqw") or {}).get("hero") or "").lower()
    return next((p["id"] for p in playlists if cle and cle in p["titre"].lower()), "")


def _maintenant() -> str:
    return timezone.localtime().isoformat(timespec="seconds")


def approuver(s: Session, video_id: str, acteur: str) -> str:
    """Geste de RT : la vidéo, finie, reçoit un brouillon par langue (la langue du script, puis chaque version de langue) ; ceux déjà là sont
    gardés (retouches comprises). Rien ne part avant « Publier »."""
    if acteur != "RT":
        raise Refus("seul RT approuve une vidéo (Approuver)")
    if s.essais:
        raise Refus("la session « Essais » ne publie jamais")
    if Tache.objects.filter(session_id=s.id, video_id=video_id, etat__in=("attente", "en_cours", "pause")).exists():
        raise Refus("cette vidéo est dans la file : l'approuver une fois sa fabrication finie")
    with routeur.session(s):
        v = m.Video.objects.filter(id=video_id).first()
        if v is None:
            raise Refus(f"vidéo inconnue : {video_id}")
        if reste := v.morceaux.exclude(etat="fini").count():
            raise Refus(f"« {v.titre} » : fabrication pas finie ({reste} morceau(x) à faire)")
        if not etat.simulation() and v.morceaux.filter(outil__startswith="faux_").exists():
            raise Refus(f"« {v.titre} » est faite par les faux outils (vidéo pilote, essai) : elle ne part jamais sur une vraie chaîne")
        langues = v.recette["reglages"]["langues"]
        base = v.script.get("language") or langues[0]
        playlists = {d.langue: d.playlists for d in youtube._destinations()}
        sc = m.Script.objects.filter(code=v.nom[11:]).first()  # « <date prévue>-<code> » : la date du calendrier, que l'ordre strict a pu décaler
        try:
            jour = sc.date_prevue if sc and sc.date_prevue else datetime.strptime(v.nom[:10], "%Y-%m-%d").date()
        except ValueError:
            jour = None
        regles = reglages.lire(s)
        faites = []
        with transaction.atomic(using=routeur.ouvrir(s)):
            for langue in dict.fromkeys([base, *langues]):
                if v.publications.filter(langue=langue).exists():
                    continue
                pub = m.Publication(video=v, langue=langue, dossier="commun" if langue == base else langue)
                d = final(s, pub)
                if v.recette.get("script") != "scenario-bramble":
                    preparer_final(s, v, langue, d)
                if (mp4 := max(d.glob("*.mp4"), key=lambda p: p.stat().st_mtime, default=None)) is None:
                    raise Refus(f"« {v.titre} » ({langue}) : aucune vidéo finale dans {d}")
                t = youtube_txt(d / "youtube.txt") or {"titre": v.titre, "description": "", "tags": v.script.get("tags", [])}
                pub.fichier, pub.miniature = mp4.name, next((f.name for f in (d / "miniature.jpg", d / "miniature.png") if f.is_file()), "")
                pub.titre, pub.description, pub.tags = t["titre"], t["description"], t["tags"]
                if v.essai and "essai" not in pub.titre.lower():
                    pub.titre = f"ESSAI — {pub.titre}"[:100]
                pub.playlist, pub.planifiee_le = playlist_proposee(v.script, playlists.get(langue, [])), creneau(jour)
                pub.enfants, pub.ia = regles["enfants"], regles["declaration_ia"]  # les règles de la session (Session → Règles)
                pub.versions = [{"numero": 1, "titre": pub.titre, "description": pub.description, "auteur": "noyau", "date": _maintenant()}]
                pub.save()
                faites.append(langue)
    noter(acteur, "approuver", session=s.id, video=video_id, langues=faites)
    return f"« {v.titre} » approuvée : brouillon(s) {', '.join(faites)} à relire avant « Publier »" if faites else f"« {v.titre} » : brouillons déjà prêts"


def horodatage(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t // 60 % 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:02d}:{t % 60:02d}"


def preparer_final(s: Session, v: m.Video, langue: str, d: Path):
    """Une vidéo d'un format hors F1 (F2, F3, F4) : à l'approbation, son dossier « final » est rempli comme celui de F1 (la publication le lit
    tel quel) : vidéo finale de la langue, sa miniature et ses sous-titres (liens durs, sinon copies), youtube.txt tiré du script dans la
    langue (titre, description, chapitres d'une compilation, tags). Un fichier déjà là n'est pas refait."""
    from fabrique.moteur import execution
    from fabrique.moteur.f1.adaptateur import lier

    video = execution.finale(s, v.id, langue)
    for source, cible in [(video, d / video.name), (video.with_suffix(".srt"), d / "sous_titres.srt")]:
        if source.is_file() and not cible.exists():
            lier(source, cible)
    mini = v.morceaux.filter(brique="miniature", etat="fini", langue__in=(langue, "")).order_by("-ordre").first()
    if mini and (r := execution.resultat(s, mini)) and (img := next((f for f in r.fichiers if f.lower().endswith((".jpg", ".png"))), None)):
        if not (cible := d / f"miniature{Path(img).suffix.lower()}").exists():
            lier(execution.dossier(s, mini) / img, cible)
    if not (d / "youtube.txt").is_file():
        script = v.script
        if (t := execution.traduction(s, v, langue)).is_file():
            script = json.loads(t.read_text(encoding="utf-8"))
        r = json.loads((video.parent / execution.RESULTAT).read_text(encoding="utf-8"))
        chapitres = "\n".join(f"{horodatage(c['debut'])} {c['titre']}" for c in r["infos"].get("chapitres", []))
        description = "\n\n".join(x for x in (script.get("description", "").strip(), chapitres) if x)
        (d / "youtube.txt").write_text(f"TITRE : {script.get('titre') or v.titre}\nDESCRIPTION : {description}\nTAGS : {', '.join(script.get('tags', []))}\n",
                                       encoding="utf-8")


def premiere(pub: m.Publication) -> bool:
    """Aucune autre publication de sa destination (langue, mode) n'a quitté le brouillon : celle-ci part en non répertorié. Une vidéo d'essai
    aussi, toujours : jamais programmée publique."""
    return pub.video.essai or not m.Publication.objects.filter(langue=pub.langue, simulation=etat.simulation()).exclude(pk=pub.pk).exclude(statut="brouillon").exists()


def apercu(s: Session, video_id: str) -> list[dict]:
    """Tout ce qui partira, par langue, et ce qui bloque « Publier » ; jamais l'adresse de la session d'envoi."""
    chaines = {d["langue"]: d for d in youtube.lister(s)}
    with routeur.session(s):
        pubs = list(m.Publication.objects.filter(video_id=video_id).select_related("video").order_by("pk"))
        lignes = []
        for pub in pubs:
            d, ch, e = final(s, pub), chapitres(pub.description), pub.envoi
            c = chaines.get(pub.langue, {"etat": "pas reliée", "reliee": False, "chaine": "", "playlists": []})
            test = pub.non_repertorie if pub.statut != "brouillon" else premiere(pub)
            lignes.append({
                "id": pub.pk, "langue": pub.langue, "statut": pub.statut, "titre": pub.titre, "description": pub.description, "tags": pub.tags,
                "chapitres": [l for _, l in ch], "playlist": pub.playlist,
                "playlist_titre": next((p["titre"] for p in c["playlists"] if p["id"] == pub.playlist), ""),
                "video": str(d / pub.fichier), "miniature": str(d / pub.miniature) if pub.miniature else "",
                "miniatures": sorted(f.name for f in d.glob("*") if f.suffix.lower() in IMAGES), "enfants": pub.enfants, "ia": pub.ia,
                "non_repertorie": test, "creneau": "" if test else f"{timezone.localtime(pub.planifiee_le):%d/%m/%Y %H:%M}",
                "destination": c["etat"], "chaine": c["chaine"], "fautes": fautes(s, pub),
                "avis": avis_chapitres(ch) + ([] if sous_titres(s, pub) else ["sans sous-titres : ni sous_titres.srt ni transcription"])
                + ([] if c["reliee"] else ["chaîne de la langue pas reliée : brouillon seulement, « Publier » refusé"]),
                "versions": len(pub.versions), "lien": f"https://youtu.be/{pub.identifiant_youtube}" if pub.identifiant_youtube else "",
                "envoi": f"{e.get('octets', 0) / 1e6:.1f} / {e['taille'] / 1e6:.1f} Mo".replace(".", ",") + (f" ; fait : {', '.join(e['fait'])}" if e.get("fait") else "")
                if e.get("taille") else "", "erreur": e.get("erreur", "")})
    return lignes


def copier_essai(video_id: str, suffixe: str) -> str:
    """« commande copier-essai <vidéo> <suffixe> » (Claude, préparation des gestes de RT de la recette J4) : une vidéo finie de la session Essais
    copiée dans la première session réelle, marquée essai (jamais au calendrier, toujours publiée en non répertorié) : la vidéo et ses morceaux
    finis en base, seulement les dossiers « final » de chaque langue sur le disque. Rien n'est publié : RT approuve et publie."""
    import shutil

    essais, cible = Session.objects.get(essais=True), Session.objects.filter(essais=False).order_by("cree").first()
    if cible is None:
        raise Refus("aucune session réelle : importer d'abord Bramble Studio (commande importer-bramble --pour-de-vrai)")
    with routeur.session(essais):
        v = m.Video.objects.filter(id=video_id).first()
        if v is None or not v.morceaux.exists() or v.morceaux.exclude(etat="fini").exists():
            raise Refus(f"vidéo de la session Essais inconnue ou pas finie : {video_id}")
        morceaux = list(v.morceaux.values("etape", "brique", "unite", "langue", "ordre", "outil", "etat", "secondes"))
    source = settings.SESSIONS / essais.dossier / "videos" / v.id
    finals = list(source.glob("*/atelier/*/final"))
    if not finals:
        raise Refus(f"« {v.titre} » : aucun dossier final")
    copie = m.Video(titre=f"ESSAI {suffixe} — {v.titre}"[:200], nom=v.nom, script=v.script, recette=v.recette, essai=True)
    for d in finals:  # les fichiers d'abord : jamais une vidéo en base sans eux
        shutil.copytree(d, settings.SESSIONS / cible.dossier / "videos" / copie.id / d.relative_to(source))
    with routeur.session(cible):
        with transaction.atomic(using=routeur.ouvrir(cible)):
            copie.save()
            m.Morceau.objects.bulk_create([m.Morceau(video=copie, **x) for x in morceaux])
    noter("claude", "copier_essai", source=video_id, session=cible.id, video=copie.id)
    return f"« {copie.titre} » copiée dans « {cible.nom} » (vidéo {copie.id}) : à approuver puis publier par RT, en non répertorié"


# ---- retoucher, choisir ----

def _pub(pk: int) -> m.Publication:
    pub = m.Publication.objects.select_related("video").filter(pk=pk).first()
    if pub is None:
        raise Refus(f"publication inconnue : {pk}")
    return pub


def modifiable(pub: m.Publication):
    if pub.statut in EN_COURS:
        raise Refus("déjà dans la file d'envoi")
    if pub.statut not in ("brouillon", "erreur"):
        raise Refus(f"publication {pub.statut.replace('_', ' ')} : plus modifiable (YouTube Studio)")


def deja(pub: m.Publication, etape: str, quoi: str):
    """Après une erreur, ce qui est déjà parti chez YouTube ne se change plus d'ici (YouTube Studio)."""
    if etape in pub.envoi.get("fait", []):
        raise Refus(f"{quoi} déjà envoyé(e) à YouTube : à changer dans YouTube Studio")


def retoucher(s: Session, pk: int, titre: str, description: str, acteur: str) -> str:
    """Titre et description retouchés = version suivante (les précédentes restent) ; refus si YouTube les refuserait."""
    with routeur.session(s):
        pub = _pub(pk)
        modifiable(pub)
        deja(pub, "video", "titre et description")
        titre, description = titre.strip(), description.replace("\r\n", "\n").strip()
        if f := fautes_texte(titre, description):
            raise Refus(" ; ".join(f))
        if (titre, description) == (pub.titre, pub.description):
            return "titre et description inchangés"
        if session_resolue(s, pub):  # une session ouverte porte les anciens textes : abandonnée si incomplète, sinon la vidéo est déjà là
            raise Refus("vidéo arrivée chez YouTube entre-temps, avec les anciens textes : les changer dans YouTube Studio, puis Reprendre l'envoi")
        numero = len(pub.versions) + 1
        pub.versions = [*pub.versions, {"numero": numero, "titre": titre, "description": description, "auteur": acteur, "date": _maintenant()}]
        pub.titre, pub.description = titre, description
        pub.save(update_fields=["versions", "titre", "description"])
    noter(acteur, "retoucher", session=s.id, publication=pk, version=numero)
    return f"version {numero} du titre et de la description"


def choisir(s: Session, pk: int, acteur: str, miniature: str = "", playlist: str | None = None, jour: str = "", horaire: str = "") -> str:
    """Les choix de l'aperçu : miniature (une image de final), playlist (une de la chaîne, « » : aucune), créneau (date et heure de Paris, à venir)."""
    with routeur.session(s):
        pub = _pub(pk)
        modifiable(pub)
        faits = []
        if miniature and miniature != pub.miniature:
            if Path(miniature).name != miniature or Path(miniature).suffix.lower() not in IMAGES or not (final(s, pub) / miniature).is_file():
                raise Refus(f"miniature inconnue : {miniature}")
            deja(pub, "miniature", "miniature")
            pub.miniature = miniature
            faits.append(f"miniature {miniature}")
        if playlist is not None and playlist != pub.playlist:
            deja(pub, "playlist", "playlist")
            connues = {p["id"]: p["titre"] for d in youtube._destinations().filter(langue=pub.langue) for p in d.playlists}
            if playlist and playlist not in connues:
                raise Refus("playlist inconnue de la chaîne (Système → Destinations → Rafraîchir)")
            pub.playlist = playlist
            faits.append("playlist " + (connues[playlist] if playlist else "aucune"))
        if jour and horaire:
            try:
                quand = timezone.make_aware(datetime.combine(datetime.strptime(jour, "%Y-%m-%d").date(), datetime.strptime(horaire, "%H:%M").time()))
            except ValueError as e:
                raise Refus("créneau : date AAAA-MM-JJ et heure HH:MM attendues") from e
            if quand != pub.planifiee_le:
                deja(pub, "video", "créneau")
                if quand < timezone.now() + timedelta(minutes=MARGE_MIN):
                    raise Refus(f"créneau passé ou trop proche : {timezone.localtime(quand):%d/%m %H:%M}")
                if session_resolue(s, pub):  # une session ouverte porte l'ancien publishAt
                    raise Refus("vidéo arrivée chez YouTube entre-temps, à l'ancien créneau : le changer dans YouTube Studio, puis Reprendre l'envoi")
                pub.planifiee_le = quand
                faits.append(f"créneau {timezone.localtime(quand):%d/%m/%Y %H:%M}")
        if faits:
            pub.save(update_fields=["miniature", "playlist", "planifiee_le"])
    if faits:
        noter(acteur, "publication_choix", session=s.id, publication=pk, choix=faits)
    return "choisi : " + ", ".join(faits) if faits else "rien de changé"


# ---- Publier, Reprendre, Annuler ----

def _avant_l_heure(pub: m.Publication):
    """Au clic et à l'ouverture d'une session : YouTube publie tout de suite une vidéo programmée à une heure passée, il faut 15 min de marge."""
    if not pub.non_repertorie and pub.planifiee_le < timezone.now() + timedelta(minutes=MARGE_MIN):
        raise Refus(f"créneau passé ou trop proche ({timezone.localtime(pub.planifiee_le):%d/%m %H:%M}) : en choisir un à venir, puis Publier ou Reprendre l'envoi")


def publier(s: Session, pk: int, acteur: str) -> str:
    """Le clic de RT : contrôles, chaîne de la langue reliée, créneau à venir (sauf première publication de la destination : non répertoriée),
    puis la tâche « publication ». Double clic : la mise en file est une mise à jour conditionnelle dans une transaction, le 2e ne trouve plus
    de brouillon."""
    if acteur != "RT":
        raise Refus("seul RT publie (Publier)")
    with routeur.session(s):
        pub = _pub(pk)
        modifiable(pub)
        if Tache.objects.filter(session_id=s.id, video_id=pub.video_id, etat__in=("attente", "en_cours", "pause")).exists():
            raise Refus("cette vidéo est de nouveau dans la file de fabrication : Publier une fois finie")
        if pub.identifiant_youtube or session_resolue(s, pub):  # partie (ou arrivée, réponse perdue) : un 2e envoi ferait une 2e vidéo
            raise Refus("vidéo déjà envoyée à YouTube : Reprendre l'envoi")
        if f := fautes(s, pub):
            raise Refus(" ; ".join(f))
        d = youtube._destinations().filter(langue=pub.langue).first()
        if d is None or not d.jeton:
            raise Refus(f"YouTube ({pub.langue}) : chaîne pas reliée — la relier depuis la fenêtre (PC), puis Publier ; le brouillon reste")
        if d.refusee:
            raise Refus(f"YouTube ({pub.langue}) : jeton refusé par Google — relier la chaîne à nouveau depuis la fenêtre, puis Publier")
        test = premiere(pub)
        if not test:
            _avant_l_heure(pub)
        with transaction.atomic(using=routeur.ouvrir(s)):
            if not m.Publication.objects.filter(pk=pk, statut__in=("brouillon", "erreur")).update(statut="en_file", envoi={}, non_repertorie=test,
                                                                                                   simulation=etat.simulation()):
                raise Refus("déjà dans la file d'envoi")
    noter(acteur, "publier", session=s.id, video=pub.video_id, langue=pub.langue, publication=pk, non_repertorie=test)
    lancer(acteur)
    quand = ("en non répertorié, tout de suite (première publication sur cette chaîne : la regarder, puis la rendre publique dans YouTube Studio)"
             if test else f"en privé, publique le {timezone.localtime(pub.planifiee_le):%d/%m/%Y à %H:%M}")
    return f"« {pub.titre} » ({pub.langue}) : envoi lancé {quand}"


def reprendre(s: Session, pk: int, acteur: str) -> str:
    """Après une erreur : la même publication repart (les étapes faites ne sont pas refaites, l'envoi reprend sa session)."""
    if acteur != "RT":
        raise Refus("seul RT reprend un envoi")
    with routeur.session(s):
        pub = _pub(pk)
        if pub.statut != "erreur":
            raise Refus(f"publication {pub.statut.replace('_', ' ')} : rien à reprendre")
        if not pub.identifiant_youtube and not pub.envoi.get("session"):  # une session ouverte : la tâche demande d'abord à YouTube où elle en est
            _avant_l_heure(pub)
        if not m.Publication.objects.filter(pk=pk, statut="erreur").update(statut="en_file"):
            raise Refus("déjà dans la file d'envoi")
    noter(acteur, "publication_reprise", session=s.id, publication=pk)
    lancer(acteur)
    return f"« {pub.titre} » ({pub.langue}) : envoi repris"


def annuler(s: Session, pk: int, acteur: str) -> str:
    """Avant le départ de la vidéo seulement (en file ou en erreur, rien chez YouTube) : la publication redevient un brouillon. Une session
    ouverte est d'abord demandée à YouTube (arrivée : rien n'est annulé)."""
    with routeur.session(s):
        pub = _pub(pk)
        if pub.identifiant_youtube:
            raise Refus("vidéo déjà chez YouTube : Reprendre l'envoi pour finir les étapes, ou la retirer dans YouTube Studio")
        if not m.Publication.objects.filter(pk=pk, statut__in=("en_file", "erreur")).update(statut="erreur"):  # la tâche ne la prend plus
            raise Refus("envoi en cours : Annuler après l'erreur, ou laisser finir" if pub.statut == "envoi" else f"publication {pub.statut.replace('_', ' ')} : rien à annuler")
        pub.refresh_from_db()
        if session_resolue(s, pub):  # arrivée : l'annuler ici ne la retirerait pas ; YouTube muet (Refus) : reste en erreur, Reprendre possible
            raise Refus("vidéo déjà chez YouTube : Reprendre l'envoi pour finir les étapes, ou la retirer dans YouTube Studio")
        pub.statut, pub.envoi = "brouillon", {}
        pub.save(update_fields=["statut", "envoi"])
    noter(acteur, "publication_annulee", session=s.id, publication=pk)
    return f"« {pub.titre} » ({pub.langue}) : envoi annulé, la publication redevient un brouillon"


# ---- la tâche détachée « publication » ----

def lancer(acteur: str):
    """La tâche détachée, si elle ne tourne pas déjà (elle prend aussi les envois mis en file pendant qu'elle tourne) ; « lancée » d'abord dans
    son état : la boucle du noyau ne la relance pas pendant son démarrage."""
    with _verrou:
        if taches.occupe("publication"):
            return
        taches.ecrire("publication", {"etat": "en_cours", "pid": 0, "lancee": datetime.now().isoformat(timespec="seconds")})
        programme.lancer_detache("executer", "publication", journal=dossiers.donnees() / "journaux" / "sortie_publication.log")
    noter(acteur, "publication", quoi="lancée")


def suivante(faites: set) -> tuple[Session, int] | None:
    """Le prochain envoi lancé par RT (en file, ou en cours quand son processus est mort), hors de `faites` ; une session illisible ne bloque pas."""
    for s in Session.objects.filter(essais=False).order_by("cree"):
        try:
            with routeur.session(s):
                pk = (m.Publication.objects.filter(statut__in=EN_COURS).exclude(pk__in=[p for i, p in faites if i == s.id])
                      .order_by("pk").values_list("pk", flat=True).first())
        except DatabaseError:
            continue
        if pk:
            return s, pk
    return None


def relancer():
    """Boucle du noyau : un envoi lancé par RT que rien n'envoie (processus tué, PC éteint, ou mis en file à la fin d'un passage) repart."""
    if not taches.occupe("publication") and suivante(set()):
        lancer("noyau")


def executer() -> int:
    """« executer publication » : les envois lancés par RT, l'un après l'autre (et ceux arrivés pendant) ; état et alertes dans
    donnees\\taches\\publication.json (la boucle du noyau les notifie)."""
    e = taches.lire("publication")
    if int(e.get("pid", 0)) not in (0, os.getpid()) and taches.vivante(e):
        print("la publication est déjà en cours")
        return 3
    taches.priorite_basse()
    taches.ecrire("publication", {"etat": "en_cours", "pid": os.getpid(), "debut": datetime.now().isoformat(timespec="seconds")})
    faites, alertes = set(), []
    while suite := suivante(faites):
        faites.add((suite[0].id, suite[1]))
        if texte := envoyer(*suite):
            alertes.append(texte)
    taches.ecrire("publication", {"etat": "erreur" if alertes else "faite", "fin": datetime.now().isoformat(timespec="seconds"),
                                  "message": " ; ".join(alertes)[:300], "alertes": alertes, "envois": len(faites)})
    print(f"publication : {len(faites)} envoi(s), {len(alertes)} en erreur")
    return 1 if alertes else 0


# ---- l'envoi ----

def _sauver(pub: m.Publication):
    pub.save(update_fields=["envoi", "identifiant_youtube", "statut"])


def _fin_plage(entetes) -> int:
    """« Range: bytes=0-524287 » → 524288 octets confirmés ; sans Range : 0."""
    plage = entetes.get("Range", "")
    return int(plage.rsplit("-", 1)[1]) + 1 if "-" in plage else 0


def metadonnees(pub: m.Publication) -> dict:
    """La ressource vidéo de videos.insert : privée + publishAt (non répertoriée sans publishAt la première fois), enfants, contenu synthétique, langue."""
    status = {"privacyStatus": "unlisted" if pub.non_repertorie else "private", "selfDeclaredMadeForKids": pub.enfants, "containsSyntheticMedia": pub.ia}
    if not pub.non_repertorie:
        status["publishAt"] = pub.planifiee_le.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"snippet": {"title": pub.titre, "description": pub.description, "tags": pub.tags, "defaultLanguage": pub.langue, "defaultAudioLanguage": pub.langue},
            "status": status}


def session_resolue(s: Session, pub: m.Publication) -> bool:
    """Une session d'envoi ouverte ne se jette jamais sans demander à YouTube où elle en est (bytes */N) : tout reçu (la réponse s'était perdue) →
    la vidéo est notée envoyée, True ; incomplète ou expirée → abandonnée, False. Sans session : False. YouTube injoignable : Refus, rien n'est jeté."""
    e = pub.envoi
    if not e.get("session"):
        return False
    if pub.simulation != etat.simulation():
        raise Refus(MODE)
    try:
        statut, _, corps = youtube.appeler(s, pub.langue, "PUT", url=e["session"], donnees=b"", entetes={"Content-Range": f"bytes */{e.get('taille', 0)}"})
    except youtube.ErreurYoutube as err:
        if err.statut not in (404, 410):
            raise Refus(f"YouTube ne dit pas où en est l'envoi ({err}) : réessayer") from err
        statut = err.statut
    except (OSError, http.client.HTTPException) as err:
        raise Refus(f"YouTube injoignable ({err.__class__.__name__}) : réessayer") from err
    if statut in (200, 201):
        _envoyee(pub, json.loads(corps))
        return True
    e.pop("session")
    e["octets"] = 0
    _sauver(pub)
    return False


def _envoyee(pub: m.Publication, video: dict):
    pub.identifiant_youtube, pub.envoi["octets"] = video["id"], pub.envoi["taille"]
    pub.envoi["fait"] = [*pub.envoi.get("fait", []), "video"]
    pub.envoi.pop("session", None)  # l'URL de session ne reste en base que pendant l'envoi
    _sauver(pub)
    log.info("publication %s : vidéo envoyée (%s)", pub.pk, video["id"])


def _video(s: Session, pub: m.Publication):
    """Envoi « resumable » : session (métadonnées) ouverte une fois ; à chaque reprise (coupure, processus tué, PC éteint) l'état est demandé à
    YouTube, puis morceaux de MORCEAU octets, octets confirmés gardés en base après chaque morceau."""
    f = final(s, pub) / pub.fichier
    taille, e = f.stat().st_size, pub.envoi
    if e.get("taille") not in (None, taille) and session_resolue(s, pub):  # la vidéo a changé depuis l'ouverture de la session
        return
    if e.get("session"):
        statut, h, corps = youtube.appeler(s, pub.langue, "PUT", url=e["session"], donnees=b"", entetes={"Content-Range": f"bytes */{taille}"})
        if statut != 308:  # tout était arrivé (réponse perdue) : pas de second envoi
            return _envoyee(pub, json.loads(corps))
        if not pub.non_repertorie and pub.planifiee_le <= timezone.now():  # l'heure est passée pendant l'envoi : YouTube la publierait à la fin
            e.pop("session")
            _sauver(pub)
            raise Refus(f"créneau dépassé pendant l'envoi ({timezone.localtime(pub.planifiee_le):%d/%m %H:%M}) : en choisir un autre, puis Reprendre l'envoi")
        e["octets"] = _fin_plage(h)
        _sauver(pub)
    if not e.get("session"):
        if not taille:
            raise Refus(f"{f.name} : fichier vide")
        _avant_l_heure(pub)
        _, h, _ = youtube.appeler(s, pub.langue, "POST", "/upload/youtube/v3/videos", {"uploadType": "resumable", "part": "snippet,status"}, corps=metadonnees(pub),
                                  entetes={"X-Upload-Content-Length": str(taille), "X-Upload-Content-Type": "video/mp4"})
        e.update(session=h["Location"], taille=taille, octets=0)
        _sauver(pub)
    while e["octets"] < taille:
        if not pub.non_repertorie and pub.planifiee_le <= timezone.now() + timedelta(minutes=2):  # publique dès la fin : avant miniature et sous-titres
            e.pop("session")
            _sauver(pub)
            raise Refus(f"créneau trop proche pendant l'envoi ({timezone.localtime(pub.planifiee_le):%d/%m %H:%M}) : en choisir un plus tard, puis Reprendre l'envoi")
        with f.open("rb") as fh:
            fh.seek(e["octets"])
            morceau = fh.read(MORCEAU)
        plage = f"bytes {e['octets']}-{e['octets'] + len(morceau) - 1}/{taille}"
        # BytesIO + longueur donnée : le délai de 300 s porte sur chaque bloc envoyé, pas sur tout le morceau (ligne lente)
        statut, h, corps = youtube.appeler(s, pub.langue, "PUT", url=e["session"], donnees=io.BytesIO(morceau), type_="video/mp4",
                                           entetes={"Content-Range": plage, "Content-Length": str(len(morceau))}, delai=300)
        if statut != 308:
            return _envoyee(pub, json.loads(corps))
        avant, e["octets"] = e["octets"], _fin_plage(h)
        if e["octets"] > avant:
            e.pop("essais", None)
        _sauver(pub)


def _miniature(s: Session, pub: m.Publication) -> str:
    f = final(s, pub) / pub.miniature
    youtube.appeler(s, pub.langue, "POST", "/upload/youtube/v3/thumbnails/set", {"videoId": pub.identifiant_youtube, "uploadType": "media"}, donnees=f.read_bytes(),
                    type_="image/png" if f.suffix.lower() == ".png" else "image/jpeg")
    return f"{pub.miniature} posée"


def _playlist(s: Session, pub: m.Publication) -> str:
    _, _, corps = youtube.appeler(s, pub.langue, "POST", "/youtube/v3/playlistItems", {"part": "snippet"},
                                  corps={"snippet": {"playlistId": pub.playlist, "resourceId": {"kind": "youtube#video", "videoId": pub.identifiant_youtube}}})
    pub.envoi["playlist_element"] = json.loads(corps)["id"]
    return f"ajoutée à {pub.playlist}"


def _sous_titres(s: Session, pub: m.Publication) -> str:
    texte = sous_titres(s, pub)
    if not texte:
        return "pas de transcription : aucun sous-titre"
    limite = "fabrique_" + secrets.token_hex(12)
    nom = (m.Langue.objects.filter(code=pub.langue).first() or m.Langue()).nom or pub.langue
    meta = {"snippet": {"videoId": pub.identifiant_youtube, "language": pub.langue, "name": nom, "isDraft": False}}
    corps = (f"--{limite}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(meta)}\r\n--{limite}\r\nContent-Type: application/octet-stream\r\n\r\n".encode("utf-8")
             + texte.encode("utf-8") + f"\r\n--{limite}--\r\n".encode())
    try:
        _, _, r = youtube.appeler(s, pub.langue, "POST", "/upload/youtube/v3/captions", {"part": "snippet", "uploadType": "multipart"}, donnees=corps,
                                  type_=f"multipart/related; boundary={limite}")
    except youtube.ErreurYoutube as e:
        if e.statut == 409:  # déjà posés (réponse perdue lors d'un essai précédent)
            return "sous-titres déjà présents sur YouTube"
        raise
    pub.envoi["sous_titres"] = json.loads(r)["id"]
    return f"{texte.count(' --> ')} sous-titre(s) ({pub.langue})"


def etapes(pub: m.Publication) -> list[str]:
    """Dans l'ordre : vidéo, playlist (pas en non répertorié : une vidéo d'essai n'entre pas dans une playlist publique), sous-titres, miniature."""
    return ["video"] + (["playlist"] if pub.playlist and not pub.non_repertorie else []) + ["sous_titres"] + (["miniature"] if pub.miniature else [])


def _echec(pub: m.Publication, err) -> str:
    pub.statut, pub.envoi["erreur"] = "erreur", str(err)[:300]
    pub.envoi.pop("essais", None)
    _sauver(pub)
    texte = f"« {pub.titre} » ({pub.langue}) : publication en erreur — {err}"
    log.warning(texte, exc_info=not isinstance(err, (Refus, youtube.ErreurYoutube)))
    noter("noyau", "publication_erreur", publication=pub.pk, langue=pub.langue, message=str(err)[:300])
    return texte


def envoyer(s: Session, pk: int) -> str:
    """Un envoi : vidéo, playlist, sous-titres, miniature — chaque étape notée dans envoi.fait, une reprise ne refait rien — puis « planifiee »
    (ou « non_repertoriee »). Coupure ou 5xx : nouvel essai (ESSAIS de suite au plus) ; refus, 4xx ou imprévu : en erreur, l'alerte en clair
    rendue (vide : envoyée)."""
    with routeur.session(s):
        if not m.Publication.objects.filter(pk=pk, statut__in=EN_COURS).update(statut="envoi"):
            return ""  # annulée entre-temps
        pub = _pub(pk)
        if pub.simulation != etat.simulation():  # jamais un clic de la simulation envoyé à une vraie chaîne (ni l'inverse)
            return _echec(pub, Refus(MODE))
        while True:
            if pub.simulation != etat.simulation():  # revu à chaque essai : RT a pu changer de mode pendant une attente
                return _echec(pub, Refus(MODE))
            try:
                if "video" not in pub.envoi.get("fait", []):
                    _video(s, pub)
                for etape, fn in (("playlist", _playlist), ("sous_titres", _sous_titres), ("miniature", _miniature)):  # miniature en dernier : seule étape
                    if etape in etapes(pub) and etape not in pub.envoi.get("fait", []):                               # propre à la chaîne (validation)
                        detail = fn(s, pub)
                        pub.envoi["fait"] = [*pub.envoi.get("fait", []), etape]
                        pub.envoi.pop("essais", None)
                        _sauver(pub)
                        log.info("publication %s, %s : %s", pk, etape, detail)
                break
            except (youtube.ErreurYoutube, OSError, http.client.HTTPException) as err:
                if isinstance(err, youtube.ErreurYoutube) and err.statut in (404, 410) and pub.envoi.pop("session", None):  # session expirée : une nouvelle
                    _sauver(pub)
                    continue
                if isinstance(err, youtube.ErreurYoutube) and err.statut < 500 or pub.envoi.get("essais", 0) >= ESSAIS:
                    return _echec(pub, err)
                pub.envoi["essais"] = pub.envoi.get("essais", 0) + 1  # coupure : l'état sera redemandé à YouTube
                _sauver(pub)
                log.warning("publication %s : %s (%s), essai %s/%s", pk, type(err).__name__, err, pub.envoi["essais"], ESSAIS)
                time.sleep(PAUSE_S * 2 ** (pub.envoi["essais"] - 1))
            except Exception as err:  # noqa: BLE001 — Refus (jeton, créneau…), réponse illisible, imprévu : dit à RT, jamais relancé en boucle
                return _echec(pub, err)
        pub.statut = "non_repertoriee" if pub.non_repertorie else "planifiee"
        for k in ("erreur", "essais"):
            pub.envoi.pop(k, None)
        _sauver(pub)
    noter("noyau", "publication_envoyee", session=s.id, publication=pk, video=pub.identifiant_youtube, etapes=pub.envoi.get("fait", []))
    return ""
