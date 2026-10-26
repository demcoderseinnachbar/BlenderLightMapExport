# SPDX-License-Identifier: GPL-3.0-or-later
"""Pipeline: ordered steps executed by a synchronous (headless) or modal (UI) runner.

Every entry point (UI operator, Python API, batch script) builds the same
list of steps through :func:`build_steps`; only the runner differs.
"""

from __future__ import annotations

import os
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import bpy

from ..config import ExportConfig
from . import naming
from .log import get_logger, add_collector, remove_handler
from .state import SceneStateSnapshot, TempTracker, ensure_object_mode

log = get_logger("pipeline")

ProgressCallback = Callable[[float, str], None]


class LightmapExportError(RuntimeError):
    """Raised for any failure inside the pipeline (with a readable message)."""


class PipelineCancelled(LightmapExportError):
    """Raised when the user cancels a run."""


# --- result ---------------------------------------------------------------------

@dataclass
class LightmapInfo:
    image_name: str
    file_path: str = ""
    relative_path: str = ""
    objects: List[str] = field(default_factory=list)
    resolution: int = 0
    uv_name: str = ""
    uv_index_by_object: Dict[str, int] = field(default_factory=dict)
    bake_type: str = ""
    image_format: str = ""
    colorspace: str = "linear"
    stats: Dict[str, float] = field(default_factory=dict)
    is_atlas: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image": self.image_name,
            "file": self.relative_path or self.file_path,
            "objects": list(self.objects),
            "resolution": self.resolution,
            "uv_name": self.uv_name,
            "uv_index_by_object": dict(self.uv_index_by_object),
            "bake_type": self.bake_type,
            "image_format": self.image_format,
            "colorspace": self.colorspace,
            "is_atlas": self.is_atlas,
            "stats": dict(self.stats),
        }


@dataclass
class PipelineResult:
    success: bool = False
    objects: List[str] = field(default_factory=list)
    lightmaps: List[LightmapInfo] = field(default_factory=list)
    exported_files: List[str] = field(default_factory=list)
    sidecar_path: str = ""
    output_dir: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    timings: Dict[str, float] = field(default_factory=dict)
    reimport_check: Dict[str, Any] = field(default_factory=dict)
    uv_validation: Dict[str, Any] = field(default_factory=dict)
    device_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "objects": self.objects,
            "lightmaps": [lm.to_dict() for lm in self.lightmaps],
            "exported_files": self.exported_files,
            "sidecar": self.sidecar_path,
            "output_dir": self.output_dir,
            "warnings": self.warnings,
            "errors": self.errors,
            "timings": {k: round(v, 3) for k, v in self.timings.items()},
            "reimport_check": self.reimport_check,
            "uv_validation": self.uv_validation,
            "device_used": self.device_used,
        }

    def summary(self) -> str:
        lines = [f"Erfolg: {self.success}", f"Objekte: {len(self.objects)}",
                 f"Lightmaps: {len(self.lightmaps)}", f"Exportdateien: {len(self.exported_files)}"]
        if self.warnings:
            lines.append(f"Warnungen: {len(self.warnings)}")
        if self.errors:
            lines.append("Fehler: " + "; ".join(self.errors))
        total = sum(self.timings.values())
        lines.append(f"Dauer: {total:.1f} s")
        return "\n".join(lines)


# --- context --------------------------------------------------------------------

class PipelineContext:
    """Mutable state shared between steps."""

    def __init__(self, cfg: ExportConfig, context: Optional[bpy.types.Context] = None,
                 objects: Optional[List[bpy.types.Object]] = None,
                 progress: Optional[ProgressCallback] = None) -> None:
        self.cfg = cfg
        self.context = context or bpy.context
        self.scene = self.context.scene
        self.view_layer = self.context.view_layer
        self.requested_objects = list(objects) if objects is not None else None
        self.objects: List[bpy.types.Object] = []
        self.result = PipelineResult()
        self.temp = TempTracker()        # always undone
        self.product = TempTracker()     # undone only when the run fails
        self.snapshot: Optional[SceneStateSnapshot] = None
        self.progress = progress
        self.cancelled = False
        # populated by steps
        self.base_name: str = ""
        self.output_dir: str = ""
        self.lightmap_dir: str = ""
        self.images: Dict[str, bpy.types.Image] = {}          # image name -> image
        self.image_objects: Dict[str, List[str]] = {}         # image name -> object names
        self.material_bindings: List[Any] = []               # see materials.py
        self.light_rig: Optional[Any] = None
        self.device_info: Dict[str, Any] = {}
        self.export_path: str = ""
        self.extra: Dict[str, Any] = {}

    def warn(self, message: str) -> None:
        log.warning(message)
        self.result.warnings.append(message)

    def check_cancel(self) -> None:
        if self.cancelled:
            raise PipelineCancelled("Vorgang abgebrochen")

    def report_progress(self, fraction: float, message: str) -> None:
        if self.progress is not None:
            try:
                self.progress(max(0.0, min(1.0, fraction)), message)
            except Exception:  # pragma: no cover
                pass


