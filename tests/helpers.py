# SPDX-License-Identifier: MIT
"""Shared helpers for the Blender-internal unittest suite."""

from __future__ import annotations

import functools
import os
import shutil
import sys
import tempfile
import unittest

import bpy

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

EXAMPLES_DIR = os.path.join(REPO_ROOT, "examples")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
BUILD_DIR = os.path.join(REPO_ROOT, "build")


def skip_env(var: str, reason: str):
    """Decorator: skip when environment variable ``var`` is set to a truthy value."""
    def deco(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if os.environ.get(var):
                raise unittest.SkipTest(reason)
            return func(*args, **kwargs)
        return wrapper
    return deco


slow = skip_env("BLME_TEST_NO_SLOW", "langsamer Test übersprungen (--no-slow)")
needs_models = skip_env("BLME_TEST_NO_MODELS", "Beispielmodelle übersprungen (--no-models)")


def requires_gpu(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if os.environ.get("BLME_TEST_NO_GPU"):
            raise unittest.SkipTest("GPU-Test übersprungen (--no-gpu)")
        from blender_lightmap_export.core import baking
        if not baking.gpu_available():
            raise unittest.SkipTest("keine GPU für Cycles verfügbar")
        return func(*args, **kwargs)
    return wrapper


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.engine = "CYCLES"


def example_model(name: str) -> str:
    """Return the path of an example model, skipping the test when missing."""
    paths = {
        "teapot": os.path.join(EXAMPLES_DIR, "teapot", "utah_teapot.glb"),
        "car": os.path.join(EXAMPLES_DIR, "car", "ToyCar.glb"),
        "ship": os.path.join(EXAMPLES_DIR, "ship", "dutch_ship_large_01_1k.gltf"),
    }
    path = paths[name]
    if not os.path.isfile(path):
        raise unittest.SkipTest(f"Beispielmodell fehlt: {path}")
    return path


class BlenderTestCase(unittest.TestCase):
    """Base class: fresh empty scene and a temporary output directory per test."""

    def setUp(self):
        reset_scene()
        self.tmp = tempfile.mkdtemp(prefix="blme_test_")

    def tearDown(self):
        try:
            bpy.ops.wm.read_factory_settings(use_empty=True)
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    # convenience ....................................................................
    def out(self, *parts: str) -> str:
        return os.path.join(self.tmp, *parts)

    def assertFileExists(self, path: str, min_size: int = 1):
        self.assertTrue(os.path.isfile(path), f"Datei fehlt: {path}")
        self.assertGreaterEqual(os.path.getsize(path), min_size, f"Datei zu klein: {path}")


def quick_config(tmp: str, **kw):
    """Small, fast configuration for tests."""
    from blender_lightmap_export.config import ExportConfig
    cfg = ExportConfig()
    cfg.output_dir = tmp
    cfg.bake.resolution = 256
    cfg.bake.samples = 8
    cfg.bake.margin_px = 2
    cfg.uv.island_margin_px = 2
    cfg.lighting.mode = "AUTO"
    cfg.export.format = "NONE"
    for key, value in kw.items():
        target = cfg
        parts = key.split("__")
        for p in parts[:-1]:
            target = getattr(target, p)
        setattr(target, parts[-1], value)
    return cfg


def image_stats(img: bpy.types.Image, channel: int = 0):
    px = img.pixels[:]
    n = len(px) // 4
    if n == 0:
        return {"mean": 0.0, "max": 0.0, "min": 0.0, "nonzero": 0.0}
    vals = px[channel::4]
    return {
        "mean": sum(vals) / n,
        "max": max(vals),
        "min": min(vals),
        "nonzero": sum(1 for v in vals if v > 1e-4) / n,
    }
