@echo off
REM Stop the Marx reference locator service started by start_service.bat
setlocal enabledelayedexpansion
cd /d "%~dp0"

if not exist "logs\marxref.pid" (
  echo [i] logs\marxref.pid not found - service is probably not running.
  pause
  exit /b 1
)

set /p PID=<"logs\marxref.pid"
echo Stopping PID !PID! ...
taskkill /PID !PID! /F
if errorlevel 1 (
  echo [i] Process not found. It may have exited already.
) else (
  echo [ok] Stopped.
)
del "logs\marxref.pid" >nul 2>&1
pause
