"""
=============================================================================================
Projeto: Monitoramento de Logs TOTVS Datasul
Módulo:  Painel Web de Métricas (Frontend) - Visão Unificada
Arquivo: painel_logs.py

Descrição: 
Dashboard interativo para monitorar logs do ambiente Datasul.
Versão 5.0: Elimina o seletor de ambientes e exibe tudo em uma única página (Single Pane of Glass).
Adiciona gráfico global comparativo (Ambientes x Espaço Livre) e consolida os gráficos
de componentes lado a lado.

Autor: Marcio Jose Gomes Bastos Filho
Data de Criação: 26/03/2026
Última Atualização: 16/04/2026
Versão: 5.0
=============================================================================================
"""

import streamlit as st
import os
import shutil
import datetime
import re
import glob
import pandas as pd
import matplotlib.pyplot as plt
from streamlit_autorefresh import st_autorefresh

# --- Configuracoes Principais ---
BASE_DIR_LOGS = r"\\192.168.0.247\Logs_Datasul"
DIRETORIO_TCPING = r"C:\Users\marciof\Documents\GitHub\Monitoramentos\Tcping\logs"
AMBIENTES_DISPONIVEIS = ["Producao", "Homologacao", "Prototipo"]

# Dicionario de Apelidos Amigaveis
DICIONARIO_APELIDOS = {
    "tomcat_datasul": "Tomcat (Datasul)",
    "pasoe_outros_arquivos": "PASOE: Outros",
    "dts_c652ui-atr_p": "PASOE: ATR",
    "dts_c652ui-fnd_p": "PASOE: FND",
    "dts_c652ui_p": "PASOE: Principal",
    "rpw_c652ui-log_p": "RPW: Logs",
    "rpw_c652ui-rpw_p": "RPW: Principal",
    "dts_c652ui-atr_q": "PASOE: ATR",
    "dts_c652ui-fnd_q": "PASOE: FND",
    "dts_c652ui_q": "PASOE: Principal",
    "rpw_c652ui-log_q": "RPW: Logs",
    "rpw_c652ui-q_q": "RPW: Secundário",
    "dts_c652ui-atr_t": "PASOE: ATR",
    "dts_c652ui-fnd_t": "PASOE: FND",
    "dts_c652ui_t": "PASOE: Principal",
    "rpw_c652ui-log_t": "RPW: Logs",
    "rpw_c652ui-rpw_t": "RPW: Principal"
}

st.set_page_config(page_title="NOC: Monitor Datasul & Rede", layout="wide")
st_autorefresh(interval=60000, limit=None, key="monitor_refresh")

