@echo off
rem 日志解析与统计报告生成器 --- 双击本文件即可启动交互窗口
cd /d "%~dp0"
.venv\Scripts\python log_parser_gui.py
if errorlevel 1 pause