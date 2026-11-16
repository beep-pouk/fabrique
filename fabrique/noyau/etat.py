"""État du noyau (repris de Bramble Studio, core/etat.py et core/mode.py) : etat.json et etat.txt dans donnees, écrits chaque minute et à chaque
changement ; Claude les lit sans joindre l'API. Mode simulation : le dépôt du code y reste toujours ; installée, jusqu'au clic de RT (réglage
« simulation », lu à chaque usage)."""
import json
import os
import shutil
from datetime import datetime

from django.conf import settings

from fabrique import dossiers, programme
from fabrique.noyau import taches
from fabrique.noyau.models import Parametre, Session

SEUIL_DISQUE_GO = 50


def simulation() -> bool:
    return not programme.installee() or Parametre.lire("simulation", "oui") != "non"


def alertes(e: dict, libre: int) -> list[str]:
    a = []
    if libre < SEUIL_DISQUE_GO * 1e9:
        a.append(f"disque : {libre / 1e9:.0f} Go libres (moins de {SEUIL_DISQUE_GO} Go)")
    if e["sauvegarde"].get("etat") == "erreur":
        a.append(f"la dernière sauvegarde a raté : {e['sauvegarde'].get('message', '')}")
    return a


def etat(maintenant: datetime | None = None) -> dict:
    e = {"heure": (maintenant or datetime.now()).isoformat(timespec="minutes"), "version": settings.VERSION,
         "mode": "simulation" if simulation() else "réel", "noyau": {"pid": os.getpid(), "port": dossiers.port()},
         "sessions": list(Session.objects.order_by("cree").values_list("nom", flat=True)),
         "file": {"attente": [], "encours": taches.occupe() or None}, "sauvegarde": taches.lire("sauvegarde")}
    e["alertes"] = alertes(e, shutil.disk_usage(settings.RACINE).free)
    s = e["sauvegarde"]
    e["texte"] = [f"[{datetime.fromisoformat(e['heure']):%d/%m %H:%M}] Fabrique {e['version']} ({e['mode']})",
                  f"Sessions : {', '.join(e['sessions']) or 'aucune'} | en cours : {e['file']['encours'] or 'rien'}",
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
