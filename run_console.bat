@echo off
title AgentRadar Console
cd /d "%~dp0"
echo ========================================================
echo   AgentRadar 控制台调试模式 (保持前台输出日志)
echo ========================================================
python src\main.py
pause
