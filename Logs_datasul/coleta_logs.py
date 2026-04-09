"""
=============================================================================================
Projeto: Monitoramento de Logs TOTVS Datasul
Módulo:  Motor de Coleta e Retenção (Backend)
Arquivo: coleta_logs.py

Descrição: 
Script de automação (Web Scraping) que acessa o servidor de logs do Datasul, faz o download 
dos históricos organizando-os em pastas por data (YYYY-MM-DD), atualiza os logs ativos na 
raiz do serviço e expurga snapshots órfãos para poupar espaço em disco.
Inclui auto-mapeamento de rede interno para rodar em Sessão 0, correção de Encoding UTF-8
e gravação reversa de relatórios (mais recentes no topo). Versão limpa, sem emojis.

Autor: Marcio Jose Gomes Bastos Filho
Data de Criação: 25/03/2026
Última Atualização: 09/04/2026
Versão: 2.8
=============================================================================================
"""

import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import urllib3
from tqdm import tqdm
import subprocess
import sys 

# Força a saída de texto a usar UTF-8 (mantido por segurança para acentuações)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Configurações Principais
MAIN_URL = "https://unimedencosta183931.datasul.cloudtotvs.com.br:8777/logs/"

# Variáveis para o Auto-Mapeamento do Python
UNIDADE_REDE = "L:"
CAMINHO_UNC = r"\\192.168.0.247\Logs_Datasul"
DIRETORIO_BASE_LOCAL = rf"{UNIDADE_REDE}\Producao"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def obter_conteudo_pagina(url):
    try:
        response = requests.get(url, verify=False, timeout=60)
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
        tqdm.write(f"Falha ao acessar {url}: {e}")
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
    
    # Auto-mapeamento de rede
    if not os.path.exists(f"{UNIDADE_REDE}\\"):
        try:
            subprocess.run(["net", "use", UNIDADE_REDE, CAMINHO_UNC], check=True, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            pass 
    
    qtd_historicos = 0
    qtd_snapshots = 0
    qtd_limpos = 0
    
    os.makedirs(DIRETORIO_BASE_LOCAL, exist_ok=True)

    print(f"\n Coleta iniciada em: {hora_inicio_str} ...")
    servicos, _ = obter_conteudo_pagina(MAIN_URL)
    
    pbar_geral = tqdm(servicos, desc="Progresso Geral", position=0, leave=True, colour='green')
    
    for servico in pbar_geral:
        nome_servico = servico.replace('/', '')
        pbar_geral.set_postfix_str(f"Processando: {nome_servico}")
        
        url_servico = urljoin(MAIN_URL, servico)
        pasta_destino_servico = os.path.join(DIRETORIO_BASE_LOCAL, nome_servico)
        os.makedirs(pasta_destino_servico, exist_ok=True)
            
        while True:
            subdiretorios, arquivos_soltos = obter_conteudo_pagina(url_servico)
            
            pastas_horario_inicio = [d for d in subdiretorios if re.match(r'\d{4}-\d{2}-\d{2}_\d{2}_\d{2}/', d)]
            arquivos_hist_inicio = [a for a in arquivos_soltos if classificar_arquivo(a) == 'HISTORICO']
            ativos_da_rodada = []
            
            for pasta in pastas_horario_inicio:
                data_pasta_pasoe = pasta[:10] 
                pasta_destino_consolidada = os.path.join(pasta_destino_servico, data_pasta_pasoe, pasta.replace('/', ''))
                os.makedirs(pasta_destino_consolidada, exist_ok=True)
                
                _, arquivos_da_pasta = obter_conteudo_pagina(urljoin(url_servico, pasta))
                
                if arquivos_da_pasta:
                    pbar_pasta = tqdm(arquivos_da_pasta, desc=f"    {pasta}", position=1, leave=False, colour='blue')
                    for arq in pbar_pasta:
                        caminho_local = os.path.join(pasta_destino_consolidada, arq)
                        if not os.path.exists(caminho_local): 
                            pbar_pasta.set_postfix_str(f"Baixando: {arq}")
                            try:
                                with requests.get(urljoin(url_servico, pasta + arq), stream=True, verify=False, timeout=60) as r:
                                    r.raise_for_status()
                                    with open(caminho_local, 'wb') as f:
                                        for chunk in r.iter_content(8192): f.write(chunk)
                                qtd_historicos += 1
                            except Exception as e:
                                tqdm.write(f"      Falha ao baixar {arq}: {e}")
            
            if arquivos_soltos:
                pbar_raiz = tqdm(arquivos_soltos, desc=f"    Raiz ({nome_servico})", position=1, leave=False, colour='cyan')
                for arquivo in pbar_raiz:
                    status = classificar_arquivo(arquivo)
                    url_arquivo = urljoin(url_servico, arquivo)
                    
                    if status == 'ATIVO':
                        nome_base, extensao = os.path.splitext(arquivo)
                        nome_final = f"{nome_base}_ATIVO{extensao}"
                        caminho_local = os.path.join(pasta_destino_servico, nome_final)
                        ativos_da_rodada.append(nome_final)
                        
                        pbar_raiz.set_postfix_str(f"Atualizando: {nome_final}")
                        try:
                            with requests.get(url_arquivo, stream=True, verify=False, timeout=60) as r:
                                r.raise_for_status()
                                with open(caminho_local, 'wb') as f:
                                    for chunk in r.iter_content(8192): f.write(chunk)
                            qtd_snapshots += 1
                        except Exception as e:
                            tqdm.write(f"      Falha ao baixar {arquivo}: {e}")
                            
                    elif status == 'HISTORICO':
                        pasta_data = extrair_data(arquivo)
                        pasta_destino_final = os.path.join(pasta_destino_servico, pasta_data)
                        
                        os.makedirs(pasta_destino_final, exist_ok=True)
                            
                        caminho_local = os.path.join(pasta_destino_final, arquivo)
                        if not os.path.exists(caminho_local):
                            pbar_raiz.set_postfix_str(f"Baixando Histórico: {arquivo}")
                            try:
                                with requests.get(url_arquivo, stream=True, verify=False, timeout=60) as r:
                                    r.raise_for_status()
                                    with open(caminho_local, 'wb') as f:
                                        for chunk in r.iter_content(8192): f.write(chunk)
                                qtd_historicos += 1
                            except Exception as e:
                                tqdm.write(f"      Falha ao baixar {arquivo}: {e}")

            subdiretorios_fim, arquivos_soltos_fim = obter_conteudo_pagina(url_servico)
            pastas_horario_fim = [d for d in subdiretorios_fim if re.match(r'\d{4}-\d{2}-\d{2}_\d{2}_\d{2}/', d)]
            arquivos_hist_fim = [a for a in arquivos_soltos_fim if classificar_arquivo(a) == 'HISTORICO']
            
            if len(pastas_horario_fim) > len(pastas_horario_inicio) or len(arquivos_hist_fim) > len(arquivos_hist_inicio):
                tqdm.write("      Rotação detectada no servidor durante o download! Refazendo serviço...")
                continue
            else:
                break 

        for raiz, dirs, arquivos_locais in os.walk(pasta_destino_servico):
            for arquivo_local in arquivos_locais:
                if "_ATIVO" in arquivo_local and arquivo_local not in ativos_da_rodada:
                    try:
                        os.remove(os.path.join(raiz, arquivo_local))
                        tqdm.write(f"      Removido snapshot antigo -> {arquivo_local}")
                        qtd_limpos += 1
                    except Exception: pass

    tempo_fim = datetime.now()
    duracao = tempo_fim - tempo_inicio
    relatorio = f"""
==================================================
RELATÓRIO DE COLETA DE LOGS
==================================================
Início: {hora_inicio_str} | Fim: {tempo_fim.strftime("%d/%m/%Y %H:%M:%S")}
Tempo total: {duracao}

Arquivos Históricos baixados novos:  {qtd_historicos}
Snapshots (Ativos) atualizados:      {qtd_snapshots}
Snapshots antigos removidos:         {qtd_limpos}
==================================================
"""
    print(relatorio)
    
    # Lógica para escrever no TOPO do arquivo
    arquivo_log_relatorio = os.path.join(DIRETORIO_BASE_LOCAL, "relatorio_coleta.txt")
    conteudo_antigo = ""
    
    if os.path.exists(arquivo_log_relatorio):
        try:
            with open(arquivo_log_relatorio, "r", encoding="utf-8") as f:
                conteudo_antigo = f.read()
        except Exception: pass
        
    try:
        with open(arquivo_log_relatorio, "w", encoding="utf-8") as f:
            f.write(relatorio + "\n" + conteudo_antigo)
    except Exception: pass

if __name__ == "__main__":
    main()