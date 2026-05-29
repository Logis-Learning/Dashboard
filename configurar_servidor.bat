@echo off
cd /d "%~dp0"
echo.
echo =====================================================
echo   Universidade SIMPAR - Configurar Servidor 24h
echo =====================================================
echo.
echo Isso vai criar 2 tarefas no Agendador de Tarefas:
echo   1. Iniciar servidor Flask ao ligar o PC
echo   2. Atualizar dados + publicar no GitHub a cada 1h
echo.
pause

:: ─── Tarefa 1: Inicia servidor.py ao boot ─────────────────────────────────
echo [1/2] Criando tarefa de inicializacao do servidor...

powershell -NoProfile -ExecutionPolicy Bypass -Command "^
  $action  = New-ScheduledTaskAction -Execute 'pythonw' -Argument 'servidor.py' -WorkingDirectory '%~dp0';^
  $trigger = New-ScheduledTaskTrigger -AtStartup;^
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Days 365);^
  $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest;^
  Register-ScheduledTask -TaskName 'SimparServidor' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force^
"

if errorlevel 1 (
    echo ERRO ao criar tarefa do servidor.
    pause
    exit /b 1
)
echo    OK - Servidor iniciara automaticamente ao ligar o PC.

:: ─── Tarefa 2: Atualiza dados + push GitHub a cada 1h ────────────────────
echo.
echo [2/2] Criando tarefa de atualizacao automatica ^(a cada 1h^)...

powershell -NoProfile -ExecutionPolicy Bypass -Command "^
  $script = '%~dp0atualizar_auto.bat';^
  $action  = New-ScheduledTaskAction -Execute 'cmd' -Argument ('/c \"' + $script + '\"');^
  $trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 1) -Once -At '07:00';^
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2);^
  $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest;^
  Register-ScheduledTask -TaskName 'SimparAtualizar' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force^
"

if errorlevel 1 (
    echo ERRO ao criar tarefa de atualizacao.
    pause
    exit /b 1
)
echo    OK - Dados atualizados e publicados no GitHub a cada 1 hora.

:: ─── Inicia o servidor agora sem esperar o reboot ─────────────────────────
echo.
echo Iniciando servidor agora...
start "" /B pythonw "%~dp0servidor.py"
timeout /t 3 /nobreak > nul
echo    Servidor rodando em http://localhost:8050

echo.
echo =====================================================
echo   Configuracao concluida!
echo.
echo   Servidor local:  http://localhost:8050
echo   Online:          https://logis-learning.github.io/Dashboard/
echo.
echo   Para verificar as tarefas:
echo     Agendador de Tarefas ^> SimparServidor
echo                          ^> SimparAtualizar
echo.
echo   Para parar o servidor:
echo     taskkill /f /im pythonw.exe
echo =====================================================
echo.
pause
