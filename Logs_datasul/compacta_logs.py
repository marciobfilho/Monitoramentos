"""
=============================================================================================
Projeto: Monitoramento de Logs TOTVS Datasul
Módulo:  Motor de Compactação e Limpeza (Backend - Disco)
Arquivo: compacta_logs.py
Versão: 2.4 (RECURSIVO)
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

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')

UNIDADE_REDE = "L:"
CAMINHO_UNC = r"\\192.168.0.247\Logs_Datasul"
AMBIENTES = ["Producao", "Homologacao", "Prototipo"]

DIAS_RETENCAO_COMPACTACAO = 5
DIAS_RETENCAO_EXPURGO = 90

def main():
    tempo_inicio = datetime.now()
    if not os.path.exists(f"{UNIDADE_REDE}\\"):
        try: subprocess.run(["net", "use", UNIDADE_REDE, CAMINHO_UNC], check=True, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except: pass 
            
    print(f"\n[INICIO] Rotina de Compactacao e Expurgo (Recursiva) em: {tempo_inicio.strftime('%d/%m/%Y %H:%M:%S')}")
    t_comp, t_exp, b_comp, b_exp = 0, 0, 0, 0
    
    for amb in AMBIENTES:
        pasta_amb = rf"{UNIDADE_REDE}\{amb}"
        if not os.path.exists(pasta_amb): continue
        print(f"\n--- Varrendo: {amb} ---")
        servicos = [d for d in os.listdir(pasta_amb) if os.path.isdir(os.path.join(pasta_amb, d))]
        pbar = tqdm(servicos, desc=f"Progresso {amb}", colour='yellow')

        for serv in pbar:
            pbar.set_postfix_str(f"Analisando: {serv}")
            dest_serv = os.path.join(pasta_amb, serv)
            
            # 🛡️ BUSCA RECURSIVA PARA EXPURGO 🛡️
            for raiz, dirs, arqs in os.walk(dest_serv, topdown=False):
                # Processa Arquivos (Zips antigos perdidos)
                for arq in arqs:
                    if "_ATIVO" in arq: continue
                    m = re.search(r'(20\d{2}-\d{2}-\d{2})', arq)
                    if m:
                        idade = (tempo_inicio - datetime.strptime(m.group(1), "%Y-%m-%d")).days
                        if idade > DIAS_RETENCAO_EXPURGO:
                            c_arq = os.path.join(raiz, arq)
                            b_exp += os.path.getsize(c_arq)
                            os.remove(c_arq); t_exp += 1
                            tqdm.write(f"      [EXPURGO] Arquivo: {arq}")

                # Processa Pastas (Pastas antigas de 2025)
                for d in dirs:
                    m = re.search(r'(20\d{2}-\d{2}-\d{2})', d)
                    if m:
                        c_dir = os.path.join(raiz, d)
                        idade = (tempo_inicio - datetime.strptime(m.group(1), "%Y-%m-%d")).days
                        
                        # REGRA SOBERANA: DELETA TUDO > 90
                        if idade > DIAS_RETENCAO_EXPURGO:
                            b_exp += sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(c_dir) for f in fs)
                            shutil.rmtree(c_dir); t_exp += 1
                            tqdm.write(f"      [EXPURGO] Pasta: {d}")
                        
                        # REGRA DE COMPACTACAO: 11 A 90 DIAS
                        elif idade > DIAS_RETENCAO_COMPACTACAO:
                            c_zip = c_dir + '.zip'
                            if not os.path.exists(c_zip):
                                t_orig = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(c_dir) for f in fs)
                                with zipfile.ZipFile(c_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                                    for r_d, _, fls in os.walk(c_dir):
                                        for f in fls:
                                            fp = os.path.join(r_d, f)
                                            if os.path.exists(fp): zf.write(fp, os.path.relpath(fp, dest_serv))
                                b_comp += (t_orig - os.path.getsize(c_zip))
                                shutil.rmtree(c_dir); t_comp += 1
                                tqdm.write(f"      [COMPACTACAO] {d}")

    print(f"\nFim. Expurgados: {t_exp} | Compactados: {t_comp} | Liberado: {b_exp/(1024**2):.2f} MB")

if __name__ == "__main__": main()