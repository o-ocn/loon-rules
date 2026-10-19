"""Package the tested public assets and Functions as one immutable CI artifact."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def files_in(root):
    root = Path(root)
    files = {}
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Release bundles cannot contain symlinks')
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path
    return files


def verify_bundle(root):
    root = Path(root)
    metadata = json.loads((root / 'release.json').read_text(encoding='utf-8'))
    import re
    if metadata['schema_version'] != 1 or not re.fullmatch(r'[a-f0-9]{40}', metadata['commit']):
        raise ValueError('Invalid release metadata')
    actual = files_in(root)
    actual.pop('release.json')
    if set(actual) != set(metadata['files']):
        raise ValueError('Release file set differs from the tested bundle')
    if not actual or any(not name.startswith(('dist/', 'functions/')) or name.startswith('dist/functions/') for name in actual):
        raise ValueError('Invalid release layout')
    if any(name == 'dist/_worker.js' or name.startswith('dist/_worker.js/') for name in actual):
        raise ValueError('Advanced Worker overrides bypass the tested Functions and are not allowed')
    if any(Path(name).name == '.env' or Path(name).name.startswith('.env.') for name in actual):
        raise ValueError('Dotenv files must not be included in a public release')
    for name, path in actual.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata['files'][name]:
            raise ValueError('Release checksum mismatch: ' + name)
    from scripts.scan_secrets import scan_tree
    if list(scan_tree(root, ignore_repository_temporary=False)):
        raise ValueError('Credential scan rejected the release bundle')
    return metadata


def create_bundle(repo, output):
    repo, output = Path(repo), Path(output)
    files_in(repo / 'dist')
    files_in(repo / 'functions')
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(repo / 'dist', output / 'dist', ignore=shutil.ignore_patterns('functions'))
    if (repo / 'functions').is_dir():
        shutil.copytree(repo / 'functions', output / 'functions')
    metadata = {'schema_version': 1,
                'commit': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip(),
                'files': {name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for name, path in sorted(files_in(output).items())}}
    (output / 'release.json').write_text(json.dumps(metadata, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    verify_bundle(output)
    print(f'[PASS] Packaged {len(metadata["files"])} tested asset and Functions files.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    create_bundle(Path(__file__).resolve().parents[1], args.output)
