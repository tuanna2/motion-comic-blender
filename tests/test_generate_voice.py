import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from motion_comic.voice import VoiceLine
from scripts.generate_voice import synthesize_line


class FakeCommunicate:
    calls = 0

    def __init__(self, text, voice, *, rate, volume, pitch):
        self.text = text
        self.voice = voice

    async def stream(self):
        type(self).calls += 1
        yield {"type": "audio", "data": b"fake-mp3"}
        yield {
            "type": "WordBoundary",
            "offset": 1_000_000,
            "duration": 2_000_000,
            "text": "Xin",
        }


class GenerateVoiceTests(unittest.TestCase):
    def test_synthesizes_and_reuses_cached_line(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        line = VoiceLine(
            scene_id="one",
            subtitle_index=0,
            target="hero",
            text="Xin chào",
            start=0.5,
            end=1.5,
            global_start=0.5,
            scene_duration=2.0,
            voice="vi-VN-HoaiMyNeural",
            rate="+0%",
            volume="+0%",
            pitch="+0Hz",
        )
        FakeCommunicate.calls = 0
        fake_module = SimpleNamespace(Communicate=FakeCommunicate)
        with patch.dict(sys.modules, {"edge_tts": fake_module}):
            audio, boundaries = asyncio.run(
                synthesize_line(line, Path(directory.name), retries=0, force=False)
            )
            cached_audio, cached_boundaries = asyncio.run(
                synthesize_line(line, Path(directory.name), retries=0, force=False)
            )

        self.assertEqual(FakeCommunicate.calls, 1)
        self.assertEqual(audio.read_bytes(), b"fake-mp3")
        self.assertEqual(audio, cached_audio)
        self.assertEqual(boundaries, cached_boundaries)
        metadata = json.loads(audio.with_suffix(".json").read_text(encoding="utf-8"))
        self.assertEqual(metadata[0]["text"], "Xin")


if __name__ == "__main__":
    unittest.main()
