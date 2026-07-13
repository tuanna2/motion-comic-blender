import json
import tempfile
import unittest
from pathlib import Path

from motion_comic.series import load_series
from motion_comic.ui_render import RenderJobManager


ROOT = Path(__file__).resolve().parents[1]


class UIRenderTests(unittest.TestCase):
    def test_recovers_running_job_as_interrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job_dir = root / "output/ui_jobs/abc123"
            job_dir.mkdir(parents=True)
            (job_dir / "request.json").write_text(
                json.dumps({"storyboard": {}, "options": {}}), encoding="utf-8"
            )
            (job_dir / "job_state.json").write_text(
                json.dumps(
                    {
                        "job_id": "abc123",
                        "status": "running",
                        "stage": "blender",
                        "progress_percent": 48,
                        "current_frame": 100,
                        "total_frames": 200,
                    }
                ),
                encoding="utf-8",
            )
            manager = RenderJobManager(
                root, load_series(ROOT / "series/urban_mystery/series.json")
            )
            job = manager.get("abc123")
            self.assertIsNotNone(job)
            self.assertEqual(job.status, "interrupted")
            self.assertTrue(job.public()["can_resume"])


if __name__ == "__main__":
    unittest.main()
