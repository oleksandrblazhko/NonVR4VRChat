@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem Панель керування запускається без консолі (pythonw).
rem Помилки запуску пишуться в logs\control_panel.log
set "PY=python"
set "PYW=pythonw"

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
    set "PYW=.venv\Scripts\pythonw.exe"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Python не знайдено. Встановіть Python 3.10 або створіть .venv ^(див. README.md^).
        pause
        exit /b 1
    )
)

start "" "%PYW%" control_panel.py
