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

# Cache para informações estáticas
_static_info = None
_process = None

def get_static_system_info():
    """
    Retorna informações do sistema que não mudam frequentemente
    """
    global _static_info
    if _static_info is None:
        system_info = get_system_info()
        internal_ip, external_ip = get_ip_addresses()
        _static_info = {
            'os': system_info['system']['os'],
            'distro': system_info['system']['os_version'],
            'kernel': system_info['system']['os_release'],
            'architecture': system_info['system']['architecture'],
            'hostname': system_info['system']['hostname'],
            'desktop': get_desktop_environment(),
            'internal_ip': internal_ip,
            'external_ip': external_ip
        }
    return _static_info

def get_dynamic_metrics():
    """
    Retorna métricas que mudam frequentemente
    """
    system_info = get_system_info()
    return {
        'cpu': system_info['cpu'],
        'memory': system_info['memory'],
        'disk': system_info['disk'],
        'processes': get_top_processes()
    }

def get_app_metrics():
    """
    Retorna o consumo de CPU e RAM da própria aplicação
    """
    global _process
    
    # Inicializa o processo se ainda não existe
    if _process is None:
        _process = psutil.Process(os.getpid())
        # Primeira chamada para inicializar a medição de CPU
        _process.cpu_percent()
        
    # Obtém as métricas atuais
    try:
        cpu_percent = _process.cpu_percent()
        memory_info = _process.memory_info()
        return {
            'cpu': f"{cpu_percent:.1f}%",
            'memory': get_size(memory_info.rss)
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
        # Em caso de erro, reinicializa o processo
        _process = None
        return {
            'cpu': "0.0%",
            'memory': "0 B"
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/events')
def events():
    def generate():
        # Obtém informações estáticas uma única vez
        static_info = get_static_system_info()
        
        while True:
            # Obtém apenas métricas dinâmicas
            dynamic_metrics = get_dynamic_metrics()
            
            # Obtém métricas da própria aplicação
            app_metrics = get_app_metrics()
            
            data = {
                'current_time': datetime.now().strftime('%H:%M:%S'),
                'system': static_info,
                'cpu': dynamic_metrics['cpu'],
                'memory': dynamic_metrics['memory'],
                'disk': dynamic_metrics['disk'],
                'processes': dynamic_metrics['processes'],
                'app_metrics': app_metrics
            }
            
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(3)  # Aumenta o intervalo para 3 segundos
    
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
