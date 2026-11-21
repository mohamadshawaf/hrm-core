"""Read-only pre-publication check for accidentally packaged sensitive files.

This is a *basic* guard; it is not a full secret scanning solution. Run a
separate credential/history audit before publishing any git repository.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


IGNORED_DIRECTORIES = frozenset({
    '.git', '.venv', '.dart_tool', 'build', '__pycache__', '.pytest_cache',
})
SENSITIVE_EXTENSIONS = frozenset({
    '.sqlite', '.sqlite3', '.db', '.pem', '.p12', '.pfx', '.key',
})
SENSITIVE_NAMES = frozenset({
    '.env', 'credentials.json', 'service-account.json', 'id_rsa',
    'verification-outbox.txt', 'invitation-outbox.txt', 'reset-outbox.txt',
})


def detect_sensitive_files(project_root: Path) -> list[str]:
    """Return repository-relative paths for files needing manual removal."""
    hits: list[str] = []
    for path in project_root.rglob('*'):
        if any(part in IGNORED_DIRECTORIES for part in
               path.relative_to(project_root).parts):
            continue
        if not path.is_file():
            continue
        name = path.name.lower()
        if (name in SENSITIVE_NAMES or name.startswith('.env.') and
                name != '.env.example' or path.suffix.lower() in
                SENSITIVE_EXTENSIONS or 'outbox' in name and name.endswith('.txt')):
            hits.append(path.relative_to(project_root).as_posix())
    return sorted(hits)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', nargs='?', default='.',
                        help='Repository source root (default: current directory)')
    args = parser.parse_args()
    root = Path(args.directory).resolve()
    if not root.is_dir():
        parser.error('The source root must exist')
    hits = detect_sensitive_files(root)
    if hits:
        print('BLOCKED: remove the following private artifact(s) before publishing:')
        for relative in hits:
            print(f'  {relative}')
        return 1
    print('PASS: no high-risk private artifact names found. Audit git history and secrets separately.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
