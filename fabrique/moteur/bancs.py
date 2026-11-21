"""Banc à l'aveugle (cahier § 7.3 et D ; plan § 5.2) : l'outil en place pour une brique (a) contre un autre (b), sur les mêmes entrées : les
demandes (demande.json) de morceaux finis d'une vidéo, rejouées telles quelles. Le banc passe par la file (tâche lourde, verrou de la carte) ;
chaque sortie s'écrit à côté puis prend son nom (bancs\\<id>\\<entrée>\\<gauche|droite>), une coupure reprend à la première qui manque. RT voit chaque
entrée en deux colonnes, gauche et droite tirées au hasard, et vote (gauche, droite, égal) sans savoir quel outil est lequel ni ce qu'en dit
le juge. Un seul juge automatique par banc (faux en simulation ; Whisper pour la voix : texte dit contre texte voulu) ; une victoire du juge
de moins de ECART point sur 10 ne compte pas. Le verdict (votes de RT, juge à côté) est gardé en base et dans bancs\\<id>\\verdict.json.
Les votes se changent jusqu'à « Rendre le verdict » (RT). « Adopter » (RT seul) : le vainqueur, s'il n'est pas déjà l'outil en place, devient le
défaut de la brique ou de la session ; l'ancien reste disponible. Un outil payant ne passe au banc que sous les plafonds (refus à la création,
arrêt avant l'appel de trop), sans repli."""
import hashlib
import json
import logging
import random
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from fabrique import garde
from fabrique.garde import Refus
from fabrique.moteur import execution, installation, outils, recettes
from fabrique.noyau import etat, routeur
from fabrique.noyau.models import Banc, Depense, Outil, Parametre, Session, noter
from fabrique.session.models import Reglage, Video

log = logging.getLogger(__name__)
ENTREES_MAX = 6
ECART = 0.5  # sur 10
JUGES = {"simule": {"titre": "Juge simulé (simulation)", "briques": None},
         "whisper": {"titre": "Whisper : le texte entendu comparé au texte voulu", "briques": {"voix"}}}


def juges(brique: str) -> list[str]:
    """Les juges possibles pour une brique : le faux en simulation, les vrais sinon (shortcut: un seul vrai juge, pour la voix ; ceux des images,
    du chant et du présentateur arrivent avec leurs bancs, J9 et J10)."""
    if etat.simulation():
        return ["simule"]
    return [j for j, d in JUGES.items() if j != "simule" and d["briques"] and brique in d["briques"]]


def dossier(b: Banc) -> Path:
    return garde.verifier(settings.RACINE / "bancs" / str(b.id))


