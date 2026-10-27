# SPDX-License-Identifier: MIT
"""Public Python API (export_lightmap convenience, overrides, result object)."""

import json
import os
import unittest

import bpy

from tests.helpers import BlenderTestCase
from scripts import generate_test_scenes as gen
from blender_lightmap_export import export_lightmap, run_pipeline, ExportConfig, LightmapExportError, api


class APITests(BlenderTestCase):

    def _input_glb(self):
        gen.cube()
        path = os.path.join(self.tmp, "in", "model.glb")
        os.makedirs(os.path.dirname(path))
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB")
        bpy.ops.wm.read_factory_settings(use_empty=True)
        return path

    def test_export_lightmap_from_file(self):
        src = self._input_glb()
        out = os.path.join(self.tmp, "out")
        result = export_lightmap(input_file=src, output_dir=out, export_format="GLB", resolution=256,
                                 samples=4, island_margin_px=4, bake_margin_px=4, denoise=False,
                                 export__reimport_check=True)
        self.assertTrue(result.success)
        self.assertEqual(result.objects, ["Cube"])
        self.assertEqual(os.path.basename(result.exported_files[0]), "model.glb")
        self.assertTrue(os.path.isfile(os.path.join(out, "model_lightmap.png")))
        self.assertTrue(os.path.isfile(result.sidecar_path))
        self.assertTrue(result.reimport_check["ok"], result.reimport_check)
        d = result.to_dict()
        json.dumps(d)  # serialisable
        self.assertIn("Erfolg: True", result.summary())

    def test_invalid_config_raises(self):
        with self.assertRaises(LightmapExportError):
            export_lightmap(output_dir=self.tmp, resolution=17)
        with self.assertRaises(LightmapExportError):
            export_lightmap(output_dir=self.tmp, nonsense__key=1)

    def test_missing_input_file(self):
        with self.assertRaises(LightmapExportError):
            export_lightmap(input_file=os.path.join(self.tmp, "missing.glb"), output_dir=self.tmp)

    def test_unsupported_input_format(self):
        bad = os.path.join(self.tmp, "model.xyz")
        with open(bad, "w") as fh:
            fh.write("x")
        with self.assertRaises(LightmapExportError):
            export_lightmap(input_file=bad, output_dir=self.tmp)

    def test_run_pipeline_on_scene_objects_with_preset(self):
        objs = gen.row()
        cfg = ExportConfig(output_dir=self.tmp)
        api_cfg = cfg.copy()
        from blender_lightmap_export.config import apply_preset
        apply_preset(api_cfg, "PREVIEW")
        api_cfg.bake.resolution = 256
        api_cfg.bake.samples = 4
        api_cfg.export.format = "NONE"
        api_cfg.atlas.mode = "SHARED_ATLAS"
        result = run_pipeline(api_cfg, objects=objs[:2])
        self.assertEqual(sorted(result.objects), ["RowCube", "RowSphere"])
        self.assertEqual(len(result.lightmaps), 1)
        self.assertNotIn("RowCylinder", result.lightmaps[0].objects)

    def test_import_model_and_find_metadata(self):
        src = self._input_glb()
        objs = api.import_model(src)
        self.assertEqual([o.name for o in objs], ["Cube"])
        self.assertIsNone(api.find_lightmap_metadata(src))
        out = os.path.join(self.tmp, "out")
        export_lightmap(output_dir=out, export_format="GLB", resolution=256, samples=4, objects=objs,
                        export__base_name="model")
        meta = api.find_lightmap_metadata(os.path.join(out, "model.glb"))
        self.assertIsNotNone(meta)
        self.assertIn("Cube", meta["objects"])


if __name__ == "__main__":
    unittest.main()
