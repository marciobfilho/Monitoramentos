import streamlit as st
import re
from datetime import time

st.set_page_config(page_title="Extrator de Logs", layout="wide", page_icon="✂️")

st.markdown("<h4 style='margin-bottom:0px; padding-bottom:0px;'>Separador de Logs por Intervalo de Tempo</h4>", unsafe_allow_html=True)
st.markdown("---")

def extract_time_secs(line):
    # Padrão ISO: 2026-05-08T08:30:05
    iso = re.search(r'\d{4}-\d{2}-\d{2}T(\d{2}):(\d{2}):(\d{2})', line)
    if iso:
        return int(iso.group(1)) * 3600 + int(iso.group(2)) * 60 + int(iso.group(3))
    # Padrão Catalina: 08-May-2026 08:30:05
    cat = re.search(r'\d{2}-[A-Za-z]{3}-\d{4}\s+(\d{2}):(\d{2}):(\d{2})', line)
    if cat:
        return int(cat.group(1)) * 3600 + int(cat.group(2)) * 60 + int(cat.group(3))
    return -1

col1, col2 = st.columns(2)
start_time = col1.time_input("Início do intervalo", value=time(0, 0))
end_time = col2.time_input("Fim do intervalo", value=time(23, 59))

st.info("Padrões suportados nativamente: Tomcat/Catalina, JBoss/Autorizador, PASOE/Datasul e RPW.")

# Utiliza o file_uploader. Lembre-se de configurar a variável STREAMLIT_SERVER_MAX_UPLOAD_SIZE no serviço NSSM para suportar logs pesados
uploaded_file = st.file_uploader("Selecione o arquivo de log (.log ou .txt)", type=["log", "txt"])

if uploaded_file is not None:
    if st.button("Executar Extração", type="primary", use_container_width=True):
        start_sec = start_time.hour * 3600 + start_time.minute * 60 + start_time.second
        end_sec = end_time.hour * 3600 + end_time.minute * 60 + end_time.second
        
        if start_sec > end_sec:
            st.error("Falha de validação: O horário de início deve ser anterior ao fim.")
        else:
            with st.spinner("Lendo e filtrando os chunks na memória..."):
                filtered_lines = []
                # Leitura iterativa nativa do Streamlit UploadedFile (bytes)
                for line_bytes in uploaded_file:
                    line = line_bytes.decode('utf-8', errors='ignore')
                    t_sec = extract_time_secs(line)
                    
                    # Se achar tempo válido e estiver no range
                    if t_sec >= 0 and start_sec <= t_sec <= end_sec:
                        filtered_lines.append(line)
                
                if not filtered_lines:
                    st.warning("Nenhuma linha localizada com o timestamp dentro do range especificado.")
                else:
                    st.success(f"Extração concluída: {len(filtered_lines):,} linhas filtradas.")
                    output_data = "".join(filtered_lines)
                    
                    st.download_button(
                        label="Download Log Extraído",
                        data=output_data,
                        file_name=f"extracao_{start_time.strftime('%H%M%S')}_{end_time.strftime('%H%M%S')}.log",
                        mime="text/plain",
                        use_container_width=True
                    )