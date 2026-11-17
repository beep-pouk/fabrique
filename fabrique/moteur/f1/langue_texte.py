"""J19 : texte d'une langue, sans Django. Score Whisper dans la langue (même mesure que controle_voix_wsl.py : ressemblance caractère à caractère,
mais normalisée pour chaque écriture : accents gardés, harakat arabes ôtés, japonais ramené en hiragana), durée dite estimée (pour l'alerte
« plus de 1,3 × l'anglaise ») et sous-titres SRT."""
import difflib
import re
import unicodedata

# Débit de la voix de Bramble (vitesse 0,85, très calme) : unités par seconde ; mots pour les langues à espaces, caractères pour ja / ko / zh.
DEBIT = {"en": ("mots", 2.3), "es": ("syll", 4.6), "pt-BR": ("syll", 4.4), "fr": ("syll", 4.5), "de": ("syll", 3.9), "it": ("syll", 4.6),
         "ja": ("car", 6.0), "ko": ("car", 4.6), "hi": ("syll", 4.2), "ar": ("syll", 3.9)}
VOYELLES = re.compile(r"[aeiouyàâäáãåèéêëíìîïóòôöõúùûüýœæ]+", re.I)
HARAKAT = re.compile(r"[ً-ْٰـ]")  # voyelles brèves, shadda, sukun, tatweel
DEVA_SYLL = re.compile(r"[अ-हक़-ॡ]")  # voyelles et consonnes (une syllabe environ chacune)
AR_SYLL = re.compile(r"[ء-ي]")


def _kana(t: str) -> str:
    try:
        import pykakasi
    except ImportError:  # shortcut: sans pykakasi, comparaison brute (kanji ≠ kana), installer pykakasi dans le venv qui contrôle
        return t
    return "".join(x["hira"] for x in pykakasi.kakasi().convert(t))


def normaliser(texte: str, langue: str) -> str:
    """Lettres seules, en minuscules, sans espaces ni ponctuation, dans une forme comparable entre le texte voulu et ce que Whisper a entendu."""
    t = unicodedata.normalize("NFKC", texte).lower().replace("-", " ")
    if langue == "ar":
        t = HARAKAT.sub("", t).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    if langue == "ja":
        t = _kana(t)
    return "".join(c for c in t if unicodedata.category(c)[0] in "LNM")


def score(voulu: str, entendu: str, langue: str) -> float:
    """1,0 = identique ; une phrase sautée, répétée ou mal dite fait baisser le score (seuil du contrôle : 0,93 en anglais)."""
    a, b = normaliser(voulu, langue), normaliser(entendu, langue)
    return round(difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 3) if a or b else 1.0


def unites(texte: str, langue: str) -> int:
    genre = DEBIT.get(langue, ("mots", 2.3))[0]
    if genre == "mots":
        return len(texte.split())
    if genre == "car":
        return sum(1 for c in texte if unicodedata.category(c)[0] in "LN")
    if langue == "hi":
        return len(DEVA_SYLL.findall(texte))
    if langue == "ar":
        return max(1, round(len(AR_SYLL.findall(texte)) * 0.75))  # consonnes écrites ≈ syllabes (voyelles brèves non écrites)
    return sum(len(VOYELLES.findall(m)) or 1 for m in texte.split())


def duree_dite(texte: str, langue: str) -> float:
    """Secondes estimées pour dire `texte` avec la voix de Bramble (pauses de fin de phrase non comprises)."""
    return round(unites(texte, langue) / DEBIT.get(langue, ("mots", 2.3))[1], 1)


def srt(scenes: list[dict]) -> str:
    """Sous-titres : une entrée par scène dite, de son début à la fin de sa voix (s['_debut'], s['_voix'] posés par le montage)."""
    def t(x):
        ms = round(x * 1000)
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    blocs, n = [], 0
    for s in scenes:
        if s.get("narration") and s.get("_voix"):
            n += 1
            blocs.append(f"{n}\n{t(s['_debut'])} --> {t(s['_debut'] + s['_voix'])}\n{s['narration'].strip()}\n")
    return "\n".join(blocs)


if __name__ == "__main__":  # auto-contrôle
    assert score("Bonsoir, je m'appelle Bramble.", "bonsoir je m appelle bramble", "fr") == 1.0
    assert score("مساءُ الخير", "مساء الخير", "ar") == 1.0
    assert score("こんばんは。ぼくの なまえは", "今晩は僕の名前は", "ja") > 0.7
    assert 2 < duree_dite("Buenas noches. Me llamo Bramble, y esta es mi linterna.", "es") < 6
    assert srt([{"narration": "A", "_debut": 0, "_voix": 1.5}, {"narration": "", "_debut": 2, "_voix": 0}]).startswith("1\n00:00:00,000 --> 00:00:01,500\nA")
    print("ok")
