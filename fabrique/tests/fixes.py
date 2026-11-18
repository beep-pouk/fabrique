"""Données fixes de la fenêtre (captures de référence, parcours) : les réponses du noyau, noms factices."""
from pathlib import Path

REFERENCE = str(Path(__file__).with_name("reference_factice.png"))  # une image dessinée par Qt (tests/test_fenetre.py), jamais une vraie
REPONSES = {
    ("GET", "/api/sante"): {"nom": "Fabrique (développement)", "version": "0.1.0", "mode": "simulation", "appelant": "fenetre", "pid": 1},
    ("GET", "/api/sauvegardes"): {
        "dossier": r"D:\Exemple\SAUVEGARDES\fabrique",
        "liste": [{"nom": "fabrique_2026-11-15_23h30m00.zip", "date": "15/11/2026 23:30", "taille_mo": 1.2},
                  {"nom": "fabrique_2026-11-14_23h30m00.zip", "date": "14/11/2026 23:30", "taille_mo": 1.1}],
        "derniere": {"etat": "faite", "fin": "2026-11-15T23:30:41", "fichier": "fabrique_2026-11-15_23h30m00.zip", "taille_mo": 1.2}},
    ("GET", "/api/versions"): {"installee": "0.1.0", "proposee": "0.1.1", "nouveautes": ["Une nouveauté d'exemple."], "raison": ""},
    ("GET", "/api/journal"): [{"date": "2026-11-15 22:10:00", "niveau": "à surveiller", "source": "noyau", "message": "exemple d'avertissement"}],
    ("GET", "/api/file"): [{"id": 2, "titre": "Le petit renard", "session": "Session factice", "etat": "en_cours", "raison": "", "alertes": [], "acteur": "RT",
                            "progression": "3/9"},
                           {"id": 3, "titre": "La lune et le hibou", "session": "Session factice", "etat": "attente", "raison": "", "alertes": [], "acteur": "RT",
                            "progression": "0/9"},
                           {"id": 1, "titre": "Un essai", "session": "Essais", "etat": "erreur", "raison": "étape voix, vidéo : Fausse voix a échoué 3 fois — le service ne répond pas",
                            "alertes": ["étape voix, vidéo : Fausse voix a échoué 3 fois — le service ne répond pas"], "acteur": "claude", "progression": "0/9"}],
    ("GET", "/api/machine"): {"carte": "9 % · 2,3 / 16 Go", "disque_go": 85, "carte_prise": "une fabrication est déjà en cours"},
    ("GET", "/api/sessions"): [{"id": "s1", "nom": "Session factice", "dossier": "session_factice", "essais": False},
                               {"id": "s2", "nom": "Essais", "dossier": "essais", "essais": True}],
    ("GET", "/api/sessions/s1/scripts"): [{"code": "s1e01", "titre": "Le petit renard", "statut": "scenario", "date_prevue": "2026-12-01", "versions": 2, "validee": True},
                                          {"code": "s1e02", "titre": "La lune et le hibou", "statut": "scenario", "date_prevue": "2026-12-02", "versions": 1, "validee": True}],
    ("GET", "/api/sessions/s1/videos"): [{"id": "v1", "titre": "Le petit renard", "nom": "2026-12-01-s1e01", "recette": "F1 v1", "progression": "3/9", "erreurs": 0}],
    ("GET", "/api/sessions/s1/videos/v1"): {
        "id": "v1", "titre": "Le petit renard", "nom": "2026-12-01-s1e01", "recette": "F1 v1",
        "etapes": [{"id": "voix", "brique": "voix", "finis": 1, "total": 1, "erreur": "", "outils": ["f1_voix"], "secondes": 840.0},
                   {"id": "images", "brique": "images", "finis": 0, "total": 1, "erreur": "", "outils": ["f1_images"], "secondes": 0.0},
                   {"id": "anim", "brique": "animation", "finis": 0, "total": 1, "erreur": "étape anim : ComfyUI n'a pas démarré", "outils": ["f1_animation"], "secondes": 0.0}],
        "plans": [{"n": 1, "image": "A small fox sleeps under a fern.", "scenes": [1, 2], "bramble": False},
                  {"n": 3, "image": "", "scenes": [3], "bramble": True},
                  {"n": 4, "image": "The moon rises over a quiet pond.", "scenes": [4], "bramble": False}],
        "script": {"title": "Le petit renard", "scenes": [{"id": 1, "narration": "Un petit renard dort."}, {"id": 3, "narration": "Bonne nuit.", "bramble": "accueil"}]},
        "controle": {"mesure": True, "note": 5.7, "video": "", "defauts": [
            {"debut": 1.5, "fin": None, "texte": "image figée 4.0 s", "source": "analyser_video", "gravite": "moyenne"},
            {"debut": 20.0, "fin": 40.0, "texte": "0020.0 : Qwen 3.5/10 (seuil 6) une patte glisse", "source": "Qwen", "gravite": "forte"},
            {"debut": None, "fin": None, "texte": "volume global -20.1 LUFS (cible -14)", "source": "analyser_video", "gravite": "legere"}]}},
    ("GET", "/api/sessions/s1/scripts/s1e01"): {
        "code": "s1e01", "titre": "Le petit renard", "statut": "scenario", "date_prevue": "2026-12-01",
        "versions": [{"numero": 2, "auteur": "RT", "date": "2026-11-16T21:00", "validee": True}, {"numero": 1, "auteur": "import", "date": "2026-11-10T21:00", "validee": True}],
        "contenu": {"title": "Le petit renard", "scenes": [{"id": 1, "narration": "Un petit renard dort sous une fougère.", "image": "A small fox sleeps under a fern."},
                                                           {"id": 2, "narration": "Bonne nuit, petit renard.", "bramble": "accueil"}]},
        "regles": {"erreurs": [], "avis": [["S-12", "une phrase un peu longue en scène 1"]], "mesures": {}},
        "plans": [{"n": 1, "image": "A small fox sleeps under a fern.", "scenes": [1], "bramble": False}, {"n": 2, "image": "", "scenes": [2], "bramble": True}],
        "estimation": {"secondes": 41400.0, "cout_eur": 0.0, "carte_go": 16}, "traductions": ["xx"]},
    ("GET", "/api/sessions/s1/univers"): {
        "personnages": [{"id": 1, "nom": "Ami Un", "role": "ami", "statut": "actif", "description": "un petit renard roux", "licence": "image générée", "credit": "",
                         "references": [{"id": 1, "chemin": REFERENCE, "vue": "face", "source": "gemini", "validee": True, "licence": "", "credit": ""},
                                        {"id": 2, "chemin": REFERENCE, "vue": "profil", "source": "RT", "validee": False, "licence": "", "credit": ""}]},
                        {"id": 2, "nom": "Ami Deux", "role": "ami", "statut": "absent", "description": "", "licence": "", "credit": "", "references": []}],
        "lieux": [{"id": 1, "nom": "La clairière", "description": "calme", "licence": "", "credit": ""}],
        "ressources": [{"id": 1, "type": "musique", "nom": "Berceuse factice", "outil": "outil_musique", "licence": "licence factice", "credit": "Compositeur Factice"}],
        "langues": [{"code": "en", "nom": "Anglais", "outil_voix": "", "voix_validee": True},
                    {"code": "xx", "nom": "Langue factice", "outil_voix": "outil_factice", "voix_validee": False}],
        "style": "aquarelle douce, couleurs de fin de journée"},
    ("GET", "/api/cles"): [{"nom": "anthropic", "titre": "Assistant en ligne (Anthropic)", "ou": "absente", "ok": False},
                           {"nom": "gemini", "titre": "Gemini", "ou": "enregistrée", "ok": True},
                           {"nom": "ntfy", "titre": "Alertes sur le téléphone (ntfy)", "ou": "absente", "ok": False}],
    ("GET", "/api/etat"): {"heure": "2026-11-18T10:00", "version": "0.1.0", "mode": "simulation", "noyau": {"pid": 1, "port": 8800}, "sessions": ["Session factice", "Essais"],
                           "file": {}, "sauvegarde": {}, "releve": {"etat": "fait", "fin": "2026-11-18T09:00:12"}, "alertes": [], "texte": []},
    ("GET", "/api/telephone/appareils"): [{"id": "0123456789ab", "appareil": "iPhone", "depuis": "17/11/2026 21:00", "expire": "17/11/2027"}],
    ("GET", "/api/sessions/s1/destinations"): [
        {"langue": "en", "reseau": "youtube", "etat": "reliée", "reliee": True, "chaine": "Chaîne factice", "chaine_id": "UCfaux", "depuis": "17/11/2026 21:00",
         "playlists": [{"id": "PLun", "titre": "Histoires du renard"}, {"id": "PLdeux", "titre": "Histoires du hibou"}]},
        {"langue": "xx", "reseau": "youtube", "etat": "pas reliée", "reliee": False, "chaine": "", "chaine_id": "", "depuis": "", "playlists": []}],
    ("GET", "/api/sessions/s1/videos/v1/publications"): [
        {"id": 7, "langue": "en", "statut": "brouillon", "titre": "Le petit renard | Histoire factice", "description": "Un petit renard cherche la lune.\n\n00:00 Le terrier\n01:10 La forêt\n02:30 La lune",
         "tags": ["renard"], "chapitres": ["00:00 Le terrier", "01:10 La forêt", "02:30 La lune"], "playlist": "PLun", "playlist_titre": "Histoires du renard",
         "video": "D:\\Exemple\\final\\v.mp4", "miniature": "D:\\Exemple\\final\\miniature.jpg", "miniatures": ["miniature.jpg", "miniature_2.jpg"], "enfants": True, "ia": True,
         "non_repertorie": True, "creneau": "", "destination": "reliée", "chaine": "Chaîne factice", "fautes": [], "avis": [], "versions": 1, "lien": "", "envoi": "", "erreur": ""},
        {"id": 8, "langue": "xx", "statut": "brouillon", "titre": "Le petit renard (xx)", "description": "Une description factice.", "tags": [], "chapitres": [], "playlist": "",
         "playlist_titre": "", "video": "D:\\Exemple\\xx\\v.mp4", "miniature": "", "miniatures": [], "enfants": True, "ia": True, "non_repertorie": False,
         "creneau": "02/12/2026 18:30", "destination": "pas reliée", "chaine": "", "fautes": [], "avis": ["chaîne de la langue pas reliée : brouillon seulement, « Publier » refusé"],
         "versions": 1, "lien": "", "envoi": "", "erreur": ""}],
    ("GET", "/api/sessions/s1/videos/v1/paquets"): [
        {"publication": 7, "langue": "en", "reseau": "tiktok", "nom": "TikTok", "etat": "fait", "raison": "", "dossier": "D:\\Exemple\\paquets\\tiktok", "miniature": "miniature.jpg",
         "fichiers": [{"nom": "v_tiktok_partie_1.mp4", "largeur": 1080, "hauteur": 1920, "duree_s": 480.2, "poids_mo": 210.4},
                      {"nom": "v_tiktok_partie_2.mp4", "largeur": 1080, "hauteur": 1920, "duree_s": 470.8, "poids_mo": 205.1}],
         "textes": [{"titre": "", "texte": "Le petit renard (1/2)"}, {"titre": "", "texte": "Le petit renard (2/2)"}], "fautes": []},
        {"publication": 7, "langue": "en", "reseau": "snapchat", "nom": "Snapchat (Spotlight)", "etat": "impossible", "raison": "vidéo de 15.9 min : Snapchat (Spotlight) prend 1 min au plus — la déclinaison courte s'en chargera",
         "dossier": "D:\\Exemple\\paquets\\snapchat", "miniature": "", "fichiers": [], "textes": [{"titre": "", "texte": "Le petit renard"}], "fautes": []}],
}


class Transport:
    """Remplace le noyau : rend les réponses fixes et retient les actions demandées."""

    def __init__(self):
        self.actions = []

    def __call__(self, methode, chemin, corps=None):
        if methode == "POST":
            self.actions.append((chemin, corps))
            if chemin.endswith("/controler"):  # les règles d'un brouillon : une erreur si « interdit » y est écrit
                return {"erreurs": [["R-1", "mot interdit"]] if "interdit" in str(corps) else [], "avis": [], "mesures": {}}
            if chemin == "/api/telephone/code":
                return {"code": "123456", "expire": "21:05"}
            if chemin.endswith("/relier"):  # sans adresse : la fenêtre n'ouvre rien pendant les tests
                return {"message": "La page de Google est ouverte dans le navigateur.", "url": ""}
            return {"message": f"fait : {chemin}"}
        return REPONSES[(methode, chemin)]
