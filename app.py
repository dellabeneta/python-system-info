from flask import Flask, render_template
import psutil
import platform
import cpuinfo
import os
from datetime import datetime

app = Flask(__name__)

def get_size(bytes):
    """
    Converte bytes para formato legível (KB, MB, GB)
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0

def get_linux_distribution():
    """
    Obtém informações detalhadas da distribuição Linux
    """
    try:
        with open('/etc/os-release') as f:
            os_info = {}
            for line in f:
                if '=' in line:
                    key, value = line.rstrip().split('=', 1)
                    os_info[key] = value.strip('"')
        return f"{os_info.get('PRETTY_NAME', 'Linux')}"
    except:
        return platform.version()

def get_system_info():
    # Informações do Sistema Operacional
    system_info = {
        'os': platform.system(),
        'os_version': get_linux_distribution() if platform.system() == 'Linux' else platform.version(),
        'os_release': platform.release(),
        'architecture': platform.machine(),
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

@app.route('/')
def index():
    system_info = get_system_info()
    return render_template('index.html', info=system_info, 
                         current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
