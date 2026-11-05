"""Hedged AI requests: a stalled FreeLLMAPI route must not hold Echo up."""
import http.server
import json
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from echo_desktop import llm  # noqa: E402

BEHAVIOUR = {}          # model -> ("stall", seconds) | ("text", words) | ("error", status)
SEEN = []


class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        model = body["model"]
        SEEN.append(model)
        kind, arg = BEHAVIOUR.get(model, ("text", ["ok"]))
        if kind == "error":
            self.send_response(arg)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"busy"}')
            return
        if not body.get("stream"):
            out = json.dumps({"choices": [{"message": {"content": "".join(arg)}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("X-Routed-Via", f"fake/{model}")
        self.end_headers()
        try:
            if kind == "stall":
                time.sleep(arg)
                words = ["slow"]
            else:
                words = arg
            for w in words:
                self.wfile.write(b"data: " + json.dumps({"choices": [{"delta": {"content": w}}]}).encode() + b"\n\n")
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
        except OSError:                         # Echo hung up on the losing route
            pass


class HedgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        BEHAVIOUR.clear()
        SEEN.clear()
        llm._first_word_s.clear()
        self.addCleanup(setattr, llm, "hedge_delay", llm.hedge_delay)
        llm.hedge_delay = lambda: 0.3

    def test_a_stalled_route_is_beaten_by_the_next(self):
        BEHAVIOUR["auto"] = ("stall", 5)
        BEHAVIOUR["auto:fast"] = ("text", ["Hello ", "there."])
        c = llm.ChatClient(self.url)
        t = time.monotonic()
        self.assertEqual("Hello there.", "".join(c.stream([{"role": "user", "content": "hi"}])))
        self.assertLess(time.monotonic() - t, 2.0)
        self.assertEqual("fake/auto:fast", c.last_route)
        self.assertEqual(["auto", "auto:fast"], SEEN)            # the third route was never needed

    def test_a_fast_first_route_needs_no_hedge(self):
        BEHAVIOUR["auto"] = ("text", ["Quick."])
        self.assertEqual("Quick.", llm.ChatClient(self.url).complete([{"role": "user", "content": "hi"}]))
        time.sleep(0.5)
        self.assertEqual(["auto"], SEEN)

    def test_an_error_races_the_next_route_at_once(self):
        BEHAVIOUR["auto"] = ("error", 503)
        BEHAVIOUR["auto:fast"] = ("text", ["Backup."])
        llm.hedge_delay = lambda: 30                             # no waiting: the failure itself triggers the hedge
        t = time.monotonic()
        self.assertEqual("Backup.", llm.ChatClient(self.url).complete([{"role": "user", "content": "hi"}]))
        self.assertLess(time.monotonic() - t, 2.0)

    def test_every_route_failing_is_reported(self):
        for m in llm.HEDGE_ROUTES:
            BEHAVIOUR[m] = ("error", 429)
        with self.assertRaises(llm.OutOfTokens):
            llm.ChatClient(self.url).complete([{"role": "user", "content": "hi"}])

    def test_a_named_model_or_other_server_gets_one_request(self):
        BEHAVIOUR["gpt-4o-mini"] = ("text", ["Single."])
        self.assertEqual("Single.", llm.ChatClient(self.url, model="gpt-4o-mini").complete([{"role": "user", "content": "hi"}]))
        self.assertEqual(["gpt-4o-mini"], SEEN)

    def test_the_deadline_follows_recent_speed(self):
        llm.hedge_delay = HedgeTest.real_delay
        self.assertEqual(2.5, llm.hedge_delay())                 # nothing measured yet
        llm._first_word_s.extend([0.8, 1.0, 1.2])
        self.assertEqual(2.0, llm.hedge_delay())                 # fast lately: never below 2 s
        llm._first_word_s.extend([9, 9, 9, 9, 9])
        self.assertEqual(5.0, llm.hedge_delay())                 # slow lately: never above 5 s


HedgeTest.real_delay = staticmethod(llm.hedge_delay)

if __name__ == "__main__":
    unittest.main()
