"""Données fixes de la fenêtre (captures de référence, parcours) : les réponses du noyau, noms factices."""
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
    ("GET", "/api/sessions/s1/univers"): {"personnages": [{"nom": "Ami Un", "role": "ami", "statut": "actif", "references": 12}],
                                          "lieux": [{"nom": "La clairière", "description": "calme"}],
                                          "langues": [{"code": "en", "nom": "Anglais", "outil_voix": "", "voix_validee": True},
                                                      {"code": "xx", "nom": "Langue factice", "outil_voix": "outil_factice", "voix_validee": False}]},
    ("GET", "/api/cles"): [{"nom": "anthropic", "titre": "Assistant en ligne (Anthropic)", "ou": "absente", "ok": False},
                           {"nom": "gemini", "titre": "Gemini", "ou": "enregistrée", "ok": True},
                           {"nom": "ntfy", "titre": "Alertes sur le téléphone (ntfy)", "ou": "absente", "ok": False}],
}


class Transport:
    """Remplace le noyau : rend les réponses fixes et retient les actions demandées."""

    def __init__(self):
        self.actions = []

    def __call__(self, methode, chemin, corps=None):
        if methode == "POST":
            self.actions.append((chemin, corps))
            return {"message": f"fait : {chemin}"}
        return REPONSES[(methode, chemin)]
