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


def alertes(e: dict, libre: int) -> list[str]:
    a = []
    if libre < SEUIL_DISQUE_GO * 1e9:
        a.append(f"disque : {libre / 1e9:.0f} Go libres (moins de {SEUIL_DISQUE_GO} Go)")
    if e["sauvegarde"].get("etat") == "erreur":
        a.append(f"la dernière sauvegarde a raté : {e['sauvegarde'].get('message', '')}")
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
         "sauvegarde": taches.lire("sauvegarde")}
    e["alertes"] = alertes(e, shutil.disk_usage(settings.RACINE).free)
    s, f = e["sauvegarde"], e["file"]
    e["texte"] = [f"[{datetime.fromisoformat(e['heure']):%d/%m %H:%M}] Fabrique {e['version']} ({e['mode']})",
                  f"Sessions : {', '.join(e['sessions']) or 'aucune'} | en cours : {f['encours'] or 'rien'} | file : {len(f['attente'])}"
                  + (f" (attend : {f['raison']})" if f["raison"] else ""),
                  f"Dernière sauvegarde : {s.get('etat', 'aucune')} {s.get('fin', '')} {s.get('fichier', s.get('message', ''))}".rstrip(),
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
