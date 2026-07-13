import unittest

from motion_comic.easing import (
    choose_render_engine,
    clamp,
    deterministic_shake,
    ease_in_out,
    lerp,
    parabolic_arc,
)


class EasingTests(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual(clamp(-1), 0)
        self.assertEqual(clamp(2), 1)

    def test_lerp(self):
        self.assertEqual(lerp(10, 20, 0.25), 12.5)

    def test_ease_endpoints(self):
        self.assertEqual(ease_in_out(0), 0)
        self.assertEqual(ease_in_out(1), 1)

    def test_arc(self):
        self.assertEqual(parabolic_arc(0, 3), 0)
        self.assertEqual(parabolic_arc(1, 3), 0)
        self.assertEqual(parabolic_arc(0.5, 3), 3)

    def test_shake_is_repeatable(self):
        self.assertEqual(deterministic_shake(5, 0.2), deterministic_shake(5, 0.2))

    def test_engine_selection_supports_blender_4_and_5(self):
        self.assertEqual(
            choose_render_engine({"BLENDER_EEVEE_NEXT", "CYCLES"}),
            "BLENDER_EEVEE_NEXT",
        )
        self.assertEqual(
            choose_render_engine({"BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES"}),
            "BLENDER_EEVEE",
        )

    def test_engine_selection_rejects_unsupported_runtime(self):
        with self.assertRaisesRegex(ValueError, "no supported Blender render engine"):
            choose_render_engine({"CYCLES"})


if __name__ == "__main__":
    unittest.main()
