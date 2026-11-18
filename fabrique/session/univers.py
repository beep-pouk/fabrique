"""L'univers complet d'une session (cahier § G) : personnages et leurs images de référence (galerie, validation, import par glisser-déposer ou
par Claude), lieux, musiques et voix, style ; droits et crédits de chaque élément ; historique des changements (journal du noyau) ; partage
d'un élément avec une autre session, au clic de RT seulement (rien ne passe d'une session à l'autre sans qu'il le demande). Un fichier importé
est copié, jamais déplacé."""
import re
import shutil
import unicodedata
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from fabrique import garde
from fabrique.garde import Refus
from fabrique.noyau import routeur
from fabrique.noyau.models import Journal, Session, noter
from fabrique.session import models as m
from fabrique.session import reglages

IMAGES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_MO = 50
TYPES = {"personnage": m.Personnage, "lieu": m.Lieu, "reference": m.Reference, "musique": m.Ressource, "voix": m.Ressource}


def racine(s: Session) -> Path:
    return settings.SESSIONS / s.dossier


def droits(o) -> dict:
    if isinstance(o, m.Ressource):
        return {"licence": o.licence, "credit": o.credit}
    return {"licence": o.details.get("licence", ""), "credit": o.details.get("credit", "")}


def lire(s: Session) -> dict:
    r = racine(s)
    with routeur.session(s):
        return {
            "personnages": [{"id": p.id, "nom": p.nom, "role": p.role, "statut": p.statut, "description": p.details.get("description", ""), **droits(p),
                             "references": [{"id": x.id, "chemin": str(r / x.fichier), "vue": x.vue, "source": x.source, "validee": x.validee, **droits(x)}
                                            for x in p.references.order_by("-validee", "id")]}
                            for p in m.Personnage.objects.order_by("nom", "id")],
            "lieux": [{"id": l.id, "nom": l.nom, "description": l.description, **droits(l)} for l in m.Lieu.objects.order_by("nom")],
            "ressources": [{"id": x.id, "type": x.type, "nom": x.nom, "outil": x.outil, **droits(x)} for x in m.Ressource.objects.order_by("type", "nom")],
            "langues": [{"code": l.code, "nom": l.nom, "outil_voix": l.outil_voix, "voix_validee": l.voix_validee} for l in m.Langue.objects.order_by("ordre", "code")],
            "style": m.Reglage.objects.filter(cle="style").values_list("valeur", flat=True).first() or "",
        }


def historique(s: Session) -> list[dict]:
    return [{"date": f"{timezone.localtime(j.date):%d/%m/%Y %H:%M}", "acteur": j.acteur, "quoi": j.detail.get("quoi", "")}
            for j in Journal.objects.filter(action="univers", detail__session=s.id).order_by("-date", "-id")[:200]]


def ajouter(s: Session, type_: str, nom: str, description: str, acteur: str, role: str = "") -> str:
    nom = nom.strip()
    if not nom:
        raise Refus("un nom est attendu")
    with routeur.session(s):
        if type_ == "personnage":
            if m.Personnage.objects.filter(nom=nom).exists():
                raise Refus(f"« {nom} » existe déjà")
            m.Personnage.objects.create(nom=nom[:100], role=role.strip()[:50], details={"description": description.strip()})
        elif type_ == "lieu":
            if m.Lieu.objects.filter(nom=nom).exists():
                raise Refus(f"« {nom} » existe déjà")
            m.Lieu.objects.create(nom=nom[:100], description=description.strip())
        elif type_ in ("musique", "voix"):
            m.Ressource.objects.create(type=type_, nom=nom[:100], consigne=description.strip())
        else:
            raise Refus(f"type inconnu : {type_}")
    noter(acteur, "univers", session=s.id, quoi=f"{type_} « {nom} » ajouté")
    return f"« {nom} » ajouté à l'univers."


def objet(type_: str, pk: int):
    if type_ not in TYPES:
        raise Refus(f"type inconnu : {type_}")
    o = TYPES[type_].objects.filter(pk=pk).first()
    if o is None or (isinstance(o, m.Ressource) and o.type != type_):
        raise Refus(f"{type_} inconnu : {pk}")
    return o


