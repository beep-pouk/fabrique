"""Construit Fabrique — UNE commande : python outils_dev\\construire.py [--publier] (repris de Bramble Studio, outils_dev\\construire.py)
  1. exige la suite verte et un dépôt sans modification en attente : on livre exactement ce qui est testé ;
  2. assemble <sortie>\\programme : lanceur natif signé (lanceur\\, identité StudioKids.Fabrique), runtime (le vrai Python 3.12 d'uv, jamais sa
     jonction, + paquets de uv.lock sans le groupe dev, PySide6 compris), app (fabrique\\ suivi par git, sans les tests), le tout précompilé ;
  3. compile l'installateur signé « Fabrique <version> - Installation.exe » (installateur\\fabrique.iss, Inno Setup de OUTILS\\innosetup) ;
  4. recette d'installation dans le bac à sable (outils_dev\\recette_installation.py), avec un installateur d'essai qui ne touche jamais à
     l'installation de RT.
--publier : pose l'installateur dans <studio>\\FABRIQUE\\versions avec versions.json (seule la dernière version proposée, les précédentes
rangées dans _old) : RT clique l'installateur la première fois, puis « Mettre à jour » (Système).
Sortie : OUTILS\\fabrique_construction (hors du dépôt). --vite : mise au point seulement (ni suite ni dépôt propre ; jamais pour livrer).
Outil de développement : jamais livré, jamais lancé par l'app."""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import date
from email.parser import HeaderParser
from pathlib import Path

import signer
import tester

DEPOT = Path(__file__).resolve().parents[1]
OUTILS = DEPOT.parent
SORTIE = OUTILS / "fabrique_construction"
VERSIONS = OUTILS.parent / "FABRIQUE" / "versions"
EXE = "Fabrique.exe"
MARQUE = "construit_par_construire.txt"
ICONE = DEPOT / "fabrique" / "fenetre" / "icone.ico"
PTH = "Lib\nDLLs\nLib\\site-packages\n..\\app\n"  # les chemins de Python : jamais PYTHONHOME ni PYTHONPATH (les outils lancés en hériteraient)
GIT = OUTILS / "git" / "cmd" / "git.exe"


def dire(texte: str):
    print(f"[construire] {texte}", flush=True)


def lancer(commande, **options):
    r = subprocess.run([str(c) for c in commande], **options)
    if r.returncode:
        sortie = (getattr(r, "stdout", None) or b"")[-3000:]
        raise SystemExit(f"échec ({r.returncode}) : {' '.join(str(c) for c in commande[:6])}…\n{sortie.decode('oem', 'replace') if isinstance(sortie, bytes) else sortie}")
    return r


