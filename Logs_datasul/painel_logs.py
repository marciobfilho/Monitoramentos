"""
=============================================================================================
Projeto: Monitoramento de Logs TOTVS Datasul
Módulo:  Painel Web de Métricas (Frontend) - Visão Unificada Turbo
Arquivo: painel_logs.py

Descrição: 
Dashboard interativo para monitorar logs do ambiente Datasul.
Versão 5.3: Porcentagens movidas exclusivamente para a legenda, padronização de nomes 
(Pasoe Datasul, RPW multiprocessos e Rpwlogs) e limpeza visual dos gráficos.

Autor: Marcio Jose Gomes Bastos Filho
Data de Criação: 26/03/2026
Última Atualização: 29/04/2026
Versão: 5.3
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
BASE_DIR_LOGS = r"\\compartilhamento\Logs_Datasul"
DIRETORIO_TCPING = r"\\Monitoramentos\Tcping\LOGS"
AMBIENTES_DISPONIVEIS = ["Producao", "Homologacao", "Prototipo"]

DATE_PATTERN = re.compile(r'(20\d{2}-\d{2}-\d{2})')

# Dicionário de Apelidos (v5.5 - Diferenciação Linux/Windows)
DICIONARIO_APELIDOS = {
    "tomcat_datasul": "Tomcat (Datasul)",
    "logs_pasoe_geral": "PASOE: Base/Logs", 
    "jboss_autorizador": "JBoss: Autorizador",
    "jboss_foundation_ptu": "JBoss: Foundation PTU",
    "jboss_foundation_gpu": "JBoss: Foundation GPU",
    
    # Servidores RPW Linux
    "pasoe_rpw_linux": "RPW multiprocessos (Linux)",
    "pasoe_rpwlog_linux": "Rpwlogs (Linux)",
    
    # Produção (_p) - Windows
    "dts_c652ui_p": "Pasoe Datasul",
    "dts_c652ui-atr_p": "PASOE: ATR",
    "dts_c652ui-fnd_p": "PASOE: FND",
    "rpw_c652ui-log_p": "Rpwlogs (Windows)",
    "rpw_c652ui-rpw_p": "RPW multiprocessos (Windows)",
    
    # Homologação (_q) - Windows
    "dts_c652ui_q": "Pasoe Datasul",
    "dts_c652ui-atr_q": "PASOE: ATR",
    "dts_c652ui-fnd_q": "PASOE: FND",
    "rpw_c652ui-log_q": "Rpwlogs (Windows)",
    "rpw_c652ui-q_q": "RPW multiprocessos (Windows)",
    
    # Protótipo (_t) - Windows
    "dts_c652ui_t": "Pasoe Datasul",
    "dts_c652ui-atr_t": "PASOE: ATR",
    "dts_c652ui-fnd_t": "PASOE: FND",
    "rpw_c652ui-log_t": "Rpwlogs (Windows)",
    "rpw_c652ui-rpw_t": "RPW multiprocessos (Windows)"
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

@st.cache_data(ttl=45)
def obter_metricas_ambiente_fast(diretorio_alvo):
    tamanho_total_bytes = 0
    tempo_mais_antigo = None
    quantidade_arquivos = 0
    tamanho_por_servico = {}

    if not os.path.exists(diretorio_alvo):
        return 0, None, 0, {}

    try:
        with os.scandir(diretorio_alvo) as it:
            servicos = [entry.name for entry in it if entry.is_dir()]
    except Exception:
        return 0, None, 0, {}

    for servico in servicos:
        caminho_servico = os.path.join(diretorio_alvo, servico)
        dirs_to_scan = [caminho_servico]
        while dirs_to_scan:
            current_dir = dirs_to_scan.pop()
            try:
                with os.scandir(current_dir) as it:
                    for entry in it:
                        match_data = DATE_PATTERN.search(entry.name)
                        if match_data:
                            data_item = datetime.datetime.strptime(match_data.group(1), "%Y-%m-%d")
                            if not tempo_mais_antigo or data_item < tempo_mais_antigo:
                                tempo_mais_antigo = data_item
                        if entry.is_dir():
                            dirs_to_scan.append(entry.path)
                        elif entry.is_file():
                            try:
                                tamanho = entry.stat().st_size
                                tamanho_total_bytes += tamanho
                                quantidade_arquivos += 1
                                nome_barra = servico.lower()
                                if nome_barra == "logs_pasoe":
                                    if ".agent." in entry.name:
                                        nome_barra = entry.name.split(".agent.")[0].lower()
                                    else:
                                        nome_barra = "logs_pasoe_geral"
                                tamanho_por_servico[nome_barra] = tamanho_por_servico.get(nome_barra, 0) + tamanho
                            except Exception: pass
            except Exception: pass

    for chave in list(tamanho_por_servico.keys()):
        tamanho_por_servico[chave] = tamanho_por_servico[chave] / (1024**3)
            
    return tamanho_total_bytes, tempo_mais_antigo, quantidade_arquivos, tamanho_por_servico

@st.cache_data(ttl=45)
def obter_metricas_rede_historico(diretorio):
    df_vazio = pd.DataFrame()
    if not os.path.exists(diretorio): return df_vazio, "Erro", 0.0
    arquivos = sorted(glob.glob(os.path.join(diretorio, "tcping_*.txt")), key=os.path.getmtime)
    if not arquivos: return df_vazio, "Sem dados", 0.0
    ultimos_arquivos = arquivos[-3:]; dados = []; status_atual = "Desconhecido"; latencia_atual = 0.0
    for caminho_arquivo in ultimos_arquivos:
        nome_arquivo = os.path.basename(caminho_arquivo)
        match_data_fn = DATE_PATTERN.search(nome_arquivo)
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

st.markdown("<h4 style='margin-bottom:0px; padding-bottom:0px;'>Painel de Controle: Datasul & Rede (Visão Global)</h4>", unsafe_allow_html=True)

dados_ambientes = {}
gb_logs_total = 0
arquivos_total = 0

with st.spinner('Consolidando métricas...'):
    for amb in AMBIENTES_DISPONIVEIS:
        dir_amb = os.path.join(BASE_DIR_LOGS, amb)
        t_bytes, t_antigo, qtd_arq, servicos = obter_metricas_ambiente_fast(dir_amb)
        gb_amb = t_bytes / (1024**3)
        gb_logs_total += gb_amb
        arquivos_total += qtd_arq
        dados_ambientes[amb] = {"gb": gb_amb, "antigo": t_antigo, "qtd": qtd_arq, "servicos": servicos}
        
    df_rede_hist, status_rede, latencia_rede = obter_metricas_rede_historico(DIRETORIO_TCPING)
    try:
        disco = shutil.disk_usage(BASE_DIR_LOGS)
        gb_livre = disco.free / (1024**3)
    except Exception:
        disco = None; gb_livre = 0

# --- LINHA 1: METRICAS GLOBAIS ---
col_met_1, col_met_2, col_met_3 = st.columns(3)
with col_met_1: st.metric(label="Total Coletado", value=f"{gb_logs_total:.2f} GB", delta=f"{arquivos_total} arquivos")
with col_met_2:
    sc = "#FF0000" if status_rede == "Offline" else "#00FF00"
    st.metric(label="Latencia Atual", value=f"{latencia_rede}ms")
    st.markdown(f"**Status:** <span style='color:{sc};'>{status_rede}</span>", unsafe_allow_html=True)
with col_met_3:
    if disco: st.markdown(f"**Storage Livre (L:\\)**<br><p class='green-metric'>{gb_livre:.2f} GB</p>", unsafe_allow_html=True)

st.markdown("---")

# --- LINHA 2: USO DE DISCO GLOBAL ---
st.markdown("**Consumo Global (Ambientes x Espaço Livre)**")
c_gl, c_p, c_h, c_pr = st.columns([1.5, 1, 1, 1])

with c_gl:
    labels_globais = ["Produção", "Homologação", "Protótipo", "Espaço Livre"]
    valores_globais = [dados_ambientes["Producao"]["gb"], dados_ambientes["Homologacao"]["gb"], dados_ambientes["Prototipo"]["gb"], gb_livre]
    total_g = sum(valores_globais)
    # Porcentagem na legenda
    labels_pct = [f"{l} ({(v/total_g)*100:.1f}%)" if total_g > 0 else l for l, v in zip(labels_globais, valores_globais)]
    
    fig, ax = plt.subplots(figsize=(5, 3))
    fig.patch.set_alpha(0)
    wedges, _ = ax.pie(valores_globais, startangle=140, colors=['#1f77b4', '#ff7f0e', '#9467bd', '#00FF00'], wedgeprops={'edgecolor': 'white'})
    ax.legend(wedges, labels_pct, loc="center left", bbox_to_anchor=(0.9, 0.5), fontsize=10)
    ax.axis('equal'); st.pyplot(fig, clear_figure=True)

for col, amb in zip([c_p, c_h, c_pr], AMBIENTES_DISPONIVEIS):
    with col:
        st.markdown(f"**{amb}**")
        dias = (datetime.datetime.now() - dados_ambientes[amb]["antigo"]).days if dados_ambientes[amb]["antigo"] else 0
        st.metric(label="Uso", value=f"{dados_ambientes[amb]['gb']:.2f} GB")
        st.metric(label="Retenção", value=f"{dias} Dias", delta_color="off")

st.markdown("---")

# --- LINHA 3: DISTRIBUIÇÃO INTERNA POR AMBIENTE ---
st.markdown("**Distribuição Interna com Espaço Livre**")
cp1, cp2, cp3 = st.columns(3)
for col, amb in zip([cp1, cp2, cp3], AMBIENTES_DISPONIVEIS):
    with col:
        st.markdown(f"*{amb}*")
        servs = dados_ambientes[amb]["servicos"]
        if servs:
            labels_raw = list(servs.keys()); vals = list(servs.values())
            labels_txt = [DICIONARIO_APELIDOS.get(n, n.replace('_', ' ').title()) for n in labels_raw]
            labels_txt.append("Espaço Livre"); vals.append(gb_livre)
            total_amb = sum(vals)
            # Porcentagem na legenda
            labels_pct_amb = [f"{l} ({(v/total_amb)*100:.1f}%)" if total_amb > 0 else l for l, v in zip(labels_txt, vals)]
            
            fig, ax = plt.subplots(figsize=(4, 2.5))
            fig.patch.set_alpha(0)
            prop_cycle = plt.rcParams['axes.prop_cycle']
            cores = [c['color'] for c in prop_cycle][:len(vals)-1] + ['#00FF00']
            wedges, _ = ax.pie(vals, startangle=140, colors=cores, wedgeprops={'edgecolor': 'white'})
            ax.legend(wedges, labels_pct_amb, loc="center left", bbox_to_anchor=(0.85, 0.5), fontsize=8)
            ax.axis('equal'); st.pyplot(fig, clear_figure=True)
        else: st.info("Sem logs.")

st.caption(f"NOC Edition v5.3 | Atualização: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")