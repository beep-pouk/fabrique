"""État du noyau (repris de Bramble Studio, core/etat.py et core/mode.py) : etat.json et etat.txt dans donnees, écrits chaque minute et à chaque
changement ; Claude les lit sans joindre l'API. Mode simulation : le dépôt du code y reste, sauf essai réel sur le PC (FABRIQUE_REEL=1 et le
réglage) ; installée, jusqu'au clic de RT (réglage « simulation », lu à chaque usage)."""
import json
import os
import shutil
from datetime import datetime

from django.conf import settings

from fabrique import dossiers, programme
from fabrique.moteur import file
from fabrique.noyau import taches
from fabrique.noyau.models import Parametre, Session

SEUIL_DISQUE_GO = 50


def simulation() -> bool:
    reel_permis = programme.installee() or os.environ.get("FABRIQUE_REEL") == "1"  # développement : les essais réels de J3, jamais par défaut
    return not reel_permis or Parametre.lire("simulation", "oui") != "non"


def changer(reel: bool, acteur: str) -> str:
    """Système → « Passer en mode réel » / « Revenir en simulation » (clic de RT, repris de Bramble Studio, core/mode_reel.py) : refusé tant
    qu'une vidéo est dans la file ou qu'un envoi est en cours (une tâche commencée dans un mode ne finit jamais dans l'autre)."""
    from fabrique.garde import Refus
    from fabrique.noyau import routeur
    from fabrique.noyau.models import Tache, noter
    from fabrique.session.models import Publication

    if acteur != "RT":
        raise Refus("seul RT change de mode")
    if Tache.objects.filter(etat__in=("attente", "en_cours", "pause")).exists() or taches.occupe("fabrication", "publication"):
        raise Refus("une vidéo est dans la file (ou une tâche tourne) : changer de mode une fois la file vide")
    for s in Session.objects.filter(essais=False):
        with routeur.session(s):
            if Publication.objects.filter(statut__in=("en_file", "envoi")).exists():
                raise Refus(f"un envoi est en cours dans « {s.nom} » : changer de mode une fois l'envoi fini ou annulé")
    Parametre.ecrire("simulation", "non" if reel else "oui")
    noter(acteur, "mode", reel=reel)
    return "Mode réel : les vrais outils et les vraies chaînes (rien ne part sans votre clic)." if reel else "Retour en simulation : faux outils, faux YouTube."


def alertes(e: dict, libre: int) -> list[str]:
    a = []
    if libre < SEUIL_DISQUE_GO * 1e9:
        a.append(f"disque : {libre / 1e9:.0f} Go libres (moins de {SEUIL_DISQUE_GO} Go)")
    if e["sauvegarde"].get("etat") == "erreur":
        a.append(f"la dernière sauvegarde a raté : {e['sauvegarde'].get('message', '')}")
    for t in ("publication", "paquets", "releve"):
        if e[t].get("etat") == "erreur":
            a += e[t].get("alertes", [])
    a += [f"« {t['titre']} » : {x}" for t in e["file"]["taches"] if t["etat"] not in ("finie", "annulee") for x in t["alertes"]]
    return a


def etat(maintenant: datetime | None = None) -> dict:
    liste = file.lister()
    encours = next((t for t in liste if t["etat"] == "en_cours"), None)
    attente = [t for t in liste if t["etat"] == "attente"]
    e = {"heure": (maintenant or datetime.now()).isoformat(timespec="minutes"), "version": settings.VERSION,
         "mode": "simulation" if simulation() else "réel", "noyau": {"pid": os.getpid(), "port": dossiers.port()},
         "sessions": list(Session.objects.order_by("cree").values_list("nom", flat=True)),
         "file": {"attente": [t["titre"] for t in attente], "encours": encours and f"{encours['titre']} ({encours['progression']})",
                  "raison": attente[0]["raison"] if attente and not encours else "", "taches": liste},
         "sauvegarde": taches.lire("sauvegarde"), "publication": taches.lire("publication"), "paquets": taches.lire("paquets"),
         "releve": taches.lire("releve")}
    e["alertes"] = alertes(e, shutil.disk_usage(settings.RACINE).free)
    s, f = e["sauvegarde"], e["file"]
    e["texte"] = [f"[{datetime.fromisoformat(e['heure']):%d/%m %H:%M}] Fabrique {e['version']} ({e['mode']})",
                  f"Sessions : {', '.join(e['sessions']) or 'aucune'} | en cours : {f['encours'] or 'rien'} | file : {len(f['attente'])}"
                  + (f" (attend : {f['raison']})" if f["raison"] else ""),
                  f"Dernière sauvegarde : {s.get('etat', 'aucune')} {s.get('fin', '')} {s.get('fichier', s.get('message', ''))}".rstrip(),
                  f"Dernier relevé des statistiques : {e['releve'].get('etat', 'aucun')} {e['releve'].get('fin', '')}".rstrip(),
                  *(f"! {a}" for a in e["alertes"])]
    return e


def ecrire(e: dict | None = None) -> dict:
    e = e or etat()
    d = settings.DONNEES
    for nom, texte in (("etat.txt", "\n".join(e["texte"]) + "\n"), ("etat.json", json.dumps(e, ensure_ascii=False, indent=1))):
        tmp = d / f"{nom}.{os.getpid()}.tmp"  # écrit à part puis renommé : un lecteur ne voit jamais un fichier à moitié écrit
        tmp.write_text(texte, encoding="utf-8")
        try:
            tmp.replace(d / nom)
        except OSError:  # Windows : ouvert par un lecteur à cet instant → au tour suivant
            tmp.unlink(missing_ok=True)
    return e
