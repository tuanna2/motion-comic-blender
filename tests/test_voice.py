import json
import tempfile
import unittest
from pathlib import Path

from motion_comic.schema import load_storyboard
from motion_comic.voice import (
    EDGE_TTS_TICKS_PER_SECOND,
    collect_voice_lines,
    ffmpeg_mix_command,
    word_boundaries_to_cues,
)


class VoiceTests(unittest.TestCase):
    def storyboard(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "storyboard.json"
        path.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "settings": {"tts": {"voice": "vi-VN-HoaiMyNeural", "rate": "+5%"}},
                    "scenes": [
                        {
                            "id": "one",
                            "duration": 2,
                            "elements": [{"id": "hero", "kind": "disc"}],
                            "subtitles": [
                                {
                                    "text": "Xin chào",
                                    "speaker": "hero",
                                    "start": 0.5,
                                    "end": 1.8,
                                }
                            ],
                        },
                        {"id": "two", "duration": 3, "elements": []},
                    ],
                }
            ),
            encoding="utf-8",
        )
        return load_storyboard(path)

    def test_collects_voice_lines_with_global_timeline(self):
        lines = collect_voice_lines(self.storyboard())
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].target, "hero")
        self.assertEqual(lines[0].global_start, 0.5)
        self.assertEqual(lines[0].rate, "+5%")
        self.assertEqual(len(lines[0].cache_key), 24)

    def test_converts_edge_word_boundaries_to_cues(self):
        line = collect_voice_lines(self.storyboard())[0]
        cues = word_boundaries_to_cues(
            line,
            [
                {
                    "offset": int(0.1 * EDGE_TTS_TICKS_PER_SECOND),
                    "duration": int(0.3 * EDGE_TTS_TICKS_PER_SECOND),
                    "text": "Xin",
                }
            ],
        )
        self.assertEqual(cues[0]["target"], "hero")
        self.assertAlmostEqual(cues[0]["start"], 0.6)
        self.assertAlmostEqual(cues[0]["end"], 0.816)

    def test_builds_delayed_audio_mix(self):
        command = ffmpeg_mix_command(
            "ffmpeg",
            [(Path("one.mp3"), 500), (Path("two.mp3"), 2200)],
            5.0,
            Path("voice.wav"),
        )
        filters = command[command.index("-filter_complex") + 1]
        self.assertIn("adelay=500:all=1", filters)
        self.assertIn("adelay=2200:all=1", filters)
        self.assertIn("amix=inputs=2", filters)
        self.assertIn("atrim=0:5.000", filters)


if __name__ == "__main__":
    unittest.main()
