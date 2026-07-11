import unittest
from pathlib import Path

from motion_comic.layout import LayoutError, resolve_scene_elements
from motion_comic.registry import AssetManifest


def scene_template():
    return AssetManifest(
        asset_id="scene_test",
        version=1,
        asset_type="scene_template",
        path=Path("/tmp/scene/manifest.json"),
        data={
            "type": "scene_template",
            "auto_order": ["left", "right"],
            "slots": {
                "left": {"x": -3, "y": -2, "scale": 0.8},
                "right": {"x": 3, "y": -2, "scale": 0.8},
            },
            "anchors": {"water": {"x": 2, "y": -1, "z": 3}},
        },
    )


class LayoutTests(unittest.TestCase):
    def test_auto_layout_uses_next_free_slot(self):
        elements = [
            {"id": "a", "kind": "character", "slot": "auto"},
            {"id": "b", "kind": "character", "slot": "auto"},
        ]
        resolved = resolve_scene_elements(elements, scene_template())
        self.assertEqual(resolved[0]["_resolved_slot"], "left")
        self.assertEqual(resolved[1]["_resolved_slot"], "right")
        self.assertEqual(resolved[0]["x"], -3)
        self.assertEqual(resolved[1]["x"], 3)

    def test_explicit_transform_overrides_slot_default(self):
        resolved = resolve_scene_elements(
            [{"id": "a", "kind": "character", "slot": "left", "x": -4.5}],
            scene_template(),
        )
        self.assertEqual(resolved[0]["x"], -4.5)
        self.assertEqual(resolved[0]["y"], -2)

    def test_scene_anchor_resolves_position(self):
        resolved = resolve_scene_elements(
            [{"id": "fish", "kind": "fish", "scene_anchor": "water"}],
            scene_template(),
        )
        self.assertEqual((resolved[0]["x"], resolved[0]["y"], resolved[0]["z"]), (2, -1, 3))

    def test_duplicate_slot_is_rejected(self):
        with self.assertRaisesRegex(LayoutError, "already occupied"):
            resolve_scene_elements(
                [
                    {"id": "a", "kind": "character", "slot": "left"},
                    {"id": "b", "kind": "character", "slot": "left"},
                ],
                scene_template(),
            )

    def test_slot_requires_template(self):
        with self.assertRaisesRegex(LayoutError, "require scene template_ref"):
            resolve_scene_elements([{"id": "a", "kind": "character", "slot": "auto"}], None)


if __name__ == "__main__":
    unittest.main()

