@echo off
setlocal
rem Führt die automatisierten Tests in Blender aus.
rem Verwendung: run_tests.bat [Optionen fuer scripts\run_tests.py]
rem Beispiel:   run_tests.bat --no-slow -k test_uv

set "SCRIPT_DIR=%~dp0"
if "%BLENDER_EXE%"=="" set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
if not exist "%BLENDER_EXE%" (
    echo [FEHLER] Blender nicht gefunden: "%BLENDER_EXE%"
    echo Setze die Umgebungsvariable BLENDER_EXE auf den Pfad zu blender.exe
    exit /b 3
)
"%BLENDER_EXE%" --background --factory-startup --python "%SCRIPT_DIR%scripts\run_tests.py" -- %*
set "RC=%ERRORLEVEL%"
echo Exit-Code: %RC%
exit /b %RC%
