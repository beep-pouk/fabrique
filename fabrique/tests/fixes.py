"""Données fixes de la fenêtre (captures de référence, parcours) : les réponses du noyau, noms factices."""
from pathlib import Path

REFERENCE = str(Path(__file__).with_name("reference_factice.png"))  # une image dessinée par Qt, jamais une vraie
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
                            "progression": "3/9", "reste_s": 30600.0, "cout_eur": 0.0, "pret_vers": "01/12 18:40"},
                           {"id": 3, "titre": "La lune et le hibou", "session": "Session factice", "etat": "attente", "raison": "", "alertes": [], "acteur": "RT",
                            "progression": "0/9", "reste_s": 39600.0, "cout_eur": 0.0, "pret_vers": "02/12 16:40"},
                           {"id": 1, "titre": "Un essai", "session": "Essais", "etat": "erreur", "raison": "étape voix, vidéo : Fausse voix a échoué 3 fois — le service ne répond pas",
                            "alertes": ["étape voix, vidéo : Fausse voix a échoué 3 fois — le service ne répond pas"], "acteur": "claude", "progression": "0/9"}],
    ("GET", "/api/machine"): {"carte": "9 % · 2,3 / 16 Go", "disque_go": 85, "carte_prise": "une fabrication est déjà en cours"},
    ("GET", "/api/sessions"): [{"id": "s1", "nom": "Session factice", "dossier": "session_factice", "essais": False, "assistant": "fini", "videos": 12,
                                "derniere": "Le petit renard", "a_faire": 2, "prochain": "02/12 La lune et le hibou", "rendement": "1 234 vues sur 28 jours"},
                               {"id": "s3", "nom": "Comptines factices", "dossier": "comptines", "essais": False, "pause": True, "assistant": "5"},
                               {"id": "s2", "nom": "Essais", "dossier": "essais", "essais": True, "videos": 3, "derniere": "Un essai"}],
    ("GET", "/api/formats"): [{"id": "F1", "nom": "Histoire illustrée", "version": 2, "script": "scenario-bramble",
                               "etapes": [{"id": "voix", "brique": "voix", "par": "video"}, {"id": "images", "brique": "images", "par": "video"},
                                          {"id": "montage", "brique": "montage", "par": "video"}]},
                              {"id": "essai", "nom": "Recette d'essai", "version": 1, "script": "scenes-plans-narrateur",
                               "etapes": [{"id": "voix", "brique": "voix", "par": "plan"}, {"id": "montage", "brique": "montage", "par": "video"}]}],
    ("GET", "/api/modeles"): [{"nom": "Modèle factice", "fichier": "modele_factice.fabrique"}],
    ("GET", "/api/sessions/s1/reglages"): {
        "nom": "Session factice", "pause": False, "public": "enfants de 3 à 6 ans", "promesse": "une histoire calme avant de dormir", "style": "aquarelle douce",
        "difference": "un ami et un lieu différents à chaque histoire", "objectif": "1 000 abonnés", "arret": "moins de 50 vues après 20 vidéos", "format": "F1",
        "formats": ["F1"], "assistant": "fini", "plafond_eur": 0.0, "duree_min": 12.0, "duree_max": 18.0, "enfants": True, "declaration_ia": True,
        "ordre_strict": True, "langues": [{"code": "en", "nom": "Anglais"}, {"code": "xx", "nom": "Langue factice"}], "manque": []},
    ("GET", "/api/sessions/s1/idees"): [{"id": 1, "titre": "Le hérisson qui comptait les étoiles", "resume": "", "source": "claude", "statut": "nouvelle", "creee": "17/11/2026"}],
    ("GET", "/api/sessions/s1/historique"): [{"date": "18/11/2026 10:00", "acteur": "RT", "quoi": "référence profil.png importée pour « Ami Un » (à valider)"},
                                             {"date": "17/11/2026 21:00", "acteur": "claude", "quoi": "lieu « La clairière » ajouté"}],
    ("GET", "/api/calendrier"): [  # la requête (debut, fin, session) ne change pas la réponse fixe
        {"session": "s1", "session_nom": "Session factice", "code": "s1e00", "titre": "Le grand chêne", "date": "2026-11-30", "statut": "publiee", "statut_nom": "publiée", "pret_vers": ""},
        {"session": "s1", "session_nom": "Session factice", "code": "s1e01", "titre": "Le petit renard", "date": "2026-12-01", "statut": "fabrication", "statut_nom": "en fabrication",
         "pret_vers": "01/12 18:40"},
        {"session": "s1", "session_nom": "Session factice", "code": "s1e02", "titre": "La lune et le hibou", "date": "2026-12-02", "statut": "prete", "statut_nom": "prête", "pret_vers": ""},
        {"session": "s1", "session_nom": "Session factice", "code": "s1e03", "titre": "La pluie d'été", "date": "2026-12-04", "statut": "reportee", "statut_nom": "reportée", "pret_vers": ""},
        {"session": "s1", "session_nom": "Session factice", "code": "s1e04", "titre": "Le pont de bois", "date": "2026-12-08", "statut": "approuvee", "statut_nom": "approuvée", "pret_vers": ""},
        {"session": "s1", "session_nom": "Session factice", "code": "s1e05", "titre": "La première neige", "date": "", "statut": "idee", "statut_nom": "idée", "pret_vers": ""}],
    ("GET", "/api/sessions/s1/videos/v1/suivi"): [
        {"langue": "en", "statut": "planifiee", "titre": "Le petit renard | Histoire factice", "lien": "https://youtu.be/AAAAAAAAAAA", "vues": 1234, "heures": 40.5, "abonnes": 12,
         "jours": [{"date": f"{j:02d}/11", "vues": v} for j, v in zip(range(1, 18), (5, 40, 120, 160, 140, 110, 90, 85, 70, 66, 60, 58, 52, 50, 47, 41, 39))]}],
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
    ("GET", "/api/sessions/s1/scripts/s1e02"): {  # un script de forme voix-off (F4) : par plan, texte dit, consigne d'image, caméra
        "code": "s1e02", "titre": "La lune et le hibou", "statut": "scenario", "date_prevue": "2026-12-02",
        "versions": [{"numero": 1, "auteur": "claude", "date": "2026-11-18T10:00", "validee": True}],
        "contenu": {"titre": "La lune et le hibou", "scenes": [{"id": "s1", "plans": [
            {"id": "p1", "texte": "La lune se lève.", "image": "a full moon over a pond", "mouvement": "avancee"},
            {"id": "p2", "texte": "Le hibou ouvre les yeux.", "image": "an owl on a branch", "mouvement": "fixe"}]}]},
        "regles": {"erreurs": [], "avis": [], "mesures": {}}, "plans": [], "estimation": {"secondes": 600.0, "cout_eur": 0.0, "carte_go": 16}, "traductions": []},
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
         "non_repertorie": True, "creneau": "", "destination": "reliée", "chaine": "Chaîne factice", "fautes": [], "avis": [], "versions": 1, "lien": "", "envoi": "", "erreur": "",
         "variantes": [{"titre": "Le petit renard | Histoire factice", "miniature": "D:\Exemple\final\miniature.jpg", "note": 7.4, "raisons": ["contraste 0,80", "couleurs 0,62", "titre de 34 caractères"], "depuis": None, "portee": None},
                       {"titre": "Le renard et la lune", "miniature": "D:\Exemple\final\miniature_2.jpg", "note": 8.1, "raisons": ["contraste 0,90", "couleurs 0,73", "titre de 20 caractères"], "depuis": None, "portee": None}],
         "variante": 0, "proposition": None},
        {"id": 8, "langue": "xx", "statut": "brouillon", "titre": "Le petit renard (xx)", "description": "Une description factice.", "tags": [], "chapitres": [], "playlist": "",
         "playlist_titre": "", "video": "D:\\Exemple\\xx\\v.mp4", "miniature": "", "miniatures": [], "enfants": True, "ia": True, "non_repertorie": False,
         "creneau": "02/12/2026 18:30", "destination": "pas reliée", "chaine": "", "fautes": [], "avis": ["chaîne de la langue pas reliée : brouillon seulement, « Publier » refusé"],
         "versions": 1, "lien": "", "envoi": "", "erreur": "", "variantes": [], "variante": 0, "proposition": None}],
    ("GET", "/api/sessions/s1/videos/v1/paquets"): [
        {"publication": 7, "langue": "en", "reseau": "tiktok", "nom": "TikTok", "etat": "fait", "raison": "", "dossier": "D:\\Exemple\\paquets\\tiktok", "miniature": "miniature.jpg",
         "fichiers": [{"nom": "v_tiktok_partie_1.mp4", "largeur": 1080, "hauteur": 1920, "duree_s": 480.2, "poids_mo": 210.4},
                      {"nom": "v_tiktok_partie_2.mp4", "largeur": 1080, "hauteur": 1920, "duree_s": 470.8, "poids_mo": 205.1}],
         "textes": [{"titre": "", "texte": "Le petit renard (1/2)"}, {"titre": "", "texte": "Le petit renard (2/2)"}], "fautes": []},
        {"publication": 7, "langue": "en", "reseau": "snapchat", "nom": "Snapchat (Spotlight)", "etat": "impossible", "raison": "vidéo de 15.9 min : Snapchat (Spotlight) prend 1 min au plus — la déclinaison courte s'en chargera",
         "dossier": "D:\\Exemple\\paquets\\snapchat", "miniature": "", "fichiers": [], "textes": [{"titre": "", "texte": "Le petit renard"}], "fautes": []}],
}


