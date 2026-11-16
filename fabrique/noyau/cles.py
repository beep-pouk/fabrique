"""Clés (repris de Bramble Studio, core/cles.py) : saisies par RT dans Système, chiffrées par Windows (DPAPI, compte de l'utilisateur) et rangées
dans la base du noyau (réglage « cle_<nom> ») ; jamais affichées, jamais journalisées, illisibles dans une sauvegarde lue sur un autre PC."""
import base64
import os

from fabrique.garde import Refus
from fabrique.noyau.models import Parametre, noter

CLES = {"anthropic": "Assistant en ligne (Anthropic)", "gemini": "Gemini", "ntfy": "Alertes sur le téléphone (ntfy)"}
LONGUEUR_MAX = 500


def _dpapi(fonction: str, donnees: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Bloc(ctypes.Structure):
        _fields_ = [("taille", wintypes.DWORD), ("donnees", ctypes.POINTER(ctypes.c_char))]

    entree, sortie = Bloc(len(donnees), ctypes.cast(ctypes.create_string_buffer(donnees, len(donnees)), ctypes.POINTER(ctypes.c_char))), Bloc()
    if not getattr(ctypes.windll.crypt32, fonction)(ctypes.byref(entree), None, None, None, None, 1, ctypes.byref(sortie)):  # 1 : jamais de fenêtre
        raise OSError(f"{fonction} refusé par Windows")
    try:
        return ctypes.string_at(sortie.donnees, sortie.taille)
    finally:
        ctypes.windll.kernel32.LocalFree(sortie.donnees)


def chiffrer(texte: str) -> str:
    if os.name != "nt":
        raise OSError("les clés se chiffrent sous Windows seulement")
    return base64.b64encode(_dpapi("CryptProtectData", texte.encode("utf-8"))).decode("ascii")


def dechiffrer(valeur: str) -> str:
    """Vide quand Windows ne sait pas la lire (base venue d'un autre PC ou compte, valeur abîmée) : la clé est à ressaisir."""
    try:
        return _dpapi("CryptUnprotectData", base64.b64decode(valeur)).decode("utf-8") if os.name == "nt" else ""
    except (OSError, ValueError):
        return ""


def lire(nom: str) -> str:
    """La clé au moment de s'en servir ; vide sans clé. Ne pas l'afficher ni la journaliser."""
    v = Parametre.lire(f"cle_{nom}")
    return v and dechiffrer(v)


def enregistrer(nom: str, valeur: str, acteur: str) -> str:
    valeur = valeur.strip()
    if nom not in CLES:
        raise Refus(f"clé inconnue : {nom}")
    if not valeur or len(valeur) > LONGUEUR_MAX or len(valeur.split()) != 1:
        raise Refus(f"clé attendue : un seul mot, sans espace, {LONGUEUR_MAX} caractères au plus")
    try:
        Parametre.ecrire(f"cle_{nom}", chiffrer(valeur))
    except OSError as e:
        raise Refus(str(e)) from None
    noter(acteur, "cle_enregistree", nom=nom)  # jamais la valeur
    return f"Clé « {CLES[nom]} » enregistrée, chiffrée par Windows."


def etat() -> list[dict]:
    lignes = []
    for nom, titre in CLES.items():
        v = Parametre.lire(f"cle_{nom}")
        ou = "enregistrée" if v and dechiffrer(v) else "illisible sur ce PC : à ressaisir" if v else "absente"
        lignes.append({"nom": nom, "titre": titre, "ou": ou, "ok": ou == "enregistrée"})
    return lignes
