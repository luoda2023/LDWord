@echo off
setlocal EnableExtensions
set "REPO_ROOT=%~dp0..\.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"
cd /d "%REPO_ROOT%"

py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Alavette Form V1.0 release tooling requires CPython 3.12.
    exit /b 1
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
    if errorlevel 1 (
        echo [ERROR] Existing .venv is not CPython 3.12. Move or remove it explicitly.
        exit /b 1
    )
) else (
    py -3.12 -m venv ".venv"
    if errorlevel 1 exit /b 1
)

echo [1/3] Pin pip
".venv\Scripts\python.exe" -m pip install "pip==26.1.2"
if errorlevel 1 exit /b 1

echo [2/3] Install reviewed release dependencies
".venv\Scripts\python.exe" -m pip install -c "requirements-release.lock" -e ".[dev,build]"
if errorlevel 1 exit /b 1

echo [3/3] Verify environment lock
".venv\Scripts\python.exe" "scripts\verify_release_environment.py"
exit /b %errorlevel%
