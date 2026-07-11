import unittest
from pathlib import Path

from motion_comic.encoding import ffmpeg_command


class EncodingTests(unittest.TestCase):
    def test_ffmpeg_command_builds_h264_mp4(self):
        command = ffmpeg_command(
            "/opt/homebrew/bin/ffmpeg",
            Path("/tmp/frames/frame_%04d.png"),
            30,
            Path("/tmp/demo.mp4"),
        )
        self.assertEqual(command[0], "/opt/homebrew/bin/ffmpeg")
        self.assertIn("libx264", command)
        self.assertIn("yuv420p", command)
        self.assertIn("/tmp/frames/frame_%04d.png", command)
        self.assertEqual(command[-1], "/tmp/demo.mp4")


if __name__ == "__main__":
    unittest.main()
