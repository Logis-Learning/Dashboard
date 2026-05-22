@echo off
cd /d "%~dp0"
echo.
echo Agendando atualizacao automatica a cada 1 hora...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "^
  $script = '%~dp0atualizar_auto.bat';^
  $action  = New-ScheduledTaskAction -Execute 'cmd' -Argument ('/c \"' + $script + '\"');^
  $trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 1) -Once -At '07:00';^
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2);^
  Register-ScheduledTask -TaskName 'SimparAtualizar' -Action $action -Trigger $trigger -Settings $settings -Force^
"

if errorlevel 1 (
    echo ERRO ao criar a tarefa.
    pause
    exit /b 1
)

echo.
echo Tarefa criada com sucesso!
echo Roda a cada 1 hora a partir das 07:00 de hoje.
echo.
echo Para verificar:  Agendador de Tarefas ^> SimparAtualizar
echo Para cancelar:  schtasks /delete /tn SimparAtualizar /f
echo.
pause
