@echo off
setlocal

REM Double-click this file to start the financial sentiment system.
REM It starts the Flask backend if needed, then opens the Web UI.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_financial_sentiment.ps1"

if errorlevel 1 (
    echo.
    echo Startup failed. Please check the message above.
    pause
)
