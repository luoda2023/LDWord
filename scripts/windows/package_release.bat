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

set "APP_NAME=Alavette-Form_V1.0"
set "DIST_DIR=dist\%APP_NAME%"
set "ZIP_PATH=dist\%APP_NAME%.zip"

tasklist /FI "IMAGENAME eq %APP_NAME%.exe" 2>nul | find /I "%APP_NAME%.exe" >nul
if not errorlevel 1 (
    echo [ERROR] %APP_NAME%.exe is running.
    echo Please close the app before packaging, then run this script again.
    pause
    exit /b 1
)

echo [1/6] Ensure PyInstaller is installed
".venv\Scripts\python.exe" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller is missing in .venv
    echo Run "install_env.bat" to refresh the environment, then try again.
    pause
    exit /b 1
) else (
    echo PyInstaller already installed.
)

echo [2/6] Build third-party license bundle
".venv\Scripts\python.exe" "scripts\build_license_bundle.py"
if errorlevel 1 (
    echo [ERROR] License bundle generation failed
    pause
    exit /b 1
)

echo [3/6] Stage immutable product configuration
".venv\Scripts\python.exe" "scripts\stage_release_config_library.py"
if errorlevel 1 (
    echo [ERROR] Product configuration staging failed
    pause
    exit /b 1
)

echo [4/6] Build release package from main.py
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed ^
    --name "%APP_NAME%" ^
    --runtime-hook "scripts\windows\pyinstaller_font_engine_hook.py" ^
    --hidden-import PySide6.QtCore ^
    --hidden-import PySide6.QtGui ^
    --hidden-import PySide6.QtWidgets ^
    --hidden-import PySide6.QtSvg ^
    --hidden-import shiboken6 ^
    --hidden-import src.config.entity_archive_codec ^
    --hidden-import src.config.entity_bundle ^
    --hidden-import src.ui.panels.theme_panel ^
    --hidden-import src.ui.panels.workbench.batch_generation_detail ^
    --hidden-import src.ui.panels.workbench.batch_generation_source_area ^
    --hidden-import src.shared.ui.button_style ^
    --hidden-import src.shared.ui.dashed_separator ^
    --hidden-import src.shared.ui.detail_pane_controller ^
    --hidden-import src.shared.ui.dynamic_navigation_rail ^
    --hidden-import src.shared.ui.flow_layout ^
    --hidden-import src.shared.ui.flow_section ^
    --hidden-import src.shared.ui.input_style ^
    --hidden-import src.shared.ui.library_action_row ^
    --hidden-import src.shared.ui.master_detail_shell ^
    --hidden-import src.shared.ui.navigation_card ^
    --hidden-import src.shared.ui.segmented_control ^
    --hidden-import src.shared.ui.summary_grid ^
    --hidden-import src.shared.ui.template_summary_card ^
    --hidden-import src.shared.ui.themed_radio_button ^
    --hidden-import src.shared.ui.toast ^
    --hidden-import src.services.material_attachments.processing ^
    --exclude-module PySide6.Qt3DAnimation ^
    --exclude-module PySide6.Qt3DCore ^
    --exclude-module PySide6.Qt3DExtras ^
    --exclude-module PySide6.Qt3DInput ^
    --exclude-module PySide6.Qt3DLogic ^
    --exclude-module PySide6.Qt3DRender ^
    --exclude-module PySide6.QtBluetooth ^
    --exclude-module PySide6.QtCharts ^
    --exclude-module PySide6.QtDataVisualization ^
    --exclude-module PySide6.QtDesigner ^
    --exclude-module PySide6.QtHelp ^
    --exclude-module PySide6.QtGraphs ^
    --exclude-module PySide6.QtGraphsWidgets ^
    --exclude-module PySide6.QtHttpServer ^
    --exclude-module PySide6.QtLocation ^
    --exclude-module PySide6.QtMultimedia ^
    --exclude-module PySide6.QtMultimediaWidgets ^
    --exclude-module PySide6.QtNetworkAuth ^
    --exclude-module PySide6.QtNfc ^
    --exclude-module PySide6.QtOpenGL ^
    --exclude-module PySide6.QtOpenGLWidgets ^
    --exclude-module PySide6.QtPdf ^
    --exclude-module PySide6.QtPdfWidgets ^
    --exclude-module PySide6.QtPositioning ^
    --exclude-module PySide6.QtQml ^
    --exclude-module PySide6.QtQuick ^
    --exclude-module PySide6.QtQuick3D ^
    --exclude-module PySide6.QtQuickWidgets ^
    --exclude-module PySide6.QtRemoteObjects ^
    --exclude-module PySide6.QtScxml ^
    --exclude-module PySide6.QtSensors ^
    --exclude-module PySide6.QtSerialBus ^
    --exclude-module PySide6.QtSerialPort ^
    --exclude-module PySide6.QtSpatialAudio ^
    --exclude-module PySide6.QtSql ^
    --exclude-module PySide6.QtStateMachine ^
    --exclude-module PySide6.QtTextToSpeech ^
    --exclude-module PySide6.QtWebChannel ^
    --exclude-module PySide6.QtWebEngineCore ^
    --exclude-module PySide6.QtWebEngineQuick ^
    --exclude-module PySide6.QtWebEngineWidgets ^
    --exclude-module PySide6.QtWebSockets ^
    --exclude-module PIL.AvifImagePlugin ^
    --exclude-module PIL._avif ^
    --add-data "defaults;defaults" ^
    --add-data "build\release_config_library;config_library" ^
    --add-data "count_profiles;count_profiles" ^
    --add-data "src\shared\ui\icons;src\shared\ui\icons" ^
    --add-data "LICENSE;." ^
    --add-data "THIRD_PARTY_NOTICES.md;." ^
    --add-data "licenses;licenses" ^
    main.py
