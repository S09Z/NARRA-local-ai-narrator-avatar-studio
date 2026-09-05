#!/usr/bin/env python3
"""Tests for scripts/audio/build_timeline.py and tts.py (PHASE 7.1, end to end).

These drive the CLIs the way a person would. The `silence` engine exists so that this
file passes on any platform: `say` is macOS-only, and a test suite that only runs on
the machine that happened to write it is not a test suite.
"""

import json
import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILD = REPO / "scripts" / "audio" / "build_timeline.py"
TTS = REPO / "scripts" / "audio" / "tts.py"
VALIDATE = REPO / "scripts" / "validation" / "validate_timeline.py"

sys.path.insert(0, str(REPO / "scripts" / "lib"))
import audioinfo  # noqa: E402


def run(script, *args):
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True)


class TTSTest(unittest.TestCase):

    def test_list_runs_anywhere(self):
        result = run(TTS, "--list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("silence", json.loads(result.stdout)["engines"])

    def test_silence_engine_produces_a_readable_wav(self):
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / "a.wav"
            result = run(TTS, "สวัสดีครับ", "-o", str(out), "--engine", "silence")
            self.assertEqual(result.returncode, 0, result.stderr)
            info = audioinfo.wav_info(out)
            self.assertGreater(info["duration"], 0)
            self.assertEqual(audioinfo.format_problems(info), [])

    def test_silence_engine_is_deterministic(self):
        result = run(TTS, "สวัสดีครับ", "--engine", "silence", "--check-determinism")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("deterministic", result.stdout)

    def test_empty_text_fails(self):
        with tempfile.TemporaryDirectory() as work:
            result = run(TTS, "   ", "-o", str(Path(work) / "a.wav"),
                         "--engine", "silence")
            self.assertEqual(result.returncode, 1)

    @unittest.skipUnless(platform.system() == "Darwin", "say is macOS only")
    def test_say_engine_is_deterministic(self):
        """PLAN 7.1 asks for deterministic output where possible."""
        result = run(TTS, "สวัสดีครับ", "--engine", "say", "--check-determinism")
        if "no Thai voice" in result.stderr:
            self.skipTest("no Thai voice installed")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("deterministic", result.stdout)


class ReportTest(unittest.TestCase):

    def test_report_shows_the_parse(self):
        result = run(BUILD, "สวัสดีครับ", "--report")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("sa wat̚ diː kʰrap̚", result.stdout)
        self.assertIn("coverage", result.stdout)

    def test_report_writes_nothing(self):
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / "t.json"
            run(BUILD, "สวัสดีครับ", "--report", "--out", str(out))
            self.assertFalse(out.exists())


class BuildTest(unittest.TestCase):

    def build(self, work, *extra):
        out = Path(work) / "t.json"
        result = run(BUILD, "สวัสดีครับ ผมชื่อนารา", "--out", str(out), *extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        return out, json.loads(out.read_text(encoding="utf-8"))

    def test_builds_an_estimated_timeline_without_audio(self):
        with tempfile.TemporaryDirectory() as work:
            _, payload = self.build(work)
            self.assertEqual(payload["timing_source"], "estimated")
            self.assertTrue(payload["events"])

    def test_fits_to_supplied_audio(self):
        with tempfile.TemporaryDirectory() as work:
            wav = audioinfo.write_silence(Path(work) / "a.wav", 2.5)
            _, payload = self.build(work, "--audio", str(wav))
            self.assertEqual(payload["timing_source"], "fitted")
            self.assertAlmostEqual(payload["duration"], 2.5, delta=0.01)
            self.assertEqual(payload["audio"]["sha256"], audioinfo.sha256(wav))

    def test_tts_and_audio_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as work:
            result = run(BUILD, "นารา", "--out", str(Path(work) / "t.json"),
                         "--tts", "--audio", "x.wav")
            self.assertEqual(result.returncode, 2)

    def test_output_validates(self):
        """The two halves of the pipeline agree about what a timeline is."""
        with tempfile.TemporaryDirectory() as work:
            out, _ = self.build(work)
            result = run(VALIDATE, str(out))
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_rebuild_is_reproducible(self):
        with tempfile.TemporaryDirectory() as work:
            _, first = self.build(work)
            _, second = self.build(work)
            self.assertEqual(first["digest"], second["digest"])


if __name__ == "__main__":
    unittest.main()
