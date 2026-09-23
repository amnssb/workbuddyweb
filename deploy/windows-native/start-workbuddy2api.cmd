@echo off
REM Native start script template for workbuddy2api on Windows.
REM Copy this file and point WB2API_START_SCRIPT to it.

if "%WB2API_BIN%"=="" set WB2API_BIN=wb2api.exe
if "%WB2API_LOG%"=="" set WB2API_LOG=server.err.log

REM Start the upstream gateway in the background and redirect logs.
start /b %WB2API_BIN% > %WB2API_LOG% 2>&1
exit /b 0
