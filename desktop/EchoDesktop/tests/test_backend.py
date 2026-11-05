import threading
import unittest
from unittest.mock import Mock, patch

from echo_desktop.backend import Backend
from echo_desktop.llm import ChatClient, LlmError


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.history = []
        self.backend = Backend(self.client)

    def test_successful_turns_preserve_followup_context(self):
        self.client.ask.side_effect = ['Your project is Echo.', 'Echo.']
        self.backend.ask('My project is Echo.')
        self.assertEqual('Echo.', self.backend.ask('What is its name?'))
        self.assertEqual(['user', 'assistant', 'user', 'assistant'], [m['role'] for m in self.client.history])
        self.assertEqual('My project is Echo.', self.client.history[0]['content'])
        self.assertFalse(self.client.ask.call_args.kwargs['remember'])

    def test_failed_turn_preserves_history_and_unlocks(self):
        self.client.history.append({'role': 'user', 'content': 'previous'})
        self.client.ask.side_effect = [LlmError('unavailable'), 'Recovered']
        with self.assertRaises(LlmError):
            self.backend.ask('Fail')
        self.assertEqual(1, len(self.client.history))
        self.assertEqual('Recovered', self.backend.ask('Retry'))

    def test_empty_reply_is_not_saved(self):
        self.client.ask.return_value = '  '
        with self.assertRaisesRegex(LlmError, 'empty reply'):
            self.backend.ask('Hello')
        self.assertEqual([], self.client.history)

    def test_busy_session_rejects_duplicate_work_and_clear(self):
        entered, finish = threading.Event(), threading.Event()
        def answer(*args, **kwargs):
            entered.set()
            finish.wait(2)
            return 'Done'
        self.client.ask.side_effect = answer
        worker = threading.Thread(target=lambda: self.backend.ask('First'))
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            with self.assertRaisesRegex(LlmError, 'already in progress'):
                self.backend.ask('Duplicate')
            with self.assertRaisesRegex(LlmError, 'active reply'):
                self.backend.clear()
            self.assertEqual(1, self.client.ask.call_count)
        finally:
            finish.set()
            worker.join(2)

    def test_history_stays_bounded(self):
        self.client.ask.return_value = 'OK'
        for index in range(20):
            self.backend.ask(str(index))
        self.assertEqual(16, len(self.client.history))
        self.assertEqual('12', self.client.history[0]['content'])

    def test_invalid_input_never_calls_provider(self):
        for text in ('', '  ', 'x' * 4001):
            with self.assertRaises(ValueError):
                self.backend.ask(text)
        for timeout in (0, -1, 61):
            with self.assertRaises(ValueError):
                self.backend.ask('Hello', timeout)
        self.client.ask.assert_not_called()

    def test_oversized_provider_response_is_rejected(self):
        client = ChatClient('http://127.0.0.1:31415/v1', model='auto:reliable')
        with patch('urllib.request.urlopen') as open_url:
            response = open_url.return_value.__enter__.return_value
            response.headers = {'Content-Type': 'application/json'}
            response.read.return_value = b'x' * (2 * 1024 * 1024 + 1)
            with self.assertRaisesRegex(LlmError, '2 MB'):
                client.complete([{'role': 'user', 'content': 'Hello'}])
            response.read.assert_called_once_with(2 * 1024 * 1024 + 1)
