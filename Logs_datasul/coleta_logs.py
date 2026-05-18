import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import urllib3
from tqdm import tqdm
import sys 

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Configuração UNC direta (Bypass de unidade mapeada Z:)
CAMINHO_UNC = r"\\compartilhamento\Logs_Datasul"

AMBIENTES = {
    "Producao": "https://unimedencosta183931.datasul.cloudtotvs.com.br:8777/logs/",
    "Homologacao": "https://unimedencosta184349.datasul.cloudtotvs.com.br:8777/logs/",
    "Prototipo": "https://unimedencosta184282.datasul.cloudtotvs.com.br:8777/logs/"
}

LIMITE_DOWNLOAD_DIAS = 21
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
    return 'ATIVO' if not re.search(r'20\d{2}[-_]?\d{2}[-_]?\d{2}', nome_arquivo) else 'HISTORICO'

def baixar_recursivo(url_origem, pasta_destino, tempo_inicio, pbar):
    qtd = 0
    subdirs, arquivos = obter_conteudo_pagina(url_origem)
    for arq in arquivos:
        data_arq = extrair_data(arq)
        try:
            if (tempo_inicio - datetime.strptime(data_arq, "%Y-%m-%d")).days > LIMITE_DOWNLOAD_DIAS: continue 
        except: pass
        caminho_local = os.path.join(pasta_destino, arq)
        if not os.path.exists(caminho_local) and not os.path.exists(caminho_local + '.gz') and not os.path.exists(caminho_local + '.zip'):
            pbar.set_postfix_str(f"Baixando: {arq[:20]}...")
            try:
                with requests.get(urljoin(url_origem, arq), stream=True, verify=False, timeout=60) as r:
                    r.raise_for_status()
                    with open(caminho_local, 'wb') as f:
                        for chunk in r.iter_content(8192): f.write(chunk)
                qtd += 1
            except: pass
    for d in subdirs:
        data_dir = extrair_data(d)
        try:
            if (tempo_inicio - datetime.strptime(data_dir, "%Y-%m-%d")).days > LIMITE_DOWNLOAD_DIAS: continue 
        except: pass
        nova_url, nova_pasta = urljoin(url_origem, d), os.path.join(pasta_destino, d.replace('/', ''))
        os.makedirs(nova_pasta, exist_ok=True)
        qtd += baixar_recursivo(nova_url, nova_pasta, tempo_inicio, pbar)
    return qtd

def processar_ambiente(nome_ambiente, url_ambiente, tempo_inicio):
    pasta_raiz = os.path.join(CAMINHO_UNC, nome_ambiente)
    os.makedirs(pasta_raiz, exist_ok=True)
    qtd_h, qtd_s, qtd_l = 0, 0, 0
    print(f"\n--- Coleta: {nome_ambiente} ---")
    servicos, _ = obter_conteudo_pagina(url_ambiente)
    if not servicos: return 0, 0, 0
    pbar_geral = tqdm(servicos, desc=f"Progresso {nome_ambiente}", colour='green')
    for servico in pbar_geral:
        nome_servico = servico.replace('/', '')
        url_servico = urljoin(url_ambiente, servico)
        pasta_dest = os.path.join(pasta_raiz, nome_servico)
        os.makedirs(pasta_dest, exist_ok=True)
        subdiretorios, arquivos_soltos = obter_conteudo_pagina(url_servico)
        pastas_rotacionadas = [d for d in subdiretorios if re.match(r'\d{4}-\d{2}-\d{2}_\d{2}_\d{2}/', d)]
        ativos_da_rodada = []
        for pasta in pastas_rotacionadas:
            data_pasta = pasta[:10]
            if os.path.exists(os.path.join(pasta_dest, f"{data_pasta}.zip")): continue
            pasta_consolidada = os.path.join(pasta_dest, data_pasta, pasta.replace('/', ''))
            os.makedirs(pasta_consolidada, exist_ok=True)
            qtd_h += baixar_recursivo(urljoin(url_servico, pasta), pasta_consolidada, tempo_inicio, pbar_geral)
        if arquivos_soltos:
            for arquivo in arquivos_soltos:
                status = classificar_arquivo(arquivo)
                if status == 'ATIVO':
                    nome_f = f"{os.path.splitext(arquivo)[0]}_ATIVO{os.path.splitext(arquivo)[1]}"
                    caminho_l = os.path.join(pasta_dest, nome_f)
                    ativos_da_rodada.append(nome_f)
                    try:
                        with requests.get(urljoin(url_servico, arquivo), stream=True, verify=False) as r:
                            with open(caminho_l, 'wb') as f:
                                for chunk in r.iter_content(8192): f.write(chunk)
                        qtd_s += 1
                    except: pass
                elif status == 'HISTORICO':
                    dt = extrair_data(arquivo)
                    if not os.path.exists(os.path.join(pasta_dest, f"{dt}.zip")):
                        p_final = os.path.join(pasta_dest, dt)
                        os.makedirs(p_final, exist_ok=True)
                        c_l = os.path.join(p_final, arquivo)
                        if not os.path.exists(c_l):
                            try:
                                with requests.get(urljoin(url_servico, arquivo), stream=True, verify=False) as r:
                                    with open(c_l, 'wb') as f:
                                        for chunk in r.iter_content(8192): f.write(chunk)
                                qtd_h += 1
                            except: pass
    return qtd_h, qtd_s, qtd_l

def main():
    inicio = datetime.now()
    t_h, t_s, t_l = 0, 0, 0
    for nome, url in AMBIENTES.items():
        h, s, l = processar_ambiente(nome, url, inicio)
        t_h += h; t_s += s; t_l += l
    fim = datetime.now()
    relatorio = f"\n==================================================\nRELATORIO DE COLETA GERAL\n==================================================\nInicio: {inicio.strftime('%d/%m/%Y %H:%M:%S')} | Fim: {fim.strftime('%d/%m/%Y %H:%M:%S')}\nHistoricos: {t_h} | Ativos: {t_s} | Limpos: {t_l}\n==================================================\n"
    print(relatorio)
    try:
        path_rep = os.path.join(CAMINHO_UNC, "relatorio_coleta_geral.txt")
        old = ""
        if os.path.exists(path_rep):
            with open(path_rep, "r", encoding="utf-8") as f: old = f.read()
        with open(path_rep, "w", encoding="utf-8") as f: f.write(relatorio + "\n" + old)
    except: pass

if __name__ == "__main__": main()