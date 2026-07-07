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
if exist ".venv" (
    rmdir /s /q ".venv"
    if exist ".venv" (
        echo [ERROR] Failed to remove .venv. Close Python/Qt processes and try again.
        exit /b 1
    )
)

echo [2/4] Remove local build outputs
if exist "build" (
    rmdir /s /q "build"
    if exist "build" (
        echo [ERROR] Failed to remove build.
        exit /b 1
    )
)
if exist "dist" (
    rmdir /s /q "dist"
    if exist "dist" (
        echo [ERROR] Failed to remove dist.
        exit /b 1
    )
)

echo [3/4] Remove generated spec and runtime logs
for %%F in (*.spec) do del /q "%%~fF"
for %%F in (*.spec) do (
    echo [ERROR] Failed to remove generated spec: %%~fF
    exit /b 1
)
if exist "crash.log" (
    del /q "crash.log"
    if exist "crash.log" (
        echo [ERROR] Failed to remove crash.log.
        exit /b 1
    )
)
if exist "demo_crash.log" (
    del /q "demo_crash.log"
    if exist "demo_crash.log" (
        echo [ERROR] Failed to remove demo_crash.log.
        exit /b 1
    )
)
if exist "alavette_form.log" (
    del /q "alavette_form.log"
    if exist "alavette_form.log" (
        echo [ERROR] Failed to remove alavette_form.log.
        exit /b 1
    )
)

echo [4/4] Done
echo Workspace cleaned for public MIT-source release checks.
exit /b 0
