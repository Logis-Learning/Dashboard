@echo off
chcp 65001 > nul
cd /d "%~dp0"

:: Se servidor ja esta rodando, so abre o navegador
netstat -aon 2>nul | findstr ":8050 " | findstr "LISTENING" > nul 2>&1
if not errorlevel 1 (
    start "" http://localhost:8050
    exit /b 0
)

:: Inicia servidor em background sem janela
start "" /B pythonw servidor.py

:: Aguarda servidor subir
timeout /t 3 /nobreak > nul

:: Abre o dashboard
start "" http://localhost:8050
