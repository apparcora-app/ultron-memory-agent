@echo off
title ULTRON PROTOCOL - Sovereign Launcher
cd /d "%~dp0.."
echo ============================================================
echo   [ULTRON PROTOCOL] INITIALIZING ALL SOVEREIGN SERVICES
echo ============================================================
echo 1. Launching FastAPI Web Mainframe...
start "ULTRON Web Mainframe" cmd /k "python app.py"
timeout /t 3 /nobreak >nul
echo 2. Launching Discord Gateway Bridge...
start "ULTRON Discord Bridge" cmd /k "python discord_bot.py"
echo.
echo ============================================================
echo   ALL ULTRON SYSTEMS ONLINE!
echo   Web HUD: http://localhost:8000
echo ============================================================
pause
