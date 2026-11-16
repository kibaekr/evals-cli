import argparse
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
                {"type": "event_msg", "timestamp": "2026-11-14T02:00:09Z", "payload": {"type": "item_completed", "item": {
                    "type": "UserMessage", "content": [{"type": "text", "text": "Make a sales deck"}]}}},
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
            self.assertEqual(codex_record["messages"][0]["repeats"], 2)
            self.assertEqual(codex_record["messages"][0]["also_at"], ["2026-11-14T02:00:09Z"])
            index = json.loads(out.joinpath("index.json").read_text())["index"]
            codex_index = next(row for row in index if row["tool"] == "codex")
            self.assertEqual((codex_index["messages_sent"], codex_index["distinct_messages"]), (2, 1))
            self.assertEqual(codex_index["first_message"]["text"], "Make a sales deck")
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


class VisibilityTests(unittest.TestCase):
    def parse(self, *extra):
        parser = argparse.ArgumentParser()
        evals.plan_args(parser)
        return parser.parse_args(list(extra))

    def test_private_and_public_shorthands_and_one_required(self):
        self.assertEqual(self.parse("--private").visibility, "private")
        self.assertEqual(self.parse("--public").visibility, "public")
        self.assertEqual(self.parse("--visibility", "public").visibility, "public")
        with contextlib.redirect_stderr(io.StringIO()):
            for extra in ((), ("--private", "--public")):
                with self.assertRaises(SystemExit):
                    self.parse(*extra)

    @patch("evals.api", side_effect=evals.ApiError(403, "This account cannot create private runs."))
    def test_private_refusal_names_the_plan_and_the_public_choice(self, api):
        args = argparse.Namespace(
            visibility="private", prompt="Brief", prompt_file=None, setup=None, model=["a", "b"], skill=None,
            input=None, attachment_id=None, suggestion=None,
        )
        with self.assertRaises(ValueError) as caught:
            evals.prepare("https://evals.ag", {"token": "t", "device_id": "d"}, args)
        self.assertIn("Plus or Pro", str(caught.exception))
        self.assertIn("--public", str(caught.exception))


class RuntimeAndDirectTests(unittest.TestCase):
    def test_native_runtime_and_a_single_direct_setup(self):
        self.assertEqual(evals.parse_setup("model=openai/gpt-6.1-sol,runtime=native")["runtime"], "native-codex")
        with self.assertRaises(ValueError):
            evals.parse_setup("model=x,runtime=fast")
        args = argparse.Namespace(
            visibility="private", prompt="Brief", prompt_file=None, setup=["model=a"], model=None, skill=None,
            input=None, attachment_id=None, suggestion=None,
        )
        self.assertEqual(len(evals.plan_body(args)["options"]), 1)
        args.setup = ["model=a"] * 9
        with self.assertRaises(ValueError):
            evals.plan_body(args)
        line = evals.option_line({"name": "GPT-6.1 Sol", "route": "codex", "runtime": "native-codex", "skill": "auto"})
        self.assertIn("native Codex", line)


class OutputsTests(unittest.TestCase):
    site = "https://evals.ag"
    run_id = "run_" + "1" * 26
    output_id = "out_" + "2" * 26
    outputs_url = site + "/outputs/" + output_id
    review_url = site + "/runs/" + run_id

    @patch("evals.api", return_value={})
    def test_start_and_results_publish_link_only_when_known(self, api):
        device = {"token": "fixture"}
        started = evals.start(self.site, device, {
            "run_id": self.run_id, "options": [{}, {}], "envelope": "signed",
            "expires_at": "2099-01-01T00:00:00Z",
        })
        self.assertEqual(started["review_url"], self.review_url)
        self.assertIsNone(started["outputs_url"])
        api.return_value = {"visibility": "public", "setups": [{"setup_index": 0, "output_id": self.output_id}]}
        with tempfile.TemporaryDirectory() as directory:
            manifest = evals.results(self.site, device, self.run_id, Path(directory))
            stored = json.loads(Path(directory, "manifest.json").read_text())
        for result in (manifest, stored):
            self.assertEqual(result["outputs_url"], self.outputs_url)
            self.assertEqual(result["review_url"], self.review_url)

    @patch("evals.credential", return_value={"token": "fixture"})
    @patch("evals.webbrowser.open_new", return_value=True)
    @patch("evals.api")
    def test_wait_only_opens_a_published_output_after_settling(self, api, browser, credential):
        cases = ((False, True, "public", self.output_id), (True, False, "public", self.output_id),
                 (True, True, "public", self.output_id), (True, True, "private", self.output_id),
                 (True, True, "public", None))
        for requested, finished, visibility, output_id in cases:
            with self.subTest(requested=requested, finished=finished, visibility=visibility, output_id=output_id):
                browser.reset_mock()
                api.return_value = {"setup_count": 2, "visibility": visibility, "attempts": [
                    {"setup_index": 0, "status": "completed", "published_output_id": output_id},
                    {"setup_index": 1, "status": "failed" if finished else "running"},
                ]}
                args = ["wait", self.run_id, "--timeout", "1"] + (["--open"] if requested else [])
                with patch("evals.origin", return_value=self.site), patch("evals.time.monotonic", side_effect=[0, 1]), contextlib.redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(evals.main(args), 0)
                result = json.loads(stdout.getvalue())
                expected_url = self.outputs_url if visibility == "public" and output_id else None
                self.assertEqual(result["outputs_url"], expected_url)
                self.assertEqual(result["review_url"], self.review_url)
                self.assertEqual(result["wait_timed_out"], not finished)
                if requested and finished and expected_url:
                    browser.assert_called_once_with(self.outputs_url)
                    self.assertTrue(result["browser_opened"])
                else:
                    browser.assert_not_called()

    @patch("evals.time.sleep")
    @patch("evals.api")
    def test_wait_allows_a_public_artifact_to_be_indexed(self, api, sleep):
        attempt = {"setup_index": 0, "status": "completed", "artifacts": ["index.html"]}
        run = {"setup_count": 1, "visibility": "public", "attempts": [attempt]}
        api.side_effect = [run, {**run, "attempts": [{**attempt, "published_output_id": self.output_id}]}]
        with patch("evals.time.monotonic", side_effect=[0, 1, 5]):
            result = evals.wait_for_run(self.site, {"token": "fixture"}, self.run_id, 10, wait_for_output=True)
        sleep.assert_called_once_with(4)
        self.assertEqual(result["outputs_url"], self.outputs_url)
        self.assertFalse(result["wait_timed_out"])

    @patch("evals.time.sleep")
    @patch("evals.api")
    def test_publication_wait_respects_timeout_without_marking_run_unfinished(self, api, sleep):
        api.return_value = {"setup_count": 1, "visibility": "public", "attempts": [
            {"setup_index": 0, "status": "completed", "artifacts": ["index.html"]},
        ]}
        with patch("evals.time.monotonic", side_effect=[0, 1]):
            result = evals.wait_for_run(self.site, {"token": "fixture"}, self.run_id, 1, wait_for_output=True)
        sleep.assert_not_called()
        self.assertIsNone(result["outputs_url"])
        self.assertFalse(result["wait_timed_out"])


if __name__ == "__main__":
    unittest.main()
