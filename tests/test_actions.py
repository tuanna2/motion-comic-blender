import json
import tempfile
import unittest
from pathlib import Path

from motion_comic.action_catalog import ACTION_CATALOG, CATEGORY_KEYS, resolve_action
from motion_comic.motions import PRESETS
from motion_comic.schema import StoryboardError, load_storyboard


class ActionCatalogTests(unittest.TestCase):
    def test_catalog_covers_all_production_categories(self):
        self.assertGreaterEqual(len(ACTION_CATALOG), 300)
        self.assertEqual(
            set(CATEGORY_KEYS),
            {
                "locomotion", "pose", "gesture", "interaction", "dialogue",
                "positive_emotion", "negative_emotion", "sad_emotion", "fear_emotion",
                "thinking", "fight", "daily", "comic", "camera", "effect",
            },
        )

    def test_every_action_resolves_to_an_implemented_handler(self):
        missing = {
            key: spec.handler
            for key, spec in ACTION_CATALOG.items()
            if spec.handler not in PRESETS
        }
        self.assertEqual(missing, {})

    def test_representative_actions_resolve_to_expected_categories(self):
        expected = {
            "sprint": "locomotion",
            "cross_arms": "pose",
            "wipe_tears": "gesture",
            "hug": "interaction",
            "talk_angry": "dialogue",
            "cry": "sad_emotion",
            "punch": "fight",
            "use_phone": "daily",
            "reaction_pop": "comic",
            "camera_whip_pan": "camera",
            "impact_flash": "effect",
        }
        self.assertEqual({key: resolve_action(key).category for key in expected}, expected)

    def test_storyboard_accepts_action_field(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "storyboard.json"
        path.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "scenes": [
                        {
                            "id": "one",
                            "duration": 2,
                            "elements": [{"id": "hero", "kind": "disc"}],
                            "motions": [
                                {"target": "hero", "action": "sprint", "start": 0, "end": 2}
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        storyboard = load_storyboard(path)
        self.assertEqual(storyboard.scenes[0]["motions"][0]["action"], "sprint")

    def test_rejects_conflicting_action_and_preset(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "storyboard.json"
        path.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "scenes": [
                        {
                            "id": "one",
                            "duration": 1,
                            "elements": [{"id": "hero", "kind": "disc"}],
                            "motions": [
                                {
                                    "target": "hero",
                                    "action": "walk",
                                    "preset": "run",
                                    "start": 0,
                                    "end": 1,
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(StoryboardError, "different action and preset"):
            load_storyboard(path)


if __name__ == "__main__":
    unittest.main()
