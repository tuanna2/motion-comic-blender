import json
import tempfile
import unittest
from pathlib import Path

from motion_comic.lipsync import LipCue, LipSyncError, cue_frame_range, load_lip_sync


class LipSyncTests(unittest.TestCase):
    def write(self, data):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "lip_sync.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_loads_and_sorts_cues(self):
        path = self.write(
            {
                "version": "1.0",
                "scenes": {
                    "one": [
                        {"target": "hero", "start": 0.8, "end": 1.0},
                        {"target": "hero", "start": 0.2, "end": 0.4},
                    ]
                },
            }
        )
        cues = load_lip_sync(path)["one"]
        self.assertEqual([cue.start for cue in cues], [0.2, 0.8])

    def test_converts_scene_seconds_to_absolute_frames(self):
        cue = LipCue(target="hero", start=0.5, end=0.8)
        self.assertEqual(cue_frame_range(cue, 61, 180, 30), (76, 85))

    def test_rejects_invalid_range(self):
        path = self.write(
            {
                "version": "1.0",
                "scenes": {"one": [{"target": "hero", "start": 1, "end": 0.5}]},
            }
        )
        with self.assertRaisesRegex(LipSyncError, "invalid cue range"):
            load_lip_sync(path)


if __name__ == "__main__":
    unittest.main()
