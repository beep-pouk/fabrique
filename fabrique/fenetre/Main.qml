// La coquille de Fabrique : navigation, Accueil (file, à faire, machine), Sessions (scripts et « Fabriquer », vidéos, univers),
// Système (sauvegardes, mises à jour, journal, clés).
// Jetons de style du plan technique § 6.2. Aucune règle ici : tout vient du noyau par « pont » (main.py).
import QtQuick
import QtQuick.Controls.Basic

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
    property var video: ({id: "", titre: "", nom: "", recette: "", etapes: [], plans: [], script: {}})
    property string ongletVideo: "fabrication"
    property var coches: []
    readonly property var etats: ({attente: "en attente", en_cours: "en cours", pause: "en pause", finie: "finie", erreur: "en erreur", annulee: "annulée"})
    readonly property string mono: Qt.fontFamilies().indexOf("Cascadia Mono") >= 0 ? "Cascadia Mono" : "Consolas"

    function recharger() {
        ["sante", "sauvegardes", "versions", "journal", "cles", "file", "machine", "sessions"].forEach(n => pont.charger(n))
        if (session !== "") ["scripts", "videos", "univers"].forEach(n => pont.lire(n, {id: session}))
        if (ecran === "video" && video.id !== "") pont.lire("video", {id: session, video: video.id})
    }
    function choisir(id) { session = id; aFabriquer = ""; recharger() }
    function ouvrirVideo(id) { video = {id: id, titre: "", nom: "", recette: "", etapes: [], plans: [], script: {}}; coches = []; ongletVideo = "fabrication"; aller("video") }
    function cocher(n) { var c = coches.slice(); var i = c.indexOf(n); if (i >= 0) c.splice(i, 1); else c.push(n); coches = c }
    function aller(e) { if (e !== "") ecran = e; recharger() }
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
        function onRecu(nom, d) { f[nom] = d; if (nom === "sessions" && session === "" && d.length) choisir(d[0].id) }
        function onFait(nom, texte, ok) { message = texte; messageOk = ok; recharger() }
        function onAller(e) { aller(e) }
        function onEvenement(type, d) { if (type !== "etat") recharger() }
    }

    component T: Text { color: cTexte; font.family: "Segoe UI Variable"; font.pixelSize: 14; wrapMode: Text.Wrap }
    component Mono: T { font.family: mono; wrapMode: Text.NoWrap }
    component Clic: TapHandler { gesturePolicy: TapHandler.ReleaseWithinBounds }
    component Bouton: Rectangle {
        property alias texte: bt.text
        property bool actif: true
        signal clic()
        width: bt.implicitWidth + 32; height: 32; radius: 6
        color: survol.hovered && actif ? cTrait : cLeve
        border.width: 1; border.color: cTrait
        opacity: actif ? 1 : 0.4
        Behavior on color { ColorAnimation { duration: 120 } }
        T { id: bt; anchors.centerIn: parent; wrapMode: Text.NoWrap }
        HoverHandler { id: survol }
        Clic { enabled: parent.actif; onTapped: parent.clic() }
        Accessible.role: Accessible.Button; Accessible.name: bt.text; Accessible.onPressAction: if (actif) clic()
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
                    color: (ecran === "video" ? "sessions" : ecran) === modelData.id || survolNav.hovered ? cLeve : "transparent"
                    Rectangle { visible: (ecran === "video" ? "sessions" : ecran) === modelData.id; width: 3; height: 20; radius: 2; color: cSelection; anchors.verticalCenter: parent.verticalCenter }
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
                Rectangle {
                    visible: aFabriquer !== ""
                    width: parent.width; height: confFabriquer.implicitHeight + 24; radius: 6; color: cLeve; border.width: 1; border.color: cAccent
                    Column {
                        id: confFabriquer
                        x: 12; y: 12; width: parent.width - 24; spacing: 12
                        T { text: "Fabriquer « " + aFabriquer + " » ? La vidéo entre dans la file ; elle part quand la carte est libre."; width: parent.width }
                        Row {
                            spacing: 8
                            Rectangle {
                                objectName: "confirmer_fabriquer"
                                width: tf.implicitWidth + 32; height: 32; radius: 6; color: cAccent
                                T { id: tf; text: "Fabriquer"; color: cFond; font.weight: Font.DemiBold; anchors.centerIn: parent; wrapMode: Text.NoWrap }
                                Clic { onTapped: { pont.agir("fabriquer", {id: session, code: aFabriquer}); aFabriquer = "" } }
                                Accessible.role: Accessible.Button; Accessible.name: "Fabriquer " + aFabriquer
                                Accessible.onPressAction: { pont.agir("fabriquer", {id: session, code: aFabriquer}); aFabriquer = "" }
                            }
                            Bouton { texte: "Annuler"; onClic: aFabriquer = "" }
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
                            width: parent.width; height: 52; radius: 6; color: cLeve
                            Mono { text: modelData.code; x: 12; anchors.verticalCenter: parent.verticalCenter }
                            T { text: modelData.titre; x: 90; width: parent.width - 400; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                            Mono { text: (modelData.date_prevue || "—") + "  v" + modelData.versions; color: cSecond
                                   anchors.right: boutonFabriquer.left; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter }
                            Bouton { id: boutonFabriquer; objectName: "fabriquer_" + index; texte: "Fabriquer"
                                     anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter; onClic: aFabriquer = modelData.code }
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
                        model: [{id: "fabrication", nom: "Fabrication"}, {id: "verification", nom: "Vérification"}, {id: "script", nom: "Script"}]
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
                             onClic: { pont.agir("refaire", {id: session, video: video.id, corps: {plans: coches}}); coches = [] } }
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

    Rectangle {
        id: barre
        anchors { left: nav.right; right: parent.right; bottom: parent.bottom }
        height: message ? 40 : 0; color: cPanneau; clip: true
        Behavior on height { NumberAnimation { duration: 150 } }
        Rectangle { width: parent.width; height: 1; color: cTrait }
        T { objectName: "message"; text: message; x: 24; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 48; elide: Text.ElideRight; wrapMode: Text.NoWrap; color: messageOk ? cTexte : cDefaut }
    }
}
