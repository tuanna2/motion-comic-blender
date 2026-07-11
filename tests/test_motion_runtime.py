import unittest

from motion_comic.action_catalog import ACTION_CATALOG
from motion_comic.motions import apply_motion


class Vector:
    def __init__(self, values=(0.0, 0.0, 0.0)):
        self.x, self.y, self.z = (float(value) for value in values)

    def copy(self):
        return Vector((self.x, self.y, self.z))

    def __iter__(self):
        return iter((self.x, self.y, self.z))


class CameraData:
    def __init__(self):
        self.ortho_scale = 9.0
        self.keyframes = []

    def keyframe_insert(self, *, data_path, frame):
        self.keyframes.append((data_path, frame))


class FakeObject:
    def __init__(self, name):
        self.name = name
        self._location = Vector()
        self._scale = Vector((1, 1, 1))
        self.rotation_euler = Vector()
        self.hide_render = False
        self.animation_data = None
        self.data = CameraData()
        self.keyframes = []

    @property
    def location(self):
        return self._location

    @location.setter
    def location(self, value):
        self._location = value.copy() if isinstance(value, Vector) else Vector(value)

    @property
    def scale(self):
        return self._scale

    @scale.setter
    def scale(self, value):
        self._scale = value.copy() if isinstance(value, Vector) else Vector(value)

    def keyframe_insert(self, *, data_path, frame):
        self.keyframes.append((data_path, frame))


def fake_registry():
    registry = {
        "hero": FakeObject("hero"),
        "rival": FakeObject("rival"),
        "camera": FakeObject("camera"),
    }
    part_ids = (
        "body", "head", "arm_upper", "forearm", "arm_left_upper", "forearm_left",
        "leg_left_upper", "leg_left_lower", "leg_right_upper", "leg_right_lower", "rod",
        "mouth", "mouth_closed", "mouth_open", "eyes_normal", "eyes_angry", "eyes_closed",
        "eyes_sad", "eyes_surprised", "blush", "tears",
    )
    for actor in ("hero", "rival"):
        for part_id in part_ids:
            registry[f"{actor}.{part_id}"] = FakeObject(f"{actor}.{part_id}")
    return registry


class MotionRuntimeTests(unittest.TestCase):
    def test_every_catalog_action_executes_with_a_complete_rig(self):
        failures = {}
        for action_key, spec in ACTION_CATALOG.items():
            registry = fake_registry()
            target = "camera" if spec.category == "camera" else "hero"
            try:
                apply_motion(
                    action_key,
                    registry[target],
                    1,
                    31,
                    {"with": "rival", "follow": "hero", "focus": "rival"},
                    registry=registry,
                    target=target,
                )
            except Exception as exc:  # Report every semantic key in one assertion.
                failures[action_key] = f"{type(exc).__name__}: {exc}"
        self.assertEqual(failures, {})


if __name__ == "__main__":
    unittest.main()
