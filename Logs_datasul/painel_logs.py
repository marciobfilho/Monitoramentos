"""
=============================================================================================
Projeto: Monitoramento de Logs TOTVS Datasul
Módulo:  Painel Web de Métricas (Frontend) - Compact Edition
Arquivo: painel_logs.py

Descrição: 
Dashboard interativo construído com Streamlit para monitorar o tamanho e a retenção 
dos logs (JBoss, Tomcat, Pasoe) do ambiente Datasul armazenados em rede.
Inclui monitoramento de rede (TCPing) em 3 janelas de tempo.
Layout compactado para NOC (1cm de margem superior) e gráfico de pizza minimalista
sem porcentagens internas, utilizando apenas legendas apelidadas.

Autor: Marcio Jose Gomes Bastos Filho
Data de Criação: 26/03/2026
Última Atualização: 27/03/2026
Versão: 3.2
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

# --- Configurações Principais ---
# --- Configurações Principais ---
DIRETORIO_LOGS = r"\\192.168.0.247\Logs_Datasul\Producao"

# ATENÇÃO: Altere este caminho para a pasta onde os seus arquivos do tcping são salvos!
DIRETORIO_TCPING = r"C:\Users\marciof\Documents\GitHub\Monitoramentos\Tcping\logs" # Placeholder

# Dicionário de Apelidos Amigáveis para os Agentes do Pasoe/Tomcat
DICIONARIO_APELIDOS = {
    "tomcat_datasul": "Tomcat (Datasul)",
    "dts_c652ui-atr_p": "PASOE: ATR",
    "dts_c652ui-fnd_p": "PASOE: FND",
    "dts_c652ui_p": "PASOE: Principal",
    "rpw_c652ui-log_p": "RPW: Logs",
    "rpw_c652ui-rpw_p": "RPW: Principal",
    "pasoe_outros_arquivos": "PASOE: Outros"
}

# Configura a página (layout wide é essencial)
st.set_page_config(page_title="NOC: Monitor Datasul & Rede", layout="wide", page_icon="📊")

# Auto Atualização a cada 1 minuto (60.000ms)
st_autorefresh(interval=60000, limit=None, key="monitor_refresh")

# ==========================================
# ⚡ AJUSTE DE LAYOUT: MARGEM SUPERIOR 1CM ⚡
# ==========================================
# Injeta CSS para remover o padding padrão do Streamlit e colar o conteúdo no topo
st.markdown("""
    <style>
        /* Ajusta o padding do container principal */
        .block-container {
            padding-top: 0.6rem; /* Equivale a aproximadamente 1cm */
            padding-bottom: 0rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        /* Tighten spacing between metric widgets */
        .stMetric {
            margin-top: -0.5rem;
            margin-bottom: -0.5rem;
        }
    </style>
    """, unsafe_allow_html=True)


# ==========================================
# FUNÇÕES DE COLETA DE MÉTRICAS (BACKEND)
# ==========================================

def obter_metricas_logs():
    """Varre a pasta de logs e calcula retenção e tamanho."""
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
                        
                        if "jboss" not in servico.lower():
                            if servico.lower() == "logs_pasoe":
                                nome_barra = arquivo.split(".agent.")[0] if ".agent." in arquivo else "pasoe_outros_arquivos"
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

def obter_metricas_rede_historico(diretorio):
    """Lê múltiplos arquivos de tcping para garantir histórico de 24h e retorna DataFrame indexado."""
    df_vazio = pd.DataFrame()
    if not os.path.exists(diretorio):
        return df_vazio, "Diretório não encontrado", 0.0

    arquivos = sorted(glob.glob(os.path.join(diretorio, "tcping_*.txt")), key=os.path.getmtime)
    if not arquivos:
        return df_vazio, "Sem arquivos", 0.0

    ultimos_arquivos = arquivos[-3:]
    dados = []
    status_atual = "Desconhecido"
    latencia_atual = 0.0

    for caminho_arquivo in ultimos_arquivos:
        nome_arquivo = os.path.basename(caminho_arquivo)
        match_data_fn = re.search(r'tcping_(20\d{2}-\d{2}-\d{2})_', nome_arquivo)
        data_arquivo = match_data_fn.group(1) if match_data_fn else None

        try:
            with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
                linhas = f.readlines()
        except Exception: continue

        for linha in linhas:
            if "Probing" in linha:
                match_hora = re.search(r"(\d{2}:\d{2}:\d{2}) Probing", linha)
                match_latencia = re.search(r"time=([\d\.]+)ms", linha)

                if match_hora and data_arquivo:
                    hora = match_hora.group(1)
                    timestamp_str = f"{data_arquivo} {hora}"
                    latencia = float(match_latencia.group(1)) if match_latencia else 0.0
                    dados.append({"Timestamp": timestamp_str, "Latência (ms)": latencia})

                    latencia_atual = latencia
                    if "Port is open" in linha:
                        status_atual = "Online"
                    elif "No response" in linha or "timeout" in linha.lower():
                        status_atual = "Offline / Timeout"

    if dados:
        df = pd.DataFrame(dados)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], format="%Y-%m-%d %H:%M:%S")
        df.set_index("Timestamp", inplace=True)
        df.sort_index(inplace=True)
        return df, status_atual, latencia_atual
    else:
        return df_vazio, "Aguardando Pings", 0.0

# ==========================================
# INTERFACE WEB (FRONTEND) - NOC COMPACT
# ==========================================

# Coleta de dados simultânea
with st.spinner('Sincronizando métricas NOC...'):
    tamanho_logs, disco, tempo_mais_antigo, qtd_arquivos, tamanho_servicos = obter_metricas_logs()
    df_rede_hist, status_rede, latencia_rede = obter_metricas_rede_historico(DIRETORIO_TCPING)

gb_logs = tamanho_logs / (1024**3)
dias_retencao = (datetime.datetime.now() - tempo_mais_antigo).days
now = pd.Timestamp.now()

# --- TÍTULO GERAL (TIGHT) ---
st.markdown("<h4 style='margin-bottom:0px; padding-bottom:0px;'>Painel de Controle: Datasul & Rede</h4>", unsafe_allow_html=True)

# --- SESSÃO GERAL DE MÉTRICAS (Agrupadas no Topo conforme solicitado) ---
# Unimos Armazenamento, Retenção e Espaço Livre em colunas consecutivas
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Armazenamento e Retenção**")
    st.metric(label="Total Coletado", value=f"{gb_logs:.2f} GB", delta=f"{qtd_arquivos} arquivos")

with col2:
    st.markdown("**Retenção Alcançada**")
    st.metric(label="Dias de Retenção", value=f"{dias_retencao} Dias", delta=f"Desde {tempo_mais_antigo.strftime('%d/%m/%Y')}", delta_color="off")

with col3:
    if disco:
        gb_livre = disco.free / (1024**3)
        st.markdown("**Espaço Livre**")
        st.metric(label="Espaço Livre no Disco", value=f"{gb_livre:.2f} GB")
    else:
        st.info("Espaço livre indisponível.")

# 🔥 REMOVIDA LINHA HORIZONTAL ("---") PARA COLAR OS GRÁFICOS NAS MÉTRICAS 🔥

# --- SESSÃO DE GRÁFICOS (REDE ESQUERDA, DISCO DIREITA) ---
# Layout NOC: Rede ocupe 2/3, Disco ocupe 1/3
col_main_rede, col_main_disco = st.columns([2, 1])

# --- COLUNA ESQUERDA: MONITOR DE REDE (3 JANELAS DE TEMPO) ---
with col_main_rede:
    st.markdown("**Conectividade (TCPing)**")
    
    # Métrica de Status e Latência (Compacta ao lado dos gráficos)
    c_m_status, c_m_charts = st.columns([1, 4])
    
    with c_m_status:
        status_color = "#FF0000" if status_rede == "Offline / Timeout" else "#00FF00" if status_rede == "Online" else "#FFFF00"
        st.metric(label="Latência (ms)", value=f"{latencia_rede}ms")
        st.markdown(f"**Status:** <span style='color:{status_color};'>{status_rede}</span>", unsafe_allow_html=True)
        st.write(" ") # Espaço para alinhar com o topo dos gráficos

    with c_m_charts:
        # Lógica de cor baseada no threshold de 35ms
        chart_color = "#FF0000" if latencia_rede > 35 else "#00FF00"
        
        if not df_rede_hist.empty:
            # Sub-colunas para os 3 gráficos
            c_5m, c_1h, c_1d = st.columns(3)
            
            with c_5m:
                st.markdown("*Ultimos 5 Minutos*")
                cutoff_5m = now - pd.Timedelta(minutes=5)
                df_5m = df_rede_hist[df_rede_hist.index >= cutoff_5m]
                if not df_5m.empty:
                    st.line_chart(df_5m["Latência (ms)"], color=chart_color, height=120)
                else: st.caption("Sem dados.")

            with c_1h:
                st.markdown("*Ultima Hora*")
                cutoff_1h = now - pd.Timedelta(hours=1)
                df_1h = df_rede_hist[df_rede_hist.index >= cutoff_1h]
                if not df_1h.empty:
                    df_1h_plot = df_1h.copy()
                    df_1h_plot.index = df_1h_plot.index.strftime('%H:%M')
                    st.line_chart(df_1h_plot["Latência (ms)"], color=chart_color, height=120)
                else: st.caption("Sem dados.")

            with c_1d:
                st.markdown("*Ultimo Dia*")
                cutoff_1d = now - pd.Timedelta(days=1)
                df_1d = df_rede_hist[df_rede_hist.index >= cutoff_1d]
                if not df_1d.empty:
                    # Amostragem a cada 10 minutos para não poluir o gráfico de 24h
                    df_1d_resampled = df_1d.resample('10T').mean().dropna()
                    df_1d_resampled.index = df_1d_resampled.index.strftime('%H:%M')
                    st.line_chart(df_1d_resampled["Latência (ms)"], color=chart_color, height=120)
                else: st.caption("Sem dados.")
        else:
            st.info("Aguardando dados de rede históricos...")

# --- COLUNA DIREITA: MONITOR DE DISCO (PIZZA + SAÚDE) ---
with col_main_disco:
    st.markdown("**Distribuição de Espaço no Disco (GB)**")
    
    if tamanho_servicos and disco:
        # Prepara dados para o gráfico de pizza Matplotlib
        labels_originais = list(tamanho_servicos.keys())
        tamanhos = list(tamanho_servicos.values())
        
        # 1. Aplica os Apelidos definidos no topo do código
        labels_apelidados = [DICIONARIO_APELIDOS.get(nome, nome.replace('_', ' ').title()) for nome in labels_originais]
        
        # 2. Adiciona o Espaço Livre como uma fatia
        labels_apelidados.append("Espaço Livre")
        tamanhos.append(gb_livre)
        
        # 3. Desenha a Pizza Minimalista (SEM porcentagens internas)
        fig, ax = plt.subplots(figsize=(6, 3))
        
        # 🚀 ALTERAÇÃO: Removido autopct='%1.1f%%' 🚀
        # Agora a pizza fica limpa, apenas as fatias coloridas.
        wedges, _ = ax.pie(
            tamanhos, 
            startangle=140, 
            textprops={'fontsize': 8},
            wedgeprops={'edgecolor': 'white'} # Adiciona borda branca sutil para separar fatias
        )
        
        # Cria a legenda lateral organizada com os apelidos
        ax.legend(
            wedges, 
            labels_apelidados, 
            title="Componentes", 
            loc="center left", 
            bbox_to_anchor=(1, 0, 0.5, 1), # Posiciona a legenda para fora da área do gráfico
            fontsize=8
        )
        ax.axis('equal') # Garante que seja um círculo perfeito
        
        # Renderiza no Streamlit
        st.pyplot(fig, clear_figure=True)
    else:
        st.info("Métricas do disco indisponíveis.")

st.markdown("---")
st.caption(f"NOC Edition Compact | Atualização: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | Logs: {DIRETORIO_LOGS} | TCPing: {DIRETORIO_TCPING}")