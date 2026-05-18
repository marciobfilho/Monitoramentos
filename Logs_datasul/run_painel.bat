@echo off
cd /d "C:\Monitoramentos\Logs_datasul"
C:\Users\suporte\AppData\Local\Microsoft\WindowsApps\python.exe -m streamlit run painel_logs.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
