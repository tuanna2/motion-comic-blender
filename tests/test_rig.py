import unittest

from motion_comic.rig import RigError, order_rig_parts


class RigTests(unittest.TestCase):
    def test_orders_parent_before_child(self):
        parts = [
            {"id": "hand", "parent": "arm", "asset": "hand.png"},
            {"id": "body", "joint": [0, 1], "asset": "body.png"},
            {"id": "arm", "parent": "body", "joint": [1, 0], "asset": "arm.png"},
        ]
        ordered = order_rig_parts(parts)
        self.assertEqual([part["id"] for part in ordered], ["body", "arm", "hand"])

    def test_rejects_cycle(self):
        with self.assertRaisesRegex(RigError, "cyclic"):
            order_rig_parts(
                [
                    {"id": "a", "parent": "b", "joint": [0, 0]},
                    {"id": "b", "parent": "a", "joint": [0, 0]},
                ]
            )

    def test_rejects_non_controller_parent(self):
        with self.assertRaisesRegex(RigError, "must define a joint controller"):
            order_rig_parts(
                [
                    {"id": "head", "asset": "head.png"},
                    {"id": "eye", "parent": "head", "asset": "eye.png"},
                ]
            )


if __name__ == "__main__":
    unittest.main()

