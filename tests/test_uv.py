# SPDX-License-Identifier: GPL-3.0-or-later
"""UV channel creation, unwrapping, validation and atlas packing."""

import unittest

import bpy
import numpy as np

from tests.helpers import BlenderTestCase, quick_config
from scripts import generate_test_scenes as gen
from blender_lightmap_export.core import uv, uv_validate
from blender_lightmap_export.core.pipeline import LightmapExportError
from blender_lightmap_export import api


class UVTests(BlenderTestCase):

    def _run_uv_only(self, objects, **kw):
        cfg = quick_config(self.tmp, **kw)
        return api.run_pipeline(cfg, objects=objects, stages=["prepare", "uv"]), cfg

    def test_lightmap_uv_created_and_existing_preserved(self):
        (obj,) = gen.existing_uvs()
        before = uv.uv_array(obj.data, "UVMap").copy()
        detail_before = uv.uv_array(obj.data, "Detail").copy()
        result, cfg = self._run_uv_only([obj])
        self.assertTrue(result.success)
        names = [u.name for u in obj.data.uv_layers]
        self.assertEqual(names, ["UVMap", "Detail", "LightmapUV"])
        np.testing.assert_array_equal(uv.uv_array(obj.data, "UVMap"), before)
        np.testing.assert_array_equal(uv.uv_array(obj.data, "Detail"), detail_before)
        self.assertTrue(obj.data.uv_layers["UVMap"].active_render, "Render-UV darf sich nicht ändern")
        self.assertFalse(obj.data.uv_layers["LightmapUV"].active_render)

    def test_object_without_uvs(self):
        (obj,) = gen.no_uvs()
        self.assertEqual(len(obj.data.uv_layers), 0)
        result, _ = self._run_uv_only([obj])
        self.assertEqual([u.name for u in obj.data.uv_layers], ["LightmapUV"])
        arr = uv.uv_array(obj.data, "LightmapUV")
        self.assertTrue(np.isfinite(arr).all())
        self.assertTrue((arr >= -1e-4).all() and (arr <= 1 + 1e-4).all())

    def test_uv_coordinates_valid_and_no_overlap(self):
        objs = gen.row()
        result, cfg = self._run_uv_only(objs)
        for o in objs:
            rep = uv_validate.validate_layout([(o.data, "LightmapUV")], 512, 1.0)
            self.assertEqual(rep["invalid"], 0)
            self.assertEqual(rep["out_of_bounds_loops"], 0)
            self.assertLess(rep["overlap_fraction"], 0.002, f"{o.name}: {rep}")
            self.assertGreater(rep["coverage_fraction"], 0.05)
        self.assertIn("RowCube", result.uv_validation)

    def test_overlap_is_detected(self):
        (obj,) = gen.cube()
        obj.data.uv_layers.new(name="LightmapUV")
        obj.data.uv_layers.active = obj.data.uv_layers["LightmapUV"]
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.reset()  # every face covers the full square -> massive overlap
        bpy.ops.object.mode_set(mode="OBJECT")
        rep = uv_validate.validate_layout([(obj.data, "LightmapUV")], 256, 1.0)
        self.assertGreater(rep["overlap_fraction"], 0.9)
        warnings = uv_validate.report_warnings("Cube", rep)
        self.assertTrue(any("überlappen" in w for w in warnings))
        # the pipeline reports it as a warning when validating an EXISTING layer
        cfg = quick_config(self.tmp, uv__method="EXISTING")
        result = api.run_pipeline(cfg, objects=[obj], stages=["prepare", "uv"])
        self.assertTrue(any("überlappen" in w for w in result.warnings))

    def test_nan_detected(self):
        (obj,) = gen.cube()
        layer = obj.data.uv_layers.new(name="LightmapUV")
        arr = uv.uv_array(obj.data, "LightmapUV")
        arr[0] = (float("nan"), 0.5)
        uv.set_uv_array(obj.data, "LightmapUV", arr)
        rep = uv_validate.validate_layout([(obj.data, "LightmapUV")], 64, 0)
        self.assertGreaterEqual(rep["invalid"], 1)

    def test_out_of_bounds_detected(self):
        (obj,) = gen.cube()
        obj.data.uv_layers.new(name="LightmapUV")
        arr = uv.uv_array(obj.data, "LightmapUV") * 1.5
        uv.set_uv_array(obj.data, "LightmapUV", arr)
        rep = uv_validate.validate_layout([(obj.data, "LightmapUV")], 64, 0)
        self.assertGreater(rep["out_of_bounds_loops"], 0)

    def test_island_margin_in_pixels(self):
        """16 px margin at 256 px keeps islands >= 8 px apart, 0 px margin does not."""
        (obj,) = gen.cube()
        cfg = quick_config(self.tmp, uv__island_margin_px=16, bake__resolution=256, uv__min_spacing_px=8)
        api.run_pipeline(cfg, objects=[obj], stages=["prepare", "uv"])
        rep_wide = uv_validate.validate_layout([(obj.data, "LightmapUV")], 256, 8)
        obj.data.uv_layers.remove(obj.data.uv_layers["LightmapUV"])
        cfg.uv.island_margin_px = 0
        api.run_pipeline(cfg, objects=[obj], stages=["prepare", "uv"])
        rep_tight = uv_validate.validate_layout([(obj.data, "LightmapUV")], 256, 8)
        self.assertEqual(rep_wide["spacing_violation_pixels"], 0, rep_wide)
        self.assertGreater(rep_tight["spacing_violation_pixels"], 0, rep_tight)

    def test_lightmap_pack_method(self):
        objs = gen.multi_material()
        result, _ = self._run_uv_only(objs, uv__method="LIGHTMAP_PACK", uv__island_margin_px=4)
        self.assertTrue(result.success)
        for o in objs:
            self.assertIn("LightmapUV", o.data.uv_layers)
            rep = uv_validate.validate_layout([(o.data, "LightmapUV")], 256, 1.0)
            self.assertEqual(rep["out_of_bounds_loops"], 0)
            self.assertLess(rep["overlap_fraction"], 0.002)

    def test_existing_method_requires_layer(self):
        (obj,) = gen.cube()
        with self.assertRaises(LightmapExportError):
            self._run_uv_only([obj], uv__method="EXISTING")
        self.assertNotIn("LightmapUV", obj.data.uv_layers)

    def test_existing_method_uses_layer(self):
        (obj,) = gen.cube()
        obj.data.uv_layers.new(name="LightmapUV")
        before = uv.uv_array(obj.data, "LightmapUV").copy()
        result, _ = self._run_uv_only([obj], uv__method="EXISTING", uv__validate=False)
        self.assertTrue(result.success)
        np.testing.assert_array_equal(uv.uv_array(obj.data, "LightmapUV"), before)

    def test_shared_atlas_packs_without_overlap(self):
        objs = gen.row()
        result, cfg = self._run_uv_only(objs, atlas__mode="SHARED_ATLAS", uv__island_margin_px=4)
        self.assertTrue(result.success)
        rep = uv_validate.validate_layout([(o.data, "LightmapUV") for o in objs], 512, 1.0)
        self.assertEqual(rep["out_of_bounds_loops"], 0)
        self.assertLess(rep["overlap_fraction"], 0.002, rep)
        self.assertGreater(rep["coverage_fraction"], 0.2)
        # every object occupies a distinct region: bounding boxes may touch but islands do not overlap
        self.assertIn("atlas", result.uv_validation)

    def test_texel_density_prescale(self):
        objs = gen.row()
        for o in objs:
            uv.unwrap_object(o, quick_config(self.tmp), 256)
        uv.prescale_for_texel_density(objs, "LightmapUV")
        ratios = []
        for o in objs:
            wa, ua = uv._triangle_areas(o.data, "LightmapUV", o)
            ratios.append(ua / wa)
        self.assertLess(max(ratios) / min(ratios), 1.05, ratios)

    def test_feasible_margin(self):
        self.assertEqual(uv.feasible_margin_px(1, 1024, 8), 8)
        self.assertEqual(uv.feasible_margin_px(16, 1024, 8), 8)          # 4 per row: max 64 px
        self.assertAlmostEqual(uv.feasible_margin_px(10000, 1024, 8), 2.56)  # 100 per row
        self.assertEqual(uv.feasible_margin_px(1000000, 256, 8), 0.5)

    def test_many_islands_reduce_margin_with_warning(self):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5)  # 20k faces, many islands with 10 degree limit
        obj = bpy.context.object
        obj.data.materials.append(gen.material("M", (0.5, 0.5, 0.5, 1)))
        cfg = quick_config(self.tmp, uv__angle_limit_deg=5.0, uv__island_margin_px=8, bake__resolution=256)
        result = api.run_pipeline(cfg, objects=[obj], stages=["prepare", "uv"])
        self.assertTrue(any("reduziert" in w for w in result.warnings), result.warnings)
        rep = uv_validate.validate_layout([(obj.data, "LightmapUV")], 256, 0)
        self.assertGreater(rep["coverage_fraction"], 0.05)
        cfg.uv.auto_reduce_margin = False
        obj.data.uv_layers.remove(obj.data.uv_layers["LightmapUV"])
        result = api.run_pipeline(cfg, objects=[obj], stages=["prepare", "uv"])
        self.assertFalse(any("reduziert" in w for w in result.warnings))

    def test_margin_conversion(self):
        self.assertAlmostEqual(uv.margin_uv_units(8, 1024), 8 / 1024)
        self.assertAlmostEqual(uv.lightmap_pack_margin(8, 1024), 8 / 1024 * 100)
        self.assertEqual(uv.lightmap_pack_margin(2000, 1024), 1.0)
        self.assertEqual(uv.lightmap_pack_margin(0, 1024), 0.001)


if __name__ == "__main__":
    unittest.main()
