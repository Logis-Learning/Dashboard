@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ============================================
echo  Instalando Dashboard como servico Windows
echo ============================================

:: Verifica se esta rodando como Administrador
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERRO: Execute este arquivo como Administrador.
    echo  Clique com botao direito ^> Executar como administrador
    echo.
    pause
    exit /b 1
)

:: Encontra o Python
for /f "delims=" %%i in ('where pythonw 2^>nul') do set PYTHONW=%%i
if "%PYTHONW%"=="" (
    echo  ERRO: pythonw nao encontrado. Verifique se o Python esta instalado.
    pause
    exit /b 1
)

set SCRIPT=%~dp0servidor.py
set NOME_TAREFA=Dashboard_Universidade_SIMPAR

:: Remove tarefa anterior se existir
schtasks /delete /tn "%NOME_TAREFA%" /f >nul 2>&1

:: Cria tarefa que inicia no boot (sem precisar de login)
schtasks /create ^
  /tn "%NOME_TAREFA%" ^
  /tr "\"%PYTHONW%\" \"%SCRIPT%\"" ^
  /sc onstart ^
  /ru SYSTEM ^
  /rl HIGHEST ^
  /f >nul

if errorlevel 1 (
    echo  ERRO ao criar tarefa agendada.
    pause
    exit /b 1
)

echo.
echo  Servico instalado com sucesso!
echo  O servidor vai iniciar automaticamente no proximo boot.
echo.
echo  Para iniciar agora sem reiniciar:
echo    schtasks /run /tn "%NOME_TAREFA%"
echo.
echo  Para remover o servico:
echo    schtasks /delete /tn "%NOME_TAREFA%" /f
echo.

set /p INICIAR="Deseja iniciar o servidor agora? (S/N): "
if /i "%INICIAR%"=="S" (
    schtasks /run /tn "%NOME_TAREFA%"
    echo  Servidor iniciado! Aguarde alguns segundos...
    timeout /t 4 /nobreak > nul
    start "" http://localhost:8050
)

pause
