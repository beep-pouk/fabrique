"""Les paroles d'une chanson (F5, J9) : mots des paroles par section et par ligne, calage sur ce que Whisper a entendu (difflib : les mots
retrouvés prennent leur heure, les autres sont placés entre leurs voisins, ou juste avant le premier et juste après le dernier retrouvé), bornes
des sections dans la chanson, sous-titres karaoké (ASS : le mot surligné quand il est chanté, libass de ffmpeg) et SRT par ligne. Partagé par
le faux chant, l'outil réel, le montage et le contrôle."""
import difflib
import json
import re
import unicodedata
from pathlib import Path
from statistics import median

AVANCE_S = 0.3  # une section commence un peu avant son premier mot chanté ; une ligne s'affiche un peu avant (AVANT_S) et reste un peu (APRES_S)
AVANT_S, APRES_S = 0.2, 0.3
COMPRIS_MIN = 0.5  # part des mots des paroles retrouvés par Whisper : en dessous, la chanson est refaite (autre graine), puis signalée


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
    """Le mot sans casse, sans accents ni ponctuation, pour toute écriture (cyrillique, arabe… : jamais réduit à l'ascii)."""
    d = unicodedata.normalize("NFKD", mot.lower())
    return re.sub(r"[^\w]", "", "".join(c for c in d if unicodedata.category(c) != "Mn")) or mot.lower()


def caler(paroles: list[dict], entendus: list[dict], total: float) -> tuple[list[dict], float]:
    """(mots des paroles avec debut et fin, part retrouvée) : `entendus` = [{mot, debut, fin}] de Whisper. Un mot non retrouvé est placé
    régulièrement entre ses voisins retrouvés ; avant le premier ou après le dernier retrouvé, il est collé à lui, à la durée médiane d'un mot
    (jamais étalé sur une intro ou une fin instrumentale) ; rien de retrouvé : tous répartis sur la chanson."""
    a, b = [norme(m["mot"]) for m in paroles], [norme(m["mot"]) for m in entendus]
    heures: dict[int, tuple[float, float]] = {}
    for bloc in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(bloc.size):
            e = entendus[bloc.b + k]
            heures[bloc.a + k] = (float(e["debut"]), max(float(e["debut"]), float(e["fin"])))
    if not heures:
        pas = total / max(1, len(paroles))
        return [{**m, "debut": round(i * pas, 3), "fin": round((i + 1) * pas, 3)} for i, m in enumerate(paroles)], 0.0
    duree = median(f - d for d, f in heures.values()) or 0.3
    cales, i = [], 0
    while i < len(paroles):
        if i in heures:
            cales.append({**paroles[i], "debut": round(heures[i][0], 3), "fin": round(heures[i][1], 3)})
            i += 1
            continue
        j = i
        while j < len(paroles) and j not in heures:
            j += 1
        if not cales:  # tête : juste avant le premier mot retrouvé
            apres = heures[j][0]
            avant = max(0.0, apres - (j - i) * duree)
        elif j == len(paroles):  # queue : juste après le dernier
            avant = cales[-1]["fin"]
            apres = min(total, avant + (j - i) * duree)
        else:
            avant, apres = cales[-1]["fin"], heures[j][0]
        pas = max(0.0, apres - avant) / (j - i)
        cales += [{**paroles[k], "debut": round(avant + (k - i) * pas, 3), "fin": round(avant + (k - i + 1) * pas, 3)} for k in range(i, j)]
        i = j
    return cales, len(heures) / len(paroles)


