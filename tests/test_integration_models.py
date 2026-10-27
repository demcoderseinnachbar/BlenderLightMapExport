# SPDX-License-Identifier: MIT
"""End-to-end workflow with the three external example models.

Steps per model (as required by the project brief):
 1. import, 2. check existing UV channels, 3. create LightmapUV, 4. unwrap,
 5. bake with Cycles, 6. save lightmap files, 7. export geometry, 8. re-import,
 9. assign lightmaps automatically, 10. verify UVs, materials and visibility.
"""

import json
import os
import unittest

import bpy
import numpy as np

from tests.helpers import BlenderTestCase, example_model, needs_models, slow, reset_scene
from blender_lightmap_export import api, ExportConfig
from blender_lightmap_export.core import materials, uv, uv_validate, images
from blender_lightmap_export.core.baking import gpu_available


def _render_visible(size=64):
    sc = bpy.context.scene
    meshes = [o for o in sc.objects if o.type == "MESH"]
    # frame all meshes with a camera looking at the bounding box centre
    from mathutils import Vector
    corners = [np.array(o.matrix_world @ Vector(c)) for o in meshes for c in o.bound_box]
    mins = np.min(corners, axis=0)
    maxs = np.max(corners, axis=0)
    centre = (mins + maxs) / 2
    radius = float(np.linalg.norm(maxs - mins)) / 2 + 1e-3
    cam_data = bpy.data.cameras.new("BLME_Cam")
    cam = bpy.data.objects.new("BLME_Cam", cam_data)
    sc.collection.objects.link(cam)
    direction = np.array([1.0, -1.0, 0.7])
    direction /= np.linalg.norm(direction)
    cam.location = tuple(centre + direction * radius * 2.6)
    from mathutils import Vector
    look = Vector(tuple(centre)) - cam.location
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    cam_data.clip_end = radius * 20
    sc.camera = cam
    for o in sc.objects:
        if o.type == "LIGHT":
            o.hide_render = True
    sc.world = None
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 4
    sc.cycles.device = "CPU"
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    path = os.path.join(bpy.app.tempdir, "blme_integration_render.png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    try:
        px = np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4)
        return float(px[:, :3].max()), float((px[:, :3].max(axis=1) > 0.02).mean())
    finally:
        bpy.data.images.remove(img)


