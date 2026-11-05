"""Local browser-test fixture using the real ECHO model client against a fake provider."""
import json
from pathlib import Path
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.server import ApiServer
from core.config import load_clients


class Provider(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        assert body['stream'] is True
        assert self.headers['Authorization'] == 'Bearer fixture-server-key'
        messages = body['messages']
        text = messages[-1]['content']
        if text == 'follow-up':
            users = [m['content'] for m in messages[:-1] if m['role'] == 'user']
            reply = 'Previous question: ' + (users[-1] if users else 'none')
        elif 'hours' in text.lower():
            assert 'Monday to Friday' in messages[0]['content']
            reply = 'Open Monday to Friday, 9 am to 5 pm.'
        else:
            reply = 'Reply: ' + text
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        if text == 'fail':
            self.wfile.write(b'data: {"error":"fixture-provider-private-error"}\n\n')
            self.wfile.flush()
            return
        for part in (reply[:8], reply[8:]):
            self.wfile.write(('data: ' + json.dumps({'choices': [{'delta': {'content': part}}]}) + '\n\n').encode())
            self.wfile.flush()
            time.sleep(0.25)
        self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()


if __name__ == '__main__':
    provider = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    clients = load_clients(ROOT / 'clients/example.json')
    api = ApiServer(('127.0.0.1', 0), clients,
                    f'http://127.0.0.1:{provider.server_port}/v1', 'fixture-server-key')
    clients['demo']['allowed_origins'] = (f'http://127.0.0.1:{api.server_port}',)
    threading.Thread(target=api.serve_forever, daemon=True).start()
    print(json.dumps({'url': f'http://127.0.0.1:{api.server_port}'}), flush=True)
    try:
        sys.stdin.read()
    finally:
        api.shutdown()
        provider.shutdown()
        api.server_close()
        provider.server_close()
