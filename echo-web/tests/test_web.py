import http.client
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.server import ApiServer
from backend.sessions import Sessions
from core.config import load_clients, origin
from core.engine import Backend, ChatClient, LlmError


class Model:
    def __init__(self):
        self.history = []
        self.prompts = []

    def stream(self, messages, timeout=30):
        self.prompts.append(messages)
        message = messages[-1]['content']
        if message == 'fail':
            yield 'Partial '
            raise LlmError('provider-secret-must-not-leak')
        if message == 'follow-up':
            yield self.history[0]['content'] if self.history else 'No history'
        else:
            yield 'Echo: '
            yield message

    def clear(self):
        self.history.clear()


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ApiServer(('127.0.0.1', 0), {}, 'http://127.0.0.1:1/v1', 'server-secret',
                               engine_factory=lambda client: Backend(Model()))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(2)

    def setUp(self):
        self.server.sessions = Sessions(ttl=60, maximum=10)
        self.server.clients = {}
        for site, host, content in [('alpha', 'https://alpha.example', 'ALPHA_ONLY'),
                                    ('beta', 'https://beta.example', 'BETA_ONLY')]:
            self.server.clients[site] = {'site_id': site, 'allowed_origins': (host,), 'enabled_capabilities': ['chat'],
                'branding': {'name': site, 'accent': '#167089', 'greeting': 'Hello'},
                'knowledge': [{'id': 'policy', 'title': 'Policy', 'text': content + ' delivery policy'}]}

    def request(self, method, site='alpha', action='sessions', body=None, token=None, caller='https://alpha.example'):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        headers = {'Content-Type': 'application/json'}
        if caller is not None:
            headers['Origin'] = caller
        if token is not None:
            headers['Authorization'] = 'Bearer ' + token
        data = json.dumps(body).encode() if body is not None else None
        connection.request(method, f'/v1/sites/{site}/{action}', data, headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode()
        connection.close()
        return result

    def session(self, site='alpha', caller='https://alpha.example'):
        status, _, text = self.request('POST', site, body={}, caller=caller)
        self.assertEqual(201, status)
        return json.loads(text)['session_token']

    def test_streaming_and_followup_use_existing_engine(self):
        token = self.session()
        status, headers, text = self.request('POST', action='messages', body={'message': 'Remember LIME47'}, token=token)
        self.assertEqual(200, status)
        self.assertIn('text/event-stream', headers['Content-Type'])
        self.assertIn('event: delta', text)
        self.assertIn('event: done', text)
        self.assertIn('Remember LIME47', self.request('POST', action='messages', body={'message': 'follow-up'}, token=token)[2])

    def test_client_session_and_knowledge_isolation(self):
        alpha = self.session()
        beta = self.session('beta', 'https://beta.example')
        self.assertNotEqual(alpha, beta)
        status, _, _ = self.request('POST', site='beta', action='messages', body={'message': 'policy'}, token=alpha,
                                    caller='https://beta.example')
        self.assertEqual(401, status)
        self.request('POST', action='messages', body={'message': 'delivery policy'}, token=alpha)
        engine = self.server.sessions.items[alpha].engine
        prompt = engine.client.prompts[-1][0]['content']
        self.assertIn('ALPHA_ONLY', prompt)
        self.assertNotIn('BETA_ONLY', prompt)
        self.assertEqual([], self.server.sessions.items[beta].engine.client.history)

    def test_new_visitor_has_separate_memory(self):
        first, second = self.session(), self.session()
        self.request('POST', action='messages', body={'message': 'private test'}, token=first)
        response = self.request('POST', action='messages', body={'message': 'follow-up'}, token=second)
        self.assertIn('No history', response[2])

    def test_public_site_id_is_not_a_session_credential(self):
        self.assertEqual(401, self.request('POST', action='messages', body={'message': 'Hello'}, token='alpha')[0])
        self.assertEqual(401, self.request('POST', action='messages', body={'message': 'Hello'})[0])

    def test_unapproved_and_missing_origins_are_rejected(self):
        for caller in ('https://evil.example', None, 'null', 'https://alpha.example.evil.test'):
            status, headers, _ = self.request('POST', body={}, caller=caller)
            self.assertEqual(403, status)
            self.assertNotIn('Access-Control-Allow-Origin', headers)

    def test_public_config_excludes_knowledge_and_keys(self):
        status, headers, text = self.request('GET', action='config')
        self.assertEqual(200, status)
        self.assertNotIn('ALPHA_ONLY', text)
        self.assertNotIn('server-secret', text)
        self.assertEqual('https://alpha.example', headers['Access-Control-Allow-Origin'])

    def test_preflight_is_scoped(self):
        status, headers, _ = self.request('OPTIONS')
        self.assertEqual(204, status)
        self.assertIn('Authorization', headers['Access-Control-Allow-Headers'])
        self.assertNotEqual('*', headers['Access-Control-Allow-Origin'])

    def test_arbitrary_tools_and_oversized_messages_are_rejected(self):
        token = self.session()
        for body in ({'message': 'Hello', 'tools': ['shell']}, {'message': 'x' * 4001}, {'message': []}, {'prompt': 'override'}):
            self.assertEqual(400, self.request('POST', action='messages', body=body, token=token)[0])
        self.assertEqual([], self.server.sessions.items[token].engine.client.prompts)

    def test_busy_and_reset_lifecycle(self):
        token = self.session()
        session = self.server.sessions.items[token]
        session.busy.acquire()
        try:
            self.assertEqual(409, self.request('POST', action='messages', body={'message': 'Hello'}, token=token)[0])
            self.assertEqual(409, self.request('DELETE', action='sessions/current', token=token)[0])
        finally:
            session.busy.release()
        self.assertEqual(200, self.request('DELETE', action='sessions/current', token=token)[0])
        self.assertEqual(401, self.request('POST', action='messages', body={'message': 'Hello'}, token=token)[0])

    def test_upstream_failure_is_safe_and_transactional(self):
        token = self.session()
        _, _, text = self.request('POST', action='messages', body={'message': 'fail'}, token=token)
        self.assertIn('event: error', text)
        self.assertNotIn('provider-secret', text)
        self.assertEqual([], self.server.sessions.items[token].engine.client.history)
        self.assertIn('event: done', self.request('POST', action='messages', body={'message': 'retry'}, token=token)[2])

    def test_chat_can_be_disabled(self):
        self.server.clients['alpha']['enabled_capabilities'] = []
        self.assertEqual(403, self.request('POST', body={})[0])

    def test_rate_limit(self):
        for _ in range(30):
            self.assertTrue(self.server.sessions.rate_allowed('example-ip'))
        self.assertFalse(self.server.sessions.rate_allowed('example-ip'))


class CoreTests(unittest.TestCase):
    def test_truncated_real_provider_stream_does_not_commit(self):
        client = ChatClient('http://127.0.0.1:1/v1', model='explicit')
        response = Mock(status=200)
        response.getheader.side_effect = lambda name: 'text/event-stream' if name == 'Content-Type' else ''
        response.readline.side_effect = io.BytesIO(
            b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n').readline
        connection = Mock(sock=None)
        connection.getresponse.return_value = response
        engine = Backend(client)
        with patch.object(client, '_connection', return_value=connection):
            stream = engine.stream('Hello')
            self.assertEqual('partial', next(stream))
            with self.assertRaisesRegex(LlmError, 'before completion'):
                next(stream)
        self.assertEqual([], client.history)

    def test_cancelled_stream_does_not_commit_and_releases_lock(self):
        engine = Backend(Model())
        stream = engine.stream('Hello')
        self.assertEqual('Echo: ', next(stream))
        stream.close()
        self.assertEqual([], engine.client.history)
        self.assertEqual('Echo: again', ''.join(engine.stream('again')))

    def test_expiration_origin_binding_and_capacity(self):
        now = [0]
        store = Sessions(ttl=10, maximum=1, clock=lambda: now[0])
        token = store.create('alpha', 'https://alpha.example', lambda: object())
        with self.assertRaises(PermissionError):
            store.get(token, 'alpha', 'https://other.example')
        with self.assertRaises(OverflowError):
            store.create('alpha', 'https://alpha.example', lambda: object())
        now[0] = 11
        with self.assertRaises(PermissionError):
            store.get(token, 'alpha', 'https://alpha.example')
        self.assertNotEqual(token, store.create('alpha', 'https://alpha.example', lambda: object()))

    def test_configuration_validation(self):
        clients = load_clients(ROOT / 'clients/example.json')
        self.assertIn('demo', clients)
        self.assertEqual('https://example.com', origin('https://EXAMPLE.com:443/'))
        for invalid in ('*', 'null', 'https://user@example.com', 'https://@example.com', 'https://example.com/path'):
            with self.assertRaises(ValueError):
                origin(invalid)
        data = list(clients.values())
        data[0]['enabled_capabilities'] = ['shell']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'client.json'
            path.write_text(json.dumps(data), 'utf-8')
            with self.assertRaises(ValueError):
                load_clients(path)

    def test_web_import_does_not_load_desktop_or_audio(self):
        result = subprocess.run([sys.executable, '-c',
            "import backend.server,sys; assert not any(n in sys.modules for n in "
            "('tkinter','winsound','echo_desktop.storage','echo_desktop.brain','echo_desktop.voice','echo_desktop.stt'))"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_standalone_local_wake_word_is_in_grammar(self):
        helper = ROOT.parent / 'desktop/EchoDesktop/echo_desktop/helpers/speech.ps1'
        wake = helper.read_text('utf-8').split("'wake' {", 1)[1].split("'interrupt'", 1)[0]
        self.assertIn("@('echo', 'hey echo'", wake)


if __name__ == '__main__':
    unittest.main()
