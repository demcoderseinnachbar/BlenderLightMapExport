@echo off
setlocal EnableExtensions
rem ===================================================================
rem  BlenderLightMapExport - Extension-ZIP bauen
rem
rem  Verwendung:
rem    build_extension.bat            Bauen, in Blender installieren und pruefen.
rem                                   War die Extension schon installiert, bleibt die
rem                                   neue Version installiert (Update); sonst wird sie
rem                                   wieder entfernt. ZIP wird nach dist\ kopiert.
rem    build_extension.bat --no-verify   Nur bauen und nach dist\ kopieren
rem
rem  Ergebnis: dist\blender_lightmap_export-<version>.zip
rem  Blender-Pfad: Umgebungsvariable BLENDER_EXE oder Standardpfad unten.
rem  Exit-Codes: 0 OK, 1 Build/Verifikation fehlgeschlagen, 3 Blender nicht gefunden
rem ===================================================================

set "SCRIPT_DIR=%~dp0"
if "%BLENDER_EXE%"=="" set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

if not exist "%BLENDER_EXE%" (
    echo [FEHLER] Blender nicht gefunden: "%BLENDER_EXE%"
    echo          Setze die Umgebungsvariable BLENDER_EXE auf den Pfad zu blender.exe
    exit /b 3
)

set "VERIFY=--verify"
if /I "%~1"=="--no-verify" set "VERIFY="

echo [INFO] Blender: "%BLENDER_EXE%"
echo [INFO] Baue Extension aus "%SCRIPT_DIR%blender_lightmap_export" ...
"%BLENDER_EXE%" --background --python "%SCRIPT_DIR%scripts\build_extension.py" -- --out "%SCRIPT_DIR%build" %VERIFY%
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo [FEHLER] Build oder Verifikation fehlgeschlagen, Exit-Code %RC%.
    exit /b 1
)

if not exist "%SCRIPT_DIR%dist" mkdir "%SCRIPT_DIR%dist"
set "ZIP="
for /f "delims=" %%F in ('dir /b /o-d "%SCRIPT_DIR%build\blender_lightmap_export-*.zip" 2^>nul') do (
    if not defined ZIP set "ZIP=%%F"
)
if not defined ZIP (
    echo [FEHLER] Keine ZIP-Datei in "%SCRIPT_DIR%build" gefunden.
    exit /b 1
)
copy /Y "%SCRIPT_DIR%build\%ZIP%" "%SCRIPT_DIR%dist\%ZIP%" >nul
echo.
echo [OK] Extension gebaut: "%SCRIPT_DIR%dist\%ZIP%"
echo      Installieren in Blender: Edit ^> Preferences ^> Get Extensions ^> Install from Disk...
exit /b 0
