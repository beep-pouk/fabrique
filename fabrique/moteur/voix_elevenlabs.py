"""Voix ElevenLabs, outil en ligne payant de la brique voix (cahier § 4 ; plan § 5.5) : texte → son minuté, par l'API REST
(POST /v1/text-to-speech/<voix>/with-timestamps, son PCM 24 kHz en base64 et minutage de chaque caractère). Clé saisie par RT (Système →
Clés, « elevenlabs »), jamais affichée ni journalisée, jamais dans un message d'erreur. Prix de la fiche par 1 000 caractères ; le coût
réel se compte sur les caractères facturés (en-tête « x-character-count » quand le service le donne). Réglages de la fiche : « modele »,
« voix_id » (une voix du catalogue d'ElevenLabs), « adresse » (les tests la pointent sur un faux service local)."""
import base64
import json
import urllib.error
import urllib.request
import wave
from pathlib import Path

from fabrique.moteur.outils import Demande, Estimation, Fiche, Resultat
from fabrique.noyau import cles

ADRESSE = "https://api.elevenlabs.io/v1/text-to-speech/{voix}/with-timestamps?output_format=pcm_24000"
TAUX = 24000


def cout(fiche: Fiche, caracteres: int) -> float:
    return round(fiche.prix_unite_eur * caracteres / 1000, 4)


def estimer(fiche: Fiche, demande: Demande) -> Estimation:
    return Estimation(secondes=2 + len(demande.texte) / 50, cout_eur=cout(fiche, len(demande.texte)))


def mots(alignement: dict | None) -> list[dict]:
    """Les mots horodatés, tirés du minutage de chaque caractère (un mot = ce qui est entre deux blancs)."""
    if not alignement:
        return []
    liste, mot, debut, fin = [], "", 0.0, 0.0
    for c, d, f in zip(alignement["characters"], alignement["character_start_times_seconds"], alignement["character_end_times_seconds"]):
        if c.isspace():
            if mot:
                liste.append({"mot": mot, "debut": round(debut, 3), "fin": round(fin, 3)})
            mot = ""
            continue
        debut = d if not mot else debut
        mot, fin = mot + c, f
    if mot:
        liste.append({"mot": mot, "debut": round(debut, 3), "fin": round(fin, 3)})
    return liste


def fabriquer(fiche: Fiche, demande: Demande, dossier: Path) -> Resultat:
    cle = cles.lire("elevenlabs")
    if not cle:
        raise RuntimeError("clé ElevenLabs absente : RT la saisit dans Système → Clés")
    if not demande.texte.strip():
        raise RuntimeError("rien à dire : texte vide")
    r = fiche.reglages
    corps = {"text": demande.texte, "model_id": r.get("modele", "eleven_multilingual_v2"), "seed": demande.graine % 4294967296}
    requete = urllib.request.Request(r.get("adresse", ADRESSE).format(voix=r["voix_id"]), data=json.dumps(corps).encode("utf-8"), method="POST",
                                     headers={"xi-api-key": cle, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(requete, timeout=180) as rep:
            donnees, facture = json.load(rep), rep.headers.get("x-character-count")
    except urllib.error.HTTPError as e:
        detail = e.read(500).decode("utf-8", "replace").replace(cle, "…")
        raise RuntimeError(f"ElevenLabs a refusé ({e.code}) : {detail[:300]}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(f"ElevenLabs ne répond pas : {getattr(e, 'reason', e)}") from None
    son = base64.b64decode(donnees.get("audio_base64") or "")
    if len(son) < TAUX // 10:
        raise RuntimeError("ElevenLabs n'a rendu aucun son")
    sortie = dossier / "voix.wav"
    with wave.open(str(sortie), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAUX)
        w.writeframes(son)
    caracteres = int(facture) if facture and facture.isdigit() else len(demande.texte)
    return Resultat(fichiers=[sortie.name], duree_s=round(len(son) / 2 / TAUX, 3),
                    infos={"mots": mots(donnees.get("alignment")), "cout_eur": cout(fiche, caracteres), "caracteres": caracteres})
