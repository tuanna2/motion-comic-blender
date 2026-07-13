import unittest
from pathlib import Path

from motion_comic.series import load_series
from motion_comic.story_prompt import build_story_creation_prompt


ROOT = Path(__file__).resolve().parents[1]


class StoryPromptTests(unittest.TestCase):
    def setUp(self):
        self.series = load_series(ROOT / "series/urban_mystery/series.json")

    def test_builds_first_person_prompt_with_exact_word_target(self):
        prompt = build_story_creation_prompt(
            self.series,
            minutes=15,
            genre="trùng sinh, bí ẩn",
            narration_mode="first_person",
            protagonist_id="char_minh_khang",
            premise="Minh Khang tỉnh lại trước vụ cháy.",
        )
        self.assertIn("Target length: 2025-2325 Vietnamese words", prompt)
        self.assertIn("Narrator ID: char_minh_khang", prompt)
        self.assertIn("Minh Khang tỉnh lại trước vụ cháy", prompt)
        self.assertIn('"full_story_text"', prompt)
        self.assertIn('"camera_whip_pan"', prompt)

    def test_third_person_uses_invisible_narrator(self):
        prompt = build_story_creation_prompt(
            self.series,
            minutes=10,
            genre="kinh dị",
            narration_mode="third_person",
            protagonist_id="char_an_nhien",
        )
        self.assertIn("Narrator ID: narrator", prompt)
        self.assertIn('"narration_mode": "third_person"', prompt)

    def test_rejects_duration_outside_supported_range(self):
        with self.assertRaisesRegex(ValueError, "between 10 and 30"):
            build_story_creation_prompt(
                self.series,
                minutes=45,
                genre="bí ẩn",
                narration_mode="first_person",
                protagonist_id="char_minh_khang",
            )


if __name__ == "__main__":
    unittest.main()
