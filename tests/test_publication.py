"""Real bare-remote regressions for serialized and atomic generated publication."""
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml
from scripts import publish_generated as publication


ROOT = Path(__file__).resolve().parents[1]


class PublicationTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.test_tmp').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.test_tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / 'remote.git'
        self.command(self.root, 'init', '--bare', '--initial-branch=main', str(self.remote))
        self.first = self.clone('first')
        for name in ['dist/rules.lsr', 'sources.yml', 'scripts/upstream_lock.json',
                     'audit/report.json', 'state/upstream.json', 'README.md']:
            self.write(self.first, name, 'baseline\n')
        self.command(self.first, 'add', '.')
        self.command(self.first, 'commit', '-m', 'initial')
        self.command(self.first, 'push', 'origin', 'main')
        self.second = self.clone('second')
        self.base = self.command(self.first, 'rev-parse', 'HEAD')

    def command(self, repo, *arguments):
        return subprocess.check_output(
            ['git', *arguments], cwd=repo, text=True, encoding='utf-8',
            stderr=subprocess.STDOUT,
        ).strip()

    def clone(self, name):
        target = self.root / name
        self.command(self.root, 'clone', str(self.remote), str(target))
        self.command(target, 'config', 'user.name', 'Publication Fixture')
        self.command(target, 'config', 'user.email', 'fixture@example.invalid')
        self.command(target, 'config', 'core.autocrlf', 'false')
        return target

    def write(self, repo, name, contents):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding='utf-8')

    def publish(self, repo, kind='rules'):
        with contextlib.redirect_stdout(io.StringIO()):
            return publication.publish(repo, kind=kind)

    def advance_source(self):
        self.write(self.second, 'README.md', 'new source\n')
        self.command(self.second, 'add', 'README.md')
        self.command(self.second, 'commit', '-m', 'concurrent source change')
        self.command(self.second, 'push', 'origin', 'main')
        return self.command(self.second, 'rev-parse', 'HEAD')

    def test_success_publishes_main_and_only_its_release_tag(self):
        self.command(self.first, 'tag', '-a', 'unrelated-local-tag', '-m', 'unrelated tag')
        self.command(self.first, 'config', 'push.followTags', 'true')
        self.write(self.first, 'dist/rules.lsr', 'verified rules\n')
        commit = self.publish(self.first)
        self.assertNotEqual(commit, self.base)
        self.assertEqual(self.command(self.remote, 'rev-parse', 'main'), commit)
        tags = self.command(self.remote, 'tag').splitlines()
        self.assertEqual(len(tags), 1)
        self.assertTrue(tags[0].startswith('release-'))
        self.assertEqual(self.command(self.remote, 'rev-parse', tags[0]), commit)
        self.assertEqual(self.command(self.first, 'status', '--porcelain'), '')

    def test_queued_duplicate_checks_out_current_main_and_is_idempotent(self):
        self.write(self.first, 'dist/rules.lsr', 'verified rules\n')
        commit = self.publish(self.first)
        # Same event SHA initially; queued checkout resolves the branch after the lock.
        self.assertEqual(self.command(self.second, 'rev-parse', 'HEAD'), self.base)
        self.command(self.second, 'fetch', 'origin', 'main')
        self.command(self.second, 'merge', '--ff-only', 'FETCH_HEAD')
        self.assertIsNone(self.publish(self.second))
        self.assertEqual(self.command(self.remote, 'rev-parse', 'main'), commit)
        self.assertEqual(len(self.command(self.remote, 'tag').splitlines()), 1)

    def test_audit_after_rules_keeps_both_results_without_extra_release_tag(self):
        self.write(self.first, 'dist/rules.lsr', 'verified rules\n')
        self.publish(self.first)
        self.command(self.second, 'fetch', 'origin', 'main')
        self.command(self.second, 'merge', '--ff-only', 'FETCH_HEAD')
        self.write(self.second, 'audit/report.json', 'new verified audit\n')
        commit = self.publish(self.second, 'audit')
        self.assertEqual(self.command(self.remote, 'rev-parse', 'main'), commit)
        self.assertEqual(self.command(self.remote, 'show', 'main:dist/rules.lsr'), 'verified rules')
        self.assertIn('[skip ci]', self.command(self.remote, 'log', '-1', '--format=%s'))
        self.assertEqual(len(self.command(self.remote, 'tag').splitlines()), 1)

    def test_source_advancing_during_verification_fails_before_commit(self):
        advanced = self.advance_source()
        self.write(self.first, 'dist/rules.lsr', 'stale rules\n')
        with self.assertRaisesRegex(RuntimeError, 'main advanced during verification'):
            self.publish(self.first)
        self.assertEqual(self.command(self.first, 'rev-parse', 'HEAD'), self.base)
        self.assertEqual(self.command(self.remote, 'rev-parse', 'main'), advanced)
        self.assertEqual(self.command(self.remote, 'tag'), '')

    def test_source_race_after_fetch_rejects_main_and_tag_atomically(self):
        self.write(self.first, 'dist/rules.lsr', 'verified but superseded\n')
        real_git = publication.git
        advanced = []
        def race(repo, *arguments):
            if arguments[0] == 'push':
                advanced.append(self.advance_source())
            return real_git(repo, *arguments)
        with patch.object(publication, 'git', side_effect=race):
            with self.assertRaises(subprocess.CalledProcessError):
                self.publish(self.first)
        self.assertEqual(len(advanced), 1)
        self.assertEqual(self.command(self.remote, 'rev-parse', 'main'), advanced[0])
        self.assertEqual(self.command(self.remote, 'tag'), '')
        self.assertEqual(self.command(self.remote, 'show', 'main:dist/rules.lsr'), 'baseline')

    def test_no_generated_change_does_not_hide_advanced_main(self):
        self.advance_source()
        with self.assertRaisesRegex(RuntimeError, 'main advanced during verification'):
            self.publish(self.first)
        self.assertEqual(self.command(self.remote, 'tag'), '')

    def test_server_without_atomic_support_fails_without_partial_publication(self):
        self.command(self.remote, 'config', 'receive.advertiseAtomic', 'false')
        self.write(self.first, 'dist/rules.lsr', 'verified rules\n')
        with self.assertRaises(subprocess.CalledProcessError):
            self.publish(self.first)
        self.assertEqual(self.command(self.remote, 'rev-parse', 'main'), self.base)
        self.assertEqual(self.command(self.remote, 'tag'), '')

    def test_legacy_nonatomic_push_reproduces_orphan_tag(self):
        self.advance_source()
        self.write(self.first, 'dist/rules.lsr', 'stale rules\n')
        self.command(self.first, 'add', 'dist/')
        self.command(self.first, 'commit', '-m', 'old publication')
        self.command(self.first, 'tag', 'legacy-orphan')
        with self.assertRaises(subprocess.CalledProcessError):
            self.command(self.first, 'push', 'origin', 'HEAD', '--tags')
        self.assertEqual(self.command(self.remote, 'tag'), 'legacy-orphan')
        self.assertEqual(self.command(self.remote, 'show', 'main:dist/rules.lsr'), 'baseline')

    def test_unexpected_staged_source_is_never_published(self):
        self.write(self.first, 'README.md', 'untested source\n')
        self.command(self.first, 'add', 'README.md')
        self.write(self.first, 'dist/rules.lsr', 'verified rules\n')
        with self.assertRaisesRegex(RuntimeError, 'outside the generated publication scope'):
            self.publish(self.first)
        self.assertEqual(self.command(self.remote, 'rev-parse', 'main'), self.base)
        self.assertEqual(self.command(self.remote, 'tag'), '')


