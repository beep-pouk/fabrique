"""Recette d'installation dans le bac à sable (repris de Bramble Studio ; appelée par construire.py, lue par verifier.py --jalon J1), avec un
installateur D'ESSAI (« Fabrique (bac à sable) » : autre identifiant, autre identité, port 8810 : il ne touche jamais à l'installation de RT),
dans le dossier de construction : refus d'un dossier non vide et d'un dossier de studio ; installation silencieuse ; ce que Windows en voit
(Applications installées, menu Démarrer, bureau, démarrage, signatures) ; lancement comme un clic, rien sur le chemin ; la fenêtre démarre le
noyau ; sauvegarde du soir rattrapée ; contrôles du banc (programme fenêtré, sans droits d'administrateur, aucune bibliothèque hors du
programme et de Windows) ; fenêtre fermée, revenue au 2e lancement, quittée, relancée ; sauvegarde au clic puis restauration ; essai de recette ; lecteur vidéo ; noyau tué puis
relancé par la fenêtre ; programme jamais écrit ; mise à jour vers une version factice par « Mettre à jour » ; arrêt ; désinstallation : il ne
reste que les données. Aucune console ; chaque processus s'appelle Fabrique.exe. Outil de développement (Windows) : jamais livré."""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import banc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fabrique.fenetre.client import Client, ErreurApi, ouvert, sonner  # noqa: E402

NOM = "Fabrique (bac à sable)"
DESINSTALLATION = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{5E0C2B7A-9F14-4C3B-8E2D-6A1F0B9C4D02}_is1"
PORT = 8810  # dossiers.PORT_BAC
SILENCE = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
GARDES = ("SystemRoot", "SystemDrive", "windir", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "ProgramData", "USERNAME", "COMPUTERNAME",
          "HOMEDRIVE", "HOMEPATH", "PUBLIC", "ALLUSERSPROFILE", "OS", "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS")


BRAMBLE = {"DJANGO_SETTINGS_MODULE": "config.settings", "PYTHONPATH": r"C:\absent\studio", "PYTHONHOME": r"C:\absent\runtime", "VIRTUAL_ENV": r"C:\absent\.venv"}
# ce qu'un processus de Bramble Studio (ou la supervision lancée par lui) transmet à Fabrique : 17/11, noyau mort au démarrage chez RT
LECTURE = """import webview
from webview.platforms import winforms
print("ok")
"""  # la fenêtre WebView2 dans le Python installé : un fichier de pywebview ou de pythonnet oublié par la construction se verrait ici


def env_reduit() -> dict:
    """Comme un clic, sur un PC où rien n'est installé sur le chemin : aucun Python, aucun outil, aucune variable de Fabrique."""
    return {**{k: os.environ[k] for k in GARDES if k in os.environ}, "PATH": str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32")}


def lancer(*commande, **options):
    return subprocess.run([str(c) for c in commande], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=options.pop("timeout", 300), **options)


def tuer_sous(dossier: Path):
    for pid in banc.sous(dossier):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)


def nettoyer(bac: Path, effacer: bool = True):
    """Une recette précédente interrompue ne laisse rien d'installé : l'installation d'essai est arrêtée et retirée, ses raccourcis aussi."""
    if ancien := banc.registre(DESINSTALLATION, "UninstallString"):
        prog = Path(ancien.strip('"')).parent
        tuer_sous(prog)
        subprocess.run([str(prog / "unins000.exe"), *SILENCE], timeout=300)
    tuer_sous(bac)
    for d in banc.raccourcis().values():
        (d / f"{NOM}.lnk").unlink(missing_ok=True)
    if effacer and bac.exists():
        shutil.rmtree(bac)  # le bac de la recette précédente (dans le dossier de construction : jamais un vrai dossier de Fabrique)