st.markdown("""
    <style>
        .block-container { padding-top: 0.6rem; padding-bottom: 0rem; padding-left: 1rem; padding-right: 1rem; }
        .stMetric { margin-top: -0.5rem; margin-bottom: -0.5rem; }
        .green-metric { color: #00FF00; font-size: 1.8rem; font-weight: bold; margin-top: -10px; }
        hr { margin-top: 10px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

def obter_metricas_ambiente(diretorio_alvo):
    """Calcula tamanho e retencao para um unico ambiente."""
    tamanho_total_bytes = 0
    tempo_mais_antigo = None
    quantidade_arquivos = 0
    tamanho_por_servico = {}

    if os.path.exists(diretorio_alvo):
        servicos = [d for d in os.listdir(diretorio_alvo) if os.path.isdir(os.path.join(diretorio_alvo, d))]
        for servico in servicos:
            caminho_servico = os.path.join(diretorio_alvo, servico)
            for raiz, _, arquivos in os.walk(caminho_servico):
                nome_pasta = os.path.basename(raiz)
                match_pasta = re.search(r'(20\d{2}-\d{2}-\d{2})', nome_pasta)
                if match_pasta:
                    data_pasta = datetime.datetime.strptime(match_pasta.group(1), "%Y-%m-%d")
                    if not tempo_mais_antigo or data_pasta < tempo_mais_antigo:
                        tempo_mais_antigo = data_pasta

                for arquivo in arquivos:
                    caminho_completo = os.path.join(raiz, arquivo)
                    if not os.path.islink(caminho_completo):
                        tamanho = os.path.getsize(caminho_completo)
                        tamanho_total_bytes += tamanho
                        quantidade_arquivos += 1
                        
                        match_arquivo = re.search(r'(20\d{2}-\d{2}-\d{2})', arquivo)
                        if match_arquivo:
                            data_arquivo = datetime.datetime.strptime(match_arquivo.group(1), "%Y-%m-%d")
                            if not tempo_mais_antigo or data_arquivo < tempo_mais_antigo:
                                tempo_mais_antigo = data_arquivo
                                
                        if "jboss" not in servico.lower():
                            nome_barra = arquivo.split(".agent.")[0] if ".agent." in arquivo else "pasoe_outros_arquivos"
                            tamanho_por_servico[nome_barra] = tamanho_por_servico.get(nome_barra, 0) + tamanho
                            
        for chave in tamanho_por_servico:
            tamanho_por_servico[chave] = tamanho_por_servico[chave] / (1024**3)
            
    return tamanho_total_bytes, tempo_mais_antigo, quantidade_arquivos, tamanho_por_servico

def obter_metricas_rede_historico(diretorio):
    df_vazio = pd.DataFrame()
    if not os.path.exists(diretorio): return df_vazio, "Erro", 0.0
    arquivos = sorted(glob.glob(os.path.join(diretorio, "tcping_*.txt")), key=os.path.getmtime)
    if not arquivos: return df_vazio, "Sem dados", 0.0
    ultimos_arquivos = arquivos[-3:]; dados = []; status_atual = "Desconhecido"; latencia_atual = 0.0
    for caminho_arquivo in ultimos_arquivos:
        nome_arquivo = os.path.basename(caminho_arquivo)
        match_data_fn = re.search(r'tcping_(20\d{2}-\d{2}-\d{2})_', nome_arquivo)
        data_arquivo = match_data_fn.group(1) if match_data_fn else None
        try:
            with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f: linhas = f.readlines()
        except Exception: continue
        for linha in linhas:
            if "Probing" in linha:
                match_hora = re.search(r"(\d{2}:\d{2}:\d{2}) Probing", linha)
                match_latencia = re.search(r"time=([\d\.]+)ms", linha)
                if match_hora and data_arquivo:
                    hora = match_hora.group(1); timestamp_str = f"{data_arquivo} {hora}"
                    latencia = float(match_latencia.group(1)) if match_latencia else 0.0
                    dados.append({"Timestamp": timestamp_str, "Latencia (ms)": latencia})
                    latencia_atual = latencia
                    status_atual = "Online" if "Port is open" in linha else "Offline"
    if dados:
        df = pd.DataFrame(dados); df['Timestamp'] = pd.to_datetime(df['Timestamp'], format="%Y-%m-%d %H:%M:%S")
        df.set_index("Timestamp", inplace=True); df.sort_index(inplace=True)
        return df, status_atual, latencia_atual
    return df_vazio, "Aguardando", 0.0

# --- COLETA DE DADOS UNIFICADA ---
st.markdown("<h4 style='margin-bottom:0px; padding-bottom:0px;'>Painel de Controle: Datasul & Rede (Visão Global)</h4>", unsafe_allow_html=True)

dados_ambientes = {}
gb_logs_total = 0
arquivos_total = 0
tempo_mais_antigo_global = None

with st.spinner('Consolidando métricas de todo o Storage...'):
    for amb in AMBIENTES_DISPONIVEIS:
        dir_amb = os.path.join(BASE_DIR_LOGS, amb)
        t_bytes, t_antigo, qtd_arq, servicos = obter_metricas_ambiente(dir_amb)
        
        gb_amb = t_bytes / (1024**3)
        gb_logs_total += gb_amb
        arquivos_total += qtd_arq
        
        if t_antigo:
            if not tempo_mais_antigo_global or t_antigo < tempo_mais_antigo_global:
                tempo_mais_antigo_global = t_antigo
                
        dados_ambientes[amb] = {
            "gb": gb_amb,
            "antigo": t_antigo,
            "qtd": qtd_arq,
            "servicos": servicos
        }
        
    df_rede_hist, status_rede, latencia_rede = obter_metricas_rede_historico(DIRETORIO_TCPING)
    try:
        disco = shutil.disk_usage(BASE_DIR_LOGS)
        gb_livre = disco.free / (1024**3)
    except Exception:
        disco = None
        gb_livre = 0

now = pd.Timestamp.now()

# --- LINHA 1: MÉTRICAS GLOBAIS E REDE ---
col_met_1, col_met_2, col_met_3 = st.columns(3)

with col_met_1:
    st.markdown("**Armazenamento (Todos os Ambientes)**")
    st.metric(label="Total Coletado", value=f"{gb_logs_total:.2f} GB", delta=f"{arquivos_total} arquivos")
    
with col_met_2:
    st.markdown("**Monitoramento TCPing**")
    sc = "#FF0000" if status_rede == "Offline" else "#00FF00"
    st.metric(label="Latencia Atual", value=f"{latencia_rede}ms")
    st.markdown(f"**Status:** <span style='color:{sc};'>{status_rede}</span>", unsafe_allow_html=True)

with col_met_3:
    st.markdown("**Espaco Livre no Storage (Geral)**")
    if disco:
        st.markdown(f"<p class='green-metric'>{gb_livre:.2f} GB</p>", unsafe_allow_html=True)
    else: st.info("Indisponivel")

st.markdown("---")

# --- LINHA 2: GRÁFICOS DE REDE ---
st.markdown("**Histórico de Conectividade**")
if not df_rede_hist.empty:
    c5, c1h, c1d = st.columns(3)
    for col, period, label in zip([c5, c1h, c1d], [pd.Timedelta(minutes=5), pd.Timedelta(hours=1), pd.Timedelta(days=1)], ["Últimos 5 Minutos", "Última Hora", "Último Dia"]):
        with col:
            st.markdown(f"*{label}*")
            df_p = df_rede_hist[df_rede_hist.index >= (now - period)]
            if not df_p.empty: st.line_chart(df_p["Latencia (ms)"], color="#00FF00", height=100)
else:
    st.info("Aguardando dados de rede...")

st.markdown("---")

# --- LINHA 3: USO DE DISCO GLOBAL ---
st.markdown("**Consumo de Disco: Ambientes x Espaço Livre**")
c_global_pizza, c_prod, c_homol, c_proto = st.columns([1.5, 1, 1, 1])

with c_global_pizza:
    if disco:
        labels_globais = ["Produção", "Homologação", "Protótipo", "Espaço Livre"]
        valores_globais = [
            dados_ambientes["Producao"]["gb"], 
            dados_ambientes["Homologacao"]["gb"], 
            dados_ambientes["Prototipo"]["gb"], 
            gb_livre
        ]
        # Cores fixas: Azul, Laranja, Roxo, e o Verde Neon imposto para o espaço livre
        cores_globais = ['#1f77b4', '#ff7f0e', '#9467bd', '#00FF00']
        
        fig, ax = plt.subplots(figsize=(5, 3))
        fig.patch.set_alpha(0)
        wedges, _ = ax.pie(valores_globais, startangle=140, colors=cores_globais, wedgeprops={'edgecolor': 'white'})
        ax.legend(wedges, labels_globais, title="Uso Global", loc="center left", bbox_to_anchor=(0.9, 0.5), fontsize=10)
        ax.axis('equal')
        st.pyplot(fig, clear_figure=True)

# Miniquadros informativos ao lado do gráfico global
amb_cols = [c_prod, c_homol, c_proto]
for idx, amb in enumerate(AMBIENTES_DISPONIVEIS):
    with amb_cols[idx]:
        st.markdown(f"**{amb}**")
        dias_ret = (datetime.datetime.now() - dados_ambientes[amb]["antigo"]).days if dados_ambientes[amb]["antigo"] else 0
        data_str = dados_ambientes[amb]["antigo"].strftime('%d/%m/%Y') if dados_ambientes[amb]["antigo"] else "N/A"
        
        st.metric(label="Uso de Disco", value=f"{dados_ambientes[amb]['gb']:.2f} GB")
        st.metric(label="Retenção Atual", value=f"{dias_ret} Dias", delta=f"Desde {data_str}", delta_color="off")

st.markdown("---")

# --- LINHA 4: DISTRIBUIÇÃO INTERNA (ZOOM NOS COMPONENTES) ---
st.markdown("**Distribuição Interna de Logs por Ambiente**")
col_pizza_1, col_pizza_2, col_pizza_3 = st.columns(3)
pizza_cols = [col_pizza_1, col_pizza_2, col_pizza_3]

for idx, amb in enumerate(AMBIENTES_DISPONIVEIS):
    with pizza_cols[idx]:
        st.markdown(f"*{amb}*")
        servicos_amb = dados_ambientes[amb]["servicos"]
        
        if servicos_amb:
            labels_originais = list(servicos_amb.keys())
            tamanhos = list(servicos_amb.values())
            labels_apelidados = [DICIONARIO_APELIDOS.get(n, n.replace('_', ' ').title()) for n in labels_originais]
            
            fig, ax = plt.subplots(figsize=(4, 2.5))
            fig.patch.set_alpha(0)
            wedges, _ = ax.pie(tamanhos, startangle=140, wedgeprops={'edgecolor': 'white'})
            
            # Legenda menor e ainda mais próxima para caber nas 3 colunas
            ax.legend(wedges, labels_apelidados, loc="center left", bbox_to_anchor=(0.85, 0.5), fontsize=8)
            ax.axis('equal')
            st.pyplot(fig, clear_figure=True)
        else:
            st.info("Nenhum log detectado.")

st.markdown("---")
st.caption(f"NOC Edition v5.0 (Unified) | Atualização: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | Storage: {BASE_DIR_LOGS}")