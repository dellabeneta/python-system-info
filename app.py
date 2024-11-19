from flask import Flask, render_template, Response
import psutil
import platform
import cpuinfo
import os
import json
from datetime import datetime
import time
import re
import subprocess
import socket
import requests
from pathlib import Path

app = Flask(__name__)

def get_size(bytes):
    """
    Converte bytes para formato legível (KB, MB, GB)
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0

def get_distro_info():
    """
    Obtém informações detalhadas da distribuição Linux
    """
    try:
        # Tenta ler o arquivo os-release
        os_release = Path('/etc/os-release').read_text()
        info = dict(line.split('=', 1) for line in os_release.splitlines() if '=' in line)
        # Remove aspas das strings
        for key in info:
            info[key] = info[key].strip('"')
        return info.get('PRETTY_NAME', 'Desconhecido')
    except:
        return 'Desconhecido'

def get_desktop_environment():
    """
    Detecta o ambiente de desktop atual
    """
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '')
    if desktop:
        if 'KDE' in desktop:
            try:
                # Tenta obter a versão do Plasma
                plasma_version = subprocess.check_output(['plasmashell', '--version']).decode().strip()
                return f"KDE Plasma {plasma_version}"
            except:
                return "KDE Plasma"
        return desktop
    return "Desconhecido"

def get_ip_addresses():
    """
    Obtém os endereços IP interno e externo
    """
    # IP interno
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        internal_ip = s.getsockname()[0]
        s.close()
    except:
        internal_ip = "Não disponível"

    # IP externo
    try:
        external_ip = requests.get('https://api.ipify.org').text
    except:
        external_ip = "Não disponível"

    return internal_ip, external_ip

def get_architecture():
    """
    Retorna a arquitetura do sistema de forma mais amigável
    """
    arch = platform.machine()
    if 'x86_64' in arch:
        return '64-bit'
    elif 'i386' in arch or 'i686' in arch:
        return '32-bit'
    return arch

def get_system_info():
    # Informações do Sistema Operacional
    system_info = {
        'os': platform.system(),
        'os_version': get_distro_info() if platform.system() == 'Linux' else platform.version(),
        'os_release': platform.release(),
        'architecture': get_architecture(),
        'processor': platform.processor(),
        'hostname': platform.node()
    }
    
    # CPU Info
    cpu_info = cpuinfo.get_cpu_info()
    cpu_freq = psutil.cpu_freq()
    cpu_data = {
        'brand': cpu_info['brand_raw'],
        'cores_physical': psutil.cpu_count(logical=False),
        'cores_total': psutil.cpu_count(logical=True),
        'freq_current': f"{cpu_freq.current:.2f}MHz" if cpu_freq else "N/A",
        'freq_max': f"{cpu_freq.max:.2f}MHz" if cpu_freq else "N/A",
        'usage_percent': psutil.cpu_percent(interval=1)
    }

    # Memória
    memory = psutil.virtual_memory()
    memory_data = {
        'total': get_size(memory.total),
        'available': get_size(memory.available),
        'used': get_size(memory.used),
        'percent': memory.percent
    }

    # Disco
    disk = psutil.disk_usage('/')
    disk_data = {
        'total': get_size(disk.total),
        'used': get_size(disk.used),
        'free': get_size(disk.free),
        'percent': disk.percent
    }

    return {
        'system': system_info,
        'cpu': cpu_data,
        'memory': memory_data,
        'disk': disk_data
    }

def get_top_processes():
    """
    Retorna os 10 processos que mais consomem recursos
    """
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            # Coleta informações do processo
            process_info = proc.info
            process_info['memory_mb'] = proc.memory_info().rss / (1024 * 1024)  # Converter para MB
            
            # Calcula uma pontuação combinada (50% CPU, 50% RAM)
            process_info['score'] = (process_info['cpu_percent'] + process_info['memory_percent']) / 2
            
            processes.append(process_info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # Ordena por score e pega os top 10
    top_processes = sorted(processes, key=lambda x: x['score'], reverse=True)[:10]
    
    # Formata os dados para exibição
    formatted_processes = []
    for proc in top_processes:
        formatted_processes.append({
            'pid': proc['pid'],
            'name': proc['name'],
            'cpu_percent': f"{proc['cpu_percent']:.1f}%",
            'memory_percent': f"{proc['memory_percent']:.1f}%",
            'memory_mb': f"{proc['memory_mb']:.1f} MB",
            'score': f"{proc['score']:.1f}"
        })
    
    return formatted_processes

def format_version(version):
    """
    Formata a versão do sistema de forma mais amigável
    """
    # Se for uma versão do kernel Linux
    if "SMP" in version:
        try:
            # Remove o prefixo "#1 SMP PREEMPT_DYNAMIC"
            cleaned = version.split("SMP PREEMPT_DYNAMIC")[1].strip()
            # Converte para um objeto datetime
            date_obj = datetime.strptime(cleaned, '%a %b %d %H:%M:%S %Z %Y')
            # Formata para uma data mais amigável
            formatted_date = date_obj.strftime('%d/%m/%Y')
            return f"Kernel Linux (compilado em {formatted_date})"
        except Exception as e:
            # Se houver qualquer erro na formatação, retorna uma versão simplificada
            return "Kernel Linux"
    
    return version

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/events')
def events():
    def generate():
        while True:
            # Obtém os IPs
            internal_ip, external_ip = get_ip_addresses()
            
            # Coleta as informações do sistema
            info = {
                'system': {
                    'os': platform.system().lower(),
                    'distro': get_distro_info(),
                    'desktop': get_desktop_environment(),
                    'kernel': platform.release(),
                    'architecture': get_architecture(),
                    'hostname': platform.node(),
                    'internal_ip': internal_ip,
                    'external_ip': external_ip
                },
                'cpu': {
                    'brand': platform.processor(),
                    'cores_physical': psutil.cpu_count(logical=False),
                    'cores_total': psutil.cpu_count(logical=True),
                    'freq_current': f"{psutil.cpu_freq().current:.2f}MHz" if psutil.cpu_freq() else "N/A",
                    'freq_max': f"{psutil.cpu_freq().max:.2f}MHz" if psutil.cpu_freq() else "N/A",
                    'usage_percent': psutil.cpu_percent(interval=1)
                },
                'memory': {
                    'total': get_size(psutil.virtual_memory().total),
                    'available': get_size(psutil.virtual_memory().available),
                    'used': get_size(psutil.virtual_memory().used),
                    'percent': psutil.virtual_memory().percent
                },
                'disk': {
                    'total': get_size(psutil.disk_usage('/').total),
                    'used': get_size(psutil.disk_usage('/').used),
                    'free': get_size(psutil.disk_usage('/').free),
                    'percent': psutil.disk_usage('/').percent
                },
                'processes': get_top_processes(),
                'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Envia os dados como evento SSE
            data = f"data: {json.dumps(info)}\n\n"
            yield data
            
            # Aguarda 2 segundos antes da próxima atualização
            time.sleep(2)

    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