def creer(s: Session, video_id: str, brique: str, outil_b: str, juge: str, acteur: str) -> Banc:
    """Le banc et sa tâche dans la file (Claude : dans la session « Essais » seulement, comme toute fabrication). Ses entrées sont les morceaux
    finis de la première étape de cette brique dans la recette, rejoués par plan ou par scène : une étape faite vidéo entière (F1) travaille
    dans l'atelier de la vidéo et ne passe pas au banc, sauf si elle est la première de la recette (le chant de F5 : rien d'avant elle). Chaque demande est copiée dans le banc (une vidéo refaite ensuite ne le change pas)."""
    from fabrique.moteur import file
    from fabrique.noyau import cles

    if brique not in outils.BRIQUES:
        raise Refus(f"brique inconnue : {brique}")
    if juge and juge not in juges(brique):
        raise Refus(f"le juge « {juge} » ne note pas la brique {outils.BRIQUES[brique]['titre']} ici (possibles : {', '.join(juges(brique)) or 'aucun'})")
    with routeur.session(s):
        v = Video.objects.filter(id=video_id).first()
        if v is None:
            raise Refus(f"vidéo inconnue : {video_id}")
        R = recettes.Recette.model_validate(v.recette)
        reglages = dict(Reglage.objects.values_list("cle", "valeur"))
        etape = next((e for e in R.etapes if e.brique == brique), None)
        finis = [m for m in v.morceaux.filter(etape=etape.id, etat="fini").order_by("ordre") if (execution.dossier(s, m) / "demande.json").is_file()] if etape else []
    if etape and etape.par == "video" and R.etapes.index(etape):
        raise Refus(f"l'étape {etape.id} du format {R.id} se fait vidéo entière, dans l'atelier de la vidéo : elle ne passe pas au banc (un format par plan ou par scène, oui)")
    if etape and R.outils.get(etape.id):
        raise Refus(f"le format {R.id} impose son outil pour l'étape {etape.id} : un banc n'y changerait rien")
    if not finis:
        raise Refus(f"cette vidéo n'a aucun morceau fini de la brique {outils.BRIQUES[brique]['titre']} : rien à rejouer")
    outil_a = outils.choisir(brique, etape.id, finis[0].langue, {}, R.outils, reglages)
    b = outils.fiches().get(outil_b)
    if b is None or brique not in b.roles:
        raise Refus(f"l'outil « {outil_b} » n'existe pas pour la brique {brique}")
    if outil_b == outil_a:
        raise Refus(f"{b.nom} est déjà l'outil en place : le banc le compare à un autre")
    if outils.etat(b) == "retire":
        raise Refus(f"{b.nom} est retiré : le remettre parmi les candidats d'abord")
    if etat.simulation() and not b.faux:
        raise Refus("en simulation, un banc ne compare que des faux outils (passer en mode réel pour un vrai outil)")
    if installation.constat(b)["etat"] not in ("pret", "installe"):
        raise Refus(f"{b.nom} n'est pas installé dans sa version {b.version} : l'installer d'abord (écran Outils)")
    if b.cle and not cles.lire(b.cle):
        raise Refus(f"{b.nom} demande sa clé : RT la saisit dans Système → Clés")
    a = outils.fiches()[outil_a]
    finis = [m for m in finis if all(not f.langues or not m.langue or m.langue in f.langues for f in (a, b))]
    if not finis:
        raise Refus("aucun morceau de cette vidéo n'est dans une langue que les deux outils parlent")
    pris = [finis[round(i * (len(finis) - 1) / (ENTREES_MAX - 1))] for i in range(ENTREES_MAX)] if len(finis) > ENTREES_MAX else finis
    pris = list(dict.fromkeys(pris))  # sans doublon, dans l'ordre de la vidéo
    demandes = [outils.Demande.model_validate_json((execution.dossier(s, m) / "demande.json").read_text(encoding="utf-8")) for m in pris]
    cout = {f.id: sum(outils.adaptateur(f).estimer(f, d).cout_eur for d in demandes) for f in (a, b)}
    for f in (a, b):
        if not f.local and (raison := execution.refus_payant(s, f, cout[f.id], reglages, pour=f"pour ce banc de {len(pris)} entrée(s)")):
            raise Refus(f"banc refusé : {raison}")
    if Banc.objects.filter(video_id=video_id, brique=brique, outil_b=outil_b, etat__in=("attente", "en_cours", "a_voter")).exists():
        raise Refus(f"un banc de {b.nom} sur cette vidéo est déjà en cours")
    banc = Banc.objects.create(brique=brique, outil_a=outil_a, outil_b=outil_b, session_id=s.id, video_id=video_id, juge=juge, acteur=acteur,
                               versions={"a": a.version, "b": b.version},
                               entrees=[{"unite": m.unite, "langue": m.langue, "texte": d.texte, "gauche": random.choice("ab")} for m, d in zip(pris, demandes)])
    try:
        for i, d in enumerate(demandes):
            (dossier(banc) / str(i)).mkdir(parents=True, exist_ok=True)
            (dossier(banc) / str(i) / "demande.json").write_text(d.model_dump_json(indent=1), encoding="utf-8")
        file.mettre(s, video_id, f"Banc {outils.BRIQUES[brique]['titre'].lower()} : {len(pris)} entrée(s)", acteur, banc=banc.id)
    except (Refus, OSError):
        shutil.rmtree(dossier(banc), ignore_errors=True)
        banc.delete()
        raise
    noter(acteur, "banc", banc=banc.id, quoi="créé", brique=brique, outils=[outil_a, outil_b], juge=juge)
    return banc


def demande_de(b: Banc, i: int) -> outils.Demande:
    return outils.Demande.model_validate_json((dossier(b) / str(i) / "demande.json").read_text(encoding="utf-8"))


