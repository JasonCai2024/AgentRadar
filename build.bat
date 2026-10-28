@echo off
cd /d "%~dp0"
title Building AgentRadar Single Executable...
echo ========================================================
echo   AgentRadar 一键构建脚本 (PyInstaller Standalone Exe)
echo ========================================================
python scripts\build_exe.py
pause
