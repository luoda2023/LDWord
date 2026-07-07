@echo off
setlocal
cd /d "%~dp0..\.."
python scripts\engineering_gate.py %*
exit /b %ERRORLEVEL%
