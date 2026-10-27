# SPDX-License-Identifier: MIT
"""Batch processing: single file, folder, broken input, missing config, unsupported formats, exit codes.

These tests start real Blender sub-processes (the same way start_export.bat does),
so they are marked @slow. A quick in-process test covers argument handling.
"""

import json
import os
import shutil
import subprocess
import sys
import unittest

import bpy

from tests.helpers import BlenderTestCase, REPO_ROOT, slow, quick_config
from scripts import generate_test_scenes as gen
from scripts import batch_export
from blender_lightmap_export import api

BATCH = os.path.join(REPO_ROOT, "scripts", "batch_export.py")
BAT = os.path.join(REPO_ROOT, "start_export.bat")
FAST = ["--set", "bake.resolution=256", "--set", "bake.samples=4", "--set", "bake.denoise=false",
        "--set", "uv.island_margin_px=2", "--set", "bake.margin_px=2"]


def run_batch(args, timeout=600):
    cmd = [bpy.app.binary_path, "--background", "--factory-startup", "--python", BATCH, "--"] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")


def run_bat(args, timeout=600, env_extra=None):
    env = dict(os.environ)
    env["BLENDER_EXE"] = bpy.app.binary_path
    if env_extra:
        env.update(env_extra)
    return subprocess.run(["cmd.exe", "/c", BAT] + args, capture_output=True, text=True, timeout=timeout,
                          env=env, encoding="utf-8", errors="replace")


class BatchArgumentTests(BlenderTestCase):

    def test_build_config_overrides_and_preset(self):
        args = batch_export.parse_args(["--input", "x.glb", "--output", self.tmp, "--format", "fbx",
                                        "--preset", "high", "--set", "bake.samples=7", "--set", "uv.validate=false"])
        cfg = batch_export.build_config(args)
        self.assertEqual(cfg.export.format, "FBX")
        self.assertEqual(cfg.bake.resolution, 2048)
        self.assertEqual(cfg.bake.samples, 7)
        self.assertFalse(cfg.uv.validate)

    def test_build_config_errors(self):
        from blender_lightmap_export.config import ConfigError
        with self.assertRaises(ConfigError):
            batch_export.build_config(batch_export.parse_args(["--input", "x.glb"]))
        with self.assertRaises(ConfigError):
            batch_export.build_config(batch_export.parse_args(["--input", "x.glb", "--output", self.tmp,
                                                               "--set", "bake.nope=1"]))
        with self.assertRaises(ConfigError):
            batch_export.build_config(batch_export.parse_args(["--config", os.path.join(self.tmp, "missing.json")]))

    def test_collect_inputs(self):
        for name in ("a.glb", "b.FBX", "c.txt", "d.obj", "a.lightmaps.json"):
            with open(os.path.join(self.tmp, name), "w") as fh:
                fh.write("x")
        os.makedirs(os.path.join(self.tmp, "sub"))
        with open(os.path.join(self.tmp, "sub", "e.usdc"), "w") as fh:
            fh.write("x")
        files, skipped = batch_export.collect_inputs(self.tmp, recursive=False)
        self.assertEqual([os.path.basename(f) for f in files], ["a.glb", "b.FBX", "d.obj"])
        self.assertEqual(sorted(os.path.basename(f) for f in skipped), ["a.lightmaps.json", "c.txt"])
        files, _ = batch_export.collect_inputs(self.tmp, recursive=True)
        self.assertEqual(len(files), 4)

    def test_main_missing_input_exit_3(self):
        code = batch_export.main(["--input", os.path.join(self.tmp, "nope.glb"), "--output", self.tmp])
        self.assertEqual(code, 3)

    def test_main_config_error_exit_2(self):
        self.assertEqual(batch_export.main(["--output", self.tmp]), 2)
        self.assertEqual(batch_export.main(["--config", os.path.join(self.tmp, "none.json")]), 2)

    def test_main_empty_folder_exit_2(self):
        os.makedirs(os.path.join(self.tmp, "empty"))
        with open(os.path.join(self.tmp, "empty", "readme.txt"), "w") as fh:
            fh.write("x")
        self.assertEqual(batch_export.main(["--input", os.path.join(self.tmp, "empty"), "--output", self.tmp]), 2)

    def test_main_in_process_single_file(self):
        """Run the batch entry point in-process on a generated GLB (fast)."""
        objs = gen.cube()
        src = os.path.join(self.tmp, "in", "cube.glb")
        os.makedirs(os.path.dirname(src))
        bpy.ops.export_scene.gltf(filepath=src, export_format="GLB")
        out = os.path.join(self.tmp, "out")
        code = batch_export.main(["--input", src, "--output", out, "--format", "GLB",
                                  "--set", "bake.resolution=256", "--set", "bake.samples=4",
                                  "--set", "bake.denoise=false"])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(os.path.join(out, "cube.glb")))
        self.assertTrue(os.path.isfile(os.path.join(out, "cube_lightmap.png")))
        self.assertTrue(os.path.isfile(os.path.join(out, "cube.lightmaps.json")))
        self.assertTrue(os.path.isfile(os.path.join(out, "export.log")))
        report = json.load(open(os.path.join(out, "export_report.json"), encoding="utf-8"))
        self.assertEqual(report["succeeded"], 1)
        self.assertEqual(report["failed"], 0)


