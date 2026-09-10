@echo off
chcp 65001 >nul
set "PROJECT_DIR=%~dp0"
if not exist "%PROJECT_DIR%.venv\Scripts\python.exe" (
  echo 正在创建虚拟环境并安装依赖...
  python -m venv "%PROJECT_DIR%.venv"
  "%PROJECT_DIR%.venv\Scripts\python.exe" -m pip install -r "%PROJECT_DIR%requirements.txt"
)
"%PROJECT_DIR%.venv\Scripts\python.exe" "%PROJECT_DIR%main.py"
