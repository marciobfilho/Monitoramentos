$logPath = "C:\Users\marciof\Documents\GitHub\Monitoramentos\Tcping\logs"

while($true) {
    # Pega o arquivo mais novo
    $arquivo = Get-ChildItem $logPath | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    
    if ($arquivo) {
        $caminhoCompleto = "$logPath\$($arquivo.Name)"
        
        # Lê o arquivo de uma forma que não bloqueia o tcping
        $linhas = Get-Content $caminhoCompleto -Tail 1 -ErrorAction SilentlyContinue
        
        foreach ($linha in $linhas) {
            # Procura o padrão de tempo (ex: time=15.4ms ou time=500ms)
            if ($linha -match "time=([0-9.]+)") {
                $tempo = [double]$matches[1]
                
                if ($tempo -gt 500) {
                    $wshell = New-Object -ComObject WScript.Shell
                    # O número 2 abaixo faz o aviso sumir em 2 segundos para não acumular janelas
                    $wshell.Popup("LENTIDÃO DETECTADA: $tempo ms", 2, "Monitoramento Datasul", 48)
                }
            }
        }
    }
    Start-Sleep -Milliseconds 500 # Verifica 2 vezes por segundo
}