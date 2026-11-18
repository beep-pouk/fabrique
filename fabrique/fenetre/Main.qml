// La coquille de Fabrique : navigation, Accueil (mur des sessions, à faire, file, machine), Sessions (calendrier et idées, vidéos, scripts et
// « Fabriquer », univers, formats, destinations, règles), nouvelle session pas à pas, File, Outils (fiches, installation, dépenses, veille),
// Banc (à l'aveugle), Système (sauvegardes, mises à jour, mode, journal, téléphone, clés).
// Jetons de style du plan technique § 6.2. Aucune règle ici : tout vient du noyau par « pont » (main.py).
import QtQuick
import QtQuick.Controls.Basic
import QtMultimedia

Window {
    id: f
    width: 1280; height: 800; minimumWidth: 960; minimumHeight: 600
    title: pont.titre; color: cFond

    readonly property color cFond: "#0E1014"
    readonly property color cPanneau: "#161A21"
    readonly property color cLeve: "#1D222B"
    readonly property color cTrait: "#2A303B"
    readonly property color cTexte: "#E8EAF0"
    readonly property color cSecond: "#9AA3B2"
    readonly property color cAccent: "#F2A93B"
    readonly property color cSelection: "#3B82F6"
    readonly property color cReussi: "#3CCB7F"
    readonly property color cAttention: "#F5C04E"
    readonly property color cDefaut: "#F0564A"

    property string ecran: "accueil"
    property var sante: ({version: ""})
    property var sauvegardes: ({dossier: "", liste: [], derniere: {}})
    property var versions: ({installee: "", proposee: null, nouveautes: [], raison: ""})
    property var journal: []
    property var cles: []
    property string message: ""
    property bool messageOk: true
    property string aRestaurer: ""
    property var file: []
    property var machine: ({carte: "", disque_go: 0, carte_prise: ""})
    property var sessions: []
    property string session: ""
    property string onglet: "scripts"
    property var scripts: []
    property var videos: []
    property var univers: ({personnages: [], lieux: [], ressources: [], langues: [], style: ""})
    property string aFabriquer: ""
    readonly property var videoVide: ({id: "", titre: "", nom: "", recette: "", etapes: [], plans: [], script: {}, controle: {mesure: false, controles: [], note: null, defauts: [], video: ""}})
    property var video: videoVide
    property string ongletVideo: "fabrication"
    property var coches: []
    property bool liberer: false  // « Refaire » envoyé : le lecteur lâche la vidéo (Windows refuse de déplacer un fichier ouvert)
    property var script: ({code: "", titre: "", date_prevue: "", versions: [], contenu: {}, regles: {}, plans: [], estimation: {secondes: 0, cout_eur: 0}, traductions: []})
    property var langues: []
    property var publications: []  // l'aperçu de chaque langue de la vidéo ouverte (approuvée)
    property var paquets: []
    property var destinations: []
    property var appareils: []
    property var etat: ({releve: {}})
    property var code_telephone: ({code: "", expire: "", adresse: ""})
    property var formats: []  // le catalogue
    property var modeles: []
    property var calendrier: []
    property var idees: []
    property var historique: []
    property var suivi: []
    readonly property var reglagesVides: ({nom: "", pause: false, public: "", promesse: "", style: "", difference: "", objectif: "", arret: "", format: "", formats: [],
                                           assistant: "", plafond_eur: 0, duree_min: null, duree_max: null, enfants: true, declaration_ia: true, ordre_strict: true,
                                           langues: [], manque: []})
    property var reglages: reglagesVides
    property var nouvelle: ({etape: 1})  // l'assistant de la nouvelle session (étapes 1 à 7) ; la session créée devient la session choisie
    property string modeleChoisi: ""
    property string vueCal: "mois"  // mois, semaine
    property bool calTout: false  // le calendrier de toutes les sessions
    property string calJour: ""  // AAAA-MM-JJ dans la période montrée ; vide : aujourd'hui
    property string jourFixe: ""  // captures de référence : un « aujourd'hui » fixe
    property var aPartager: ({type: "", pk: -1})
    property string reglagesDe: ""  // la session dont les champs des règles et de l'assistant ont été remplis
    property string universDe: ""
    property bool aChangerMode: false  // « Passer en mode réel » attend la confirmation
    property var outils: ({briques: [], installation: {}})
    property var depenses: ({plafond_mois_eur: 0, depense_mois_eur: 0, lignes: []})
    property bool plafondRempli: false
    property var veille: []
    property var bancs: []
    readonly property var bancVide: ({id: 0, brique: "", session: "", video: "", etat: "", etat_nom: "", outils: "", juge: "", entrees: 0, votes: 0, verdict: "", raison: "",
                                      lignes: [], gagnant: "", adopte: "", peut_adopter: false})
    property var banc: bancVide
    property int ligneBanc: 0  // l'entrée que G, E et D votent
    property bool bancOuvert: false  // le banc vient d'être ouvert : G, E et D partent de sa première entrée sans vote
    property var nouveauBanc: ({brique: "", outil: "", video: "", juge: ""})
    property var relier: ({url: "", message: ""})
    property int aPublier: -1  // la publication dont « Publier » attend la confirmation
    property var brouillon: null  // le script en cours d'écriture (copie du contenu) ; null : lecture
    property var brouillons: ({})  // les brouillons des autres scripts ouverts entre-temps : jamais perdus sans « Abandonner »
    property var controler: ({erreurs: [], avis: [], mesures: {}})  // les règles du brouillon, rejouées pendant la frappe
    readonly property var etats: ({attente: "en attente", en_cours: "en cours", pause: "en pause", finie: "finie", erreur: "en erreur", annulee: "annulée"})
    readonly property string mono: Qt.fontFamilies().indexOf("Cascadia Mono") >= 0 ? "Cascadia Mono" : "Consolas"

    function recharger() {
        ["sante", "sauvegardes", "versions", "journal", "cles", "file", "machine", "sessions", "etat", "appareils", "formats", "modeles", "outils", "depenses", "veille",
         "bancs"].forEach(n => pont.charger(n))
        if (ecran === "banc" && banc.id > 0) pont.lire("banc", {id: banc.id})
        if (session !== "") ["scripts", "videos", "univers", "destinations", "reglages", "idees", "historique"].forEach(n => pont.lire(n, {id: session}))
        if (ecran === "sessions" && onglet === "calendrier") chargerCal()
        if (ecran === "video" && video.id !== "") ["video", "publications", "paquets", "suivi"].forEach(n => pont.lire(n, {id: session, video: video.id}))
        if (ecran === "script" && script.code !== "") pont.lire("script", {id: session, code: script.code})
    }
    function ouvrirOnglet(id) { onglet = id; defileSession.contentY = 0; if (id === "calendrier") chargerCal() }
    function rafraichir() {  // un événement du noyau (un morceau fini, une sauvegarde…) : ce qui bouge seul, jamais les champs que RT remplit
        ["file", "machine", "sessions", "etat", "outils", "bancs"].forEach(n => pont.charger(n))
        if (ecran === "banc" && banc.id > 0) pont.lire("banc", {id: banc.id})
        if (ecran === "video" && video.id !== "") ["video", "publications", "paquets", "suivi"].forEach(n => pont.lire(n, {id: session, video: video.id}))
        if (ecran === "sessions" && onglet === "videos") pont.lire("videos", {id: session})
        if (ecran === "sessions" && onglet === "calendrier") chargerCal()
    }
    function remplir() {  // les champs des règles et de l'assistant, une fois par session
        reglagesDe = session
        rDiff.texte = nDiff.texte = reglages.difference; rPublic.texte = nPublic.texte = reglages.public; rPromesse.texte = nPromesse.texte = reglages.promesse
        rObjectif.texte = nObjectif.texte = reglages.objectif; rArret.texte = nArret.texte = reglages.arret; nStyle.texte = reglages.style
        rMin.texte = nMin.texte = reglages.duree_min != null ? String(reglages.duree_min).replace(".", ",") : ""
        rMax.texte = nMax.texte = reglages.duree_max != null ? String(reglages.duree_max).replace(".", ",") : ""
        rPlafond.texte = nPlafond.texte = String(reglages.plafond_eur || 0).replace(".", ",")
        if (nouvelle.id) { nNom.texte = reglages.nom; nLangues.texte = reglages.langues.map(l => l.code).join(", ") }
    }
    function choisir(id) { if (id !== session) { reglages = reglagesVides; reglagesDe = ""; universDe = "" }; session = id; aFabriquer = ""; aPartager = {type: "", pk: -1}; recharger() }
    function deux(n) { return String(n).padStart(2, "0") }
    function iso(d) { return d.getFullYear() + "-" + deux(d.getMonth() + 1) + "-" + deux(d.getDate()) }
    function jourDe(s) { var p = s.split("-"); return new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2])) }
    function aujourdhui() { return jourFixe || iso(new Date()) }
    function lundi(d) { var x = new Date(d); x.setDate(x.getDate() - (x.getDay() + 6) % 7); return x }
    function debutCal() { var d = jourDe(calJour || aujourdhui()); return lundi(vueCal === "mois" ? new Date(d.getFullYear(), d.getMonth(), 1) : d) }
    function joursCal() {  // 6 semaines (mois) ou 7 jours (semaine), du lundi
        var d = debutCal(), mois = jourDe(calJour || aujourdhui()).getMonth(), liste = []
        for (var i = 0; i < (vueCal === "mois" ? 42 : 7); i++) {
            var x = new Date(d); x.setDate(d.getDate() + i)
            liste.push({iso: iso(x), jour: x.getDate(), dedans: vueCal === "semaine" || x.getMonth() === mois})
        }
        return liste
    }
    function chargerCal() { var j = joursCal(); pont.lire("calendrier", {debut: j[0].iso, fin: j[j.length - 1].iso, session: calTout ? "" : session}) }
    function deplacerCal(sens) {
        var d = jourDe(calJour || aujourdhui())
        if (vueCal === "mois") d = new Date(d.getFullYear(), d.getMonth() + sens, 1); else d.setDate(d.getDate() + 7 * sens)
        calJour = iso(d); chargerCal()
    }
    function titreCal() {
        var d = jourDe(calJour || aujourdhui()), mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        if (vueCal === "mois") return mois[d.getMonth()] + " " + d.getFullYear()
        var l = lundi(d); return "semaine du " + l.getDate() + " " + mois[l.getMonth()]
    }
    function couleurStatut(s) {
        return s === "reportee" || s === "script" ? cDefaut : s === "fabrication" || s === "a_verifier" ? cAttention : s === "approuvee" || s === "programmee" ? cSelection
             : s === "publiee" || s === "suivie" ? cReussi : s === "idee" ? cSecond : cTexte
    }
    function euros(x) { return (x || 0).toFixed(2).replace(".", ",") + " €" }
    function nombre(texte) { var x = Number(texte.trim().replace(",", ".")); return texte.trim() === "" || isNaN(x) ? null : x }
    function sessionChoisie() { return sessions.find(x => x.id === session) || {nom: "", pause: false, archivee: "", essais: false} }
    function basculerFormat(id) { var c = reglages.formats.slice(); var i = c.indexOf(id); if (i >= 0) c.splice(i, 1); else c.push(id)
                                  pont.agir("ecrire_reglages", {id: session, corps: {formats: c}}) }
    function nouvelleSession() { nouvelle = {etape: 1, id: ""}; modeleChoisi = ""; nNom.texte = nLangues.texte = nPublic.texte = nPromesse.texte = ""; aller("nouvelle") }
    function ouvrirSession(s) {
        choisir(s.id)
        if (s.assistant && s.assistant !== "fini") { nouvelle = {etape: Number(s.assistant), id: s.id}; reglagesDe = ""; aller("nouvelle") } else aller("sessions")
    }
    function suivant(champs) {  // l'étape enregistrée (appel à son propre nom), l'assistant avance (onFait) ; un refus le laisse à l'étape
        pont.agir("etape_suivante", {id: session, corps: Object.assign(nouvelle.etape < 6 ? {assistant: String(nouvelle.etape + 1)} : {}, champs)})
    }
    function ouvrirVideo(id) { video = Object.assign({}, videoVide, {id: id}); coches = []; ongletVideo = "fabrication"; aller("video") }
    function mmss(s) { s = Math.floor(s); return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0") }
    function aller_a(s) { lecteur.position = Math.round(s * 1000) + 20; lecteur.pause() }  // + 20 ms : Qt Multimedia montre sinon l'image d'avant (banc du 16/11)
    function ouvrirScript(code) { if (brouillon !== null && script.code !== code) brouillons[script.code] = brouillon
                                  if (script.code !== code) { brouillon = brouillons[code] || null; delete brouillons[code] }
                                  script = {code: code, titre: "", date_prevue: "", versions: [], contenu: {}, regles: {}, plans: [], estimation: {secondes: 0, cout_eur: 0}, traductions: []}
                                  aFabriquer = ""; langues = []; if (brouillon) aControler.restart(); aller("script") }
    function ecrire() { brouillon = JSON.parse(JSON.stringify(script.contenu)); controler = script.regles }
    function regles() { return brouillon ? controler : script.regles }
    function basculer(l) { var c = langues.slice(); var i = c.indexOf(l); if (i >= 0) c.splice(i, 1); else c.push(l); langues = c }
    function duree(s) { return s >= 3600 ? (s / 3600).toFixed(1).replace(".", ",") + " h" : Math.max(1, Math.round(s / 60)) + " min" }
    function cocher(n) { var c = coches.slice(); var i = c.indexOf(n); if (i >= 0) c.splice(i, 1); else c.push(n); coches = c }
    function aller(e) { if (e !== "") ecran = e; recharger() }
    function copier(texte) { pressePapier.text = texte; pressePapier.selectAll(); pressePapier.copy(); message = "Texte copié."; messageOk = true }
    function chaineDe(langue) { return destinations.find(d => d.langue === langue) || {playlists: []} }
    function nomDe(chemin) { return chemin.split(/[\\/]/).pop() }
    function url(chemin) { return "file:///" + chemin.replace(/\\/g, "/") }
    function estImage(chemin) { return /\.(png|jpe?g)$/i.test(chemin) }
    function ouvrirBanc(id) { banc = Object.assign({}, bancVide, {id: id}); ligneBanc = 0; bancOuvert = true; lecteurBanc.stop(); pont.lire("banc", {id: id}) }
    function voterBanc(choix) {
        if (banc.etat !== "a_voter" || !banc.lignes.length) return
        pont.agir("voter", {id: banc.id, corps: {entree: banc.lignes[ligneBanc].n, choix: choix}})  // l'entrée suivante quand le vote est enregistré (onFait)
    }
    function briqueChoisie() { return outils.briques.find(b => b.id === nouveauBanc.brique) || {outils: [], juges: [], defaut: ""} }
    function aFaire() { return file.filter(t => t.etat === "erreur" || t.alertes.length > 0 && t.etat !== "finie" && t.etat !== "annulee") }
    function derniere() {
        var d = sauvegardes.derniere
        return d.etat === "en_cours" ? "Sauvegarde en cours…"
             : d.etat === "faite" ? "Dernière sauvegarde : le " + d.fin.slice(8, 10) + "/" + d.fin.slice(5, 7) + " à " + d.fin.slice(11, 16) + " (" + String(d.taille_mo).replace(".", ",") + " Mo)"
             : d.etat === "erreur" ? "La dernière sauvegarde a raté : " + d.message : "Aucune sauvegarde encore."
    }

    Component.onCompleted: recharger()
    Connections {
        target: pont
        function onRecu(nom, d) {
            if (nom === "nouvelle_session") { message = d.message; messageOk = true; nouvelle = {etape: 2, id: d.id}; choisir(d.id); return }  // la session créée : étape 2
            f[nom] = d
            if (nom === "reglages" && reglagesDe !== session) remplir()
            if (nom === "univers" && universDe !== session) { universDe = session; champStyle.texte = d.style }
            if (nom === "sessions" && session === "" && d.length) choisir(d[0].id)
            if (nom === "banc" && bancOuvert) { bancOuvert = false; ligneBanc = Math.max(0, d.lignes.findIndex(l => l.vote === "")) }
            if (nom === "depenses" && !plafondRempli) { plafondRempli = true; champPlafond.texte = String(d.plafond_mois_eur).replace(".", ",") }
            if (nom === "relier" && d.url) { message = d.message; messageOk = true; Qt.openUrlExternally(d.url) }  // la page de Google, dans le navigateur du PC
        }
        function onFait(nom, texte, ok) {
            message = texte; messageOk = ok
            if (nom === "refaire") liberer = false
            if (nom === "nouvelle_version" && ok) brouillon = null  // refusé ou noyau absent : le texte tapé reste là
            if (nom === "etape_suivante" && ok) {  // « Suivant » enregistré : l'assistant avance ; la 6e étape finit la session (« fini » posé par le noyau)
                if (nouvelle.etape === 6) pont.agir("finir_session", {id: session})
                else nouvelle = {etape: nouvelle.etape + 1, id: nouvelle.id}
            }
            if (nom === "finir_session" && ok) nouvelle = {etape: 7, id: nouvelle.id}
            if (nom === "voter" && ok) ligneBanc = Math.min(ligneBanc + 1, banc.lignes.length - 1)
            recharger()
        }
        function onAller(e) { aller(e) }
        function onEvenement(type, d) { if (type !== "etat") rafraichir() }
    }

    component T: Text { color: cTexte; font.family: "Segoe UI Variable"; font.pixelSize: 14; wrapMode: Text.Wrap }
    component Mono: T { font.family: mono; wrapMode: Text.NoWrap }
    component Clic: TapHandler { gesturePolicy: TapHandler.ReleaseWithinBounds }
    component Bouton: Rectangle {
        property alias texte: bt.text
        property bool actif: true
        property bool ambre: false  // un geste de RT qui part dehors (Publier)
        signal clic()
        width: bt.implicitWidth + 32; height: 32; radius: 6
        color: ambre ? cAccent : survol.hovered && actif ? cTrait : cLeve
        border.width: 1; border.color: activeFocus ? cSelection : cTrait
        activeFocusOnTab: actif
        Keys.onReturnPressed: if (actif) clic()
        Keys.onSpacePressed: if (actif) clic()
        opacity: actif ? 1 : 0.4
        Behavior on color { ColorAnimation { duration: 120 } }
        T { id: bt; anchors.centerIn: parent; wrapMode: Text.NoWrap; color: ambre ? cFond : cTexte; font.weight: ambre ? Font.DemiBold : Font.Normal }
        HoverHandler { id: survol }
        Clic { enabled: parent.actif; onTapped: parent.clic() }
        Accessible.role: Accessible.Button; Accessible.name: bt.text; Accessible.onPressAction: if (actif) clic()
    }
    component Champ: Item {  // une ligne de texte modifiable ; son libellé dedans tant qu'elle est vide, ou au-dessus (« etiquette »)
        property alias texte: saisie.text
        property alias nom: saisie.objectName
        property string libelle: ""
        property bool etiquette: false  // un champ rempli d'avance garde son libellé lisible
        property alias seul: saisie.readOnly
        width: parent.width; height: etiquette ? 52 : 32
        Text { visible: etiquette; text: libelle; color: cSecond; font.family: "Segoe UI Variable"; font.pixelSize: 12; width: parent.width; elide: Text.ElideRight }
        Rectangle {
            anchors.bottom: parent.bottom; width: parent.width; height: 32; radius: 6; color: cFond; border.width: 1; border.color: saisie.activeFocus ? cSelection : cTrait
            TextInput { id: saisie; anchors.fill: parent; anchors.margins: 8; clip: true; color: cTexte; font.family: "Segoe UI Variable"; font.pixelSize: 14; selectByMouse: true
                        Accessible.name: libelle }
            Text { visible: !etiquette && saisie.text === "" && !saisie.activeFocus; text: libelle; color: cSecond; font.family: "Segoe UI Variable"; font.pixelSize: 13; x: 8
                   anchors.verticalCenter: parent.verticalCenter; width: parent.width - 16; elide: Text.ElideRight }
        }
    }
    component Droits: Column {  // licence et crédit d'un élément de l'univers ; partager (personnage, lieu) avec une autre session
        property string type: ""
        property var element: ({})
        width: parent.width; spacing: 6
        Row {
            spacing: 6
            Champ { id: lic; width: 190; etiquette: true; libelle: "Licence"; nom: "licence_" + type + "_" + element.id; texte: element.licence || "" }
            Champ { id: cre; width: 190; etiquette: true; libelle: "Crédit à citer"; nom: "credit_" + type + "_" + element.id; texte: element.credit || "" }
            Bouton { anchors.bottom: parent.bottom; objectName: "droits_" + type + "_" + element.id; texte: "Enregistrer les droits"
                     onClic: pont.agir("ecrire_droits", {id: session, type: type, pk: element.id, corps: {licence: lic.texte, credit: cre.texte}}) }
            Bouton { anchors.bottom: parent.bottom; visible: type === "personnage" || type === "lieu"; objectName: "partager_" + type + "_" + element.id; texte: "Partager…"
                     onClic: aPartager = {type: type, pk: element.id} }
        }
        Flow {
            visible: aPartager.type === type && aPartager.pk === element.id
            width: parent.width; spacing: 6
            T { text: "Copier « " + element.nom + " » dans :"; color: cSecond; height: 32; verticalAlignment: Text.AlignVCenter; wrapMode: Text.NoWrap }
            Repeater {
                model: sessions.filter(x => x.id !== session && !x.essais && !x.archivee)
                Bouton { objectName: "partager_vers_" + index; texte: modelData.nom
                         onClic: { pont.agir("partager", {id: session, type: aPartager.type, pk: aPartager.pk, corps: {vers: modelData.id}}); aPartager = {type: "", pk: -1} } }
            }
            Bouton { texte: "Annuler"; onClic: aPartager = {type: "", pk: -1} }
        }
    }
    component Puce: Bouton {  // un choix parmi plusieurs : bordure de sélection
        property bool choisi: false
        border.width: choisi ? 2 : 1; border.color: choisi || activeFocus ? cSelection : cTrait
        Accessible.checkable: true; Accessible.checked: choisi
    }
    component Panneau: Rectangle {
        property alias titre: entete.text
        default property alias contenu: colonne.data
        width: parent.width; height: colonne.implicitHeight + 32; radius: 10
        color: cPanneau; border.width: 1; border.color: cTrait
        Column {
            id: colonne
            x: 16; y: 16; width: parent.width - 32; spacing: 12
            T { id: entete; font.pixelSize: 20; font.weight: Font.DemiBold; width: parent.width }
        }
    }

    Rectangle {
        id: nav
        width: 220; height: parent.height; color: cPanneau
        Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: cTrait }
        Column {
            x: 16; y: 16; width: parent.width - 32; spacing: 8
            T { text: "Fabrique"; font.pixelSize: 20; font.weight: Font.DemiBold }
            Mono { text: sante.version ? "version " + sante.version : ""; color: cSecond; font.pixelSize: 12 }
            Item { width: 1; height: 16 }
            Repeater {
                model: [{id: "accueil", nom: "Accueil", touche: "Ctrl+1"}, {id: "sessions", nom: "Sessions", touche: "Ctrl+2"}, {id: "file", nom: "File", touche: "Ctrl+3"},
                        {id: "outils", nom: "Outils", touche: "Ctrl+4"}, {id: "banc", nom: "Banc", touche: "Ctrl+5"}, {id: "systeme", nom: "Système", touche: "Ctrl+9"}]
                Rectangle {
                    objectName: "nav_" + modelData.id
                    width: parent.width; height: 40; radius: 6
                    color: (ecran === "video" || ecran === "script" || ecran === "nouvelle" ? "sessions" : ecran) === modelData.id || survolNav.hovered ? cLeve : "transparent"
                    Rectangle { visible: (ecran === "video" || ecran === "script" || ecran === "nouvelle" ? "sessions" : ecran) === modelData.id; width: 3; height: 20; radius: 2; color: cSelection; anchors.verticalCenter: parent.verticalCenter }
                    T { text: modelData.nom; x: 12; anchors.verticalCenter: parent.verticalCenter }
                    Mono { text: modelData.touche; color: cSecond; font.pixelSize: 12; anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter }
                    HoverHandler { id: survolNav }
                    Clic { onTapped: aller(modelData.id) }
                    Accessible.role: Accessible.Button; Accessible.name: modelData.nom + " (" + modelData.touche + ")"; Accessible.onPressAction: aller(modelData.id)
                }
            }
        }
        Mono { x: 16; anchors.bottom: parent.bottom; anchors.bottomMargin: 16; text: "F5 : actualiser"; color: cSecond; font.pixelSize: 12 }
    }

    Item {
        id: contenu
        anchors { left: nav.right; right: parent.right; top: parent.top; bottom: barre.top }

        Flickable {
            objectName: "ecran_accueil"
            visible: ecran === "accueil"
            anchors.fill: parent; contentHeight: pileAccueil.height + 48; clip: true
            ScrollBar.vertical: ScrollBar { width: 8; policy: ScrollBar.AsNeeded; contentItem: Rectangle { radius: 4; color: cTrait } }
            Column {
                id: pileAccueil
                x: 24; y: 24; width: Math.min(contenu.width - 48, 960); spacing: 16
                T { text: "Accueil"; font.pixelSize: 28; font.weight: Font.DemiBold }
                Panneau {
                    objectName: "mur"
                    titre: "Sessions"
                    Flow {
                        width: parent.width; spacing: 12
                        Repeater {
                            model: sessions.filter(x => !x.archivee)
                            Rectangle {
                                objectName: "carte_" + index
                                width: 300; height: carteSession.implicitHeight + 24; radius: 10; color: survolCarte.hovered ? cTrait : cLeve; border.width: 1
                                border.color: activeFocus ? cSelection : cTrait
                                property bool aFinir: !!modelData.assistant && modelData.assistant !== "fini"
                                Column {
                                    id: carteSession
                                    x: 12; y: 12; width: parent.width - 24; spacing: 4
                                    T { text: modelData.nom; font.pixelSize: 16; font.weight: Font.DemiBold; width: parent.width; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                                    T { font.pixelSize: 12; color: parent.parent.aFinir || modelData.pause ? cAttention : cSecond
                                        text: modelData.essais ? "Essais de construction, jamais publiés" : parent.parent.aFinir ? "Nouvelle session à finir (étape " + modelData.assistant + ")"
                                            : modelData.pause ? "En pause" : "En service" }
                                    T { text: modelData.videos + " vidéo(s)" + (modelData.derniere ? " · dernière : " + modelData.derniere : ""); width: parent.width; elide: Text.ElideRight
                                        wrapMode: Text.NoWrap; font.pixelSize: 12 }
                                    T { text: modelData.a_faire ? modelData.a_faire + " à faire (approuver, publier, erreur)" : "Rien à faire"; color: modelData.a_faire ? cAccent : cSecond; font.pixelSize: 12 }
                                    T { text: modelData.prochain ? "Prochaine : " + modelData.prochain : "Rien de daté à venir"; width: parent.width; elide: Text.ElideRight; wrapMode: Text.NoWrap
                                        font.pixelSize: 12; color: cSecond }
                                    T { text: modelData.rendement || "Pas encore de statistiques"; font.pixelSize: 12; color: cSecond }
                                }
                                HoverHandler { id: survolCarte }
                                Clic { onTapped: ouvrirSession(modelData) }
                                activeFocusOnTab: true
                                Keys.onReturnPressed: ouvrirSession(modelData)
                                Keys.onSpacePressed: ouvrirSession(modelData)
                                Accessible.role: Accessible.Button; Accessible.name: "Session " + modelData.nom; Accessible.onPressAction: ouvrirSession(modelData)
                            }
                        }
                    }
                    Bouton { objectName: "bouton_nouvelle_session"; texte: "Nouvelle session"; onClic: nouvelleSession() }
                }
                Panneau {
                    titre: aFaire().length ? "À faire" : "Rien à faire pour l'instant"
                    T { visible: !aFaire().length; text: "Ici s'affiche ce qui attend votre clic : une fabrication en erreur, une vidéo à approuver ou à publier."; color: cSecond; width: parent.width }
                    Repeater {
                        model: aFaire()
                        T { text: "« " + modelData.titre + " » (" + modelData.session + ") : " + (modelData.raison || modelData.alertes[modelData.alertes.length - 1]); width: parent.width
                            color: modelData.etat === "erreur" ? cDefaut : cAttention }
                    }
                }
                Panneau {
                    objectName: "panneau_file"
                    titre: "File"
                    T { width: parent.width; color: cSecond
                        text: file.filter(x => x.etat === "en_cours").length + " en cours, " + file.filter(x => x.etat === "attente").length + " en attente, "
                              + file.filter(x => x.etat === "erreur").length + " en erreur." }
                    Bouton { objectName: "voir_file"; texte: "Voir la file (Ctrl+3)"; onClic: aller("file") }
                }
                Panneau {
                    titre: "Machine"
                    Row {
                        spacing: 8
                        T { text: "Carte :"; color: cSecond; wrapMode: Text.NoWrap }
                        Mono { objectName: "machine_carte"; text: machine.carte }
                        Item { width: 24; height: 1 }
                        T { text: "Disque libre :"; color: cSecond; wrapMode: Text.NoWrap }
                        Mono { text: machine.disque_go + " Go"; color: machine.disque_go < 50 ? cDefaut : cTexte }
                    }
                    T { text: machine.carte_prise ? "Rien ne part pour l'instant : " + machine.carte_prise + "." : "La carte est libre : la prochaine fabrication peut partir."
                        color: machine.carte_prise ? cAttention : cReussi; width: parent.width }
                }
            }
        }

        Flickable {
            objectName: "ecran_file"
            visible: ecran === "file"
            anchors.fill: parent; contentHeight: pileFile.height + 48; clip: true
            ScrollBar.vertical: ScrollBar { width: 8; policy: ScrollBar.AsNeeded; contentItem: Rectangle { radius: 4; color: cTrait } }
            Column {
                id: pileFile
                x: 24; y: 24; width: Math.min(contenu.width - 48, 960); spacing: 16
                T { text: "File"; font.pixelSize: 28; font.weight: Font.DemiBold }
                T { text: "Une seule file pour toutes les sessions ; la carte n'est prise que si Bramble Studio ne fabrique pas. Durées estimées d'après les fabrications passées (PC éteint de minuit à 7 h)."
                    color: cSecond; width: parent.width }
                Panneau {
                    titre: "Ce qui tourne et ce qui attend"
                    T { visible: !file.length; text: "Rien en cours ni en attente."; color: cSecond; width: parent.width }
                    Repeater {
                        model: file
                        Rectangle {
                            width: parent.width; height: ligneFile.implicitHeight + 20; radius: 6; color: cLeve
                            Column {
                                id: ligneFile
                                x: 12; y: 10; width: parent.width - 300; spacing: 4
                                T { text: modelData.titre + "  ·  " + modelData.session; font.weight: Font.DemiBold; width: parent.width; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                                Row {
                                    spacing: 12
                                    T { text: etats[modelData.etat]; color: modelData.etat === "erreur" ? cDefaut : modelData.etat === "en_cours" ? cReussi : cSecond; wrapMode: Text.NoWrap }
                                    Mono { text: modelData.progression + (modelData.banc ? " sorties du banc" : " morceaux"); color: cSecond }
                                }
                                Mono { visible: modelData.reste_s != null; font.pixelSize: 12; color: cSecond
                                       text: "reste environ " + duree(modelData.reste_s || 0) + "  ·  " + euros(modelData.cout_eur) + "  ·  prête vers le " + modelData.pret_vers }
                                T { visible: modelData.raison !== ""; text: modelData.raison; color: modelData.etat === "erreur" ? cDefaut : cAttention; width: parent.width; font.pixelSize: 12 }
                            }
                            Row {
                                anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                                Bouton { objectName: "pause_" + index; visible: modelData.etat === "attente" || modelData.etat === "en_cours"; texte: "Pause"
                                         onClic: pont.agir("agir_file", {id: modelData.id, action: "pause"}) }
                                Bouton { objectName: "reprendre_" + index; visible: modelData.etat === "pause" || modelData.etat === "erreur"; texte: "Reprendre"
                                         onClic: pont.agir("agir_file", {id: modelData.id, action: "reprendre"}) }
                                Bouton { objectName: "annuler_" + index; visible: modelData.etat !== "finie" && modelData.etat !== "annulee"; texte: "Annuler"
                                         onClic: pont.agir("agir_file", {id: modelData.id, action: "annuler"}) }
                            }
                        }
                    }
                }
            }
        }

        Flickable {
            objectName: "ecran_nouvelle"
            visible: ecran === "nouvelle"
            anchors.fill: parent; contentHeight: pileNouvelle.height + 48; clip: true
            ScrollBar.vertical: ScrollBar { width: 8; policy: ScrollBar.AsNeeded; contentItem: Rectangle { radius: 4; color: cTrait } }
            Column {
                id: pileNouvelle
                x: 24; y: 24; width: Math.min(contenu.width - 48, 960); spacing: 16
                T { text: nouvelle.etape === 1 ? "Nouvelle session" : "Nouvelle session : " + reglages.nom; font.pixelSize: 28; font.weight: Font.DemiBold; width: parent.width }
                Flow {
                    width: parent.width; spacing: 6
                    Repeater {
                        model: ["Identité", "Formats", "Univers", "Destinations", "Règles", "Objectif", "Vidéo pilote"]
                        Rectangle {
                            width: nomEtape.implicitWidth + 24; height: 30; radius: 6
                            color: nouvelle.etape === index + 1 ? cSelection : nouvelle.etape > index + 1 ? cTrait : cLeve
                            T { id: nomEtape; text: (index + 1) + ". " + modelData; anchors.centerIn: parent; wrapMode: Text.NoWrap; font.pixelSize: 13
                                color: nouvelle.etape >= index + 1 ? cTexte : cSecond }
                            Accessible.name: "Étape " + (index + 1) + " : " + modelData + (nouvelle.etape === index + 1 ? " (en cours)" : nouvelle.etape > index + 1 ? " (faite)" : "")
                        }
                    }
                }
                Panneau {
                    visible: nouvelle.etape === 1
                    titre: "1. Identité"
                    Champ { id: nNom; nom: "nouvelle_nom"; libelle: "Nom de la session"; etiquette: !!nouvelle.id; seul: !!nouvelle.id }
                    Champ { id: nLangues; nom: "nouvelle_langues"; libelle: "Langues, codes séparés par des virgules (ex. en, fr) : la première est celle des scripts"; etiquette: !!nouvelle.id }
                    Champ { id: nPublic; nom: "nouvelle_public"; libelle: "Public (ex. enfants de 3 à 6 ans)"; etiquette: !!nouvelle.id }
                    Champ { id: nPromesse; nom: "nouvelle_promesse"; libelle: "Promesse (ce que chaque vidéo apporte)"; etiquette: !!nouvelle.id }
                    T { visible: !nouvelle.id; text: "Partir d'un modèle de session (facultatif) : ses règles, son univers et ses formats sont repris, ni vidéos, ni scripts, ni comptes."
                        color: cSecond; width: parent.width; font.pixelSize: 12 }
                    Flow {
                        visible: !nouvelle.id
                        width: parent.width; spacing: 8
                        Bouton { objectName: "modele_aucun"; texte: "De zéro" + (modeleChoisi === "" ? " ✓" : ""); onClic: modeleChoisi = "" }
                        Repeater {
                            model: modeles
                            Bouton { objectName: "modele_" + index; texte: modelData.nom + (modeleChoisi === modelData.fichier ? " ✓" : ""); onClic: modeleChoisi = modelData.fichier }
                        }
                    }
                    Bouton { objectName: "suivant_1"; visible: !!nouvelle.id; texte: "Enregistrer et continuer"; actif: nLangues.texte.trim() !== ""
                             onClic: suivant({public: nPublic.texte, promesse: nPromesse.texte,
                                              langues: nLangues.texte.split(",").map(x => x.trim().toLowerCase()).filter(x => x !== "").map(x => ({code: x, nom: ""}))}) }
                    Bouton { objectName: "creer_session"; visible: !nouvelle.id; texte: "Créer la session"; actif: nNom.texte.trim() !== "" && nLangues.texte.trim() !== ""
                             onClic: pont.lire("nouvelle_session", {corps: {nom: nNom.texte, public: nPublic.texte, promesse: nPromesse.texte, modele: modeleChoisi,
                                                                            langues: nLangues.texte.split(",").map(x => x.trim().toLowerCase()).filter(x => x !== "").map(x => ({code: x, nom: ""}))}}) }
                }
                Panneau {
                    visible: nouvelle.etape === 2
                    titre: "2. Formats"
                    T { text: "Les formats de la session, pris dans le catalogue ; le premier choisi est celui de « Fabriquer » (il se change dans Session → Formats)."
                        color: cSecond; width: parent.width }
                    Repeater {
                        model: nouvelle.etape === 2 ? formats : []
                        Bouton { objectName: "nouvelle_format_" + modelData.id; texte: modelData.nom + (reglages.formats.indexOf(modelData.id) >= 0 ? " ✓" : "")
                                 onClic: basculerFormat(modelData.id) }
                    }
                    Bouton { objectName: "suivant_2"; texte: "Suivant"; actif: reglages.formats.length > 0; onClic: suivant({}) }
                }
                Panneau {
                    visible: nouvelle.etape === 3
                    titre: "3. Univers"
                    Champ { etiquette: true; id: nStyle; nom: "nouvelle_style"; libelle: "Le style (images, couleurs, ton)" }
                    T { text: univers.personnages.length ? "Personnages : " + univers.personnages.map(x => x.nom).join(", ") : "Aucun personnage pour l'instant."
                        width: parent.width; color: cSecond }
                    Row {
                        spacing: 6
                        Champ { id: nPerso; width: 260; nom: "nouvelle_personnage"; libelle: "Nom d'un personnage" }
                        Champ { id: nRole; width: 180; nom: "nouvelle_role"; libelle: "Rôle" }
                        Bouton { objectName: "nouvelle_ajouter_personnage"; texte: "Ajouter"; actif: nPerso.texte.trim() !== ""
                                 onClic: { pont.agir("ajouter_element", {id: session, corps: {type: "personnage", nom: nPerso.texte, role: nRole.texte, description: ""}})
                                           nPerso.texte = ""; nRole.texte = "" } }
                    }
                    T { text: "Les images de référence se glissent sur chaque personnage dans Session → Univers ; la voix de chaque langue se choisit au banc, à l'aveugle."
                        color: cSecond; width: parent.width; font.pixelSize: 12 }
                    Bouton { objectName: "suivant_3"; texte: "Suivant"; onClic: suivant({style: nStyle.texte}) }
                }
                Panneau {
                    visible: nouvelle.etape === 4
                    titre: "4. Destinations"
                    T { text: "Une chaîne YouTube par langue. Une langue sans chaîne reliée est fabriquée, pas envoyée : relier maintenant, ou plus tard dans Session → Destinations."
                        color: cSecond; width: parent.width }
                    Repeater {
                        model: nouvelle.etape === 4 ? destinations : []
                        Row {
                            spacing: 12
                            Mono { text: modelData.langue; width: 40; anchors.verticalCenter: parent.verticalCenter }
                            T { text: modelData.reliee ? modelData.chaine : modelData.etat; width: 360; color: modelData.reliee ? cTexte : cAttention; anchors.verticalCenter: parent.verticalCenter
                                elide: Text.ElideRight; wrapMode: Text.NoWrap }
                            Bouton { objectName: "nouvelle_relier_" + modelData.langue; texte: modelData.reliee ? "Relier à nouveau" : "Relier"
                                     onClic: pont.lire("relier", {id: session, langue: modelData.langue}) }
                        }
                    }
                    Bouton { objectName: "suivant_4"; texte: "Suivant"; onClic: suivant({}) }
                }
                Panneau {
                    visible: nouvelle.etape === 5
                    titre: "5. Règles"
                    T { text: "Ce qui rend chaque vidéo différente (histoire, personnages) : obligatoire. YouTube écarte le « contenu en série sur gabarit »."
                        color: cAttention; width: parent.width; font.pixelSize: 13 }
                    Champ { etiquette: true; id: nDiff; nom: "nouvelle_difference"; libelle: "Ce qui rend chaque vidéo différente" }
                    Row {
                        spacing: 8
                        Champ { etiquette: true; id: nMin; width: 220; nom: "nouvelle_duree_min"; libelle: "Durée minimale (min)" }
                        Champ { etiquette: true; id: nMax; width: 220; nom: "nouvelle_duree_max"; libelle: "Durée maximale (min)" }
                    }
                    Flow {
                        width: parent.width; spacing: 8
                        Bouton { objectName: "nouvelle_enfants"; texte: "Conçue pour les enfants" + (reglages.enfants ? " ✓" : "")
                                 onClic: pont.agir("ecrire_reglages", {id: session, corps: {enfants: !reglages.enfants}}) }
                        Bouton { objectName: "nouvelle_ia"; texte: "Déclaration IA" + (reglages.declaration_ia ? " ✓" : "")
                                 onClic: pont.agir("ecrire_reglages", {id: session, corps: {declaration_ia: !reglages.declaration_ia}}) }
                    }
                    Bouton { objectName: "suivant_5"; texte: "Suivant"; actif: nDiff.texte.trim() !== ""
                             onClic: suivant({difference: nDiff.texte, duree_min: nombre(nMin.texte), duree_max: nombre(nMax.texte)}) }
                }
                Panneau {
                    visible: nouvelle.etape === 6
                    titre: "6. Objectif, critère d'arrêt, plafond"
                    Champ { etiquette: true; id: nObjectif; nom: "nouvelle_objectif"; libelle: "Objectif (ex. 1 000 abonnés en 6 mois)" }
                    Champ { etiquette: true; id: nArret; nom: "nouvelle_arret"; libelle: "Critère d'arrêt (ex. moins de 50 vues par vidéo après 20 vidéos)" }
                    Champ { etiquette: true; id: nPlafond; nom: "nouvelle_plafond"; libelle: "Plafond des outils payants, en € par mois (0 : jamais)" }
                    T { visible: reglages.manque.length > 0; text: "Il manque encore : " + reglages.manque.join(", ") + "."; color: cAttention; width: parent.width }
                    Bouton { objectName: "terminer_session"; texte: "Terminer"
                             onClic: suivant({objectif: nObjectif.texte, arret: nArret.texte, plafond_eur: nombre(nPlafond.texte) || 0}) }
                }
                Panneau {
                    visible: nouvelle.etape === 7
                    titre: "7. Vidéo pilote"
                    T { text: "La session est prête. La vidéo pilote se fabrique en simulation : chaque étape sur un faux outil, quelques secondes, rien ne sort de ce PC. "
                              + "Elle se regarde ensuite dans Vidéos. « En vrai » : « Fabriquer » un script de la session, plus tard."; width: parent.width }
                    Row {
                        spacing: 8
                        Bouton { objectName: "lancer_pilote"; texte: "Lancer la vidéo pilote"; onClic: pont.agir("pilote", {id: session}) }
                        Bouton { objectName: "ouvrir_session"; texte: "Ouvrir la session"; onClic: { onglet = "videos"; aller("sessions") } }
                    }
                }
                Row {
                    visible: nouvelle.etape > 1 && nouvelle.etape < 7  // étape 1 d'une session créée : ses champs se corrigent, rien n'est recréé
                    spacing: 8
                    Bouton { objectName: "etape_avant"; texte: "← Étape d'avant"; onClic: nouvelle = {etape: nouvelle.etape - 1, id: nouvelle.id} }
                    T { text: "La session reste en pause jusqu'à « Terminer » ; elle se reprend depuis sa carte de l'Accueil."; color: cSecond; font.pixelSize: 12
                        anchors.verticalCenter: parent.verticalCenter; wrapMode: Text.NoWrap }
                }
            }
        }

        Item {
            objectName: "ecran_sessions"
            visible: ecran === "sessions"
            anchors.fill: parent
            Column {
                id: listeSessions
                x: 24; y: 24; width: 220; spacing: 8
                T { text: "Sessions"; font.pixelSize: 28; font.weight: Font.DemiBold }
                Repeater {
                    model: sessions
                    Rectangle {
                        objectName: "session_" + index
                        width: parent.width; height: 44; radius: 6
                        color: session === modelData.id || survolSession.hovered ? cLeve : "transparent"
                        border.width: session === modelData.id ? 1 : 0; border.color: cSelection
                        T { text: modelData.nom + (modelData.archivee ? " (archivée)" : modelData.pause ? " (en pause)" : ""); x: 12; width: parent.width - 24
                            anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight; wrapMode: Text.NoWrap; color: modelData.pause ? cSecond : cTexte }
                        HoverHandler { id: survolSession }
                        Clic { onTapped: choisir(modelData.id) }
                        Accessible.role: Accessible.Button; Accessible.name: "Session " + modelData.nom; Accessible.onPressAction: choisir(modelData.id)
                    }
                }
                Item { width: 1; height: 8 }
                Bouton { objectName: "nouvelle_session"; texte: "Nouvelle session"; onClic: nouvelleSession() }
                Rectangle {
                    width: parent.width; height: colImport.implicitHeight + 16; radius: 6; color: depotSession.containsDrag ? cTrait : "transparent"
                    border.width: 1; border.color: depotSession.containsDrag ? cSelection : cTrait
                    DropArea {
                        id: depotSession; anchors.fill: parent
                        onDropped: (d) => { d.urls.forEach(u => pont.agir("importer_session", {corps: {fichier: decodeURIComponent(String(u).replace(/^file:\/\/\//, "")),
                                                                                                        nom: nomImport.texte.trim()}})); d.acceptProposedAction() }
                    }
                    Column {
                        id: colImport
                        x: 8; y: 8; width: parent.width - 16; spacing: 6
                        T { text: "Importer une session : glisser son fichier .fabrique ici, ou coller son chemin."; color: cSecond; font.pixelSize: 12; width: parent.width }
                        Champ { id: cheminImport; nom: "chemin_import"; libelle: "Chemin du fichier .fabrique" }
                        Champ { id: nomImport; nom: "nom_import"; libelle: "Sous le nom (facultatif)" }
                        Bouton { objectName: "importer_session"; texte: "Importer"; actif: cheminImport.texte.trim() !== ""
                                 onClic: { pont.agir("importer_session", {corps: {fichier: cheminImport.texte.trim().replace(/^"|"$/g, ""), nom: nomImport.texte.trim()}})
                                           cheminImport.texte = ""; nomImport.texte = "" } }
                    }
                }
            }
            Column {
                id: entetesSession
                anchors { left: listeSessions.right; leftMargin: 24; top: parent.top; topMargin: 72; right: parent.right; rightMargin: 24 }
                spacing: 12
                Row {
                    spacing: 8
                    Repeater {
                        model: [{id: "calendrier", nom: "Calendrier"}, {id: "videos", nom: "Vidéos"}, {id: "scripts", nom: "Scripts"}, {id: "univers", nom: "Univers"},
                                {id: "formats", nom: "Formats"}, {id: "destinations", nom: "Destinations"}, {id: "regles", nom: "Règles"}]
                        Rectangle {
                            objectName: "onglet_" + modelData.id
                            width: nomOnglet.implicitWidth + 32; height: 36; radius: 6
                            color: onglet === modelData.id ? cLeve : "transparent"; border.width: 1; border.color: onglet === modelData.id ? cSelection : cTrait
                            T { id: nomOnglet; text: modelData.nom; anchors.centerIn: parent; wrapMode: Text.NoWrap }
                            Clic { onTapped: ouvrirOnglet(modelData.id) }
                            Accessible.role: Accessible.PageTab; Accessible.name: modelData.nom; Accessible.onPressAction: ouvrirOnglet(modelData.id)
                        }
                    }
                }
            }
            Flickable {
                id: defileSession
                objectName: "defile_session"
                anchors { left: entetesSession.left; right: entetesSession.right; top: entetesSession.bottom; topMargin: 12; bottom: parent.bottom }
                contentHeight: pileSession.height + 24; clip: true
                ScrollBar.vertical: ScrollBar { width: 8; policy: ScrollBar.AsNeeded; contentItem: Rectangle { radius: 4; color: cTrait } }
                Column {
                    id: pileSession
                    width: Math.min(parent.width - 16, 960); spacing: 8  // la barre de défilement à droite, hors des boutons
                    Repeater {
                        model: onglet === "scripts" ? scripts : []
                        Rectangle {
                            objectName: "script_" + index
                            width: parent.width; height: 52; radius: 6; color: survolScript.hovered ? cTrait : cLeve
                            HoverHandler { id: survolScript }
                            Clic { onTapped: ouvrirScript(modelData.code) }
                            Accessible.role: Accessible.Button; Accessible.name: "Script " + modelData.titre; Accessible.onPressAction: ouvrirScript(modelData.code)
                            Mono { text: modelData.code; x: 12; anchors.verticalCenter: parent.verticalCenter }
                            T { text: modelData.titre; x: 90; width: parent.width - 400; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                            Mono { text: (modelData.date_prevue || "—") + "  v" + modelData.versions; color: cSecond
                                   anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter }
                        }
                    }
                    T { visible: onglet === "scripts" && !scripts.length; text: "Aucun script dans cette session."; color: cSecond }
                    Row {
                        visible: onglet === "scripts"
                        spacing: 8
                        Champ { id: titreScript; width: 380; nom: "titre_script"; libelle: "Titre d'un nouveau script" }
                        Champ { id: dateScript; width: 200; nom: "date_script"; libelle: "Date (AAAA-MM-JJ, facultative)" }
                        Bouton { objectName: "creer_script"; texte: "Créer le script"; actif: titreScript.texte.trim() !== ""
                                 onClic: { pont.agir("creer_script", {id: session, corps: {titre: titreScript.texte, date: dateScript.texte.trim(), idee: 0}})
                                           titreScript.texte = ""; dateScript.texte = "" } }
                    }
                    Repeater {
                        model: onglet === "videos" ? videos : []
                        Rectangle {
                            objectName: "video_" + index
                            width: parent.width; height: 52; radius: 6; color: survolVideo.hovered ? cTrait : cLeve
                            HoverHandler { id: survolVideo }
                            Clic { onTapped: ouvrirVideo(modelData.id) }
                            Accessible.role: Accessible.Button; Accessible.name: "Vidéo " + modelData.titre; Accessible.onPressAction: ouvrirVideo(modelData.id)
                            T { text: modelData.titre; x: 12; width: parent.width - 360; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                            Mono { text: modelData.recette + "  ·  " + modelData.progression + (modelData.erreurs ? "  ·  " + modelData.erreurs + " en erreur" : "")
                                   color: modelData.erreurs ? cDefaut : cSecond; anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter }
                        }
                    }
                    T { visible: onglet === "videos" && !videos.length; text: "Aucune vidéo fabriquée dans cette session."; color: cSecond }
                    Panneau {
                        visible: onglet === "univers"; titre: "Style"
                        Row {
                            spacing: 8; width: parent.width
                            Champ { etiquette: true; id: champStyle; nom: "champ_style"; libelle: "Le style de l'univers (images, couleurs, ton)"; width: parent.width - 140 }
                            Bouton { anchors.bottom: parent.bottom; objectName: "enregistrer_style"; texte: "Enregistrer"; onClic: pont.agir("ecrire_style", {id: session, valeur: champStyle.texte}) }
                        }
                    }
                    Panneau {
                        visible: onglet === "univers"; titre: "Personnages"
                        T { text: "Glisser des images sur un personnage : elles sont copiées dans ses références (jamais déplacées), à valider d'un clic (cadre vert = validée)."
                            color: cSecond; width: parent.width; font.pixelSize: 12 }
                        Repeater {
                            model: onglet === "univers" ? univers.personnages : []
                            Rectangle {
                                id: fichePerso
                                objectName: "personnage_" + index
                                property var p: modelData
                                width: parent.width; height: colPerso.implicitHeight + 20; radius: 6; color: depotRef.containsDrag ? cTrait : cLeve
                                border.width: depotRef.containsDrag ? 1 : 0; border.color: cSelection
                                DropArea {
                                    id: depotRef; anchors.fill: parent
                                    onDropped: (d) => { d.urls.forEach(u => pont.agir("importer_reference", {id: session, pk: fichePerso.p.id,
                                                            corps: {fichier: decodeURIComponent(String(u).replace(/^file:\/\/\//, "")), vue: ""}})); d.acceptProposedAction() }
                                }
                                Column {
                                    id: colPerso
                                    x: 10; y: 10; width: parent.width - 20; spacing: 8
                                    T { text: fichePerso.p.nom + (fichePerso.p.role ? " · " + fichePerso.p.role : "") + (fichePerso.p.statut !== "actif" ? " · " + fichePerso.p.statut : "")
                                              + (fichePerso.p.description ? " — " + fichePerso.p.description : ""); width: parent.width; font.weight: Font.DemiBold
                                        color: fichePerso.p.statut === "actif" ? cTexte : cSecond }
                                    Flow {
                                        width: parent.width; spacing: 6
                                        Repeater {
                                            model: fichePerso.p.references
                                            Rectangle {
                                                objectName: "reference_" + fichePerso.p.id + "_" + index
                                                width: 88; height: 88; radius: 6; color: cFond; border.width: 2; border.color: modelData.validee ? cReussi : cTrait
                                                Image { anchors.fill: parent; anchors.margins: 4; source: "file:///" + modelData.chemin.replace(/\\/g, "/"); fillMode: Image.PreserveAspectFit
                                                        asynchronous: true; sourceSize.width: 160 }
                                                Clic { onTapped: pont.agir("valider_reference", {id: session, pk: modelData.id, corps: {validee: !modelData.validee}}) }
                                                Accessible.role: Accessible.CheckBox; Accessible.name: "Image " + (modelData.vue || index + 1) + " de " + fichePerso.p.nom + (modelData.validee ? " (validée)" : " (à valider)")
                                                Accessible.checked: modelData.validee
                                                Accessible.onPressAction: pont.agir("valider_reference", {id: session, pk: modelData.id, corps: {validee: !modelData.validee}})
                                            }
                                        }
                                        T { visible: !fichePerso.p.references.length; text: "Aucune image de référence."; color: cSecond; font.pixelSize: 12 }
                                    }
                                    Row {
                                        spacing: 6
                                        Champ { id: cheminRef; width: 386; nom: "chemin_reference_" + fichePerso.p.id; libelle: "Ou le chemin d'une image à ajouter" }
                                        Bouton { objectName: "ajouter_reference_" + fichePerso.p.id; texte: "Ajouter l'image"; actif: cheminRef.texte.trim() !== ""
                                                 onClic: { pont.agir("importer_reference", {id: session, pk: fichePerso.p.id, corps: {fichier: cheminRef.texte.trim().replace(/^"|"$/g, ""), vue: ""}})
                                                           cheminRef.texte = "" } }
                                    }
                                    Droits { type: "personnage"; element: fichePerso.p }
                                }
                            }
                        }
                        Row {
                            spacing: 6
                            Champ { id: nomPerso; width: 220; nom: "nom_personnage"; libelle: "Nom du personnage" }
                            Champ { id: rolePerso; width: 160; nom: "role_personnage"; libelle: "Rôle (héros, ami…)" }
                            Bouton { objectName: "ajouter_personnage"; texte: "Ajouter"; actif: nomPerso.texte.trim() !== ""
                                     onClic: { pont.agir("ajouter_element", {id: session, corps: {type: "personnage", nom: nomPerso.texte, role: rolePerso.texte, description: ""}})
                                               nomPerso.texte = ""; rolePerso.texte = "" } }
                        }
                    }
                    Panneau {
                        visible: onglet === "univers"; titre: "Lieux"
                        Repeater {
                            model: onglet === "univers" ? univers.lieux : []
                            Column {
                                width: parent.width; spacing: 6
                                T { text: modelData.nom + (modelData.description ? " — " + modelData.description : ""); width: parent.width; font.weight: Font.DemiBold }
                                Droits { type: "lieu"; element: modelData }
                            }
                        }
                        Row {
                            spacing: 6
                            Champ { id: nomLieu; width: 386; nom: "nom_lieu"; libelle: "Nom du lieu" }
                            Bouton { objectName: "ajouter_lieu"; texte: "Ajouter"; actif: nomLieu.texte.trim() !== ""
                                     onClic: { pont.agir("ajouter_element", {id: session, corps: {type: "lieu", nom: nomLieu.texte, description: "", role: ""}}); nomLieu.texte = "" } }
                        }
                    }
                    Panneau {
                        visible: onglet === "univers"; titre: "Musiques et voix"
                        T { visible: !univers.ressources.length; text: "Aucune musique ni voix déclarée."; color: cSecond }
                        Repeater {
                            model: onglet === "univers" ? univers.ressources : []
                            Column {
                                width: parent.width; spacing: 6
                                T { text: (modelData.type === "musique" ? "Musique" : "Voix") + " · " + modelData.nom + (modelData.outil ? " · " + modelData.outil : ""); width: parent.width
                                    font.weight: Font.DemiBold }
                                Droits { type: modelData.type; element: modelData }
                            }
                        }
                        Row {
                            spacing: 6
                            Champ { id: nomMusique; width: 386; nom: "nom_musique"; libelle: "Nom d'une musique" }
                            Bouton { objectName: "ajouter_musique"; texte: "Ajouter"; actif: nomMusique.texte.trim() !== ""
                                     onClic: { pont.agir("ajouter_element", {id: session, corps: {type: "musique", nom: nomMusique.texte, description: "", role: ""}}); nomMusique.texte = "" } }
                        }
                    }
                    Panneau {
                        visible: onglet === "univers"; titre: "Langues et voix"
                        Repeater {
                            model: onglet === "univers" ? univers.langues : []
                            T { text: modelData.code + " · " + modelData.nom + " · " + (modelData.outil_voix || "voix de la session") + (modelData.voix_validee ? "" : " (voix à valider)")
                                width: parent.width; color: modelData.voix_validee ? cTexte : cAttention }
                        }
                        T { text: "Une voix se choisit au banc, à l'aveugle (écran Outils)."; color: cSecond; font.pixelSize: 12; width: parent.width }
                    }
                    Panneau {
                        visible: onglet === "univers"; titre: "Historique"
                        T { visible: !historique.length; text: "Aucun changement depuis la création de la session."; color: cSecond }
                        Repeater {
                            model: onglet === "univers" ? historique.slice(0, 30) : []
                            Row {
                                spacing: 12; width: parent.width
                                Mono { text: modelData.date; color: cSecond; font.pixelSize: 12 }
                                T { text: modelData.acteur + " : " + modelData.quoi; width: parent.width - 160; font.pixelSize: 12 }
                            }
                        }
                    }

                    // ---- Calendrier et idées ----
                    Row {
                        visible: onglet === "calendrier"
                        spacing: 8
                        Bouton { objectName: "cal_avant"; texte: "◀"; onClic: deplacerCal(-1) }
                        T { objectName: "titre_calendrier"; text: titreCal(); font.pixelSize: 20; font.weight: Font.DemiBold; width: 230; horizontalAlignment: Text.AlignHCenter
                            anchors.verticalCenter: parent.verticalCenter; wrapMode: Text.NoWrap }
                        Bouton { objectName: "cal_apres"; texte: "▶"; onClic: deplacerCal(1) }
                        Item { width: 8; height: 1 }
                        Bouton { objectName: "cal_mois"; texte: "Mois" + (vueCal === "mois" ? " ✓" : ""); onClic: { vueCal = "mois"; chargerCal() } }
                        Bouton { objectName: "cal_semaine"; texte: "Semaine" + (vueCal === "semaine" ? " ✓" : ""); onClic: { vueCal = "semaine"; chargerCal() } }
                        Bouton { objectName: "cal_tout"; texte: "Toutes les sessions" + (calTout ? " ✓" : ""); onClic: { calTout = !calTout; chargerCal() } }
                    }
                    Grid {
                        visible: onglet === "calendrier"
                        columns: 7; spacing: 4
                        Repeater {
                            model: ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
                            T { text: modelData; width: (pileSession.width - 24) / 7; color: cSecond; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter }
                        }
                        Repeater {
                            model: onglet === "calendrier" ? joursCal() : []
                            Rectangle {
                                id: caseJour
                                objectName: "jour_" + modelData.iso
                                property string jour: modelData.iso
                                width: (pileSession.width - 24) / 7; height: vueCal === "mois" ? 92 : 260; radius: 6; clip: true
                                color: modelData.iso === aujourdhui() ? cTrait : cLeve; opacity: modelData.dedans ? 1 : 0.4
                                Column {
                                    x: 6; y: 4; width: parent.width - 12; spacing: 2
                                    Mono { text: modelData.jour; color: cSecond; font.pixelSize: 12 }
                                    Repeater {
                                        model: calendrier.filter(e => e.date === caseJour.jour)
                                        T { text: (calTout ? modelData.session_nom + " · " : "") + modelData.titre; width: parent.width; elide: Text.ElideRight
                                            wrapMode: vueCal === "semaine" ? Text.Wrap : Text.NoWrap; maximumLineCount: 3; font.pixelSize: 12; color: couleurStatut(modelData.statut)
                                            Accessible.name: modelData.titre + ", " + modelData.statut_nom + (modelData.pret_vers ? ", prête vers le " + modelData.pret_vers : "") }
                                    }
                                }
                            }
                        }
                    }
                    Flow {
                        visible: onglet === "calendrier"
                        width: parent.width; spacing: 16
                        Repeater {
                            model: [["prete", "prête"], ["fabrication", "en fabrication, à vérifier"], ["approuvee", "approuvée, programmée"], ["publiee", "publiée, suivie"],
                                    ["reportee", "reportée (ordre strict), script à corriger (règles)"], ["idee", "idée, fiche du calendrier éditorial"]]
                            T { text: "■ " + modelData[1]; color: couleurStatut(modelData[0]); font.pixelSize: 12; wrapMode: Text.NoWrap }
                        }
                    }
                    Panneau {
                        visible: onglet === "calendrier" && calendrier.some(e => e.pret_vers !== "")
                        titre: "Dans la file"
                        Repeater {
                            model: onglet === "calendrier" ? calendrier.filter(e => e.pret_vers !== "") : []
                            T { text: modelData.titre + " (" + modelData.session_nom + ") : prête vers le " + modelData.pret_vers; width: parent.width }
                        }
                    }
                    Panneau {
                        visible: onglet === "calendrier" && !calTout
                        titre: "Idées"
                        Row {
                            spacing: 8; width: parent.width
                            Champ { id: champIdee; nom: "champ_idee"; libelle: "Une idée de vidéo (titre)"; width: parent.width - 110 }
                            Bouton { objectName: "ajouter_idee"; texte: "Ajouter"; actif: champIdee.texte.trim() !== ""
                                     onClic: { pont.agir("ajouter_idee", {id: session, corps: {titre: champIdee.texte, resume: "", source: ""}}); champIdee.texte = "" } }
                        }
                        T { visible: !idees.length; text: "Aucune idée pour l'instant ; Claude peut aussi en déposer."; color: cSecond; width: parent.width }
                        Repeater {
                            model: onglet === "calendrier" ? idees : []
                            Row {
                                spacing: 8; width: parent.width
                                Bouton { objectName: "idee_script_" + index; visible: modelData.statut !== "convertie"; texte: "En faire un script"
                                         onClic: pont.agir("creer_script", {id: session, corps: {titre: "", date: "", idee: modelData.id}}) }
                                T { text: modelData.titre + (modelData.resume ? " — " + modelData.resume : "") + "  (" + modelData.source + ", " + modelData.creee
                                          + (modelData.statut === "convertie" ? ", devenue un script" : "") + ")"; width: parent.width - 180; anchors.verticalCenter: parent.verticalCenter
                                    color: modelData.statut === "nouvelle" ? cTexte : cSecond }
                            }
                        }
                    }

                    // ---- Formats ----
                    T { visible: onglet === "formats"; width: parent.width; color: cSecond
                        text: "Les formats du catalogue ; « Fabriquer » prend celui par défaut. Les nouveaux formats arrivent au fil des versions." }
                    Repeater {
                        model: onglet === "formats" ? formats : []
                        Rectangle {
                            objectName: "format_" + modelData.id
                            property bool utilise: reglages.formats.indexOf(modelData.id) >= 0
                            width: parent.width; height: colFormat.implicitHeight + 20; radius: 6; color: cLeve
                            border.width: reglages.format === modelData.id ? 1 : 0; border.color: cAccent
                            Column {
                                id: colFormat
                                x: 12; y: 10; width: parent.width - 24; spacing: 6
                                T { text: modelData.nom + "  ·  " + modelData.id + " v" + modelData.version; font.weight: Font.DemiBold; width: parent.width }
                                T { text: modelData.etapes.map(e => e.id + " (" + e.brique + ")").join("  →  "); color: cSecond; font.pixelSize: 12; width: parent.width }
                                Row {
                                    spacing: 8
                                    Bouton { objectName: "utiliser_" + modelData.id; texte: parent.parent.parent.utilise ? "Utilisé par la session ✓" : "Utiliser dans la session"
                                             onClic: basculerFormat(modelData.id) }
                                    Bouton { objectName: "par_defaut_" + modelData.id; visible: parent.parent.parent.utilise; texte: reglages.format === modelData.id ? "Par défaut ✓" : "Par défaut"
                                             onClic: pont.agir("ecrire_reglages", {id: session, corps: {format: modelData.id}}) }
                                }
                            }
                        }
                    }

                    // ---- Destinations (une chaîne par langue) ----
                    Panneau {
                        visible: onglet === "destinations"
                        titre: "Destinations"
                        T { text: "Une chaîne YouTube par langue ; une langue sans chaîne reliée est fabriquée, pas envoyée. Relier ouvre la page de Google dans le navigateur."
                            color: cSecond; width: parent.width }
                        T { visible: destinations.length === 0; text: "Aucune destination pour cette session (la session « Essais » ne publie jamais)."; color: cSecond; width: parent.width }
                        Repeater {
                            model: onglet === "destinations" ? destinations : []
                            Rectangle {
                                width: parent.width; height: 48; radius: 6; color: cLeve
                                Mono { text: modelData.langue; x: 12; width: 40; anchors.verticalCenter: parent.verticalCenter }
                                T { text: modelData.reliee ? modelData.chaine + "  ·  depuis le " + modelData.depuis + "  ·  " + modelData.playlists.length + " playlist(s)" : modelData.etat
                                    x: 60; width: parent.width - 330; elide: Text.ElideRight; wrapMode: Text.NoWrap; color: modelData.reliee ? cTexte : cAttention; anchors.verticalCenter: parent.verticalCenter }
                                Row {
                                    anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                                    Bouton { visible: modelData.reliee; texte: "Rafraîchir"; onClic: pont.agir("rafraichir", {id: session, langue: modelData.langue}) }
                                    Bouton { objectName: "relier_" + modelData.langue; texte: modelData.reliee ? "Relier à nouveau" : "Relier"; onClic: pont.lire("relier", {id: session, langue: modelData.langue}) }
                                }
                            }
                        }
                        T { objectName: "releve"; width: parent.width; font.pixelSize: 13; color: etat.releve.etat === "erreur" ? cDefaut : cSecond
                            text: etat.releve.etat === "fait" ? "Statistiques relevées le " + etat.releve.fin.slice(8, 10) + "/" + etat.releve.fin.slice(5, 7) + " à " + etat.releve.fin.slice(11, 16) + " (chaque jour après 9 h)."
                                  : etat.releve.etat === "erreur" ? "Relevé des statistiques reporté d'une heure : " + etat.releve.message : "Statistiques relevées chaque jour après 9 h." }
                    }

                    // ---- Règles de la session et sa vie ----
                    Panneau {
                        visible: onglet === "regles"
                        titre: "Règles"
                        T { text: "Ce qui rend chaque vidéo différente (histoire, personnages) : sans cela, « Fabriquer » est refusé — YouTube écarte le « contenu en série sur gabarit »."
                            color: reglages.difference ? cSecond : cAttention; width: parent.width; font.pixelSize: 12 }
                        Champ { etiquette: true; id: rDiff; nom: "regle_difference"; libelle: "Ce qui rend chaque vidéo différente" }
                        Row {
                            spacing: 8; width: parent.width
                            Champ { etiquette: true; id: rPublic; nom: "regle_public"; libelle: "Public"; width: (parent.width - 8) / 2 }
                            Champ { etiquette: true; id: rPromesse; nom: "regle_promesse"; libelle: "Promesse"; width: (parent.width - 8) / 2 }
                        }
                        Row {
                            spacing: 8; width: parent.width
                            Champ { etiquette: true; id: rMin; nom: "regle_duree_min"; libelle: "Durée minimale (min)"; width: 200 }
                            Champ { etiquette: true; id: rMax; nom: "regle_duree_max"; libelle: "Durée maximale (min)"; width: 200 }
                            Champ { etiquette: true; id: rPlafond; nom: "regle_plafond"; libelle: "Plafond des outils payants (€ par mois)"; width: parent.width - 416 }
                        }
                        Row {
                            spacing: 8; width: parent.width
                            Champ { etiquette: true; id: rObjectif; nom: "regle_objectif"; libelle: "Objectif"; width: (parent.width - 8) / 2 }
                            Champ { etiquette: true; id: rArret; nom: "regle_arret"; libelle: "Critère d'arrêt"; width: (parent.width - 8) / 2 }
                        }
                        Bouton { objectName: "enregistrer_regles"; texte: "Enregistrer les règles"
                                 onClic: pont.agir("ecrire_reglages", {id: session, corps: {difference: rDiff.texte, public: rPublic.texte, promesse: rPromesse.texte, objectif: rObjectif.texte,
                                                                                         arret: rArret.texte, duree_min: nombre(rMin.texte), duree_max: nombre(rMax.texte),
                                                                                         plafond_eur: nombre(rPlafond.texte) || 0}}) }
                        Flow {
                            width: parent.width; spacing: 8
                            Bouton { objectName: "regle_enfants"; texte: "Conçue pour les enfants" + (reglages.enfants ? " ✓" : "")
                                     onClic: pont.agir("ecrire_reglages", {id: session, corps: {enfants: !reglages.enfants}}) }
                            Bouton { objectName: "regle_ia"; texte: "Déclaration IA" + (reglages.declaration_ia ? " ✓" : "")
                                     onClic: pont.agir("ecrire_reglages", {id: session, corps: {declaration_ia: !reglages.declaration_ia}}) }
                            Bouton { objectName: "regle_ordre"; texte: "Ordre strict (une vidéo pas prête décale les suivantes)" + (reglages.ordre_strict ? " ✓" : "")
                                     onClic: pont.agir("ecrire_reglages", {id: session, corps: {ordre_strict: !reglages.ordre_strict}}) }
                        }
                    }
                    Panneau {
                        visible: onglet === "regles" && !sessionChoisie().essais
                        titre: "Vie de la session"
                        Flow {
                            width: parent.width; spacing: 8
                            Bouton { objectName: "session_pause"; visible: !sessionChoisie().archivee; texte: sessionChoisie().pause ? "Reprendre" : "Mettre en pause"
                                     onClic: pont.agir("agir_session", {id: session, action: sessionChoisie().pause ? "reprendre" : "pause", corps: {nom: ""}}) }
                            Bouton { objectName: "session_exporter"; texte: "Exporter"; onClic: pont.agir("agir_session", {id: session, action: "exporter", corps: {nom: "", videos: false}}) }
                            Bouton { objectName: "session_exporter_videos"; texte: "Exporter avec les vidéos"; onClic: pont.agir("agir_session", {id: session, action: "exporter", corps: {nom: "", videos: true}}) }
                            Bouton { objectName: "session_archiver"; texte: sessionChoisie().archivee ? "Sortir des archives" : "Archiver"
                                     onClic: pont.agir("agir_session", {id: session, action: sessionChoisie().archivee ? "desarchiver" : "archiver", corps: {nom: ""}}) }
                        }
                        Row {
                            spacing: 8; width: parent.width
                            Champ { id: nomCopie; nom: "nom_copie"; libelle: "Nom de la copie ou du modèle"; width: parent.width - 330 }
                            Bouton { objectName: "session_dupliquer"; texte: "Dupliquer"; actif: nomCopie.texte.trim() !== ""
                                     onClic: { pont.agir("agir_session", {id: session, action: "dupliquer", corps: {nom: nomCopie.texte}}); nomCopie.texte = "" } }
                            Bouton { objectName: "session_modele"; texte: "Enregistrer comme modèle"; actif: nomCopie.texte.trim() !== ""
                                     onClic: { pont.agir("agir_session", {id: session, action: "modele", corps: {nom: nomCopie.texte}}); nomCopie.texte = "" } }
                        }
                    }
                }
            }
        }

        Item {
            objectName: "ecran_video"
            visible: ecran === "video"
            anchors.fill: parent
            Column {
                id: enteteVideo
                x: 24; y: 24; width: parent.width - 48; spacing: 12
                Row {
                    spacing: 12
                    Bouton { objectName: "retour_session"; texte: "← Session"; onClic: aller("sessions") }
                    T { text: video.titre; font.pixelSize: 28; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                }
                Mono { text: video.recette + "  ·  " + video.nom; color: cSecond }
                Row {
                    spacing: 8
                    Repeater {
                        model: [{id: "script", nom: "Script"}, {id: "planche", nom: "Planche"}, {id: "fabrication", nom: "Fabrication"}, {id: "verification", nom: "Vérification"},
                                {id: "publication", nom: "Publication"}, {id: "suivi", nom: "Suivi"}]
                        Rectangle {
                            objectName: "onglet_video_" + modelData.id
                            width: nomOngletVideo.implicitWidth + 32; height: 36; radius: 6
                            color: ongletVideo === modelData.id ? cLeve : "transparent"; border.width: 1; border.color: ongletVideo === modelData.id ? cSelection : cTrait
                            T { id: nomOngletVideo; text: modelData.nom; anchors.centerIn: parent; wrapMode: Text.NoWrap }
                            Clic { onTapped: ongletVideo = modelData.id }
                            Accessible.role: Accessible.PageTab; Accessible.name: modelData.nom; Accessible.onPressAction: ongletVideo = modelData.id
                        }
                    }
                }
                Row {
                    visible: ongletVideo === "verification"
                    spacing: 12
                    Bouton { objectName: "refaire_coches"; texte: "Refaire les plans cochés (" + coches.length + ")"; actif: coches.length > 0
                             onClic: { liberer = true; envoiRefaire.start() } }
                    Timer { id: envoiRefaire; interval: 1500; onTriggered: { pont.agir("refaire", {id: session, video: video.id, corps: {plans: coches}}); coches = [] } }
                    T { text: "Seules les pièces des plans cochés, et ce qui en dépend, sont refaites ; l'avant reste à côté."; color: cSecond; wrapMode: Text.NoWrap
                        anchors.verticalCenter: parent.verticalCenter }
                }
            }
            Flickable {
                anchors { left: parent.left; leftMargin: 24; right: parent.right; rightMargin: 24; top: enteteVideo.bottom; topMargin: 12; bottom: parent.bottom }
                contentHeight: pileVideo.height + 24; clip: true
                ScrollBar.vertical: ScrollBar { width: 8; policy: ScrollBar.AsNeeded; contentItem: Rectangle { radius: 4; color: cTrait } }
                Column {
                    id: pileVideo
                    width: Math.min(parent.width - 16, 960); spacing: 8
                    Repeater {
                        model: ongletVideo === "fabrication" ? video.etapes : []
                        Rectangle {
                            width: parent.width; height: ligneEtape.implicitHeight + 20; radius: 6; color: cLeve
                            Column {
                                id: ligneEtape
                                x: 12; y: 10; width: parent.width - 24; spacing: 4
                                Row {
                                    spacing: 12
                                    T { text: modelData.id; font.weight: Font.DemiBold; width: 120; wrapMode: Text.NoWrap }
                                    Mono { text: modelData.finis + "/" + modelData.total; color: modelData.finis === modelData.total ? cReussi : cSecond; width: 60 }
                                    Mono { text: modelData.secondes ? Math.round(modelData.secondes / 60) + " min" : ""; color: cSecond; width: 80 }
                                    T { text: modelData.outils.join(", "); color: cSecond; wrapMode: Text.NoWrap }
                                }
                                T { visible: modelData.erreur !== ""; text: modelData.erreur; color: cDefaut; width: parent.width; font.pixelSize: 12 }
                            }
                        }
                    }
                    Column {
                        visible: ongletVideo === "verification"
                        width: parent.width; spacing: 8
                        Rectangle {
                            visible: video.controle.video !== ""
                            width: parent.width; height: Math.min(width * 9 / 16, f.height * 0.45); radius: 6; color: "black"; clip: true  // les défauts restent visibles sous lui
                            MediaPlayer {
                                id: lecteur
                                objectName: "lecteur"
                                source: video.controle.video !== "" && ecran === "video" && ongletVideo === "verification" && !liberer
                                        ? "file:///" + video.controle.video.replace(/\\/g, "/") : ""
                                videoOutput: sortieVideo
                                audioOutput: AudioOutput {}
                            }
                            VideoOutput { id: sortieVideo; anchors.fill: parent }
                            Clic { onTapped: { parent.forceActiveFocus(); lecteur.playbackState === MediaPlayer.PlayingState ? lecteur.pause() : lecteur.play() } }
                            // au clavier, l'image prise : Espace lit ou arrête, ← et → reculent ou avancent de 5 s
                            Keys.onSpacePressed: lecteur.playbackState === MediaPlayer.PlayingState ? lecteur.pause() : lecteur.play()
                            Keys.onLeftPressed: lecteur.position = Math.max(0, lecteur.position - 5000)
                            Keys.onRightPressed: lecteur.position = Math.min(lecteur.duration, lecteur.position + 5000)
                            Accessible.role: Accessible.Animation; Accessible.name: "Vidéo : Espace lit ou arrête, flèches ± 5 s"
                        }
                        Item {
                            objectName: "frise"
                            visible: video.controle.video !== ""
                            width: parent.width; height: 28
                            Rectangle { y: 12; width: parent.width; height: 4; radius: 2; color: cTrait }
                            Rectangle { y: 12; width: lecteur.duration ? parent.width * lecteur.position / lecteur.duration : 0; height: 4; radius: 2; color: cSelection }
                            Repeater {  // un repère par défaut minuté, à la couleur de sa gravité
                                model: video.controle.defauts.filter(d => d.debut != null)
                                Rectangle { x: lecteur.duration ? parent.width * modelData.debut * 1000 / lecteur.duration - 2 : 0; y: 4; width: 4; height: 20; radius: 2
                                            color: modelData.gravite === "forte" ? cDefaut : modelData.gravite === "moyenne" ? cAttention : cSecond }
                            }
                            Clic { onTapped: (e) => { if (lecteur.duration) lecteur.position = Math.round(lecteur.duration * e.position.x / parent.width) } }
                        }
                        Row {
                            visible: video.controle.video !== ""
                            spacing: 12
                            Bouton { objectName: "lire"; texte: lecteur.playbackState === MediaPlayer.PlayingState ? "Pause" : "Lecture"
                                     onClic: lecteur.playbackState === MediaPlayer.PlayingState ? lecteur.pause() : lecteur.play() }
                            Mono { text: mmss(lecteur.position / 1000) + "," + String(lecteur.position % 1000).padStart(3, "0") + " / " + mmss(lecteur.duration / 1000)
                                   color: cSecond; anchors.verticalCenter: parent.verticalCenter }
                            Repeater {
                                model: [0.5, 1, 1.5, 2]
                                Bouton { objectName: "vitesse_" + index; texte: String(modelData).replace(".", ",") + "×"; onClic: lecteur.playbackRate = modelData }
                            }
                        }
                        T {
                            objectName: "note_controle"
                            width: parent.width
                            text: !video.controle.mesure ? (video.controle.defauts.length ? "Contrôle pas fini : " + video.controle.defauts.length + " défaut(s) déjà relevé(s)"
                                                                                           : "Pas encore contrôlée : le contrôle passe après le montage.")
                                : (video.controle.note != null ? "Note de Qwen : " + String(video.controle.note).replace(".", ",") + "/10  ·  " : "")
                                  + (video.controle.defauts.length ? video.controle.defauts.length + " défaut(s) ; un clic sur l'un va à son moment" : "aucun défaut relevé")
                            color: video.controle.mesure && !video.controle.defauts.length ? cReussi : cSecond
                        }
                        Repeater {
                            model: video.controle.defauts
                            Rectangle {
                                objectName: "defaut_" + index
                                width: parent.width; height: ligneDefaut.implicitHeight + 12; radius: 6; color: cLeve
                                Row {
                                    id: ligneDefaut
                                    x: 12; y: 6; width: parent.width - 24; spacing: 12
                                    Rectangle { width: 10; height: 10; radius: 5; anchors.verticalCenter: parent.verticalCenter
                                                color: modelData.gravite === "forte" ? cDefaut : modelData.gravite === "moyenne" ? cAttention : cSecond }
                                    Mono { text: modelData.debut == null ? "toute" : mmss(modelData.debut); width: 56; color: cSecond }
                                    T { text: modelData.texte; width: parent.width - 220 }
                                    Mono { text: modelData.source; color: cSecond; font.pixelSize: 12 }
                                }
                                Clic { enabled: modelData.debut != null && video.controle.video !== ""; onTapped: aller_a(modelData.debut) }
                                Accessible.role: Accessible.Button; Accessible.name: (modelData.debut == null ? "Toute la vidéo" : mmss(modelData.debut)) + " : " + modelData.texte
                                Accessible.onPressAction: if (modelData.debut != null && video.controle.video !== "") aller_a(modelData.debut)
                            }
                        }
                        T { text: "Plans à refaire"; font.pixelSize: 18; font.weight: Font.DemiBold; topPadding: 8 }
                    }
                    Repeater {
                        model: ongletVideo === "verification" ? video.plans : []
                        Rectangle {
                            objectName: "plan_" + index
                            width: parent.width; height: 44; radius: 6; color: coches.indexOf(modelData.n) >= 0 ? cTrait : cLeve
                            border.width: coches.indexOf(modelData.n) >= 0 ? 1 : 0; border.color: cSelection
                            Rectangle {
                                x: 12; anchors.verticalCenter: parent.verticalCenter; width: 18; height: 18; radius: 4; color: "transparent"; border.width: 2
                                border.color: coches.indexOf(modelData.n) >= 0 ? cSelection : cSecond
                                Rectangle { anchors.centerIn: parent; width: 8; height: 8; radius: 2; color: cSelection; visible: coches.indexOf(modelData.n) >= 0 }
                            }
                            Mono { text: "plan " + modelData.n; x: 44; anchors.verticalCenter: parent.verticalCenter }
                            T { text: modelData.image || "Bramble parle face caméra"; x: 130; width: parent.width - 260; anchors.verticalCenter: parent.verticalCenter
                                elide: Text.ElideRight; wrapMode: Text.NoWrap; color: modelData.image ? cTexte : cSecond }
                            Mono { text: modelData.scenes.length + " scène(s)"; color: cSecond; anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter }
                            Clic { onTapped: cocher(modelData.n) }
                            Accessible.role: Accessible.CheckBox; Accessible.name: "Plan " + modelData.n; Accessible.checked: coches.indexOf(modelData.n) >= 0
                            Accessible.onPressAction: cocher(modelData.n)
                        }
                    }
                    Column {
                        objectName: "onglet_publication"
                        visible: ongletVideo === "publication"
                        width: parent.width; spacing: 8
                        T { visible: publications.length === 0; text: "Pas encore approuvée : « Approuver » prépare un brouillon par langue ; rien ne part avant « Publier »."; color: cSecond; width: parent.width }
                        Bouton { objectName: "bouton_approuver"; visible: publications.length === 0; texte: "Approuver"
                                 actif: video.etapes.length > 0 && video.etapes.every(e => e.finis === e.total); onClic: pont.agir("approuver", {id: session, video: video.id}) }
                        Repeater {
                            model: publications
                            Rectangle {
                                id: carte
                                property var p: modelData
                                property bool modifiable: ["brouillon", "erreur"].indexOf(p.statut) >= 0 && p.lien === ""
                                width: parent.width; height: colPub.implicitHeight + 24; radius: 6; color: cLeve
                                Column {
                                    id: colPub
                                    x: 12; y: 12; width: parent.width - 24; spacing: 6
                                    Row {
                                        spacing: 12
                                        T { text: p.langue + "  ·  " + p.statut; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                                        T { text: p.chaine !== "" ? p.chaine : "chaîne : " + p.destination; color: p.destination === "reliée" ? cReussi : cAttention; wrapMode: Text.NoWrap }
                                        Mono { text: p.versions + " version(s) du texte"; color: cSecond; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                                    }
                                    Champ { id: titrePub; nom: "titre_" + index; libelle: "Titre (" + p.langue + ")"; texte: p.titre }
                                    Rectangle {
                                        width: parent.width; height: Math.min(Math.max(descPub.implicitHeight + 16, 80), 220); radius: 6; color: cFond; border.width: 1; border.color: descPub.activeFocus ? cSelection : cTrait; clip: true
                                        TextEdit { id: descPub; objectName: "description_" + index; anchors.fill: parent; anchors.margins: 8; text: p.description; color: cTexte; font.family: "Segoe UI Variable"; font.pixelSize: 13
                                                   wrapMode: TextEdit.Wrap; selectByMouse: true; Accessible.name: "Description (" + p.langue + ")" }
                                    }
                                    Bouton { objectName: "retoucher_" + index; texte: "Enregistrer le texte (nouvelle version)"; visible: carte.modifiable
                                             actif: titrePub.texte !== p.titre || descPub.text !== p.description
                                             onClic: pont.agir("retoucher", {id: session, pub: p.id, corps: {titre: titrePub.texte, description: descPub.text}}) }
                                    Image { visible: status === Image.Ready; source: p.miniature !== "" ? "file:///" + p.miniature.replace(/\\/g, "/") : ""
                                            width: 192; height: 108; fillMode: Image.PreserveAspectFit; asynchronous: true; cache: false }
                                    T { width: parent.width; color: cSecond; font.pixelSize: 13
                                        text: (p.non_repertorie ? "Part en non répertorié (première vidéo de la chaîne, ou vidéo d'essai)" : "En privé, publique le " + p.creneau)
                                              + "  ·  " + (p.non_repertorie ? "sans playlist (non répertorié)" : p.playlist_titre !== "" ? "playlist : " + p.playlist_titre : "sans playlist")
                                              + "  ·  pour enfants : " + (p.enfants ? "oui" : "non")
                                              + "  ·  IA déclarée : " + (p.ia ? "oui" : "non") + (p.chapitres.length ? "  ·  " + p.chapitres.length + " chapitres" : "") }
                                    Flow {
                                        visible: carte.modifiable && p.miniatures.length > 0; width: parent.width; spacing: 6
                                        T { text: "Miniature :"; color: cSecond; wrapMode: Text.NoWrap; height: 32; verticalAlignment: Text.AlignVCenter }
                                        Repeater { model: p.miniatures; Bouton { texte: modelData + (p.miniature !== "" && nomDe(p.miniature) === modelData ? " ✓" : "")
                                                                                 onClic: pont.agir("choisir", {id: session, pub: p.id, corps: {miniature: modelData}}) } }
                                    }
                                    Flow {
                                        visible: carte.modifiable && !p.non_repertorie && chaineDe(p.langue).playlists.length > 0; width: parent.width; spacing: 6
                                        T { text: "Playlist :"; color: cSecond; wrapMode: Text.NoWrap; height: 32; verticalAlignment: Text.AlignVCenter }
                                        Bouton { texte: "aucune" + (p.playlist === "" ? " ✓" : ""); onClic: pont.agir("choisir", {id: session, pub: p.id, corps: {playlist: ""}}) }
                                        Repeater { model: chaineDe(p.langue).playlists; Bouton { texte: modelData.titre + (p.playlist === modelData.id ? " ✓" : "")
                                                                                                onClic: pont.agir("choisir", {id: session, pub: p.id, corps: {playlist: modelData.id}}) } }
                                    }
                                    Row {
                                        visible: carte.modifiable && !p.non_repertorie; spacing: 6
                                        T { text: "Créneau :"; color: cSecond; wrapMode: Text.NoWrap; height: 32; verticalAlignment: Text.AlignVCenter }
                                        Champ { id: jourPub; width: 120; libelle: "Jour (AAAA-MM-JJ)"; texte: p.creneau ? p.creneau.slice(6, 10) + "-" + p.creneau.slice(3, 5) + "-" + p.creneau.slice(0, 2) : "" }
                                        Champ { id: heurePub; width: 70; libelle: "Heure (HH:MM)"; texte: p.creneau.slice(11, 16) }
                                        Bouton { texte: "Changer le créneau"; onClic: pont.agir("choisir", {id: session, pub: p.id, corps: {jour: jourPub.texte, horaire: heurePub.texte}}) }
                                    }
                                    Repeater { model: p.fautes; T { text: "✗ " + modelData; color: cDefaut; width: parent.width } }
                                    Repeater { model: p.avis; T { text: "• " + modelData; color: cSecond; width: parent.width; font.pixelSize: 13 } }
                                    T { visible: p.envoi !== ""; text: "Envoi : " + p.envoi; color: cSecond; width: parent.width }
                                    T { visible: p.erreur !== ""; text: p.erreur; color: cDefaut; width: parent.width }
                                    T { visible: p.lien !== ""; text: p.lien; color: cSelection; width: parent.width
                                        Clic { onTapped: Qt.openUrlExternally(p.lien) } }
                                    Row {
                                        spacing: 8
                                        Bouton { objectName: "publier_" + index; ambre: true; visible: carte.modifiable || p.statut === "erreur"
                                                 actif: p.fautes.length === 0 && p.destination === "reliée" && titrePub.texte === p.titre && descPub.text === p.description  // un texte retouché s'enregistre d'abord
                                                 texte: p.statut === "erreur" ? "Reprendre l'envoi" : "Publier"; onClic: aPublier = p.id }
                                        Bouton { visible: p.statut === "en_file"; texte: "Annuler l'envoi"; onClic: pont.agir("publier", {id: session, pub: p.id, action: "annuler"}) }
                                    }
                                    Rectangle {
                                        visible: aPublier === p.id
                                        width: parent.width; height: confPub.implicitHeight + 24; radius: 6; color: cPanneau; border.width: 1; border.color: cAccent
                                        Column {
                                            id: confPub
                                            x: 12; y: 12; width: parent.width - 24; spacing: 12
                                            T { width: parent.width; text: (p.statut === "erreur" ? "Reprendre l'envoi de « " : "Publier « ") + p.titre + " » (" + p.langue + ") sur « " + p.chaine + " », "
                                                + (p.non_repertorie ? "en non répertorié ?" : "en privé, publique le " + p.creneau + " ?") }
                                            Row {
                                                spacing: 8
                                                Bouton { objectName: "confirmer_publier_" + index; ambre: true; texte: p.statut === "erreur" ? "Reprendre l'envoi" : "Publier"
                                                         onClic: { pont.agir("publier", {id: session, pub: p.id, action: p.statut === "erreur" ? "reprendre" : "publier"}); aPublier = -1 } }
                                                Bouton { texte: "Annuler"; onClic: aPublier = -1 }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        Row {
                            visible: publications.length > 0; spacing: 12
                            T { text: "Paquets prêts à poster"; font.pixelSize: 18; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                            Bouton { objectName: "refaire_paquets"; texte: "Refaire les paquets"; onClic: pont.agir("refaire_paquets", {id: session, video: video.id}) }
                        }
                        Repeater {
                            model: paquets
                            Rectangle {
                                id: lignePaquet
                                property var q: modelData
                                width: parent.width; height: colPaquet.implicitHeight + 20; radius: 6; color: cLeve
                                Column {
                                    id: colPaquet
                                    x: 12; y: 10; width: parent.width - 24; spacing: 4
                                    Row {
                                        spacing: 12
                                        T { text: modelData.nom + "  ·  " + modelData.langue; font.weight: Font.DemiBold; wrapMode: Text.NoWrap; width: 260 }
                                        T { text: modelData.etat; color: modelData.etat === "fait" ? cReussi : modelData.etat === "erreur" ? cDefaut : cSecond; wrapMode: Text.NoWrap; width: 90 }
                                        Mono { text: modelData.fichiers.map(x => Math.round(x.duree_s) + " s · " + String(x.poids_mo).replace(".", ",") + " Mo").join("   "); color: cSecond; font.pixelSize: 12 }
                                    }
                                    T { visible: modelData.raison !== ""; text: modelData.raison; color: modelData.etat === "erreur" ? cDefaut : cSecond; width: parent.width; font.pixelSize: 13 }
                                    Row {
                                        visible: modelData.etat === "fait"; spacing: 8
                                        Bouton { objectName: "dossier_paquet_" + index; texte: "Ouvrir le dossier"; onClic: Qt.openUrlExternally("file:///" + modelData.dossier.replace(/\\/g, "/")) }
                                        Repeater { model: lignePaquet.q.textes; Bouton { objectName: "copier_" + lignePaquet.q.reseau + "_" + index; texte: "Copier le texte" + (lignePaquet.q.textes.length > 1 ? " " + (index + 1) : "")
                                                                                   onClic: copier(modelData.titre ? modelData.titre + "\n\n" + modelData.texte : modelData.texte) } }
                                    }
                                }
                            }
                        }
                    }
                    T { visible: ongletVideo === "planche" && !video.plans.length; text: "Ce format n'a pas de planche des plans."; color: cSecond }
                    Repeater {
                        model: ongletVideo === "planche" ? video.plans : []
                        Rectangle {
                            width: parent.width; height: lignePlanche.implicitHeight + 16; radius: 6; color: cLeve
                            Column {
                                id: lignePlanche
                                x: 12; y: 8; width: parent.width - 24; spacing: 2
                                Mono { text: "plan " + modelData.n + "  ·  scène(s) " + modelData.scenes.join(", "); color: cSecond; font.pixelSize: 12 }
                                T { text: modelData.bramble ? "Pose du narrateur" : modelData.image; width: parent.width; color: modelData.bramble ? cSecond : cTexte }
                            }
                        }
                    }
                    T { visible: ongletVideo === "suivi" && !suivi.length; text: "Pas encore publiée : le suivi commence au premier relevé après la publication."; color: cSecond; width: parent.width }
                    Repeater {
                        model: ongletVideo === "suivi" ? suivi : []
                        Panneau {
                            id: panneauSuivi
                            property var sv: modelData
                            titre: sv.langue + " · " + sv.titre
                            Row {
                                spacing: 24
                                T { text: ({brouillon: "brouillon", en_file: "dans la file d'envoi", envoi: "envoi en cours", erreur: "envoi en erreur", planifiee: "programmée",
                                            non_repertoriee: "non répertoriée"})[sv.statut] || sv.statut; color: cSecond; wrapMode: Text.NoWrap }
                                Mono { text: sv.vues + " vues" }
                                Mono { text: String(sv.heures).replace(".", ",") + " h regardées" }
                                Mono { text: "+" + sv.abonnes + " abonnés" }
                                T { visible: sv.lien !== ""; text: sv.lien; color: cSelection; wrapMode: Text.NoWrap
                                    Clic { onTapped: Qt.openUrlExternally(panneauSuivi.sv.lien) } }
                            }
                            Row {
                                visible: sv.jours.length > 0
                                height: 80; spacing: 3
                                Repeater {
                                    model: panneauSuivi.sv.jours
                                    Rectangle {
                                        width: 14; anchors.bottom: parent.bottom; radius: 2; color: cSelection
                                        height: Math.max(2, 78 * modelData.vues / Math.max(1, Math.max.apply(null, panneauSuivi.sv.jours.map(j => j.vues))))
                                        Accessible.name: modelData.date + " : " + modelData.vues + " vues"
                                    }
                                }
                            }
                            T { visible: sv.jours.length > 0; text: "Vues par jour, " + sv.jours[0].date + " → " + sv.jours[sv.jours.length - 1].date + " (YouTube les donne avec 2 à 3 jours de retard)."
                                color: cSecond; font.pixelSize: 12 }
                        }
                    }
                    Repeater {
                        model: ongletVideo === "script" ? (video.script.scenes || []) : []
                        Rectangle {
                            width: parent.width; height: ligneScene.implicitHeight + 16; radius: 6; color: cLeve
                            Column {
                                id: ligneScene
                                x: 12; y: 8; width: parent.width - 24; spacing: 2
                                Mono { text: "scène " + modelData.id + (modelData.bramble ? "  ·  Bramble : " + modelData.bramble : ""); color: cSecond; font.pixelSize: 12 }
                                T { text: modelData.narration || ""; width: parent.width }
                            }
                        }
                    }
                }
            }
        }

        Item {
            objectName: "ecran_script"
            visible: ecran === "script"
            anchors.fill: parent
            Column {
                id: enteteScript
                x: 24; y: 24; width: parent.width - 48; spacing: 12
                Row {
                    spacing: 12
                    Bouton { objectName: "retour_scripts"; texte: "← Session"; onClic: aller("sessions") }
                    T { text: script.titre; font.pixelSize: 28; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                }
                Row {
                    spacing: 8
                    Champ { id: dateDuScript; width: 200; etiquette: true; nom: "date_du_script"; libelle: "Date prévue (AAAA-MM-JJ)"; texte: script.date_prevue }
                    Bouton { anchors.bottom: parent.bottom; objectName: "dater_script"; texte: dateDuScript.texte.trim() ? "Dater" : "Retirer du calendrier"
                             onClic: pont.agir("dater_script", {id: session, code: script.code, corps: {date: dateDuScript.texte.trim()}}) }
                }
                Mono { text: script.code + "  ·  " + (script.date_prevue || "pas encore au calendrier") + "  ·  version " + (script.versions.length ? script.versions[0].numero : "—")
                       + (script.versions.length ? " (" + script.versions[0].auteur + ")" : ""); color: cSecond }
                Row {
                    spacing: 12
                    Rectangle {
                        objectName: "bouton_fabriquer"
                        property bool actif: !(script.regles.erreurs || []).length && !script.estimation.refus && script.versions.length > 0 && !brouillon
                        width: tfs.implicitWidth + 32; height: 32; radius: 6; color: actif ? cAccent : cLeve; opacity: actif ? 1 : 0.5
                        T { id: tfs; text: "Fabriquer"; color: parent.actif ? cFond : cSecond; font.weight: Font.DemiBold; anchors.centerIn: parent; wrapMode: Text.NoWrap }
                        Clic { enabled: parent.actif; onTapped: aFabriquer = script.code }
                        Accessible.role: Accessible.Button; Accessible.name: "Fabriquer " + script.titre; Accessible.onPressAction: if (actif) aFabriquer = script.code
                    }
                    T { anchors.verticalCenter: parent.verticalCenter; wrapMode: Text.NoWrap
                        text: script.estimation.refus ? script.estimation.refus
                            : (script.regles.erreurs || []).length ? "Les règles de l'univers bloquent la fabrication : à corriger d'abord."
                            : "Environ " + duree(script.estimation.secondes) + ", " + String(script.estimation.cout_eur.toFixed(2)).replace(".", ",") + " €"
                        color: script.estimation.refus || (script.regles.erreurs || []).length ? cDefaut : cSecond }
                }
                Flow {
                    visible: brouillon !== null
                    width: parent.width; spacing: 8
                    Bouton { objectName: "enregistrer_version"; texte: "Enregistrer comme nouvelle version"
                             onClic: { aControler.stop(); pont.agir("nouvelle_version", {id: session, code: script.code, corps: {contenu: brouillon}}) } }
                    Bouton { objectName: "abandonner_brouillon"; texte: "Abandonner les changements"; onClic: { aControler.stop(); brouillon = null } }
                    T { text: (controler.erreurs || []).length ? "Les règles signalent " + controler.erreurs.length + " erreur(s) : la version s'enregistre, la fabrication attendra."
                              : "Les règles sont rejouées pendant la frappe."; color: (controler.erreurs || []).length ? cDefaut : cSecond
                        wrapMode: Text.NoWrap; height: 32; verticalAlignment: Text.AlignVCenter }
                }
                Flow {
                    visible: brouillon === null
                    width: parent.width; spacing: 8
                    Bouton { objectName: "modifier_script"; texte: "Modifier le script"; actif: script.versions.length > 0; onClic: ecrire() }
                    Bouton { objectName: "demander_ecrire"; texte: "Demander à Claude une nouvelle version"; onClic: pont.agir("demander", {id: session, code: script.code, corps: {quoi: "ecrire", langue: ""}}) }
                    Repeater {
                        model: univers.langues.filter(l => l.code !== (script.contenu.language || "en"))
                        Bouton { objectName: "traduire_" + modelData.code; texte: "Traduire en " + modelData.code
                                 onClic: pont.agir("demander", {id: session, code: script.code, corps: {quoi: "traduire", langue: modelData.code}}) }
                    }
                }
                Rectangle {
                    visible: aFabriquer !== "" && aFabriquer === script.code
                    width: parent.width; height: confFabriquerScript.implicitHeight + 24; radius: 6; color: cLeve; border.width: 1; border.color: cAccent
                    Column {
                        id: confFabriquerScript
                        x: 12; y: 12; width: parent.width - 24; spacing: 12
                        T { text: "Fabriquer « " + script.titre + " » (environ " + duree(script.estimation.secondes) + ") ? La vidéo entre dans la file ; elle part quand la carte est libre."
                            width: parent.width }
                        Flow {
                            visible: script.traductions.length > 0
                            width: parent.width; spacing: 8
                            T { text: "Aussi en :"; color: cSecond; wrapMode: Text.NoWrap; height: 32; verticalAlignment: Text.AlignVCenter }
                            Repeater {
                                model: script.traductions
                                Rectangle {
                                    objectName: "langue_" + modelData
                                    width: tl.implicitWidth + 24; height: 32; radius: 6
                                    color: langues.indexOf(modelData) >= 0 ? cTrait : "transparent"; border.width: 1; border.color: langues.indexOf(modelData) >= 0 ? cSelection : cTrait
                                    T { id: tl; text: modelData; anchors.centerIn: parent; wrapMode: Text.NoWrap }
                                    Clic { onTapped: basculer(modelData) }
                                    Accessible.role: Accessible.CheckBox; Accessible.name: "Langue " + modelData; Accessible.checked: langues.indexOf(modelData) >= 0
                                    Accessible.onPressAction: basculer(modelData)
                                }
                            }
                        }
                        Row {
                            spacing: 8
                            Rectangle {
                                objectName: "confirmer_fabriquer"
                                width: tcf.implicitWidth + 32; height: 32; radius: 6; color: cAccent
                                T { id: tcf; text: "Fabriquer"; color: cFond; font.weight: Font.DemiBold; anchors.centerIn: parent; wrapMode: Text.NoWrap }
                                Clic { onTapped: { pont.agir("fabriquer", {id: session, code: aFabriquer, corps: {langues: langues, version: script.versions[0].numero}}); aFabriquer = "" } }
                                Accessible.role: Accessible.Button; Accessible.name: "Confirmer : fabriquer " + script.titre
                                Accessible.onPressAction: { pont.agir("fabriquer", {id: session, code: aFabriquer, corps: {langues: langues, version: script.versions[0].numero}}); aFabriquer = "" }
                            }
                            Bouton { texte: "Annuler"; onClic: aFabriquer = "" }
                        }
                    }
                }
            }
            Flickable {
                anchors { left: parent.left; leftMargin: 24; right: parent.right; rightMargin: 24; top: enteteScript.bottom; topMargin: 12; bottom: parent.bottom }
                contentHeight: pileScript.height + 24; clip: true
                ScrollBar.vertical: ScrollBar { width: 8; policy: ScrollBar.AsNeeded; contentItem: Rectangle { radius: 4; color: cTrait } }
                Column {
                    id: pileScript
                    width: Math.min(parent.width - 16, 960); spacing: 12
                    Panneau {
                        titre: "Règles de l'univers"
                        T { visible: !(regles().erreurs || []).length && !(regles().avis || []).length; text: "Aucune erreur, aucun avis."; color: cReussi; width: parent.width }
                        Repeater { model: regles().erreurs || []; T { text: "[" + modelData[0] + "] " + modelData[1]; color: cDefaut; width: parent.width } }
                        Repeater { model: regles().avis || []; T { text: "[" + modelData[0] + "] " + modelData[1]; color: cAttention; width: parent.width } }
                    }
                    Panneau {
                        visible: script.plans.length > 0
                        titre: "Planche : " + script.plans.length + " plans"
                        Repeater {
                            model: script.plans
                            Row {
                                spacing: 12
                                Mono { text: "plan " + modelData.n; color: cSecond; width: 70 }
                                T { text: modelData.image || "Bramble parle face caméra"; width: pileScript.width - 200; color: modelData.image ? cTexte : cSecond }
                                Mono { text: modelData.scenes.length + " sc."; color: cSecond }
                            }
                        }
                    }
                    Panneau {
                        visible: brouillon !== null
                        titre: "Scènes (écriture)"
                        Timer { id: aControler; interval: 600; onTriggered: if (brouillon) pont.lire("controler", {id: session, code: script.code, corps: {contenu: brouillon}}) }
                        Repeater {
                            model: brouillon ? brouillon.scenes || [] : []  // le brouillon est changé sur place : la liste n'est pas refaite pendant la frappe
                            Column {
                                width: parent.width; spacing: 4
                                property int scene: index
                                property string sceneId: modelData.id
                                Mono { text: "scène " + modelData.id + (modelData.bramble ? "  ·  Bramble : " + modelData.bramble : ""); color: cSecond; font.pixelSize: 12 }
                                Repeater {
                                    model: ["narration", "image", "motion"].filter(c => c === "narration" || modelData[c] !== undefined)
                                    Column {
                                      width: parent.width; spacing: 2
                                      property string nomChamp: ({narration: "Narration", image: "Image", motion: "Mouvement"})[modelData]
                                      T { text: parent.nomChamp; color: cSecond; font.pixelSize: 12 }
                                      Rectangle {
                                        width: parent.width; height: Math.max(36, champScene.implicitHeight + 12); radius: 6; color: cLeve
                                        border.width: champScene.activeFocus ? 2 : 1; border.color: champScene.activeFocus ? cSelection : cTrait
                                        TextEdit {
                                            id: champScene
                                            objectName: "champ_" + modelData + "_" + scene
                                            x: 8; y: 6; width: parent.width - 16; wrapMode: TextEdit.Wrap; selectByMouse: true
                                            color: cTexte; selectionColor: cSelection; font.family: "Segoe UI Variable"; font.pixelSize: 14
                                            text: brouillon.scenes[scene][modelData] || ""
                                            onTextChanged: if (brouillon && brouillon.scenes[scene][modelData] !== text) { brouillon.scenes[scene][modelData] = text; aControler.restart() }
                                            Accessible.role: Accessible.EditableText
                                            Accessible.name: parent.parent.nomChamp + " de la scène " + sceneId
                                        }
                                      }
                                    }
                                }
                            }
                        }
                    }
                    Panneau {
                        visible: brouillon === null
                        titre: "Scènes"
                        Repeater {
                            model: script.contenu.scenes || []
                            Column {
                                width: parent.width; spacing: 2
                                Mono { text: "scène " + modelData.id + (modelData.bramble ? "  ·  Bramble : " + modelData.bramble : ""); color: cSecond; font.pixelSize: 12 }
                                T { text: modelData.narration || ""; width: parent.width }
                            }
                        }
                    }
                }
            }
        }

        Flickable {
            objectName: "ecran_outils"
            visible: ecran === "outils"
            anchors.fill: parent; contentHeight: pileOutils.height + 48; clip: true
            ScrollBar.vertical: ScrollBar { width: 8; policy: ScrollBar.AsNeeded; contentItem: Rectangle { radius: 4; color: cTrait } }
            Column {
                id: pileOutils
                x: 24; y: 24; width: Math.min(contenu.width - 48, 960); spacing: 16
                T { text: "Outils"; font.pixelSize: 28; font.weight: Font.DemiBold }
                T { text: "Chaque brique et ses outils. Un outil ne passe en service qu'après un banc à l'aveugle gagné et votre accord ; l'ancien reste disponible."
                    color: cSecond; width: parent.width }
                T { objectName: "installation_en_cours"; visible: outils.installation.etat === "en_cours"; width: parent.width; color: cAttention
                    text: "Installation en cours : " + (outils.installation.outil || "") + " (une notification dira quand elle est finie)." }
                Repeater {
                    model: outils.briques
                    Panneau {
                        id: panneauBrique
                        property var brique: modelData
                        titre: modelData.titre
                        Repeater {
                            model: panneauBrique.brique.outils
                            Rectangle {
                                width: parent.width; height: Math.max(ficheOutil.implicitHeight, actionsOutil.implicitHeight) + 20; radius: 6; color: cLeve
                                border.width: modelData.defaut ? 1 : 0; border.color: cSelection
                                Column {
                                    id: ficheOutil
                                    x: 12; y: 10; width: parent.width - 250; spacing: 4
                                    Row {
                                        spacing: 12
                                        T { text: modelData.nom; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                                        T { text: modelData.defaut ? "par défaut" : modelData.etat_nom; wrapMode: Text.NoWrap
                                            color: modelData.defaut || modelData.etat === "en_service" ? cReussi : modelData.etat === "retire" ? cSecond : cAttention }
                                        T { visible: !modelData.local; text: "en ligne"; color: cSelection; wrapMode: Text.NoWrap }
                                    }
                                    T { width: parent.width; font.pixelSize: 12; color: cSecond
                                        text: [modelData.prix, "licence : " + modelData.licence, modelData.besoins, "langues : " + modelData.langues, "version " + modelData.version].join("  ·  ") }
                                    T { visible: modelData.limites !== ""; text: modelData.limites; width: parent.width; font.pixelSize: 12; color: cSecond }
                                    T { width: parent.width; font.pixelSize: 12; text: "Installation : " + modelData.installation; color: modelData.action !== "" ? cAttention : cSecond }
                                    T { visible: modelData.sessions.length > 0; width: parent.width; font.pixelSize: 12; text: "Outil de : " + modelData.sessions.join(", ") }
                                    T { visible: modelData.dernier_banc !== ""; width: parent.width; font.pixelSize: 12; text: "Dernier banc : " + modelData.dernier_banc }
                                }
                                Column {
                                    id: actionsOutil
                                    anchors.right: parent.right; anchors.rightMargin: 8; y: 10; spacing: 6
                                    Bouton { objectName: "installer_" + modelData.id; visible: modelData.action !== ""; actif: outils.installation.etat !== "en_cours"
                                             texte: modelData.action === "mettre_a_jour" ? "Mettre à jour" : "Installer"
                                             onClic: pont.agir("agir_outil", {outil: modelData.id, action: "installer"}) }
                                    Bouton { objectName: "banc_" + modelData.id; visible: !modelData.defaut && modelData.etat !== "retire"; texte: "Banc contre l'outil en place"
                                             onClic: { banc = bancVide; nouveauBanc = {brique: panneauBrique.brique.id, outil: modelData.id, video: "",
                                                                      juge: panneauBrique.brique.juges.length ? panneauBrique.brique.juges[0].id : ""}; aller("banc") } }
                                    Bouton { objectName: "retirer_" + modelData.id; visible: modelData.etat !== "retire" && !modelData.defaut && !modelData.sessions.length; texte: "Retirer"
                                             onClic: pont.agir("agir_outil", {outil: modelData.id, action: "retirer"}) }
                                    Bouton { objectName: "remettre_" + modelData.id; visible: modelData.etat === "retire"; texte: "Remettre parmi les candidats"
                                             onClic: pont.agir("agir_outil", {outil: modelData.id, action: "remettre"}) }
                                }
                            }
                        }
                    }
                }

                Panneau {
                    titre: "Dépenses des outils en ligne"
                    T { objectName: "depense_du_mois"; width: parent.width
                        text: "Ce mois-ci : " + euros(depenses.depense_mois_eur) + " sur un plafond de " + euros(depenses.plafond_mois_eur)
                              + (depenses.plafond_mois_eur > 0 ? "." : " : aucun outil payant ne sert (chaque session a aussi le sien, dans ses règles).") }
                    Row {
                        spacing: 8
                        Champ { id: champPlafond; width: 280; etiquette: true; nom: "champ_plafond"; libelle: "Plafond du mois, toutes sessions (€)" }
                        Bouton { objectName: "enregistrer_plafond"; anchors.bottom: parent.bottom; texte: "Enregistrer"; actif: nombre(champPlafond.texte) !== null
                                 onClic: pont.agir("plafond", {corps: {valeur: nombre(champPlafond.texte)}}) }
                    }
                    T { visible: !depenses.lignes.length; text: "Aucune dépense."; color: cSecond; width: parent.width }
                    Repeater {
                        model: depenses.lignes.slice(0, 50)
                        Row {
                            spacing: 12
                            Mono { text: modelData.date; color: cSecond; font.pixelSize: 12; width: 130 }
                            T { text: modelData.session; width: 180; font.pixelSize: 12; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                            T { text: modelData.outil; width: 220; font.pixelSize: 12; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                            Mono { text: "estimé " + euros(modelData.estime_eur) + (modelData.reel_eur != null ? "  ·  réel " + euros(modelData.reel_eur) : ""); font.pixelSize: 12 }
                        }
                    }
                }

                Panneau {
                    titre: "Veille du mois"
                    T { text: "Ce que Claude repère chaque mois. Un candidat n'entre en service qu'avec son adaptateur (une version de Fabrique), puis un banc gagné."
                        color: cSecond; width: parent.width }
                    T { visible: !veille.length; text: "Aucun candidat repéré."; color: cSecond; width: parent.width }
                    Repeater {
                        model: veille
                        Rectangle {
                            width: parent.width; height: ligneVeille.implicitHeight + 20; radius: 6; color: cLeve
                            Column {
                                id: ligneVeille
                                x: 12; y: 10; width: parent.width - 260; spacing: 4
                                T { text: modelData.nom + "  ·  " + modelData.brique + "  ·  " + modelData.statut_nom; font.weight: Font.DemiBold; width: parent.width }
                                T { width: parent.width; font.pixelSize: 12; color: modelData.commercial === false ? cDefaut : cSecond
                                    text: "licence : " + (modelData.licence || "?") + "  ·  usage commercial : " + (modelData.commercial === true ? "oui" : modelData.commercial === false ? "non" : "à vérifier")
                                          + (modelData.besoins ? "  ·  " + modelData.besoins : "") + "  ·  repéré le " + modelData.date }
                                T { visible: modelData.avis !== ""; text: modelData.avis; width: parent.width; font.pixelSize: 12 }
                                T { visible: modelData.source !== ""; text: modelData.source; width: parent.width; font.pixelSize: 12; color: cSecond }
                            }
                            Row {
                                anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                                Bouton { objectName: "veille_essayer_" + index; visible: modelData.statut === "nouveau"; texte: "À essayer"
                                         onClic: pont.agir("statut_veille", {pk: modelData.id, corps: {valeur: "a_essayer"}}) }
                                Bouton { objectName: "veille_ecarter_" + index; visible: modelData.statut !== "ecarte"; texte: "Écarter"
                                         onClic: pont.agir("statut_veille", {pk: modelData.id, corps: {valeur: "ecarte"}}) }
                            }
                        }
                    }
                }
            }
        }

        Flickable {
            objectName: "ecran_banc"
            visible: ecran === "banc"
            anchors.fill: parent; contentHeight: pileBanc.height + 48; clip: true
            ScrollBar.vertical: ScrollBar { width: 8; policy: ScrollBar.AsNeeded; contentItem: Rectangle { radius: 4; color: cTrait } }
            Shortcut { sequences: ["G"]; autoRepeat: false; enabled: ecran === "banc"; onActivated: voterBanc("gauche") }
            Shortcut { sequences: ["E"]; autoRepeat: false; enabled: ecran === "banc"; onActivated: voterBanc("egal") }
            Shortcut { sequences: ["D"]; autoRepeat: false; enabled: ecran === "banc"; onActivated: voterBanc("droite") }
            Shortcut { sequences: ["Up"]; enabled: ecran === "banc" && banc.lignes.length > 0; onActivated: ligneBanc = Math.max(0, ligneBanc - 1) }
            Shortcut { sequences: ["Down"]; enabled: ecran === "banc" && banc.lignes.length > 0; onActivated: ligneBanc = Math.min(banc.lignes.length - 1, ligneBanc + 1) }
            MediaPlayer {
                id: lecteurBanc
                videoOutput: sortieBanc
                audioOutput: AudioOutput {}
            }
            Column {
                id: pileBanc
                x: 24; y: 24; width: Math.min(contenu.width - 48, 960); spacing: 16
                T { text: "Banc"; font.pixelSize: 28; font.weight: Font.DemiBold }
                T { text: "Deux outils, les mêmes entrées. Vous votez sans savoir quel outil est à gauche : G (gauche), E (égal) ou D (droite), entrée par entrée (↑ ↓ pour changer d'entrée) ; un vote se change jusqu'à « Rendre le verdict ». Les outils et le juge automatique se voient ensuite."
                    color: cSecond; width: parent.width }

                Panneau {
                    objectName: "detail_banc"
                    visible: banc.id > 0
                    titre: "Banc " + banc.id + " · " + banc.brique + " · " + banc.video
                    Row {
                        width: parent.width; spacing: 12
                        T { text: banc.outils + "  ·  juge : " + banc.juge + "  ·  " + banc.etat_nom; color: cSecond; width: parent.width - fermerBanc.width - 12 }
                        Bouton { id: fermerBanc; objectName: "fermer_banc"; texte: "Fermer"; onClic: { lecteurBanc.stop(); banc = bancVide } }
                    }
                    T { objectName: "verdict_banc"; visible: banc.verdict !== ""; text: "Verdict : " + banc.verdict; color: cReussi; width: parent.width; font.weight: Font.DemiBold }
                    Bouton { objectName: "rendre_verdict"; visible: banc.etat === "a_voter" && banc.votes === banc.entrees && banc.entrees > 0; texte: "Rendre le verdict"
                             onClic: pont.agir("rendre_verdict", {id: banc.id}) }
                    T { visible: banc.raison !== "" && banc.etat !== "fini"; text: banc.raison; color: cAttention; width: parent.width }
                    Row {
                        visible: banc.peut_adopter
                        spacing: 8
                        Bouton { objectName: "adopter_brique"; texte: "Adopter pour toutes les sessions"; onClic: pont.agir("adopter", {id: banc.id, corps: {ou: "brique"}}) }
                        Bouton { objectName: "adopter_session"; texte: "Adopter pour « " + banc.session + " » seulement"; onClic: pont.agir("adopter", {id: banc.id, corps: {ou: "session"}}) }
                    }
                    T { visible: banc.adopte !== ""; text: "Adopté (" + (banc.adopte === "brique" ? "toutes les sessions" : "la session " + banc.session) + ")."; color: cSecond; width: parent.width }
                    VideoOutput { id: sortieBanc; visible: lecteurBanc.hasVideo; width: parent.width; height: visible ? width * 9 / 16 : 0 }
                    Repeater {
                        model: banc.lignes
                        Rectangle {
                            id: caseEntree
                            property var ligne: modelData
                            property int n: index
                            objectName: "entree_" + index
                            width: parent.width; height: colEntree.implicitHeight + 20; radius: 6; color: cLeve
                            Accessible.role: Accessible.Grouping; Accessible.name: "Entrée " + (index + 1) + " : " + (modelData.texte || "sans texte")
                            border.width: index === ligneBanc && banc.etat === "a_voter" ? 2 : 0; border.color: cSelection
                            Column {
                                id: colEntree
                                x: 12; y: 10; width: parent.width - 24; spacing: 8
                                T { text: (index + 1) + ". " + (modelData.texte || "(sans texte)") + (modelData.langue ? "  ·  " + modelData.langue : ""); width: parent.width }
                                Row {
                                    spacing: 16; width: parent.width
                                    Repeater {
                                        model: ["gauche", "droite"]
                                        Column {
                                            property string cote: modelData
                                            property var ligne: caseEntree.ligne
                                            width: (parent.width - 16) / 2; spacing: 6
                                            T { width: parent.width; font.weight: Font.DemiBold
                                                text: (cote === "gauche" ? "Gauche" : "Droite") + (ligne.qui ? " : " + ligne.qui[cote] : "") + (ligne.notes ? "  ·  juge " + String(ligne.notes[cote]).replace(".", ",") + "/10" : "") }
                                            Image { visible: (ligne[cote] || []).length > 0 && estImage(ligne[cote][0]); width: parent.width; height: visible ? width * 9 / 16 : 0
                                                    source: visible ? url(ligne[cote][0]) : ""; fillMode: Image.PreserveAspectFit; Accessible.name: "Sortie " + cote }
                                            Bouton { objectName: "ecouter_" + cote + "_" + caseEntree.n; visible: (ligne[cote] || []).length > 0 && !estImage(ligne[cote][0])
                                                     texte: lecteurBanc.playbackState === MediaPlayer.PlayingState && String(lecteurBanc.source) === url(ligne[cote][0] || "") ? "Arrêter" : "Écouter / voir"
                                                     Accessible.name: "Écouter, " + cote + ", entrée " + (caseEntree.n + 1)
                                                     onClic: { if (lecteurBanc.playbackState === MediaPlayer.PlayingState && String(lecteurBanc.source) === url(ligne[cote][0])) lecteurBanc.stop()
                                                               else { lecteurBanc.source = url(ligne[cote][0]); lecteurBanc.play() } } }
                                        }
                                    }
                                }
                                Row {
                                    visible: banc.etat === "a_voter" || modelData.vote !== ""
                                    spacing: 6
                                    Puce { objectName: "vote_gauche_" + index; texte: "Gauche (G)"; choisi: modelData.vote === "gauche"; actif: banc.etat === "a_voter"
                                           onClic: { ligneBanc = index; voterBanc("gauche") } }
                                    Puce { objectName: "vote_egal_" + index; texte: "Égal (E)"; choisi: modelData.vote === "egal"; actif: banc.etat === "a_voter"
                                           onClic: { ligneBanc = index; voterBanc("egal") } }
                                    Puce { objectName: "vote_droite_" + index; texte: "Droite (D)"; choisi: modelData.vote === "droite"; actif: banc.etat === "a_voter"
                                           onClic: { ligneBanc = index; voterBanc("droite") } }
                                }
                            }
                        }
                    }
                }
                Panneau {
                    titre: "Bancs"
                    T { visible: !bancs.length; text: "Aucun banc encore."; color: cSecond; width: parent.width }
                    Repeater {
                        model: bancs
                        Rectangle {
                            objectName: "banc_liste_" + index
                            width: parent.width; height: ligneBancs.implicitHeight + 20; radius: 6; color: banc.id === modelData.id || survolBanc.hovered ? cTrait : cLeve
                            activeFocusOnTab: true; border.width: activeFocus ? 1 : 0; border.color: cSelection
                            Keys.onReturnPressed: ouvrirBanc(modelData.id)
                            Keys.onSpacePressed: ouvrirBanc(modelData.id)
                            Column {
                                id: ligneBancs
                                x: 12; y: 10; width: parent.width - 24; spacing: 4
                                T { text: "Banc " + modelData.id + " · " + modelData.brique + " · " + modelData.session + " · " + modelData.video; font.weight: Font.DemiBold; width: parent.width }
                                T { text: modelData.outils + "  ·  juge : " + modelData.juge; font.pixelSize: 12; color: cSecond; width: parent.width }
                                T { text: modelData.etat_nom + (modelData.etat === "a_voter" ? " (" + modelData.votes + "/" + modelData.entrees + ")" : "") + (modelData.raison ? " — " + modelData.raison : "")
                                    color: modelData.etat === "a_voter" ? cAttention : modelData.etat === "erreur" ? cDefaut : modelData.etat === "fini" ? cReussi : cSecond; width: parent.width; font.pixelSize: 12 }
                                T { visible: modelData.verdict !== ""; text: modelData.verdict; width: parent.width; font.pixelSize: 12 }
                            }
                            HoverHandler { id: survolBanc }
                            Clic { onTapped: ouvrirBanc(modelData.id) }
                            Accessible.role: Accessible.Button; Accessible.name: "Banc " + modelData.id + " : " + modelData.etat_nom; Accessible.onPressAction: ouvrirBanc(modelData.id)
                        }
                    }
                }

                Panneau {
                    titre: "Nouveau banc"
                    T { text: "Brique"; color: cSecond; width: parent.width }
                    Flow {
                        width: parent.width; spacing: 6
                        Repeater {
                            model: outils.briques
                            Puce { objectName: "brique_" + modelData.id; texte: modelData.titre; choisi: nouveauBanc.brique === modelData.id
                                   onClic: nouveauBanc = {brique: modelData.id, outil: "", video: nouveauBanc.video, juge: modelData.juges.length ? modelData.juges[0].id : ""} }
                        }
                    }
                    T { visible: nouveauBanc.brique !== ""; text: "Outil à mesurer à l'outil en place (" + briqueChoisie().defaut + ")"; color: cSecond; width: parent.width }
                    Flow {
                        width: parent.width; spacing: 6
                        Repeater {
                            model: briqueChoisie().outils.filter(o => !o.defaut && o.etat !== "retire")
                            Puce { objectName: "outil_banc_" + modelData.id; texte: modelData.nom; choisi: nouveauBanc.outil === modelData.id
                                   onClic: nouveauBanc = Object.assign({}, nouveauBanc, {outil: modelData.id}) }
                        }
                    }
                    T { text: "Vidéo de « " + sessionChoisie().nom + " » dont les morceaux finis sont rejoués"; color: cSecond; width: parent.width }
                    Flow {
                        width: parent.width; spacing: 6
                        Repeater {
                            model: videos
                            Puce { objectName: "video_banc_" + index; texte: modelData.titre; choisi: nouveauBanc.video === modelData.id
                                   onClic: nouveauBanc = Object.assign({}, nouveauBanc, {video: modelData.id}) }
                        }
                    }
                    T { text: "Juge automatique (un seul par banc)"; color: cSecond; width: parent.width }
                    Flow {
                        width: parent.width; spacing: 6
                        Repeater {
                            model: briqueChoisie().juges
                            Puce { objectName: "juge_" + modelData.id; texte: modelData.titre; choisi: nouveauBanc.juge === modelData.id
                                   onClic: nouveauBanc = Object.assign({}, nouveauBanc, {juge: modelData.id}) }
                        }
                        Puce { objectName: "juge_aucun"; texte: "Sans juge"; choisi: nouveauBanc.juge === ""; onClic: nouveauBanc = Object.assign({}, nouveauBanc, {juge: ""}) }
                    }
                    Bouton { objectName: "lancer_banc"; texte: "Lancer le banc"; actif: nouveauBanc.brique !== "" && nouveauBanc.outil !== "" && nouveauBanc.video !== ""
                             onClic: pont.agir("nouveau_banc", {corps: {session: session, video: nouveauBanc.video, brique: nouveauBanc.brique, outil: nouveauBanc.outil, juge: nouveauBanc.juge}}) }
                }
            }
        }

        Flickable {
            objectName: "ecran_systeme"
            visible: ecran === "systeme"
            anchors.fill: parent; contentHeight: pile.height + 48; clip: true
            ScrollBar.vertical: ScrollBar { width: 8; policy: ScrollBar.AsNeeded; contentItem: Rectangle { radius: 4; color: cTrait } }
            Column {
                id: pile
                x: 24; y: 24; width: Math.min(contenu.width - 48, 960); spacing: 16
                T { text: "Système"; font.pixelSize: 28; font.weight: Font.DemiBold }

                Panneau {
                    titre: "Sauvegardes"
                    T { text: "Chaque soir à 23 h 30, gardées 30 jours, dans " + sauvegardes.dossier; color: cSecond; width: parent.width }
                    T { objectName: "derniere_sauvegarde"; text: derniere(); width: parent.width; color: sauvegardes.derniere.etat === "erreur" ? cDefaut : cTexte }
                    Bouton { objectName: "bouton_sauvegarder"; texte: "Sauvegarder maintenant"; actif: sauvegardes.derniere.etat !== "en_cours"; onClic: pont.agir("sauvegarder", {}) }
                    Repeater {
                        model: sauvegardes.liste
                        Rectangle {
                            width: parent.width; height: 44; radius: 6; color: cLeve
                            Mono { text: modelData.date; x: 12; anchors.verticalCenter: parent.verticalCenter }
                            Mono { text: modelData.taille_mo.toFixed(1).replace(".", ",") + " Mo"; color: cSecond; x: 200; anchors.verticalCenter: parent.verticalCenter }
                            Bouton { objectName: "restaurer_" + index; texte: "Restaurer"; anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter; onClic: aRestaurer = modelData.nom }
                        }
                    }
                    Rectangle {
                        visible: aRestaurer !== ""
                        width: parent.width; height: confirmation.implicitHeight + 24; radius: 6; color: cLeve; border.width: 1; border.color: cAttention
                        Column {
                            id: confirmation
                            x: 12; y: 12; width: parent.width - 24; spacing: 12
                            T { text: "Restaurer « " + aRestaurer + " » ? L'état actuel est d'abord gardé de côté."; width: parent.width }
                            Row {
                                spacing: 8
                                Bouton { objectName: "confirmer_restaurer"; texte: "Restaurer"; onClic: { pont.agir("restaurer", {nom: aRestaurer}); aRestaurer = "" } }
                                Bouton { texte: "Annuler"; onClic: aRestaurer = "" }
                            }
                        }
                    }
                }

                Panneau {
                    titre: "Mises à jour"
                    Mono { text: "Version installée : " + versions.installee }
                    T { objectName: "version_proposee"; width: parent.width; text: versions.proposee ? "Version " + versions.proposee + " prête." : versions.raison; color: versions.proposee ? cReussi : cSecond }
                    Repeater { model: versions.nouveautes; T { text: "• " + modelData; width: parent.width } }
                    // une valeur vide du noyau (None) arrive « undefined », pas « null »
                    Bouton { objectName: "bouton_mettre_a_jour"; visible: !!versions.proposee; actif: versions.raison === ""; texte: "Mettre à jour"; onClic: pont.agir("mettre_a_jour", {}) }
                    T { visible: !!versions.proposee && versions.raison !== ""; text: versions.raison; color: cAttention; width: parent.width }
                }

                Panneau {
                    titre: "Mode"
                    T { objectName: "mode"; width: parent.width
                        text: sante.mode === "réel" ? "Mode réel : vrais outils, vraies chaînes. Rien ne part sans votre clic." : "Simulation : faux outils et faux YouTube, rien ne sort de ce PC." }
                    Bouton { objectName: "bouton_mode"; texte: sante.mode === "réel" ? "Revenir en simulation" : "Passer en mode réel"; onClic: aChangerMode = true }
                    Rectangle {
                        visible: aChangerMode
                        width: parent.width; height: confMode.implicitHeight + 24; radius: 6; color: cLeve; border.width: 1; border.color: cAccent
                        Column {
                            id: confMode
                            x: 12; y: 12; width: parent.width - 24; spacing: 12
                            T { width: parent.width; text: sante.mode === "réel" ? "Revenir en simulation ? Les chaînes réelles restent reliées." : "Passer en mode réel ? Les vidéos se fabriqueront avec les vrais outils et « Publier » enverra sur les vraies chaînes." }
                            Row {
                                spacing: 8
                                Bouton { objectName: "confirmer_mode"; ambre: sante.mode !== "réel"; texte: sante.mode === "réel" ? "Revenir en simulation" : "Passer en mode réel"
                                         onClic: { pont.agir("changer_mode", {corps: {reel: sante.mode !== "réel"}}); aChangerMode = false } }
                                Bouton { texte: "Annuler"; onClic: aChangerMode = false }
                            }
                        }
                    }
                }

                Panneau {
                    titre: "Téléphone"
                    T { text: "La page iPhone (par Tailscale, adresse de ce PC suivie de /iphone/) : état, approuver, publier, paquets. Un code la relie pour un an."; color: cSecond; width: parent.width }
                    Row {
                        spacing: 16
                        Bouton { objectName: "bouton_code_telephone"; texte: "Connecter un téléphone"; onClic: pont.lire("code_telephone", {}) }
                        Mono { objectName: "code_telephone"; visible: code_telephone.code !== ""; text: code_telephone.code.slice(0, 3) + " " + code_telephone.code.slice(3); font.pixelSize: 26; color: cAccent }
                        T { visible: code_telephone.code !== ""; text: "à taper sur l'iPhone avant " + code_telephone.expire + " (une seule fois)"; color: cSecond; anchors.verticalCenter: parent.verticalCenter; wrapMode: Text.NoWrap }
                    }
                    T { objectName: "adresse_iphone"; visible: code_telephone.code !== ""; width: parent.width
                        text: code_telephone.adresse !== "" ? "Sur l'iPhone : " + code_telephone.adresse : "Tailscale est introuvable sur ce PC : la page iPhone n'est pas joignable."
                        color: code_telephone.adresse !== "" ? cTexte : cAttention }
                    Repeater {
                        model: appareils
                        Rectangle {
                            width: parent.width; height: 44; radius: 6; color: cLeve
                            T { text: modelData.appareil + "  ·  connecté le " + modelData.depuis + "  ·  jusqu'au " + modelData.expire; x: 12; anchors.verticalCenter: parent.verticalCenter; wrapMode: Text.NoWrap }
                            Bouton { objectName: "deconnecter_" + index; texte: "Déconnecter"; anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter
                                     onClic: pont.agir("deconnecter", {appareil: modelData.id}) }
                        }
                    }
                }

                Panneau {
                    titre: "Journal"
                    T { visible: journal.length === 0; text: "Aucun avertissement ni problème dans les journaux."; color: cSecond; width: parent.width }
                    Repeater {
                        model: journal
                        Row {
                            spacing: 12; width: parent.width
                            Mono { text: modelData.date; color: cSecond; font.pixelSize: 12 }
                            T { text: modelData.niveau; width: 100; color: modelData.niveau === "problème" ? cDefaut : cAttention; font.pixelSize: 12 }
                            T { text: modelData.source + " : " + modelData.message; width: parent.width - 300; font.pixelSize: 12 }
                        }
                    }
                }

                Panneau {
                    titre: "Clés"
                    T { text: "Chiffrées par Windows, jamais affichées."; color: cSecond; width: parent.width }
                    Repeater {
                        model: cles
                        Rectangle {
                            width: parent.width; height: 48; radius: 6; color: cLeve
                            T { text: modelData.titre; x: 12; width: 260; anchors.verticalCenter: parent.verticalCenter }
                            T { text: modelData.ou; x: 280; width: 190; color: modelData.ok ? cReussi : cSecond; anchors.verticalCenter: parent.verticalCenter }
                            Rectangle {
                                anchors.left: parent.left; anchors.leftMargin: 480; anchors.right: enregistrer.left; anchors.rightMargin: 8; height: 32; radius: 6; color: cFond; border.width: 1; border.color: champ.activeFocus ? cSelection : cTrait
                                anchors.verticalCenter: parent.verticalCenter
                                TextInput {
                                    id: champ
                                    objectName: "champ_" + modelData.nom
                                    anchors.fill: parent; anchors.margins: 8; clip: true
                                    color: cTexte; font.pixelSize: 14; echoMode: TextInput.Password; selectByMouse: true
                                    Accessible.name: "Nouvelle clé : " + modelData.titre
                                }
                            }
                            Bouton {
                                id: enregistrer
                                objectName: "enregistrer_" + modelData.nom
                                texte: "Enregistrer"; actif: champ.text.length > 0
                                anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter
                                onClic: { pont.agir("enregistrer_cle", {nom: modelData.nom, valeur: champ.text}); champ.text = "" }
                            }
                        }
                    }
                }
            }
        }
    }

    TextEdit { id: pressePapier; visible: false }  // copier : QML n'a pas d'accès direct au presse-papiers

    Rectangle {
        id: barre
        anchors { left: nav.right; right: parent.right; bottom: parent.bottom }
        height: message ? 40 : 0; color: cPanneau; clip: true
        Behavior on height { NumberAnimation { duration: 150 } }
        Rectangle { width: parent.width; height: 1; color: cTrait }
        T { objectName: "message"; text: message; x: 24; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 48; elide: Text.ElideRight; wrapMode: Text.NoWrap; color: messageOk ? cTexte : cDefaut }
    }
}
