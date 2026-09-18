@echo off
chcp 65001 > nul
echo ============================================================
echo 🚀 Iniciando CV Auto - Sistema de Automatización
echo ============================================================
IF EXIST .venv\Scripts\python.exe (
    .venv\Scripts\python.exe run_all.py %*
) ELSE (
    python run_all.py %*
)
pause
