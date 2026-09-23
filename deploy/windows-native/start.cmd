@echo off
REM One-click start wrapper for Windows native deployment.
REM It launches the management console and the upstream gateway.

cd /d "%~dp0"
start /b python -m uvicorn server.main:app --host 0.0.0.0 --port 7864
exit /b 0
