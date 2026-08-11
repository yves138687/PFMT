@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "ROOT_DIR=%%~fI"
set "SERVER_SCRIPT=%ROOT_DIR%\scripts\dev\start_server.ps1"
set "WEB_SCRIPT=%ROOT_DIR%\scripts\dev\start_web.ps1"
set "FRPC_SCRIPT=%ROOT_DIR%\scripts\dev\start_frpc_vite.ps1"
set "WEB_DIR=%ROOT_DIR%\web"
set "START_FRPC=1"
set "DRY_RUN=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--dry-run" set "DRY_RUN=1"
if /I "%~1"=="--no-frpc" set "START_FRPC=0"
if /I "%~1"=="--local-only" set "START_FRPC=0"
shift
goto parse_args

:args_done

if "%DRY_RUN%"=="1" (
    echo ROOT_DIR=%ROOT_DIR%
    echo SERVER_SCRIPT=%SERVER_SCRIPT%
    echo WEB_SCRIPT=%WEB_SCRIPT%
    echo FRPC_SCRIPT=%FRPC_SCRIPT%
    echo WEB_DIR=%WEB_DIR%
    echo START_FRPC=%START_FRPC%
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

ping -n 3 127.0.0.1 >nul

echo Starting PFMT frontend...
start "PFMT frontend" /D "%WEB_DIR%" pwsh -NoExit -ExecutionPolicy Bypass -File "%WEB_SCRIPT%" -PackageManager npm

ping -n 3 127.0.0.1 >nul

if "%START_FRPC%"=="1" (
    if exist "%FRPC_SCRIPT%" (
        echo Starting PFMT FRP tunnel...
        start "PFMT frpc vite" /D "%ROOT_DIR%" pwsh -NoExit -ExecutionPolicy Bypass -File "%FRPC_SCRIPT%"
    ) else (
        echo Warning: missing FRP startup script, skip public tunnel: %FRPC_SCRIPT%
    )
) else (
    echo Skipping PFMT FRP tunnel.
)

echo.
if "%START_FRPC%"=="1" (
    echo PFMT startup commands have been opened. FRP tunnel is optional; if it fails, local services can still be used.
) else (
    echo PFMT local startup commands have been opened.
)
echo Backend:  http://127.0.0.1:8000
echo Frontend local: http://127.0.0.1:5173
if "%START_FRPC%"=="1" echo Public dev: see VITE_PUBLIC_DEV_HOST and FRP/Nginx configuration.
echo Close those windows to stop the services.
exit /b 0
