# SPDX-License-Identifier: MIT
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
from .pipeline import LightmapExportError, LightmapInfo, PipelineContext
from . import naming

log = get_logger("metadata")

PROP_NAME = "BLME_lightmap"
PROP_NAME_JSON = "BLME_lightmap_json"   # string copy: survives exporters without dict properties (FBX)
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
    obj[PROP_NAME_JSON] = json.dumps(meta)


def clear_object_metadata(obj: bpy.types.Object) -> None:
    for key in (PROP_NAME, PROP_NAME_JSON):
        if key in obj:
            del obj[key]


def read_object_metadata(obj: bpy.types.Object) -> Optional[Dict[str, Any]]:
    raw = obj.get(PROP_NAME)
    if raw is not None and not isinstance(raw, str):
        try:
            return {k: (v.to_dict() if hasattr(v, "to_dict") else (list(v) if hasattr(v, "to_list") else v))
                    for k, v in raw.items()}
        except AttributeError:
            pass
    # string candidates: the dict property may come back as a (useless) string from FBX,
    # the JSON copy is the reliable carrier
    for candidate in (raw if isinstance(raw, str) else None, obj.get(PROP_NAME_JSON)):
        if not isinstance(candidate, str):
            continue
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def collect_existing_lightmaps(ctx: PipelineContext) -> List[LightmapInfo]:
    """Rebuild LightmapInfo entries from object metadata (export-only runs)."""
    by_image: Dict[str, LightmapInfo] = {}
    for o in ctx.objects:
        meta = read_object_metadata(o)
        if not meta:
            ctx.warn(f"Objekt '{o.name}' hat keine Lightmap-Metadaten und wird ohne Lightmap exportiert")
            continue
        img = resolve_lightmap_image(meta, o, ctx.output_dir)
        key = meta.get("image") or (img.name if img else meta.get("file", o.name))
        info = by_image.get(key)
        if info is None:
            file_path = ""
            if img is not None and img.filepath:
                file_path = os.path.abspath(bpy.path.abspath(img.filepath))
            elif meta.get("file"):
                file_path = os.path.abspath(os.path.join(ctx.output_dir, meta["file"]))
            info = LightmapInfo(
                image_name=key, file_path=file_path,
                relative_path=naming.relpath(file_path, ctx.output_dir) if file_path else meta.get("file", ""),
                resolution=int(meta.get("resolution", 0)), uv_name=meta.get("uv_name", ctx.cfg.uv.uv_name),
                bake_type=meta.get("bake_type", ctx.cfg.bake.type), image_format=meta.get("image_format", ""),
                colorspace=meta.get("colorspace", "linear"), is_atlas=bool(meta.get("is_atlas", False)),
            )
            by_image[key] = info
            if img is not None:
                ctx.images[key] = img
        info.objects.append(o.name)
        info.uv_index_by_object[o.name] = int(meta.get("uv_index", -1))
        ctx.image_objects.setdefault(key, []).append(o.name)
    return list(by_image.values())


def step_collect_existing_lightmaps(ctx: PipelineContext) -> None:
    infos = collect_existing_lightmaps(ctx)
    ctx.result.lightmaps.extend(infos)
    missing = [i.image_name for i in infos if i.file_path and not os.path.isfile(i.file_path)]
    for name in missing:
        ctx.warn(f"Lightmap-Datei für '{name}' nicht gefunden, Sidecar verweist auf eine fehlende Datei")
    log.info("%d vorhandene Lightmap(s) aus Metadaten übernommen", len(infos))


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
    uv_override = ctx.extra.get("sidecar_uv_index_override")
    for info in ctx.result.lightmaps:
        for obj_name in info.objects:
            obj = bpy.data.objects.get(obj_name)
            objects[obj_name] = {
                "mesh": obj.data.name if obj else "",
                "lightmap": naming.relpath(info.file_path, model_dir),
                "uv_name": info.uv_name,
                "uv_index": int(uv_override if uv_override is not None else info.uv_index_by_object.get(obj_name, -1)),
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
        "note": ctx.extra.get("sidecar_note", ""),
        "secondary_model": ctx.extra.get("sidecar_secondary_model", ""),
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
    if not os.path.isfile(path):
        # secondary OBJ file (<name>_lightmapuv.obj) shares the sidecar of the main file
        stem = os.path.splitext(os.path.basename(model_path))[0]
        if stem.endswith("_lightmapuv"):
            path = os.path.join(os.path.dirname(model_path), naming.sidecar_file_name(stem[: -len("_lightmapuv")]))
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
                     apply: bool = True, mode: Optional[str] = None) -> Dict[str, Any]:
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
                obj.data.uv_layers[idx].name = name          # restore the lost name (glTF / OBJ index 0)
            elif len(obj.data.uv_layers) >= 2:
                obj.data.uv_layers[-1].name = name
                log.warning("UV-Index für '%s' unbekannt, letzter UV-Layer wird als '%s' verwendet", obj.name, name)
            else:
                report["unmatched"].append(obj.name)
                log.warning("'%s' hat keinen Lightmap-UV-Layer (Index %d), Lightmap kann nicht zugeordnet werden",
                            obj.name, idx)
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


