import streamlit as st
import re
						 

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

def parse_time_input(time_str):
    """Converte string HH:MM ou HH:MM:SS em segundos. Retorna None se inválido."""
    time_str = time_str.strip()
    match = re.fullmatch(r'(\d{1,2}):(\d{2})(?::(\d{2}))?', time_str)
    if not match:
        return None
    h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)
    if h > 23 or m > 59 or s > 59:
        return None
    return h * 3600 + m * 60 + s

col1, col2 = st.columns(2)
start_str = col1.text_input("Início do intervalo (HH:MM ou HH:MM:SS)", value="00:00")
end_str   = col2.text_input("Fim do intervalo (HH:MM ou HH:MM:SS)", value="23:59")

st.info("Padrões suportados nativamente: Tomcat/Catalina, JBoss/Autorizador, PASOE/Datasul e RPW.")

																																		   
uploaded_file = st.file_uploader("Selecione o arquivo de log (.log ou .txt)", type=["log", "txt"])

if uploaded_file is not None:
    if st.button("Executar Extração", type="primary", use_container_width=True):
        start_sec = parse_time_input(start_str)
        end_sec   = parse_time_input(end_str)

        if start_sec is None:
            st.error("Horário de início inválido. Use o formato HH:MM ou HH:MM:SS.")
        elif end_sec is None:
            st.error("Horário de fim inválido. Use o formato HH:MM ou HH:MM:SS.")
        elif start_sec > end_sec:
            st.error("Falha de validação: O horário de início deve ser anterior ao fim.")
        else:
            with st.spinner("Lendo e filtrando os chunks na memória..."):
                filtered_lines = []
																			
                for line_bytes in uploaded_file:
                    line = line_bytes.decode('utf-8', errors='ignore')
                    t_sec = extract_time_secs(line)
					
															   
                    if t_sec >= 0 and start_sec <= t_sec <= end_sec:
                        filtered_lines.append(line)

                if not filtered_lines:
                    st.warning("Nenhuma linha localizada com o timestamp dentro do range especificado.")
                else:
                    st.success(f"Extração concluída: {len(filtered_lines):,} linhas filtradas.")
                    output_data = "".join(filtered_lines)

                    # Formata o nome do arquivo com base no texto digitado
                    start_tag = start_str.replace(":", "")
                    end_tag   = end_str.replace(":", "")
                    st.download_button(
                        label="Download Log Extraído",
                        data=output_data,
                        file_name=f"extracao_{start_tag}_{end_tag}.log",
                        mime="text/plain",
                        use_container_width=True
                    )