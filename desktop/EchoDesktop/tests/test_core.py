import json
import tempfile
import unittest
from pathlib import Path

from echo_desktop import core
from echo_desktop.core import Action


class PersonaTests(unittest.TestCase):
    def test_shared_catalog_matches_phone(self):
        personas = core.load_personas()
        self.assertEqual(["echo", "grind", "chill", "sage", "lingo"], [p.id for p in personas])
        self.assertIn("Tamil", next(p for p in personas if p.id == "lingo").system_prompt("Tamil"))
        self.assertEqual("grind", core.find_persona(personas, "focus mode").id)
        self.assertIsNone(core.find_persona(personas, "pirate"))

    def test_bad_persona_values_are_rejected_or_clamped(self):
        self.assertIsNone(core.parse_persona({"id": "X!", "name": "x", "prompt": "p"}))
        p = core.parse_persona({"id": "ok", "name": "Ok", "prompt": "Be nice.", "speechRate": 9, "geminiVoice": "../x", "color": "red"})
        self.assertEqual((1.15, "Aoede", "#42D9FF"), (p.speech_rate, p.gemini_voice, p.color))

    def test_missing_catalog_falls_back(self):
        self.assertEqual("echo", core.load_personas(Path(tempfile.gettempdir()) / "nope.json")[0].id)


class CommandTests(unittest.TestCase):
    aliases = frozenset({"grind", "focus", "chill", "casual", "sage", "echo", "lingo"})

    def action(self, text):
        reply = core.parse_command(text, self.aliases)
        self.assertIsNotNone(reply, text)
        self.assertEqual("action", reply.type, f"{text} -> {reply}")
        return reply.action

    def test_controls(self):
        self.assertEqual(Action("volume", {"change": "up"}), self.action("volume up"))
        self.assertEqual(Action("volume", {"change": "set", "percent": 30}), self.action("set volume to 30%"))
        self.assertEqual(Action("media", {"command": "next"}), self.action("skip song"))
        self.assertEqual(Action("lock", {}), self.action("Lock my PC"))
        self.assertEqual(Action("open_app", {"name": "Visual Studio Code"}), self.action("open Visual Studio Code"))
        self.assertEqual(Action("open_url", {"url": "https://Example.com/A"}), self.action("open https://Example.com/A"))
        self.assertEqual("rejected", core.parse_command("open https://").type)
        self.assertEqual(Action("web_search", {"engine": "youtube", "query": "lofi"}), self.action("play lofi on YouTube"))

    def test_timers(self):
        self.assertEqual(Action("set_timer", {"seconds": 600, "label": None}), self.action("set a timer for 10 minutes"))
        self.assertEqual(Action("set_timer", {"seconds": 1200, "label": "stretch"}), self.action("remind me in 20 minutes to stretch"))
        self.assertEqual(Action("set_timer", {"seconds": 300, "label": "check the oven"}), self.action("remind me to check the oven in 5 minutes"))
        self.assertEqual("rejected", core.parse_command("set a timer for pizza").type)

    def test_memory_persona_screen(self):
        self.assertEqual(Action("remember", {"fact": "my sister is Priya"}), self.action("Remember that my sister is Priya"))
        self.assertEqual(Action("forget", {"phrase": "my sister"}), self.action("forget about my sister"))
        self.assertEqual(Action("switch_persona", {"name": "grind"}), self.action("grind mode"))
        self.assertEqual(Action("switch_persona", {"name": "casual"}), self.action("be casual"))
        self.assertEqual(Action("set_translator", {"language": "Spanish"}), self.action("translate to spanish"))
        self.assertEqual("screen_question", self.action("What's on my screen?").kind)
        self.assertEqual("clipboard_question", self.action("summarize my clipboard").kind)
        self.assertIsNone(core.parse_command("be careful", self.aliases))
        self.assertIsNone(core.parse_command("what's the capital of France?", self.aliases))
        self.assertEqual("stop", self.action("Stop.").kind)


class ModelReplyTests(unittest.TestCase):
    def test_speech_and_actions(self):
        self.assertEqual(core.Reply("speech", "Hello"), core.parse_model_reply("Hello"))
        reply = core.parse_model_reply('{"action":"open_app","args":{"name":"Spotify"},"say":"On it"}')
        self.assertEqual((Action("open_app", {"name": "Spotify"}), "On it"), (reply.action, reply.text))

    def test_rejections(self):
        for bad in ('{"action":"run_shell","args":{"cmd":"del *"}}',
                    '{"action":"open_url","args":{"url":"file:///C:/Windows"}}',
                    '{"action":"volume","args":{"change":"set","percent":101}}',
                    '{"action":"volume","args":{"change":"set","percent":true}}',
                    '{"action":"set_timer","args":{"seconds":0}}',
                    '{"action":"screen_question","args":{}}',
                    '{"action":"open_app","args":{"name":null}}'):
            self.assertEqual("rejected", core.parse_model_reply(bad).type, bad)

    def test_fenced_json(self):
        reply = core.parse_model_reply('```json\n{"action":"lock","args":{}}\n```')
        self.assertEqual(Action("lock", {}), reply.action)


class MemoryRuleTests(unittest.TestCase):
    def item(self, i, text, source="user"):
        return {"id": i, "text": text, "created": 0, "used": 0, "uses": 0, "source": source}

    def test_sensitive(self):
        self.assertTrue(core.is_sensitive("my wifi password is abc"))
        self.assertTrue(core.is_sensitive("4111 1111 1111 1111"))
        self.assertFalse(core.is_sensitive("my sister is Priya"))

    def test_rank_and_forget(self):
        items = [self.item("1", "my sister is Priya"), self.item("2", "I like filter coffee")]
        self.assertEqual("1", core.rank_memories(items, "gift ideas for my sister", now=0, limit=1)[0]["id"])
        self.assertEqual(["1"], [i["id"] for i in core.forget_matches(items, "my sister")])
        self.assertEqual([], core.forget_matches(items, "pizza"))
        self.assertTrue(core.is_duplicate(items, "My sister is Priya."))


class StorageTests(unittest.TestCase):
    def test_dpapi_round_trip_and_memory_store(self):
        from echo_desktop import storage
        self.assertEqual(b"secret", storage.unprotect(storage.protect(b"secret")))
        with tempfile.TemporaryDirectory() as d:
            store = storage.MemoryStore(Path(d))
            self.assertEqual("saved", store.remember("my sister is Priya", "user"))
            self.assertEqual("sensitive", store.remember("my PIN is 4821", "user"))
            self.assertEqual("duplicate", store.remember("My sister is Priya.", "user"))
            raw = (Path(d) / "memory.bin").read_bytes()
            self.assertNotIn(b"Priya", raw)                       # encrypted at rest
            self.assertEqual(1, len(storage.MemoryStore(Path(d)).all()))   # survives reload
            settings = storage.Settings(Path(d))
            settings.set_secret("llm_key", "abc123")
            self.assertNotIn(b"abc123", (Path(d) / "secrets.bin").read_bytes())
            self.assertEqual("abc123", storage.Settings(Path(d)).secret("llm_key"))
            settings["orb_size"] = 120
            self.assertEqual(120, json.loads((Path(d) / "settings.json").read_text())["orb_size"])


if __name__ == "__main__":
    unittest.main()
