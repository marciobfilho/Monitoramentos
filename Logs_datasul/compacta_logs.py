"""
=============================================================================================
Projeto: Monitoramento de Logs TOTVS Datasul
Módulo:  Motor de Compactação e Limpeza (Backend - Disco)
Arquivo: compacta_logs.py

Descrição: 
Script focado EXCLUSIVAMENTE em I/O de disco. Varre a estrutura de rede local, identifica 
pastas de log com idade superior à retenção configurada, as consolida em pacotes ZIP únicos
e as exclui para poupar clusters e Master File Table.
Contém proteção contra arquivos "fantasmas" de cache de rede (WinError 2).

Autor: Marcio Jose Gomes Bastos Filho
Data de Criação: 15/04/2026
Versão: 1.1
=============================================================================================
"""

import os
import re
from datetime import datetime
import zipfile
import shutil
from tqdm import tqdm
import subprocess
import sys 

# Força a saída de texto a usar UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Variáveis de Rede e Retenção
UNIDADE_REDE = "L:"
CAMINHO_UNC = r"\\192.168.0.247\Logs_Datasul"
DIRETORIO_BASE_LOCAL = rf"{UNIDADE_REDE}\Producao"
DIAS_RETENCAO_COMPACTACAO = 10

def main():
    tempo_inicio = datetime.now()
    hora_inicio_str = tempo_inicio.strftime("%d/%m/%Y %H:%M:%S")
    
    # Auto-mapeamento de rede (Garante que vai rodar no Agendador de Tarefas)
    if not os.path.exists(f"{UNIDADE_REDE}\\"):
        try:
            subprocess.run(["net", "use", UNIDADE_REDE, CAMINHO_UNC], check=True, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            pass 
            
    if not os.path.exists(DIRETORIO_BASE_LOCAL):
        print("[ERRO] Diretório base não encontrado. Verifique o mapeamento da rede.")
        return

    print(f"\n[INICIO] Rotina de Compactação de Disco iniciada em: {hora_inicio_str} ...")
    
    qtd_pastas_compactadas = 0
    bytes_poupados = 0
    
    # Mapeia todos os serviços (ex: jboss_autorizador, logs_pasoe)
    servicos = [d for d in os.listdir(DIRETORIO_BASE_LOCAL) if os.path.isdir(os.path.join(DIRETORIO_BASE_LOCAL, d))]
    pbar_geral = tqdm(servicos, desc="Varredura de Serviços", position=0, leave=True, colour='yellow')

    for servico in pbar_geral:
        pbar_geral.set_postfix_str(f"Analisando: {servico}")
        pasta_destino_servico = os.path.join(DIRETORIO_BASE_LOCAL, servico)
        
        # Lista tudo dentro do serviço
        itens_servico = os.listdir(pasta_destino_servico)
        
        for item in itens_servico:
            caminho_completo = os.path.join(pasta_destino_servico, item)
            
            # Checa se é uma pasta de DATA (ex: 2026-03-24)
            if os.path.isdir(caminho_completo) and re.match(r'20\d{2}-\d{2}-\d{2}', item):
                try:
                    data_pasta = datetime.strptime(item, "%Y-%m-%d")
                    idade_dias = (tempo_inicio - data_pasta).days
                    
                    if idade_dias > DIAS_RETENCAO_COMPACTACAO:
                        caminho_zip = caminho_completo + '.zip'
                        
                        # Calcula tamanho original
                        tamanho_orig = sum(os.path.getsize(os.path.join(dirpath, filename)) 
                                           for dirpath, _, filenames in os.walk(caminho_completo) 
                                           for filename in filenames)
                        
                        if tamanho_orig > 0:
                            # Compressão ZIP máxima
                            with zipfile.ZipFile(caminho_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                                for root_dir, _, files in os.walk(caminho_completo):
                                    for file in files:
                                        file_path = os.path.join(root_dir, file)
                                        
                                        #  PROTEÇÃO CONTRA WINERROR 2 (Arquivos fantasmas na rede) 🛡️
                                        if os.path.exists(file_path):
                                            # Mantém estrutura interna limpa
                                            arcname = os.path.relpath(file_path, pasta_destino_servico)
                                            zipf.write(file_path, arcname=arcname)
                                        
                            tamanho_novo = os.path.getsize(caminho_zip)
                            shutil.rmtree(caminho_completo) # Limpa a pasta
                            
                            qtd_pastas_compactadas += 1
                            bytes_poupados += (tamanho_orig - tamanho_novo)
                            tqdm.write(f"      [COMPACTACAO] Pasta {item} unificada em ZIP (Idade: {idade_dias} dias).")
                        else:
                            shutil.rmtree(caminho_completo) # Limpa se estiver vazia
                except Exception as e:
                    tqdm.write(f"      [ERRO] Falha ao processar pasta {item}: {e}")

    tempo_fim = datetime.now()
    duracao = tempo_fim - tempo_inicio
    mb_poupados = bytes_poupados / (1024 * 1024)
    
    relatorio = f"""
==================================================
RELATÓRIO DE DISCO (COMPRESSOR)
==================================================
Início: {hora_inicio_str} | Fim: {tempo_fim.strftime("%d/%m/%Y %H:%M:%S")}
Tempo total: {duracao}

Pastas diárias unificadas (>10d):    {qtd_pastas_compactadas}
Economia de Disco gerada:            {mb_poupados:.2f} MB
==================================================
"""
    print(relatorio)
    
    try:
        arquivo_log_relatorio = os.path.join(DIRETORIO_BASE_LOCAL, "relatorio_compactacao.txt")
        conteudo_antigo = ""
        if os.path.exists(arquivo_log_relatorio):
            with open(arquivo_log_relatorio, "r", encoding="utf-8") as f: conteudo_antigo = f.read()
        with open(arquivo_log_relatorio, "w", encoding="utf-8") as f: f.write(relatorio + "\n" + conteudo_antigo)
    except Exception: pass

if __name__ == "__main__":
    main()