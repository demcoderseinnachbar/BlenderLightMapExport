# SPDX-License-Identifier: MIT
"""Wavefront OBJ export.

OBJ carries exactly one UV set (the mesh's active UV layer) and no custom
properties, so a lightmap UV channel cannot be transported next to the original
UVs. Nothing is lost silently – the strategy is explicit:

* ``WARN_KEEP_ORIGINAL`` (default): original UVs are exported, a warning is
  issued, the sidecar documents that the lightmap UV is missing.
* ``REPLACE_WITH_LIGHTMAP_UV``: the lightmap UV becomes the only UV set of the
  OBJ (original UVs are *not* in the file; they stay in the Blender scene).
* ``TWO_FILES``: ``<name>.obj`` with the original UVs and
  ``<name>_lightmapuv.obj`` with the lightmap UVs.
* ``ERROR``: abort the export.
"""

from __future__ import annotations

import contextlib
import os
from typing import List, Optional

import bpy

from ..core.log import get_logger
from ..core.pipeline import LightmapExportError, PipelineContext
from ..core.state import select_only, ensure_object_mode
from .base import BaseExporter, FormatCapabilities, register_exporter

log = get_logger("obj")


@contextlib.contextmanager
def active_uv(objects, uv_name: Optional[str]):
    """Temporarily make ``uv_name`` (or the render UV when None) the active UV layer."""
    saved = []
    for o in objects:
        layers = o.data.uv_layers
        if not layers:
            continue
        saved.append((o.data.name, layers.active.name if layers.active else None))
        if uv_name is None:
            target = next((u for u in layers if u.active_render and u.name != "LightmapUV"), None)
            if target is None:
                target = next((u for u in layers if u.name != "LightmapUV"), layers[0])
        else:
            target = layers.get(uv_name)
        if target is not None:
            layers.active = target
    try:
        yield
    finally:
        for mesh_name, name in saved:
            mesh = bpy.data.meshes.get(mesh_name)
            if mesh is not None and name and name in mesh.uv_layers:
                mesh.uv_layers.active = mesh.uv_layers[name]


@register_exporter("OBJ")
class OBJExporter(BaseExporter):
    capabilities = FormatCapabilities(
        name="OBJ", extension=".obj", multiple_uv_sets=False, uv_names_preserved=False,
        custom_properties=False, textures_embedded=False, lightmap_in_material=False,
        notes="OBJ transportiert nur ein UV-Set und keine Metadaten. Strategie über export.obj_uv_strategy.")

    def import_extensions(self):
        return [".obj"]

    def check_capabilities(self, ctx: PipelineContext) -> None:
        strategy = ctx.cfg.export.obj_uv_strategy
        ctx.extra["format_capabilities"] = dict(self.capabilities.__dict__, obj_uv_strategy=strategy)
        if strategy == "ERROR":
            raise LightmapExportError("OBJ kann nur ein UV-Set transportieren; Export abgebrochen "
                                      "(export.obj_uv_strategy=ERROR). Alternativen: REPLACE_WITH_LIGHTMAP_UV, TWO_FILES "
                                      "oder ein anderes Format (GLB, FBX, USD).")
        if strategy == "WARN_KEEP_ORIGINAL":
            ctx.warn("OBJ: nur die Original-UVs werden exportiert, der Lightmap-UV-Channel ist NICHT in der Datei. "
                     "Die Lightmap kann nach einem Reimport nicht zugeordnet werden (Strategie WARN_KEEP_ORIGINAL).")
            ctx.extra["sidecar_note"] = "OBJ enthält nur Original-UVs, Lightmap-UV fehlt in der Datei"
            ctx.extra["sidecar_uv_index_override"] = -1
        elif strategy == "REPLACE_WITH_LIGHTMAP_UV":
            ctx.warn("OBJ: der Lightmap-UV-Channel ersetzt die Original-UVs in der Datei "
                     "(Strategie REPLACE_WITH_LIGHTMAP_UV). Originaltexturen passen in der OBJ nicht mehr.")
            ctx.extra["sidecar_note"] = "OBJ enthält nur den Lightmap-UV-Channel als einziges UV-Set (Index 0)"
            ctx.extra["sidecar_uv_index_override"] = 0
        elif strategy == "TWO_FILES":
            ctx.warn("OBJ: zwei Dateien werden geschrieben (Original-UVs und *_lightmapuv.obj mit Lightmap-UVs).")
            ctx.extra["sidecar_note"] = "Zwei OBJ-Dateien: Original-UVs und *_lightmapuv.obj (Lightmap-UV als Index 0)"
            ctx.extra["sidecar_uv_index_override"] = 0

    def _export_one(self, ctx: PipelineContext, path: str) -> None:
        try:
            bpy.ops.wm.obj_export(
                filepath=path,
                export_selected_objects=True,
                export_uv=True,
                export_normals=True,
                export_materials=True,
                export_triangulated_mesh=False,
                path_mode="COPY",
                apply_modifiers=True,
            )
        except RuntimeError as exc:
            raise LightmapExportError(f"OBJ-Export fehlgeschlagen: {exc}") from exc

    def export(self, ctx: PipelineContext, path: str) -> List[str]:
        ensure_object_mode()
        select_only(ctx.objects, ctx.objects[0], ctx.view_layer)
        strategy = ctx.cfg.export.obj_uv_strategy
        uv_name = ctx.cfg.uv.uv_name
        files: List[str] = []
        mtl = os.path.splitext(path)[0] + ".mtl"
        if strategy == "WARN_KEEP_ORIGINAL":
            with active_uv(ctx.objects, None):
                self._export_one(ctx, path)
            files.append(path)
        elif strategy == "REPLACE_WITH_LIGHTMAP_UV":
            with active_uv(ctx.objects, uv_name):
                self._export_one(ctx, path)
            files.append(path)
        elif strategy == "TWO_FILES":
            with active_uv(ctx.objects, None):
                self._export_one(ctx, path)
            files.append(path)
            second = os.path.splitext(path)[0] + "_lightmapuv.obj"
            with active_uv(ctx.objects, uv_name):
                self._export_one(ctx, second)
            files.append(second)
            ctx.extra["sidecar_secondary_model"] = os.path.basename(second)
        if os.path.isfile(mtl):
            files.append(mtl)
        return files

    def import_file(self, path: str, context: Optional[bpy.types.Context] = None) -> List[bpy.types.Object]:
        from ..core import io_import
        return io_import.import_file(path, context)
