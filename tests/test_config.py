# SPDX-License-Identifier: MIT
"""Tests for configuration loading, validation and presets."""

import json
import os
import tempfile
import unittest

from tests.helpers import REPO_ROOT  # noqa: F401  (ensures sys.path)

from blender_lightmap_export.config import ExportConfig, ConfigError, apply_preset, PRESETS


class ConfigTests(unittest.TestCase):

    def test_defaults_are_valid(self):
        cfg = ExportConfig(output_dir="C:/tmp")
        self.assertEqual(cfg.validate(), [])

    def test_roundtrip_json(self):
        cfg = ExportConfig(output_dir="C:/tmp")
        cfg.bake.resolution = 2048
        cfg.uv.method = "LIGHTMAP_PACK"
        data = json.loads(cfg.to_json())
        cfg2 = ExportConfig.from_dict(data)
        self.assertEqual(cfg2.bake.resolution, 2048)
        self.assertEqual(cfg2.uv.method, "LIGHTMAP_PACK")
        self.assertEqual(cfg2.to_dict(), cfg.to_dict())

    def test_invalid_values_reported(self):
        cfg = ExportConfig(output_dir="x")
        cfg.bake.resolution = 100
        cfg.uv.method = "NOPE"
        cfg.export.format = "XYZ"
        problems = cfg.validate()
        self.assertEqual(len(problems), 3)
        with self.assertRaises(ConfigError):
            cfg.validate_or_raise()

    def test_unknown_key_strict(self):
        with self.assertRaises(ConfigError):
            ExportConfig.from_dict({"foo": 1})
        cfg = ExportConfig.from_dict({"foo": 1, "bake": {"samples": 3}}, strict=False)
        self.assertEqual(cfg.bake.samples, 3)

    def test_type_coercion(self):
        cfg = ExportConfig.from_dict({"bake": {"samples": "12", "denoise": "true"}})
        self.assertEqual(cfg.bake.samples, 12)
        self.assertTrue(cfg.bake.denoise)
        with self.assertRaises(ConfigError):
            ExportConfig.from_dict({"bake": {"samples": "zwölf"}})

    def test_presets(self):
        cfg = ExportConfig()
        apply_preset(cfg, "high")
        self.assertEqual(cfg.bake.samples, PRESETS["HIGH"]["samples"])
        with self.assertRaises(ConfigError):
            apply_preset(cfg, "ultra")

    def test_load_preset_keeps_explicit_values(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"output_dir": d, "preset": "HIGH", "bake": {"samples": 5}}, fh)
            cfg = ExportConfig.load(path)
            self.assertEqual(cfg.bake.samples, 5)
            self.assertEqual(cfg.bake.resolution, PRESETS["HIGH"]["resolution"])

    def test_missing_and_broken_file(self):
        with self.assertRaises(ConfigError):
            ExportConfig.load("C:/does/not/exist.json")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "broken.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{ not json")
            with self.assertRaises(ConfigError):
                ExportConfig.load(path)

    def test_example_config_in_repo_is_valid(self):
        path = os.path.join(REPO_ROOT, "config.example.json")
        if not os.path.isfile(path):
            self.skipTest("config.example.json noch nicht vorhanden")
        cfg = ExportConfig.load(path)
        self.assertEqual(cfg.validate(), [])


if __name__ == "__main__":
    unittest.main()
