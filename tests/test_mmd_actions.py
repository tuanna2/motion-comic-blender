import json
import tempfile
import unittest
from pathlib import Path

from motion_comic.mmd_actions import MMDActionError, resolve_mmd_action
from motion_comic.registry import AssetRegistry


ROOT = Path(__file__).resolve().parents[1]


class MMDActionsTests(unittest.TestCase):
    def manifest(self, data):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "manifest.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return AssetRegistry(directory.name).scan().resolve(data["id"])

    def test_resolves_direct_action_and_fallback(self):
        manifest = self.manifest(
            {
                "id": "actions",
                "version": 1,
                "type": "action_library",
                "blend": "actions.blend",
                "actions": {
                    "idle": {"action": "Idle", "loop": True},
                    "walk_fast": {"fallback": "walk"},
                    "walk": {"action": "Walk", "track": "base", "loop": True},
                },
            }
        )
        idle = resolve_mmd_action(manifest, "idle")
        walk = resolve_mmd_action(manifest, "walk_fast")
        self.assertTrue(idle.loop)
        self.assertEqual(walk.blender_action, "Walk")
        self.assertEqual(walk.resolved_key, "walk")

    def test_uses_default_fallback_for_unmapped_semantic_action(self):
        manifest = self.manifest(
            {
                "id": "actions",
                "version": 1,
                "type": "action_library",
                "blend": "actions.blend",
                "default_fallback": "idle",
                "actions": {"idle": {"action": "Idle"}},
            }
        )
        self.assertEqual(resolve_mmd_action(manifest, "cook").blender_action, "Idle")

    def test_rejects_fallback_cycle(self):
        manifest = self.manifest(
            {
                "id": "actions",
                "version": 1,
                "type": "action_library",
                "blend": "actions.blend",
                "actions": {"a": {"fallback": "b"}, "b": {"fallback": "a"}},
            }
        )
        with self.assertRaisesRegex(MMDActionError, "cyclic"):
            resolve_mmd_action(manifest, "a")

    def test_production_facing_actions_use_idle_armature_under_root_turn(self):
        registry = AssetRegistry(ROOT / "assets").scan()
        manifest = registry.resolve("actions_humanoid_mmd@1", "action_library")
        for action in ("turn_left", "turn_right", "turn_around", "face_target", "body_turn"):
            with self.subTest(action=action):
                self.assertEqual(resolve_mmd_action(manifest, action).blender_action, "MMD_Idle")


if __name__ == "__main__":
    unittest.main()