def jouer(assemble: Path, bac: Path, dire=print, preuve: Path | None = None) -> list[str]:
    import construire

    if preuve:
        preuve.unlink(missing_ok=True)
    nettoyer(bac)
    racine = bac / "FABRIQUE"
    prog, donnees = racine / "programme", racine / "donnees"
    exe, env = prog / "Fabrique.exe", env_reduit()
    v0 = construire.version()
    v1 = ".".join([*v0.split(".")[:2], str(int(v0.split(".")[2]) + 1)])
    i0 = construire.installateur(assemble, bac / "installateurs", bac=True)
    i1 = construire.installateur(assemble, bac / "installateurs", bac=True, numero=v1)
    client, points = Client(port=PORT, donnees=donnees), []

    def sante() -> dict:  # le noyau peut tomber entre deux questions (relance, mise à jour)
        try:
            return client.appeler("sante")
        except (OSError, ErreurApi):
            return {}

    def point(texte: str):
        dire(f"  {texte}")
        points.append(texte)

    def fenetre(delai: float, quoi: str):
        return banc.attendre(lambda: [f for f in banc.fenetres() if f[1] == NOM and f[4] > 400 and os.path.normcase(banc.processus().get(f[3], "")) == os.path.normcase(str(exe))],
                             delai, quoi)

    lieux = banc.raccourcis()
    avant = {n: {f.name for f in d.glob("*.lnk")} for n, d in lieux.items()}
    consoles_avant = {f[0] for f in banc.fenetres() if f[2] in banc.CONSOLES}
    vus, consoles, fini, hors_guet = set(), {}, threading.Event(), threading.Event()

    def surveiller():  # tout au long de la recette : les exe du programme qui tournent, les consoles qui apparaissent
        while not fini.wait(0.3):
            if not hors_guet.is_set():  # l'étape « lecteur » lance elle-même le Python installé : ce n'est pas un processus de Fabrique
                vus.update(Path(c).name for c in banc.sous(prog).values())
            consoles.update({f[0]: f for f in banc.fenetres() if f[2] in banc.CONSOLES and f[0] not in consoles_avant})

    threading.Thread(target=surveiller, daemon=True).start()
    reussi = False
    try:
        # 0. refus : rien n'est écrit
        autre, studio = bac / "autre chose", bac / "un studio"
        autre.mkdir()
        (autre / "document.txt").write_text("pas une installation", encoding="utf-8")
        (studio / "PROJET").mkdir(parents=True)
        for dossier, quoi in ((autre, "dossier non vide"), (studio, "dossier d'un studio de Bramble Studio")):
            r = lancer(i0, *SILENCE, f"/DIR={dossier}", env=env)
            assert r.returncode != 0 and not (dossier / "programme").exists() and banc.registre(DESINSTALLATION, "DisplayName") is None, f"{quoi} : pas refusé ({r.returncode})"
        point("refus d'installer dans un dossier non vide ou dans un studio de Bramble Studio : rien n'a été écrit")

        # 1. installer, comme RT la première fois : l'installateur publié dans <racine>\versions, lancé de là
        construire.publier(i0, racine / "versions", v0, ["Version de la recette d'installation."])
        r = lancer(racine / "versions" / i0.name, *SILENCE, f"/DIR={racine}", "/TASKS=bureau,demarrage", f"/LOG={bac / 'installation.log'}", env=env, timeout=600)
        assert r.returncode == 0 and exe.is_file(), f"installation : code {r.returncode} (journal : {bac / 'installation.log'})"
        vu = {v: banc.registre(DESINSTALLATION, v) for v in ("DisplayName", "DisplayVersion", "Publisher", "DisplayIcon")}
        assert vu == {"DisplayName": NOM, "DisplayVersion": v0, "Publisher": "StudioKids", "DisplayIcon": str(exe)}, vu
        for n, d in lieux.items():
            nouveaux = {f.name for f in d.glob("*.lnk")} - avant[n]
            assert nouveaux == {f"{NOM}.lnk"}, f"{n} : {nouveaux}"
            assert banc.identite(d / f"{NOM}.lnk").lower() == f"StudioKids.Fabrique.Bac | {exe}".lower(), f"{n} : {banc.identite(d / f'{NOM}.lnk')}"
        signes = {f.name: banc.signataire(f) for f in (exe, prog / "unins000.exe", i0)}
        assert len(set(signes.values())) == 1 and all(signes.values()), f"signatures : {signes}"
        assert banc.sous_systeme(exe) == 2, "Fabrique.exe n'est pas un programme fenêtré"
        taille = sum(f.stat().st_size for f in prog.rglob("*") if f.is_file()) / 2**20
        point(f"installée comme RT la première fois (installateur publié dans le dossier versions, lancé de là) : entrée « {NOM} » {v0} (StudioKids) dans Windows, 3 raccourcis à l'identité de l'app, programme ({taille:.0f} Mio), "
              "installateur et désinstallateur signés ; Fabrique.exe est un programme fenêtré (jamais de console)")

        # 1 bis. programme abîmé (fichiers effacés, 22/11) : le lanceur le dit et propose le dernier installateur du dossier versions
        effaces = (prog / "runtime" / "Lib" / "csv.py", prog / construire.MARQUE)  # la marque aussi : l'installateur ne doit pas refuser le dossier
        for f in effaces:
            f.unlink()
        p = None
        try:
            p = subprocess.Popen([str(exe)], env=env, cwd=str(prog))
            h, texte = banc.boite(p.pid, 30)
            banc.repondre(h, 7)  # « Non » (« Oui » lance ce même installateur, joué ici en silence)
            assert p.wait(30) == 1 and f"{len(effaces)} fichier(s)" in texte and i0.name in texte, texte  # le lanceur nomme le 1er manquant (ici la marque)
        finally:
            if p and p.poll() is None:  # pas de boîte : il démarrait comme si de rien n'était
                p.kill()
        r = lancer(racine / "versions" / i0.name, *SILENCE, f"/DIR={racine}", f"/LOG={bac / 'reparation.log'}", env=env, timeout=600)
        assert r.returncode == 0 and all(f.is_file() for f in effaces), f"réparation : code {r.returncode} (journal : {bac / 'reparation.log'})"
        point(f"programme abîmé (fichiers effacés) : Fabrique le dit au lancement et propose « {i0.name} » du dossier versions ; « Non » : rien ne démarre ; "
              "l'installateur proposé répare (fichiers revenus)")
        installe = banc.empreinte(prog)

        # 2. lancer comme un clic : la fenêtre démarre le noyau
        t0 = time.monotonic()
        subprocess.Popen([str(exe)], env=env, cwd=str(prog))
        banc.attendre(client.repond, 120, "le noyau répond (démarré par la fenêtre)")
        f = fenetre(60, f"la fenêtre « {NOM} » est visible")
        lu = sante()
        assert lu.get("version") == v0 and lu.get("mode") == "simulation", lu
        point(f"lancée comme un clic, rien sur le chemin : fenêtre « {NOM} » et noyau prêts en {time.monotonic() - t0:.1f} s, en simulation")

        # 3. la sauvegarde du soir, jamais faite : rattrapée au démarrage
        banc.attendre(lambda: client.appeler("sauvegardes")["derniere"].get("etat") == "faite", 180, "la sauvegarde du soir est rattrapée", pas=1)
        s = client.appeler("sauvegardes")
        assert len(s["liste"]) == 1 and Path(s["dossier"]) == racine / "sauvegardes", s
        point(f"sauvegarde du soir rattrapée au premier démarrage (tâche détachée) : {s['liste'][0]['nom']}")

        # 4. contrôles du banc d'interface sur le programme livré
        pids = banc.sous(prog)
        assert {Path(c).name for c in pids.values()} == {"Fabrique.exe"} and len(pids) == 2, f"processus : {pids}"
        dehors = sorted({m for p in pids for m in banc.externes(p, prog)})
        assert not dehors, "bibliothèques chargées hors du programme et de Windows :\n" + "\n".join(dehors)
        r = lancer(exe, "diagnostic", env=env)
        assert r.returncode == 0 and "ok sans droits d'administrateur" in r.stdout, f"diagnostic : code {r.returncode}\n{r.stdout}\n{r.stderr}"
        point("contrôles du banc : deux processus (fenêtre, noyau), tous « Fabrique.exe » ; aucune bibliothèque chargée hors du programme et de "
              "Windows ; diagnostic vert, sans droits d'administrateur")

        # 5. fenêtre fermée (le noyau continue), revenue au 2e lancement, quittée, relancée
        banc.fermer_fenetre(f[0][0])
        banc.attendre(lambda: not [x for x in banc.fenetres() if x[1] == NOM], 15, "la fenêtre se ferme (croix)")
        assert client.repond(), "le noyau s'est arrêté avec la fenêtre"
        r = lancer(exe, env=env, timeout=60)
        assert r.returncode == 0, f"2e lancement : code {r.returncode}"
        fenetre(20, "la fenêtre revient au 2e lancement")
        assert len(banc.sous(prog)) == 2, f"instance unique : {banc.sous(prog)}"
        assert sonner("quitter", PORT)
        banc.attendre(lambda: len(banc.sous(prog)) == 1 and not ouvert(PORT + 1), 20, "la fenêtre se quitte, le noyau continue")
        assert client.repond()
        subprocess.Popen([str(exe)], env={**env, **BRAMBLE}, cwd=str(prog))
        fenetre(60, "la fenêtre est relancée")
        point("fenêtre fermée (le noyau continue), revenue au 2e lancement (instance unique), quittée, puis relancée depuis un parent qui porte les "
              "variables de Bramble Studio (DJANGO_SETTINGS_MODULE, PYTHONPATH, PYTHONHOME, VIRTUAL_ENV)")

        # 6. sauvegarde au clic, puis restauration
        client.appeler("sauvegarder")
        banc.attendre(lambda: len((s := client.appeler("sauvegardes"))["liste"]) == 2 and s["derniere"].get("etat") == "faite", 180, "la sauvegarde au clic est faite", pas=1)
        nom = client.appeler("sauvegardes")["liste"][0]["nom"]
        client.appeler("enregistrer_cle", {"valeur": "cle-factice-de-la-recette"}, nom="gemini")
        assert {c["nom"]: c["ou"] for c in client.appeler("cles")}["gemini"] == "enregistrée"
        client.appeler("restaurer", nom=nom)
        assert {c["nom"]: c["ou"] for c in client.appeler("cles")}["gemini"] == "absente", "la restauration n'a pas remis la base d'avant"
        assert list((donnees / "_old").glob("restauration_*/donnees/noyau.sqlite3")), "l'état d'avant la restauration n'est pas gardé"
        point(f"sauvegarde au clic ({nom}), puis restauration : la clé enregistrée après elle a disparu, l'état d'avant est gardé dans donnees\\_old")

        # 6 bis. un essai de recette par le programme installé : « moteur » (Claude) met la vidéo dans la file, le noyau la fait jouer
        script = bac / "script.json"
        script.write_text(json.dumps({"titre": "Essai installé", "scenes": [{"id": "s1", "plans": [{"id": "p1", "texte": "Bonjour."}]}]}), encoding="utf-8")
        r = lancer(exe, "moteur", "essai", script, env={**env, **BRAMBLE})
        assert r.returncode == 0 and "dans la file" in r.stdout, f"moteur : {r.returncode} {r.stdout} {r.stderr}"
        # réponse A de la supervision (25/11) : quand Bramble Studio a la carte, la file lui cède ; l'étape est notée non jouée au lieu de bloquer la version
        t = banc.attendre(lambda: next((t for t in client.appeler("file") if t["titre"] == "Essai installé" and (t["etat"] in ("finie", "erreur")
                                        or t["etat"] == "attente" and t["raison"].startswith("Bramble Studio"))), None), 180,
                          f"l'essai est fabriqué ({client.appeler('file')})", pas=1)
        if t["etat"] == "attente":
            point(f"essai de recette par le programme installé : « moteur essai » l'a mis dans la file ; non joué : carte prise par Bramble Studio (la file attend : « {t['raison']} »)")
        else:
            assert t["etat"] == "finie" and t["progression"] == "15/15", t
            point(f"essai de recette par le programme installé : « moteur essai » puis le noyau et son exécuteur (Fabrique.exe), faux outils, {t['progression']} morceaux")
        hors_guet.set()
        try:
            r = lancer(prog / "runtime" / "python.exe", "-B", "-c", LECTURE, env=env, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
        finally:
            hors_guet.clear()
        assert r.stdout.strip() == "ok", f"le Python installé ne charge pas la fenêtre WebView2 : {r.stdout} {r.stderr[-800:]}"
        point("la fenêtre WebView2 se charge dans le programme installé (pywebview, pythonnet)")

        # 7. le noyau ne bat plus : la fenêtre le relance
        ancien = int((donnees / "noyau.pid").read_text())
        subprocess.run(["taskkill", "/PID", str(ancien), "/F"], capture_output=True)
        banc.attendre(lambda: not client.repond(), 15, "le noyau est tué")
        t0 = time.monotonic()
        banc.attendre(lambda: sante().get("pid", ancien) != ancien, 120, "la fenêtre relance le noyau", pas=1)
        point(f"noyau tué : la fenêtre (lancée avec les variables de Bramble Studio) l'a relancé seule en {time.monotonic() - t0:.0f} s (chien de garde)")
        assert not (d := banc.differences(installe, banc.empreinte(prog))), "le programme a été écrit :\n" + "\n".join(d[:20])
        point("le dossier du programme n'a pas été écrit depuis l'installation")

        # 8. mise à jour vers une version factice, par « Mettre à jour »
        construire.publier(i1, racine / "versions", v1, ["Version d'essai de la recette d'installation."])
        v = client.appeler("versions")
        assert v["proposee"] == v1 and v["raison"] == "", v
        client.appeler("mettre_a_jour")
        banc.attendre(lambda: sante().get("version") == v1, 420, f"la version {v1} tourne après « Mettre à jour »", pas=2)
        fenetre(90, "la fenêtre revient après la mise à jour")
        assert banc.registre(DESINSTALLATION, "DisplayVersion") == v1 and client.appeler("versions")["raison"] == "Fabrique est à jour"
        assert list((donnees / "_old").glob("mise_a_jour_*/donnees/noyau.sqlite3")), "les bases n'ont pas été copiées avant la mise à jour"
        assert {Path(c).name for c in banc.sous(prog).values()} == {"Fabrique.exe"}
        point(f"mise à jour {v0} → {v1} par « Mettre à jour » : empreinte et signature contrôlées, bases copiées, installée en silence, Fabrique relancée seule")

        # 9. arrêt, puis désinstallation : il ne reste que les données
        r = lancer(exe, "arreter", env=env)
        assert r.returncode == 0 and not ouvert(PORT) and not ouvert(PORT + 1), f"arreter : {r.returncode} {r.stdout}"
        r = lancer(prog / "unins000.exe", *SILENCE, env=env)
        assert r.returncode == 0, f"désinstallation : code {r.returncode}"
        banc.attendre(lambda: not exe.exists(), 60, "le programme est retiré")
        assert banc.registre(DESINSTALLATION, "DisplayName") is None and all(not (d / f"{NOM}.lnk").exists() for d in lieux.values())
        assert (donnees / "noyau.sqlite3").is_file() and (racine / "sessions" / "essais" / "session.sqlite3").is_file() and len(list((racine / "sauvegardes").glob("*.zip"))) == 2
        point("arrêtée puis désinstallée : programme, raccourcis et entrée de Windows retirés ; données, sessions et sauvegardes restées")
        reussi = True
    finally:
        fini.set()
        if not reussi:
            nettoyer(bac, effacer=False)  # rien d'installé ne reste ; le bac reste pour comprendre
    assert not consoles, f"consoles apparues : {list(consoles.values())}"
    assert vus <= {"Fabrique.exe", "unins000.exe"}, f"processus du programme : {vus}"
    point("aucune console apparue ; chaque processus de Fabrique s'appelle Fabrique.exe")
    if preuve:
        preuve.write_text(json.dumps({"version": v0, "date": f"{datetime.now():%d/%m/%Y %H:%M}", "arbres": construire.arbres(), "points": points},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    return points