def bornes(sections: list[dict], mots: list[dict], total: float) -> list[dict]:
    """Début et fin de chaque section dans la chanson, bout à bout de 0 à `total` : une section chantée commence un peu avant son premier mot ;
    des sections sans paroles qui se suivent (intro, pont, fin) se partagent l'intervalle entre les mots d'avant et ceux d'après."""
    premiers, derniers = {}, {}
    for m in mots:
        premiers.setdefault(m["section"], m["debut"])
        derniers[m["section"]] = m["fin"]
    debuts: list[float | None] = [0.0 if not i else (max(0.0, premiers[s["id"]] - AVANCE_S) if s["id"] in premiers else None) for i, s in enumerate(sections)]
    i = 1
    while i < len(sections):
        if debuts[i] is not None:
            i += 1
            continue
        j = i
        while j < len(sections) and debuts[j] is None:
            j += 1
        a = derniers.get(sections[i - 1]["id"], debuts[i - 1])  # après les mots de la section d'avant
        b = debuts[j] if j < len(sections) else total
        a = min(max(a, debuts[i - 1]), b)
        debuts[i:j] = [a + (b - a) * (k - i) / (j - i) for k in range(i, j)]
        i = j
    for k in range(1, len(debuts)):  # jamais en arrière, jamais au-delà de la chanson
        debuts[k] = min(total, max(debuts[k], debuts[k - 1]))
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
    """Sous-titres karaoké : une ligne à la fois (affichée un peu avant d'être chantée, jamais par-dessus la suivante), chaque mot surligné au
    moment où il est chanté (\\k en centièmes, comptés depuis le début de la ligne : aucune dérive)."""
    t = lambda s: f"{int(s // 3600)}:{int(s // 60 % 60):02d}:{s % 60:05.2f}"  # noqa: E731
    cs = lambda s: round(s * 100)  # noqa: E731
    taille = round(hauteur / 14)
    texte = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {largeur}", f"PlayResY: {hauteur}", "", "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
             "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             f"Style: Karaoke,Segoe UI,{taille},&H0000D7FF,&H00FFFFFF,&H00202020,&H64000000,-1,0,0,0,100,100,0,0,1,{max(2, taille // 16)},1,2,60,60,{round(hauteur / 12)},1",
             "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    groupes, fin_avant = lignes(mots), 0.0
    for n, g in enumerate(groupes):
        debut = max(fin_avant, g[0]["debut"] - AVANT_S)
        suivante = groupes[n + 1][0]["debut"] - AVANT_S if n + 1 < len(groupes) else float("inf")
        fin = max(g[-1]["fin"], min(g[-1]["fin"] + APRES_S, suivante))
        heures = [m["debut"] for m in g] + [g[-1]["fin"]]
        k = [f"{{\\k{cs(g[0]['debut'] - debut)}}}"] + [f"{{\\k{max(1, cs(heures[i + 1] - debut) - cs(heures[i] - debut))}}}{echapper(m['mot'])} " for i, m in enumerate(g)]
        texte.append(f"Dialogue: 0,{t(debut)},{t(fin)},Karaoke,,0,0,0,,{''.join(k).strip()}")
        fin_avant = fin
    return "\n".join(texte) + "\n"


def echapper(mot: str) -> str:
    """Un mot des paroles tel quel à l'écran : ni commande ASS ({…}), ni retour à la ligne (\\N)."""
    return mot.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


if __name__ == "__main__":  # vérification rapide : python -m fabrique.moteur.paroles
    p = mots_du_texte([{"id": "i", "paroles": []}, {"id": "c", "paroles": ["Twinkle little star", "how I wonder"]}])
    c, part = caler(p, [{"mot": "twinkle", "debut": 1, "fin": 1.5}, {"mot": "star", "debut": 2, "fin": 2.5}, {"mot": "wonder", "debut": 4, "fin": 4.5}], 6)
    assert part == 0.5 and [x["debut"] for x in c] == [1, 1.5, 2, 2.5, 3.25, 4] and c[1]["fin"] == 2.0, c
    assert bornes([{"id": "i"}, {"id": "c"}], c, 6) == [{"id": "i", "debut": 0.0, "fin": 0.7}, {"id": "c", "debut": 0.7, "fin": 6}]
    a = ass(c, 1920, 1080)
    assert "Dialogue: 0,0:00:00.80,0:00:02.50,Karaoke,,0,0,0,,{\\k20}{\\k50}Twinkle {\\k50}little {\\k50}star" in a, a  # surligné à l'heure, sans chevauchement
    assert "Dialogue: 0,0:00:02.50,0:00:04.80" in a and len(segments(c)) == 2
    # tête et queue manquées : collées aux mots retrouvés, jamais étalées sur l'intro ou la fin ; deux sections muettes se partagent l'intervalle
    p = mots_du_texte([{"id": "a", "paroles": ["un deux trois"]}, {"id": "b", "paroles": []}, {"id": "c", "paroles": []}, {"id": "d", "paroles": ["quatre cinq"]}])
    c, _ = caler(p, [{"mot": "trois", "debut": 10, "fin": 10.5}, {"mot": "quatre", "debut": 20, "fin": 20.5}], 60)
    assert [x["debut"] for x in c] == [9.0, 9.5, 10, 20, 20.5] and c[-1]["fin"] == 21.0, c
    assert bornes([{"id": "x"}, {"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}], c, 60) == [
        {"id": "x", "debut": 0.0, "fin": 8.7}, {"id": "a", "debut": 8.7, "fin": 10.5}, {"id": "b", "debut": 10.5, "fin": 15.1},
        {"id": "c", "debut": 15.1, "fin": 19.7}, {"id": "d", "debut": 19.7, "fin": 60}]
    assert norme("Привет,") == "привет" and norme("Été!") == "ete" and echapper("{\\b1}") == "\\{\\\\b1\\}"
    print("ok")
