@echo off
REM Native stop script template for workbuddy2api on Windows.
REM Copy this file and point WB2API_STOP_SCRIPT to it.

tasklist | findstr /i "wb2api.exe" >nul
if errorlevel 1 (
    echo workbuddy2api is not running
    exit /b 0
)

taskkill /f /im wb2api.exe >nul 2>&1
exit /b 0
