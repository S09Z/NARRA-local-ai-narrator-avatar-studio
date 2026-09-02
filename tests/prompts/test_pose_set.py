#!/usr/bin/env python3
"""Pins the real PHASE 5 pose prompt set in prompts/poses/."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMPILE = REPO / "scripts" / "generation" / "compile_prompt.py"
POSE_DIR = REPO / "prompts" / "poses"

sys.path.insert(0, str(REPO / "scripts" / "lib"))
import canon  # noqa: E402

# ASSET_SPEC 8 / visual-spec 2: hands must be fully in frame in these classes.
HANDS_IN_FRAME = {"upper-body", "three-quarter"}
GESTURE_POSES = {"pointing-left", "pointing-right", "presenting", "excited", "confident"}


def compile_pose(name):
    result = subprocess.run(
        [sys.executable, str(COMPILE), f"poses/{name}-v1.0.md", "--json"],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(f"{name} failed to compile: {result.stderr}")
    return json.loads(result.stdout)


class PoseSetTest(unittest.TestCase):

    def test_every_canonical_pose_has_a_prompt(self):
        for name in canon.POSES:
            with self.subTest(pose=name):
                self.assertTrue((POSE_DIR / f"{name}-v1.0.md").exists())

    def test_there_are_no_extra_prompt_files(self):
        stems = {path.stem.rsplit("-v", 1)[0] for path in POSE_DIR.glob("*.md")}
        self.assertEqual(stems, set(canon.POSES))

    def test_seeds_are_the_canonical_index(self):
        for index, name in enumerate(canon.POSES):
            with self.subTest(pose=name):
                self.assertEqual(compile_pose(name)["seed"], 30000 + index)

    def test_every_pose_declares_a_valid_camera_class(self):
        for name in canon.POSES:
            with self.subTest(pose=name):
                self.assertIn(compile_pose(name)["camera_class"], canon.CAMERA_CLASSES)

    def test_gesture_poses_use_a_hands_in_frame_class(self):
        # A hand cropped at the wrist is the most common pose failure
        # (PROMPT_GUIDE 7). Poses with visible hands must be framed for them.
        for name in GESTURE_POSES:
            with self.subTest(pose=name):
                self.assertIn(compile_pose(name)["camera_class"], HANDS_IN_FRAME)

    def test_every_pose_preserves_the_face(self):
        for name in canon.POSES:
            with self.subTest(pose=name):
                compiled = compile_pose(name)["compiled"]
                kept = [line for line in compiled.splitlines()
                        if "Keep the same person" in line][0]
                for feature in ("face shape", "eye shape and position", "eyebrows",
                                "mouth shape and position", "hairstyle"):
                    self.assertIn(feature, kept)

    def test_pose_preservation_releases_the_camera(self):
        for name in canon.POSES:
            with self.subTest(pose=name):
                kept = [line for line in compile_pose(name)["compiled"].splitlines()
                        if "Keep the same person" in line][0]
                self.assertNotIn("camera framing", kept)

    def test_pose_negatives_omit_the_framing_group(self):
        # A pose changes camera class by design; those negatives would fight it.
        for name in canon.POSES:
            with self.subTest(pose=name):
                negative = compile_pose(name)["negative"]
                self.assertNotIn("changed camera distance", negative)
                self.assertIn("different person", negative)

    def test_every_pose_has_both_a_pose_and_a_camera_block(self):
        for name in canon.POSES:
            with self.subTest(pose=name):
                compiled = compile_pose(name)["compiled"]
                self.assertIn("POSE:", compiled)
                self.assertIn("CAMERA:", compiled)

    def test_pose_bodies_are_distinct(self):
        bodies = {}
        for name in canon.POSES:
            block = [c for c in compile_pose(name)["compiled"].split("\n\n")
                     if c.startswith("POSE:")][0]
            self.assertNotIn(block, bodies,
                             f"{name} has the same POSE block as {bodies.get(block)}")
            bodies[block] = name

    def test_pointing_poses_are_described_as_mirrors(self):
        right = (POSE_DIR / "pointing-right-v1.0.md").read_text()
        self.assertIn("mirror of pointing-left", right)

    def test_medium_poses_keep_hands_out_of_frame(self):
        for name in canon.POSES:
            if compile_pose(name)["camera_class"] != "medium":
                continue
            with self.subTest(pose=name):
                compiled = compile_pose(name)["compiled"]
                self.assertIn("below the frame edge", compiled)


if __name__ == "__main__":
    unittest.main()
