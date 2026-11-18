"""Les paroles d'une chanson (F5, J9) : mots des paroles par section et par ligne, calage sur ce que Whisper a entendu (difflib : les mots
retrouvés prennent leur heure, les autres sont répartis entre leurs voisins), bornes des sections dans la chanson, sous-titres karaoké (ASS : le
mot surligné à son moment, libass de ffmpeg) et SRT par ligne. Partagé par le faux chant, l'outil réel et le montage."""
import difflib
import json
import re
import unicodedata
from pathlib import Path

AVANCE_S = 0.3  # une section commence un peu avant son premier mot chanté


def script_de(d) -> dict:
    """Le script de la vidéo dans la langue du morceau (sa traduction posée à côté, si elle existe)."""
    s = Path(d.script)
    if d.langue and (t := s.with_name(f"{s.stem}.{d.langue}.json")).is_file():
        s = t
    return json.loads(s.read_text(encoding="utf-8"))


def mots_du_texte(sections: list[dict]) -> list[dict]:
    """Chaque mot des paroles, avec sa section et sa ligne (rang dans la section)."""
    return [{"mot": m, "section": s["id"], "ligne": i} for s in sections for i, l in enumerate(s.get("paroles", [])) for m in l.split()]


def norme(mot: str) -> str:
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKD", mot.lower()).encode("ascii", "ignore").decode()) or mot.lower()


def caler(paroles: list[dict], entendus: list[dict], total: float) -> tuple[list[dict], float]:
    """(mots des paroles avec debut et fin, part retrouvée) : `entendus` = [{mot, debut, fin}] de Whisper ; un mot non retrouvé est placé
    entre ses voisins retrouvés (régulièrement), au début ou à la fin de la chanson s'il n'en a pas."""
    a, b = [norme(m["mot"]) for m in paroles], [norme(m["mot"]) for m in entendus]
    heures: dict[int, tuple[float, float]] = {}
    for bloc in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(bloc.size):
            e = entendus[bloc.b + k]
            heures[bloc.a + k] = (float(e["debut"]), float(e["fin"]))
    cales, i = [], 0
    while i < len(paroles):
        if i in heures:
            cales.append({**paroles[i], "debut": round(heures[i][0], 3), "fin": round(heures[i][1], 3)})
            i += 1
            continue
        j = i
        while j < len(paroles) and j not in heures:
            j += 1
        avant = cales[-1]["fin"] if cales else 0.0
        apres = heures[j][0] if j < len(paroles) else total
        pas = max(0.0, apres - avant) / (j - i)
        cales += [{**paroles[k], "debut": round(avant + (k - i) * pas, 3), "fin": round(avant + (k - i + 1) * pas, 3)} for k in range(i, j)]
        i = j
    return cales, (len(heures) / len(paroles) if paroles else 0.0)


def bornes(sections: list[dict], mots: list[dict], total: float) -> list[dict]:
    """Début et fin de chaque section dans la chanson, bout à bout de 0 à `total` : une section commence un peu avant son premier mot ; une
    section sans paroles (intro, fin) commence après les derniers mots de celle d'avant."""
    premiers, derniers = {}, {}
    for m in mots:
        premiers.setdefault(m["section"], m["debut"])
        derniers[m["section"]] = m["fin"]
    debuts = []
    for i, s in enumerate(sections):
        if not i:
            debuts.append(0.0)
        elif s["id"] in premiers:
            debuts.append(min(total, max(debuts[-1], premiers[s["id"]] - AVANCE_S)))
        else:
            debuts.append(min(total, max(debuts[-1], derniers.get(sections[i - 1]["id"], debuts[-1]))))
    return [{"id": s["id"], "debut": round(a, 3), "fin": round(b, 3)} for s, a, b in zip(sections, debuts, debuts[1:] + [total])]


def lignes(mots: list[dict]) -> list[list[dict]]:
    """Les mots groupés par ligne chantée, dans l'ordre."""
    groupes: list[list[dict]] = []
    for m in mots:
        if groupes and (groupes[-1][0]["section"], groupes[-1][0]["ligne"]) == (m["section"], m["ligne"]):
            groupes[-1].append(m)
        else:
            groupes.append([m])
    return groupes


def segments(mots: list[dict]) -> list[dict]:
    """Une ligne de sous-titres par ligne chantée (SRT de YouTube)."""
    return [{"start": g[0]["debut"], "end": g[-1]["fin"], "text": " ".join(m["mot"] for m in g)} for g in lignes(mots)]


def ass(mots: list[dict], largeur: int, hauteur: int) -> str:
    """Sous-titres karaoké : chaque ligne affichée pendant qu'elle est chantée, chaque mot surligné à son moment (\\k, en centièmes)."""
    t = lambda s: f"{int(s // 3600)}:{int(s // 60 % 60):02d}:{s % 60:05.2f}"  # noqa: E731
    taille = round(hauteur / 14)
    texte = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {largeur}", f"PlayResY: {hauteur}", "", "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
             "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             f"Style: Karaoke,Segoe UI,{taille},&H0000D7FF,&H00FFFFFF,&H00202020,&H64000000,-1,0,0,0,100,100,0,0,1,{max(2, taille // 16)},1,2,60,60,{round(hauteur / 12)},1",
             "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for g in lignes(mots):
        debut, k = g[0]["debut"], []
        for m in g:  # le blanc avant un mot compte dans sa durée : la ligne reste juste
            k.append(f"{{\\k{max(1, round((m['fin'] - debut) * 100))}}}{m['mot']} ")
            debut = m["fin"]
        texte.append(f"Dialogue: 0,{t(max(0.0, g[0]['debut'] - 0.2))},{t(g[-1]['fin'] + 0.3)},Karaoke,,0,0,0,,{''.join(k).strip()}")
    return "\n".join(texte) + "\n"


if __name__ == "__main__":  # vérification rapide : python -m fabrique.moteur.paroles
    p = mots_du_texte([{"id": "i", "paroles": []}, {"id": "c", "paroles": ["Twinkle little star", "how I wonder"]}])
    c, part = caler(p, [{"mot": "twinkle", "debut": 1, "fin": 1.5}, {"mot": "star", "debut": 2, "fin": 2.5}, {"mot": "wonder", "debut": 4, "fin": 4.5}], 6)
    assert part == 0.5 and [x["debut"] for x in c] == [1, 1.5, 2, 2.5, 3.25, 4] and c[1]["fin"] == 2.0, c
    assert bornes([{"id": "i"}, {"id": "c"}], c, 6) == [{"id": "i", "debut": 0.0, "fin": 0.7}, {"id": "c", "debut": 0.7, "fin": 6}]
    assert "{\\k50}Twinkle" in ass(c, 1920, 1080) and len(segments(c)) == 2
    print("ok")
