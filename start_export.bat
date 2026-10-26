@echo off
setlocal EnableExtensions
rem ===================================================================
rem  BlenderLightMapExport - Batch-Export (Einzeldatei oder Ordner)
rem
rem  Verwendung:
rem    start_export.bat <Eingabe(Datei|Ordner)> <Ausgabeordner> [Optionen]
rem    start_export.bat --config config.json [Optionen]
rem
rem  Beispiele:
rem    start_export.bat C:\Models\car.glb C:\Export
rem    start_export.bat C:\Models C:\Export --format FBX --preset HIGH --recursive
rem    start_export.bat --config config.example.json
rem    start_export.bat C:\Models C:\Export --set bake.samples=32 --set image.format=EXR
rem
rem  Alle Optionen: scripts\batch_export.py (Kopf der Datei)
rem  Blender-Pfad: Umgebungsvariable BLENDER_EXE oder Standardpfad unten.
rem  Exit-Codes: 0 OK, 1 mindestens eine Datei fehlgeschlagen,
rem              2 Konfigurationsfehler, 3 Umgebungsfehler (Blender/Pfade)
rem ===================================================================

set "SCRIPT_DIR=%~dp0"
if "%BLENDER_EXE%"=="" set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

if not exist "%BLENDER_EXE%" (
    echo [FEHLER] Blender nicht gefunden: "%BLENDER_EXE%"
    echo          Setze die Umgebungsvariable BLENDER_EXE auf den Pfad zu blender.exe
    exit /b 3
)

if "%~1"=="" (
    echo Verwendung: %~nx0 ^<Eingabe^> ^<Ausgabeordner^> [Optionen]
    echo        oder: %~nx0 --config config.json [Optionen]
    echo Optionen siehe: scripts\batch_export.py
    exit /b 2
)

echo [INFO] Blender: "%BLENDER_EXE%"
"%BLENDER_EXE%" --background --factory-startup --python "%SCRIPT_DIR%scripts\batch_export.py" -- %*
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" (
    echo [INFO] Export abgeschlossen.
) else (
    echo [WARNUNG] Export beendet mit Exit-Code %RC%.
)
exit /b %RC%
