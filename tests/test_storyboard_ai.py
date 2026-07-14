import unittest
from pathlib import Path

from motion_comic.series import load_series
from motion_comic.storyboard_ai import (
    build_storyboard_creation_prompt,
    prepare_storyboard_for_render,
    validate_storyboard_payload,
)


ROOT = Path(__file__).resolve().parents[1]


class StoryboardAITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.series = load_series(ROOT / "series/urban_mystery/series.json")
        cls.story = {
            "version": "1.0",
            "series_id": "urban_mystery",
            "title": "Tập thử",
            "narration_mode": "first_person",
            "narrator_character_id": "char_minh_khang",
            "estimated_minutes": 10,
            "characters_used": ["char_minh_khang"],
            "logline": "Một tập thử.",
            "full_story_text": ("Tôi bước vào hành lang và nhìn thấy cánh cửa. " * 80).strip(),
        }

    def storyboard(self):
        return {
            "version": "1.0",
            "title": "Tập thử",
            "settings": {
                "width": 1280,
                "height": 720,
                "fps": 30,
                "world_height": 9,
                "asset_library": "assets",
            },
            "scenes": [
                {
                    "id": "beat_0001",
                    "duration": 5,
                    "elements": [
                        {
                            "id": "char_minh_khang",
                            "kind": "disc",
                            "x": 0,
                            "y": 0,
                            "z": 1,
                        }
                    ],
                    "motions": [
                        {
                            "target": "char_minh_khang",
                            "action": "think",
                            "start": 0,
                            "end": 2,
                            "params": {},
                        }
                    ],
                    "subtitles": [
                        {
                            "start": 0,
                            "end": 4.8,
                            "text": "Tôi bước vào hành lang và nhìn thấy cánh cửa.",
                            "speaker": "char_minh_khang",
                            "lip_sync": False,
                        }
                    ],
                }
            ],
        }

    def test_builds_renderer_prompt(self):
        prompt = build_storyboard_creation_prompt(self.story, self.series)
        self.assertIn("ALLOWED_ACTIONS", prompt)
        self.assertIn("char_minh_khang@1", prompt)
        self.assertIn("full_story_text", prompt)

    def test_validates_renderer_storyboard(self):
        result = validate_storyboard_payload(
            self.storyboard(),
            self.series,
            story_source=self.story,
            asset_root=ROOT / "assets",
        )
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.scene_count, 1)
        self.assertEqual(result.subtitle_count, 1)

    def test_keeps_registered_mmd_character_asset_for_preview(self):
        storyboard = self.storyboard()
        storyboard["scenes"][0]["elements"][0] = {
            "id": "char_minh_khang",
            "kind": "character",
            "asset_ref": "char_minh_khang@1",
            "x": 0,
            "y": -3,
            "z": 1,
        }
        prepared, warnings = prepare_storyboard_for_render(
            storyboard,
            asset_root=ROOT / "assets",
            placeholder_missing_assets=True,
        )
        self.assertEqual(
            prepared["scenes"][0]["elements"][0]["asset_ref"],
            "char_minh_khang@1",
        )
        self.assertFalse(warnings)


if __name__ == "__main__":
    unittest.main()
