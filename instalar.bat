@echo off
rem Instala a ferramenta num computador novo (Windows). Basta dar dois cliques.
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0instalar.ps1"
pause
