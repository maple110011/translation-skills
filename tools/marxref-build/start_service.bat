@echo off
REM ---------------------------------------------------------------------------
REM  Marx reference locator - start the service in the background.
REM
REM    start_service.bat          -> port 8080
REM    start_service.bat 9000     -> port 9000
REM
REM  NOTE: uses findstr / ping instead of find / timeout on purpose -
REM        find and timeout collide with Unix tools when Git Bash is on PATH.
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"
set PORT=8080
if not "%~1"=="" set PORT=%~1
if not exist logs mkdir logs

where pythonw >nul 2>&1
if errorlevel 1 (
  echo [x] pythonw not found. Install Python 3.8+ and make sure it is on PATH.
  pause
  exit /b 1
)

if exist "logs\marxref.pid" call :killold

REM Redirect the child stdio to files. If it inherits the console pipe it can be
REM taken down together with the parent shell.
start "" /b pythonw server.py --host 0.0.0.0 --port %PORT% --log "logs\server.log" --pid "logs\marxref.pid" >>"logs\stderr.log" 2>&1

set /a TRIES=0
:wait
set /a TRIES+=1
powershell -NoProfile -Command "try{(Invoke-WebRequest -Uri 'http://127.0.0.1:%PORT%/healthz' -UseBasicParsing -TimeoutSec 2).StatusCode|Out-Null;exit 0}catch{exit 1}" >nul 2>&1
if not errorlevel 1 goto up
if %TRIES% GEQ 25 goto fail
ping -n 2 127.0.0.1 >nul
goto wait

:fail
echo [x] Service did not answer on port %PORT%. Check logs\server.log and logs\stderr.log
pause
exit /b 1

:up
echo [ok] Service is up:  http://127.0.0.1:%PORT%/healthz
echo.
echo      POST /v1/match            single quote
echo      POST /v1/match/batch      list of quotes
echo      GET  /v1/meta  /healthz  /v1/openapi.json
echo.
echo      LAN access:  http://^<this-machine-ip^>:%PORT%/healthz
echo      Log:  logs\server.log
echo      Stop: stop_service.bat
pause
exit /b 0

:killold
set /p OLDPID=<"logs\marxref.pid"
if "%OLDPID%"=="" exit /b 0
tasklist /FI "PID eq %OLDPID%" 2>nul | findstr /C:"%OLDPID%" >nul
if not errorlevel 1 (
  echo [i] An instance is already running ^(PID %OLDPID%^), stopping it first ...
  taskkill /PID %OLDPID% /F >nul 2>&1
  ping -n 2 127.0.0.1 >nul
)
exit /b 0
