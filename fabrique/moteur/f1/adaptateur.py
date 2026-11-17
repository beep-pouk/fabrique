"""La prise de F1 : chaque fiche « f1_* » joue une étape du moteur de Bramble Studio (etape.jouer) sur l'atelier de la vidéo, gardé d'une étape à
l'autre (chaque étape lit ce que les précédentes y ont mis, et reprend où elle s'était arrêtée), puis lie (lien dur, sinon copie) ce qu'elle a
fait dans le dossier du morceau. Réglages de la fiche : « etape » (celle de Bramble Studio), « sorties » (motifs relatifs à l'atelier, ou à la
session s'ils commencent par « session: », le principal d'abord), « secondes » (estimation sans chrono). Le fond d'écran animé de RT n'est
jamais touché."""
import json
import os
import shutil
from pathlib import Path

from fabrique import dossiers, garde
from fabrique.moteur.f1 import etape
from fabrique.moteur.f1.outils import Lieux
from fabrique.moteur.outils import Demande, Estimation, Fiche, Resultat

SESSION = "session:"


def estimer(fiche: Fiche, demande: Demande) -> Estimation:
    return Estimation(secondes=fiche.reglages.get("secondes", 60), carte_go=fiche.besoins.carte_go)


def lier(source: Path, cible: Path):
    cible.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, cible)
    except OSError:  # autre disque, ou lien refusé : une copie
        shutil.copy2(source, cible)


def fabriquer(fiche: Fiche, demande: Demande, dossier: Path) -> Resultat:
    atelier, session = Path(demande.atelier), Path(demande.session)
    garde.verifier(atelier)
    atelier.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((session / "reglages" / "config.json").read_text(encoding="utf-8"))
    lignes: list[str] = []
    code = etape.jouer(Lieux(garde.studio_bramble() or dossiers.racine().parent, session), demande.script, fiche.reglages["etape"], cfg,
                       dossier=atelier, ecran=lignes.append, fond=lambda *a: False)
    if code or any("tourne deja" in ligne for ligne in lignes):
        raise RuntimeError(f"étape {fiche.reglages['etape']} : " + (lignes[-1] if lignes else f"code {code}"))
    fichiers = []
    if fiche.reglages.get("rapport"):  # le contrôle de F1 v1 : aucun défaut relevé (l'analyse arrive avec l'écran Vérification)
        (dossier / "rapport.json").write_text(json.dumps({"defauts": []}), encoding="utf-8")
        fichiers.append("rapport.json")
    for motif in fiche.reglages["sorties"]:
        base = session if motif.startswith(SESSION) else atelier
        for f in sorted(base.glob(motif.removeprefix(SESSION))):
            if f.is_file() and (rel := f.relative_to(base).as_posix()) not in fichiers:
                lier(f, dossier / rel)
                fichiers.append(rel)
    infos = {"journal": lignes[-20:], **({"mots": []} if demande.brique == "voix" else {}), **({"defauts": []} if demande.brique == "controle" else {})}
    return Resultat(fichiers=fichiers, infos=infos)