def _is_transmissive(obj) -> bool:
    for slot in obj.material_slots:
        mat = slot.material
        if mat is None or mat.node_tree is None:
            return False
        bsdf = next((n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
        if bsdf is None:
            return False
        sock = bsdf.inputs.get("Transmission Weight")
        if sock is None or sock.is_linked or sock.default_value < 0.5:
            return False
    return bool(obj.material_slots)


class IntegrationModelTests(BlenderTestCase):

    def _config(self, out, fmt="GLB", atlas="PER_OBJECT", resolution=512, samples=16):
        cfg = ExportConfig(output_dir=out)
        cfg.bake.resolution = resolution
        cfg.bake.samples = samples
        cfg.bake.margin_px = 4
        cfg.bake.denoise = False
        cfg.bake.device = "AUTO"
        cfg.uv.island_margin_px = 4
        cfg.lighting.mode = "AUTO"
        cfg.export.format = fmt
        cfg.export.scope = "SCENE"
        cfg.export.reimport_check = True
        cfg.atlas.mode = atlas
        return cfg

    def _workflow(self, key, fmt="GLB", atlas="PER_OBJECT", expect_uv_before=True, resolution=512, samples=16):
        src = example_model(key)
        out = self.out(key)
        # 1. import
        objs = api.import_model(src)
        meshes = [o for o in objs if o.type == "MESH"]
        self.assertGreater(len(meshes), 0)
        # 2. existing UV channels
        uv_before = {o.name: [u.name for u in o.data.uv_layers] for o in meshes}
        if expect_uv_before:
            self.assertTrue(all(uv_before.values()), uv_before)
        uv_data_before = {o.name: (uv.uv_array(o.data, o.data.uv_layers[0].name).copy() if o.data.uv_layers else None)
                          for o in meshes}
        mats_before = {o.name: [s.material.name for s in o.material_slots if s.material] for o in meshes}
        # 3.-7. unwrap, bake, save, export (+ reimport check)
        cfg = self._config(out, fmt, atlas, resolution, samples)
        cfg.export.base_name = key
        result = api.run_pipeline(cfg, objects=meshes)
        self.assertTrue(result.success, result.errors)
        self.assertEqual(result.errors, [])
        for o in meshes:
            names = [u.name for u in o.data.uv_layers]
            self.assertEqual(names[:-1], uv_before[o.name], f"{o.name}: bestehende UVs verändert")
            self.assertEqual(names[-1], "LightmapUV")
            if uv_data_before[o.name] is not None:
                np.testing.assert_array_equal(uv.uv_array(o.data, uv_before[o.name][0]), uv_data_before[o.name])
            self.assertEqual([s.material.name for s in o.material_slots if s.material], mats_before[o.name],
                             "Materialzuweisung verändert")
            rep = uv_validate.validate_layout([(o.data, "LightmapUV")], 512, 0)
            self.assertEqual(rep["invalid"], 0)
            self.assertEqual(rep["out_of_bounds_loops"], 0)
            self.assertLess(rep["overlap_fraction"], 0.01, f"{o.name}: {rep}")
        for lm in result.lightmaps:
            self.assertFileExists(lm.file_path, 500)
            img = bpy.data.images.load(lm.file_path)
            try:
                self.assertEqual(tuple(img.size), (resolution, resolution))
                stats = images.image_stats(img)
            finally:
                bpy.data.images.remove(img)
            if all(_is_transmissive(bpy.data.objects[n]) for n in lm.objects):
                # pure glass has no diffuse response: a black diffuse lightmap is correct, and reported
                self.assertTrue(any(lm.image_name in w and "schwarz" in w for w in result.warnings), result.warnings)
                continue
            self.assertGreater(stats["max"], 0.05, f"{lm.image_name}: Lightmap leer")
            self.assertGreater(stats["nonzero"], 0.02, f"{lm.image_name}: kaum belegte Pixel")
        self.assertTrue(result.reimport_check.get("ok"), result.reimport_check)
        model_path = result.exported_files[0]
        self.assertFileExists(model_path, 1000)
        self.assertFileExists(result.sidecar_path)
        # 8./9. fresh scene, re-import with automatic lightmap assignment
        reset_scene()
        report = api.import_with_lightmaps(model_path, apply=True)
        self.assertEqual(report["unmatched"], [], report)
        self.assertEqual(len(report["matched"]), len(meshes), report)
        # 10. UVs, materials, visible lightmap
        for o in [o for o in bpy.data.objects if o.type == "MESH"]:
            names = [u.name for u in o.data.uv_layers]
            self.assertIn("LightmapUV", names, o.name)
            base = o.name.rsplit(".", 1)[0] if "." in o.name else o.name
            expected_layers = len(uv_before.get(o.name, uv_before.get(base, []))) + 1
            self.assertEqual(len(names), expected_layers, o.name)
            self.assertTrue(all(materials.is_bound(s.material) for s in o.material_slots if s.material), o.name)
            for s in o.material_slots:
                node = s.material.node_tree.nodes[materials.NODE_IMAGE]
                self.assertIsNotNone(node.image)
                self.assertTrue(os.path.isfile(bpy.path.abspath(node.image.filepath)), node.image.filepath)
                self.assertEqual(s.material.node_tree.nodes[materials.NODE_UV].uv_map, "LightmapUV")
        peak, coverage = _render_visible()
        self.assertGreater(peak, 0.05, "Lightmap nach Reimport nicht sichtbar")
        self.assertGreater(coverage, 0.01)
        return result

    @needs_models
    @slow
    def test_teapot_workflow_glb(self):
        """Utah Teapot: curved surfaces, no UVs, no materials textures."""
        result = self._workflow("teapot", expect_uv_before=False)
        self.assertEqual(len(result.lightmaps), 1)

    @needs_models
    @slow
    def test_car_workflow_glb_per_object(self):
        """Toy Car: 3 meshes, textured materials with clearcoat/transmission, existing UVs."""
        result = self._workflow("car", resolution=1024)
        self.assertEqual(len(result.lightmaps), 3)
        # the glass mesh is purely transmissive: reported, not silently ignored
        self.assertTrue(any("Glass_lightmap" in w and "schwarz" in w for w in result.warnings), result.warnings)

    @needs_models
    @slow
    def test_ship_workflow_fbx_atlas(self):
        """Dutch Ship: 110k polygons, 3 materials, shared atlas, FBX export."""
        result = self._workflow("ship", fmt="FBX", atlas="SHARED_ATLAS", resolution=1024)
        self.assertEqual(len(result.lightmaps), 1)
        self.assertTrue(result.lightmaps[0].is_atlas)

    @needs_models
    @slow
    def test_car_workflow_usd(self):
        result = self._workflow("car", fmt="USD", resolution=1024)
        self.assertEqual(len(result.lightmaps), 3)

    @needs_models
    @slow
    def test_teapot_lightmap_pack_exr(self):
        src = example_model("teapot")
        objs = api.import_model(src)
        cfg = self._config(self.out("teapot_lp"))
        cfg.uv.method = "LIGHTMAP_PACK"
        cfg.image.format = "EXR"
        cfg.export.format = "GLTF"
        result = api.run_pipeline(cfg, objects=objs)
        self.assertTrue(result.success)
        self.assertTrue(result.lightmaps[0].file_path.endswith(".exr"))
        self.assertTrue(result.reimport_check["ok"], result.reimport_check)

    @needs_models
    @slow
    def test_example_models_hashes(self):
        """SOURCE.json hashes match the files in the repository (license provenance)."""
        from scripts import fetch_example_models
        for key in ("car", "ship"):
            fetch_example_models.fetch(key, verify_only=True)


if __name__ == "__main__":
    unittest.main()
