@echo off
title Locked - System Launcher
echo ========================================
echo   LOCKED - STARTING SYSTEM FILES
echo ========================================

:: Starting Backend Server
echo [1] Starting Backend Server (app.py)...
start "Locked Backend (app.py)" cmd /k "python %~dp0..\backend\app.py"

echo [2] Starting Observing Server (observe.py)...
start "Locked Observing (observe.py)" cmd /k "python %~dp0..\backend\observer.py"
