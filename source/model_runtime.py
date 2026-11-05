import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from app_paths import APP_ROOT, DATA_ROOT, RUNTIME_ROOT


MODEL = 'qwen3-embedding:0.6b'
PORT = int(os.environ.get('SEARCH_AGENT_OLLAMA_PORT', '11434'))
ENDPOINT = f'http://127.0.0.1:{PORT}'
PROJECT = APP_ROOT
START_LOCK = threading.Lock()
OWNED_SERVERS = []


class LocalEmbedder:
    def request(self, route, payload=None, timeout=180):
        data = None if payload is None else json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(ENDPOINT + route, data=data, headers={'Content-Type': 'application/json'})
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode('utf-8', errors='replace')[:500]
            raise RuntimeError(f'Yerel model yanıtı: {detail}') from error
        except (OSError, ValueError) as error:
            raise RuntimeError('Yerel model servisine erişilemiyor. Ollama kurulumunu kontrol edin.') from error

    def ensure_ready(self):
        with START_LOCK:
            try:
                tags = self.request('/api/tags', timeout=2)
            except RuntimeError:
                executable = RUNTIME_ROOT / 'ollama' / 'ollama.exe'
                if not executable.is_file():
                    raise RuntimeError('Projenin yerel model servisi bulunamadı. Ollama kurulumu gerekli.')
                environment = os.environ.copy()
                environment['OLLAMA_HOST'] = f'127.0.0.1:{PORT}'
                environment['OLLAMA_MODELS'] = str(RUNTIME_ROOT / 'models')
                environment['OLLAMA_NO_CLOUD'] = '1'
                log_path = DATA_ROOT / 'logs' / 'ollama-server.log'
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with log_path.open('ab') as log:
                    server = subprocess.Popen([str(executable), 'serve'], cwd=executable.parent, env=environment,
                                              stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    OWNED_SERVERS.append(server)
                for attempt in range(40):
                    time.sleep(0.5)
                    try:
                        tags = self.request('/api/tags', timeout=2)
                        break
                    except RuntimeError:
                        continue
                else:
                    raise RuntimeError('Yerel model servisi başlatılamadı. logs/ollama-server.log dosyasını kontrol edin.')
        for model in tags.get('models', []):
            if model.get('name') == MODEL or model.get('model') == MODEL:
                return model['digest']
        raise RuntimeError('Qwen3-Embedding-0.6B henüz indirilmemiş. Yerel model kurulumunu tamamlayın.')

    def embed(self, texts):
        result = self.request('/api/embed', {
            'model': MODEL, 'input': texts, 'truncate': False,
            'keep_alive': os.environ.get('SEARCH_AGENT_KEEP_ALIVE', '30m'), 'options': {'num_ctx': 4096},
        })
        vectors = result.get('embeddings', [])
        if len(vectors) != len(texts):
            raise RuntimeError('Model beklenen sayıda metin vektörü döndürmedi.')
        return vectors


def stop_test_servers():
    for server in OWNED_SERVERS:
        if server.poll() is None:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(server.pid), '/T', '/F'], capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                server.terminate()
    OWNED_SERVERS.clear()
