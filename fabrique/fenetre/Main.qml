// La coquille de Fabrique : navigation, Accueil (file, à faire, machine), Sessions (scripts et « Fabriquer », vidéos, univers),
// Système (sauvegardes, mises à jour, journal, clés).
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
    property var univers: ({personnages: [], lieux: [], langues: []})
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
    property var code_telephone: ({code: "", expire: ""})
    property var relier: ({url: "", message: ""})
    property int aPublier: -1  // la publication dont « Publier » attend la confirmation
    property var brouillon: null  // le script en cours d'écriture (copie du contenu) ; null : lecture
    property var brouillons: ({})  // les brouillons des autres scripts ouverts entre-temps : jamais perdus sans « Abandonner »
    property var controler: ({erreurs: [], avis: [], mesures: {}})  // les règles du brouillon, rejouées pendant la frappe
    readonly property var etats: ({attente: "en attente", en_cours: "en cours", pause: "en pause", finie: "finie", erreur: "en erreur", annulee: "annulée"})
    readonly property string mono: Qt.fontFamilies().indexOf("Cascadia Mono") >= 0 ? "Cascadia Mono" : "Consolas"

    function recharger() {
        ["sante", "sauvegardes", "versions", "journal", "cles", "file", "machine", "sessions", "etat", "appareils"].forEach(n => pont.charger(n))
        if (session !== "") ["scripts", "videos", "univers", "destinations"].forEach(n => pont.lire(n, {id: session}))
        if (ecran === "video" && video.id !== "") ["video", "publications", "paquets"].forEach(n => pont.lire(n, {id: session, video: video.id}))
        if (ecran === "script" && script.code !== "") pont.lire("script", {id: session, code: script.code})
    }
    function choisir(id) { session = id; aFabriquer = ""; recharger() }
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
            f[nom] = d
            if (nom === "sessions" && session === "" && d.length) choisir(d[0].id)
            if (nom === "relier" && d.url) { message = d.message; messageOk = true; Qt.openUrlExternally(d.url) }  // la page de Google, dans le navigateur du PC
        }
        function onFait(nom, texte, ok) {
            message = texte; messageOk = ok
            if (nom === "refaire") liberer = false
            if (nom === "nouvelle_version" && ok) brouillon = null  // refusé ou noyau absent : le texte tapé reste là
            recharger()
        }
        function onAller(e) { aller(e) }
        function onEvenement(type, d) { if (type !== "etat") recharger() }
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
        border.width: 1; border.color: cTrait
        opacity: actif ? 1 : 0.4
        Behavior on color { ColorAnimation { duration: 120 } }
        T { id: bt; anchors.centerIn: parent; wrapMode: Text.NoWrap; color: ambre ? cFond : cTexte; font.weight: ambre ? Font.DemiBold : Font.Normal }
        HoverHandler { id: survol }
        Clic { enabled: parent.actif; onTapped: parent.clic() }
        Accessible.role: Accessible.Button; Accessible.name: bt.text; Accessible.onPressAction: if (actif) clic()
    }
    component Champ: Rectangle {  // une ligne de texte modifiable
        property alias texte: saisie.text
        property alias nom: saisie.objectName
        property string libelle: ""
        width: parent.width; height: 32; radius: 6; color: cFond; border.width: 1; border.color: saisie.activeFocus ? cSelection : cTrait
        TextInput { id: saisie; anchors.fill: parent; anchors.margins: 8; clip: true; color: cTexte; font.family: "Segoe UI Variable"; font.pixelSize: 14; selectByMouse: true; Accessible.name: libelle }
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
                model: [{id: "accueil", nom: "Accueil", touche: "Ctrl+1"}, {id: "sessions", nom: "Sessions", touche: "Ctrl+2"}, {id: "systeme", nom: "Système", touche: "Ctrl+3"}]
                Rectangle {
                    objectName: "nav_" + modelData.id
                    width: parent.width; height: 40; radius: 6
                    color: (ecran === "video" || ecran === "script" ? "sessions" : ecran) === modelData.id || survolNav.hovered ? cLeve : "transparent"
                    Rectangle { visible: (ecran === "video" || ecran === "script" ? "sessions" : ecran) === modelData.id; width: 3; height: 20; radius: 2; color: cSelection; anchors.verticalCenter: parent.verticalCenter }
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
                                    Mono { text: modelData.progression + " morceaux"; color: cSecond }
                                }
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
                        T { text: modelData.nom; x: 12; width: parent.width - 24; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                        HoverHandler { id: survolSession }
                        Clic { onTapped: choisir(modelData.id) }
                        Accessible.role: Accessible.Button; Accessible.name: "Session " + modelData.nom; Accessible.onPressAction: choisir(modelData.id)
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
                        model: [{id: "scripts", nom: "Scripts"}, {id: "videos", nom: "Vidéos"}, {id: "univers", nom: "Univers"}]
                        Rectangle {
                            objectName: "onglet_" + modelData.id
                            width: nomOnglet.implicitWidth + 32; height: 36; radius: 6
                            color: onglet === modelData.id ? cLeve : "transparent"; border.width: 1; border.color: onglet === modelData.id ? cSelection : cTrait
                            T { id: nomOnglet; text: modelData.nom; anchors.centerIn: parent; wrapMode: Text.NoWrap }
                            Clic { onTapped: onglet = modelData.id }
                            Accessible.role: Accessible.PageTab; Accessible.name: modelData.nom; Accessible.onPressAction: onglet = modelData.id
                        }
                    }
                }
            }
            Flickable {
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
                        visible: onglet === "univers"; titre: "Personnages"
                        Repeater {
                            model: onglet === "univers" ? univers.personnages : []
                            T { text: modelData.nom + (modelData.role ? " · " + modelData.role : "") + " · " + modelData.references + " référence(s)"; width: parent.width
                                color: modelData.statut === "actif" ? cTexte : cSecond }
                        }
                    }
                    Panneau {
                        visible: onglet === "univers"; titre: "Lieux"
                        Repeater { model: onglet === "univers" ? univers.lieux : []; T { text: modelData.nom; width: parent.width } }
                    }
                    Panneau {
                        visible: onglet === "univers"; titre: "Langues et voix"
                        Repeater {
                            model: onglet === "univers" ? univers.langues : []
                            T { text: modelData.code + " · " + modelData.nom + " · " + (modelData.outil_voix || "voix de la session") + (modelData.voix_validee ? "" : " (voix à valider)")
                                width: parent.width; color: modelData.voix_validee ? cTexte : cAttention }
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
                        model: [{id: "fabrication", nom: "Fabrication"}, {id: "verification", nom: "Vérification"}, {id: "script", nom: "Script"}, {id: "publication", nom: "Publication"}]
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
                                    T { width: parent.width; color: cSecond; font.pixelSize: 13
                                        text: (p.non_repertorie ? "Part en non répertorié (première vidéo de la chaîne)" : "En privé, publique le " + p.creneau)
                                              + "  ·  " + (p.playlist_titre !== "" ? "playlist : " + p.playlist_titre : "sans playlist") + "  ·  pour enfants : " + (p.enfants ? "oui" : "non")
                                              + "  ·  IA déclarée : " + (p.ia ? "oui" : "non") + (p.chapitres.length ? "  ·  " + p.chapitres.length + " chapitres" : "") }
                                    Flow {
                                        visible: carte.modifiable && p.miniatures.length > 0; width: parent.width; spacing: 6
                                        T { text: "Miniature :"; color: cSecond; wrapMode: Text.NoWrap; height: 32; verticalAlignment: Text.AlignVCenter }
                                        Repeater { model: p.miniatures; Bouton { texte: modelData + (p.miniature !== "" && nomDe(p.miniature) === modelData ? " ✓" : "")
                                                                                 onClic: pont.agir("choisir", {id: session, pub: p.id, corps: {miniature: modelData}}) } }
                                    }
                                    Flow {
                                        visible: carte.modifiable && chaineDe(p.langue).playlists.length > 0; width: parent.width; spacing: 6
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
                                        Bouton { objectName: "publier_" + index; ambre: true; visible: carte.modifiable; actif: p.fautes.length === 0 && p.destination === "reliée"
                                                 texte: p.statut === "erreur" ? "Reprendre l'envoi" : "Publier"; onClic: aPublier = p.id }
                                        Bouton { visible: p.statut === "en_file"; texte: "Annuler l'envoi"; onClic: pont.agir("publier", {id: session, pub: p.id, action: "annuler"}) }
                                    }
                                    Rectangle {
                                        visible: aPublier === p.id
                                        width: parent.width; height: confPub.implicitHeight + 24; radius: 6; color: cPanneau; border.width: 1; border.color: cAccent
                                        Column {
                                            id: confPub
                                            x: 12; y: 12; width: parent.width - 24; spacing: 12
                                            T { width: parent.width; text: (p.statut === "erreur" ? "Reprendre l'envoi de « " : "Publier « ") + titrePub.texte + " » (" + p.langue + ") sur « " + p.chaine + " », "
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
                    titre: "Destinations"
                    T { text: "Les chaînes de « " + ((sessions.find(s => s.id === session) || {nom: "?"}).nom) + " », une par langue. Relier ouvre la page de Google dans le navigateur."; color: cSecond; width: parent.width }
                    T { visible: destinations.length === 0; text: "Aucune destination pour cette session (la session « Essais » ne publie jamais)."; color: cSecond; width: parent.width }
                    Repeater {
                        model: destinations
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

                Panneau {
                    titre: "Téléphone"
                    T { text: "La page iPhone (par Tailscale, adresse de ce PC suivie de /iphone/) : état, approuver, publier, paquets. Un code la relie pour un an."; color: cSecond; width: parent.width }
                    Row {
                        spacing: 16
                        Bouton { objectName: "bouton_code_telephone"; texte: "Connecter un téléphone"; onClic: pont.lire("code_telephone", {}) }
                        Mono { objectName: "code_telephone"; visible: code_telephone.code !== ""; text: code_telephone.code.slice(0, 3) + " " + code_telephone.code.slice(3); font.pixelSize: 26; color: cAccent }
                        T { visible: code_telephone.code !== ""; text: "à taper sur l'iPhone avant " + code_telephone.expire + " (une seule fois)"; color: cSecond; anchors.verticalCenter: parent.verticalCenter; wrapMode: Text.NoWrap }
                    }
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