def sortie(b: Banc, i: int, outil: str) -> Path:
    """La sortie de l'outil « a » ou « b » pour l'entrée i, rangée sous le côté où RT la voit : le chemin ne dit pas quel outil l'a faite."""
    return dossier(b) / str(i) / ("gauche" if b.entrees[i]["gauche"] == outil else "droite")


def faites(b: Banc) -> int:
    return sum(execution.lu(sortie(b, i, c)) is not None for i in range(len(b.entrees)) for c in "ab")


def estimer(b: Banc) -> dict:
    """Ce qui reste du banc : durée (estimation des outils) et coût."""
    secondes = cout = 0.0
    for i in range(len(b.entrees)):
        for c, o in (("a", b.outil_a), ("b", b.outil_b)):
            if execution.lu(sortie(b, i, c)) is None and o in outils.fiches():
                f = outils.fiches()[o]
                x = outils.adaptateur(f).estimer(f, demande_de(b, i))
                secondes, cout = secondes + x.secondes, cout + x.cout_eur
    return {"secondes": round(secondes, 1), "cout_eur": round(cout, 2),
            "carte_go": max((outils.fiches()[o].besoins.carte_go for o in (b.outil_a, b.outil_b) if o in outils.fiches()), default=0)}


def jouer(banc_id: int, alerter=lambda texte: None, progres=lambda: None):
    """Les sorties qui manquent, outil par outil (chaque modèle chargé une fois), puis les notes du juge ; Echec si une sortie épuise ses essais.
    L'atelier de chaque demande est celui du banc : un outil n'écrit jamais dans le dossier de la vidéo."""
    b = Banc.objects.get(id=banc_id)
    s = Session.objects.get(id=b.session_id)
    with routeur.session(s):
        reglages = dict(Reglage.objects.values_list("cle", "valeur"))
    Banc.objects.filter(id=b.id).update(etat="en_cours", raison="")
    for c, o in (("a", b.outil_a), ("b", b.outil_b)):
        f = outils.fiches().get(o)
        if f is None or outils.etat(f) == "retire" or f.version != b.versions.get(c, f.version):
            raise execution.Echec(f"l'outil {o} a été retiré ou changé de version depuis la création du banc : refaire un banc")
        for i in range(len(b.entrees)):
            if execution.lu(final := sortie(b, i, c)) is not None:
                continue
            d = demande_de(b, i).model_copy(update={"atelier": str(dossier(b) / str(i) / f"atelier_{final.name}")})
            for essai in range(1, (execution.ESSAIS if f.local else execution.ESSAIS_PAYANT) + 1):
                depense = None
                if not f.local:
                    cout = outils.adaptateur(f).estimer(f, d).cout_eur
                    if raison := execution.refus_payant(s, f, cout, reglages):
                        raise execution.Echec(f"banc arrêté avant l'appel de trop : {raison}")
                    depense = Depense.objects.create(session_id=s.id, outil=f.id, estime_eur=cout)
                try:
                    r = execution.produire(f, d, final)
                except Exception as x:  # noqa: BLE001 — l'outil peut tout lever : essai suivant, ou arrêt avec la cause
                    log.warning("banc %s, %s, entrée %s, échec %s : %s", b.id, f.id, i, essai, x)
                    if essai == (execution.ESSAIS if f.local else execution.ESSAIS_PAYANT):
                        raise execution.Echec(f"banc {b.id}, entrée {i + 1} : {f.nom} a échoué {essai} fois — {x}") from x
                    time.sleep(execution.PAUSE_S)
                    continue
                if depense:
                    depense.reel_eur = r.infos.get("cout_eur")
                    depense.save(update_fields=["reel_eur"])
                progres()
                break
    raison = ""
    if b.juge:
        lot = [(demande_de(b, i), sortie(b, i, c) / execution.lu(sortie(b, i, c)).fichiers[0]) for i in range(len(b.entrees)) for c in "ab"]
        try:
            notes = notes_du_juge(b.juge, lot)
            Banc.objects.filter(id=b.id).update(notes={str(i): {"a": notes[2 * i], "b": notes[2 * i + 1]} for i in range(len(b.entrees))})
        except Exception as x:  # noqa: BLE001 — le juge est « en plus » : sans lui, RT vote quand même
            log.exception("juge du banc %s", b.id)
            raison = f"le juge n'a pas pu noter ce banc ({x}) : votes de RT seulement"[:500]
            alerter(raison)
    Banc.objects.filter(id=b.id, etat="en_cours").update(etat="a_voter", raison=raison)


