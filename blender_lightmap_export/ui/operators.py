# SPDX-License-Identifier: MIT
"""Operators: modal pipeline runner, preview toggles, import with lightmaps, config I/O."""

from __future__ import annotations

import os
import time
import traceback
from typing import List, Optional

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from .. import api
from ..config import ExportConfig, ConfigError
from ..core import baking, materials, metadata
from ..core.log import get_logger, add_collector, remove_handler
from ..core.pipeline import (LightmapExportError, PipelineCancelled, PipelineContext, SceneStateSnapshot,
                             build_steps, finish_run)
from .preferences import get_prefs

log = get_logger("ui")

_STAGES = {
    "BAKE": ["prepare", "uv", "bake", "save", "materials"],
    "FULL": None,
    "EXPORT": ["prepare", "export", "reimport"],
}


def _redraw_all():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in ("VIEW_3D", "PROPERTIES"):
                area.tag_redraw()


def _settings(context):
    return context.scene.blme


def _visible(obj) -> bool:
    try:
        return obj.visible_get()
    except Exception:
        return not obj.hide_viewport


def _store_result(settings, result, error: str = ""):
    settings.last_summary = result.summary() if result else ""
    settings.last_files = "\n".join(result.exported_files + [lm.file_path for lm in result.lightmaps]) if result else ""
    settings.last_warnings = "\n".join(result.warnings) if result else ""
    settings.last_error = error


def set_material_preview(context, only_solid: bool = True) -> int:
    """Switch 3D viewports to Material Preview (Solid shading does not show node materials)."""
    count = 0
    wm = context.window_manager
    for window in (wm.windows if wm else []):
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type != "VIEW_3D":
                    continue
                if space.shading.type == "SOLID" or (not only_solid and space.shading.type != "RENDERED"):
                    space.shading.type = "MATERIAL"
                    count += 1
            area.tag_redraw()
    return count


def _after_success(context, settings, result):
    prefs = get_prefs()
    if result is not None and result.lightmaps and settings.apply_lightmap_preview and \
            (prefs is None or prefs.switch_viewport_shading) and not bpy.app.background:
        if set_material_preview(context):
            settings.status_text = "Fertig – Viewport auf Material Preview umgeschaltet"


# --- modal runner -----------------------------------------------------------------------

