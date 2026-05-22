@echo off
cd /d "%~dp0"
set LOG=%~dp0logs\atualizar_auto.log
if not exist "%~dp0logs" mkdir "%~dp0logs"
echo [%date% %time%] Iniciando atualizacao >> "%LOG%"

python skore_not_started_20.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERRO no skore_not_started_20.py >> "%LOG%"
    exit /b 1
)

python gerar_dados_dash.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERRO no gerar_dados_dash.py >> "%LOG%"
    exit /b 1
)

copy /Y dashboard_simpar.html index.html > nul
git add dados.js index.html dashboard_simpar.html
git commit -m "Atualiza dados automatico" >> "%LOG%" 2>&1
git push >> "%LOG%" 2>&1

echo [%date% %time%] Concluido com sucesso >> "%LOG%"