class PublicationWorkflowTests(unittest.TestCase):
    def test_all_automated_writers_lock_before_checkout_and_publication(self):
        def load(name):
            return yaml.load((ROOT / '.github/workflows' / name).read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
        build = load('sync-and-build.yml')['jobs']['build-and-validate']
        audit = load('shadow-audit.yml')['jobs']['shadow-audit']
        self.assertEqual(audit['if'], "github.ref == 'refs/heads/main'")
        for job, kind in [(build, 'rules'), (audit, 'audit')]:
            self.assertEqual(job['concurrency'], {
                'group': 'loon-rules-repository-${{ github.ref }}',
                'cancel-in-progress': 'false', 'queue': 'max',
            })
            steps = job['steps']
            checkout = steps[0]['with']
            self.assertEqual(checkout['fetch-depth'], '0')
            self.assertIn('ref', checkout)
            self.assertIn('main' if kind == 'audit' else 'github.ref_name', checkout['ref'])
            publisher = next(s for s in steps if 'scripts.publish_generated' in s.get('run', ''))
            self.assertIn('--kind ' + kind, publisher['run'])
            self.assertGreater(steps.index(publisher), next(i for i, s in enumerate(steps) if 'test_publication.py' in s.get('run', '')))
        self.assertIn("github.event_name == 'pull_request' && github.ref", build['steps'][0]['with']['ref'])
        self.assertEqual(build['outputs']['release_commit'], '${{ steps.release.outputs.commit }}')
        pages = load('sync-and-build.yml')['jobs']['pages-deploy']
        checkout = next(s for s in pages['steps'] if s.get('uses') == 'actions/checkout@v4')
        self.assertEqual(checkout['with']['ref'], '${{ needs.build-and-validate.outputs.release_commit }}')
        self.assertNotEqual(pages['concurrency']['group'], build['concurrency']['group'])


if __name__ == '__main__':
    unittest.main()