class BLME_OT_run(bpy.types.Operator):
    """Bake lightmaps and/or export using the shared pipeline (modal, UI stays responsive)"""
    bl_idname = "blme.run"
    bl_label = "Lightmap-Pipeline ausführen"
    bl_options = {"REGISTER"}

    mode: EnumProperty(items=[("BAKE", "Bake", ""), ("FULL", "Bake & Export", ""), ("EXPORT", "Export", "")],
                       default="FULL")

    _timer = None
    _ctx: Optional[PipelineContext] = None
    _steps: List = []
    _index = 0
    _done = 0.0
    _total = 1.0
    _waiting_bake = False
    _bake_state = ""
    _step_start = 0.0
    _collector = None
    _failed = False

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and not _settings(context).is_running

    # ..........................................................................
    def _prepare(self, context):
        """Validate settings; return (cfg, objects) or None after reporting the error."""
        settings = _settings(context)
        try:
            cfg = settings.to_config()
            cfg.validate_or_raise()
        except ConfigError as exc:
            self.report({"ERROR"}, str(exc))
            return None
        if self.mode == "EXPORT" and cfg.export.format == "NONE":
            self.report({"ERROR"}, "Für den Export muss ein Exportformat gewählt sein")
            return None
        objects = None
        if cfg.export.scope == "SELECTED":
            objects = [o for o in context.selected_objects if o.type == "MESH"]
            if not objects:
                # nothing selected: process (and select) every visible mesh object of the scene
                objects = [o for o in context.scene.objects if o.type == "MESH" and _visible(o)]
                if not objects:
                    self.report({"ERROR"}, "Keine Mesh-Objekte in der Szene")
                    return None
                for o in context.selected_objects:
                    o.select_set(False)
                for o in objects:
                    try:
                        o.select_set(True)
                    except RuntimeError:
                        pass
                context.view_layer.objects.active = objects[0]
                self.report({"INFO"}, f"Keine Auswahl: alle {len(objects)} Mesh-Objekte der Szene werden verarbeitet")
        if self.mode == "EXPORT":
            if not any(metadata.read_object_metadata(o) for o in (objects or context.scene.objects)):
                self.report({"ERROR"}, "Keine gebackenen Lightmaps gefunden, bitte zuerst backen")
                return None
        return cfg, objects

    def execute(self, context):
        """Blocking run (used without a window, e.g. in background mode or from scripts)."""
        prepared = self._prepare(context)
        if prepared is None:
            return {"CANCELLED"}
        cfg, objects = prepared
        settings = _settings(context)
        settings.is_running = True
        settings.last_error = ""
        result = None
        try:
            result = api.run_pipeline(cfg, objects=objects, context=context, progress=self._progress,
                                      stages=_STAGES[self.mode])
        except LightmapExportError as exc:
            settings.is_running = False
            settings.status_text = "Fehler"
            _store_result(settings, None, str(exc))
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        finally:
            settings.is_running = False
        settings.status_text = "Fertig"
        _store_result(settings, result)
        _after_success(context, settings, result)
        self.report({"INFO"}, f"{len(result.lightmaps)} Lightmap(s), {len(result.exported_files)} Datei(en)")
        return {"FINISHED"}

    def invoke(self, context, event):
        if context.window is None or bpy.app.background:
            return self.execute(context)
        prepared = self._prepare(context)
        if prepared is None:
            return {"CANCELLED"}
        cfg, objects = prepared
        settings = _settings(context)
        self._collector = add_collector()
        self._ctx = PipelineContext(cfg, context=context, objects=objects, progress=self._progress)
        self._steps = build_steps(self._ctx, _STAGES[self.mode])
        self._ctx.snapshot = SceneStateSnapshot(context)
        self._index = 0
        self._done = 0.0
        self._total = sum(s.weight for s in self._steps) or 1.0
        self._waiting_bake = False
        self._failed = False
        settings.is_running = True
        settings.progress = 0.0
        settings.status_text = "Start"
        settings.last_error = ""
        context.window_manager.progress_begin(0, 100)
        self._timer = context.window_manager.event_timer_add(0.05, window=context.window)
        context.window_manager.modal_handler_add(self)
        self._add_bake_handlers()
        return {"RUNNING_MODAL"}

    # ..........................................................................
    def _progress(self, fraction, message):
        settings = _settings(bpy.context)
        settings.progress = fraction
        settings.status_text = message
        try:
            bpy.context.window_manager.progress_update(int(fraction * 100))
        except Exception:
            pass
        if not bpy.app.background:
            _redraw_all()

    def modal(self, context, event):
        settings = _settings(context)
        if event.type == "ESC":
            self._ctx.cancelled = True
            settings.status_text = "Abbruch angefordert ..."
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        if self._waiting_bake:
            if self._bake_state == "":
                return {"PASS_THROUGH"}
            self._waiting_bake = False
            if self._bake_state == "CANCELLED":
                return self._finish(context, error="Bake wurde abgebrochen", cancelled=True)
            self._bake_state = ""
            self._complete_step()
            return {"PASS_THROUGH"}
        if self._ctx.cancelled:
            return self._finish(context, error="Vorgang abgebrochen", cancelled=True)
        if self._index >= len(self._steps):
            return self._finish(context)
        step = self._steps[self._index]
        self._ctx.extra["current_step"] = step.name
        self._progress(self._done / self._total, step.label)
        self._step_start = time.perf_counter()
        try:
            if step.bake_image and self._use_background_bake():
                target = next(t for t in self._ctx.extra["bake_targets"] if t.image_name == step.bake_image)
                kwargs = baking.prepare_bake_call(self._ctx, target)
                self._bake_state = ""
                result = bpy.ops.object.bake("INVOKE_DEFAULT", **kwargs)
                if "RUNNING_MODAL" in result:
                    self._waiting_bake = True
                    settings.status_text = f"{step.label} (Esc bricht ab)"
                    return {"PASS_THROUGH"}
                # invoke not possible -> blocking fallback
                log.warning("Hintergrund-Bake nicht möglich (%s), verwende blockierenden Bake", result)
                baking.bake_target(self._ctx, target)
                self._complete_step()
            else:
                new_steps = step.func(self._ctx)
                if new_steps:
                    self._steps[self._index + 1:self._index + 1] = list(new_steps)
                    self._total += sum(s.weight for s in new_steps)
                self._complete_step()
        except PipelineCancelled as exc:
            return self._finish(context, error=str(exc), cancelled=True)
        except LightmapExportError as exc:
            return self._finish(context, error=str(exc))
        except Exception as exc:  # pragma: no cover
            log.error("Unerwarteter Fehler: %s\n%s", exc, traceback.format_exc())
            return self._finish(context, error=f"Unerwarteter Fehler in '{step.label}': {exc}")
        return {"PASS_THROUGH"}

    def _complete_step(self):
        step = self._steps[self._index]
        self._ctx.result.timings[step.name] = self._ctx.result.timings.get(step.name, 0.0) + time.perf_counter() - self._step_start
        self._done += step.weight
        self._index += 1

    def _use_background_bake(self) -> bool:
        prefs = get_prefs()
        return bool(prefs.use_background_bake) if prefs else True

    # bake job handlers ...........................................................
    def _add_bake_handlers(self):
        self._remove_bake_handlers()
        bpy.app.handlers.object_bake_complete.append(_on_bake_complete)
        bpy.app.handlers.object_bake_cancel.append(_on_bake_cancel)
        _ACTIVE["op"] = self

    def _remove_bake_handlers(self):
        for h, fn in ((bpy.app.handlers.object_bake_complete, _on_bake_complete),
                      (bpy.app.handlers.object_bake_cancel, _on_bake_cancel)):
            while fn in h:
                h.remove(fn)
        _ACTIVE.pop("op", None)

    # ..........................................................................
    def _finish(self, context, error: str = "", cancelled: bool = False):
        settings = _settings(context)
        ctx = self._ctx
        failed = bool(error)
        try:
            if error:
                ctx.result.errors.append(error)
            else:
                ctx.result.success = True
            finish_run(ctx, failed)
        except Exception as exc:  # pragma: no cover
            log.error("Aufräumen fehlgeschlagen: %s", exc)
        finally:
            self._remove_bake_handlers()
            if self._timer is not None:
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None
            try:
                context.window_manager.progress_end()
            except Exception:
                pass
            if self._collector is not None:
                for level, msg in self._collector.records:
                    if level == "ERROR" and msg not in ctx.result.errors:
                        ctx.result.errors.append(msg)
                remove_handler(self._collector)
            settings.is_running = False
            settings.progress = 1.0 if not failed else 0.0
            settings.status_text = "Fertig" if not failed else ("Abgebrochen" if cancelled else "Fehler")
            _store_result(settings, ctx.result, error)
            if not failed:
                _after_success(context, settings, ctx.result)
            _redraw_all()
        if failed:
            self.report({"WARNING" if cancelled else "ERROR"}, error)
            return {"CANCELLED"}
        n_warn = len(ctx.result.warnings)
        msg = f"{len(ctx.result.lightmaps)} Lightmap(s)"
        if ctx.result.exported_files:
            msg += f", {len(ctx.result.exported_files)} Datei(en) exportiert"
        if n_warn:
            msg += f", {n_warn} Warnung(en) – siehe Panel"
        self.report({"INFO"}, msg)
        return {"FINISHED"}