def version() -> str:
    v = tomllib.loads((DEPOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        raise SystemExit(f"version « {v} » (pyproject.toml) : la forme attendue est X.Y.Z")
    return v


def suivis(*chemins: str) -> list[str]:
    r = lancer([GIT, "ls-files", "-z", *chemins], cwd=DEPOT, capture_output=True, text=True, encoding="utf-8")
    return [f for f in r.stdout.split("\0") if f]


def depot_propre():
    r = lancer([GIT, "status", "--porcelain", "fabrique", "lanceur", "installateur", "pyproject.toml", "uv.lock"], cwd=DEPOT, capture_output=True, text=True, encoding="utf-8")
    if r.stdout.strip():
        raise SystemExit("des modifications ne sont pas commitées (on livre exactement ce qui est testé) :\n" + r.stdout)


def arbres() -> dict:
    """Les arbres git de ce qui est livré : la preuve d'une recette ne vaut que pour eux."""
    return {d: lancer([GIT, "rev-parse", f"HEAD:{d}"], cwd=DEPOT, capture_output=True, text=True).stdout.strip() for d in ("fabrique", "lanceur", "installateur")}


def msvc() -> dict:
    """L'environnement du compilateur C de Microsoft (Build Tools du PC).
    shortcut: seul MSVC est cherché ; sur un PC sans Build Tools, ranger un compilateur portable (zig) dans OUTILS et l'ajouter ici."""
    vswhere = Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    racine = subprocess.run([str(vswhere), "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
                            capture_output=True, text=True).stdout.strip() if vswhere.is_file() else ""
    bat = Path(racine) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
    if not racine or not bat.is_file():
        raise SystemExit("compilateur C introuvable : installer « Build Tools pour Visual Studio » (gratuit)")
    r = subprocess.run(f'cmd /s /c ""{bat}" >nul 2>&1 && set"', capture_output=True, text=True, encoding="oem", errors="replace")
    env = dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)
    if not any(k.upper() == "INCLUDE" for k in env):
        raise SystemExit(f"environnement du compilateur illisible ({bat})")
    return env


def lanceur(prog: Path, travail: Path):
    """Compile lanceur\\lanceur.c : icône, version, éditeur et manifeste dans les ressources ; sans bibliothèque C ; puis le signe."""
    dire("lanceur natif…")
    env = msvc()
    chemins = next(v for k, v in env.items() if k.upper() == "PATH")
    shutil.rmtree(travail, ignore_errors=True)
    travail.mkdir(parents=True)
    for f in ("lanceur.c", "lanceur.rc", "lanceur.manifest"):
        shutil.copy(DEPOT / "lanceur" / f, travail / f)
    shutil.copy(ICONE, travail / "icone.ico")
    v = version()
    (travail / "version.h").write_text(f'#define VERSION_N {",".join((v.split(".") + ["0"])[:4])}\n#define VERSION_T "{v}"\n', encoding="ascii")
    run = lambda exe, *c: lancer([shutil.which(exe, path=chemins), *c], cwd=travail, env=env, capture_output=True)  # noqa: E731
    run("rc", "/nologo", "/fo", "lanceur.res", "lanceur.rc")
    run("cl", "/nologo", "/O1", "/GS-", "/W4", "/WX", "/c", "lanceur.c")
    run("link", "/nologo", "/NODEFAULTLIB", "/ENTRY:entree", "/SUBSYSTEM:WINDOWS", "/MANIFEST:NO", f"/OUT:{EXE}", "lanceur.obj", "lanceur.res", "kernel32.lib", "user32.lib", "shell32.lib")
    shutil.copy(travail / EXE, prog / EXE)
    dire(f"lanceur signé ({signer.signer(prog / EXE)})")


def uv(*args, **options):
    return lancer([OUTILS / "uv" / "uv.exe", *args], env={**os.environ, "UV_CACHE_DIR": str(OUTILS / "uv" / "cache")}, **options)


def paquets(python: Path, cible: Path, travail: Path):
    """Les paquets de uv.lock sans le groupe dev (empreintes vérifiées) dans `cible` : d'abord depuis le cache d'uv, sinon par le réseau."""
    req = travail / "requirements.txt"
    travail.mkdir(parents=True, exist_ok=True)
    uv("export", "--frozen", "--no-dev", "--no-emit-project", "--format", "requirements-txt", "-o", req, cwd=DEPOT, capture_output=True)
    installer = ["pip", "install", "--python", python, "--target", cible, "--no-deps", "-r", req]
    try:
        uv(*installer, "--offline", capture_output=True)
    except SystemExit:
        uv(*installer)
    shutil.rmtree(cible / "bin", ignore_errors=True)


def assembler(prog: Path):
    if prog.exists():
        if not (prog / MARQUE).is_file():
            raise SystemExit(f"{prog} existe et n'a pas été construit par cet outil : rien n'est effacé")
        shutil.rmtree(prog)
    prog.mkdir(parents=True)
    (prog / MARQUE).write_text(f"Fabrique {version()} assemblé par outils_dev/construire.py\n", encoding="utf-8")
    base = Path(sys.base_prefix)  # le vrai dossier de Python 3.12 (le venv du dépôt est bâti dessus, jamais sur la jonction d'uv : WinError 448)
    if not (base / "python312.dll").is_file():
        raise SystemExit(f"Python 3.12 introuvable ({base}) : lancer construire.py avec le Python du venv du dépôt")
    dire("runtime (Python + paquets de uv.lock sans le groupe dev)…")
    rt = prog / "runtime"
    shutil.copytree(base, rt, ignore=lambda d, noms: [n for n in noms if n == "__pycache__" or (Path(d) == base and n in ("Scripts", "include", "libs"))
                                                      or (Path(d) == base / "Lib" and n == "site-packages")])
    (rt / "Lib" / "site-packages").mkdir()
    (rt / "python312._pth").write_text(PTH, encoding="ascii")
    paquets(rt / "python.exe", rt / "Lib" / "site-packages", SORTIE / "travail")
    dire("app (fabrique\\ suivi par git, sans les tests)…")
    for f in ["pyproject.toml", *(f for f in suivis("fabrique") if not f.startswith("fabrique/tests/"))]:
        (prog / "app" / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(DEPOT / f, prog / "app" / f)
    (prog / "construction.json").write_text(json.dumps({"version": version(), "date": f"{date.today():%d/%m/%Y}", "licences": licences(prog)}, ensure_ascii=False, indent=1), encoding="utf-8")
    dire("précompilation…")
    compiler = [rt / "python.exe", "-m", "compileall", "-q", "-j", "0", "--invalidation-mode", "unchecked-hash"]
    lancer([*compiler, prog / "app"], capture_output=True)
    subprocess.run([str(c) for c in [*compiler, rt / "Lib"]], capture_output=True)  # quelques fichiers d'essai de paquets tiers ne se compilent pas : sans gravité
    lanceur(prog, SORTIE / "travail" / "lanceur")
    dire(f"assemblé : {prog} ({sum(f.stat().st_size for f in prog.rglob('*') if f.is_file()) / 1e6:.0f} Mo)")


def licences(prog: Path) -> list[dict]:
    """Ce qui est livré et sa licence (Qt et PySide6 : LGPL v3, bibliothèques livrées à part, non modifiées)."""
    lues = [{"nom": "Python", "version": platform.python_version(), "licence": "PSF-2.0"}]
    for meta in sorted((prog / "runtime" / "Lib" / "site-packages").glob("*.dist-info/METADATA"), key=lambda m: m.parent.name.lower()):
        h = HeaderParser().parsestr(meta.read_text(encoding="utf-8", errors="replace"))
        classe = [c.split("::")[-1].strip() for c in h.get_all("Classifier", []) if c.startswith("License ::")]
        libre = (h.get("License") or "").strip().splitlines()
        lues.append({"nom": h.get("Name", meta.parent.name), "version": h.get("Version", ""),
                     "licence": (h.get("License-Expression") or ", ".join(classe) or (libre[0] if libre else "") or "non indiquée")[:80]})
    return lues


def installateur(prog: Path, sortie: Path, bac: bool = False, numero: str | None = None) -> Path:
    """Compile installateur\\fabrique.iss sur le dossier assemblé ; `bac` : l'installateur d'essai ; `numero` : une version factice (essai de
    mise à jour, le pyproject.toml posé porte ce numéro)."""
    iscc = OUTILS / "innosetup" / "ISCC.exe"
    if not iscc.is_file():
        raise SystemExit(f"Inno Setup introuvable ({iscc})")
    v = numero or version()
    nom = f"Fabrique{' (bac à sable)' if bac else ''} {v} - Installation"
    travail = SORTIE / "travail" / "installateur"
    travail.mkdir(parents=True, exist_ok=True)
    sortie.mkdir(parents=True, exist_ok=True)
    script = travail / "fabrique.iss"
    script.write_text((DEPOT / "installateur" / "fabrique.iss").read_text(encoding="utf-8"), encoding="utf-8-sig")  # Inno Setup lit l'UTF-8 à sa marque
    definitions = {"VERSION": v, "PROGRAMME": prog, "SORTIE": sortie, "FICHIER": nom, "ICONE": ICONE, "MARQUE": MARQUE, "SIGNER": "1"}
    if bac:
        definitions["BAC"] = travail / "BAC_A_SABLE"
        definitions["BAC"].write_text("Installation d'essai (outils_dev/recette_installation.py) : autre identifiant, autre port, autre identité.\n", encoding="utf-8")
    if numero:
        definitions["PYPROJECT"] = travail / f"pyproject_{numero}.toml"
        definitions["PYPROJECT"].write_text((DEPOT / "pyproject.toml").read_text(encoding="utf-8").replace(f'version = "{version()}"', f'version = "{numero}"', 1), encoding="utf-8")
    dire(f"installateur « {nom}.exe »…")
    lancer([iscc, "/Qp", f'/Ssigner=$q{sys.executable}$q $q{DEPOT / "outils_dev" / "signer.py"}$q $f', *(f"/D{k}={val}" for k, val in definitions.items()), script],
           capture_output=True)
    return sortie / f"{nom}.exe"


def nouveautes(numero: str) -> list[str]:
    return json.loads((DEPOT / "fabrique" / "nouveautes.json").read_text(encoding="utf-8")).get(numero, [])


def publier(fichier: Path, dossier: Path, numero: str, textes: list[str]):
    """L'installateur dans un dossier « versions », décrit dans versions.json (lu par noyau/versions.py) ; seule la dernière version reste
    proposée, les plus anciennes sont rangées dans _old avec une note (on avance seulement)."""
    dossier.mkdir(parents=True, exist_ok=True)
    liste = dossier / "versions.json"
    connues = [v for v in (json.loads(liste.read_text(encoding="utf-8")) if liste.is_file() else []) if v["version"] != numero]
    shutil.copy(fichier, dossier / fichier.name)
    connues.append({"version": numero, "date": f"{date.today():%d/%m/%Y}", "fichier": fichier.name, "sha256": hashlib.sha256(fichier.read_bytes()).hexdigest(), "nouveautes": textes})
    connues.sort(key=lambda v: tuple(int(n) for n in v["version"].split(".")))
    for v in connues[:-1]:
        if (dossier / v["fichier"]).is_file():
            (dossier / "_old").mkdir(exist_ok=True)
            (dossier / "_old" / "NOTE.md").write_text("Anciens installateurs rangés par construire.py : plus proposés (on avance seulement). Ne pas les réinstaller.\n", encoding="utf-8")
            shutil.move(dossier / v["fichier"], dossier / "_old" / v["fichier"])
    liste.write_text(json.dumps(connues[-1:], ensure_ascii=False, indent=1), encoding="utf-8")
    dire(f"publié : {dossier / fichier.name} ({fichier.stat().st_size / 1e6:.0f} Mo)")


def menage(sortie: Path, numero: str):
    """Après une construction vérifiée : il ne reste que l'installateur de cette version, la preuve et les journaux."""
    for d in ("programme", "travail", "bac_installation"):
        shutil.rmtree(sortie / d, ignore_errors=True)
    for f in (sortie / "installateurs").glob("*.exe"):
        if f.name != f"Fabrique {numero} - Installation.exe":
            f.unlink()


def main():
    p = argparse.ArgumentParser(description="Construit Fabrique")
    p.add_argument("--vite", action="store_true", help="mise au point seulement : ni suite ni dépôt propre ; garde le programme assemblé")
    p.add_argument("--publier", action="store_true", help="pose l'installateur dans <studio>\\FABRIQUE\\versions")
    a = p.parse_args()
    if a.vite and a.publier:
        raise SystemExit("--publier refuse --vite : on ne livre que ce qui est vérifié")
    prog = SORTIE / "programme"
    if a.vite:
        dire("--vite : construction NON VALIDÉE (ni suite, ni dépôt propre)")
    else:
        depot_propre()
        dire("suite du dépôt (pytest)…")
        if tester.suite():
            raise SystemExit("la suite du dépôt n'est pas verte : rien n'est construit")
    assembler(prog)
    livre = installateur(prog, SORTIE / "installateurs")
    import recette_installation

    recette_installation.jouer(prog, SORTIE / "bac_installation", dire, preuve=None if a.vite else SORTIE / "recette_installation.json")
    if a.publier:
        if not nouveautes(version()):
            raise SystemExit(f"fabrique\\nouveautes.json ne dit rien de la version {version()} : rien n'est publié")
        publier(livre, VERSIONS, version(), nouveautes(version()))
    if not a.vite:
        menage(SORTIE, version())
    dire(f"Fabrique {version()} : {'assemblée (non validée)' if a.vite else 'construite et vérifiée'} — {livre}")


if __name__ == "__main__":
    main()
