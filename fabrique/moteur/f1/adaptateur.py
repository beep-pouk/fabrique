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
from fabrique.moteur.f1 import etape, langue, mouvement
from fabrique.moteur.f1.outils import Lieux, Outils
from fabrique.moteur.outils import Demande, Estimation, Fiche, Resultat

SESSION = "session:"


def estimer(fiche: Fiche, demande: Demande) -> Estimation:
    """Sans chrono : une durée fixe, ou par scène (relevées sur un épisode de Bramble Studio)."""
    r = fiche.reglages
    return Estimation(secondes=r.get("secondes", 0) + r.get("secondes_par_scene", 0) * demande.reglages.get("scenes", 0), carte_go=fiche.besoins.carte_go)


def langue_de(session: Path, code: str) -> dict:
    """La langue de la session telle que langue.faire la lit : code, outil de voix, ses réglages, police."""
    from fabrique.noyau import routeur
    from fabrique.noyau.models import Session
    from fabrique.session.models import Langue

    with routeur.session(Session.objects.get(dossier=session.name)):
        l = Langue.objects.filter(code=code).first()
    if l is None:
        raise RuntimeError(f"la langue « {code} » n'est pas une langue de la session")
    return {"code": l.code, "outil": l.outil_voix, "reglages": l.reglages_voix, "police": l.police}


MEDIAS = {".wav", ".mp4", ".png", ".jpg"}  # écrits une fois puis remplacés : liés ; le reste (json, txt) est réécrit sur place par le moteur : copié


def lier(source: Path, cible: Path):
    cible.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() in MEDIAS:
        try:
            os.link(source, cible)
            return
        except OSError:  # autre disque, ou lien refusé : une copie
            pass
    shutil.copy2(source, cible)  # une copie : l'avant gardé par un « refaire » ne suit jamais l'après


def fabriquer(fiche: Fiche, demande: Demande, dossier: Path) -> Resultat:
    atelier, session = Path(demande.atelier), Path(demande.session)
    garde.verifier(atelier)
    atelier.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((session / "reglages" / "config.json").read_text(encoding="utf-8"))
    lignes: list[str] = []
    lieux = Lieux(garde.studio_bramble() or dossiers.racine().parent, session)
    if fiche.reglages["etape"] == "langue":  # une version de langue entière, à partir de l'atelier de la langue du script
        script = Path(demande.script).with_name(f"{Path(demande.script).stem}.{demande.langue}.json")
        if not script.is_file():
            raise RuntimeError(f"traduction en « {demande.langue} » absente de la vidéo ({script.name})")
        cfg = lieux.config(cfg)
        code = langue.faire(lieux, script, cfg, langue_de(session, demande.langue), cfg["voix"]["ref_audio"], ecran=lignes.append, dossier=atelier,
                            anglais_run=atelier.parents[2] / "commun" / "atelier" / atelier.name)
    else:
        code = etape.jouer(lieux, demande.script, fiche.reglages["etape"], cfg, dossier=atelier, ecran=lignes.append, fond=lambda *a: False)
    if code or any("tourne deja" in ligne for ligne in lignes):
        raise RuntimeError(f"étape {fiche.reglages['etape']} : " + (lignes[-1] if lignes else f"code {code}"))
    fichiers = []
    defauts = None  # pas mesuré
    if fiche.reglages.get("rapport"):  # le contrôle : F1 v2 mesure le mouvement de chaque plan ; F1 v1 n'analyse rien encore — dit tel quel
        if (max_s := demande.reglages.get("plan_fixe_max_s")) and (videos := sorted((atelier / "final").glob("*.mp4"))):
            outils_ = Outils(lieux)
            defauts = mouvement.defauts(outils_.ffmpeg, videos[0], outils_.duree(videos[0]), max_s)
        (dossier / "rapport.json").write_text(json.dumps({"defauts": defauts, "analyse": "mouvement" if defauts is not None else "absente"}, ensure_ascii=False),
                                             encoding="utf-8")
        fichiers.append("rapport.json")
    for motif in fiche.reglages["sorties"]:
        base = session if motif.startswith(SESSION) else atelier
        for f in sorted(base.glob(motif.removeprefix(SESSION))):
            if f.is_file() and (rel := f.relative_to(base).as_posix()) not in fichiers:
                lier(f, dossier / rel)
                fichiers.append(rel)
    infos = {"journal": lignes[-20:], **({"mots": None} if demande.brique == "voix" else {}), **({"defauts": defauts} if demande.brique == "controle" else {}),
             **({"rien_a_faire": True} if not fichiers and fiche.reglages.get("peut_etre_vide") else {})}  # None : pas mesuré (jamais « rien trouvé »)
    return Resultat(fichiers=fichiers, infos=infos)
