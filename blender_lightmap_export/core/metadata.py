# SPDX-License-Identifier: GPL-3.0-or-later
"""Lightmap metadata: custom properties on objects and the sidecar JSON file.

The same information is stored twice so that it survives every export format
that carries custom properties (glTF extras, FBX custom properties, USD user
properties) *and* formats that do not (OBJ):

* ``obj["BLME_lightmap"]`` – dict with file, uv name/index, bake type ...
* ``<Model>.lightmaps.json`` next to the exported model.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

import bpy

from .log import get_logger
from .pipeline import LightmapExportError, PipelineContext
from . import naming

log = get_logger("metadata")

PROP_NAME = "BLME_lightmap"
SIDECAR_VERSION = 1


# --- object custom properties -------------------------------------------------------

def object_metadata(info, obj_name: str) -> Dict[str, Any]:
    return {
        "version": SIDECAR_VERSION,
        "image": info.image_name,
        "file": info.relative_path or os.path.basename(info.file_path),
        "uv_name": info.uv_name,
        "uv_index": int(info.uv_index_by_object.get(obj_name, -1)),
        "bake_type": info.bake_type,
        "resolution": int(info.resolution),
        "colorspace": info.colorspace,
        "image_format": info.image_format,
        "is_atlas": bool(info.is_atlas),
    }


def write_object_metadata(obj: bpy.types.Object, meta: Dict[str, Any]) -> None:
    obj[PROP_NAME] = meta


def read_object_metadata(obj: bpy.types.Object) -> Optional[Dict[str, Any]]:
    raw = obj.get(PROP_NAME)
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    try:
        return {k: (v.to_dict() if hasattr(v, "to_dict") else (list(v) if hasattr(v, "to_list") else v))
                for k, v in raw.items()}
    except AttributeError:
        return None


def step_write_object_metadata(ctx: PipelineContext) -> None:
    for info in ctx.result.lightmaps:
        for obj_name in info.objects:
            obj = bpy.data.objects.get(obj_name)
            if obj is not None:
                write_object_metadata(obj, object_metadata(info, obj_name))


# --- sidecar ---------------------------------------------------------------------------

def sidecar_path_for(model_path: str) -> str:
    stem = os.path.splitext(os.path.basename(model_path))[0]
    return os.path.join(os.path.dirname(model_path), naming.sidecar_file_name(stem))


def build_sidecar(ctx: PipelineContext, model_path: str) -> Dict[str, Any]:
    model_dir = os.path.dirname(model_path)
    objects: Dict[str, Any] = {}
    for info in ctx.result.lightmaps:
        for obj_name in info.objects:
            obj = bpy.data.objects.get(obj_name)
            objects[obj_name] = {
                "mesh": obj.data.name if obj else "",
                "lightmap": naming.relpath(info.file_path, model_dir),
                "uv_name": info.uv_name,
                "uv_index": int(info.uv_index_by_object.get(obj_name, -1)),
                "materials": [s.material.name if s.material else None for s in obj.material_slots] if obj else [],
                "original_uv_names": [u.name for u in obj.data.uv_layers if u.name != info.uv_name] if obj else [],
            }
    caps = ctx.extra.get("format_capabilities", {})
    return {
        "format": "BlenderLightMapExport",
        "version": SIDECAR_VERSION,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "blender": bpy.app.version_string,
        "model": os.path.basename(model_path),
        "export_format": ctx.cfg.export.format,
        "format_capabilities": caps,
        "bake": {
            "type": ctx.cfg.bake.type, "resolution": ctx.cfg.bake.resolution, "samples": ctx.cfg.bake.samples,
            "margin_px": ctx.cfg.bake.margin_px, "denoise": ctx.cfg.bake.denoise, "device": ctx.result.device_used,
        },
        "uv": {"name": ctx.cfg.uv.uv_name, "method": ctx.cfg.uv.method, "island_margin_px": ctx.cfg.uv.island_margin_px},
        "image": {"format": ctx.cfg.image.format, "colorspace": "linear"},
        "atlas": ctx.cfg.atlas.mode,
        "lightmaps": [dict(lm.to_dict(), file=naming.relpath(lm.file_path, model_dir)) for lm in ctx.result.lightmaps],
        "objects": objects,
        "warnings": list(ctx.result.warnings),
    }


def step_write_sidecar(ctx: PipelineContext) -> None:
    if not ctx.cfg.export.write_sidecar or not ctx.export_path:
        return
    path = sidecar_path_for(ctx.export_path)
    data = build_sidecar(ctx, ctx.export_path)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    ctx.result.sidecar_path = path
    if path not in ctx.result.exported_files:
        ctx.result.exported_files.append(path)
    log.info("Sidecar geschrieben: %s", path)


def load_sidecar(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or data.get("format") != "BlenderLightMapExport":
        raise LightmapExportError(f"Keine gültige Lightmap-Sidecar-Datei: {path}")
    return data


def load_sidecar_for(model_path: str) -> Optional[Dict[str, Any]]:
    path = sidecar_path_for(model_path)
    if os.path.isfile(path):
        data = load_sidecar(path)
        data["_path"] = path
        return data
    return None


# --- resolving lightmap images --------------------------------------------------------

def _candidate_paths(meta: Dict[str, Any], obj: bpy.types.Object, model_dir: str = "") -> List[str]:
    paths: List[str] = []
    file = meta.get("file") or meta.get("lightmap") or ""
    bases = [b for b in (model_dir, meta.get("_model_dir", ""), os.path.dirname(bpy.data.filepath)) if b]
    for base in bases:
        if file:
            paths.append(os.path.normpath(os.path.join(base, file)))
    if os.path.isabs(file):
        paths.append(file)
    # file name convention fallback
    for base in bases:
        for ext in (".png", ".exr"):
            paths.append(os.path.join(base, naming.lightmap_file_name(obj.name, ext)))
            paths.append(os.path.join(base, "Lightmaps", naming.lightmap_file_name(obj.name, ext)))
    return paths


def resolve_lightmap_image(meta: Dict[str, Any], obj: bpy.types.Object, model_dir: str = "") -> Optional[bpy.types.Image]:
    """Find/load the lightmap image described by ``meta`` (object custom property)."""
    name = meta.get("image")
    if name and name in bpy.data.images:
        img = bpy.data.images[name]
        if img.size[0] > 0:
            return img
    for path in _candidate_paths(meta, obj, model_dir):
        if os.path.isfile(path):
            abspath = os.path.abspath(path)
            for img in bpy.data.images:
                if img.filepath and os.path.abspath(bpy.path.abspath(img.filepath)) == abspath:
                    return img
            img = bpy.data.images.load(abspath, check_existing=True)
            img.colorspace_settings.name = "Non-Color"
            if name:
                img.name = name
            return img
    return None


# --- import with lightmaps ---------------------------------------------------------------

def attach_lightmaps(objects: List[bpy.types.Object], model_path: str, sidecar: Optional[Dict[str, Any]] = None,
                     apply: bool = True, mode: str = "PREVIEW") -> Dict[str, Any]:
    """Attach lightmaps to ``objects`` using sidecar → custom props → file names."""
    from . import materials
    model_dir = os.path.dirname(os.path.abspath(model_path))
    if sidecar is None:
        sidecar = load_sidecar_for(model_path)
    report: Dict[str, Any] = {"model": model_path, "sidecar": bool(sidecar), "matched": [], "unmatched": [],
                              "source": {}, "applied": 0}
    by_image: Dict[str, List[bpy.types.Object]] = {}
    images: Dict[str, bpy.types.Image] = {}
    uv_name = (sidecar or {}).get("uv", {}).get("name", "LightmapUV")
    bake_type = (sidecar or {}).get("bake", {}).get("type", "DIFFUSE_LIGHTING")
    sidecar_objects = (sidecar or {}).get("objects", {})

    for obj in objects:
        if obj.type != "MESH":
            continue
        meta = None
        source = ""
        entry = _match_sidecar_entry(sidecar_objects, obj)
        if entry is not None:
            meta = {"file": entry["lightmap"], "uv_name": entry.get("uv_name", uv_name),
                    "uv_index": entry.get("uv_index", -1), "bake_type": bake_type, "image": ""}
            source = "sidecar"
        if meta is None:
            meta = read_object_metadata(obj)
            if meta:
                source = "custom_property"
        if meta is None:
            # file name convention
            for ext in (".png", ".exr"):
                for sub in ("", "Lightmaps"):
                    p = os.path.join(model_dir, sub, naming.lightmap_file_name(obj.name, ext))
                    if os.path.isfile(p):
                        meta = {"file": naming.relpath(p, model_dir), "uv_name": uv_name, "uv_index": -1,
                                "bake_type": bake_type, "image": ""}
                        source = "file_name"
                        break
                if meta:
                    break
        if meta is None:
            report["unmatched"].append(obj.name)
            continue
        img = resolve_lightmap_image(meta, obj, model_dir)
        if img is None:
            report["unmatched"].append(obj.name)
            log.warning("Lightmap-Datei für '%s' nicht gefunden: %s", obj.name, meta.get("file"))
            continue
        name = meta.get("uv_name") or uv_name
        idx = int(meta.get("uv_index", -1))
        if name not in obj.data.uv_layers:
            if 0 <= idx < len(obj.data.uv_layers):
                obj.data.uv_layers[idx].name = name          # restore the lost name (glTF)
            elif len(obj.data.uv_layers) >= 2:
                obj.data.uv_layers[-1].name = name
                log.warning("UV-Index für '%s' unbekannt, letzter UV-Layer wird als '%s' verwendet", obj.name, name)
            else:
                report["unmatched"].append(obj.name)
                log.warning("'%s' hat keinen zweiten UV-Layer, Lightmap kann nicht zugeordnet werden", obj.name)
                continue
        write_object_metadata(obj, {**meta, "image": img.name, "uv_name": name,
                                    "uv_index": list(obj.data.uv_layers).index(obj.data.uv_layers[name]),
                                    "version": SIDECAR_VERSION})
        images[img.name] = img
        by_image.setdefault(img.name, []).append(obj)
        report["matched"].append(obj.name)
        report["source"][obj.name] = source
        uv_name = name
    if apply and by_image:
        report["applied"] = materials.bind_objects(by_image, images, uv_name, bake_type, mode)
    return report


def _match_sidecar_entry(entries: Dict[str, Any], obj: bpy.types.Object) -> Optional[Dict[str, Any]]:
    if not entries:
        return None
    if obj.name in entries:
        return entries[obj.name]
    # importers may rename objects ("Cube.001") or use the mesh name
    base = obj.name.rsplit(".", 1)[0] if "." in obj.name and obj.name.rsplit(".", 1)[1].isdigit() else obj.name
    if base in entries:
        return entries[base]
    for name, entry in entries.items():
        if entry.get("mesh") and entry["mesh"] == obj.data.name:
            return entry
    return None


def import_with_lightmaps(path: str, context: bpy.types.Context, apply: bool = True, mode: str = "PREVIEW") -> Dict[str, Any]:
    from . import io_import
    objects = io_import.import_file(path, context)
    report = attach_lightmaps(objects, path, apply=apply, mode=mode)
    report["objects"] = [o.name for o in objects]
    return report


# --- reimport verification ------------------------------------------------------------------

def verify_reimport(ctx: PipelineContext, exporter) -> Dict[str, Any]:
    """Import the exported file into a temporary scene and check geometry, UVs and lightmaps."""
    from . import materials
    path = ctx.export_path
    expected = {}
    for o in ctx.objects:
        expected[o.name] = {
            "polys": len(o.data.polygons),
            "uvs": [u.name for u in o.data.uv_layers],
            "materials": [s.material.name for s in o.material_slots if s.material],
        }
    temp_scene = bpy.data.scenes.new("BLME_ReimportCheck")
    original_scene = ctx.context.window.scene if ctx.context.window else None
    report: Dict[str, Any] = {"file": path, "ok": True, "objects": {}, "problems": []}
    try:
        if ctx.context.window:
            ctx.context.window.scene = temp_scene
        imported = exporter.import_file(path, bpy.context)
        attach = attach_lightmaps(imported, path, apply=True)
        for o in imported:
            if o.type != "MESH":
                continue
            exp = expected.get(o.name) or expected.get(o.name.rsplit(".", 1)[0]) or {}
            entry = {
                "polys": len(o.data.polygons),
                "polys_expected": exp.get("polys"),
                "uvs": [u.name for u in o.data.uv_layers],
                "lightmap_attached": o.name in attach["matched"],
                "lightmap_source": attach["source"].get(o.name),
                "preview_bound": any(materials.is_bound(s.material) for s in o.material_slots if s.material),
            }
            if exp and exp.get("polys") != entry["polys"] and not (exporter.capabilities.name == "OBJ" or
                                                                   exporter.capabilities.name.startswith("GL")):
                report["problems"].append(f"{o.name}: Polygonanzahl {entry['polys']} statt {exp['polys']}")
            if exporter.capabilities.multiple_uv_sets and len(entry["uvs"]) < len(exp.get("uvs", [])):
                report["problems"].append(f"{o.name}: nur {len(entry['uvs'])} UV-Layer nach Reimport "
                                          f"(erwartet {len(exp.get('uvs', []))})")
            if not entry["lightmap_attached"]:
                report["problems"].append(f"{o.name}: Lightmap konnte nach Reimport nicht zugeordnet werden")
            report["objects"][o.name] = entry
        report["ok"] = not report["problems"]
        for p in report["problems"]:
            ctx.warn("Reimport-Prüfung: " + p)
        log.info("Reimport-Prüfung: %s", "OK" if report["ok"] else "Probleme gefunden")
    finally:
        if ctx.context.window and original_scene is not None:
            ctx.context.window.scene = original_scene
        for o in list(temp_scene.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.scenes.remove(temp_scene)
    return report
