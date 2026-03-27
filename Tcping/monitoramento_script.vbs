Set WshShell = CreateObject("WScript.Shell")

' Inicia o monitoramento (BAT)
WshShell.Run chr(34) & "C:\Users\marciof\Documents\GitHub\Monitoramentos\Tcping\monitoramento.bat" & Chr(34), 0

' Inicia o alerta - Importante usar o nome exato: alertar_ping.ps1
WshShell.Run "powershell.exe -ExecutionPolicy Bypass -File C:\Users\marciof\Documents\GitHub\Monitoramentos\Tcping\alertar_ping.ps1", 0

Set WshShell = Nothing