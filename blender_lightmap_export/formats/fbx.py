# SPDX-License-Identifier: GPL-3.0-or-later
"""FBX export via the bundled io_scene_fbx add-on.

Verified: both UV layers keep their names, custom properties survive
(``use_custom_props``). Textures are copied next to the file (``path_mode='COPY'``).
FBX has no notion of a lightmap material slot; the binding is restored from the
sidecar / custom properties by the add-on importer.
"""

from __future__ import annotations

from typing import List, Optional

import bpy

from ..core.log import get_logger
from ..core.pipeline import LightmapExportError, PipelineContext
from ..core.state import select_only, ensure_object_mode
from .base import BaseExporter, FormatCapabilities, register_exporter

log = get_logger("fbx")


@register_exporter("FBX")
class FBXExporter(BaseExporter):
    capabilities = FormatCapabilities(
        name="FBX", extension=".fbx", multiple_uv_sets=True, uv_names_preserved=True,
        custom_properties=True, textures_embedded=False, lightmap_in_material=False,
        notes="Texturen werden neben die Datei kopiert. Lightmap-Zuordnung über Custom Properties/Sidecar.")

    def import_extensions(self):
        return [".fbx"]

    def check_capabilities(self, ctx: PipelineContext) -> None:
        super().check_capabilities(ctx)
        ctx.extra["format_capabilities"] = self.capabilities.__dict__

    def export(self, ctx: PipelineContext, path: str) -> List[str]:
        ensure_object_mode()
        select_only(ctx.objects, ctx.objects[0], ctx.view_layer)
        try:
            bpy.ops.export_scene.fbx(
                filepath=path,
                use_selection=True,
                object_types={"MESH"},
                use_custom_props=True,
                path_mode="COPY",
                embed_textures=False,
                mesh_smooth_type="FACE",
                use_mesh_modifiers=True,
                add_leaf_bones=False,
                bake_anim=False,
            )
        except RuntimeError as exc:
            raise LightmapExportError(f"FBX-Export fehlgeschlagen: {exc}") from exc
        return [path]

    def import_file(self, path: str, context: Optional[bpy.types.Context] = None) -> List[bpy.types.Object]:
        from ..core import io_import
        return io_import.import_file(path, context)
