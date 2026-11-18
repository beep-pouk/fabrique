"""Installer, mettre à jour, retirer un outil depuis l'écran Outils (plan § 5.2 ; repris de Bramble Studio, core/reparation.py). La recette
d'installation est dans la fiche (« installation » : pas, témoins, place, « manuel ») ; elle est jouée cachée par la tâche détachée
« installation » (jamais pendant une fabrication ni un banc), pas à pas, journal dans journaux\\installation.log, vers
<racine>\\outils\\<outil>\\<version> : une nouvelle version s'installe à côté de l'ancienne, qui reste. Pas possibles :
  {"dossier": "x"}                                crée le dossier (dans celui de l'outil)
  {"telecharger": url, "vers": "x", "sha256": …}  curl.exe avec reprise ; l'empreinte, si elle est donnée, est contrôlée ; un fichier déjà bon est sauté
  {"commande": [...], "cwd": "x", "env": {…}}     un programme, caché ; {ici} (dossier de l'outil), {programme} (le paquet fabrique), {python} remplacés
  chaque pas peut porter "si_absent": "x" (sauté si ce fichier existe dans le dossier de l'outil) et "titre".
Ce qui exige des droits administrateur n'a pas de pas : la fiche porte « manuel », l'explication montrée à RT. Un outil sans recette (faux
outil, service en ligne, outil partagé de Bramble Studio, lu seulement) n'est jamais installé ni rangé par Fabrique. Retirer : état « retiré »
et dossier rangé dans outils\\_corbeille (jamais effacé) ; refusé pour un outil qui sert de défaut ou le dernier en service de sa brique."""
import hashlib
import json
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings

from fabrique import dossiers, garde, programme
from fabrique.garde import Refus
from fabrique.moteur import outils, recettes
from fabrique.noyau import routeur, taches
from fabrique.noyau.models import Outil, Parametre, Session, noter

log = logging.getLogger(__name__)
SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def racine() -> Path:
    return garde.verifier(settings.RACINE / "outils")


def version_installee(f: outils.Fiche) -> str:
    o = Outil.objects.filter(id=f.id).first()
    return o.version if o else ""


def dossier(f: outils.Fiche, version: str = "") -> Path:
    """Le dossier de l'outil : celui de la version installée (l'adaptateur s'en sert), ou de `version`."""
    return racine() / f.id / (version or version_installee(f) or f.version)


def complet(f: outils.Fiche, version: str) -> bool:
    return bool(version) and all((dossier(f, version) / t).exists() for t in f.installation.temoins)


def constat(f: outils.Fiche) -> dict:
    """Ce que l'écran Outils montre : {etat, texte, action} ; action : « installer », « mettre_a_jour » ou vide."""
    if f.installation is None:
        return {"etat": "pret", "texte": "rien à installer", "action": ""}
    v = version_installee(f)
    if v and v != f.version and complet(f, v):
        return {"etat": "ancienne", "texte": f"version {v} installée ; {f.version} disponible", "action": "mettre_a_jour"}
    if complet(f, f.version):
        return {"etat": "installe", "texte": f"version {f.version} installée", "action": ""}
    if f.installation.manuel and not f.installation.pas:
        return {"etat": "manuel", "texte": f.installation.manuel, "action": ""}
    return {"etat": "absent", "texte": "pas installé" if not v else f"version {v} incomplète", "action": "installer"}


def refus(f: outils.Fiche) -> str:
    """Pourquoi l'installation ne peut pas partir maintenant ; vide si rien ne s'y oppose."""
    if f.installation is None or not f.installation.pas:
        return f.installation.manuel if f.installation else "cet outil n'a rien à installer"
    if not constat(f)["action"]:
        return f"{f.nom} est déjà installé (version {f.version})"
    if o := taches.occupe("fabrication", "installation"):
        return f"une {o} est en cours : un outil s'installe quand plus rien ne tourne"
    racine().mkdir(parents=True, exist_ok=True)
    if f.installation.place_go and shutil.disk_usage(racine()).free < f.installation.place_go * 1e9:
        return f"il faut {f.installation.place_go:g} Go libres, il y en a {shutil.disk_usage(racine()).free / 1e9:.0f}"
    return ""


