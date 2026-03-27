@echo off
set EXE_PATH=C:\Users\marciof\Documents\GitHub\Monitoramentos\Tcping\tcping.exe
set LOG_DIR=C:\Users\marciof\Documents\GitHub\Monitoramentos\Tcping\logs

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f "tokens=*" %%a in ('powershell -Command "Get-Date -format 'yyyy-MM-dd_HH-mm-ss'"') do set TIMESTAMP=%%a
set MYLOG=%LOG_DIR%\tcping_%TIMESTAMP%.txt

:: O comando abaixo inicia o monitoramento
"%EXE_PATH%" -t -d unimedencosta183931.datasul.cloudtotvs.com.br 491 > "%MYLOG%"