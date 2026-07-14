import math
import unittest

from motion_comic.facing import FacingError, animate_root_facing, yaw_toward


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class Root:
    def __init__(self, x=0.0, y=0.0, yaw=0.0):
        self.location = Vector(x, y, 0)
        self.rotation_euler = Vector(0, 0, yaw)
        self.keyframes = []

    def keyframe_insert(self, *, data_path, frame):
        self.keyframes.append((data_path, frame, self.rotation_euler.z))


class FacingTests(unittest.TestCase):
    def test_yaw_toward_uses_mmd_negative_y_forward_axis(self):
        source = Root()
        self.assertAlmostEqual(yaw_toward(source, Root(x=2)), math.pi / 2)
        self.assertAlmostEqual(yaw_toward(source, Root(x=-2)), -math.pi / 2)

    def test_turn_around_rotates_root_and_holds_direction(self):
        root = Root()
        final = animate_root_facing(
            root,
            "turn_around",
            1,
            16,
            {"direction": "clockwise", "hold": True},
            registry={},
        )
        self.assertAlmostEqual(final, -math.pi)
        self.assertAlmostEqual(root.rotation_euler.z, -math.pi)
        self.assertEqual([item[1] for item in root.keyframes], [1, 16])

    def test_face_target_turns_each_root_to_the_other(self):
        left = Root(x=-3)
        right = Root(x=3)
        registry = {"left": left, "right": right}
        animate_root_facing(
            left, "face_target", 1, 12, {"target": "right"}, registry=registry
        )
        animate_root_facing(
            right, "face_target", 1, 12, {"target": "left"}, registry=registry
        )
        self.assertAlmostEqual(left.rotation_euler.z, math.pi / 2)
        self.assertAlmostEqual(right.rotation_euler.z, -math.pi / 2)

    def test_face_target_rejects_missing_character(self):
        with self.assertRaisesRegex(FacingError, "cannot resolve"):
            animate_root_facing(
                Root(), "face_target", 1, 12, {"target": "missing"}, registry={}
            )


if __name__ == "__main__":
    unittest.main()
