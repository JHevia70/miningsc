; Inno Setup script for MiningSC Scanner
; Compile with: iscc installer.iss
; Output: F:\SC_temp\installer\MiningScanner_Setup.exe

#define AppName      "MiningSC Scanner"
#define AppVersion   "1.0.0"
#define AppPublisher "MiningSC"
#define AppURL       "https://miningsc.vercel.app"
#define AppExeName   "MiningScanner.exe"
#define SourceDir    "F:\SC_temp\dist\MiningScanner"
#define OutputDir    "F:\SC_temp\installer"

[Setup]
AppId={{B3F1A2C4-7E8D-4F9A-B0C1-D2E3F4A5B6C7}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\MiningSC Scanner
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=MiningScanner_Setup
SetupIconFile=
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Admin needed for installer only (to write to Program Files)
; The installed exe itself does NOT require admin elevation
PrivilegesRequired=admin
; Show the license/readme on install
; LicenseFile=LICENSE.txt
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon";    Description: "{cm:CreateDesktopIcon}";    GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon";    Description: "Launch MiningSC Scanner when Windows starts"; GroupDescription: "Startup";

[Files]
; Copy the entire PyInstaller output folder
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";                Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}";      Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}";        Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}";          Filename: "{app}\{#AppExeName}"; Tasks: startupicon

[Run]
; Offer to launch the app after install
Filename: "{app}\{#AppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; \
  Flags: nowait postinstall skipifsilent runascurrentuser

[UninstallRun]
; Kill the running process before uninstalling
Filename: "taskkill.exe"; Parameters: "/f /im {#AppExeName}"; Flags: runhidden; RunOnceId: "KillScanner"

[Code]
// Kill any running instance before upgrading
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
    Exec('taskkill.exe', '/f /im {#AppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

