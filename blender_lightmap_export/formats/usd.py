# SPDX-License-Identifier: GPL-3.0-or-later
"""USD export via Blender's built-in USD exporter.

Verified: UV layers are written as named primvars (``primvars:LightmapUV``),
custom properties as ``userProperties``. Textures go to a ``textures``
sub-folder next to the file (``export_textures_mode='NEW'``).
"""

from __future__ import annotations

from typing import List, Optional

import bpy

from ..core.log import get_logger
from ..core.pipeline import LightmapExportError, PipelineContext
from ..core.state import select_only, ensure_object_mode
from .base import BaseExporter, FormatCapabilities, register_exporter

log = get_logger("usd")


@register_exporter("USD")
class USDExporter(BaseExporter):
    capabilities = FormatCapabilities(
        name="USD", extension=".usdc", multiple_uv_sets=True, uv_names_preserved=True,
        custom_properties=True, textures_embedded=False, lightmap_in_material=False,
        notes="UVs als benannte Primvars, Custom Properties als userProperties. Texturen im Ordner 'textures'.")

    def import_extensions(self):
        return [".usd", ".usda", ".usdc", ".usdz"]

    def check_capabilities(self, ctx: PipelineContext) -> None:
        super().check_capabilities(ctx)
        ctx.extra["format_capabilities"] = self.capabilities.__dict__

    def export(self, ctx: PipelineContext, path: str) -> List[str]:
        ensure_object_mode()
        select_only(ctx.objects, ctx.objects[0], ctx.view_layer)
        try:
            bpy.ops.wm.usd_export(
                filepath=path,
                selected_objects_only=True,
                export_uvmaps=True,
                rename_uvmaps=False,
                export_materials=True,
                export_textures_mode="NEW",
                overwrite_textures=True,
                export_custom_properties=True,
                export_mesh_colors=True,
                export_animation=False,
                export_lights=False,
                export_cameras=False,
                relative_paths=True,
            )
        except RuntimeError as exc:
            raise LightmapExportError(f"USD-Export fehlgeschlagen: {exc}") from exc
        return [path]

    def import_file(self, path: str, context: Optional[bpy.types.Context] = None) -> List[bpy.types.Object]:
        from ..core import io_import
        return io_import.import_file(path, context)
