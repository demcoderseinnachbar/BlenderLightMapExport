# SPDX-License-Identifier: MIT
"""Hooks for the bundled glTF importer/exporter.

The glTF add-on looks for ``glTF2ExportUserExtension`` / ``glTF2ImportUserExtension``
on every *enabled* add-on module. The classes are re-exported from the package
``__init__`` so they are found when the extension is enabled.

* Export: writes a compact lightmap summary into ``asset.extras`` so a GLB
  carries the information even without the sidecar file.
* Import: after the nodes of a scene are created, lightmaps are attached
  automatically (sidecar → extras → file names) when the preference
  "auto_apply_on_gltf_import" is on.
"""

from __future__ import annotations

import os
from typing import Any, Dict

import bpy

from ..core.log import get_logger

log = get_logger("gltf_hooks")

CURRENT_EXPORT: Dict[str, Any] = {}
ASSET_EXTRAS_KEY = "BLME_lightmaps"


def _prefs_auto_apply() -> bool:
    try:
        from ..ui.preferences import get_prefs
        prefs = get_prefs()
        return True if prefs is None else bool(prefs.auto_apply_on_gltf_import)
    except Exception:
        return True


class glTF2ExportUserExtension:
    def __init__(self):
        from io_scene_gltf2.io.com.gltf2_io_extensions import Extension  # noqa: F401
        self.Extension = Extension

    def gather_asset_hook(self, gltf2_asset, export_settings):
        ctx = CURRENT_EXPORT.get("ctx")
        if ctx is None or not ctx.result.lightmaps:
            return
        if gltf2_asset.extras is None:
            gltf2_asset.extras = {}
        model_dir = os.path.dirname(ctx.export_path) if ctx.export_path else ctx.output_dir
        from ..core import naming
        gltf2_asset.extras[ASSET_EXTRAS_KEY] = {
            "version": 1,
            "uv_name": ctx.cfg.uv.uv_name,
            "bake_type": ctx.cfg.bake.type,
            "colorspace": "linear",
            "lightmaps": [
                {"file": naming.relpath(lm.file_path, model_dir), "objects": list(lm.objects),
                 "resolution": lm.resolution, "is_atlas": lm.is_atlas}
                for lm in ctx.result.lightmaps
            ],
        }


class glTF2ImportUserExtension:
    def __init__(self):
        self.properties = None
        self.filename = ""

    def gather_import_gltf_before_hook(self, gltf):
        self.filename = getattr(gltf, "filename", "") or ""

    def gather_import_scene_after_nodes_hook(self, gltf_scene, blender_scene, gltf):
        if not _prefs_auto_apply():
            return
        path = self.filename or getattr(gltf, "filename", "")
        if not path:
            return
        objects = []
        for vnode in getattr(gltf, "vnodes", {}).values():
            obj = getattr(vnode, "blender_object", None)
            if obj is not None and obj.type == "MESH":
                objects.append(obj)
        if not objects:
            return
        try:
            from ..core import metadata
            report = metadata.attach_lightmaps(objects, path, apply=True)
        except Exception as exc:  # never break the import
            log.warning("Automatische Lightmap-Zuordnung fehlgeschlagen: %s", exc)
            return
        if report["matched"]:
            log.info("glTF-Import: Lightmaps für %d Objekt(e) zugewiesen (%s)", len(report["matched"]),
                     ", ".join(sorted(set(report["source"].values()))))


def draw_import(context, layout):
    layout.label(text="Lightmap Exporter: Lightmaps werden automatisch zugewiesen", icon="LIGHT_DATA")
