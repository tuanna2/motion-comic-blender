import json
import tempfile
import unittest
from pathlib import Path

from motion_comic.registry import AssetRegistry, AssetRegistryError


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write_manifest(self, folder: str, asset_id: str, version: int):
        path = self.root / folder / "manifest.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "id": asset_id,
                    "version": version,
                    "type": "layered_character",
                    "appearances": {"default": {"parts": [{"id": "body", "asset": "body.png"}]}},
                }
            ),
            encoding="utf-8",
        )

    def test_resolves_exact_and_latest_version(self):
        self.write_manifest("hero-v1", "char_hero", 1)
        self.write_manifest("hero-v2", "char_hero", 2)
        registry = AssetRegistry(self.root).scan()
        self.assertEqual(registry.resolve("char_hero@1").version, 1)
        self.assertEqual(registry.resolve("char_hero").version, 2)

    def test_unknown_reference_lists_registered_assets(self):
        self.write_manifest("hero", "char_hero", 1)
        registry = AssetRegistry(self.root).scan()
        with self.assertRaisesRegex(AssetRegistryError, "char_hero@1"):
            registry.resolve("char_missing")

    def test_registers_mmd_character_and_action_library(self):
        character = self.root / "mmd" / "manifest.json"
        character.parent.mkdir(parents=True)
        character.write_text(
            json.dumps(
                {
                    "id": "char_mmd",
                    "version": 1,
                    "type": "mmd_character",
                    "blend": "compiled/char.blend",
                    "collection": "CHARACTER",
                    "armature": "Armature",
                    "action_set": "actions@1",
                    "morphs": {"mouth_open": "あ"},
                }
            ),
            encoding="utf-8",
        )
        actions = self.root / "actions" / "manifest.json"
        actions.parent.mkdir(parents=True)
        actions.write_text(
            json.dumps(
                {
                    "id": "actions",
                    "version": 1,
                    "type": "action_library",
                    "blend": "compiled/actions.blend",
                    "actions": {"idle": {"action": "Idle"}},
                }
            ),
            encoding="utf-8",
        )
        registry = AssetRegistry(self.root).scan()
        self.assertEqual(registry.resolve("char_mmd@1").asset_type, "mmd_character")
        self.assertEqual(registry.resolve("actions@1").asset_type, "action_library")


if __name__ == "__main__":
    unittest.main()