# --- steps ----------------------------------------------------------------------

@dataclass
class Step:
    name: str
    label: str
    func: Callable[[PipelineContext], Any]   # may return a list of Steps to insert after itself
    weight: float = 1.0
    stage: str = ""
    bake_image: Optional[str] = None   # set for bake steps (modal runner needs it)


STAGES = ("import", "prepare", "uv", "bake", "save", "materials", "export", "reimport")


def build_steps(ctx: PipelineContext, stages: Optional[List[str]] = None) -> List[Step]:
    """Build the ordered step list for ``ctx.cfg``.

    ``stages`` restricts the pipeline, e.g. ``["prepare", "uv", "bake", "save",
    "materials"]`` for bake-only runs.
    """
    from . import io_import, lighting, uv, baking, images, materials, metadata
    from ..formats import get_exporter

    cfg = ctx.cfg
    stages = list(stages) if stages else list(STAGES)
    steps: List[Step] = []

    def add(stage, name, label, func, weight=1.0, bake_image=None):
        if stage in stages:
            steps.append(Step(name=name, label=label, func=func, weight=weight, stage=stage, bake_image=bake_image))

    if cfg.input_file:
        add("import", "import", "Modell importieren", io_import.step_import, 2.0)

    add("prepare", "collect", "Objekte sammeln", step_collect_objects, 0.2)
    add("prepare", "paths", "Ausgabepfade vorbereiten", step_prepare_paths, 0.1)
    add("prepare", "device", "Render-Gerät wählen", baking.step_select_device, 0.2)
    add("prepare", "lighting", "Beleuchtung vorbereiten", lighting.step_prepare_lighting, 0.2)

    add("uv", "uv", "Lightmap-UVs erzeugen", uv.step_create_lightmap_uvs, 2.0)
    if cfg.uv.validate:
        add("uv", "uv_validate", "UVs prüfen", uv.step_validate_uvs, 1.0)

    # step_prepare_bake_targets returns one bake step per image (inserted by the runner)
    add("bake", "bake_targets", "Bake-Ziele vorbereiten", baking.step_prepare_bake_targets, 0.5)
    add("bake", "bake_finish", "Bake abschließen", baking.step_bake_finish, 0.5)

    add("save", "denoise", "Lightmaps entrauschen", images.step_denoise, 1.0)
    add("save", "save", "Lightmaps speichern", images.step_save_images, 1.0)

    add("materials", "materials", "Materialien zuweisen", materials.step_apply_materials, 0.5)
    add("materials", "metadata_props", "Metadaten an Objekten speichern", metadata.step_write_object_metadata, 0.2)

    if cfg.export.format != "NONE":
        exporter = get_exporter(cfg.export.format)
        add("export", "export", f"Export als {cfg.export.format}", exporter.step_export, 3.0)
        add("export", "sidecar", "Sidecar-Datei schreiben", metadata.step_write_sidecar, 0.2)
        if cfg.export.reimport_check:
            add("reimport", "reimport_check", "Reimport prüfen", exporter.step_reimport_check, 3.0)
    return steps


# --- generic steps ----------------------------------------------------------------

def collect_mesh_objects(ctx: PipelineContext) -> List[bpy.types.Object]:
    cfg = ctx.cfg
    vl = ctx.view_layer
    if ctx.requested_objects is not None:
        candidates = list(ctx.requested_objects)
    elif cfg.export.scope == "SCENE" or cfg.input_file:
        candidates = [o for o in vl.objects]
    else:
        candidates = [o for o in vl.objects if o.select_get(view_layer=vl)]
        if not candidates:
            candidates = [o for o in vl.objects]
            if candidates:
                ctx.warn("Keine Objekte ausgewählt, verwende alle Objekte der Szene")
    meshes = []
    for o in candidates:
        if o.type != "MESH":
            if o.type not in ("LIGHT", "CAMERA", "EMPTY"):
                ctx.warn(f"Objekt '{o.name}' ({o.type}) wird übersprungen, nur Meshes werden unterstützt")
            continue
        if len(o.data.polygons) == 0:
            ctx.warn(f"Objekt '{o.name}' hat keine Flächen und wird übersprungen")
            continue
        if o.hide_render:
            ctx.warn(f"Objekt '{o.name}' ist für das Rendern ausgeblendet und wird übersprungen")
            continue
        meshes.append(o)
    return meshes


