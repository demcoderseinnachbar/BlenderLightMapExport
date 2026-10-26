# SPDX-License-Identifier: GPL-3.0-or-later
"""Public Python API.

Example::

    from blender_lightmap_export import export_lightmap

    result = export_lightmap(
        input_file="C:/Models/model.glb",
        output_dir="C:/Export",
        export_format="GLB",
        resolution=2048,
        samples=128,
        island_margin_px=8,
        bake_margin_px=12,
    )
    print(result.summary())
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import bpy

from .config import ExportConfig, ConfigError, apply_preset
from .core.pipeline import (
    LightmapExportError,
    PipelineCancelled,
    PipelineContext,
    PipelineResult,
    SyncRunner,
    build_steps,
)
from .core.log import get_logger, set_level

__all__ = [
    "LightmapExportError",
    "PipelineCancelled",
    "PipelineResult",
    "export_lightmap",
    "run_pipeline",
    "bake_lightmaps",
    "export_scene",
    "apply_lightmaps",
    "restore_materials",
    "import_model",
    "import_with_lightmaps",
    "find_lightmap_metadata",
]

log = get_logger("api")


def _prepare(cfg: ExportConfig) -> ExportConfig:
    try:
        cfg.validate_or_raise()
    except ConfigError as exc:
        raise LightmapExportError(str(exc)) from exc
    set_level(cfg.log_level)
    return cfg


def run_pipeline(cfg: ExportConfig, objects: Optional[Iterable[bpy.types.Object]] = None,
                 context: Optional[bpy.types.Context] = None,
                 progress=None, stages: Optional[List[str]] = None) -> PipelineResult:
    """Run the full pipeline (or the given ``stages``) on the current scene."""
    cfg = _prepare(cfg)
    ctx = PipelineContext(cfg, context=context, objects=list(objects) if objects is not None else None,
                          progress=progress)
    steps = build_steps(ctx, stages)
    return SyncRunner().run(ctx, steps)


def export_lightmap(input_file: str = "", output_dir: str = "", export_format: str = "GLB",
                    resolution: int = 1024, samples: int = 64, island_margin_px: float = 8.0,
                    bake_margin_px: int = 12, uv_method: str = "SMART_PROJECT",
                    bake_type: str = "DIFFUSE_LIGHTING", device: str = "AUTO", denoise: bool = False,
                    lighting: str = "AUTO", atlas_mode: str = "PER_OBJECT", image_format: str = "PNG16",
                    preset: str = "", config: Optional[ExportConfig] = None,
                    objects: Optional[Iterable[bpy.types.Object]] = None,
                    progress=None, **overrides: Any) -> PipelineResult:
    """Convenience wrapper: import ``input_file`` (optional), bake and export.

    Keyword ``overrides`` use dotted paths, e.g. ``export__reimport_check=True``
    or ``uv__angle_limit_deg=45``.
    """
    cfg = config.copy() if config is not None else ExportConfig()
    if input_file:
        cfg.input_file = input_file
    if output_dir:
        cfg.output_dir = output_dir
    cfg.export.format = export_format
    cfg.bake.resolution = resolution
    cfg.bake.samples = samples
    cfg.bake.margin_px = bake_margin_px
    cfg.bake.type = bake_type
    cfg.bake.device = device
    cfg.bake.denoise = denoise
    cfg.uv.island_margin_px = island_margin_px
    cfg.uv.method = uv_method
    cfg.lighting.mode = lighting
    cfg.atlas.mode = atlas_mode
    cfg.image.format = image_format
    if preset:
        apply_preset(cfg, preset)
    _apply_overrides(cfg, overrides)
    return run_pipeline(cfg, objects=objects, progress=progress)


def bake_lightmaps(cfg: ExportConfig, objects: Optional[Iterable[bpy.types.Object]] = None,
                   context=None, progress=None) -> PipelineResult:
    """UV + bake + save + material preview, without exporting."""
    stages = ["import", "prepare", "uv", "bake", "save", "materials"]
    return run_pipeline(cfg, objects=objects, context=context, progress=progress, stages=stages)


def export_scene(cfg: ExportConfig, objects: Optional[Iterable[bpy.types.Object]] = None,
                 context=None, progress=None) -> PipelineResult:
    """Export only, using lightmaps that were baked earlier (metadata on objects)."""
    stages = ["prepare", "export", "reimport"]
    return run_pipeline(cfg, objects=objects, context=context, progress=progress, stages=stages)


def apply_lightmaps(objects: Iterable[bpy.types.Object], mode: str = "PREVIEW") -> int:
    """Switch lightmap material preview on for objects that carry lightmap metadata."""
    from .core import materials
    return materials.apply_from_metadata(list(objects), mode=mode)


def restore_materials(objects: Iterable[bpy.types.Object]) -> int:
    from .core import materials
    return materials.restore_objects(list(objects))


def import_model(path: str, context=None) -> List[bpy.types.Object]:
    from .core import io_import
    return io_import.import_file(path, context or bpy.context)


def import_with_lightmaps(path: str, context=None, apply: bool = True, mode: str = "PREVIEW") -> Dict[str, Any]:
    """Import a model and attach lightmaps found via sidecar, metadata or file names."""
    from .core import metadata
    return metadata.import_with_lightmaps(path, context or bpy.context, apply=apply, mode=mode)


def find_lightmap_metadata(path: str) -> Optional[Dict[str, Any]]:
    from .core import metadata
    return metadata.load_sidecar_for(path)


def _apply_overrides(cfg: ExportConfig, overrides: Dict[str, Any]) -> None:
    for key, value in overrides.items():
        parts = key.split("__")
        target: Any = cfg
        for part in parts[:-1]:
            if not hasattr(target, part):
                raise LightmapExportError(f"Unbekannte Option '{key}'")
            target = getattr(target, part)
        if not hasattr(target, parts[-1]):
            raise LightmapExportError(f"Unbekannte Option '{key}'")
        setattr(target, parts[-1], value)
