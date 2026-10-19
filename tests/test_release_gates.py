"""Real failure controls for credential detection and artifact-only deployment."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.scan_secrets import find_secret, scan_tree
from scripts.pages_bundle import create_bundle, verify_bundle
from scripts.deploy_pages import deploy


ROOT = Path(__file__).resolve().parents[1]


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.test_tmp').mkdir(exist_ok=True)

    def test_request_variables_and_empty_or_environment_defaults_are_allowed(self):
        for source in [
            'const password = (body.password || "").trim();',
            'const password = process.env.ACCESS_PASSWORD;',
            'password' + ' = ""',
            'password' + ': "${ACCESS_PASSWORD}"',
        ]:
            self.assertIsNone(find_secret(source), source)
        self.assertIsNone(find_secret('password' + ': ""', '.yaml'))

    def test_hardcoded_password_key_and_subscription_values_still_fail(self):
        for source, suffix in [
            ('password' + ' = "' + 'synthetic-secret' + '"', '.py'),
            ('PASSWORD' + '=\'' + 'synthetic-secret' + '\'', '.js'),
            ('"password"' + ': "' + 'synthetic-secret' + '"', '.json'),
            ('password' + ': ' + 'synthetic-secret', '.yaml'),
            ('BEGIN' + ' PRIVATE KEY', '.txt'),
            ('tok' + 'en=' + 'x' * 24, '.txt'),
        ]:
            with self.subTest(suffix=suffix):
                self.assertIsNotNone(find_secret(source, suffix))

    def test_only_temporary_copies_are_ignored_and_reports_do_not_echo_values(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.test_tmp') as directory:
            root = Path(directory)
            content = 'password' + ' = "' + 'synthetic-secret' + '"'
            for path in ['.test_tmp/old.js', 'dist/functions/live.js', 'functions/live.js', 'dist/index.html', 'dist/.test_tmp/live.js']:
                p = root / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content)
            findings = list(scan_tree(root))
            self.assertEqual({p for p, _ in findings}, {'dist/functions/live.js', 'functions/live.js', 'dist/index.html', 'dist/.test_tmp/live.js'})
            self.assertNotIn('synthetic-secret', str(findings))

    def make_bundle(self, base):
        repo = base / 'repo'
        (repo / 'dist').mkdir(parents=True)
        (repo / 'dist/index.html').write_text('tested portal')
        (repo / 'functions').mkdir()
        (repo / 'functions/api.js').write_text('export const fixture = 1;')
        output = base / 'bundle'
        with patch('scripts.pages_bundle.subprocess.check_output', return_value='a' * 40), contextlib.redirect_stdout(io.StringIO()):
            create_bundle(repo, output)
        return output

    def test_bundle_detects_function_change_missing_file_and_extra_file(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.test_tmp') as directory:
            bundle = self.make_bundle(Path(directory))
            self.assertEqual(verify_bundle(bundle)['commit'], 'a' * 40)
            source = bundle / 'functions/api.js'
            original = source.read_bytes()
            source.write_text('modified function')
            with self.assertRaises(ValueError):
                verify_bundle(bundle)
            source.unlink()
            with self.assertRaises(ValueError):
                verify_bundle(bundle)
            source.write_bytes(original)
            (bundle / 'dist/extra.js').write_text('unverified')
            with self.assertRaises(ValueError):
                verify_bundle(bundle)

    def test_advanced_worker_cannot_override_tested_functions(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.test_tmp') as directory:
            bundle = self.make_bundle(Path(directory))
            metadata = json.loads((bundle / 'release.json').read_text())
            for name in ['dist/_worker.js', 'dist/_worker.js/index.js']:
                worker = bundle / name
                worker.parent.mkdir(parents=True, exist_ok=True)
                worker.write_text('unverified Worker')
                import hashlib
                metadata['files'][name] = hashlib.sha256(worker.read_bytes()).hexdigest()
                (bundle / 'release.json').write_text(json.dumps(metadata))
                with self.assertRaisesRegex(ValueError, 'override'):
                    verify_bundle(bundle)
                worker.unlink()
                del metadata['files'][name]

    def test_local_deploy_is_refused_before_any_upload(self):
        with patch.dict(os.environ, {}, clear=True), patch('scripts.deploy_pages.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError, 'GitHub Actions'):
                deploy('missing-bundle')
            run.assert_not_called()

    def test_ci_deploy_uses_only_the_verified_bundle_in_isolated_directory(self):
        environment = {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'o-ocn/loon-rules',
                       'GITHUB_REF': 'refs/heads/main', 'GITHUB_JOB': 'pages-deploy',
                       'GITHUB_RUN_ID': '123', 'GITHUB_EVENT_NAME': 'push',
                       'CLOUDFLARE_API_TOKEN': 'fixture', 'CLOUDFLARE_ACCOUNT_ID': 'fixture'}
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as runner, tempfile.TemporaryDirectory(dir=ROOT / '.test_tmp') as directory:
            environment['RUNNER_TEMP'] = runner
            bundle = self.make_bundle(Path(directory))
            def upload(command, *, cwd, check):
                cwd = Path(cwd)
                self.assertNotIn(str(ROOT), str(cwd))
                self.assertEqual((cwd / 'functions/api.js').read_text(), 'export const fixture = 1;')
                self.assertIn('loon-rules', command)
                self.assertIn('main', command)
                self.assertNotIn('--commit-dirty=true', command)
                self.assertTrue(check)
            with patch.dict(os.environ, environment, clear=True), patch('scripts.deploy_pages.verify_local_pre_release'), patch('scripts.deploy_pages.subprocess.run', side_effect=upload) as run:
                deploy(bundle)
                run.assert_called_once()
            (bundle / 'functions/api.js').write_text('unverified change')
            with patch.dict(os.environ, environment, clear=True), patch('scripts.deploy_pages.subprocess.run') as run:
                with self.assertRaises(ValueError):
                    deploy(bundle)
                run.assert_not_called()
