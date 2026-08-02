@echo off
setlocal EnableExtensions
set "REPO_ROOT=%~dp0..\.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"
cd /d "%REPO_ROOT%"

echo This command removes generated build and legacy dist outputs only.
echo It never deletes .venv, the version-controlled spec, logs, or user libraries.

if exist "build" rmdir /s /q "build"
if exist "build" (
    echo [ERROR] Failed to remove generated build directory.
    exit /b 1
)
if exist "dist" rmdir /s /q "dist"
if exist "dist" (
    echo [ERROR] Failed to remove generated legacy dist directory.
    exit /b 1
)

echo [OK] Generated build outputs removed.
exit /b 0
