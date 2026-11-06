"""Bounded HTTP/SSE adapter. Use a TLS reverse proxy for hosted staging."""
import json
import os
from pathlib import Path
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.config import load_clients, origin
from core.engine import conversation, references, LlmError
from backend.sessions import Sessions


class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class ApiServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, address, clients, model_url, model_key, model='auto:reliable',
                 timeout=30, ttl=1800, maximum=100, workers=4, engine_factory=None):
        self.clients = clients
        self.sessions = Sessions(ttl, maximum)
        self.timeout_seconds = timeout
        self.engine_factory = engine_factory or (lambda client: conversation(client, model_url, model_key, model))
        self.slots = threading.BoundedSemaphore(workers)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = 'EchoWeb'

    def setup(self):
        super().setup()
        self.connection.settimeout(10)
        self.allowed_origin = None

    def _headers(self, status, content_type, length=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Vary', 'Origin')
        if self.allowed_origin:
            self.send_header('Access-Control-Allow-Origin', self.allowed_origin)
        if length is not None:
            self.send_header('Content-Length', str(length))

    def _json(self, status, data):
        body = json.dumps(data).encode('utf-8')
        self._headers(status, 'application/json; charset=utf-8', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _route(self):
        path = urlsplit(self.path)
        match = re.fullmatch(r'/v1/sites/([a-z][a-z0-9-]{1,62})/(config|sessions|messages|sessions/current)', path.path)
        if not match or path.query:
            raise ApiError(404, 'Endpoint not found.')
        site, action = match.groups()
        client = self.server.clients.get(site)
        if client is None:
            raise ApiError(404, 'Site not found.')
        try:
            supplied_origin = self.headers.get('Origin', '')
            if not supplied_origin and self.command == 'GET':
                referer = urlsplit(self.headers.get('Referer', ''))
                supplied_origin = f'{referer.scheme}://{referer.netloc}'
            caller = origin(supplied_origin)
        except ValueError:
            raise ApiError(403, 'An approved website origin is required.') from None
        if caller not in client['allowed_origins']:
            raise ApiError(403, 'This website origin is not enabled.')
        self.allowed_origin = caller
        return site, action, client

    def _body(self):
        if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            raise ApiError(415, 'Use application/json.')
        if self.headers.get('Transfer-Encoding'):
            raise ApiError(400, 'Chunked request bodies are unsupported.')
        try:
            length = int(self.headers.get('Content-Length', ''))
        except ValueError:
            raise ApiError(411, 'Content-Length is required.') from None
        if not 0 < length <= 16384:
            raise ApiError(413, 'Request body exceeds the limit.')
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ApiError(400, 'Incomplete request body.')
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ApiError(400, 'Invalid JSON.') from None
        if not isinstance(body, dict):
            raise ApiError(400, 'A JSON object is required.')
        return body

    def _session(self, site):
        header = self.headers.get('Authorization', '')
        if not re.fullmatch(r'Bearer [A-Za-z0-9_-]{32,128}', header):
            raise ApiError(401, 'A conversation session token is required.')
        token = header[7:]
        try:
            return token, self.server.sessions.acquire(token, site, self.allowed_origin)
        except PermissionError as error:
            raise ApiError(401, str(error)) from None
        except BlockingIOError as error:
            raise ApiError(409, str(error)) from None

    def do_OPTIONS(self):
        try:
            self._route()
            self._headers(204, 'application/json', 0)
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
            self.end_headers()
        except ApiError as error:
            self._json(error.status, {'error': error.message})

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/health':
            return self._json(200, {'status': 'ok'})
        if path == '/ready':
            if not self.server.clients:
                return self._json(503, {'status': 'unavailable'})
            return self._json(200, {'status': 'ready'})
        if path in ('/widget.js', '/demo', '/demo/'):
            file = ROOT / 'widget' / ('widget.js' if path == '/widget.js' else 'demo.html')
            body = file.read_bytes()
            kind = 'text/javascript' if path == '/widget.js' else 'text/html'
            self._headers(200, kind + '; charset=utf-8', len(body))
            self.end_headers()
            self.wfile.write(body)
            return
        try:
            site, action, client = self._route()
            if action != 'config':
                raise ApiError(405, 'Method not allowed.')
            self._json(200, {'site_id': site, 'branding': client['branding'],
                             'enabled_capabilities': client['enabled_capabilities']})
        except ApiError as error:
            self._json(error.status, {'error': error.message})

    def do_POST(self):
        try:
            site, action, client = self._route()
            if 'chat' not in client['enabled_capabilities']:
                raise ApiError(403, 'Chat is disabled for this site.')
            if action not in ('sessions', 'messages'):
                raise ApiError(405, 'Method not allowed.')
            if not self.server.sessions.rate_allowed(self.client_address[0]):
                raise ApiError(429, 'Request limit reached. Wait a minute before trying again.')
            body = self._body()
            if action == 'sessions':
                if body:
                    raise ApiError(400, 'Session creation expects an empty object.')
                token = self.server.sessions.create(site, self.allowed_origin, lambda: self.server.engine_factory(client))
                return self._json(201, {'session_token': token, 'expires_in': self.server.sessions.ttl})
            if set(body) != {'message'} or not isinstance(body['message'], str) or not 1 <= len(body['message'].strip()) <= 4000:
                raise ApiError(400, 'Provide only a message with 1–4,000 characters.')
            _, session = self._session(site)
        except ApiError as error:
            return self._json(error.status, {'error': error.message})
        except OverflowError as error:
            return self._json(503, {'error': str(error)})
        try:
            self._stream(session, client, body['message'].strip())
        finally:
            session.busy.release()

    def _event(self, kind, data):
        message = f'event: {kind}\ndata: {json.dumps(data)}\n\n'.encode('utf-8')
        self.wfile.write(message)
        self.wfile.flush()

    def _stream(self, session, client, text):
        source = None
        try:
            self._headers(200, 'text/event-stream; charset=utf-8')
            self.send_header('X-Accel-Buffering', 'no')
            self.end_headers()
            context, sources = references(client, text)
            source = session.engine.stream(text, context=context, timeout=self.server.timeout_seconds)
            for piece in source:
                self._event('delta', {'text': piece})
            self._event('done', {'references': sources})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except (LlmError, ValueError, OSError):
            try:
                self._event('error', {'message': 'The AI service could not complete this reply. Please try again.'})
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
        finally:
            if source is not None:
                source.close()

    def do_DELETE(self):
        try:
            site, action, _ = self._route()
            if action != 'sessions/current':
                raise ApiError(405, 'Method not allowed.')
            token, session = self._session(site)
            try:
                self.server.sessions.delete(token, session)
            finally:
                session.busy.release()
            self._json(200, {'deleted': True})
        except ApiError as error:
            self._json(error.status, {'error': error.message})


def main():
    env_file = ROOT / '.env'
    if env_file.is_file():
        for line in env_file.read_text('utf-8-sig').splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    key = os.environ.get('ECHO_MODEL_API_KEY', '')
    if not key or key == 'replace-with-your-server-side-key':
        raise SystemExit('Configure ECHO_MODEL_API_KEY on the backend before starting.')
    def number(name, default, low, high):
        value = int(os.environ.get(name, default))
        if not low <= value <= high:
            raise ValueError(f'{name} is outside its allowed range.')
        return value
    config = Path(os.environ.get('ECHO_CLIENTS_FILE', 'clients/example.json'))
    clients = load_clients(config if config.is_absolute() else ROOT / config)
    conversation(next(iter(clients.values())), os.environ.get('ECHO_MODEL_BASE_URL', 'http://127.0.0.1:31415/v1'),
                 key, os.environ.get('ECHO_MODEL', 'auto:reliable'))
    server = ApiServer((os.environ.get('ECHO_HOST', '127.0.0.1'), number('ECHO_PORT', 8765, 1, 65535)),
                       clients, os.environ.get('ECHO_MODEL_BASE_URL', 'http://127.0.0.1:31415/v1'), key,
                       os.environ.get('ECHO_MODEL', 'auto:reliable'), number('ECHO_REQUEST_TIMEOUT', 30, 1, 60),
                       number('ECHO_SESSION_TTL', 1800, 60, 86400), number('ECHO_MAX_SESSIONS', 100, 1, 500),
                       number('ECHO_MAX_REQUESTS', 4, 1, 16))
    print(f'ECHO web API listening on {server.server_address[0]}:{server.server_address[1]}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
