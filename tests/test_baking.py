# SPDX-License-Identifier: GPL-3.0-or-later
"""Cycles baking: files, resolution, content, lighting dependence, materials, atlas, devices."""

import os
import unittest

import bpy

from tests.helpers import BlenderTestCase, quick_config, requires_gpu, slow
from scripts import generate_test_scenes as gen
from blender_lightmap_export import api
from blender_lightmap_export.core import images, materials, baking
from blender_lightmap_export.core.pipeline import LightmapExportError


def load_stats(path):
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = "Non-Color"
    try:
        return tuple(img.size), images.image_stats(img)
    finally:
        bpy.data.images.remove(img)


class BakingTests(BlenderTestCase):

    def test_cpu_bake_png(self):
        objs = gen.cube()
        cfg = quick_config(self.tmp, bake__device="CPU", bake__resolution=256)
        result = api.bake_lightmaps(cfg, objects=objs)
        self.assertTrue(result.success)
        self.assertEqual(result.device_used, "CPU")
        self.assertEqual(len(result.lightmaps), 1)
        lm = result.lightmaps[0]
        self.assertFileExists(lm.file_path, 100)
        self.assertEqual(os.path.basename(lm.file_path), "Cube_lightmap.png")
        size, stats = load_stats(lm.file_path)
        self.assertEqual(size, (256, 256))
        self.assertGreater(stats["max"], 0.05, "Lightmap ist leer")
        self.assertGreater(stats["nonzero"], 0.2)

    @requires_gpu
    def test_gpu_bake_matches_cpu(self):
        objs = gen.cube()
        cfg = quick_config(self.tmp, bake__device="GPU", bake__samples=16)
        result = api.bake_lightmaps(cfg, objects=objs)
        self.assertTrue(result.success)
        self.assertIn(result.device_used, baking.GPU_BACKENDS)
        _, gpu_stats = load_stats(result.lightmaps[0].file_path)
        cfg.bake.device = "CPU"
        cfg.output_dir = self.out("cpu")
        result2 = api.bake_lightmaps(cfg, objects=objs)
        _, cpu_stats = load_stats(result2.lightmaps[0].file_path)
        self.assertAlmostEqual(gpu_stats["mean"], cpu_stats["mean"], delta=0.05 * max(gpu_stats["mean"], 1e-3))

    def test_auto_device_selected(self):
        objs = gen.cube()
        cfg = quick_config(self.tmp, bake__device="AUTO")
        result = api.bake_lightmaps(cfg, objects=objs)
        expected = "CPU" if not baking.gpu_available() else baking.GPU_BACKENDS
        self.assertIn(result.device_used, expected)

    def test_exr_output(self):
        objs = gen.cube()
        cfg = quick_config(self.tmp, image__format="EXR")
        result = api.bake_lightmaps(cfg, objects=objs)
        lm = result.lightmaps[0]
        self.assertTrue(lm.file_path.endswith(".exr"))
        self.assertFileExists(lm.file_path, 100)
        size, stats = load_stats(lm.file_path)
        self.assertEqual(size, (256, 256))
        self.assertAlmostEqual(stats["mean"], lm.stats["mean"], delta=0.01)

    def test_png_matches_in_memory_values_when_ldr(self):
        objs = gen.cube()
        cfg = quick_config(self.tmp, lighting__mode="DEFAULT_RIG", lighting__sun_energy=0.8)
        result = api.bake_lightmaps(cfg, objects=objs)
        lm = result.lightmaps[0]
        _, stats = load_stats(lm.file_path)
        if lm.stats["max"] <= 1.0:
            self.assertAlmostEqual(stats["mean"], lm.stats["mean"], delta=0.01)

    def test_hdr_warning_for_png(self):
        objs = gen.cube()
        cfg = quick_config(self.tmp, lighting__mode="DEFAULT_RIG", lighting__sun_energy=20.0)
        result = api.bake_lightmaps(cfg, objects=objs)
        self.assertGreater(result.lightmaps[0].stats["max"], 1.0)
        self.assertTrue(any("über 1.0" in w for w in result.warnings))

    def test_lighting_changes_result(self):
        objs = gen.cube()
        cfg = quick_config(self.tmp, lighting__mode="DEFAULT_RIG", lighting__sun_energy=3.0,
                           lighting__world_strength=0.0)
        a = api.bake_lightmaps(cfg, objects=objs).lightmaps[0].stats["mean"]
        cfg.lighting.sun_energy = 0.3
        cfg.output_dir = self.out("dark")
        b = api.bake_lightmaps(cfg, objects=objs).lightmaps[0].stats["mean"]
        self.assertGreater(a, b * 3.0)

    def test_direct_only_vs_indirect(self):
        objs = gen.room()
        cfg = quick_config(self.tmp, bake__use_indirect=False)
        a = api.bake_lightmaps(cfg, objects=objs[:1])
        cfg.bake.use_direct = False
        cfg.bake.use_indirect = True
        cfg.output_dir = self.out("ind")
        b = api.bake_lightmaps(cfg, objects=objs[:1])
        self.assertNotAlmostEqual(a.lightmaps[0].stats["mean"], b.lightmaps[0].stats["mean"], places=3)

    def test_multi_material_object(self):
        objs = gen.multi_material()
        cfg = quick_config(self.tmp)
        result = api.bake_lightmaps(cfg, objects=objs[:1])
        self.assertEqual(len(result.lightmaps), 1)
        obj = objs[0]
        self.assertEqual(len(obj.material_slots), 3)
        for slot in obj.material_slots:
            self.assertTrue(materials.is_bound(slot.material), slot.material.name)
            self.assertEqual(slot.material.node_tree.nodes[materials.NODE_IMAGE].image.name, result.lightmaps[0].image_name)
            self.assertIsNone(slot.material.node_tree.nodes.get(baking.BAKE_NODE), "Bake-Node nicht entfernt")
        self.assertGreater(result.lightmaps[0].stats["nonzero"], 0.3)

    def test_object_without_material(self):
        (obj,) = gen.no_uvs()
        cfg = quick_config(self.tmp)
        result = api.bake_lightmaps(cfg, objects=[obj])
        self.assertTrue(result.success)
        # objects without material get a neutral material that carries the preview
        self.assertEqual(len(obj.material_slots), 1)
        mat = obj.material_slots[0].material
        self.assertTrue(mat.name.startswith(baking.DEFAULT_MATERIAL_PREFIX))
        self.assertTrue(materials.is_bound(mat))
        self.assertTrue(any("kein Material" in w for w in result.warnings))
        self.assertGreater(result.lightmaps[0].stats["max"], 0.05)

    def test_object_without_material_rolled_back_on_failure(self):
        (obj,) = gen.no_uvs()
        cfg = quick_config(self.tmp)
        # force a failure after the material was assigned: overwrite disabled and file present
        cfg.export.overwrite = False
        with open(os.path.join(self.tmp, "NoUV_lightmap.png"), "wb") as fh:
            fh.write(b"x")
        with self.assertRaises(LightmapExportError):
            api.bake_lightmaps(cfg, objects=[obj])
        self.assertEqual(len(obj.material_slots), 0, "Material wurde nach Fehler nicht entfernt")
        self.assertNotIn("LightmapUV", obj.data.uv_layers)

    def test_multiple_objects_per_object_mode(self):
        objs = gen.row()
        cfg = quick_config(self.tmp)
        result = api.bake_lightmaps(cfg, objects=objs)
        self.assertEqual(len(result.lightmaps), 4)
        for lm in result.lightmaps:
            self.assertFileExists(lm.file_path)
            self.assertEqual(os.path.basename(os.path.dirname(lm.file_path)), "Lightmaps")
            self.assertFalse(lm.is_atlas)
        names = sorted(os.path.basename(lm.file_path) for lm in result.lightmaps)
        self.assertEqual(names, ["RowCube_lightmap.png", "RowCylinder_lightmap.png", "RowGround_lightmap.png",
                                 "RowSphere_lightmap.png"])

    def test_shared_atlas(self):
        objs = gen.row()
        cfg = quick_config(self.tmp, atlas__mode="SHARED_ATLAS", bake__resolution=512)
        result = api.bake_lightmaps(cfg, objects=objs)
        self.assertEqual(len(result.lightmaps), 1)
        lm = result.lightmaps[0]
        self.assertTrue(lm.is_atlas)
        self.assertEqual(sorted(lm.objects), sorted(o.name for o in objs))
        self.assertGreater(lm.stats["nonzero"], 0.3)
        for o in objs:
            for slot in o.material_slots:
                self.assertEqual(slot.material.node_tree.nodes[materials.NODE_IMAGE].image.name, lm.image_name)

    def test_shared_material_gets_per_object_copy(self):
        objs = gen.shared_material()
        cfg = quick_config(self.tmp)
        result = api.bake_lightmaps(cfg, objects=objs)
        self.assertEqual(len(result.lightmaps), 2)
        mats = [o.material_slots[0].material for o in objs]
        self.assertNotEqual(mats[0], mats[1])
        self.assertIsNotNone(bpy.data.materials.get("MatShared"))
        self.assertFalse(materials.is_bound(bpy.data.materials["MatShared"]), "Originalmaterial wurde verändert")
        images_used = {m.node_tree.nodes[materials.NODE_IMAGE].image.name for m in mats}
        self.assertEqual(len(images_used), 2)
        api.restore_materials(objs)
        self.assertEqual([o.material_slots[0].material.name for o in objs], ["MatShared", "MatShared"])

    def test_instances_share_lightmap_with_warning(self):
        objs = gen.instances()
        cfg = quick_config(self.tmp)
        result = api.bake_lightmaps(cfg, objects=objs)
        self.assertEqual(len(result.lightmaps), 1)
        self.assertTrue(any("teilen sich Mesh" in w for w in result.warnings))

    def test_ao_bake(self):
        objs = gen.room()
        cfg = quick_config(self.tmp, bake__type="AO")
        result = api.bake_lightmaps(cfg, objects=[objs[0]])
        stats = result.lightmaps[0].stats
        self.assertGreater(stats["max"], 0.5)
        self.assertEqual(result.lightmaps[0].bake_type, "AO")

    def test_combined_bake(self):
        objs = gen.cube()
        cfg = quick_config(self.tmp, bake__type="COMBINED")
        result = api.bake_lightmaps(cfg, objects=objs)
        self.assertGreater(result.lightmaps[0].stats["max"], 0.01)

    def test_bake_margin_adds_padding(self):
        objs = gen.cube()
        cfg = quick_config(self.tmp, bake__margin_px=0, uv__island_margin_px=12)
        tight = api.bake_lightmaps(cfg, objects=objs).lightmaps[0].stats["nonzero"]
        cfg.bake.margin_px = 12
        cfg.output_dir = self.out("padded")
        padded = api.bake_lightmaps(cfg, objects=objs).lightmaps[0].stats["nonzero"]
        self.assertGreater(padded, tight * 1.1)

    @slow
    def test_denoise(self):
        objs = gen.cube()
        cfg = quick_config(self.tmp, bake__denoise=True, bake__samples=4)
        result = api.bake_lightmaps(cfg, objects=objs)
        self.assertTrue(result.success)
        stats = result.lightmaps[0].stats
        self.assertGreater(stats["max"], 0.05)
        self.assertIsNone(bpy.data.node_groups.get(images.DENOISE_GROUP), "Denoise-Gruppe nicht entfernt")

    def test_scene_state_restored(self):
        objs = gen.cube()
        sc = bpy.context.scene
        sc.render.engine = "BLENDER_EEVEE"
        sc.cycles.samples = 123
        sc.render.bake.margin = 1
        world = sc.world
        cfg = quick_config(self.tmp, lighting__mode="DEFAULT_RIG")
        api.bake_lightmaps(cfg, objects=objs)
        self.assertEqual(sc.render.engine, "BLENDER_EEVEE")
        self.assertEqual(sc.cycles.samples, 123)
        self.assertEqual(sc.render.bake.margin, 1)
        self.assertEqual(sc.world, world)
        self.assertIsNone(bpy.data.objects.get("BLME_Sun"))
        self.assertIsNone(bpy.data.collections.get("BLME_TempLights"))
        self.assertIsNone(bpy.data.worlds.get("BLME_TempWorld"))
        self.assertFalse(bpy.data.objects["Sun"].hide_render, "Originallicht bleibt ausgeblendet")
        self.assertEqual(bpy.context.mode, "OBJECT")

    def test_failure_rolls_back_products(self):
        (obj,) = gen.cube()
        n_images = len(bpy.data.images)
        cfg = quick_config(self.tmp, uv__method="EXISTING")  # LightmapUV missing -> fails in uv step
        with self.assertRaises(LightmapExportError):
            api.bake_lightmaps(cfg, objects=[obj])
        self.assertEqual(len(bpy.data.images), n_images)
        self.assertNotIn("LightmapUV", obj.data.uv_layers)
        self.assertFalse(materials.is_bound(obj.material_slots[0].material))

    def test_missing_lights_warning_in_scene_mode(self):
        objs = gen.cube(with_light=False)
        cfg = quick_config(self.tmp, lighting__mode="SCENE")
        result = api.bake_lightmaps(cfg, objects=objs)
        self.assertTrue(any("keine Lichtquellen" in w for w in result.warnings))

    def test_multi_light_scene(self):
        objs = gen.multi_lights()
        cfg = quick_config(self.tmp, lighting__mode="SCENE", atlas__mode="SHARED_ATLAS")
        result = api.bake_lightmaps(cfg, objects=objs)
        self.assertTrue(result.success)
        self.assertGreater(result.lightmaps[0].stats["mean"], 0.01)


if __name__ == "__main__":
    unittest.main()
