@echo off
setlocal
call "%~dp0scripts\windows\clean_public_release.bat" %*
exit /b %errorlevel%
