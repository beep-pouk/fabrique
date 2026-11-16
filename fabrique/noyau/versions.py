"""Mises à jour (repris de Bramble Studio, core/versions.py et core/signature.py) : outils_dev\\construire.py --publier pose l'installateur et
versions.json dans <racine>\\versions. « Mettre à jour » (clic de RT, jamais pendant une tâche) : installateur copié dans les données, empreinte
et signature contrôlées (la même que celle du programme qui tourne), chaque base copiée dans _old, puis l'installateur silencieux par le relais :
il arrête Fabrique, installe et la relance ; les migrations se font au démarrage du noyau. On avance seulement : aucun retour de version."""
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from django.conf import settings

from fabrique import dossiers, programme
from fabrique.garde import Refus
from fabrique.noyau import bases, taches
from fabrique.noyau.models import noter

FORME = re.compile(r"\d+\.\d+\.\d+")
OPTIONS = ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELANCER=1")
SIGNATAIRE = ("$s = Get-AuthenticodeSignature -LiteralPath $env:FABRIQUE_FICHIER; "
              "if ($s.SignerCertificate -and $s.Status -in 'Valid','UnknownError') { $s.SignerCertificate.Thumbprint }")  # UnknownError : signé, certificat pas de confiance


def numero(v: str) -> tuple:
    return tuple(int(n) for n in v.split("."))


def catalogue(d: Path | None = None) -> list[dict]:
    """Les versions dont l'installateur est là, de la plus ancienne à la plus récente ; une ligne mal formée est ignorée."""
    d = d or dossiers.versions(settings.RACINE)
    try:
        lu = json.loads((d / "versions.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    bons = [v for v in lu if isinstance(v, dict) and FORME.fullmatch(str(v.get("version", ""))) and isinstance(v.get("fichier"), str)
            and Path(v["fichier"]).name == v["fichier"] and (d / v["fichier"]).is_file()] if isinstance(lu, list) else []
    return sorted(bons, key=lambda v: numero(v["version"]))


def proposee() -> dict | None:
    c = catalogue()
    return c[-1] if c and numero(c[-1]["version"]) > numero(settings.VERSION) else None


def raison(v: dict | None) -> str:
    """Ce qui empêche « Mettre à jour » (vide : rien)."""
    if not programme.installee():
        return "en développement, pas de mise à jour"
    if not v:
        return "Fabrique est à jour"
    return f"la {o} est en cours : réessayer quand elle sera finie" if (o := taches.occupe()) else ""


def etat() -> dict:
    v = proposee()
    return {"installee": settings.VERSION, "proposee": v and v["version"], "nouveautes": (v or {}).get("nouveautes", []), "raison": raison(v)}


def signataire(fichier: Path) -> str:
    """L'empreinte du certificat qui a signé le fichier ; vide : pas signé, ou modifié depuis."""
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"  # rien sur le chemin
    r = subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-Command", SIGNATAIRE], capture_output=True, text=True, timeout=60,
                       env={**os.environ, "FABRIQUE_FICHIER": str(fichier)}, creationflags=subprocess.CREATE_NO_WINDOW)
    return r.stdout.strip()


def mettre_a_jour(acteur: str) -> str:
    v = proposee()
    if r := raison(v):
        raise Refus(r)
    travail = settings.DONNEES / "mise_a_jour"
    travail.mkdir(parents=True, exist_ok=True)
    copie = travail / v["fichier"]  # celui qu'on lance est celui qu'on a contrôlé
    shutil.copyfile(dossiers.versions(settings.RACINE) / v["fichier"], copie)
    if hashlib.sha256(copie.read_bytes()).hexdigest() != str(v.get("sha256", "")).lower():
        raise Refus(f"le fichier de la version {v['version']} est abîmé (empreinte inattendue) : rien n'est installé")
    signe = signataire(copie)
    if not signe or signe != signataire(dossiers.programme() / programme.EXE):
        raise Refus(f"la version {v['version']} ne porte pas la signature de Fabrique : rien n'est installé")
    bases.copier_bases("mise_a_jour")
    noter(acteur, "mise_a_jour", version=v["version"], depuis=settings.VERSION)
    programme.lancer_detache("--installateur", copie, *OPTIONS, f"/LOG={settings.JOURNAUX / 'installation.log'}", journal=settings.JOURNAUX / "mise_a_jour.log")
    return f"Mise à jour vers la version {v['version']} : Fabrique se ferme, s'installe et se rouvre toute seule dans une minute."
