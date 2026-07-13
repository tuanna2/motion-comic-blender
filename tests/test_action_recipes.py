import unittest
from pathlib import Path

from motion_comic.action_recipes import expand_action_recipes
from motion_comic.registry import AssetRegistry


ROOT = Path(__file__).resolve().parents[1]


class ActionRecipeTests(unittest.TestCase):
    def test_expands_normalized_recipe_timing(self):
        registry = AssetRegistry(ROOT / "assets").scan()
        scene = {
            "id": "fight",
            "motions": [],
            "recipes": [
                {
                    "recipe": "punch_impact",
                    "actor": "hero",
                    "target": "villain",
                    "start": 2,
                    "end": 4,
                }
            ],
        }
        expanded = expand_action_recipes(scene, registry, "recipes_cinematic@1")
        self.assertNotIn("recipes", expanded)
        self.assertEqual(expanded["motions"][0]["target"], "hero")
        self.assertEqual(expanded["motions"][1]["target"], "villain")
        self.assertGreaterEqual(expanded["motions"][0]["start"], 2)
        self.assertLessEqual(expanded["motions"][-1]["end"], 4)


if __name__ == "__main__":
    unittest.main()
