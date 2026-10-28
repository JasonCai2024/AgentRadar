@echo off
cd /d "%~dp0"

where pythonw >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" pythonw src\main.py
    exit /b 0
)

where pyw >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" pyw src\main.py
    exit /b 0
)

if exist "E:\Python312_new\pythonw.exe" (
    start "" "E:\Python312_new\pythonw.exe" src\main.py
    exit /b 0
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" python src\main.py
    exit /b 0
)

echo [AgentRadar] Error: Python runtime not found in PATH!
echo Please install Python 3.10+ and ensure pythonw/python is in your PATH.
pause
