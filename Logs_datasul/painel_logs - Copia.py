"""
=============================================================================================
Projeto: Monitoramento de Logs TOTVS Datasul
Módulo:  Painel Web de Métricas (Frontend)
Arquivo: painel_logs.py

Descrição: 
Dashboard interativo construído com Streamlit para monitorar o tamanho, a retenção 
e a saúde dos logs (JBoss, Tomcat, Pasoe) do ambiente Datasul armazenados em rede.
Possui atualização automática em tempo real.

Autor: Marcio Jose Gomes Bastos Filho
Data de Criação: 25/03/2026
Última Atualização: 26/03/2026
Versão: 1.0
=============================================================================================
"""

import streamlit as st
import os
import shutil
import datetime
import re
from streamlit_autorefresh import st_autorefresh

DIRETORIO_LOGS = r"\\192.168.0.247\Logs_Datasul\Producao"

st.set_page_config(page_title="Monitor de Logs Datasul", layout="wide", page_icon="📊")
st_autorefresh(interval=60000, limit=None, key="monitor_logs_refresh")

def obter_metricas():
    tamanho_total_bytes = 0
    tempo_mais_antigo = datetime.datetime.now()
    quantidade_arquivos = 0
    tamanho_por_servico = {}

    if os.path.exists(DIRETORIO_LOGS):
        servicos = [d for d in os.listdir(DIRETORIO_LOGS) if os.path.isdir(os.path.join(DIRETORIO_LOGS, d))]
        
        for servico in servicos:
            caminho_servico = os.path.join(DIRETORIO_LOGS, servico)
            
            for raiz, diretorios, arquivos in os.walk(caminho_servico):
                nome_pasta = os.path.basename(raiz)
                if re.match(r'20\d{2}-\d{2}-\d{2}', nome_pasta):
                    data_pasta = datetime.datetime.strptime(nome_pasta[:10], "%Y-%m-%d")
                    if data_pasta < tempo_mais_antigo:
                        tempo_mais_antigo = data_pasta

                for arquivo in arquivos:
                    caminho_completo = os.path.join(raiz, arquivo)
                    if not os.path.islink(caminho_completo):
                        tamanho = os.path.getsize(caminho_completo)
                        tamanho_total_bytes += tamanho
                        quantidade_arquivos += 1
                        
                        # --- O SEGREDO ESTÁ NO .lower() AQUI ---
                        if "jboss" not in servico.lower():
                            if servico.lower() == "logs_pasoe":
                                nome_barra = arquivo.split(".agent.")[0] if ".agent." in arquivo else "pasoe_outros"
                            else:
                                nome_barra = servico
                                
                            tamanho_por_servico[nome_barra] = tamanho_por_servico.get(nome_barra, 0) + tamanho

        for chave in tamanho_por_servico:
            tamanho_por_servico[chave] = tamanho_por_servico[chave] / (1024**3)

    try:
        disco = shutil.disk_usage(DIRETORIO_LOGS)
    except Exception:
        disco = None 
        
    return tamanho_total_bytes, disco, tempo_mais_antigo, quantidade_arquivos, tamanho_por_servico

st.title("📊 Monitor de Retenção de Logs - TOTVS Datasul")
st.markdown("---")

with st.spinner('Analisando o servidor de rede...'):
    tamanho_logs, disco, tempo_mais_antigo, qtd_arquivos, tamanho_servicos = obter_metricas()

gb_logs = tamanho_logs / (1024**3)
dias_retencao = (datetime.datetime.now() - tempo_mais_antigo).days

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Total Armazenado (Incluindo JBoss)", value=f"{gb_logs:.2f} GB", delta=f"{qtd_arquivos} arquivos")

with col2:
    st.metric(label="Retenção Alcançada", value=f"{dias_retencao} Dias", delta=f"Desde {tempo_mais_antigo.strftime('%d/%m/%Y')}", delta_color="off")

with col3:
    if disco:
        gb_livre = disco.free / (1024**3)
        st.metric(label="Espaço Livre no Servidor", value=f"{gb_livre:.2f} GB")
    else:
        st.metric(label="Espaço Livre no Servidor", value="Indisponível", help="O Windows bloqueia leitura de capacidade via UNC Path.")

st.markdown("---")
col_grafico, col_saude = st.columns([2, 1])

with col_grafico:
    st.subheader("Consumo por Agente/Serviço (GB)")
    if tamanho_servicos:
        st.bar_chart(tamanho_servicos)
    else:
        st.info("Nenhum serviço mapeado para o gráfico.")

with col_saude:
    st.subheader("Saúde do Disco")
    if disco:
        percentual = (disco.used / disco.total) * 100
        st.progress(int(percentual), text=f"Uso Total do Disco: {percentual:.1f}%")
    else:
        st.warning("A capacidade do disco na rede não pode ser lida.")

st.caption(f"Última atualização: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | Caminho: {DIRETORIO_LOGS}")