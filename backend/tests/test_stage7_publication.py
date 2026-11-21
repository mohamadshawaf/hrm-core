"""Basic GitHub publication hygiene checks (no external services)."""

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_public_artifacts import detect_sensitive_files  # noqa: E402


class PublicationHygieneTests(unittest.TestCase):
    def test_source_snapshot_contains_no_private_data_files(self):
        self.assertEqual(detect_sensitive_files(ROOT), [])

    def test_rejects_untracked_secrets_and_demo_databases(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('LOCAL_ONLY=example', encoding='utf-8')
            (root / 'demo.sqlite3').touch()
            (root / '.env.example').touch()
            (root / 'sample.txt').touch()
            self.assertEqual(detect_sensitive_files(root), ['.env', 'demo.sqlite3'])


if __name__ == '__main__':
    unittest.main()
