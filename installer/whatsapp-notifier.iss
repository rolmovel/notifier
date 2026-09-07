; -*- mode: ini -*-
; WhatsApp Notifier — Inno Setup script
;
; Build with:
;   iscc installer\whatsapp-notifier.iss
;
; Expects the PyInstaller output in ..\dist\WhatsAppNotifier\ and the
; portable Node.js runtime in ..\dist\WhatsAppNotifier\node\.
; The version is read from the VERSION environment variable (set by CI
; from the git tag); falls back to "1.0.0" for local builds.

#ifndef VERSION
  #define VERSION "1.0.0"
#endif

#define AppName         "WhatsApp Notifier"
#define AppExeName      "WhatsAppNotifier.exe"
#define AppPublisher    "WhatsApp Notifier"
#define AppURL          "https://github.com/PC/notifier"

[Setup]
AppId={{8F2C4A1B-3D5E-4F6A-9B7C-8D9E0F1A2B3C}
AppName={#AppName}
AppVersion={#VERSION}
AppVerName={#AppName} {#VERSION}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
OutputDir=Output
OutputBaseFilename=WhatsAppNotifier-Setup-{#VERSION}
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
; LicenseFile=license.txt
; SetupIconFile=..\assets\icon.ico
; UsePreviousAppDir=yes
; UsePreviousTasks=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Application bundle (PyInstaller onedir output: exe + _internal/)
Source: "..\dist\WhatsAppNotifier\WhatsAppNotifier.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\WhatsAppNotifier\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; Bridge (JS source + node_modules)
Source: "..\dist\WhatsAppNotifier\bridge\*"; DestDir: "{app}\bridge"; Flags: ignoreversion recursesubdirs createallsubdirs
; Bundled portable Node.js
Source: "..\dist\WhatsAppNotifier\node\*"; DestDir: "{app}\node"; Flags: ignoreversion recursesubdirs createallsubdirs
; Misc
Source: "..\dist\WhatsAppNotifier\README.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove bundled runtime files that may have been created at runtime
; (auth state lives in %APPDATA% and is intentionally preserved)
Type: filesandordirs; Name: "{app}\bridge\auth"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