def lancer(outil: str, acteur: str) -> str:
    f = outils.fiches().get(outil)
    if f is None:
        raise Refus(f"outil inconnu : {outil}")
    if raison := refus(f):
        raise Refus(raison)
    taches.ecrire("installation", {"etat": "en_cours", "pid": 0, "outil": f.id, "lancee": datetime.now().isoformat(timespec="seconds")})
    programme.lancer_detache("executer", "installation", f.id, journal=dossiers.donnees() / "journaux" / "sortie_installation.log")
    noter(acteur, "outil", outil=f.id, quoi="installation lancée", version=f.version)
    return f"Installation de {f.nom} {f.version} lancée : une notification dira quand elle est finie."


def sha256(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for bloc in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def curl() -> str:
    """curl.exe de Windows (il se sert du magasin de certificats de Windows)."""
    systeme = Path(os.environ.get("SystemRoot", "")) / "System32" / "curl.exe"
    return str(systeme) if systeme.is_file() else (shutil.which("curl") or "curl")


def _lancer(cmd: list[str], sortie, cwd=None, env: dict | None = None) -> int:
    sortie.write(f"> {' '.join(str(c) for c in cmd)}\n")
    sortie.flush()
    try:
        r = subprocess.run([str(c) for c in cmd], cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                           encoding="utf-8", errors="replace", env={**os.environ, **env} if env else None, creationflags=SANS_FENETRE)
    except OSError as e:
        sortie.write(f"ERREUR : {e}\n")
        return 1
    sortie.write(r.stdout[-20000:])
    return r.returncode


def telecharger(url: str, vers: Path, empreinte: str, sortie) -> str:
    """Le fichier `vers`, téléchargé par curl avec reprise dans `vers`.part puis renommé ; vide si tout va bien, sinon la phrase de l'échec."""
    if vers.is_file() and (not empreinte or sha256(vers) == empreinte):
        return ""
    vers.parent.mkdir(parents=True, exist_ok=True)
    part = vers.with_name(vers.name + ".part")
    if _lancer([curl(), "-L", "--fail", "--silent", "--show-error", "--retry", "5", "--retry-delay", "5", "-C", "-", "-o", part, url], sortie):
        return f"téléchargement interrompu ({vers.name}) : relancer reprend où il s'était arrêté"
    if empreinte and sha256(part) != empreinte:
        part.unlink()
        return f"{vers.name} : le fichier reçu n'est pas le bon (empreinte différente) ; il a été effacé"
    os.replace(part, vers)
    return ""


def jouer_pas(pas: dict, ici: Path, sortie) -> str:
    """Un pas de la recette ; vide si fait (ou sauté), sinon la phrase de l'échec."""
    if pas.get("si_absent") and (ici / pas["si_absent"]).exists():
        sortie.write(f"déjà là : {pas['si_absent']}\n")
        return ""
    remplacer = lambda x: str(x).format(ici=ici, programme=dossiers.CODE.as_posix(), python=programme.python())  # noqa: E731
    if "dossier" in pas:
        (ici / pas["dossier"]).mkdir(parents=True, exist_ok=True)
        return ""
    if "telecharger" in pas:
        return telecharger(remplacer(pas["telecharger"]), ici / pas["vers"], pas.get("sha256", ""), sortie)
    if "commande" in pas:
        code = _lancer([remplacer(a) for a in pas["commande"]], sortie, cwd=str(ici / pas.get("cwd", "")),
                       env={k: remplacer(v) for k, v in pas.get("env", {}).items()})
        return "" if code == 0 else f"la commande a échoué (code {code}) : voir le journal"
    return f"pas inconnu dans la recette : {sorted(pas)}"


def installer(outil: str) -> str:
    """La recette jouée dans outils\\<outil>\\<version de la fiche> ; vide si l'outil est complet à la fin, sinon la cause. La version installée
    n'est notée qu'une fois les témoins présents : une installation coupée garde l'ancienne version en service et reprend où elle était."""
    f = outils.fiches()[outil]
    ici = dossier(f, f.version)
    ici.mkdir(parents=True, exist_ok=True)
    settings.JOURNAUX.mkdir(parents=True, exist_ok=True)
    with open(settings.JOURNAUX / "installation.log", "a", encoding="utf-8") as sortie:
        sortie.write(f"\n== {datetime.now():%d/%m/%Y %H:%M:%S} {f.nom} {f.version}\n")
        for i, pas in enumerate(f.installation.pas, 1):
            sortie.write(f"-- {pas.get('titre') or f'pas {i}'}\n")
            if echec := jouer_pas(pas, ici, sortie):
                sortie.write(f"ÉCHEC : {echec}\n")
                return echec
        if manquent := [t for t in f.installation.temoins if not (ici / t).exists()]:
            return f"la recette est finie mais il manque : {', '.join(manquent)}"
    Outil.objects.update_or_create(id=f.id, defaults={"version": f.version})
    return ""


def executer(outil: str = "") -> int:
    """« executer installation <outil> » : tâche détachée, l'état dans donnees\\taches\\installation.json (lu par le noyau, qui prévient RT)."""
    if outil not in outils.fiches() or outils.fiches()[outil].installation is None:
        print(f"outil inconnu ou sans recette : {outil}")
        return 2
    if taches.occupe("fabrication"):
        print("une fabrication est en cours")
        return 3
    taches.ecrire("installation", {"etat": "en_cours", "pid": os.getpid(), "outil": outil, "debut": datetime.now().isoformat(timespec="seconds")})
    try:
        echec = installer(outil)
    except Exception as e:  # noqa: BLE001 — dite à RT (état, notification), le détail dans le journal
        log.exception("installation de %s", outil)
        echec = f"erreur imprévue : {e}"
    taches.ecrire("installation", {"etat": "erreur" if echec else "faite", "outil": outil, "fin": datetime.now().isoformat(timespec="seconds"),
                                   "message": echec[:300]})
    noter("noyau", "outil", outil=outil, quoi="installation " + ("ratée" if echec else "faite"), message=echec[:300])
    print(f"installation de {outil} : {echec or 'faite'}")
    return 1 if echec else 0


def defaut_de(f: outils.Fiche) -> str:
    """Où l'outil sert de défaut (brique, noyau, une session, un format livré) ; vide : nulle part."""
    for b in f.roles:
        if outils.BRIQUES[b]["defaut"] == f.id or outils.BRIQUES[b]["simulation"] == f.id:
            return f"défaut livré de la brique {outils.BRIQUES[b]['titre']}"
        if Parametre.lire(f"outil.{b}") == f.id:
            return f"défaut de la brique {outils.BRIQUES[b]['titre']}"
    for r in recettes.LIVREES.glob("*.json"):
        if f.id in json.loads(r.read_text(encoding="utf-8")).get("outils", {}).values():
            return f"défaut du format {r.stem}"
    from fabrique.session.models import Reglage

    for s in Session.objects.all():
        with routeur.session(s):
            if Reglage.objects.filter(cle__startswith="outil.", valeur=f.id).exists():
                return f"défaut de la session « {s.nom} »"
    return ""


def retirer(outil: str, acteur: str) -> str:
    f = outils.fiches().get(outil)
    if f is None:
        raise Refus(f"outil inconnu : {outil}")
    if outils.etat(f) == "retire":
        raise Refus(f"{f.nom} est déjà retiré")
    if ou := defaut_de(f):
        raise Refus(f"{f.nom} sert de {ou} : faire gagner un autre outil au banc d'abord")
    seul = [b for b in f.roles if not any(g.id != f.id and b in g.roles and outils.etat(g) == "en_service" for g in outils.fiches().values())]
    if outils.etat(f) == "en_service" and seul:
        raise Refus(f"{f.nom} est le dernier outil en service de la brique {outils.BRIQUES[seul[0]]['titre']}")
    if taches.occupe("fabrication", "installation"):
        raise Refus("une fabrication ou une installation est en cours : retirer un outil quand plus rien ne tourne")
    rangement = ""
    if f.installation is not None and (d := racine() / f.id).exists():
        (cible := racine() / "_corbeille" / f"{f.id}_{datetime.now():%Y%m%d_%H%M%S}").parent.mkdir(parents=True, exist_ok=True)
        try:
            d.rename(cible)
        except OSError as e:
            raise Refus(f"un fichier de {f.nom} est ouvert ailleurs ({e.__class__.__name__}) : rien n'a bougé, réessayer") from None
        rangement = f" ; ses fichiers sont rangés dans {cible}"
    Outil.objects.update_or_create(id=f.id, defaults={"etat": "retire", "version": ""})
    noter(acteur, "outil", outil=f.id, quoi="retiré")
    return f"{f.nom} retiré (plus jamais choisi){rangement}."


def remettre(outil: str, acteur: str) -> str:
    """Un outil retiré redevient candidat : il ne repasse en service qu'après un banc gagné."""
    f = outils.fiches().get(outil)
    if f is None or outils.etat(f) != "retire":
        raise Refus("seul un outil retiré se remet parmi les candidats")
    Outil.objects.update_or_create(id=f.id, defaults={"etat": "candidat"})
    noter(acteur, "outil", outil=f.id, quoi="remis parmi les candidats")
    return f"{f.nom} est de nouveau candidat : il repassera en service après un banc gagné."


def prix(f: outils.Fiche) -> str:
    if f.local or not f.prix_unite_eur:
        return "gratuit"
    return f"{f.prix_unite_eur:.3f}".rstrip("0").replace(".", ",") + f" € / {f.unite}" + (f" (prix du {f.prix_date})" if f.prix_date else "")


def registre(simulation: bool) -> list[dict]:
    """L'écran Outils : chaque brique, l'outil qui sert par défaut, ses juges de banc, et la fiche de chacun de ses outils (les faux outils en
    simulation seulement), avec son état, son installation et son dernier banc."""
    from fabrique.moteur import bancs
    from fabrique.session.models import Reglage

    des_sessions: dict[str, list[str]] = {}
    for s in Session.objects.filter(archivee__isnull=True):
        with routeur.session(s):
            for o in Reglage.objects.filter(cle__startswith="outil.").values_list("valeur", flat=True):
                des_sessions.setdefault(o, []).append(s.nom)
    etats = {"en_service": "en service", "candidat": "candidat", "retire": "retiré"}
    briques = []
    for b, d in outils.BRIQUES.items():
        defaut = Parametre.lire(f"outil.{b}") or d["defaut"]
        fiches = []
        for f in outils.fiches().values():
            if b not in f.roles or (f.faux and not simulation):
                continue
            c, e = constat(f), outils.etat(f)
            fiches.append({"id": f.id, "nom": f.nom, "local": f.local, "prix": prix(f), "licence": f.licence, "credit": f.credit,
                           "besoins": f"{f.besoins.carte_go:g} Go de carte, {f.besoins.disque_go:g} Go de disque", "langues": ", ".join(f.langues) or "toutes",
                           "limites": f.limites, "version": f.version, "etat": e, "etat_nom": etats[e], "installation": c["texte"], "action": c["action"],
                           "simule": f.faux, "defaut": f.id == defaut, "sessions": des_sessions.get(f.id, []), "dernier_banc": bancs.dernier(f.id)})
        briques.append({"id": b, "titre": d["titre"], "defaut": defaut, "juges": [{"id": j, "titre": bancs.JUGES[j]["titre"]} for j in bancs.juges(b)],
                        "outils": sorted(fiches, key=lambda x: (not x["defaut"], x["etat"] != "en_service", x["nom"]))})
    return briques