def import_with_lightmaps(path: str, context: bpy.types.Context, apply: bool = True,
                          mode: Optional[str] = None) -> Dict[str, Any]:
    from . import io_import
    objects = io_import.import_file(path, context)
    report = attach_lightmaps(objects, path, apply=apply, mode=mode)
    report["objects"] = [o.name for o in objects]
    return report


# --- reimport verification ------------------------------------------------------------------

def verify_reimport(ctx: PipelineContext, exporter) -> Dict[str, Any]:
    """Import the exported file, check geometry, UVs and lightmap binding, then remove it again.

    The check imports into the current scene (works headless) and removes every
    datablock it created afterwards, so the user's scene is unchanged.
    """
    from . import materials
    from .state import ensure_object_mode, select_only
    path = ctx.export_path
    expected = {}
    for o in ctx.objects:
        expected[o.name] = {
            "polys": len(o.data.polygons),
            "verts": len(o.data.vertices),
            "uvs": [u.name for u in o.data.uv_layers],
            "materials": [s.material.name for s in o.material_slots if s.material],
        }
    snapshot = {coll: {d.name for d in getattr(bpy.data, coll)}
                for coll in ("objects", "meshes", "materials", "images", "node_groups", "collections")}
    report: Dict[str, Any] = {"file": path, "ok": True, "objects": {}, "problems": []}
    ensure_object_mode()
    try:
        imported = exporter.import_file(path, bpy.context)
        attach = attach_lightmaps(imported, path, apply=True)
        multi_uv = exporter.capabilities.multiple_uv_sets
        for o in imported:
            if o.type != "MESH":
                continue
            base = o.name.rsplit(".", 1)[0] if "." in o.name and o.name.rsplit(".", 1)[1].isdigit() else o.name
            exp = expected.get(o.name) or expected.get(base) or {}
            bound = any(materials.is_bound(s.material) for s in o.material_slots if s.material)
            entry = {
                "polys": len(o.data.polygons), "polys_expected": exp.get("polys"),
                "verts": len(o.data.vertices), "verts_expected": exp.get("verts"),
                "uvs": [u.name for u in o.data.uv_layers],
                "lightmap_attached": o.name in attach["matched"],
                "lightmap_source": attach["source"].get(o.name),
                "preview_bound": bound,
            }
            name = exporter.capabilities.name
            if exp and name in ("FBX", "USD") and exp.get("polys") != entry["polys"]:
                report["problems"].append(f"{o.name}: Polygonanzahl {entry['polys']} statt {exp['polys']}")
            if exp and name.startswith("GL") and entry["polys"] < exp.get("polys", 0):
                report["problems"].append(f"{o.name}: weniger Polygone nach Reimport ({entry['polys']} < {exp['polys']})")
            if multi_uv and len(entry["uvs"]) < len(exp.get("uvs", [])):
                report["problems"].append(f"{o.name}: nur {len(entry['uvs'])} UV-Layer nach Reimport "
                                          f"(erwartet {len(exp.get('uvs', []))})")
            if multi_uv and not entry["lightmap_attached"]:
                report["problems"].append(f"{o.name}: Lightmap konnte nach Reimport nicht zugeordnet werden")
            if multi_uv and entry["lightmap_attached"] and not bound:
                report["problems"].append(f"{o.name}: Lightmap zugeordnet, aber Material nicht verbunden")
            report["objects"][o.name] = entry
        report["ok"] = not report["problems"]
        for p in report["problems"]:
            ctx.warn("Reimport-Prüfung: " + p)
        log.info("Reimport-Prüfung: %s", "OK" if report["ok"] else "Probleme gefunden")
    finally:
        _remove_new_datablocks(snapshot)
        select_only(ctx.objects, ctx.objects[0], ctx.view_layer)
    return report


def _remove_new_datablocks(snapshot: Dict[str, set]) -> None:
    for o in [o for o in bpy.data.objects if o.name not in snapshot["objects"]]:
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in ("collections", "meshes", "materials", "node_groups", "images"):
        data = getattr(bpy.data, coll)
        for d in [d for d in data if d.name not in snapshot[coll]]:
            if coll == "node_groups" and d.name in ("BLME_LightmapShader", "glTF Material Output"):
                continue
            if coll == "images" and d.users > 0:
                continue
            try:
                data.remove(d)
            except Exception:
                pass
