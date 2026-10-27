# SPDX-License-Identifier: MIT
"""Export, reimport and automatic lightmap assignment for every format."""

import json
import os
import shutil
import subprocess
import sys
import unittest

import bpy
import numpy as np

from tests.helpers import BlenderTestCase, quick_config, slow, reset_scene, REPO_ROOT
from scripts import generate_test_scenes as gen
from blender_lightmap_export import api
from blender_lightmap_export.core import materials, metadata, uv
from blender_lightmap_export.core.pipeline import LightmapExportError
from blender_lightmap_export.formats import available_formats


def _render_max(scene_objects_lights_hidden=True, size=48):
    """Render the current scene with Cycles (lights hidden) and return the max red value."""
    sc = bpy.context.scene
    cam = bpy.data.objects.get("BLME_TestCam")
    if cam is None:
        cam_data = bpy.data.cameras.new("BLME_TestCam")
        cam = bpy.data.objects.new("BLME_TestCam", cam_data)
        sc.collection.objects.link(cam)
        cam.location = (4, -4, 3)
        cam.rotation_euler = (1.05, 0, 0.785)
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
    path = os.path.join(bpy.app.tempdir, "blme_render_check.png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    try:
        px = img.pixels[:]
        return max(px[0::4])
    finally:
        bpy.data.images.remove(img)


class ExportTests(BlenderTestCase):

    def _bake_and_export(self, objs, fmt, **kw):
        cfg = quick_config(self.tmp, export__format=fmt, export__scope="SCENE", **kw)
        return api.run_pipeline(cfg, objects=objs), cfg

    def _reimport(self, path, apply=True):
        reset_scene()
        return api.import_with_lightmaps(path, apply=apply)

    def _check_visible(self):
        self.assertGreater(_render_max(), 0.02, "Lightmap nach Reimport nicht sichtbar")

    # --- registry ------------------------------------------------------------------
    def test_available_formats(self):
        self.assertEqual(available_formats(), ["FBX", "GLB", "GLTF", "OBJ", "USD"])

    # --- GLB ------------------------------------------------------------------------
    def test_glb_roundtrip_with_auto_assignment(self):
        objs = gen.multi_material()
        result, cfg = self._bake_and_export(objs, "GLB")
        self.assertTrue(result.success)
        glb = os.path.join(self.tmp, "Scene.glb")
        self.assertFileExists(glb, 1000)
        self.assertFileExists(result.sidecar_path)
        self.assertEqual(len(result.lightmaps), 2)
        sidecar = json.load(open(result.sidecar_path, encoding="utf-8"))
        self.assertEqual(set(sidecar["objects"]), {"MultiMat", "MultiGround"})
        self.assertTrue(sidecar["objects"]["MultiMat"]["lightmap"].startswith("Lightmaps/"))
        self.assertEqual(sidecar["objects"]["MultiMat"]["uv_index"], 1)
        expected_uv = {o.name: uv.uv_array(o.data, "LightmapUV").copy() for o in objs}

        report = self._reimport(glb)
        self.assertEqual(sorted(report["matched"]), ["MultiGround", "MultiMat"], report)
        self.assertEqual(report["unmatched"], [])
        self.assertEqual(report["source"]["MultiMat"], "sidecar")
        obj = bpy.data.objects["MultiMat"]
        # UV name restored from the index, both layers present
        self.assertEqual([u.name for u in obj.data.uv_layers], ["UVMap", "LightmapUV"])
        self.assertEqual(len(obj.material_slots), 3)
        for slot in obj.material_slots:
            self.assertTrue(materials.is_bound(slot.material))
            node = slot.material.node_tree.nodes[materials.NODE_IMAGE]
            self.assertTrue(node.image.filepath.endswith("MultiMat_lightmap.png"))
            self.assertEqual(slot.material.node_tree.nodes[materials.NODE_UV].uv_map, "LightmapUV")
            self.assertEqual(node.image.colorspace_settings.name, "Non-Color")
        # UV values survive (glTF splits vertices, compare as sets of rounded coordinates)
        got = {tuple(np.round(v, 4)) for v in uv.uv_array(obj.data, "LightmapUV")}
        exp = {tuple(np.round(v, 4)) for v in expected_uv["MultiMat"]}
        self.assertTrue(exp <= got, "LightmapUV-Koordinaten nach Reimport verändert")
        self._check_visible()

    def test_glb_custom_property_fallback_without_sidecar(self):
        objs = gen.cube()
        result, cfg = self._bake_and_export(objs, "GLB")
        os.remove(result.sidecar_path)
        report = self._reimport(os.path.join(self.tmp, "Cube.glb"))
        self.assertEqual(report["matched"], ["Cube"])
        self.assertEqual(report["source"]["Cube"], "custom_property")
        self.assertIn("LightmapUV", bpy.data.objects["Cube"].data.uv_layers)

    def test_glb_without_apply_only_metadata(self):
        objs = gen.cube()
        self._bake_and_export(objs, "GLB")
        report = self._reimport(os.path.join(self.tmp, "Cube.glb"), apply=False)
        self.assertEqual(report["applied"], 0)
        obj = bpy.data.objects["Cube"]
        self.assertFalse(materials.is_bound(obj.material_slots[0].material))
        self.assertIsNotNone(metadata.read_object_metadata(obj))
        self.assertEqual(api.apply_lightmaps([obj]), 1)
        self.assertTrue(materials.is_bound(obj.material_slots[0].material))

    def test_gltf_separate_roundtrip(self):
        objs = gen.cube()
        result, cfg = self._bake_and_export(objs, "GLTF")
        gltf = os.path.join(self.tmp, "Cube.gltf")
        self.assertFileExists(gltf)
        self.assertFileExists(os.path.join(self.tmp, "Cube.bin"))
        self.assertIn(os.path.join(self.tmp, "Cube.bin"), result.exported_files)
        data = json.load(open(gltf, encoding="utf-8"))
        self.assertIn("BLME_lightmap", json.dumps(data))
        self.assertIn("TEXCOORD_1", json.dumps(data))
        report = self._reimport(gltf)
        self.assertEqual(report["matched"], ["Cube"])
        self._check_visible()

    def test_gltf_lightmap_as_occlusion(self):
        objs = gen.cube()
        result, cfg = self._bake_and_export(objs, "GLTF", bake__type="AO", export__gltf_lightmap_as_occlusion=True)
        data = json.load(open(os.path.join(self.tmp, "Cube.gltf"), encoding="utf-8"))
        mat = data["materials"][0]
        self.assertIn("occlusionTexture", mat, mat)
        self.assertEqual(mat["occlusionTexture"].get("texCoord"), 1)
        # temporary glTF output node removed again
        self.assertIsNone(objs[0].material_slots[0].material.node_tree.nodes.get("BLME_glTFOutput"))

    def test_reimport_check_option(self):
        objs = gen.multi_material()
        n_objects = len(bpy.data.objects)
        result, cfg = self._bake_and_export(objs, "GLB", export__reimport_check=True)
        self.assertTrue(result.reimport_check.get("ok"), result.reimport_check)
        self.assertEqual(len(result.reimport_check["objects"]), 2)
        self.assertEqual(len(bpy.data.objects), n_objects, "Reimport-Prüfung hat Objekte hinterlassen")
        for o in objs:
            self.assertTrue(materials.is_bound(o.material_slots[0].material))

    # --- FBX --------------------------------------------------------------------------
    def test_fbx_roundtrip(self):
        objs = gen.multi_material()
        result, cfg = self._bake_and_export(objs, "FBX")
        fbx = os.path.join(self.tmp, "Scene.fbx")
        self.assertFileExists(fbx, 1000)
        report = self._reimport(fbx)
        self.assertEqual(sorted(report["matched"]), ["MultiGround", "MultiMat"], report)
        obj = bpy.data.objects["MultiMat"]
        self.assertEqual([u.name for u in obj.data.uv_layers], ["UVMap", "LightmapUV"])
        self.assertEqual(len(obj.data.polygons), 6)
        self.assertTrue(all(materials.is_bound(s.material) for s in obj.material_slots))
        self._check_visible()

    def test_fbx_custom_props_without_sidecar(self):
        objs = gen.cube()
        result, cfg = self._bake_and_export(objs, "FBX")
        os.remove(result.sidecar_path)
        report = self._reimport(os.path.join(self.tmp, "Cube.fbx"))
        self.assertEqual(report["source"].get("Cube"), "custom_property", report)

    # --- USD --------------------------------------------------------------------------
    def test_usd_roundtrip(self):
        objs = gen.multi_material()
        result, cfg = self._bake_and_export(objs, "USD")
        usd = os.path.join(self.tmp, "Scene.usdc")
        self.assertFileExists(usd, 1000)
        report = self._reimport(usd)
        self.assertEqual(sorted(report["matched"]), ["MultiGround", "MultiMat"], report)
        obj = bpy.data.objects["MultiMat"]
        self.assertIn("LightmapUV", [u.name for u in obj.data.uv_layers])
        self.assertIn("UVMap", [u.name for u in obj.data.uv_layers])
        self.assertTrue(all(materials.is_bound(s.material) for s in obj.material_slots))
        self._check_visible()

    # --- OBJ --------------------------------------------------------------------------
    def test_obj_warn_keep_original(self):
        objs = gen.existing_uvs()
        original = uv.uv_array(objs[0].data, "UVMap").copy()
        result, cfg = self._bake_and_export(objs, "OBJ")
        self.assertTrue(any("nur die Original-UVs" in w for w in result.warnings))
        obj_path = os.path.join(self.tmp, "TexturedCube.obj")
        self.assertFileExists(obj_path)
        self.assertFileExists(os.path.join(self.tmp, "TexturedCube.mtl"))
        report = self._reimport(obj_path)
        obj = bpy.data.objects["TexturedCube"]
        self.assertEqual(len(obj.data.uv_layers), 1)
        self.assertEqual(report["unmatched"], ["TexturedCube"])   # not silently wrong: explicitly unmatched
        got = {tuple(np.round(v, 4)) for v in uv.uv_array(obj.data, obj.data.uv_layers[0].name)}
        self.assertTrue({tuple(np.round(v, 4)) for v in original} <= got)

    def test_obj_replace_with_lightmap_uv(self):
        objs = gen.existing_uvs()
        result, cfg = self._bake_and_export(objs, "OBJ", export__obj_uv_strategy="REPLACE_WITH_LIGHTMAP_UV")
        lm_uv = uv.uv_array(objs[0].data, "LightmapUV").copy()
        self.assertIn("UVMap", objs[0].data.uv_layers)  # scene keeps the originals
        report = self._reimport(os.path.join(self.tmp, "TexturedCube.obj"))
        obj = bpy.data.objects["TexturedCube"]
        self.assertEqual(report["matched"], ["TexturedCube"])
        self.assertEqual([u.name for u in obj.data.uv_layers], ["LightmapUV"])
        got = {tuple(np.round(v, 4)) for v in uv.uv_array(obj.data, "LightmapUV")}
        self.assertTrue({tuple(np.round(v, 4)) for v in lm_uv} <= got)
        self.assertTrue(materials.is_bound(obj.material_slots[0].material))
        self._check_visible()

    def test_obj_two_files(self):
        objs = gen.cube()
        result, cfg = self._bake_and_export(objs, "OBJ", export__obj_uv_strategy="TWO_FILES")
        self.assertFileExists(os.path.join(self.tmp, "Cube.obj"))
        self.assertFileExists(os.path.join(self.tmp, "Cube_lightmapuv.obj"))
        report = self._reimport(os.path.join(self.tmp, "Cube_lightmapuv.obj"))
        self.assertEqual(report["matched"], ["Cube"])

    def test_obj_error_strategy(self):
        objs = gen.cube()
        with self.assertRaises(LightmapExportError):
            self._bake_and_export(objs, "OBJ", export__obj_uv_strategy="ERROR")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "Cube.obj")))

    # --- misc -----------------------------------------------------------------------------
    def test_overwrite_disabled(self):
        objs = gen.cube()
        self._bake_and_export(objs, "GLB")
        with self.assertRaises(LightmapExportError):
            self._bake_and_export(objs, "GLB", export__overwrite=False)

    def test_export_only_after_bake(self):
        objs = gen.cube()
        cfg = quick_config(self.tmp, export__scope="SCENE")
        api.bake_lightmaps(cfg, objects=objs)
        cfg.export.format = "GLB"
        result = api.export_scene(cfg, objects=objs)
        self.assertTrue(result.success)
        self.assertFileExists(os.path.join(self.tmp, "Cube.glb"))
        self.assertFileExists(result.sidecar_path)
        sidecar = json.load(open(result.sidecar_path, encoding="utf-8"))
        self.assertIn("Cube", sidecar["objects"])

    def test_file_name_convention_fallback(self):
        (obj,) = gen.cube()
        cfg = quick_config(self.tmp)
        api.bake_lightmaps(cfg, objects=[obj])
        api.restore_materials([obj])
        metadata.clear_object_metadata(obj)
        model = os.path.join(self.tmp, "Cube.glb")
        report = metadata.attach_lightmaps([obj], model, apply=True)
        self.assertEqual(report["matched"], ["Cube"])
        self.assertEqual(report["source"]["Cube"], "file_name")
        self.assertTrue(materials.is_bound(obj.material_slots[0].material))

    def test_shared_atlas_export_roundtrip(self):
        objs = gen.row()
        result, cfg = self._bake_and_export(objs, "GLB", atlas__mode="SHARED_ATLAS")
        self.assertEqual(len(result.lightmaps), 1)
        self.assertFileExists(os.path.join(self.tmp, "Scene_lightmap.png"))
        report = self._reimport(os.path.join(self.tmp, "Scene.glb"))
        self.assertEqual(len(report["matched"]), 4, report)
        imgs = {o.material_slots[0].material.node_tree.nodes[materials.NODE_IMAGE].image.name
                for o in bpy.data.objects if o.type == "MESH"}
        self.assertEqual(len(imgs), 1)

    @slow
    def test_gltf_hook_with_installed_extension(self):
        """The real thing: install the extension ZIP in a fresh Blender, import via File > Import > glTF."""
        objs = gen.multi_material()
        result, cfg = self._bake_and_export(objs, "GLB")
        glb = os.path.join(self.tmp, "Scene.glb")
        from scripts import build_extension
        zip_path = build_extension.build(os.path.join(REPO_ROOT, "build"))
        script = (
            "import bpy, sys, json\n"
            f"sys.path.insert(0, {repr(REPO_ROOT)})\n"
            "from scripts import build_extension\n"
            f"bpy.ops.extensions.package_install_files(filepath={repr(zip_path)}, repo='user_default', enable_on_install=True)\n"
            "mod = 'bl_ext.user_default.blender_lightmap_export'\n"
            "if mod not in sys.modules: bpy.ops.preferences.addon_enable(module=mod)\n"
            "try:\n"
            "    bpy.ops.wm.read_homefile(use_empty=True)\n"
            "    assert mod in bpy.context.preferences.addons.keys(), 'Extension nicht aktiviert'\n"
            f"    bpy.ops.import_scene.gltf(filepath={repr(glb)})\n"
            "    m = sys.modules[mod].core.materials\n"
            "    out = {o.name: {'uvs': [u.name for u in o.data.uv_layers], 'bound': all(m.is_bound(s.material) for s in o.material_slots)}\n"
            "           for o in bpy.data.objects if o.type == 'MESH'}\n"
            "    print('HOOK_RESULT ' + json.dumps(out))\n"
            "finally:\n"
            "    build_extension.uninstall()\n"
        )
        script_path = os.path.join(self.tmp, "hook_test.py")
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(script)
        res = subprocess.run([bpy.app.binary_path, "--background", "--python", script_path],
                             capture_output=True, text=True, timeout=300)
        line = next((l for l in res.stdout.splitlines() if l.startswith("HOOK_RESULT ")), None)
        self.assertIsNotNone(line, res.stdout[-3000:] + res.stderr[-2000:])
        out = json.loads(line[len("HOOK_RESULT "):])
        self.assertEqual(set(out), {"MultiMat", "MultiGround"})
        for name, entry in out.items():
            self.assertIn("LightmapUV", entry["uvs"], out)
            self.assertTrue(entry["bound"], out)


if __name__ == "__main__":
    unittest.main()
