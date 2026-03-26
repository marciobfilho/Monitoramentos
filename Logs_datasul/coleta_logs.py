"""
=============================================================================================
Projeto: Monitoramento de Logs TOTVS Datasul
Módulo:  Motor de Coleta e Retenção (Backend)
Arquivo: coleta_logs.py

Descrição: 
Script de automação (Web Scraping) que acessa o servidor de logs do Datasul, faz o download 
dos históricos organizando-os em pastas por data (YYYY-MM-DD), atualiza os logs ativos na 
raiz do serviço e expurga snapshots órfãos para poupar espaço em disco.
Contém mecanismo de dupla-checagem para evitar corrupção de arquivos durante a rotação.
Inclui barras de progresso (tqdm) para execução manual.

Autor: Marcio Jose Gomes Bastos Filho
Data de Criação: 25/03/2026
Última Atualização: 26/03/2026
Versão: 2.2
=============================================================================================
"""

import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import urllib3
from tqdm import tqdm # Importando a barra de progresso

# Configurações Principais
MAIN_URL = "https://unimedencosta183931.datasul.cloudtotvs.com.br:8777/logs/"
DIRETORIO_BASE_LOCAL = r"\\192.168.0.247\Logs_Datasul\Producao"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def obter_conteudo_pagina(url):
    try:
        response = requests.get(url, verify=False, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        diretorios, arquivos = [], []
        for link in soup.find_all('a'):
            href = link.get('href')
            if not href or href == '../': continue
            if href.endswith('/'): diretorios.append(href)
            else: arquivos.append(href)
        return diretorios, arquivos
    except Exception as e:
        tqdm.write(f"❌ Erro ao acessar {url}: {e}")
        return [], []

def extrair_data(nome_arquivo):
    match_hifen = re.search(r'(20\d{2})-(\d{2})-(\d{2})', nome_arquivo)
    if match_hifen: return f"{match_hifen.group(1)}-{match_hifen.group(2)}-{match_hifen.group(3)}"
    match_junto = re.search(r'(20\d{2})(\d{2})(\d{2})', nome_arquivo)
    if match_junto: return f"{match_junto.group(1)}-{match_junto.group(2)}-{match_junto.group(3)}"
    return datetime.now().strftime("%Y-%m-%d")

def classificar_arquivo(nome_arquivo):
    hoje = datetime.now()
    str_hoje_hifen = hoje.strftime("%Y-%m-%d")
    str_hoje_junto = hoje.strftime("%Y%m%d")
    
    if nome_arquivo.endswith('.gz'): return 'HISTORICO'
    if str_hoje_hifen in nome_arquivo or str_hoje_junto in nome_arquivo: return 'ATIVO'
    ativos_conhecidos = ['server.log', 'boot.log', 'catalina.out', 'sib.log', 'monitortissnet.log']
    if nome_arquivo in ativos_conhecidos: return 'ATIVO'
    if re.search(r'20\d{2}[-_]?\d{2}[-_]?\d{2}', nome_arquivo): return 'HISTORICO'
    return 'ATIVO'

def main():
    tempo_inicio = datetime.now()
    hora_inicio_str = tempo_inicio.strftime("%d/%m/%Y %H:%M:%S")
    
    qtd_historicos = 0
    qtd_snapshots = 0
    qtd_limpos = 0
    
    if not os.path.exists(DIRETORIO_BASE_LOCAL): os.makedirs(DIRETORIO_BASE_LOCAL)

    print(f"\n🚀 Iniciando Coleta [{hora_inicio_str}]...")
    servicos, _ = obter_conteudo_pagina(MAIN_URL)
    
    # BARRA DE PROGRESSO GERAL (Serviços)
    pbar_geral = tqdm(servicos, desc="Progresso Geral", position=0, leave=True, colour='green')
    
    for servico in pbar_geral:
        nome_servico = servico.replace('/', '')
        pbar_geral.set_postfix_str(f"Processando: {nome_servico}")
        
        url_servico = urljoin(MAIN_URL, servico)
        pasta_destino_servico = os.path.join(DIRETORIO_BASE_LOCAL, nome_servico)
        if not os.path.exists(pasta_destino_servico): os.makedirs(pasta_destino_servico)
            
        while True:
            subdiretorios, arquivos_soltos = obter_conteudo_pagina(url_servico)
            
            pastas_horario_inicio = [d for d in subdiretorios if re.match(r'\d{4}-\d{2}-\d{2}_\d{2}_\d{2}/', d)]
            arquivos_hist_inicio = [a for a in arquivos_soltos if classificar_arquivo(a) == 'HISTORICO']
            ativos_da_rodada = []
            
            # 1. TRATA AS PASTAS CONSOLIDADAS (Pasoe)
            for pasta in pastas_horario_inicio:
                data_pasta_pasoe = pasta[:10] 
                pasta_destino_consolidada = os.path.join(pasta_destino_servico, data_pasta_pasoe, pasta.replace('/', ''))
                if not os.path.exists(pasta_destino_consolidada): os.makedirs(pasta_destino_consolidada)
                
                _, arquivos_da_pasta = obter_conteudo_pagina(urljoin(url_servico, pasta))
                
                # BARRA DE PROGRESSO SECUNDÁRIA (Arquivos da Pasta Pasoe)
                if arquivos_da_pasta:
                    pbar_pasta = tqdm(arquivos_da_pasta, desc=f"   📁 {pasta}", position=1, leave=False, colour='blue')
                    for arq in pbar_pasta:
                        caminho_local = os.path.join(pasta_destino_consolidada, arq)
                        if not os.path.exists(caminho_local): 
                            pbar_pasta.set_postfix_str(f"Baixando: {arq}")
                            with requests.get(urljoin(url_servico, pasta + arq), stream=True, verify=False) as r:
                                r.raise_for_status()
                                with open(caminho_local, 'wb') as f:
                                    for chunk in r.iter_content(8192): f.write(chunk)
                            qtd_historicos += 1
            
            # 2. TRATA OS ARQUIVOS SOLTOS (Ativos e Históricos)
            if arquivos_soltos:
                # BARRA DE PROGRESSO SECUNDÁRIA (Arquivos Raiz)
                pbar_raiz = tqdm(arquivos_soltos, desc=f"   📄 Raiz ({nome_servico})", position=1, leave=False, colour='cyan')
                for arquivo in pbar_raiz:
                    status = classificar_arquivo(arquivo)
                    url_arquivo = urljoin(url_servico, arquivo)
                    
                    if status == 'ATIVO':
                        nome_base, extensao = os.path.splitext(arquivo)
                        nome_final = f"{nome_base}_ATIVO{extensao}"
                        caminho_local = os.path.join(pasta_destino_servico, nome_final)
                        ativos_da_rodada.append(nome_final)
                        
                        pbar_raiz.set_postfix_str(f"Atualizando: {nome_final}")
                        with requests.get(url_arquivo, stream=True, verify=False) as r:
                            r.raise_for_status()
                            with open(caminho_local, 'wb') as f:
                                for chunk in r.iter_content(8192): f.write(chunk)
                        qtd_snapshots += 1
                            
                    elif status == 'HISTORICO':
                        pasta_data = extrair_data(arquivo)
                        pasta_destino_final = os.path.join(pasta_destino_servico, pasta_data)
                        
                        if not os.path.exists(pasta_destino_final): os.makedirs(pasta_destino_final)
                            
                        caminho_local = os.path.join(pasta_destino_final, arquivo)
                        if not os.path.exists(caminho_local):
                            pbar_raiz.set_postfix_str(f"Baixando Histórico: {arquivo}")
                            with requests.get(url_arquivo, stream=True, verify=False) as r:
                                r.raise_for_status()
                                with open(caminho_local, 'wb') as f:
                                    for chunk in r.iter_content(8192): f.write(chunk)
                            qtd_historicos += 1

            # --- CHECAGEM PÓS-DOWNLOAD (Rotacionou no meio?) ---
            subdiretorios_fim, arquivos_soltos_fim = obter_conteudo_pagina(url_servico)
            pastas_horario_fim = [d for d in subdiretorios_fim if re.match(r'\d{4}-\d{2}-\d{2}_\d{2}_\d{2}/', d)]
            arquivos_hist_fim = [a for a in arquivos_soltos_fim if classificar_arquivo(a) == 'HISTORICO']
            
            if len(pastas_horario_fim) > len(pastas_horario_inicio) or len(arquivos_hist_fim) > len(arquivos_hist_inicio):
                tqdm.write("      ⚠️ Rotação detectada no servidor durante o download! Refazendo serviço...")
                continue
            else:
                break 

        # 3. FAXINA DE SNAPSHOTS ÓRFÃOS
        for raiz, dirs, arquivos_locais in os.walk(pasta_destino_servico):
            for arquivo_local in arquivos_locais:
                if "_ATIVO" in arquivo_local and arquivo_local not in ativos_da_rodada:
                    try:
                        os.remove(os.path.join(raiz, arquivo_local))
                        tqdm.write(f"      🧹 Limpeza: Removido snapshot antigo -> {arquivo_local}")
                        qtd_limpos += 1
                    except Exception: pass

    tempo_fim = datetime.now()
    duracao = tempo_fim - tempo_inicio
    relatorio = f"""
==================================================
📊 RELATÓRIO DE COLETA DE LOGS
==================================================
Início: {hora_inicio_str} | Fim: {tempo_fim.strftime("%d/%m/%Y %H:%M:%S")}
Tempo total: {duracao}

Arquivos Históricos baixados novos:  {qtd_historicos}
Snapshots (Ativos) atualizados:      {qtd_snapshots}
Snapshots antigos removidos:         {qtd_limpos}
==================================================
"""
    print(relatorio)
    try:
        with open(os.path.join(DIRETORIO_BASE_LOCAL, "relatorio_coleta.txt"), "a", encoding="utf-8") as f:
            f.write(relatorio + "\n")
    except Exception: pass

if __name__ == "__main__":
    main()