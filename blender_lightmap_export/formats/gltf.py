# SPDX-License-Identifier: GPL-3.0-or-later
"""glTF / GLB export via the bundled io_scene_gltf2 add-on.

Facts (verified with Blender 5.2.3):

* both UV sets are written (``TEXCOORD_0``/``TEXCOORD_1``), but UV *names* are
  not part of glTF – on import Blender names them ``UVMap``/``UVMap.001``.
  The lightmap UV index is therefore stored in the object ``extras`` and in the
  sidecar file, and the importer renames the layer back.
* custom properties survive as ``extras`` (``export_extras=True``).
* optional: the lightmap can be embedded as ``occlusionTexture`` on
  ``TEXCOORD_1`` through the official "glTF Material Output" node group, so
  standard viewers (three.js, Babylon, ...) display it without any add-on.
  This only makes sense for AO or LDR lightmaps (single channel, 0..1).
"""

from __future__ import annotations

import contextlib
import os
from typing import List, Optional

import bpy

from ..core import materials
from ..core.log import get_logger
from ..core.pipeline import LightmapExportError, PipelineContext
from ..core.state import select_only, ensure_object_mode
from .base import BaseExporter, FormatCapabilities, register_exporter

log = get_logger("gltf")

GLTF_OUTPUT_GROUP = "glTF Material Output"
OCCLUSION_NODE = "BLME_glTFOutput"


def _gltf_output_group() -> bpy.types.ShaderNodeTree:
    ng = bpy.data.node_groups.get(GLTF_OUTPUT_GROUP)
    if ng is None:
        ng = bpy.data.node_groups.new(GLTF_OUTPUT_GROUP, "ShaderNodeTree")
        ng.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
        ng.nodes.new("NodeGroupInput")
        ng.nodes.new("NodeGroupOutput")
    elif "Occlusion" not in [s.name for s in ng.interface.items_tree if s.item_type == "SOCKET"]:
        ng.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    return ng


@contextlib.contextmanager
def lightmap_as_occlusion(objects):
    """Temporarily connect the lightmap image to a glTF Material Output node (Occlusion)."""
    touched = []
    for o in objects:
        for slot in o.material_slots:
            mat = slot.material
            if mat is None or mat.node_tree is None or not materials.is_bound(mat):
                continue
            nt = mat.node_tree
            if nt.nodes.get(OCCLUSION_NODE) is not None:
                continue
            img_node = nt.nodes.get(materials.NODE_IMAGE)
            if img_node is None or img_node.image is None:
                continue
            group = nt.nodes.new("ShaderNodeGroup")
            group.name = OCCLUSION_NODE
            group.node_tree = _gltf_output_group()
            group.location = (img_node.location.x + 300, img_node.location.y - 200)
            nt.links.new(img_node.outputs["Color"], group.inputs["Occlusion"])
            touched.append(mat.name)
    try:
        yield touched
    finally:
        for name in touched:
            mat = bpy.data.materials.get(name)
            if mat is not None and mat.node_tree is not None:
                node = mat.node_tree.nodes.get(OCCLUSION_NODE)
                if node is not None:
                    mat.node_tree.nodes.remove(node)


class _GLTFBase(BaseExporter):
    export_format = "GLB"

    def import_extensions(self):
        return [".glb", ".gltf"]

    def check_capabilities(self, ctx: PipelineContext) -> None:
        super().check_capabilities(ctx)
        ctx.extra["format_capabilities"] = self.capabilities.__dict__
        if ctx.cfg.export.gltf_lightmap_as_occlusion and ctx.cfg.bake.type != "AO":
            ctx.warn("glTF occlusionTexture: Lightmap wird als Occlusion eingebettet, obwohl der Bake-Typ nicht AO ist. "
                     "Viewer interpretieren nur den Rotkanal (0..1) als Verdeckung.")

    def export(self, ctx: PipelineContext, path: str) -> List[str]:
        ensure_object_mode()
        select_only(ctx.objects, ctx.objects[0], ctx.view_layer)
        kwargs = dict(
            filepath=path,
            export_format=self.export_format,
            use_selection=True,
            export_extras=True,
            export_texcoords=True,
            export_normals=True,
            export_materials="EXPORT",
            export_image_format="AUTO",
            export_apply=False,
            export_yup=True,
            export_animations=False,
            export_skins=False,
            export_morph=False,
            export_lights=False,
            export_cameras=False,
        )
        if self.export_format == "GLTF_SEPARATE":
            kwargs["export_keep_originals"] = False
        from . import gltf_hooks
        gltf_hooks.CURRENT_EXPORT["ctx"] = ctx
        try:
            if ctx.cfg.export.gltf_lightmap_as_occlusion:
                with lightmap_as_occlusion(ctx.objects) as touched:
                    log.info("glTF: Lightmap als Occlusion in %d Material(ien)", len(touched))
                    bpy.ops.export_scene.gltf(**kwargs)
            else:
                bpy.ops.export_scene.gltf(**kwargs)
        except RuntimeError as exc:
            raise LightmapExportError(f"glTF-Export fehlgeschlagen: {exc}") from exc
        finally:
            gltf_hooks.CURRENT_EXPORT.pop("ctx", None)
        files = [path]
        if self.export_format == "GLTF_SEPARATE":
            bin_path = os.path.splitext(path)[0] + ".bin"
            if os.path.isfile(bin_path):
                files.append(bin_path)
        return files

    def import_file(self, path: str, context: Optional[bpy.types.Context] = None) -> List[bpy.types.Object]:
        from ..core import io_import
        return io_import.import_file(path, context)


@register_exporter("GLB")
class GLBExporter(_GLTFBase):
    export_format = "GLB"
    capabilities = FormatCapabilities(
        name="GLB", extension=".glb", multiple_uv_sets=True, uv_names_preserved=False,
        custom_properties=True, textures_embedded=True, lightmap_in_material=False,
        notes="UV-Namen gehen verloren (TEXCOORD_n), Zuordnung über Index in extras/Sidecar. "
              "Optional: Lightmap als occlusionTexture auf TEXCOORD_1.")


@register_exporter("GLTF")
class GLTFExporter(_GLTFBase):
    export_format = "GLTF_SEPARATE"
    capabilities = FormatCapabilities(
        name="GLTF", extension=".gltf", multiple_uv_sets=True, uv_names_preserved=False,
        custom_properties=True, textures_embedded=False, lightmap_in_material=False,
        notes="Wie GLB, Texturen und .bin liegen separat neben der Datei.")
