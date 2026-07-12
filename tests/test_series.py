import json
import tempfile
import unittest
from pathlib import Path

from motion_comic.series import SUPPORTED_VI_VOICES, load_series, validate_story_source


ROOT = Path(__file__).resolve().parents[1]
SERIES_PATH = ROOT / "series/urban_mystery/series.json"


class SeriesTests(unittest.TestCase):
    def test_loads_five_distinct_main_characters(self):
        series = load_series(SERIES_PATH)
        self.assertEqual(series.series_id, "urban_mystery")
        self.assertEqual(len(series.characters), 5)
        self.assertEqual(series.data["story_rules"]["default_protagonist_id"], "char_minh_khang")
        primary_colors = [item["visual"]["palette"][0] for item in series.data["characters"]]
        self.assertEqual(len(primary_colors), len(set(primary_colors)))

    def test_all_character_voices_are_supported_and_profiles_are_distinct(self):
        series = load_series(SERIES_PATH)
        signatures = []
        for character in series.data["characters"]:
            voice = character["voice_profiles"]["dialogue"]
            self.assertIn(voice["voice"], SUPPORTED_VI_VOICES)
            signatures.append((voice["voice"], voice["rate"], voice["volume"], voice["pitch"]))
        self.assertEqual(len(signatures), len(set(signatures)))

    def test_validates_ai_story_source(self):
        series = load_series(SERIES_PATH)
        text = " ".join(["Tôi bước vào căn phòng và nghe An Nhiên gọi tên mình."] * 160)
        result = validate_story_source(
            {
                "version": "1.0",
                "series_id": "urban_mystery",
                "title": "Căn phòng không có cửa",
                "narration_mode": "first_person",
                "narrator_character_id": "char_minh_khang",
                "estimated_minutes": 10,
                "characters_used": ["char_minh_khang", "char_an_nhien"],
                "full_story_text": text,
            },
            series,
        )
        self.assertTrue(result.valid)
        self.assertGreater(result.word_count, 1000)

    def test_rejects_unknown_character_from_ai(self):
        series = load_series(SERIES_PATH)
        result = validate_story_source(
            {
                "version": "1.0",
                "series_id": "urban_mystery",
                "title": "Test",
                "narration_mode": "first_person",
                "narrator_character_id": "char_minh_khang",
                "estimated_minutes": 10,
                "characters_used": ["char_someone_new"],
                "full_story_text": "nội dung " * 300,
            },
            series,
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("unknown IDs" in error for error in result.errors))

    def test_schema_files_are_valid_json(self):
        for path in (ROOT / "schemas/series.schema.json", ROOT / "schemas/story_source.schema.json"):
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)


if __name__ == "__main__":
    unittest.main()
