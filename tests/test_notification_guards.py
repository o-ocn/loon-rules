"""Behavior checks for notification trust, delivery state and fresh audit evidence."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts import audit_pipeline as audit
from scripts import notify_telegram as notify


class NotificationGuards(unittest.TestCase):
    def test_actual_entrypoint_rejects_untrusted_event_without_sending(self):
        trusted = {"name": "Shadow Audit Scheduled Run", "head_repository": {"full_name": "o-ocn/loon-rules"}, "head_branch": "main", "event": "schedule"}
        variants = [
            {**trusted, "event": "pull_request"},
            {**trusted, "head_repository": {"full_name": "foreign/repository"}},
            {**trusted, "head_branch": "other"},
            {**trusted, "name": "Other workflow"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            event_file = Path(directory) / "event.json"
            environment = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_PATH": str(event_file), "GITHUB_EVENT_NAME": "workflow_run", "GITHUB_REPOSITORY": "o-ocn/loon-rules"}
            for run in variants:
                event_file.write_text(json.dumps({"workflow_run": run}))
                with self.subTest(run=run), patch.dict(os.environ, environment), patch.object(notify, "send_telegram_message") as send, contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as caught:
                        notify.main()
                    self.assertEqual(caught.exception.code, 0)
                    send.assert_not_called()
            event_file.write_text(json.dumps({"workflow_run": trusted}))
            with patch.dict(os.environ, environment):
                self.assertTrue(notify.trusted_runtime_event())

    def test_recovery_clears_all_workflow_steps_and_recurrence_is_delivered(self):
        workflow = "Shadow Audit Scheduled Run"
        with tempfile.TemporaryDirectory() as directory:
            state_path = str(Path(directory) / "alerts.json")
            state = notify.AlertDeduplicator(state_path)
            for key in [workflow + "::Audit", workflow + "::Tests", "Other::Build"]:
                state.mark_sent(key)
            state.save()
            arguments = ["notify", "--event-type", "workflow_run", "--workflow-name", workflow, "--dedup-state-file", state_path]
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), patch.object(sys, "argv", arguments + ["--conclusion", "success"]), patch.object(notify, "send_telegram_message") as send, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    notify.main()
                self.assertEqual(caught.exception.code, 0)
                send.assert_not_called()
            self.assertEqual(set(notify.AlertDeduplicator(state_path).state), {"Other::Build"})
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), patch.object(sys, "argv", arguments + ["--failed-step", "Audit", "--conclusion", "failure"]), patch.object(notify, "send_telegram_message", return_value=(True, "SUCCESS")) as send, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    notify.main()
                self.assertEqual(caught.exception.code, 0)
                send.assert_called_once()

    def test_failed_delivery_does_not_store_sent_state(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path = str(Path(directory) / "state.json")
            arguments = ["notify", "--event-type", "workflow_run", "--conclusion", "failure", "--workflow-name", "Shadow Audit Scheduled Run", "--dedup-state-file", state_path]
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), patch.object(sys, "argv", arguments), patch.object(notify, "send_telegram_message", return_value=(False, "FAILED")), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    notify.main()
                self.assertEqual(caught.exception.code, 1)
            self.assertEqual(notify.AlertDeduplicator(state_path).state, {})

    def test_api_error_code_cannot_echo_response_secrets(self):
        sensitive = "response-body-private-value"
        response = MagicMock()
        response.status = 200
        response.read.return_value = json.dumps({"ok": False, "error_code": sensitive, "description": sensitive}).encode()
        response.__enter__.return_value = response
        output = io.StringIO()
        with patch.object(notify.urllib.request, "urlopen", return_value=response), patch.object(notify.time, "sleep"), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            success, reason = notify.send_telegram_message("fake-token", "fake-chat", "probe")
        self.assertFalse(success)
        self.assertNotIn(sensitive, output.getvalue() + reason)

    def test_invalid_parsed_fetch_preserves_last_good_cache(self):
        valid = "DOMAIN,one.cn\nDOMAIN,two.cn\n"
        url = "https://example.test/rules"
        response = MagicMock()
        response.status = 200
        response.read.return_value = b"not-a-rule\nstill-not-a-rule\ninvalid\n"
        response.__enter__.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            cache_file = Path(directory) / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".list")
            cache_file.write_text(valid)
            with patch.object(audit, "UPSTREAM_CACHE_DIR", directory), patch.object(audit.urllib.request, "urlopen", return_value=response):
                text, cached = audit.fetch_source_text(url, min_rules=2)
            self.assertTrue(cached)
            self.assertEqual(text, valid)
            self.assertEqual(cache_file.read_text(), valid)

    def test_partial_invalid_source_does_not_enter_aggregation_and_receipt_is_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config" / "upstream_sources.yml").write_text("providers:\n  good:\n    url: https://example.test/good\n    expected_min_rules: 1\n  bad:\n    url: https://example.test/bad\n    expected_min_rules: 2\n")
            engine = MagicMock()
            engine.evaluate.return_value = {"decision": "REVIEW", "confidence_score": 60, "reason": "fixture", "stage": "fixture"}
            def fetch(url, **kwargs):
                return ("DOMAIN,good.cn\n" if url.endswith("good") else "DOMAIN,bad-only.cn\n"), False
            receipt_path = root / "receipt.json"
            environment = {"SHADOW_HEALTH_RECEIPT": str(receipt_path), "GITHUB_RUN_ID": "guard-run"}
            with patch.object(audit, "BASE_DIR", directory), patch.object(audit, "AUDIT_DIR", str(root / "audit")), patch.object(audit, "STATE_DIR", str(root / "state")), patch.object(audit, "ScoreEngine", return_value=engine), patch.object(audit, "fetch_source_text", side_effect=fetch), patch.dict(os.environ, environment), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    audit.run_shadow_audit()
                self.assertEqual(caught.exception.code, 1)
            engine.evaluate.assert_called_once()
            self.assertEqual(engine.evaluate.call_args.args[1], "good.cn")
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(receipt["run_id"], "guard-run")
            state_file = root / "state" / "upstream_state.json"
            self.assertEqual(receipt["files"]["state"], hashlib.sha256(state_file.read_bytes()).hexdigest())
            self.assertIsNone(json.loads(state_file.read_text())["sources"]["bad"]["last_synced_at"])


if __name__ == "__main__":
    unittest.main()