def step_collect_objects(ctx: PipelineContext) -> None:
    ensure_object_mode()
    ctx.objects = collect_mesh_objects(ctx)
    if not ctx.objects:
        raise LightmapExportError("Keine Mesh-Objekte zum Verarbeiten gefunden")
    ctx.result.objects = [o.name for o in ctx.objects]
    for o in ctx.objects:
        s = o.matrix_world.to_scale()
        if s.x * s.y * s.z < 0:
            ctx.warn(f"Objekt '{o.name}' hat eine negative Skalierung, Normalen können beim Backen invertiert sein")
        if any(m.type in ("MIRROR", "ARRAY") for m in o.modifiers):
            ctx.warn(f"Objekt '{o.name}' hat Mirror/Array-Modifikatoren, die UVs können sich im Bake überlappen")
    log.info("Verarbeite %d Objekt(e): %s", len(ctx.objects), ", ".join(ctx.result.objects))


def step_prepare_paths(ctx: PipelineContext) -> None:
    cfg = ctx.cfg
    if cfg.export.base_name:
        ctx.base_name = naming.sanitize(cfg.export.base_name)
    elif cfg.input_file:
        ctx.base_name = naming.base_name_from_path(cfg.input_file)
    elif bpy.data.filepath:
        ctx.base_name = naming.base_name_from_path(bpy.data.filepath)
    elif len(ctx.objects) == 1:
        ctx.base_name = naming.sanitize(ctx.objects[0].name)
    else:
        ctx.base_name = "Scene"
    out = cfg.output_dir or (os.path.dirname(bpy.data.filepath) if bpy.data.filepath else "")
    if not out:
        out = os.path.join(bpy.app.tempdir or os.getcwd(), "lightmap_export")
        ctx.warn(f"Kein Ausgabeverzeichnis angegeben, verwende {out}")
    out = os.path.abspath(bpy.path.abspath(out))
    os.makedirs(out, exist_ok=True)
    ctx.output_dir = out
    ctx.result.output_dir = out
    multi = len(ctx.objects) > 1 and cfg.atlas.mode == "PER_OBJECT"
    if multi or cfg.image.always_use_subdir:
        ctx.lightmap_dir = os.path.join(out, cfg.image.lightmap_subdir) if cfg.image.lightmap_subdir else out
    else:
        ctx.lightmap_dir = out
    os.makedirs(ctx.lightmap_dir, exist_ok=True)
    log.info("Ausgabe: %s (Basisname %s)", out, ctx.base_name)


# --- runner --------------------------------------------------------------------------

class SyncRunner:
    """Runs all steps immediately (headless / Python API)."""

    def run(self, ctx: PipelineContext, steps: List[Step]) -> PipelineResult:
        collector = add_collector()
        ctx.snapshot = SceneStateSnapshot(ctx.context)
        total = sum(s.weight for s in steps) or 1.0
        done = 0.0
        failed = False
        try:
            steps = list(steps)
            i = 0
            while i < len(steps):
                step = steps[i]
                ctx.check_cancel()
                ctx.extra["current_step"] = step.name
                ctx.report_progress(done / total, step.label)
                log.info("--- %s", step.label)
                t0 = time.perf_counter()
                new_steps = step.func(ctx)
                ctx.result.timings[step.name] = ctx.result.timings.get(step.name, 0.0) + time.perf_counter() - t0
                done += step.weight
                if new_steps:
                    steps[i + 1:i + 1] = list(new_steps)
                    total += sum(s.weight for s in new_steps)
                i += 1
            ctx.result.success = True
            ctx.report_progress(1.0, "Fertig")
        except PipelineCancelled as exc:
            failed = True
            ctx.result.errors.append(str(exc))
            raise
        except LightmapExportError as exc:
            failed = True
            ctx.result.errors.append(str(exc))
            log.error("%s", exc)
            raise
        except Exception as exc:
            failed = True
            msg = f"Unerwarteter Fehler in Schritt '{ctx.extra.get('current_step', '?')}': {exc}"
            ctx.result.errors.append(msg)
            log.error("%s\n%s", msg, traceback.format_exc())
            raise LightmapExportError(msg) from exc
        finally:
            finish_run(ctx, failed)
            for level, msg in collector.records:
                if level == "ERROR" and msg not in ctx.result.errors:
                    ctx.result.errors.append(msg)
            remove_handler(collector)
        return ctx.result


def finish_run(ctx: PipelineContext, failed: bool) -> None:
    """Undo temporary changes; on failure also undo product changes."""
    try:
        ensure_object_mode()
        ctx.temp.cleanup()
        if failed:
            ctx.product.cleanup(remove_images=True)
    finally:
        if ctx.snapshot is not None:
            ctx.snapshot.restore()
