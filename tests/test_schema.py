import json
import tempfile
import unittest
from pathlib import Path

from motion_comic.schema import StoryboardError, load_storyboard


class SchemaTests(unittest.TestCase):
    def write_storyboard(self, data):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "storyboard.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_load_minimal_storyboard(self):
        path = self.write_storyboard(
            {
                "version": "1.0",
                "title": "Test",
                "settings": {"fps": 24},
                "scenes": [
                    {
                        "id": "one",
                        "duration": 2,
                        "elements": [{"id": "hero", "kind": "disc"}],
                        "motions": [
                            {"target": "hero", "preset": "idle", "start": 0, "end": 2}
                        ],
                    }
                ],
            }
        )
        storyboard = load_storyboard(path)
        self.assertEqual(storyboard.total_frames, 48)
        self.assertEqual(storyboard.duration_seconds, 2)

    def test_rejects_unknown_target(self):
        path = self.write_storyboard(
            {
                "version": "1.0",
                "scenes": [
                    {
                        "id": "one",
                        "duration": 1,
                        "elements": [],
                        "motions": [
                            {"target": "missing", "preset": "idle", "start": 0, "end": 1}
                        ],
                    }
                ],
            }
        )
        with self.assertRaisesRegex(StoryboardError, "unknown motion target"):
            load_storyboard(path)

    def test_rejects_motion_outside_scene(self):
        path = self.write_storyboard(
            {
                "version": "1.0",
                "scenes": [
                    {
                        "id": "one",
                        "duration": 1,
                        "elements": [{"id": "hero", "kind": "disc"}],
                        "motions": [
                            {"target": "hero", "preset": "idle", "start": 0, "end": 2}
                        ],
                    }
                ],
            }
        )
        with self.assertRaisesRegex(StoryboardError, "ends after scene duration"):
            load_storyboard(path)

    def test_character_requires_asset_ref(self):
        path = self.write_storyboard(
            {
                "version": "1.0",
                "scenes": [
                    {
                        "id": "one",
                        "duration": 1,
                        "elements": [{"id": "hero", "kind": "character"}],
                    }
                ],
            }
        )
        with self.assertRaisesRegex(StoryboardError, "character asset_ref is required"):
            load_storyboard(path)

    def test_attachment_target_must_exist(self):
        path = self.write_storyboard(
            {
                "version": "1.0",
                "scenes": [
                    {
                        "id": "one",
                        "duration": 1,
                        "elements": [
                            {
                                "id": "hat",
                                "kind": "prop",
                                "asset_ref": "prop_hat@1",
                                "attach": {"target": "missing", "anchor": "head"},
                            }
                        ],
                    }
                ],
            }
        )
        with self.assertRaisesRegex(StoryboardError, "attachment target 'missing' does not exist"):
            load_storyboard(path)


if __name__ == "__main__":
    unittest.main()