_ACTIVE = {}


def _on_bake_complete(*args):
    op = _ACTIVE.get("op")
    if op is not None:
        op._bake_state = "COMPLETE"


def _on_bake_cancel(*args):
    op = _ACTIVE.get("op")
    if op is not None:
        op._bake_state = "CANCELLED"


# --- simple operators ---------------------------------------------------------------------

class BLME_OT_apply_preview(bpy.types.Operator):
    """Show the baked lightmap in the materials of the selected objects"""
    bl_idname = "blme.apply_preview"
    bl_label = "Lightmap-Vorschau anzeigen"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(items=[("PREVIEW", "Lightmap × Farbe", "Basisfarbe multipliziert mit der Lightmap"),
                              ("LIGHTMAP_ONLY", "Nur Lightmap", "Lightmap ohne Materialfarbe"),
                              ("ORIGINAL", "Original", "Originalmaterial (Nodes bleiben erhalten)")],
                       default="PREVIEW")

    def execute(self, context):
        objs = [o for o in context.selected_objects if o.type == "MESH"] or [o for o in context.scene.objects if o.type == "MESH"]
        n = api.apply_lightmaps(objs, mode=self.mode)
        set_material_preview(context)
        if n == 0:
            self.report({"WARNING"}, "Keine Objekte mit Lightmap-Metadaten gefunden")
            return {"CANCELLED"}
        self.report({"INFO"}, f"{n} Material-Slot(s) aktualisiert")
        return {"FINISHED"}


