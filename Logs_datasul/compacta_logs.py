import os
import re
import zipfile
import shutil
from datetime import datetime
from tqdm import tqdm

CAMINHO_UNC = r"\\compartilhamento\Logs_Datasul"
AMBIENTES = ["Producao", "Homologacao", "Prototipo"]
DIAS_RETENCAO_COMPACTACAO = 1
DIAS_RETENCAO_EXPURGO = 90

def main():
    inicio = datetime.now()
    t_comp, t_exp, b_exp = 0, 0, 0
    for amb in AMBIENTES:
        pasta_amb = os.path.join(CAMINHO_UNC, amb)
        if not os.path.exists(pasta_amb): continue
        for serv in os.listdir(pasta_amb):
            dest_serv = os.path.join(pasta_amb, serv)
            if not os.path.isdir(dest_serv): continue
            for raiz, dirs, arqs in os.walk(dest_serv, topdown=False):
                for arq in arqs:
                    m = re.search(r'(20\d{2}-\d{2}-\d{2})', arq)
                    if m and (inicio - datetime.strptime(m.group(1), "%Y-%m-%d")).days > DIAS_RETENCAO_EXPURGO:
                        c = os.path.join(raiz, arq); b_exp += os.path.getsize(c); os.remove(c); t_exp += 1
                for d in dirs:
                    m = re.search(r'(20\d{2}-\d{2}-\d{2})', d)
                    if m:
                        c_dir = os.path.join(raiz, d); idade = (inicio - datetime.strptime(m.group(1), "%Y-%m-%d")).days
                        if idade > DIAS_RETENCAO_EXPURGO:
                            shutil.rmtree(c_dir); t_exp += 1
                        elif idade > DIAS_RETENCAO_COMPACTACAO:
                            c_zip = c_dir + '.zip'
                            if not os.path.exists(c_zip):
                                with zipfile.ZipFile(c_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                                    for r, _, fs in os.walk(c_dir):
                                        for f in fs:
                                            fp = os.path.join(r, f)
                                            zf.write(fp, os.path.relpath(fp, dest_serv))
                                shutil.rmtree(c_dir); t_comp += 1
    relatorio = f"\n==================================================\nRELATORIO DE COMPACTACAO GERAL\n==================================================\nData: {inicio.strftime('%d/%m/%Y %H:%M:%S')}\nCompactados: {t_comp} | Expurgados: {t_exp}\n==================================================\n"
    try:
        p = os.path.join(CAMINHO_UNC, "relatorio_compactacao_geral.txt")
        old = open(p, "r", encoding="utf-8").read() if os.path.exists(p) else ""
        open(p, "w", encoding="utf-8").write(relatorio + "\n" + old)
    except: pass

if __name__ == "__main__": main()