def notes_du_juge(juge: str, lot: list[tuple[outils.Demande, Path]]) -> list[float]:
    """Une note sur 10 pour chaque (demande, fichier) ; le juge ne voit que les fichiers et les demandes, jamais le nom de l'outil."""
    if juge == "simule":  # déterministe : la même sortie a toujours la même note
        return [round(int(hashlib.sha256(f.read_bytes()).hexdigest()[:8], 16) % 101 / 10, 1) for _, f in lot]
    if juge == "whisper":
        return whisper(lot)
    raise Refus(f"juge inconnu : {juge}")


def whisper(lot: list[tuple[outils.Demande, Path]]) -> list[float]:
    """Whisper large-v3 (dans Linux, celui de F1) réécoute chaque voix dans sa langue ; note = 10 × ressemblance du texte entendu au texte voulu."""
    from fabrique.moteur.f1 import langue_texte
    from fabrique.moteur.f1.outils import dans_wsl, wsl
    from fabrique.moteur.f1.voix import wslp, wslq

    (settings.RACINE / "bancs").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=settings.RACINE / "bancs") as t:
        lf = Path(t) / "lot.json"
        lf.write_text(json.dumps([{"wav": wslp(f), "langue": d.langue or "en", "texte": d.texte} for d, f in lot], ensure_ascii=False), encoding="utf-8")
        cmd = ("cd " + dans_wsl("longcat") + " && ./venv/bin/python " + wslq(Path(__file__).parent / "f1" / "whisper_langue_wsl.py") + " " + wslq(lf)
               + " " + dans_wsl("whisper"))
        subprocess.run(wsl(cmd), capture_output=True, timeout=3600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        rf = lf.with_name("lot_resultat.json")
        if not rf.is_file():
            raise RuntimeError("Whisper n'a pas répondu (Linux de l'app) : le banc reste sans note du juge")
        return [round(10 * langue_texte.score(r["texte"], r["entendu"], r["langue"]), 2) for r in json.loads(rf.read_text(encoding="utf-8"))]


def verdict(b: Banc) -> dict:
    """Les votes de RT décident ; le juge est montré à côté (une victoire de moins de ECART point ne compte pas), s'il a noté."""
    rt = Counter(b.votes.values())
    juge = Counter("b" if x["b"] - x["a"] >= ECART else "a" if x["a"] - x["b"] >= ECART else "egal" for x in b.notes.values())
    gagnant = b.outil_a if rt["a"] > rt["b"] else b.outil_b if rt["b"] > rt["a"] else ""
    pour_juge = b.outil_a if juge["a"] > juge["b"] else b.outil_b if juge["b"] > juge["a"] else ""
    nom = lambda o: outils.fiches()[o].nom if o in outils.fiches() else o  # noqa: E731
    g = "a" if gagnant == b.outil_a else "b"
    texte = (f"{nom(gagnant)} gagne ({rt[g]} contre {rt['b' if g == 'a' else 'a']}, {rt['egal']} égalité(s))" if gagnant
             else f"pas de vainqueur ({rt['a']} contre {rt['b']}, {rt['egal']} égalité(s))")
    if b.juge and b.notes:
        texte += (f" ; juge ({JUGES[b.juge]['titre']}) : {nom(b.outil_a)} {juge['a']}, {nom(b.outil_b)} {juge['b']}, sans écart {juge['egal']}"
                  + (" — le juge n'est pas d'accord" if pour_juge and gagnant and pour_juge != gagnant else ""))
    elif b.juge:
        texte += " ; sans note du juge (il a échoué)"
    return {"gagnant": gagnant, "rt": dict(rt), "juge": dict(juge), "juge_pour": pour_juge, "texte": texte}


def voter(banc_id: int, entree: int, choix: str, acteur: str) -> str:
    """Le vote de RT sur une entrée (gauche, droite, égal), modifiable jusqu'à « Rendre le verdict » ; lu et écrit d'un coup (jamais un vote perdu
    quand deux arrivent ensemble)."""
    if acteur != "RT":
        raise Refus("seul RT vote aux bancs")
    if choix not in ("gauche", "droite", "egal"):
        raise Refus("vote attendu : gauche, droite ou égal")
    with transaction.atomic():
        b = Banc.objects.filter(id=banc_id).first()
        if b is None or b.etat != "a_voter":
            raise Refus("ce banc n'attend pas de vote")
        if not 0 <= entree < len(b.entrees):
            raise Refus("entrée inconnue dans ce banc")
        g = b.entrees[entree]["gauche"]
        b.votes[str(entree)] = "egal" if choix == "egal" else g if choix == "gauche" else ("b" if g == "a" else "a")
        b.save(update_fields=["votes"])
    return f"Vote enregistré ({len(b.votes)}/{len(b.entrees)})" + (" : « Rendre le verdict » quand vous êtes sûr." if len(b.votes) == len(b.entrees) else ".")


def rendre(banc_id: int, acteur: str) -> str:
    """Toutes les entrées votées : le verdict, gardé en base et dans verdict.json ; ensuite les côtés et les notes du juge se voient."""
    if acteur != "RT":
        raise Refus("seul RT rend le verdict d'un banc")
    with transaction.atomic():
        b = Banc.objects.filter(id=banc_id).first()
        if b is None or b.etat != "a_voter":
            raise Refus("ce banc n'attend pas de verdict")
        if len(b.votes) < len(b.entrees):
            raise Refus(f"voter chaque entrée d'abord ({len(b.votes)}/{len(b.entrees)})")
        b.verdict, b.etat, b.fini = verdict(b), "fini", timezone.now()
        b.save(update_fields=["verdict", "etat", "fini"])
    (dossier(b) / "verdict.json").write_text(json.dumps({"banc": b.id, "brique": b.brique, "a": b.outil_a, "b": b.outil_b, "versions": b.versions, "juge": b.juge,
                                                       "entrees": b.entrees, "votes": b.votes, "notes": b.notes, "verdict": b.verdict, "fini": b.fini.isoformat()},
                                                      ensure_ascii=False, indent=1), encoding="utf-8")
    noter(acteur, "banc", banc=b.id, quoi="verdict", texte=b.verdict["texte"])
    return f"Verdict : {b.verdict['texte']}."


def refus_adoption(b: Banc) -> str:
    """Pourquoi le vainqueur ne peut pas devenir le défaut ; vide s'il le peut (fiche là, pas retiré, installé dans la version du banc, pas un faux
    outil en mode réel)."""
    if b.etat != "fini":
        return "ce banc n'a pas de verdict"
    if b.adopte:
        return f"déjà adopté ({b.adopte})"
    if b.verdict.get("gagnant") != b.outil_b:
        return "le nouvel outil n'a pas gagné ce banc : l'outil en place reste" if b.verdict.get("gagnant") else "pas de vainqueur : rien à adopter"
    f = outils.fiches().get(b.outil_b)
    if f is None or outils.etat(f) == "retire":
        return "l'outil gagnant a été retiré depuis le banc"
    if f.version != b.versions.get("b") or installation.constat(f)["etat"] not in ("pret", "installe"):
        return f"{f.nom} a changé de version ou n'est plus installé depuis le banc : refaire un banc"
    if f.faux and not etat.simulation():
        return "un faux outil ne s'adopte qu'en simulation"
    return ""


def adopter(banc_id: int, ou: str, acteur: str) -> str:
    """L'accord de RT : le vainqueur du banc devient le défaut de la brique (toutes les sessions) ou de la session du banc ; rien d'autre ne bouge."""
    if acteur != "RT":
        raise Refus("seul RT change l'outil d'une brique, après un banc")
    if ou not in ("brique", "session"):
        raise Refus("adopter pour la brique ou pour la session")
    with transaction.atomic():
        b = Banc.objects.filter(id=banc_id).first()
        if b is None:
            raise Refus(f"banc inconnu : {banc_id}")
        if raison := refus_adoption(b):
            raise Refus(raison)
        s = Session.objects.get(id=b.session_id)
        with routeur.session(s):
            if ou == "session":
                Reglage.objects.update_or_create(cle=f"outil.{b.brique}", defaults={"valeur": b.outil_b})
        if ou == "brique":
            Parametre.ecrire(f"outil.{b.brique}", b.outil_b)
        Outil.objects.update_or_create(id=b.outil_b, defaults={"etat": "en_service"})
        Banc.objects.filter(id=b.id).update(adopte=ou)
        noter(acteur, "banc", banc=b.id, quoi="adopté", outil=b.outil_b, ou=ou, avant=b.outil_a)
    f, avant = outils.fiches()[b.outil_b], outils.fiches().get(b.outil_a)
    return (f"{f.nom} est maintenant l'outil {outils.BRIQUES[b.brique]['titre'].lower()} "
            + ("de toutes les sessions (sauf celles qui ont le leur)" if ou == "brique" else f"de « {s.nom} »")
            + (f" ; {avant.nom} reste disponible" if avant else "") + (" ; outil payant : chaque appel compte dans les plafonds." if not f.local else "."))


def dernier(outil: str) -> str:
    """Le dernier verdict d'un outil, pour sa fiche."""
    b = (Banc.objects.filter(etat="fini", outil_a=outil) | Banc.objects.filter(etat="fini", outil_b=outil)).order_by("-fini").first()
    return f"{timezone.localtime(b.fini):%d/%m/%Y} : {b.verdict['texte']}" if b else ""


ETATS = {"attente": "dans la file", "en_cours": "en cours", "a_voter": "à voter", "fini": "verdict rendu", "erreur": "en erreur", "annule": "annulé"}


def resume(b: Banc) -> dict:
    """La ligne d'un banc dans la liste (BancListe) ; une session ou une vidéo disparue ne l'empêche pas de s'afficher."""
    s = Session.objects.filter(id=b.session_id).first()
    titre = ""
    if s:
        with routeur.session(s):
            titre = Video.objects.filter(id=b.video_id).values_list("titre", flat=True).first() or ""
    nom = lambda o: outils.fiches()[o].nom if o in outils.fiches() else o  # noqa: E731
    return {"id": b.id, "brique": outils.BRIQUES.get(b.brique, {}).get("titre", b.brique), "session": s.nom if s else "", "video": titre, "etat": b.etat,
            "etat_nom": ETATS[b.etat], "outils": f"{nom(b.outil_a)} (en place) contre {nom(b.outil_b)}", "juge": JUGES.get(b.juge, {}).get("titre", "aucun"),
            "entrees": len(b.entrees), "votes": len(b.votes), "verdict": b.verdict.get("texte", ""), "raison": b.raison, "cree": f"{timezone.localtime(b.cree):%d/%m/%Y %H:%M}"}


def detail(b: Banc) -> dict:
    """Ce que RT voit pour voter : chaque entrée, gauche et droite ; les outils de chaque côté et les notes du juge seulement après le verdict."""
    fini, lignes = b.etat == "fini", []
    for i, e in enumerate(b.entrees):
        cotes = {"gauche": e["gauche"], "droite": "b" if e["gauche"] == "a" else "a"}
        fichiers = {c: [str(sortie(b, i, x) / f) for f in getattr(execution.lu(sortie(b, i, x)), "fichiers", [])] for c, x in cotes.items()}
        vote = b.votes.get(str(i), "")
        lignes.append({"n": i, "texte": e["texte"], "langue": e["langue"], **fichiers,
                       "vote": "egal" if vote == "egal" else next((c for c, x in cotes.items() if x == vote), ""),
                       "notes": {c: b.notes[str(i)][x] for c, x in cotes.items()} if fini and str(i) in b.notes else None,
                       "qui": {c: outils.fiches()[b.outil_a if x == "a" else b.outil_b].nom for c, x in cotes.items()} if fini else None})
    return {**resume(b), "lignes": lignes, "gagnant": outils.fiches()[g].nom if (g := b.verdict.get("gagnant")) in outils.fiches() else "", "adopte": b.adopte,
            "peut_adopter": not refus_adoption(b)}
