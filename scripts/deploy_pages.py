"""Production deployment entry: verified CI bundle only, isolated from checkout."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from scripts.pages_bundle import verify_bundle
from scripts.verify_mirrors import verify_local_pre_release


def deploy(bundle):
    expected = {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'o-ocn/loon-rules',
                'GITHUB_REF': 'refs/heads/main', 'GITHUB_JOB': 'pages-deploy'}
    if any(os.environ.get(key) != value for key, value in expected.items()) or not os.environ.get('GITHUB_RUN_ID', '').isdigit():
        raise ValueError('Production deployment must use the main GitHub Actions workflow; local uploads are not an approved release path.')
    if os.environ.get('GITHUB_EVENT_NAME') == 'pull_request':
        raise ValueError('Pull requests cannot deploy production')
    if not all(os.environ.get(key) for key in ('CLOUDFLARE_API_TOKEN', 'CLOUDFLARE_ACCOUNT_ID')):
        raise ValueError('Deployment credentials are missing')
    runner_temp = Path(os.environ.get('RUNNER_TEMP', ''))
    if not runner_temp.is_absolute() or not runner_temp.is_dir() or runner_temp.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Deployment requires the isolated GitHub runner temporary directory')
    bundle = Path(bundle).resolve()
    metadata = verify_bundle(bundle)
    verify_local_pre_release(dist_dir=str(bundle / 'dist'), manifest_path=str(bundle / 'dist/diagnostics/manifest.json'))
    with tempfile.TemporaryDirectory(prefix='loon-pages-release-', dir=runner_temp) as directory:
        isolated = Path(directory) / 'release'
        shutil.copytree(bundle, isolated)
        verify_bundle(isolated)
        # Wrangler can only discover the Functions shipped with this exact artifact.
        subprocess.run(['npx', '--yes', 'wrangler@4.151.1', 'pages', 'deploy', 'dist',
                        '--project-name', 'loon-rules', '--branch', 'main',
                        '--commit-hash', metadata['commit'], '--commit-message',
                        'Verified GitHub Actions run ' + os.environ['GITHUB_RUN_ID']],
                       cwd=isolated, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True)
    args = parser.parse_args()
    deploy(args.bundle)
