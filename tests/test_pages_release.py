"""Pages release isolation, public artifact verification and alert semantics."""
import contextlib
import io
import json
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import yaml

from scripts import notify_telegram as notify
from scripts import verify_pages_release as pages


ROOT = Path(__file__).resolve().parents[1]


class PagesReleaseTests(unittest.TestCase):
    def make_bundle(self, root):
        paths = [f"rule-{i}.lsr" for i in range(19)] + [
            "diagnostics/manifest.json", "diagnostics/LoonRules-Diagnostic.lpx",
            "diagnostics/loon-rules-diagnostic.js", "plugins/Loon-China-DNS.lpx", "index.html",
        ]
        for path in paths:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((path + "\n").encode())
        (root / "index.html").write_bytes(b"<html><body>current portal\n</body>\n</html>\n")

    def test_only_observed_cloudflare_analytics_injection_is_ignored(self):
        body = b"<html><body>current portal\n</body>\n</html>\n"
        script = (b'<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js/vabcdef1234" '
                  b'integrity="sha512-YWJjZA==" data-cf-beacon=\'{"version":"fixture"}\' crossorigin="anonymous"></script>\n')
        inject = lambda tag: body.replace(b"</body>", tag + b"</body>")
        self.assertEqual(pages.public_body("index.html", inject(script)), body)
        for bad in (
            script.replace(b' type=', b' onload="alert(1)" type='),
            script.replace(b"static.cloudflareinsights.com", b"static.cloudflareinsights.com.evil.test"),
            script.replace(b"/vabcdef1234", b"/vabcdef1234?query=1"),
            script.replace(b' type=', b' src="https://evil.test/script.js" type='),
            script.replace(b"></script>", b">alert(1)</script>"),
        ):
            self.assertNotEqual(pages.public_body("index.html", inject(bad)), body)
        self.assertNotEqual(pages.public_body("index.html", script + body), body)
        self.assertNotEqual(pages.public_body("index.html", inject(script).replace(b"current portal", b"old portal")), body)
        self.assertEqual(pages.public_body("rule-0.lsr", inject(script)), inject(script))

    def opener(self, root, *, corrupt=None, denied=False):
        def open_file(request, **kwargs):
            self.assertEqual(request.get_header("User-agent"), "Loon-Rules-Release-Check/1.0")
            if denied:
                raise urllib.error.HTTPError(request.full_url, 403, "Denied", {}, None)
            relative = request.full_url.removeprefix(pages.PAGES_BASE)
            body = b"<html>fallback</html>" if relative == corrupt else (root / relative).read_bytes()
            response = MagicMock()
            response.status = 200
            response.read.return_value = body
            response.__enter__.return_value = response
            return response
        return open_file

    def test_public_release_matches_and_rejects_stale_or_html_content(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            self.make_bundle(root)
            self.assertTrue(pages.verify_release(root, opener=self.opener(root), attempts=1))
            for corrupt in ("rule-0.lsr", "diagnostics/manifest.json", "plugins/Loon-China-DNS.lpx", "index.html"):
                with self.subTest(corrupt=corrupt):
                    self.assertFalse(pages.verify_release(root, opener=self.opener(root, corrupt=corrupt), attempts=1))
            self.assertFalse(pages.verify_release(root, opener=self.opener(root, denied=True), attempts=1))

    def test_incomplete_bundle_is_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_bundle(root)
            (root / "diagnostics/manifest.json").unlink()
            opener = MagicMock()
            with self.assertRaises(ValueError):
                pages.verify_release(root, opener=opener)
            opener.assert_not_called()

    def test_old_run_cannot_overwrite_new_rule_or_portal_release(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory) / 'dist'
            root.mkdir()
            self.make_bundle(root)
            sha = "a" * 40
            current_files = {'dist/' + p.relative_to(root).as_posix(): p.read_bytes()
                             for p in root.rglob("*") if p.is_file()}
            current_files['functions/api/unlock.js'] = b'export const fixture = 1;\n'
            for name, body in current_files.items():
                path = root.parent / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)

            def open_current(request, **kwargs):
                response = MagicMock()
                response.status = 200
                if request.full_url == pages.MAIN_REF_API:
                    body = json.dumps({"object": {"sha": sha}}).encode()
                elif '/git/trees/' in request.full_url:
                    body = json.dumps({'truncated': False, 'tree': [
                        {'path': name, 'type': 'blob'} for name in current_files]}).encode()
                else:
                    self.assertIsNone(request.get_header("Authorization"))
                    prefix = f"https://raw.githubusercontent.com/o-ocn/loon-rules/{sha}/"
                    self.assertTrue(request.full_url.startswith(prefix))
                    body = current_files[request.full_url.removeprefix(prefix)]
                response.read.return_value = body
                response.__enter__.return_value = response
                return response

            self.assertTrue(pages.is_current_release(root, opener=open_current))
            for relative in ("dist/rule-0.lsr", "dist/index.html", "functions/api/unlock.js"):
                original = current_files[relative]
                current_files[relative] = b"newer validated release\n"
                self.assertFalse(pages.is_current_release(root, opener=open_current))
                current_files[relative] = original
            current_files['functions/new-handler.js'] = b'newer function'
            self.assertFalse(pages.is_current_release(root, opener=open_current))
            del current_files['functions/new-handler.js']
            removed = current_files.pop('functions/api/unlock.js')
            self.assertFalse(pages.is_current_release(root, opener=open_current))
            current_files['functions/api/unlock.js'] = removed
            with self.assertRaises(urllib.error.URLError):
                pages.is_current_release(root, opener=MagicMock(side_effect=urllib.error.URLError("offline")))

    def test_deployment_is_separate_and_requires_successful_rule_checks(self):
        workflow = yaml.load((ROOT / ".github/workflows/sync-and-build.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        jobs = workflow["jobs"]
        build_steps = jobs["build-and-validate"]["steps"]
        names = [s["name"] for s in build_steps]
        self.assertFalse(any("pages deploy" in s.get("run", "") for s in build_steps))
        self.assertLess(names.index('Compile tested Pages Functions'), names.index('Pre-Release Local Integrity Gate (Fail-Stop Release Barrier)'))
        self.assertTrue(any(s.get('with', {}).get('path') == '.release_tmp/pages-release/' for s in build_steps))
        self.assertLess(names.index("Post-Release Mirrors and CDN Health Alert Gate"), names.index("Upload Verified Pages Bundle"))
        deployment = jobs["pages-deploy"]
        self.assertEqual(deployment["needs"], "build-and-validate")
        self.assertIn("github.event_name != 'pull_request'", deployment["if"])
        self.assertIn("github.repository == 'o-ocn/loon-rules'", deployment["if"])
        self.assertIn("github.ref == 'refs/heads/main'", deployment["if"])
        self.assertEqual(deployment["permissions"], {"contents": "read"})
        steps = deployment["steps"]
        self.assertIn("exit 1", steps[0]["run"])
        self.assertTrue(any(s.get("uses") == "actions/download-artifact@v4" and s["with"]["name"] == "loon-rules-dist" for s in steps))
        self.assertEqual(steps[-1]["name"], "Verify public Cloudflare Pages release")
        self.assertEqual(steps[-1]["if"], "steps.current.outputs.current == 'true'")
        self.assertTrue(any(s.get("id") == "current" and "--check-current" in s["run"] for s in steps))
        self.assertFalse(any("continue-on-error" in s for s in steps))

    def test_pages_failure_has_a_distinct_alert(self):
        context = {"workflow_name": "Sync Upstream and Build Loon Rules", "conclusion": "failure"}
        message = notify.build_alert_message("workflow_run", {**context, "failed_step": "Cloudflare Pages - Check deployment credentials"})
        self.assertIn("网站部署异常", message)
        self.assertNotIn("规则更新异常", message)
        rule_message = notify.build_alert_message("workflow_run", {**context, "failed_step": "Build Rulesets and Diagnostics"})
        self.assertIn("规则更新异常", rule_message)
        self.assertIn('job.get("name") == "Cloudflare Pages deployment"', (ROOT / ".github/workflows/notify-exceptions.yml").read_text(encoding="utf-8"))

    def test_actual_workflow_query_identifies_failed_pages_job(self):
        workflow = yaml.load((ROOT / ".github/workflows/notify-exceptions.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        step = next(s for s in workflow["jobs"]["notify"]["steps"] if s["name"] == "Query Failed Step Summary")
        code = step["run"].split("python -c '", 1)[1].rsplit("'", 1)[0]
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({"jobs": [
            {"name": "build-and-validate", "conclusion": "success", "steps": []},
            {"name": "Cloudflare Pages deployment", "conclusion": "failure",
             "steps": [{"name": "Check deployment credentials", "conclusion": "failure"}]},
        ]}).encode()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "github-output"
            environment = {"GH_TOKEN": "fixture-token", "JOBS_URL": "https://api.github.com/repos/o-ocn/loon-rules/actions/runs/1/jobs", "GITHUB_OUTPUT": str(output)}
            with patch.dict(os.environ, environment), patch("urllib.request.urlopen", return_value=response), contextlib.redirect_stdout(io.StringIO()):
                exec(compile(code, "workflow-failed-step-query", "exec"), {})
            self.assertIn("step=Cloudflare Pages - Check deployment credentials", output.read_text())


if __name__ == "__main__":
    unittest.main()
