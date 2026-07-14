import json
import tempfile
import unittest
from pathlib import Path

from motion_comic.batch import BatchError, build_job_commands, empty_status, load_batch


class BatchTests(unittest.TestCase):
    def batch_fixture(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        storyboard = root / "episode.json"
        storyboard.write_text("{}", encoding="utf-8")
        manifest = root / "batch.json"
        manifest.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "output_dir": "output",
                    "cache_dir": "cache",
                    "retries": 2,
                    "episodes": [
                        {
                            "id": "ep-01",
                            "storyboard": "episode.json",
                            "voice": True,
                            "save_blend": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return load_batch(manifest)

    def test_loads_batch_and_builds_voice_render_commands(self):
        plan = self.batch_fixture()
        job = plan.jobs[0]
        commands = build_job_commands(
            plan,
            job,
            python_bin="python3",
            blender_bin="blender",
            project_root=Path("/project"),
        )
        self.assertEqual(plan.retries, 2)
        self.assertEqual(len(commands), 2)
        self.assertIn("generate_voice.py", " ".join(commands[0]))
        self.assertIn("--lip-sync", commands[1])
        self.assertIn("--save-blend", commands[1])

    def test_empty_status_contains_pending_episode(self):
        plan = self.batch_fixture()
        status = empty_status(plan)
        self.assertEqual(status["episodes"]["ep-01"]["state"], "pending")

    def test_rejects_duplicate_job_id(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / "episode.json").write_text("{}", encoding="utf-8")
        manifest = root / "batch.json"
        manifest.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "episodes": [
                        {"id": "same", "storyboard": "episode.json"},
                        {"id": "same", "storyboard": "episode.json"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(BatchError, "duplicate"):
            load_batch(manifest)

    def test_episode_plan_adds_compile_step(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / "plan.json").write_text("{}", encoding="utf-8")
        manifest = root / "batch.json"
        manifest.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "episodes": [{"id": "planned", "episode_plan": "plan.json"}],
                }
            ),
            encoding="utf-8",
        )
        plan = load_batch(manifest)
        commands = build_job_commands(
            plan,
            plan.jobs[0],
            python_bin="python3",
            blender_bin="blender",
            project_root=Path("/project"),
        )
        self.assertEqual(len(commands), 3)
        self.assertIn("compile_episode.py", " ".join(commands[0]))
        self.assertIn(".compiled", " ".join(commands[1]))


if __name__ == "__main__":
    unittest.main()
