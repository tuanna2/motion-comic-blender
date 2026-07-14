import unittest
from pathlib import Path

from motion_comic.compiler import EpisodeCompileError, compile_episode_plan
from motion_comic.series import load_series


ROOT = Path(__file__).resolve().parents[1]


class CompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.series = load_series(ROOT / "series/urban_mystery/series.json")

    def plan(self):
        return {
            "version": "1.0",
            "title": "Đêm trong hẻm",
            "scenes": [
                {
                    "id": "beat_0001",
                    "location_id": "urban_alley",
                    "characters": ["char_minh_khang", "char_an_nhien"],
                    "speech": [
                        {
                            "speaker": "char_minh_khang",
                            "text": "Tôi nghe tiếng bước chân phía sau.",
                            "narration": True,
                        },
                        {
                            "speaker": "char_an_nhien",
                            "text": "Đừng quay lại.",
                            "narration": False,
                        },
                    ],
                    "visual_beats": [
                        {
                            "actor": "char_minh_khang",
                            "recipe": "dramatic_reveal",
                            "start": 0,
                            "duration": 2.5,
                        }
                    ],
                }
            ],
        }

    def test_compiles_assets_voices_layout_space_and_recipe(self):
        storyboard = compile_episode_plan(
            self.plan(), self.series, asset_root=ROOT / "assets"
        )
        self.assertEqual(storyboard["settings"]["scene_mode"], "mmd_3d")
        scene = storyboard["scenes"][0]
        self.assertEqual(scene["template_ref"], "scene_urban_alley@1")
        self.assertNotIn("recipes", scene)
        self.assertTrue(any(item["action"] == "reaction_pop" for item in scene["motions"]))
        self.assertEqual(scene["elements"][0]["asset_ref"], "char_minh_khang@1")
        self.assertEqual(scene["elements"][0]["slot"], "auto")
        self.assertEqual(scene["subtitles"][1]["voice"], "vi-VN-HoaiMyNeural")
        self.assertTrue(scene["subtitles"][1]["lip_sync"])
        facing = [item for item in scene["motions"] if item["action"] == "face_target"]
        self.assertEqual(len(facing), 2)
        self.assertEqual(
            {(item["target"], item["params"]["target"]) for item in facing},
            {
                ("char_minh_khang", "char_an_nhien"),
                ("char_an_nhien", "char_minh_khang"),
            },
        )

    def test_rejects_unknown_location(self):
        plan = self.plan()
        plan["scenes"][0]["location_id"] = "moon"
        with self.assertRaisesRegex(EpisodeCompileError, "unknown location_id"):
            compile_episode_plan(plan, self.series, asset_root=ROOT / "assets")

    def test_rejects_dialogue_listener_not_visible_in_scene(self):
        plan = self.plan()
        plan["scenes"][0]["speech"][1]["listener"] = "char_tran_vu"
        with self.assertRaisesRegex(EpisodeCompileError, "dialogue listener"):
            compile_episode_plan(plan, self.series, asset_root=ROOT / "assets")


if __name__ == "__main__":
    unittest.main()
