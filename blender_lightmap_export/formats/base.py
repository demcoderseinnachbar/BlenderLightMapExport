# SPDX-License-Identifier: MIT
"""Exporter interface, capabilities and registry."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Type

import bpy

from ..core.log import get_logger
from ..core.pipeline import LightmapExportError, PipelineContext

log = get_logger("formats")


@dataclass(frozen=True)
class FormatCapabilities:
    name: str
    extension: str
    multiple_uv_sets: bool
    uv_names_preserved: bool
    custom_properties: bool
    textures_embedded: bool
    lightmap_in_material: bool
    notes: str = ""


class BaseExporter:
    """Base class of all format exporters. Subclasses implement :meth:`export`."""

    capabilities: FormatCapabilities = FormatCapabilities("NONE", "", False, False, False, False, False)
    importer_available: bool = True

    # --- pipeline steps ------------------------------------------------------
    def step_export(self, ctx: PipelineContext) -> None:
        from ..core import materials
        cfg = ctx.cfg
        self.check_capabilities(ctx)
        path = self.export_path(ctx)
        if os.path.exists(path) and not cfg.export.overwrite:
            raise LightmapExportError(f"Datei existiert bereits und Überschreiben ist deaktiviert: {path}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # export always sees the original material graphs
        with materials.original_materials(ctx.objects):
            files = self.export(ctx, path)
        ctx.export_path = path
        for f in files:
            if f not in ctx.result.exported_files:
                ctx.result.exported_files.append(f)
        for f in files:
            if not os.path.isfile(f):
                raise LightmapExportError(f"Export meldete Erfolg, aber Datei fehlt: {f}")
        log.info("Exportiert: %s", ", ".join(files))

    def step_reimport_check(self, ctx: PipelineContext) -> None:
        from ..core import metadata
        ctx.result.reimport_check = metadata.verify_reimport(ctx, self)

    # --- hooks for subclasses ------------------------------------------------
    def export_path(self, ctx: PipelineContext) -> str:
        return os.path.join(ctx.output_dir, ctx.base_name + self.capabilities.extension)

    def check_capabilities(self, ctx: PipelineContext) -> None:
        caps = self.capabilities
        if not caps.multiple_uv_sets:
            ctx.warn(f"{caps.name}: unterstützt nur ein UV-Set. {caps.notes}")
        elif not caps.uv_names_preserved:
            ctx.warn(f"{caps.name}: UV-Namen gehen verloren, die Zuordnung erfolgt über den UV-Index "
                     f"(TEXCOORD_n) und die Sidecar-Datei")
        if not caps.lightmap_in_material:
            log.info("%s: Lightmap-Materialverknüpfung wird nur als Metadaten/Sidecar transportiert", caps.name)

    def export(self, ctx: PipelineContext, path: str) -> List[str]:
        raise NotImplementedError

    def import_file(self, path: str, context: Optional[bpy.types.Context] = None) -> List[bpy.types.Object]:
        """Import ``path`` and return the new objects."""
        raise NotImplementedError

    def import_extensions(self) -> List[str]:
        return [self.capabilities.extension]


_REGISTRY: Dict[str, Type[BaseExporter]] = {}


def register_exporter(name: str):
    def deco(cls: Type[BaseExporter]):
        _REGISTRY[name.upper()] = cls
        return cls
    return deco


def _ensure_loaded() -> None:
    if _REGISTRY:
        return
    from . import gltf, fbx, obj, usd  # noqa: F401  (registration side effect)


def get_exporter(name: str) -> BaseExporter:
    _ensure_loaded()
    try:
        return _REGISTRY[name.upper()]()
    except KeyError:
        raise LightmapExportError(f"Unbekanntes Exportformat '{name}', verfügbar: {', '.join(sorted(_REGISTRY))}")


def available_formats() -> List[str]:
    _ensure_loaded()
    return sorted(_REGISTRY)


def exporter_for_path(path: str) -> Optional[BaseExporter]:
    _ensure_loaded()
    ext = os.path.splitext(path)[1].lower()
    for cls in _REGISTRY.values():
        inst = cls()
        if ext in inst.import_extensions():
            return inst
    return None
