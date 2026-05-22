@echo off
cd /d "%~dp0"

echo.
echo Universidade SIMPAR - Publicar Dashboard
echo.

echo [1/4] Extraindo dados da Skore...
python skore_not_started_20.py
if errorlevel 1 (
    echo ERRO ao extrair dados da Skore.
    pause
    exit /b 1
)

echo.
echo [2/4] Gerando dashboard...
python gerar_dados_dash.py
if errorlevel 1 (
    echo ERRO ao gerar dados.js.
    pause
    exit /b 1
)

echo.
echo [3/4] Atualizando index.html...
copy /Y dashboard_simpar.html index.html > nul

echo [4/4] Publicando no GitHub...
git add dados.js index.html dashboard_simpar.html gerar_dados_dash.py servidor.py
git commit -m "Atualiza dados"
git push

echo.
echo Publicado com sucesso!
echo https://logis-learning.github.io/Dashboard/
echo.
pause
