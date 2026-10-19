"""Verify that the public Pages entry serves the exact validated release bundle."""
import argparse
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


PAGES_BASE = "https://loon.rules.o-ous.com/"
REQUEST_HEADERS = {"User-Agent": "Loon-Rules-Release-Check/1.0"}
MAIN_REF_API = "https://api.github.com/repos/o-ocn/loon-rules/git/ref/heads/main"


def public_body(relative, data):
    body = data.replace(b"\r\n", b"\n")
    if relative != "index.html":
        return body
    # Cloudflare adds this empty analytics script immediately before </body>.
    match = re.search(rb'<script\b[^>]*>\s*</script>\n?(?=\s*</body>\s*</html>\s*\Z)', body)
    if not match:
        return body

    class TagParser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            self.tag, self.attrs = tag, attrs

    parsed = TagParser()
    parsed.feed(match.group().decode("utf-8"))
    attrs = dict(parsed.attrs)
    allowed = {"type", "src", "integrity", "data-cf-beacon", "crossorigin"}
    if parsed.tag != "script" or set(attrs) != allowed or len(parsed.attrs) != len(allowed):
        return body
    url = urlsplit(attrs.get("src") or "")
    if (url.scheme != "https" or url.netloc != "static.cloudflareinsights.com"
            or url.query or url.fragment
            or not re.fullmatch(r"/beacon\.min\.js/v[0-9a-f]+", url.path)
            or attrs["type"] != "module" or attrs["crossorigin"] != "anonymous"
            or not re.fullmatch(r"sha512-[A-Za-z0-9+/]+=*", attrs["integrity"] or "")):
        return body
    return body[:match.start()] + body[match.end():]


def release_files(dist_dir):
    root = Path(dist_dir)
    files = sorted(root.glob("*.lsr")) + sorted((root / "diagnostics").glob("*"))
    files += [root / "plugins" / "Loon-China-DNS.lpx", root / "index.html"]
    if len(list(root.glob("*.lsr"))) != 19 or any(not p.is_file() for p in files):
        raise ValueError("The validated release bundle is incomplete")
    required = {"manifest.json", "LoonRules-Diagnostic.lpx", "loon-rules-diagnostic.js"}
    if not required <= {p.name for p in files if p.parent.name == "diagnostics"}:
        raise ValueError("The release bundle is missing diagnostic artifacts")
    return files


def is_current_release(dist_dir, *, opener=urllib.request.urlopen):
    """Reject an old run before it can overwrite newer rule or portal content."""
    root = Path(dist_dir)
    headers = dict(REQUEST_HEADERS)
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with opener(urllib.request.Request(MAIN_REF_API, headers=headers), timeout=15) as response:
        sha = json.loads(response.read())["object"]["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("GitHub returned an invalid main revision")
    release_files(root)
    tree_url = f"https://api.github.com/repos/o-ocn/loon-rules/git/trees/{sha}?recursive=1"
    with opener(urllib.request.Request(tree_url, headers=headers), timeout=15) as response:
        tree = json.loads(response.read())
    if tree.get('truncated'):
        raise ValueError('GitHub release file listing is incomplete')
    expected = {entry['path'] for entry in tree['tree'] if entry['type'] == 'blob'
                and entry['path'].startswith(('dist/', 'functions/'))}
    if any(entry.get('mode') == '120000' for entry in tree['tree'] if entry['path'] in expected):
        raise ValueError('Release sources cannot contain symlinks')
    files = {}
    for prefix, directory in (('dist', root), ('functions', root.parent / 'functions')):
        for path in directory.rglob('*'):
            if path.is_symlink():
                raise ValueError('Release sources cannot contain symlinks')
            if path.is_file():
                files[prefix + '/' + path.relative_to(directory).as_posix()] = path
    if set(files) != expected:
        print('[SKIP] Current main has a different asset or Functions file set; deployment skipped.')
        return False
    for relative, path in sorted(files.items()):
        url = f"https://raw.githubusercontent.com/o-ocn/loon-rules/{sha}/{relative}"
        # The GitHub token is never sent to Raw or Cloudflare.
        with opener(urllib.request.Request(url, headers=REQUEST_HEADERS), timeout=15) as response:
            remote = response.read()
        if remote.replace(b"\r\n", b"\n") != path.read_bytes().replace(b"\r\n", b"\n"):
            print("[SKIP] This bundle is superseded by the current main release; deployment skipped.")
            return False
    print("[PASS] Bundle matches the current main assets and Functions, including the complete file set.")
    return True


def verify_release(dist_dir, *, opener=urllib.request.urlopen, attempts=3, sleep=time.sleep):
    root = Path(dist_dir)
    files = release_files(root)

    for attempt in range(attempts):
        failures = []
        for path in files:
            relative = path.relative_to(root).as_posix()
            request = urllib.request.Request(PAGES_BASE + relative, headers=REQUEST_HEADERS)
            try:
                with opener(request, timeout=15) as response:
                    remote = response.read()
                    status = response.status
                if status != 200 or public_body(relative, remote) != public_body(relative, path.read_bytes()):
                    failures.append(relative)
            except (urllib.error.URLError, TimeoutError, OSError):
                failures.append(relative)
        if not failures:
            print(f"[PASS] Public Cloudflare Pages matches all {len(files)} validated release files.")
            return True
        print(f"[FAIL] Pages attempt {attempt + 1}/{attempts}: {', '.join(failures)}")
        if attempt + 1 < attempts:
            sleep(10)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", default="dist")
    parser.add_argument("--check-current", action="store_true")
    args = parser.parse_args()
    try:
        if args.check_current:
            current = is_current_release(args.dist_dir)
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                    output.write(f"current={'true' if current else 'false'}\n")
            return 0
        return 0 if verify_release(args.dist_dir) else 1
    except (ValueError, KeyError, urllib.error.URLError, TimeoutError, OSError) as error:
        print(f"[FAIL] {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