def ecrire_droits(s: Session, type_: str, pk: int, licence: str, credit: str, acteur: str) -> str:
    with routeur.session(s):
        o = objet(type_, pk)
        if isinstance(o, m.Ressource):
            o.licence, o.credit = licence.strip()[:200], credit.strip()[:200]
        else:
            o.details = {**o.details, "licence": licence.strip()[:200], "credit": credit.strip()[:200]}
        o.save()
        nom = getattr(o, "nom", "") or Path(getattr(o, "fichier", "")).name
    noter(acteur, "univers", session=s.id, quoi=f"droits de {type_} « {nom} » : {licence.strip() or '—'}, crédit {credit.strip() or '—'}")
    return "Droits enregistrés."


def slug(nom: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()).strip("_") or "element"


def importer_reference(s: Session, personnage: int, fichier: str, acteur: str, vue: str = "") -> str:
    """Une image copiée sous univers\\personnages\\<personnage>\\importees\\ (jamais déplacée, jamais par-dessus une autre), à valider."""
    source = Path(fichier)
    if not source.is_absolute() or not source.is_file():
        raise Refus(f"fichier introuvable : {fichier}")
    if source.suffix.lower() not in IMAGES:
        raise Refus(f"une image est attendue ({', '.join(sorted(IMAGES))}), pas {source.suffix or 'un fichier sans extension'}")
    if source.stat().st_size > MAX_MO * 1e6:
        raise Refus(f"image trop lourde (plus de {MAX_MO} Mo)")
    with routeur.session(s):
        p = objet("personnage", personnage)
        dossier = garde.verifier(racine(s) / "univers" / "personnages" / slug(p.nom) / "importees")
        dossier.mkdir(parents=True, exist_ok=True)
        cible, n = dossier / f"{slug(source.stem)}{source.suffix.lower()}", 1
        while cible.exists():
            n += 1
            cible = dossier / f"{slug(source.stem)}_{n}{source.suffix.lower()}"
        shutil.copy2(source, cible)
        m.Reference.objects.create(personnage=p, fichier=cible.relative_to(racine(s)).as_posix(), vue=vue.strip()[:50], source=acteur, date=timezone.now())
    noter(acteur, "univers", session=s.id, quoi=f"référence {cible.name} importée pour « {p.nom} » (à valider)")
    return f"Image ajoutée aux références de « {p.nom} » : à valider."


def valider(s: Session, reference: int, validee: bool, acteur: str) -> str:
    with routeur.session(s):
        r = objet("reference", reference)
        r.validee = validee
        r.save(update_fields=["validee"])
        nom = r.personnage.nom
    noter(acteur, "univers", session=s.id, quoi=f"référence {Path(r.fichier).name} de « {nom} » {'validée' if validee else 'retirée des validées'}")
    return "Référence validée." if validee else "Référence retirée des validées."


def partager(s: Session, type_: str, pk: int, vers: Session, acteur: str) -> str:
    """Copie un personnage (et ses références, fichiers compris) ou un lieu dans une autre session ; refusé si elle a déjà ce nom."""
    if vers.id == s.id or vers.essais:
        raise Refus("partager avec une autre session réelle")
    if type_ not in ("personnage", "lieu"):
        raise Refus("se partagent : un personnage ou un lieu")
    with routeur.session(s):
        o = objet(type_, pk)
        refs = list(o.references.all()) if type_ == "personnage" else []
    with routeur.session(vers):
        if TYPES[type_].objects.filter(nom=o.nom).exists():
            raise Refus(f"« {vers.nom} » a déjà un {type_} « {o.nom} »")
    copies = []
    for r in refs:  # fichiers d'abord : la base de l'autre session ne pointe jamais vers un fichier absent
        src, dst = racine(s) / r.fichier, garde.verifier(racine(vers) / r.fichier)
        if src.is_file() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        copies.append(r)
    with routeur.session(vers):
        if type_ == "lieu":
            m.Lieu.objects.create(nom=o.nom, description=o.description, details=o.details)
        else:
            p = m.Personnage.objects.create(nom=o.nom, role=o.role, statut=o.statut, details=o.details)
            for r in copies:
                m.Reference.objects.create(personnage=p, fichier=r.fichier, vue=r.vue, source=r.source, validee=r.validee, verifiee=r.verifiee,
                                           date=r.date, details=r.details)
    noter(acteur, "univers", session=s.id, quoi=f"{type_} « {o.nom} » partagé avec « {vers.nom} »")
    noter(acteur, "univers", session=vers.id, quoi=f"{type_} « {o.nom} » reçu de « {s.nom} »")
    return f"« {o.nom} » copié dans « {vers.nom} »."


def ecrire_style(s: Session, style: str, acteur: str) -> str:
    reglages.ecrire(s, {"style": style}, acteur)
    noter(acteur, "univers", session=s.id, quoi="style changé")
    return "Style enregistré."
