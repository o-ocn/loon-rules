"""Publish tested generated files without racing or partially pushing release refs."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCOPES = {
    'rules': ('dist/', 'sources.yml', 'scripts/upstream_lock.json'),
    'audit': ('audit/', 'state/'),
}


def git(repo, *arguments):
    return subprocess.check_output(
        ['git', *arguments], cwd=repo, text=True, encoding='utf-8',
    ).strip()


def publish(repo=ROOT, *, kind):
    """Never rebase verified output onto source code that was not tested."""
    paths = SCOPES[kind]
    base = git(repo, 'rev-parse', 'HEAD')
    git(repo, 'fetch', '--no-tags', 'origin', 'refs/heads/main')
    current = git(repo, 'rev-parse', 'FETCH_HEAD')
    if current != base:
        raise RuntimeError(
            f'main advanced during verification ({base[:12]} -> {current[:12]}). '
            'Nothing published. Run the workflow again against current main; '
            'do not rebase untested generated output.'
        )

    git(repo, 'add', '--', *paths)
    staged = git(repo, 'diff', '--cached', '--name-only').splitlines()
    if any(not any(name == p or (p.endswith('/') and name.startswith(p))
                   for p in paths) for name in staged):
        raise RuntimeError('Unexpected staged files outside the generated publication scope.')
    if not staged:
        print(f'No {kind} changes detected. No commit or release tag created.')
        return None

    git(repo, 'config', '--local', 'user.name', 'github-actions[bot]')
    git(repo, 'config', '--local', 'user.email', 'github-actions[bot]@users.noreply.github.com')
    timestamp = datetime.now(timezone.utc)
    message = (
        'chore(rules): sync upstream and rebuild rules'
        if kind == 'rules' else 'chore(audit): update shadow audit report and upstream state'
    )
    suffix = '' if kind == 'rules' else ' [skip ci]'
    git(repo, 'commit', '-m', f'{message} [{timestamp:%Y-%m-%d %H:%M:%S UTC}]{suffix}')
    commit = git(repo, 'rev-parse', 'HEAD')
    refs = ['HEAD:refs/heads/main']
    if kind == 'rules':
        tag = f'release-{timestamp:%Y%m%d-%H%M%S}-{commit[:12]}'
        git(repo, 'tag', tag)
        refs.append(f'refs/tags/{tag}:refs/tags/{tag}')
    # One transaction: rejected main must not leave a misleading release tag.
    # Explicit refs and no-follow-tags avoid exporting unrelated local tags.
    git(repo, 'push', '--atomic', '--no-follow-tags', 'origin', *refs)
    print(f'Published verified {kind} commit {commit} to main.')
    return commit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=SCOPES, required=True)
    args = parser.parse_args()
    try:
        publish(kind=args.kind)
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f'::error::Generated publication failed: {error}')
        raise SystemExit(1) from error


if __name__ == '__main__':
    main()
