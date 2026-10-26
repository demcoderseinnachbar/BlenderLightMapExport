# SPDX-License-Identifier: GPL-3.0-or-later
"""Lightmap preview materials: binding, bypass for export, restore."""

import unittest

import bpy

from tests.helpers import BlenderTestCase, quick_config
from scripts import generate_test_scenes as gen
from blender_lightmap_export import api
from blender_lightmap_export.core import materials


def _surface_source(mat):
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    link = out.inputs["Surface"].links[0]
    return link.from_node.bl_idname


class MaterialTests(BlenderTestCase):

    def test_bind_and_restore(self):
        (obj,) = gen.existing_uvs()
        mat = obj.material_slots[0].material
        n_nodes = len(mat.node_tree.nodes)
        n_links = len(mat.node_tree.links)
        self.assertEqual(_surface_source(mat), "ShaderNodeBsdfPrincipled")
        cfg = quick_config(self.tmp)
        api.bake_lightmaps(cfg, objects=[obj])
        self.assertTrue(materials.is_bound(mat))
        self.assertEqual(_surface_source(mat), "ShaderNodeGroup")
        group = mat.node_tree.nodes[materials.NODE_GROUP]
        self.assertEqual(group.inputs["Preview"].default_value, 1.0)
        self.assertEqual(mat.node_tree.nodes[materials.NODE_UV].uv_map, "LightmapUV")
        # base colour texture feeds the group so lighting * albedo is shown
        self.assertTrue(group.inputs["Base Color"].is_linked)
        self.assertEqual(group.inputs["Base Color"].links[0].from_node.bl_idname, "ShaderNodeTexImage")
        self.assertEqual(api.restore_materials([obj]), 1)
        self.assertFalse(materials.is_bound(mat))
        self.assertEqual(_surface_source(mat), "ShaderNodeBsdfPrincipled")
        self.assertEqual(len(mat.node_tree.nodes), n_nodes)
        self.assertEqual(len(mat.node_tree.links), n_links)
        self.assertNotIn(materials.PROP_RESTORE, mat)

    def test_mode_switch(self):
        (obj,) = gen.cube()
        api.bake_lightmaps(quick_config(self.tmp), objects=[obj])
        mat = obj.material_slots[0].material
        self.assertEqual(api.apply_lightmaps([obj], mode="ORIGINAL"), 1)
        self.assertEqual(mat.node_tree.nodes[materials.NODE_GROUP].inputs["Preview"].default_value, 0.0)
        api.apply_lightmaps([obj], mode="PREVIEW")
        self.assertEqual(mat.node_tree.nodes[materials.NODE_GROUP].inputs["Preview"].default_value, 1.0)

    def test_original_materials_context(self):
        (obj,) = gen.cube()
        api.bake_lightmaps(quick_config(self.tmp), objects=[obj])
        mat = obj.material_slots[0].material
        with materials.original_materials([obj]):
            self.assertEqual(_surface_source(mat), "ShaderNodeBsdfPrincipled")
        self.assertEqual(_surface_source(mat), "ShaderNodeGroup")

    def test_bake_type_value(self):
        (obj,) = gen.cube()
        api.bake_lightmaps(quick_config(self.tmp, bake__type="AO"), objects=[obj])
        group = obj.material_slots[0].material.node_tree.nodes[materials.NODE_GROUP]
        self.assertEqual(group.inputs["Lightmap Type"].default_value, 2.0)

    def test_preview_disabled_leaves_materials(self):
        (obj,) = gen.cube()
        result = api.bake_lightmaps(quick_config(self.tmp, export__apply_lightmap_preview=False), objects=[obj])
        self.assertTrue(result.success)
        self.assertFalse(materials.is_bound(obj.material_slots[0].material))
        self.assertIn("BLME_lightmap", obj)

    def test_rebake_updates_existing_binding(self):
        (obj,) = gen.cube()
        cfg = quick_config(self.tmp)
        api.bake_lightmaps(cfg, objects=[obj])
        mat = obj.material_slots[0].material
        cfg.output_dir = self.out("second")
        api.bake_lightmaps(cfg, objects=[obj])
        self.assertEqual(sum(1 for n in mat.node_tree.nodes if n.name.startswith("BLME_")), 3)

    def test_group_node_renders(self):
        """The preview shader must actually produce a visible image (EEVEE render of the cube)."""
        (obj,) = gen.cube()
        api.bake_lightmaps(quick_config(self.tmp, lighting__mode="DEFAULT_RIG"), objects=[obj])
        sc = bpy.context.scene
        cam_data = bpy.data.cameras.new("Cam")
        cam = bpy.data.objects.new("Cam", cam_data)
        sc.collection.objects.link(cam)
        cam.location = (3, -3, 2.5)
        cam.rotation_euler = (1.1, 0, 0.8)
        sc.camera = cam
        for o in sc.objects:
            if o.type == "LIGHT":
                o.hide_render = True  # only the lightmap emission may light the cube
        sc.render.engine = "CYCLES"
        sc.cycles.samples = 4
        sc.render.resolution_x = sc.render.resolution_y = 64
        sc.render.resolution_percentage = 100
        sc.render.image_settings.file_format = "PNG"
        sc.render.filepath = self.out("render.png")
        sc.world = None
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(sc.render.filepath)
        px = img.pixels[:]
        self.assertGreater(max(px[0::4]), 0.05, "Lightmap-Vorschau ist im Render nicht sichtbar")


if __name__ == "__main__":
    unittest.main()
