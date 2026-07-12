import math
import unittest

from motion_comic.camera import camera_baseline


class CameraTests(unittest.TestCase):
    def test_sprite_scene_resets_to_center(self):
        baseline = camera_baseline("sprite_2d", 9)
        self.assertEqual(baseline.location, (0.0, 0.0, 20.0))
        self.assertEqual(baseline.ortho_scale, 9)

    def test_mmd_scene_uses_front_facing_coordinate_system(self):
        baseline = camera_baseline("mmd_3d", 9)
        self.assertEqual(baseline.location, (0.0, -18.0, 5.0))
        self.assertAlmostEqual(baseline.rotation[0], math.pi / 2)

    def test_unknown_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported scene mode"):
            camera_baseline("broken", 9)


if __name__ == "__main__":
    unittest.main()
