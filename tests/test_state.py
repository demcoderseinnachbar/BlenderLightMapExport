# SPDX-License-Identifier: MIT
"""Tests for state snapshot/restore and temporary datablock tracking."""

import unittest

import bpy

from tests.helpers import BlenderTestCase
from blender_lightmap_export.core.state import SceneStateSnapshot, TempTracker, preserved_scene_state


class StateTests(BlenderTestCase):

    def test_snapshot_restores_render_settings(self):
        sc = bpy.context.scene
        sc.render.engine = "BLENDER_EEVEE"
        sc.render.bake.margin = 3
        sc.render.image_settings.file_format = "JPEG"
        snap = SceneStateSnapshot()
        sc.render.engine = "CYCLES"
        sc.render.bake.margin = 40
        sc.render.image_settings.file_format = "OPEN_EXR"
        sc.cycles.samples = 7
        snap.restore()
        self.assertEqual(sc.render.engine, "BLENDER_EEVEE")
        self.assertEqual(sc.render.bake.margin, 3)
        self.assertEqual(sc.render.image_settings.file_format, "JPEG")

    def test_snapshot_restores_selection_and_uv(self):
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.object
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.object
        cube.data.uv_layers.new(name="Second")
        cube.data.uv_layers.active = cube.data.uv_layers["UVMap"]
        cube.data.uv_layers["UVMap"].active_render = True
        cube.select_set(True)
        plane.select_set(False)
        bpy.context.view_layer.objects.active = cube
        with preserved_scene_state():
            cube.data.uv_layers.active = cube.data.uv_layers["Second"]
            cube.data.uv_layers["Second"].active_render = True
            plane.select_set(True)
            cube.select_set(False)
            bpy.context.view_layer.objects.active = plane
            bpy.ops.object.mode_set(mode="EDIT")
        self.assertEqual(bpy.context.mode, "OBJECT")
        self.assertEqual(cube.data.uv_layers.active.name, "UVMap")
        self.assertTrue(cube.data.uv_layers["UVMap"].active_render)
        self.assertTrue(cube.select_get())
        self.assertFalse(plane.select_get())
        self.assertEqual(bpy.context.view_layer.objects.active, cube)

    def test_snapshot_restores_on_exception(self):
        sc = bpy.context.scene
        sc.cycles.samples = 11
        try:
            with preserved_scene_state():
                sc.cycles.samples = 999
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        self.assertEqual(sc.cycles.samples, 11)

    def test_temp_tracker_removes_objects_and_data(self):
        tracker = TempTracker()
        bpy.ops.object.light_add(type="SUN")
        light = bpy.context.object
        tracker.add_object(light)
        coll = bpy.data.collections.new("TmpColl")
        bpy.context.scene.collection.children.link(coll)
        tracker.add_collection(coll)
        img = bpy.data.images.new("TmpImg", 8, 8)
        tracker.add_image(img, keep=False)
        ng = bpy.data.node_groups.new("TmpNG", "ShaderNodeTree")
        tracker.add_node_group(ng)
        n_lights = len(bpy.data.lights)
        tracker.cleanup()
        self.assertIsNone(bpy.data.objects.get("Sun"))
        self.assertIsNone(bpy.data.collections.get("TmpColl"))
        self.assertIsNone(bpy.data.images.get("TmpImg"))
        self.assertIsNone(bpy.data.node_groups.get("TmpNG"))
        self.assertEqual(len(bpy.data.lights), n_lights - 1)

    def test_temp_tracker_material_and_mesh_copies(self):
        tracker = TempTracker()
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        mat = bpy.data.materials.new("Orig")
        obj.data.materials.append(mat)
        cp = mat.copy()
        cp_name = cp.name
        obj.material_slots[0].material = cp
        tracker.add_material_copy(obj, 0, mat, cp)
        mesh_cp = obj.data.copy()
        orig_mesh = obj.data
        obj.data = mesh_cp
        tracker.add_mesh_copy(obj, orig_mesh, mesh_cp)
        mat.use_nodes = True
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.name = "TMP_NODE"
        tracker.add_nodes(mat, ["TMP_NODE"])
        tracker.cleanup()
        self.assertEqual(obj.material_slots[0].material, mat)
        self.assertIsNone(bpy.data.materials.get(cp_name))
        self.assertEqual(obj.data, orig_mesh)
        self.assertIsNone(mat.node_tree.nodes.get("TMP_NODE"))

    def test_temp_tracker_keeps_images_by_default(self):
        tracker = TempTracker()
        img = bpy.data.images.new("KeepImg", 4, 4)
        tracker.add_image(img, keep=True)
        tracker.cleanup()
        self.assertIsNotNone(bpy.data.images.get("KeepImg"))
        tracker.add_image(img, keep=True)
        tracker.cleanup(remove_images=True)
        self.assertIsNone(bpy.data.images.get("KeepImg"))


if __name__ == "__main__":
    unittest.main()