if errorlevel 1 (
    echo [ERROR] Packaging failed
    pause
    exit /b 1
)

echo [5/6] Copy human-readable notices next to the EXE
if not exist "%DIST_DIR%" (
    echo [ERROR] Dist folder not found: %DIST_DIR%
    pause
    exit /b 1
)
copy /Y "LICENSE" "%DIST_DIR%\LICENSE" >nul
copy /Y "THIRD_PARTY_NOTICES.md" "%DIST_DIR%\THIRD_PARTY_NOTICES.md" >nul
if exist "%DIST_DIR%\licenses" rmdir /s /q "%DIST_DIR%\licenses"
xcopy /E /I /Y "licenses" "%DIST_DIR%\licenses" >nul
if exist "defaults" (
    if exist "%DIST_DIR%\defaults" rmdir /s /q "%DIST_DIR%\defaults"
    xcopy /E /I /Y "defaults" "%DIST_DIR%\defaults" >nul
)

echo Removing accidentally collected Qt add-on payloads, if any...
for %%D in ("%DIST_DIR%\_internal\PySide6" "%DIST_DIR%\PySide6") do (
    if exist "%%~D" (
        for %%F in (
            Qt6WebEngineCore.dll
            Qt6WebEngineQuick.dll
            Qt6WebEngineWidgets.dll
            Qt6QmlMeta.dll
            Qt6QmlModels.dll
            Qt6QmlWorkerScript.dll
            Qt6Qml.dll
            Qt6Quick.dll
            Qt6Quick3D.dll
            Qt6Multimedia.dll
            Qt6Charts.dll
            Qt6Pdf.dll
        ) do (
            if exist "%%~D\%%~F" del /q "%%~D\%%~F"
        )
        for %%P in (qml resources translations) do (
            if exist "%%~D\%%~P" rmdir /s /q "%%~D\%%~P"
        )
    )
)

echo [6/6] Create compressed release archive
if exist "%ZIP_PATH%" del /q "%ZIP_PATH%"
for %%I in ("%DIST_DIR%") do set "DIST_DIR_ABS=%%~fI"
for %%I in ("%ZIP_PATH%") do set "ZIP_PATH_ABS=%%~fI"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Compress-Archive -LiteralPath $env:DIST_DIR_ABS -DestinationPath $env:ZIP_PATH_ABS -CompressionLevel Optimal -Force"
if errorlevel 1 (
    echo [ERROR] Failed to create release archive
    pause
    exit /b 1
)

echo [OK] Build completed.
echo Output folder: %DIST_DIR%
echo Output archive: %ZIP_PATH%
exit /b 0
