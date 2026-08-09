; Script Inno Setup Professionnel pour Sinistres App (v4.0.0)
; Produit un installateur unique : release/Sinistres-App-Setup.exe
;
; Pour compiler ce script sous Windows avec Inno Setup 6 :
;   - Ouvrez Inno Setup -> Compile
;   - OU exécutez en ligne de commande : ISCC.exe installer\Sinistres-App.iss

#define MyAppName "Sinistres App"
#define MyAppVersion "4.0.0"
#define MyAppPublisher "Bezzioune Karim"
#define MyAppURL "https://github.com/bezziounekarim923-hub/Sinistres-App-V4"
#define MyAppExeName "Sinistres App.exe"
#define MyDataDir "{userappdata}\SinistresApp"

[Setup]
; Identifiant unique pour désinstallation / mise à jour sans doublon (GUID permanent)
AppId={{019FE1E5-SINI-STRE-SAPP-0000000000V4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Répertoire de sortie du fichier Setup.exe (dossier /release/ à la racine du projet)
OutputDir=..\release
OutputBaseFilename=Sinistres-App-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion=4.0.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Logiciel autonome de gestion et suivi des sinistres (Windows)
VersionInfoProductName={#MyAppName}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Inclusion de tous les fichiers de l'application compilée par PyInstaller (--onedir)
Source: "..\dist\windows\Sinistres App\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Option d'exécution après la fin de l'assistant d'installation
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Dirs]
; Création du dossier de données utilisateur inscriptible dans %APPDATA%\SinistresApp
Name: "{#MyDataDir}"; Permissions: users-modify
Name: "{#MyDataDir}\backups"; Permissions: users-modify
Name: "{#MyDataDir}\Documents_Sinistres"; Permissions: users-modify
Name: "{#MyDataDir}\Fiches"; Permissions: users-modify

[UninstallDelete]
; Supprime uniquement les fichiers temporaires du dossier programme,
; ne supprime JAMAIS les données personnelles ({userappdata}\SinistresApp)
Type: files; Name: "{app}\*.log"
Type: files; Name: "{app}\*.tmp"

[Code]
// Note: Lors d'une mise à jour ou d'une désinstallation, les données utilisateur
// (%APPDATA%\SinistresApp\sinistres.db, sauvegardes, pièces jointes, modèles Word)
// sont systématiquement préservées pour éviter toute perte de travail.