class BLME_OT_restore_materials(bpy.types.Operator):
    """Remove the lightmap preview nodes and restore the original materials"""
    bl_idname = "blme.restore_materials"
    bl_label = "Originalmaterialien wiederherstellen"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = [o for o in context.selected_objects if o.type == "MESH"] or [o for o in context.scene.objects if o.type == "MESH"]
        n = api.restore_materials(objs)
        self.report({"INFO"}, f"{n} Material(ien) wiederhergestellt")
        return {"FINISHED"}


class BLME_OT_import_with_lightmaps(bpy.types.Operator, ImportHelper):
    """Import a model and attach its lightmaps (sidecar, metadata or file names)"""
    bl_idname = "blme.import_with_lightmaps"
    bl_label = "Mit Lightmaps importieren"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(default="*.glb;*.gltf;*.fbx;*.obj;*.usd;*.usda;*.usdc;*.usdz", options={"HIDDEN"})
    apply: BoolProperty(name="Vorschau zuweisen", default=True)

    def execute(self, context):
        try:
            report = api.import_with_lightmaps(self.filepath, context, apply=self.apply)
        except LightmapExportError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        matched, unmatched = len(report["matched"]), len(report["unmatched"])
        level = "INFO" if matched and not unmatched else "WARNING"
        self.report({level}, f"{len(report['objects'])} Objekte importiert, Lightmaps zugeordnet: {matched}, "
                             f"ohne Lightmap: {unmatched}")
        return {"FINISHED"}


class BLME_OT_save_config(bpy.types.Operator, ExportHelper):
    """Save the current settings as JSON (usable with start_export.bat)"""
    bl_idname = "blme.save_config"
    bl_label = "Konfiguration speichern"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        cfg = _settings(context).to_config()
        cfg.save(self.filepath)
        self.report({"INFO"}, f"Gespeichert: {self.filepath}")
        return {"FINISHED"}


class BLME_OT_load_config(bpy.types.Operator, ImportHelper):
    """Load settings from a JSON configuration"""
    bl_idname = "blme.load_config"
    bl_label = "Konfiguration laden"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            cfg = ExportConfig.load(self.filepath, strict=False)
        except ConfigError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _settings(context).from_config(cfg)
        self.report({"INFO"}, f"Geladen: {self.filepath}")
        return {"FINISHED"}


class BLME_OT_open_output(bpy.types.Operator):
    """Open the output directory in the file browser"""
    bl_idname = "blme.open_output"
    bl_label = "Ausgabeordner öffnen"

    def execute(self, context):
        path = bpy.path.abspath(_settings(context).output_dir)
        if not os.path.isdir(path):
            self.report({"WARNING"}, f"Ordner existiert nicht: {path}")
            return {"CANCELLED"}
        bpy.ops.wm.path_open(filepath=path)
        return {"FINISHED"}


class BLME_OT_material_preview(bpy.types.Operator):
    """Switch the 3D viewports to Material Preview so that the lightmap preview is visible"""
    bl_idname = "blme.material_preview"
    bl_label = "Viewport: Material Preview"

    def execute(self, context):
        n = set_material_preview(context, only_solid=False)
        self.report({"INFO"}, f"{n} Viewport(s) umgeschaltet" if n else "Viewports stehen bereits auf Material Preview/Rendered")
        return {"FINISHED"}


class BLME_OT_select_lightmapped(bpy.types.Operator):
    """Select all objects that carry lightmap metadata"""
    bl_idname = "blme.select_lightmapped"
    bl_label = "Objekte mit Lightmap auswählen"

    def execute(self, context):
        n = 0
        for o in context.scene.objects:
            has = o.type == "MESH" and metadata.read_object_metadata(o) is not None
            o.select_set(has)
            n += int(has)
        self.report({"INFO"}, f"{n} Objekt(e) ausgewählt")
        return {"FINISHED"}


CLASSES = (
    BLME_OT_run, BLME_OT_apply_preview, BLME_OT_restore_materials, BLME_OT_import_with_lightmaps,
    BLME_OT_save_config, BLME_OT_load_config, BLME_OT_open_output, BLME_OT_select_lightmapped,
    BLME_OT_material_preview,
)


def menu_import(self, context):
    self.layout.operator(BLME_OT_import_with_lightmaps.bl_idname, text="Modell mit Lightmaps (.glb/.fbx/.usd/.obj)")


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
