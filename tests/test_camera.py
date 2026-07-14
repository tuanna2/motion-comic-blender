import math
import unittest

from motion_comic.camera import camera_baseline, subtitle_screen_y


class CameraTests(unittest.TestCase):
    def test_sprite_scene_resets_to_center(self):
        baseline = camera_baseline("sprite_2d", 9)
        self.assertEqual(baseline.location, (0.0, 0.0, 20.0))
        self.assertEqual(baseline.ortho_scale, 9)

    def test_mmd_scene_uses_front_facing_coordinate_system(self):
        baseline = camera_baseline("mmd_3d", 9)
        self.assertEqual(baseline.location, (0.0, -18.0, 4.5))
        self.assertAlmostEqual(baseline.rotation[0], math.pi / 2)

    def test_subtitle_coordinates_keep_legacy_mmd_position_in_camera_space(self):
        self.assertAlmostEqual(subtitle_screen_y("sprite_2d", 9), -3.51)
        self.assertAlmostEqual(subtitle_screen_y("mmd_3d", 9), -3.24)
        self.assertAlmostEqual(subtitle_screen_y("mmd_3d", 9, 2.0), -2.5)

    def test_unknown_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported scene mode"):
            camera_baseline("broken", 9)


if __name__ == "__main__":
    unittest.main()