def outil(id, nom, **plus):
    return {"id": id, "nom": nom, "local": True, "prix": "gratuit", "licence": "MIT", "credit": "", "besoins": "8 Go de carte, 0 Go de disque", "langues": "toutes",
            "limites": "", "version": "1.0", "etat": "en_service", "etat_nom": "en service", "installation": "rien à installer", "action": "", "simule": False,
            "defaut": False, "sessions": [], "dernier_banc": "", **plus}


BANCS = [{"id": 1, "brique": "Voix", "session": "Session factice", "video": "Le petit renard", "etat": "a_voter", "etat_nom": "à voter",
          "outils": "Voix locale A (en place) contre Voix locale B", "juge": "Whisper : le texte entendu comparé au texte voulu", "entrees": 3, "votes": 1, "verdict": "",
          "raison": "", "cree": "18/11/2026 11:00"},
         {"id": 2, "brique": "Images", "session": "Essais", "video": "Un essai", "etat": "fini", "etat_nom": "verdict rendu", "outils": "Images A (en place) contre Images B",
          "juge": "aucun", "entrees": 2, "votes": 2, "verdict": "Images B gagne (2 contre 0, 0 égalité(s))", "raison": "", "cree": "17/11/2026 22:00"}]
REPONSES.update({
    ("GET", "/api/outils"): {"installation": {}, "briques": [
        {"id": "voix", "titre": "Voix", "defaut": "voix_a", "juges": [{"id": "whisper", "titre": "Whisper : le texte entendu comparé au texte voulu"}], "outils": [
            outil("voix_a", "Voix locale A", defaut=True, dernier_banc="17/11/2026 : Voix locale A gagne (4 contre 1, 1 égalité(s))"),
            outil("voix_b", "Voix locale B", etat="candidat", etat_nom="candidat", installation="pas installé", action="installer", version="2.0", besoins="6 Go de carte, 4 Go de disque"),
            outil("voix_en_ligne", "Voix en ligne factice", local=False, prix="0,09 € / 1 000 caractères (prix du 2026-11-18)", licence="service payant",
                  besoins="0 Go de carte, 0 Go de disque", etat="candidat", etat_nom="candidat", limites="en ligne : clé de RT, plafond du mois")]},
        {"id": "images", "titre": "Images", "defaut": "images_a", "juges": [], "outils": [
            outil("images_a", "Images A", defaut=True),
            outil("images_vieilles", "Images d'avant", etat="retire", etat_nom="retiré", installation="version 1 installée", version="1")]}]},
    ("GET", "/api/depenses"): {"plafond_mois_eur": 2.0, "depense_mois_eur": 0.42, "lignes": [
        {"date": "18/11/2026 10:00", "session": "Essais", "outil": "voix_en_ligne", "estime_eur": 0.21, "reel_eur": 0.2},
        {"date": "17/11/2026 21:00", "session": "Essais", "outil": "voix_en_ligne", "estime_eur": 0.22, "reel_eur": None}]},
    ("GET", "/api/veille"): [
        {"id": 1, "date": "01/11/2026", "brique": "voix", "nom": "Voix candidate factice", "source": "https://exemple.org/voix", "licence": "Apache 2.0", "commercial": True,
         "besoins": "6 Go de carte", "avis": "annonce une voix plus calme ; à passer au banc", "statut": "nouveau", "statut_nom": "nouveau"},
        {"id": 2, "date": "01/11/2026", "brique": "animation", "nom": "Animation factice", "source": "", "licence": "non commerciale", "commercial": False,
         "besoins": "30 Go de carte", "avis": "", "statut": "ecarte", "statut_nom": "écarté"}],
    ("GET", "/api/bancs"): BANCS,
    ("GET", "/api/bancs/1"): {**BANCS[0], "gagnant": "", "adopte": "", "peut_adopter": False, "lignes": [
        {"n": 0, "texte": "Un petit renard dort sous une fougère.", "langue": "en", "gauche": [r"D:\Exemple\bancs\1\0\a\voix.wav"],
         "droite": [r"D:\Exemple\bancs\1\0\b\voix.wav"], "vote": "droite", "notes": None, "qui": None},
        {"n": 1, "texte": "La lune monte.", "langue": "en", "gauche": [r"D:\Exemple\bancs\1\1\b\voix.wav"], "droite": [r"D:\Exemple\bancs\1\1\a\voix.wav"],
         "vote": "", "notes": None, "qui": None},
        {"n": 2, "texte": "Bonne nuit.", "langue": "en", "gauche": [r"D:\Exemple\bancs\1\2\a\voix.wav"], "droite": [r"D:\Exemple\bancs\1\2\b\voix.wav"],
         "vote": "", "notes": None, "qui": None}]},
    ("GET", "/api/bancs/2"): {**BANCS[1], "gagnant": "Images B", "adopte": "", "peut_adopter": True, "lignes": [
        {"n": 0, "texte": "A small fox sleeps under a fern.", "langue": "", "gauche": [REFERENCE], "droite": [REFERENCE], "vote": "gauche",
         "notes": None, "qui": {"gauche": "Images B", "droite": "Images A"}},
        {"n": 1, "texte": "The moon rises over a quiet pond.", "langue": "", "gauche": [REFERENCE], "droite": [REFERENCE], "vote": "droite",
         "notes": None, "qui": {"gauche": "Images A", "droite": "Images B"}}]},
    ("GET", "/api/statistiques"): {  # J11
        "sessions": [{"id": "s1", "nom": "Histoires factices", "videos": 4, "publiees": 3, "vues": 1834, "heures": 52.5, "carte_h": 6.0, "rt_min": 95.0,
                      "depenses_eur": 1.5, "revenu_eur": None, "par_heure_carte": 8.75, "par_minute_rt": 0.553}],
        "ensuite": [{"session": "Histoires factices", "session_id": "s1", "format": "F1", "langue": "en", "videos": 3, "recentes": 1, "heures": 52.5, "carte_h": 6.0,
                     "rt_min": 95.0, "revenu_eur": None, "par_heure_carte": 8.75, "par_minute_rt": 0.553, "assez": True},
                    {"session": "Histoires factices", "session_id": "s1", "format": "F1", "langue": "xx", "videos": 1, "recentes": 0, "heures": 2.0, "carte_h": 1.0,
                     "rt_min": 0.0, "revenu_eur": None, "par_heure_carte": 2.0, "par_minute_rt": None, "assez": False}]},
    ("GET", "/api/sessions/s1/statistiques"): {
        "videos": [{"id": "v1", "titre": "Le petit renard", "format": "F1", "langues": ["en"], "publiee_le": "01/11/2026", "vues": 1234, "heures": 40.5, "abonnes": 12,
                    "retention": 41.0, "impressions": 20000, "ctr": 5.2, "carte_h": 2.0, "rt_min": 35.0, "depenses_eur": 0.0, "revenu_eur": None,
                    "par_heure_carte": 20.25, "par_minute_rt": 1.157, "publications": [{"id": 7, "langue": "en", "revenu_eur": None}]}],
        "destinations": [{"langue": "en", "reseau": "youtube", "chaine": "Chaîne factice", "vues": 1834, "heures": 52.5, "abonnes": 20, "retention": 40.0,
                          "impressions": 30000, "ctr": 5.0, "vues_28j": 900, "heures_28j": 20.0,
                          "jours": [{"date": f"{j:02d}/11", "vues": v} for j, v in zip(range(1, 8), (5, 40, 120, 160, 140, 110, 90))]}]},
})


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
            if chemin == "/api/sessions":
                return {"message": "Session « Nouvelle factice » créée.", "id": "s1"}
            return {"message": f"fait : {chemin}"}
        return REPONSES[(methode, chemin.split("?")[0])]
