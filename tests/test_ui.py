# SPDX-License-Identifier: GPL-3.0-or-later
"""Add-on registration, property/config conversion and operators (headless where possible)."""

import os
import sys
import unittest

import bpy

from tests.helpers import BlenderTestCase, REPO_ROOT
from scripts import generate_test_scenes as gen


def _register_addon():
    import blender_lightmap_export as pkg
    try:
        pkg.register()
    except ValueError:
        pass  # already registered
    return pkg


class UITests(BlenderTestCase):

    def setUp(self):
        super().setUp()
        self.pkg = _register_addon()

    def test_registration_and_panels(self):
        self.assertTrue(hasattr(bpy.types.Scene, "blme"))
        for idname in ("BLME_PT_main", "BLME_PT_advanced", "BLME_PT_status", "BLME_PT_tools"):
            self.assertTrue(hasattr(bpy.types, idname), idname)
        self.assertTrue(hasattr(bpy.ops.blme, "run"))
        self.assertTrue(hasattr(bpy.ops.blme, "import_with_lightmaps"))
        self.assertTrue(hasattr(bpy.ops.blme, "material_preview"))
        self.assertEqual(bpy.ops.blme.material_preview(), {"FINISHED"})  # no 3D views headless
        self.pkg.unregister()
        self.assertFalse(hasattr(bpy.types, "BLME_PT_main"))
        self.pkg.register()

    def test_settings_roundtrip(self):
        s = bpy.context.scene.blme
        s.preset = "HIGH"
        self.assertEqual(s.samples, 256)
        self.assertEqual(s.resolution, "2048")
        s.export_format = "FBX"
        s.island_margin_px = 5.5
        s.atlas_mode = "SHARED_ATLAS"
        cfg = s.to_config()
        self.assertEqual(cfg.export.format, "FBX")
        self.assertEqual(cfg.bake.samples, 256)
        self.assertEqual(cfg.uv.island_margin_px, 5.5)
        self.assertEqual(cfg.atlas.mode, "SHARED_ATLAS")
        self.assertEqual(cfg.validate(), [])
        cfg.bake.type = "AO"
        cfg.bake.resolution = 512
        s.from_config(cfg)
        self.assertEqual(s.bake_type, "AO")
        self.assertEqual(s.resolution, "512")
        self.assertEqual(s.preset, "CUSTOM")

    def test_run_operator_blocking_in_background(self):
        """Without a window the operator runs the pipeline blocking (same core as the modal path)."""
        gen.cube()
        s = bpy.context.scene.blme
        s.output_dir = self.tmp
        s.preset = "PREVIEW"
        s.resolution = "256"
        s.samples = 4
        s.export_format = "NONE"
        s.export_scope = "SCENE"
        s.denoise = False
        result = bpy.ops.blme.run(mode="BAKE")
        self.assertEqual(result, {"FINISHED"})
        self.assertFalse(s.is_running)
        self.assertEqual(s.last_error, "", s.last_error)
        self.assertIn("Lightmaps: 1", s.last_summary)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "Cube_lightmap.png")))

    def test_run_operator_reports_config_error(self):
        gen.cube()
        s = bpy.context.scene.blme
        s.output_dir = self.tmp
        s.export_scope = "SCENE"
        s.uv_method = "EXISTING"
        s.uv_name = "DoesNotExist"
        s.export_format = "NONE"
        # operators that report an error raise RuntimeError when called from Python
        with self.assertRaises(RuntimeError) as cm:
            bpy.ops.blme.run(mode="BAKE")
        self.assertIn("DoesNotExist", str(cm.exception))
        self.assertFalse(s.is_running)
        self.assertIn("DoesNotExist", s.last_error)
        self.assertEqual(bpy.context.mode, "OBJECT")

    def test_run_operator_without_selection_uses_whole_scene(self):
        objs = gen.row()
        bpy.ops.object.select_all(action="DESELECT")
        s = bpy.context.scene.blme
        s.output_dir = self.tmp
        s.export_scope = "SELECTED"
        s.export_format = "NONE"
        s.resolution = "256"
        s.samples = 4
        s.denoise = False
        self.assertEqual(bpy.ops.blme.run(mode="BAKE"), {"FINISHED"})
        self.assertIn("Lightmaps: 4", s.last_summary)
        self.assertTrue(all(o.select_get() for o in objs), "Objekte wurden nicht selektiert")

    def test_run_operator_without_any_mesh(self):
        s = bpy.context.scene.blme
        s.output_dir = self.tmp
        s.export_scope = "SELECTED"
        with self.assertRaises(RuntimeError) as cm:
            bpy.ops.blme.run(mode="BAKE")
        self.assertIn("Keine Mesh-Objekte", str(cm.exception))

    def test_export_requires_baked_lightmaps(self):
        gen.cube()
        s = bpy.context.scene.blme
        s.output_dir = self.tmp
        s.export_scope = "SCENE"
        s.export_format = "GLB"
        with self.assertRaises(RuntimeError) as cm:
            bpy.ops.blme.run(mode="EXPORT")
        self.assertIn("zuerst backen", str(cm.exception))

    def test_save_and_load_config_operators(self):
        s = bpy.context.scene.blme
        s.samples = 33
        path = os.path.join(self.tmp, "ui.json")
        bpy.ops.blme.save_config(filepath=path)
        self.assertTrue(os.path.isfile(path))
        s.samples = 1
        bpy.ops.blme.load_config(filepath=path)
        self.assertEqual(s.samples, 33)

    def test_apply_and_restore_operators(self):
        from blender_lightmap_export import api
        from blender_lightmap_export.core import materials
        from tests.helpers import quick_config
        (obj,) = gen.cube()
        api.bake_lightmaps(quick_config(self.tmp), objects=[obj])
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        self.assertEqual(bpy.ops.blme.apply_preview(mode="ORIGINAL"), {"FINISHED"})
        mat = obj.material_slots[0].material
        self.assertEqual(mat.node_tree.nodes[materials.NODE_GROUP].inputs["Preview"].default_value, 0.0)
        self.assertEqual(bpy.ops.blme.restore_materials(), {"FINISHED"})
        self.assertFalse(materials.is_bound(mat))


if __name__ == "__main__":
    unittest.main()
