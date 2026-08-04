@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "ROOT_DIR=%%~fI"
set "SERVER_SCRIPT=%ROOT_DIR%\scripts\dev\start_server.ps1"
set "WEB_SCRIPT=%ROOT_DIR%\scripts\dev\start_web.ps1"
set "WEB_DIR=%ROOT_DIR%\web"

if /I "%~1"=="--dry-run" (
    echo ROOT_DIR=%ROOT_DIR%
    echo SERVER_SCRIPT=%SERVER_SCRIPT%
    echo WEB_SCRIPT=%WEB_SCRIPT%
    echo WEB_DIR=%WEB_DIR%
    exit /b 0
)

where pwsh >nul 2>nul
if errorlevel 1 (
    echo PowerShell 7 ^(pwsh^) was not found. Please install PowerShell 7 or start the two .ps1 scripts manually.
    pause
    exit /b 1
)

if not exist "%SERVER_SCRIPT%" (
    echo Missing backend startup script: %SERVER_SCRIPT%
    pause
    exit /b 1
)

if not exist "%WEB_SCRIPT%" (
    echo Missing frontend startup script: %WEB_SCRIPT%
    pause
    exit /b 1
)

if not exist "%WEB_DIR%\package.json" (
    echo Missing frontend package file: %WEB_DIR%\package.json
    pause
    exit /b 1
)

echo Starting PFMT backend...
start "PFMT backend" /D "%ROOT_DIR%" pwsh -NoExit -ExecutionPolicy Bypass -File "%SERVER_SCRIPT%"

timeout /t 2 /nobreak >nul

echo Starting PFMT frontend...
start "PFMT frontend" /D "%WEB_DIR%" pwsh -NoExit -ExecutionPolicy Bypass -File "%WEB_SCRIPT%" -PackageManager npm

echo.
echo PFMT startup commands have been opened in two windows.
echo Backend:  http://127.0.0.1:8000
echo Frontend local: http://127.0.0.1:5173
echo Frontend LAN:   see the PFMT frontend window for your IPv4 URL.
echo Close those windows to stop the services.
exit /b 0
