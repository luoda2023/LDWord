@echo off
setlocal
set "REPO_ROOT=%~dp0..\.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"
cd /d "%REPO_ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Missing virtual environment: .venv
    echo Run "install_env.bat" first.
    pause
    exit /b 1
)

set "APP_NAME=Lark-Formatter_V1.0"
set "DIST_DIR=dist\%APP_NAME%"

tasklist /FI "IMAGENAME eq %APP_NAME%.exe" 2>nul | find /I "%APP_NAME%.exe" >nul
if not errorlevel 1 (
    echo [ERROR] %APP_NAME%.exe is running.
    echo Please close the app before packaging, then run this script again.
    pause
    exit /b 1
)

echo [1/3] Ensure PyInstaller is installed
".venv\Scripts\python.exe" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller is missing in .venv
    echo Run "install_env.bat" to refresh the environment, then try again.
    pause
    exit /b 1
) else (
    echo PyInstaller already installed.
)

echo [2/3] Build release package from main.py
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed ^
    --name "%APP_NAME%" ^
    --hidden-import PySide6.QtCore ^
    --hidden-import PySide6.QtGui ^
    --hidden-import PySide6.QtWidgets ^
    --hidden-import PySide6.QtSvg ^
    --hidden-import shiboken6 ^
    --exclude-module PySide6.QtGraphs ^
    --exclude-module PySide6.QtGraphsWidgets ^
    --exclude-module PySide6.QtHttpServer ^
    --exclude-module PySide6.QtNetworkAuth ^
    --exclude-module PySide6.QtQuick3D ^
    --add-data "defaults;defaults" ^
    --add-data "src\ui\icons;src\ui\icons" ^
    --add-data "LICENSE;." ^
    --add-data "THIRD_PARTY_NOTICES.md;." ^
    main.py
if errorlevel 1 (
    echo [ERROR] Packaging failed
    pause
    exit /b 1
)

echo [3/3] Copy human-readable notices next to the EXE
if not exist "%DIST_DIR%" (
    echo [ERROR] Dist folder not found: %DIST_DIR%
    pause
    exit /b 1
)
copy /Y "LICENSE" "%DIST_DIR%\LICENSE" >nul
copy /Y "THIRD_PARTY_NOTICES.md" "%DIST_DIR%\THIRD_PARTY_NOTICES.md" >nul
if exist "defaults" (
    if exist "%DIST_DIR%\defaults" rmdir /s /q "%DIST_DIR%\defaults"
    xcopy /E /I /Y "defaults" "%DIST_DIR%\defaults" >nul
)

echo [OK] Build completed.
echo Output folder: %DIST_DIR%
exit /b 0
