; Inno Setup script for SpeedPulse (Windows installer).
; Build from the repository root with the PyInstaller payload present:
;   iscc packaging\windows\speedpulse.iss /DAppVersion=0.1.0

#ifndef AppVersion
#define AppVersion "0.1.0"
#endif

[Setup]
AppName=SpeedPulse
AppVersion={#AppVersion}
AppPublisher=rafi138
AppPublisherURL=https://github.com/rafi138/speedpulse
DefaultDirName={autopf}\SpeedPulse
DefaultGroupName=SpeedPulse
DisableProgramGroupPage=yes
; relative to THIS script's directory (packaging/windows/) -> repo dist/
OutputDir=..\..\dist\installer
OutputBaseFilename=SpeedPulse-{#AppVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\speedpulse.exe
; unsigned build: no signtool step yet (documented SmartScreen workaround)

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
  GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\speedpulse\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SpeedPulse"; Filename: "{app}\speedpulse.exe"
Name: "{autodesktop}\SpeedPulse"; Filename: "{app}\speedpulse.exe"; \
  Tasks: desktopicon

[Run]
Filename: "{app}\speedpulse.exe"; Description: "{cm:LaunchProgram,SpeedPulse}"; \
  Flags: nowait postinstall skipifsilent
