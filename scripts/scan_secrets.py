"""Small source/artifact credential gate; diagnostics never include matched values."""
import re
from pathlib import Path


EXTENSIONS = {'.py', '.js', '.mjs', '.html', '.env', '.lpx', '.list', '.lsr', '.yml', '.yaml', '.json', '.md', '.txt', '.sh'}
IGNORED_DIRS = {'.git', '__pycache__', '.pytest_cache', 'node_modules', 'tmp_build',
                '.tmp_staging', '.test_tmp', '.upstream_cache', 'scripts/.upstream_cache', '.wrangler', '.release_tmp'}
PASSWORD_LITERAL = re.compile(
    r'''(?i)\b["']?password["']?\s*[:=]\s*(?P<quote>["'`])(?P<value>[^"'`\r\n]+)(?P=quote)''')
PATTERNS = [(re.compile('BEGIN' + ' PRIVATE KEY'), 'Private Key'),
            (re.compile('BEGIN' + ' RSA PRIVATE KEY'), 'RSA Private Key'),
            (re.compile('BEGIN' + ' CERTIFICATE'), 'Certificate'),
            (re.compile('tok' + 'en=[a-zA-Z0-9_-]{16,}'), 'Subscription token')]


def find_secret(content, suffix=''):
    for pattern, label in PATTERNS:
        if pattern.search(content):
            return label
    for match in PASSWORD_LITERAL.finditer(content):
        if not re.fullmatch(r'\$\{[A-Za-z_][A-Za-z0-9_]*\}', match['value']):
            return 'Hardcoded password'
    if suffix in {'.yml', '.yaml'}:
        for match in re.finditer(r'(?im)^\s*password\s*:\s*([^#\r\n]+)', content):
            value = match[1].strip().strip('"\'')
            if value and value.lower() not in {'null', '~'} and not re.fullmatch(r'\$\{[A-Za-z_][A-Za-z0-9_]*\}', value):
                return 'Hardcoded password'
    return None


def scan_tree(root, *, ignore_repository_temporary=True):
    import os
    root = Path(root)
    for directory, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not ignore_repository_temporary or
                   (Path(directory) / d).relative_to(root).as_posix() not in IGNORED_DIRS]
        for name in files:
            path = Path(directory) / name
            if path.suffix.lower() in EXTENSIONS or path.name == '.env':
                label = find_secret(path.read_text(encoding='utf-8', errors='ignore'), path.suffix.lower())
                if label:
                    yield path.relative_to(root).as_posix(), label
