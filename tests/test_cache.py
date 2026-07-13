import tempfile
import unittest
from pathlib import Path

from motion_comic.cache import cached_artifact, file_digest


class CacheTests(unittest.TestCase):
    def test_content_addressed_artifact_is_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "model.blend"
            source.write_bytes(b"compiled model")
            first = cached_artifact(source, root / "cache")
            second = cached_artifact(source, root / "cache")
            self.assertEqual(first, second)
            self.assertEqual(first.read_bytes(), source.read_bytes())
            self.assertIn(file_digest(source), first.name)


if __name__ == "__main__":
    unittest.main()
