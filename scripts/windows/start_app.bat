@echo off
setlocal
set "REPO_ROOT=%~dp0..\.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"
cd /d "%REPO_ROOT%"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py --gui
) else (
    python main.py --gui
)
exit /b %errorlevel%
