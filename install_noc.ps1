$AppDir = "\\compartilhamento\Monitoramentos\Logs_datasul"
$PythonExe = (Get-Command python).Source

# 1. Tarefa de Coleta
$ActionColeta = New-ScheduledTaskAction -Execute $PythonExe -Argument "coleta_logs.py" -WorkingDirectory $AppDir
$TriggerColeta = New-ScheduledTaskTrigger -Daily -At "00:00"
$TriggerColeta.Repetition = $(New-Object -ComObject PSConfiguration.RepetitionPattern)
$TriggerColeta.Repetition.Interval = "PT30M" 
$TriggerColeta.Repetition.Duration = "P10000D"
$SettingsColeta = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "Coleta de Logs - Datasul" -Action $ActionColeta -Trigger $TriggerColeta -Settings $SettingsColeta -User "SYSTEM" -RunLevel Highest -Force

# 2. Tarefa de Compactacao
$ActionCompacta = New-ScheduledTaskAction -Execute $PythonExe -Argument "compacta_logs.py" -WorkingDirectory $AppDir
$TriggerCompacta = New-ScheduledTaskTrigger -Daily -At "02:00"
$SettingsCompacta = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 4) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "Compactacao e Expurgo - Datasul" -Action $ActionCompacta -Trigger $TriggerCompacta -Settings $SettingsCompacta -User "SYSTEM" -RunLevel Highest -Force

Write-Host "Tarefas injetadas via UNC." -ForegroundColor Green