@echo off
setlocal
set "REPO_ROOT=%~dp0..\.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"
cd /d "%REPO_ROOT%"

set "APP_NAME=Alavette-Form_V1.0.exe"
tasklist /FI "IMAGENAME eq %APP_NAME%" 2>nul | find /I "%APP_NAME%" >nul
if not errorlevel 1 (
    echo [ERROR] %APP_NAME% is running.
    echo Please close the app before cleaning release artifacts.
    exit /b 1
)

echo [1/4] Remove local virtual environment
if exist ".venv" rmdir /s /q ".venv"

echo [2/4] Remove local build outputs
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo [3/4] Remove generated spec and runtime logs
for %%F in (*.spec) do del /q "%%~fF"
if exist "crash.log" del /q "crash.log"
if exist "demo_crash.log" del /q "demo_crash.log"
if exist "alavette_form.log" del /q "alavette_form.log"

echo [4/4] Done
echo Workspace cleaned for public MIT-source release checks.
exit /b 0
