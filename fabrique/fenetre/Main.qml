// La coquille de Fabrique : navigation, Accueil (vide à J1), Système (sauvegardes, mises à jour, journal, clés).
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
    readonly property string mono: Qt.fontFamilies().indexOf("Cascadia Mono") >= 0 ? "Cascadia Mono" : "Consolas"

    function recharger() { ["sante", "sauvegardes", "versions", "journal", "cles"].forEach(n => pont.charger(n)) }
    function aller(e) { if (e !== "") ecran = e; recharger() }
    function derniere() {
        var d = sauvegardes.derniere
        return d.etat === "en_cours" ? "Sauvegarde en cours…"
             : d.etat === "faite" ? "Dernière sauvegarde : le " + d.fin.slice(8, 10) + "/" + d.fin.slice(5, 7) + " à " + d.fin.slice(11, 16) + " (" + String(d.taille_mo).replace(".", ",") + " Mo)"
             : d.etat === "erreur" ? "La dernière sauvegarde a raté : " + d.message : "Aucune sauvegarde encore."
    }

    Component.onCompleted: recharger()
    Connections {
        target: pont
        function onRecu(nom, d) { f[nom] = d }
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
                model: [{id: "accueil", nom: "Accueil", touche: "Ctrl+1"}, {id: "systeme", nom: "Système", touche: "Ctrl+2"}]
                Rectangle {
                    objectName: "nav_" + modelData.id
                    width: parent.width; height: 40; radius: 6
                    color: ecran === modelData.id || survolNav.hovered ? cLeve : "transparent"
                    Rectangle { visible: ecran === modelData.id; width: 3; height: 20; radius: 2; color: cSelection; anchors.verticalCenter: parent.verticalCenter }
                    T { text: modelData.nom; x: 12; anchors.verticalCenter: parent.verticalCenter }
                    Mono { text: modelData.touche; color: cSecond; font.pixelSize: 12; anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter }
                    HoverHandler { id: survolNav }
                    Clic { onTapped: aller(modelData.id) }
                }
            }
        }
        Mono { x: 16; anchors.bottom: parent.bottom; anchors.bottomMargin: 16; text: "F5 : actualiser"; color: cSecond; font.pixelSize: 12 }
    }

    Item {
        id: contenu
        anchors { left: nav.right; right: parent.right; top: parent.top; bottom: barre.top }

        Column {
            objectName: "ecran_accueil"
            visible: ecran === "accueil"
            x: 24; y: 24; width: Math.min(contenu.width - 48, 960); spacing: 16
            T { text: "Accueil"; font.pixelSize: 28; font.weight: Font.DemiBold }
            Panneau {
                titre: "Rien à faire pour l'instant"
                T { text: "Ici s'afficheront les vidéos en cours et ce qui attend votre clic."; color: cSecond; width: parent.width }
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
                    Bouton { objectName: "bouton_mettre_a_jour"; visible: versions.proposee !== null; actif: versions.raison === ""; texte: "Mettre à jour"; onClic: pont.agir("mettre_a_jour", {}) }
                    T { visible: versions.proposee !== null && versions.raison !== ""; text: versions.raison; color: cAttention; width: parent.width }
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
