# SPDX-License-Identifier: GPL-3.0-or-later
"""Importing models by file extension."""

from __future__ import annotations

import os
from typing import List, Optional

import bpy

from ..config import SUPPORTED_INPUT_EXTENSIONS
from .log import get_logger
from .pipeline import LightmapExportError, PipelineContext
from .state import ensure_object_mode

log = get_logger("import")


def is_supported_input(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED_INPUT_EXTENSIONS


def _run_importer(path: str, ext: str) -> None:
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path, use_custom_props=True)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext in (".usd", ".usda", ".usdc", ".usdz"):
        bpy.ops.wm.usd_import(filepath=path, import_textures_mode="IMPORT_PACK")
    else:
        raise LightmapExportError(f"Nicht unterstütztes Eingabeformat '{ext}' ({path})")


def import_file(path: str, context: Optional[bpy.types.Context] = None) -> List[bpy.types.Object]:
    """Import ``path`` into the current scene; return the newly created objects.

    ``.blend`` files replace the current file (all objects of the opened file
    are returned).
    """
    context = context or bpy.context
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise LightmapExportError(f"Eingabedatei nicht gefunden: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_INPUT_EXTENSIONS:
        raise LightmapExportError(
            f"Nicht unterstütztes Eingabeformat '{ext}'. Unterstützt: {', '.join(SUPPORTED_INPUT_EXTENSIONS)}")
    ensure_object_mode()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=path, load_ui=False)
        return [o for o in bpy.context.scene.objects]
    before = {o.name for o in bpy.data.objects}
    try:
        _run_importer(path, ext)
    except RuntimeError as exc:
        raise LightmapExportError(f"Import von '{path}' fehlgeschlagen: {exc}") from exc
    new_objects = [o for o in bpy.data.objects if o.name not in before]
    if not new_objects:
        raise LightmapExportError(f"Import von '{path}' lieferte keine Objekte (Datei defekt oder leer?)")
    log.info("Importiert: %s (%d Objekte)", os.path.basename(path), len(new_objects))
    return new_objects


def step_import(ctx: PipelineContext) -> None:
    objs = import_file(ctx.cfg.input_file, ctx.context)
    # the .blend importer replaces the whole file: refresh context references
    ctx.scene = bpy.context.scene
    ctx.view_layer = bpy.context.view_layer
    ctx.requested_objects = objs
    ctx.extra["imported_objects"] = [o.name for o in objs]