class BatchSubprocessTests(BlenderTestCase):
    """End-to-end through blender.exe / start_export.bat."""

    def _make_inputs(self):
        src_dir = os.path.join(self.tmp, "in")
        os.makedirs(src_dir)
        gen.reset()
        gen.cube()
        bpy.ops.export_scene.gltf(filepath=os.path.join(src_dir, "cube.glb"), export_format="GLB")
        gen.reset()
        gen.multi_material()
        bpy.ops.export_scene.fbx(filepath=os.path.join(src_dir, "multi.fbx"))
        with open(os.path.join(src_dir, "broken.glb"), "wb") as fh:
            fh.write(b"this is not a glb file")
        with open(os.path.join(src_dir, "notes.txt"), "w") as fh:
            fh.write("ignored")
        return src_dir

    @slow
    def test_single_file_exit_0(self):
        src_dir = self._make_inputs()
        out = os.path.join(self.tmp, "out1")
        res = run_batch(["--input", os.path.join(src_dir, "cube.glb"), "--output", out, "--format", "GLB"] + FAST)
        self.assertEqual(res.returncode, 0, res.stdout[-3000:] + res.stderr[-1000:])
        self.assertTrue(os.path.isfile(os.path.join(out, "cube.glb")))
        self.assertTrue(os.path.isfile(os.path.join(out, "cube_lightmap.png")))
        report = json.load(open(os.path.join(out, "export_report.json"), encoding="utf-8"))
        self.assertEqual(report["succeeded"], 1)

    @slow
    def test_folder_with_broken_file_exit_1_but_others_succeed(self):
        src_dir = self._make_inputs()
        out = os.path.join(self.tmp, "out2")
        res = run_batch(["--input", src_dir, "--output", out, "--format", "GLB"] + FAST)
        self.assertEqual(res.returncode, 1, res.stdout[-3000:])
        report = json.load(open(os.path.join(out, "export_report.json"), encoding="utf-8"))
        self.assertEqual(report["total"], 3)
        self.assertEqual(report["succeeded"], 2)
        self.assertEqual(report["failed"], 1)
        failed = [f for f in report["files"] if not f["success"]]
        self.assertTrue(failed[0]["input"].endswith("broken.glb"))
        self.assertTrue(failed[0]["error"])
        self.assertTrue(any(s.endswith("notes.txt") for s in report["skipped_unsupported"]))
        # per-file sub folders for folder processing
        self.assertTrue(os.path.isfile(os.path.join(out, "cube", "cube.glb")))
        self.assertTrue(os.path.isfile(os.path.join(out, "multi", "multi.glb")))
        self.assertTrue(os.path.isdir(os.path.join(out, "multi", "Lightmaps")))
        log = open(os.path.join(out, "export.log"), encoding="utf-8").read()
        self.assertIn("FEHLER", log)
        self.assertIn("Zusammenfassung: 2 erfolgreich, 1 fehlgeschlagen", log)

    @slow
    def test_stop_on_error(self):
        src_dir = self._make_inputs()
        out = os.path.join(self.tmp, "out3")
        res = run_batch(["--input", src_dir, "--output", out, "--format", "GLB", "--stop-on-error"] + FAST)
        self.assertEqual(res.returncode, 1)
        report = json.load(open(os.path.join(out, "export_report.json"), encoding="utf-8"))
        self.assertLess(report["total"], 3)

    @slow
    def test_repeated_run_overwrites(self):
        src_dir = self._make_inputs()
        out = os.path.join(self.tmp, "out4")
        args = ["--input", os.path.join(src_dir, "cube.glb"), "--output", out, "--format", "GLB"] + FAST
        self.assertEqual(run_batch(args).returncode, 0)
        first = os.path.getmtime(os.path.join(out, "cube.glb"))
        self.assertEqual(run_batch(args).returncode, 0)
        self.assertGreaterEqual(os.path.getmtime(os.path.join(out, "cube.glb")), first)
        res = run_batch(args + ["--set", "export.overwrite=false"])
        self.assertEqual(res.returncode, 1)

    @slow
    def test_config_file_and_unsupported_format(self):
        src_dir = self._make_inputs()
        out = os.path.join(self.tmp, "out5")
        cfg = quick_config(out, export__format="FBX", export__scope="SCENE")
        cfg.input_file = os.path.join(src_dir, "cube.glb")
        cfg_path = os.path.join(self.tmp, "cfg.json")
        cfg.save(cfg_path)
        res = run_batch(["--config", cfg_path])
        self.assertEqual(res.returncode, 0, res.stdout[-2000:])
        self.assertTrue(os.path.isfile(os.path.join(out, "cube.fbx")))
        res = run_batch(["--config", cfg_path, "--format", "XYZ"])
        self.assertEqual(res.returncode, 2)
        res = run_batch(["--config", os.path.join(self.tmp, "missing.json")])
        self.assertEqual(res.returncode, 2)

    @slow
    def test_bat_file(self):
        src_dir = self._make_inputs()
        out = os.path.join(self.tmp, "out6")
        res = run_bat([os.path.join(src_dir, "cube.glb"), out, "--format", "GLB"] + FAST)
        self.assertEqual(res.returncode, 0, res.stdout[-3000:] + res.stderr[-1000:])
        self.assertTrue(os.path.isfile(os.path.join(out, "cube.glb")))
        res = run_bat([])
        self.assertEqual(res.returncode, 2)
        res = run_bat([os.path.join(src_dir, "cube.glb"), out], env_extra={"BLENDER_EXE": r"C:\nope\blender.exe"})
        self.assertEqual(res.returncode, 3)


if __name__ == "__main__":
    unittest.main()
