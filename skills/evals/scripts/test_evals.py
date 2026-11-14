import contextlib
import json
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evals


class CliTests(unittest.TestCase):
    @patch("evals.api", return_value={"items": [{"id": "skl_1"}]})
    def test_discovery_encodes_query_and_uses_no_device_credential(self, api):
        with patch.dict(os.environ, {"EVALS_CLI_ORIGIN": "https://evals.ag"}):
            result = evals.search("skills", "visual & design", 2)
        api.assert_called_once_with("https://evals.ag", "/skills/search?q=visual+%26+design&limit=2")
        self.assertEqual(result["items"][0]["id"], "skl_1")

    @patch("evals.api")
    def test_untrusted_state_and_origin_never_send_a_credential(self, api):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"EVALS_CLI_HOME": directory, "EVALS_CLI_ORIGIN": "https://other.example"},
        ):
            path = Path(directory) / "device.json"
            evals.save_state(path, {"origin": "https://evals.ag", "device_id": "device", "token": "evcli_" + "a" * 43})
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(evals.main(["whoami"]), 1)
        api.assert_not_called()

    def test_terminal_review_escapes_control_sequences(self):
        self.assertEqual(evals.terminal_text("a\x1b]52;input\nb"), "a\\x1b]52;input\nb")

    @patch("evals.api")
    def test_blank_and_over_limit_searches_stay_local(self, api):
        for query, limit in ((" ", 5), ("q", 31), ("q" * 251, 5)):
            with self.assertRaises(ValueError):
                evals.search("skills", query, limit)
        api.assert_not_called()


def _write_jsonl(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\nnot json\n", encoding="utf-8")


class LocalCommandTests(unittest.TestCase):
    def test_sessions_keep_every_typed_message_and_count_usage_once(self):
        long_brief = "Rebrand a coffee shop. " * 2000
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claude = root / "claude" / "-Users-me-proj" / "abc.jsonl"
            _write_jsonl(claude, [
                {"type": "custom-title", "customTitle": "Coffee rebrand"},
                {"type": "user", "timestamp": "2026-11-14T01:00:00Z", "cwd": "/proj", "promptSource": "typed",
                 "message": {"role": "user", "content": long_brief}},
                {"type": "assistant", "timestamp": "2026-11-14T01:00:05Z", "message": {
                    "id": "msg_1", "model": "claude-opus-5-5", "usage": {"input_tokens": 10, "output_tokens": 5},
                    "content": [{"type": "thinking"}]}},
                {"type": "assistant", "timestamp": "2026-11-14T01:00:06Z", "message": {
                    "id": "msg_1", "model": "claude-opus-5-5", "usage": {"input_tokens": 10, "output_tokens": 5},
                    "content": [{"type": "tool_use", "name": "Write", "input": {"file_path": "/proj/logo.svg"}}]}},
                {"type": "user", "timestamp": "2026-11-14T01:00:07Z",
                 "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}},
            ])
            _write_jsonl(claude.parent / "abc" / "subagents" / "agent-1.jsonl", [
                {"type": "assistant", "message": {"id": "s1", "model": "claude-haiku-5-5", "usage": {"output_tokens": 7}}},
            ])
            codex = root / "codex" / "2026" / "11" / "14" / "rollout-1.jsonl"
            _write_jsonl(codex, [
                {"type": "session_meta", "timestamp": "2026-11-14T02:00:00Z", "payload": {"id": "cx1", "cwd": "/deck"}},
                {"type": "turn_context", "payload": {"model": "gpt-6.1-sol", "effort": "high"}},
                {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "# AGENTS.md"}]}},
                {"type": "event_msg", "timestamp": "2026-11-14T02:00:01Z", "payload": {"type": "item_completed", "item": {
                    "type": "UserMessage", "content": [{"type": "text", "text": "Make a sales deck"}]}}},
                {"type": "event_msg", "payload": {"type": "item_completed", "item": {"type": "McpToolCall", "server": "higgsfield", "tool": "generate_image"}}},
                {"type": "token_usage_record", "payload": {"thread_token_usage": {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7}}},
            ])
            out = root / "out"
            summary = evals.sessions(365, out, root / "claude", root / "codex")
            self.assertEqual(summary["sessions"], 2)
            records = {}
            for path in out.glob("*-*.json"):
                record = json.loads(path.read_text())
                records[record["tool"]] = record
            claude_record = records["claude-code"]
            self.assertEqual(claude_record["messages"][0]["text"], long_brief)
            self.assertEqual(len(claude_record["messages"]), 1)
            self.assertEqual(claude_record["usage"], {"input_tokens": 10, "output_tokens": 5})
            self.assertEqual(claude_record["subagent_usage"], {"claude-haiku-5-5": {"output_tokens": 7}})
            self.assertEqual(claude_record["files_written"], ["/proj/logo.svg"])
            self.assertEqual(claude_record["title"], "Coffee rebrand")
            self.assertEqual(claude_record["unparsed_lines"], 1)
            codex_record = records["codex"]
            self.assertEqual([m["text"] for m in codex_record["messages"]], ["Make a sales deck"])
            self.assertEqual(codex_record["tool_calls"], {"mcp:higgsfield:generate_image": 1})
            self.assertEqual(codex_record["usage"]["total_tokens"], 7)
            self.assertEqual(out.joinpath("index.json").stat().st_mode & 0o777, 0o600)

    def test_tally_is_arithmetic_and_reports_missing_judges(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {"setups": [
                {"setup_index": 0, "label": "Judge 1", "dir": "setup-1"},
                {"setup_index": 1, "label": "Judge 2", "dir": "setup-2"},
                {"setup_index": 2, "label": "Judge 3", "dir": "setup-3"},
            ]}
            (root / "manifest.json").write_text(json.dumps(manifest))
            for name, verdict in (
                ("setup-1", {"scores": {"A": {"look": 8, "fit": 6}, "B": {"look": 4, "fit": 4}}, "winner": "A", "reasons": {"A": "cleaner"}}),
                ("setup-2", {"scores": {"A": {"look": 6, "fit": 6}, "B": {"look": 8, "fit": 8}}, "winner": "B", "reasons": {"B": "bolder"}}),
            ):
                (root / name / "work").mkdir(parents=True)
                (root / name / "work" / "verdict.json").write_text(json.dumps(verdict))
            (root / "setup-3").mkdir()
            weights = root / "weights.json"
            weights.write_text(json.dumps({"look": 75, "fit": 25}))
            key = root / "key.json"
            key.write_text(json.dumps({"A": "Opus direction", "B": "Sol direction"}))
            result = evals.tally(root, key, weights)
        self.assertEqual(result["judges_read"], 2)
        self.assertEqual(result["problems"][0]["judge"], "Judge 3")
        ranking = {row["candidate"]: row for row in result["ranking"]}
        self.assertEqual(ranking["A"]["scores"], [{"judge": "Judge 1", "score": 75.0}, {"judge": "Judge 2", "score": 60.0}])
        self.assertEqual(ranking["A"]["mean_score_0_100"], 67.5)
        self.assertEqual(ranking["B"]["mean_score_0_100"], 60.0)
        self.assertEqual(ranking["A"]["name"], "Opus direction")
        self.assertEqual(ranking["B"]["winner_reasons"], [{"judge": "Judge 2", "reason": "bolder"}])


if __name__ == "__main__":
    unittest.main()
