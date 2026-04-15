"""
=============================================================================================
Projeto: Monitoramento de Logs TOTVS Datasul
Módulo:  Motor de Coleta (Backend - Rede)
Arquivo: coleta_logs.py

Descrição: 
Script focado EXCLUSIVAMENTE em web scraping e download. Acessa múltiplos servidores
(Produção, Homologação, Protótipo), baixa históricos novos e atualiza os logs ativos.
A compactação foi movida para outro robô. Zero caracteres especiais no terminal.

Autor: Marcio Jose Gomes Bastos Filho
Data de Criação: 25/03/2026
Última Atualização: 15/04/2026
Versão: 4.1
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

# Forca a saida de texto a usar UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Configuracoes Principais e Mapeamento de Rede
UNIDADE_REDE = "L:"
CAMINHO_UNC = r"\\192.168.0.247\Logs_Datasul"

# Dicionario de Ambientes (Nome do Ambiente : URL Raiz)
AMBIENTES = {
    "Producao": "https://unimedencosta183931.datasul.cloudtotvs.com.br:8777/logs/",
    "Homologacao": "https://unimedencosta184349.datasul.cloudtotvs.com.br:8777/logs/",
    "Prototipo": "https://unimedencosta184282.datasul.cloudtotvs.com.br:8777/logs/"
}

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
        tqdm.write(f"[ERRO] Falha ao acessar {url}: {e}")
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
    if nome_arquivo.endswith('.gz') or nome_arquivo.endswith('.zip'): return 'HISTORICO'
    if str_hoje_hifen in nome_arquivo or str_hoje_junto in nome_arquivo: return 'ATIVO'
    ativos_conhecidos = ['server.log', 'boot.log', 'catalina.out', 'sib.log', 'monitortissnet.log']
    if nome_arquivo in ativos_conhecidos: return 'ATIVO'
    if re.search(r'20\d{2}[-_]?\d{2}[-_]?\d{2}', nome_arquivo): return 'HISTORICO'
    return 'ATIVO'

def processar_ambiente(nome_ambiente, url_ambiente):
    """Processa a coleta de logs para um unico ambiente"""
    pasta_raiz_ambiente = rf"{UNIDADE_REDE}\{nome_ambiente}"
    os.makedirs(pasta_raiz_ambiente, exist_ok=True)
    
    qtd_historicos, qtd_snapshots, qtd_limpos = 0, 0, 0
    
    print(f"\n--- Iniciando coleta no ambiente: {nome_ambiente} ---")
    servicos, _ = obter_conteudo_pagina(url_ambiente)
    
    if not servicos:
        print(f"[ERRO] Nenhum servico encontrado no ambiente {nome_ambiente}. Verifique a URL ou a conexao.")
        return 0, 0, 0

    pbar_geral = tqdm(servicos, desc=f"Progresso {nome_ambiente}", position=0, leave=True, colour='green')
    
    for servico in pbar_geral:
        nome_servico = servico.replace('/', '')
        pbar_geral.set_postfix_str(f"Processando: {nome_servico}")
        url_servico = urljoin(url_ambiente, servico)
        pasta_destino_servico = os.path.join(pasta_raiz_ambiente, nome_servico)
        os.makedirs(pasta_destino_servico, exist_ok=True)
            
        while True:
            subdiretorios, arquivos_soltos = obter_conteudo_pagina(url_servico)
            pastas_horario_inicio = [d for d in subdiretorios if re.match(r'\d{4}-\d{2}-\d{2}_\d{2}_\d{2}/', d)]
            arquivos_hist_inicio = [a for a in arquivos_soltos if classificar_arquivo(a) == 'HISTORICO']
            ativos_da_rodada = []
            
            for pasta in pastas_horario_inicio:
                data_pasta_pasoe = pasta[:10] 
                zip_do_dia = os.path.join(pasta_destino_servico, f"{data_pasta_pasoe}.zip")
                if os.path.exists(zip_do_dia): continue
                
                pasta_destino_consolidada = os.path.join(pasta_destino_servico, data_pasta_pasoe, pasta.replace('/', ''))
                os.makedirs(pasta_destino_consolidada, exist_ok=True)
                _, arquivos_da_pasta = obter_conteudo_pagina(urljoin(url_servico, pasta))
                
                if arquivos_da_pasta:
                    pbar_pasta = tqdm(arquivos_da_pasta, desc=f"    {pasta}", position=1, leave=False, colour='blue')
                    for arq in pbar_pasta:
                        caminho_local = os.path.join(pasta_destino_consolidada, arq)
                        if not os.path.exists(caminho_local) and not os.path.exists(caminho_local + '.gz') and not os.path.exists(caminho_local + '.zip'): 
                            pbar_pasta.set_postfix_str(f"Baixando: {arq}")
                            try:
                                with requests.get(urljoin(url_servico, pasta + arq), stream=True, verify=False, timeout=60) as r:
                                    r.raise_for_status()
                                    with open(caminho_local, 'wb') as f:
                                        for chunk in r.iter_content(8192): f.write(chunk)
                                qtd_historicos += 1
                            except Exception as e:
                                tqdm.write(f"      [ERRO] Falha ao baixar {arq}: {e}")
            
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
                        except Exception: pass
                    elif status == 'HISTORICO':
                        pasta_data = extrair_data(arquivo)
                        if os.path.exists(os.path.join(pasta_destino_servico, f"{pasta_data}.zip")): continue
                        pasta_destino_final = os.path.join(pasta_destino_servico, pasta_data)
                        os.makedirs(pasta_destino_final, exist_ok=True)
                        caminho_local = os.path.join(pasta_destino_final, arquivo)
                        if not os.path.exists(caminho_local) and not os.path.exists(caminho_local + '.gz') and not os.path.exists(caminho_local + '.zip'):
                            pbar_raiz.set_postfix_str(f"Baixando Historico: {arquivo}")
                            try:
                                with requests.get(url_arquivo, stream=True, verify=False, timeout=60) as r:
                                    r.raise_for_status()
                                    with open(caminho_local, 'wb') as f:
                                        for chunk in r.iter_content(8192): f.write(chunk)
                                qtd_historicos += 1
                            except Exception: pass

            subdiretorios_fim, arquivos_soltos_fim = obter_conteudo_pagina(url_servico)
            if len([d for d in subdiretorios_fim if re.match(r'\d{4}-\d{2}-\d{2}_\d{2}_\d{2}/', d)]) > len(pastas_horario_inicio):
                tqdm.write("      [ATENCAO] Rotacao detectada! Refazendo servico...")
                continue
            else: break 

        for item in os.listdir(pasta_destino_servico):
            caminho_completo = os.path.join(pasta_destino_servico, item)
            if os.path.isfile(caminho_completo) and "_ATIVO" in item and item not in ativos_da_rodada:
                try:
                    os.remove(caminho_completo)
                    tqdm.write(f"      [LIMPEZA] Removido ativo orfao -> {item}")
                    qtd_limpos += 1
                except Exception: pass
                
    return qtd_historicos, qtd_snapshots, qtd_limpos

def main():
    tempo_inicio = datetime.now()
    hora_inicio_str = tempo_inicio.strftime("%d/%m/%Y %H:%M:%S")
    
    if not os.path.exists(f"{UNIDADE_REDE}\\"):
        try:
            subprocess.run(["net", "use", UNIDADE_REDE, CAMINHO_UNC], check=True, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError: pass 
    
    print(f"\n[INICIO] Coleta de Rede Multi-Ambiente iniciada em: {hora_inicio_str}")
    
    total_historicos = 0
    total_snapshots = 0
    total_limpos = 0
    
    # Processa todos os ambientes sequencialmente
    for nome_ambiente, url_ambiente in AMBIENTES.items():
        hist, snap, limp = processar_ambiente(nome_ambiente, url_ambiente)
        total_historicos += hist
        total_snapshots += snap
        total_limpos += limp

    tempo_fim = datetime.now()
    relatorio = f"""
==================================================
RELATORIO DE COLETA (DOWNLOADER MULTI-AMBIENTE)
==================================================
Inicio: {hora_inicio_str} | Fim: {tempo_fim.strftime("%d/%m/%Y %H:%M:%S")}
Tempo total: {tempo_fim - tempo_inicio}

Arquivos Historicos baixados:        {total_historicos}
Snapshots (Ativos) atualizados:      {total_snapshots}
Snapshots orfaos removidos:          {total_limpos}
==================================================
"""
    print(relatorio)
    
    # Salva um unico relatorio consolidado na raiz do L:
    try:
        arquivo_log_relatorio = os.path.join(f"{UNIDADE_REDE}\\", "relatorio_coleta_geral.txt")
        conteudo_antigo = ""
        if os.path.exists(arquivo_log_relatorio):
            with open(arquivo_log_relatorio, "r", encoding="utf-8") as f: conteudo_antigo = f.read()
        with open(arquivo_log_relatorio, "w", encoding="utf-8") as f: f.write(relatorio + "\n" + conteudo_antigo)
    except Exception: pass

if __name__ == "__main__":
    main()