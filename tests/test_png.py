import tempfile
import unittest
from pathlib import Path

from motion_comic.png import canvas, draw_ellipse, write_png


class PngTests(unittest.TestCase):
    def test_writes_rgba_png(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "part.png"
            image = canvas(16, 16)
            draw_ellipse(image, 8, 8, 5, 5, (255, 0, 0, 255))
            write_png(path, image)
            content = path.read_bytes()
            self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertIn(b"IHDR", content)
            self.assertIn(b"IDAT", content)


if __name__ == "__main__":
    unittest.main()

