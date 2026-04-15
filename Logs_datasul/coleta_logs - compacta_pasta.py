"""
=============================================================================================
Projeto: Monitoramento de Logs TOTVS Datasul
Módulo:  Motor de Coleta e Retenção (Backend)
Arquivo: coleta_logs.py

Descrição: 
Script de automação (Web Scraping) que acessa o servidor de logs do Datasul, faz o download 
dos históricos organizando-os em pastas por data (YYYY-MM-DD), atualiza os logs ativos na 
raiz do serviço e expurga snapshots órfãos.
Inclui auto-mapeamento de rede, correção de Encoding UTF-8, gravação reversa de relatórios,
compactação diária unificada (1 ZIP por dia) e validação de arquivos legados já compactados.

Autor: Marcio Jose Gomes Bastos Filho
Data de Criação: 25/03/2026
Última Atualização: 15/04/2026
Versão: 3.2
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
import zipfile
import shutil

# Força a saída de texto a usar UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Configurações Principais
MAIN_URL = "https://unimedencosta183931.datasul.cloudtotvs.com.br:8777/logs/"

# Variáveis de Rede e Retenção
UNIDADE_REDE = "L:"
CAMINHO_UNC = r"\\192.168.0.247\Logs_Datasul"
DIRETORIO_BASE_LOCAL = rf"{UNIDADE_REDE}\Producao"
DIAS_RETENCAO_COMPACTACAO = 10

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
    qtd_pastas_compactadas = 0
    bytes_poupados = 0
    
    os.makedirs(DIRETORIO_BASE_LOCAL, exist_ok=True)

    print(f"\n[INICIO] Coleta iniciada em: {hora_inicio_str} ...")
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
            
            # 1. TRATA AS PASTAS CONSOLIDADAS (Pasoe)
            for pasta in pastas_horario_inicio:
                data_pasta_pasoe = pasta[:10] 
                zip_do_dia = os.path.join(pasta_destino_servico, f"{data_pasta_pasoe}.zip")
                
                # Pula a pasta inteira se o dia já foi consolidado e zipado
                if os.path.exists(zip_do_dia):
                    continue
                
                pasta_destino_consolidada = os.path.join(pasta_destino_servico, data_pasta_pasoe, pasta.replace('/', ''))
                os.makedirs(pasta_destino_consolidada, exist_ok=True)
                
                _, arquivos_da_pasta = obter_conteudo_pagina(urljoin(url_servico, pasta))
                
                if arquivos_da_pasta:
                    pbar_pasta = tqdm(arquivos_da_pasta, desc=f"    {pasta}", position=1, leave=False, colour='blue')
                    for arq in pbar_pasta:
                        caminho_local = os.path.join(pasta_destino_consolidada, arq)
                        caminho_local_gz = caminho_local + '.gz'
                        caminho_local_zip = caminho_local + '.zip'
                        
                        # Verifica todas as formas possíveis de o arquivo já existir
                        if not os.path.exists(caminho_local) and not os.path.exists(caminho_local_gz) and not os.path.exists(caminho_local_zip): 
                            pbar_pasta.set_postfix_str(f"Baixando: {arq}")
                            try:
                                with requests.get(urljoin(url_servico, pasta + arq), stream=True, verify=False, timeout=60) as r:
                                    r.raise_for_status()
                                    with open(caminho_local, 'wb') as f:
                                        for chunk in r.iter_content(8192): f.write(chunk)
                                qtd_historicos += 1
                            except Exception as e:
                                tqdm.write(f"      [ERRO] Falha ao baixar {arq}: {e}")
            
            # 2. TRATA OS ARQUIVOS SOLTOS (Ativos e Históricos)
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
                            tqdm.write(f"      [ERRO] Falha ao baixar {arquivo}: {e}")
                            
                    elif status == 'HISTORICO':
                        pasta_data = extrair_data(arquivo)
                        zip_do_dia = os.path.join(pasta_destino_servico, f"{pasta_data}.zip")
                        
                        # Pula a coleta se o dia já foi consolidado em ZIP
                        if os.path.exists(zip_do_dia):
                            continue
                            
                        pasta_destino_final = os.path.join(pasta_destino_servico, pasta_data)
                        os.makedirs(pasta_destino_final, exist_ok=True)
                            
                        caminho_local = os.path.join(pasta_destino_final, arquivo)
                        caminho_local_gz = caminho_local + '.gz'
                        caminho_local_zip = caminho_local + '.zip'
                        
                        # Verifica todas as formas possíveis de o arquivo já existir
                        if not os.path.exists(caminho_local) and not os.path.exists(caminho_local_gz) and not os.path.exists(caminho_local_zip):
                            pbar_raiz.set_postfix_str(f"Baixando Histórico: {arquivo}")
                            try:
                                with requests.get(url_arquivo, stream=True, verify=False, timeout=60) as r:
                                    r.raise_for_status()
                                    with open(caminho_local, 'wb') as f:
                                        for chunk in r.iter_content(8192): f.write(chunk)
                                qtd_historicos += 1
                            except Exception as e:
                                tqdm.write(f"      [ERRO] Falha ao baixar {arquivo}: {e}")

            subdiretorios_fim, arquivos_soltos_fim = obter_conteudo_pagina(url_servico)
            pastas_horario_fim = [d for d in subdiretorios_fim if re.match(r'\d{4}-\d{2}-\d{2}_\d{2}_\d{2}/', d)]
            arquivos_hist_fim = [a for a in arquivos_soltos_fim if classificar_arquivo(a) == 'HISTORICO']
            
            if len(pastas_horario_fim) > len(pastas_horario_inicio) or len(arquivos_hist_fim) > len(arquivos_hist_inicio):
                tqdm.write("      [ATENCAO] Rotação detectada no servidor durante o download! Refazendo serviço...")
                continue
            else:
                break 

        # 3. FAXINA DE ATIVOS ÓRFÃOS E COMPACTAÇÃO DIÁRIA DE PASTAS
        for item in os.listdir(pasta_destino_servico):
            caminho_completo = os.path.join(pasta_destino_servico, item)
            
            # Limpeza de Ativos Órfãos
            if os.path.isfile(caminho_completo) and "_ATIVO" in item:
                if item not in ativos_da_rodada:
                    try:
                        os.remove(caminho_completo)
                        tqdm.write(f"      [LIMPEZA] Removido snapshot antigo -> {item}")
                        qtd_limpos += 1
                    except Exception: pass
                continue
            
            # Compactação de Pastas Diárias (> 10 dias)
            if os.path.isdir(caminho_completo) and re.match(r'20\d{2}-\d{2}-\d{2}', item):
                try:
                    data_pasta = datetime.strptime(item, "%Y-%m-%d")
                    idade_dias = (tempo_inicio - data_pasta).days
                    
                    if idade_dias > DIAS_RETENCAO_COMPACTACAO:
                        caminho_zip = caminho_completo + '.zip'
                        
                        tamanho_orig = sum(os.path.getsize(os.path.join(dirpath, filename)) 
                                           for dirpath, _, filenames in os.walk(caminho_completo) 
                                           for filename in filenames)
                        
                        if tamanho_orig > 0:
                            with zipfile.ZipFile(caminho_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                                for root_dir, _, files in os.walk(caminho_completo):
                                    for file in files:
                                        file_path = os.path.join(root_dir, file)
                                        arcname = os.path.relpath(file_path, pasta_destino_servico)
                                        zipf.write(file_path, arcname=arcname)
                                        
                            tamanho_novo = os.path.getsize(caminho_zip)
                            shutil.rmtree(caminho_completo) 
                            
                            qtd_pastas_compactadas += 1
                            bytes_poupados += (tamanho_orig - tamanho_novo)
                            tqdm.write(f"      [COMPACTACAO] Pasta do dia {item} unificada em ZIP (Idade: {idade_dias} dias).")
                        else:
                            shutil.rmtree(caminho_completo) 
                except Exception as e:
                    pass

    tempo_fim = datetime.now()
    duracao = tempo_fim - tempo_inicio
    mb_poupados = bytes_poupados / (1024 * 1024)
    
    relatorio = f"""
==================================================
RELATÓRIO DE COLETA DE LOGS
==================================================
Início: {hora_inicio_str} | Fim: {tempo_fim.strftime("%d/%m/%Y %H:%M:%S")}
Tempo total: {duracao}

Arquivos Históricos baixados:        {qtd_historicos}
Snapshots (Ativos) atualizados:      {qtd_snapshots}
Snapshots antigos removidos:         {qtd_limpos}
Pastas diárias unificadas (>10d):    {qtd_pastas_compactadas}
Economia de Disco gerada:            {mb_poupados:.2f} MB
==================================================
"""
    print(relatorio)
    
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