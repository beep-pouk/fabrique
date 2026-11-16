; Installateur de Fabrique (Inno Setup 6, rangé dans OUTILS\innosetup : outil de développement), repris de Bramble Studio (installateur\bramble.iss).
; Compilé par outils_dev\construire.py, qui passe : VERSION, PROGRAMME (le dossier assemblé), SORTIE, FICHIER (nom de l'installateur), ICONE,
; MARQUE ; SIGNER (lanceur, installateur et désinstallateur signés) ; BAC (fichier marqueur : installateur d'essai, autre nom, autre identité :
; il ne touche jamais à l'installation de RT) ; PYPROJECT (version factice pour l'essai de mise à jour).
; Par utilisateur, sans droits administrateur. Le dossier choisi est celui de Fabrique (proposé : <studio>\FABRIQUE) : le programme va dans son
; sous-dossier « programme », les données à côté. La désinstallation ne retire que ce que l'installation a posé : les données restent.
#ifndef VERSION
  #error VERSION manquant : ce script est compilé par outils_dev\construire.py
#endif
#ifdef BAC
  #define NOM "Fabrique (bac à sable)"
  #define ID "5E0C2B7A-9F14-4C3B-8E2D-6A1F0B9C4D02"
  #define IDENTITE "StudioKids.Fabrique.Bac"
#else
  #define NOM "Fabrique"
  #define ID "5E0C2B7A-9F14-4C3B-8E2D-6A1F0B9C4D01"
  #define IDENTITE "StudioKids.Fabrique"
#endif
#define EXE "Fabrique.exe"

[Setup]
AppId={{{#ID}}
AppName={#NOM}
AppVersion={#VERSION}
AppVerName={#NOM} {#VERSION}
AppPublisher=StudioKids
DefaultDirName={code:DossierParDefaut}
AppendDefaultDirName=no
DirExistsWarning=no
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
ShowLanguageDialog=no
CloseApplications=no
SetupIconFile={#ICONE}
UninstallDisplayIcon={app}\programme\{#EXE}
UninstallDisplayName={#NOM}
UninstallFilesDir={app}\programme
VersionInfoVersion={#VERSION}
VersionInfoCompany=StudioKids
VersionInfoProductName={#NOM}
VersionInfoDescription=Installation de {#NOM}
OutputDir={#SORTIE}
OutputBaseFilename={#FICHIER}
Compression=lzma2/fast
SolidCompression=no
#ifdef SIGNER
SignTool=signer
SignedUninstaller=yes
#endif

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
; proposées à la première installation seulement : une mise à jour ne remet pas un raccourci que RT a retiré
Name: "bureau"; Description: "Créer une icône sur le Bureau"; Check: not MiseAJour
Name: "demarrage"; Description: "Démarrer avec Windows (fenêtre cachée près de l'horloge jusqu'à votre clic)"; Check: not MiseAJour

[InstallDelete]
; mise à jour : le code et le Python embarqué sont reposés en entier (un fichier retiré d'une version ne reste pas)
Type: filesandordirs; Name: "{app}\programme\app"
Type: filesandordirs; Name: "{app}\programme\runtime"

[Files]
Source: "{#PROGRAMME}\*"; DestDir: "{app}\programme"; Flags: ignoreversion recursesubdirs createallsubdirs
#ifdef BAC
Source: "{#BAC}"; DestDir: "{app}\programme"; DestName: "BAC_A_SABLE"; Flags: ignoreversion
#endif
#ifdef PYPROJECT
Source: "{#PYPROJECT}"; DestDir: "{app}\programme\app"; DestName: "pyproject.toml"; Flags: ignoreversion
#endif

[Icons]
Name: "{autoprograms}\{#NOM}"; Filename: "{app}\programme\{#EXE}"; AppUserModelID: "{#IDENTITE}"
Name: "{autodesktop}\{#NOM}"; Filename: "{app}\programme\{#EXE}"; AppUserModelID: "{#IDENTITE}"; Tasks: bureau
Name: "{userstartup}\{#NOM}"; Filename: "{app}\programme\{#EXE}"; Parameters: "--fond"; AppUserModelID: "{#IDENTITE}"; Tasks: demarrage

[Run]
Filename: "{app}\programme\{#EXE}"; Description: "Lancer {#NOM}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\programme\{#EXE}"; Flags: nowait; Check: Relancer

[Code]
const
  DESINSTALLATION = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{' + '{#ID}' + '}_is1';

function MiseAJour: Boolean;
begin
  Result := RegKeyExists(HKCU, DESINSTALLATION);
end;

function Relancer: Boolean;
begin
  Result := ExpandConstant('{param:RELANCER|0}') = '1';
end;

function StudioBramble: String;
begin
  Result := '';
  RegQueryStringValue(HKCU, 'Software\Bramble Studio', 'Studio', Result);  // lu seulement
end;

function DossierParDefaut(P: String): String;
begin
  if StudioBramble <> '' then
    Result := AddBackslash(StudioBramble) + 'FABRIQUE'
  else
    Result := ExpandConstant('{localappdata}\Fabrique');
end;

function Dans(D, Parent: String): Boolean;
begin
  Result := Pos(Lowercase(AddBackslash(Parent)), Lowercase(AddBackslash(D))) = 1;
end;

function SeulementFabrique(D: String): Boolean;
// le dossier ne contient que des dossiers de Fabrique (« versions » y est posé par la publication avant la première installation)
var
  F: TFindRec;
  N: String;
begin
  Result := True;
  if FindFirst(AddBackslash(D) + '*', F) then
  try
    repeat
      N := Lowercase(F.Name);
      if (N <> '.') and (N <> '..') and (N <> 'versions') and (N <> 'donnees') and (N <> 'sessions') and (N <> 'sauvegardes') and (N <> 'programme') then
        Result := False;
    until (not Result) or (not FindNext(F));
  finally
    FindClose(F);
  end;
end;

function RefusDossier: String;
var
  D, S: String;
begin
  Result := '';
  D := RemoveBackslashUnlessRoot(WizardDirValue);
  S := StudioBramble;
  if DirExists(AddBackslash(D) + 'PROJET') or DirExists(AddBackslash(D) + 'Bramble Studio') or DirExists(AddBackslash(D) + 'DEPOT') or
     ((S <> '') and (Dans(D, AddBackslash(S) + 'Bramble Studio') or Dans(D, AddBackslash(S) + 'DONNEES') or Dans(D, AddBackslash(S) + 'DEPOT') or
                     Dans(D, AddBackslash(S) + 'PROJET') or (Lowercase(AddBackslash(D)) = Lowercase(AddBackslash(S))))) then
    Result := 'Ce dossier appartient à Bramble Studio : Fabrique s''installe à côté, dans son propre dossier (par exemple « FABRIQUE » dans le dossier du studio).'
  else if DirExists(D) and ((not SeulementFabrique(D)) or (DirExists(AddBackslash(D) + 'programme') and not FileExists(AddBackslash(D) + 'programme\{#MARQUE}'))) then
    Result := 'Ce dossier contient déjà autre chose que Fabrique.' + #13#10#13#10 + 'Choisissez un dossier vide ou nouveau.';
end;

function Occupee(Exe: String): Boolean;
var
  Code: Integer;
begin
  Result := FileExists(Exe) and Exec(Exe, 'libre', '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 3);
end;

procedure Arreter(Exe: String);
var
  Code: Integer;
begin
  if FileExists(Exe) then
    Exec(Exe, 'arreter', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function Verrouille(F: String): Boolean;
var
  S: TFileStream;
begin
  Result := False;
  if FileExists(F) then
  try
    S := TFileStream.Create(F, fmOpenReadWrite or fmShareExclusive);
    S.Free;
  except
    Result := True;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpSelectDir) and (RefusDossier <> '') then
  begin
    SuppressibleMsgBox(RefusDossier, mbError, MB_OK, IDOK);
    Result := False;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Exe, Dll: String;
  I: Integer;
begin
  // Toujours joué, même pages sautées (mise à jour, /DIR= en silence) : rien n'est retiré ni posé avant ces contrôles.
  Exe := ExpandConstant('{app}\programme\{#EXE}');
  Dll := ExpandConstant('{app}\programme\runtime\python312.dll');
  Result := RefusDossier;
  if Result <> '' then
    exit;
  if Occupee(Exe) then
  begin
    Result := 'Une sauvegarde ou une tâche est en cours dans Fabrique. Réessayez quand elle sera finie : rien n''a été changé.';
    exit;
  end;
  Arreter(Exe);
  for I := 1 to 60 do
  begin
    if not (Verrouille(Exe) or Verrouille(Dll)) then
      break;
    Sleep(500);
  end;
  if Verrouille(Exe) or Verrouille(Dll) then
    Result := 'Fabrique tourne encore et n''a pas pu être arrêtée. Quittez-la (icône près de l''horloge) puis réessayez : rien n''a été changé.';
end;

function InitializeUninstall: Boolean;
var
  Exe: String;
begin
  Result := True;
  Exe := ExpandConstant('{app}\programme\{#EXE}');
  if Occupee(Exe) then
  begin
    SuppressibleMsgBox('Une sauvegarde ou une tâche est en cours dans Fabrique. Désinstallez quand elle sera finie : rien n''a été changé.', mbError, MB_OK, IDOK);
    Result := False;
  end
  else
    Arreter(Exe);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    SuppressibleMsgBox('Vos sessions, vos données et vos sauvegardes n''ont pas été touchées. Elles restent dans :' + #13#10#13#10 + ExpandConstant('{app}'), mbInformation, MB_OK, IDOK);
end;
