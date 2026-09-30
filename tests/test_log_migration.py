import json
import tempfile
import unittest
from pathlib import Path

from app.logging_config import migrate_json_log


class LogMigrationTests(unittest.TestCase):
    def test_moves_legacy_logs_and_merges_existing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "logs.json"
            destination = root / "logs" / "interactions.json"
            destination.parent.mkdir()
            source.write_text(json.dumps([{"id": 1}]), encoding="utf-8")
            destination.write_text(json.dumps([{"id": 2}]), encoding="utf-8")

            migrate_json_log(source, destination, [])

            self.assertFalse(source.exists())
            self.assertEqual(json.loads(destination.read_text(encoding="utf-8")),
                             [{"id": 1}, {"id": 2}])

    def test_moves_legacy_conversation_logs_into_logs_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "conversation_history.json"
            destination = root / "logs" / "conversation_history.json"
            destination.parent.mkdir()
            source.write_text(json.dumps({"__ai_logs__": [{"id": 1}]}), encoding="utf-8")

            migrate_json_log(source, destination, {})

            self.assertFalse(source.exists())
            self.assertEqual(json.loads(destination.read_text(encoding="utf-8")),
                             {"__ai_logs__": [{"id": 1}]})
