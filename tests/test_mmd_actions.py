import json
import tempfile
import unittest
from pathlib import Path

from motion_comic.mmd_actions import MMDActionError, resolve_mmd_action
from motion_comic.registry import AssetRegistry


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


if __name__ == "__main__":
    unittest.main()
