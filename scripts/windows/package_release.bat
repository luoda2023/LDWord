@echo off
setlocal EnableExtensions
set "REPO_ROOT=%~dp0..\.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"
cd /d "%REPO_ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Missing release environment: .venv
    echo Run install_env.bat with CPython 3.12 first.
    exit /b 1
)

echo [1/2] Verify pinned release environment
".venv\Scripts\python.exe" "scripts\verify_release_environment.py"
if errorlevel 1 exit /b 1

echo [2/2] Run clean-revision release pipeline
".venv\Scripts\python.exe" "scripts\build_release.py" %*
exit /b %errorlevel%
