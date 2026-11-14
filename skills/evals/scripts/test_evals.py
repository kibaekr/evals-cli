import contextlib
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


if __name__ == "__main__":
    unittest.main()
