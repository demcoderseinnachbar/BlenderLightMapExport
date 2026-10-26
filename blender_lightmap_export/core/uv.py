# SPDX-License-Identifier: GPL-3.0-or-later
"""Lightmap UV channel creation, unwrapping and atlas packing.

Margin semantics (documented and tested):

* ``island_margin_px`` is converted to UV units as ``px / resolution``.
* Smart UV Project and ``pack_islands`` use ``margin_method='ADD'`` – the
  margin is an absolute distance in UV space, independent of island size.
* Lightmap Pack expresses the margin as a *percentage of the UV square*
  (``PREF_MARGIN_DIV``, 0.001..1.0 %). ``px / resolution * 100`` is clamped to
  that range, so with Lightmap Pack the maximum margin is 1 % of the texture.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import bpy
import numpy as np

from .log import get_logger
from .pipeline import LightmapExportError, PipelineContext
from .state import ensure_object_mode, select_only

log = get_logger("uv")


# --- channel handling ------------------------------------------------------------

def uv_index(mesh: bpy.types.Mesh, name: str) -> int:
    for i, layer in enumerate(mesh.uv_layers):
        if layer.name == name:
            return i
    return -1


def ensure_lightmap_uv(obj: bpy.types.Object, uv_name: str, product_tracker=None,
                       reuse_existing: bool = False) -> Tuple[bpy.types.MeshUVLoopLayer, bool]:
    """Return (layer, created). Existing layers are never modified unless
    ``reuse_existing`` is False (then an existing layer with that name is re-unwrapped)."""
    mesh = obj.data
    layer = mesh.uv_layers.get(uv_name)
    if layer is not None:
        return layer, False
    if len(mesh.uv_layers) >= 8:
        raise LightmapExportError(f"Objekt '{obj.name}' hat bereits 8 UV-Layer, Blender erlaubt nicht mehr")
    layer = mesh.uv_layers.new(name=uv_name, do_init=False)
    if layer is None:
        raise LightmapExportError(f"UV-Layer '{uv_name}' konnte für '{obj.name}' nicht angelegt werden")
    if product_tracker is not None:
        product_tracker.add_uv_layer(mesh, uv_name)
    return layer, True


def margin_uv_units(px: float, resolution: int) -> float:
    return max(0.0, float(px)) / float(max(1, resolution))


def lightmap_pack_margin(px: float, resolution: int) -> float:
    """Value for ``PREF_MARGIN_DIV`` (percent of UV square, 0.001..1.0)."""
    return min(1.0, max(0.001, margin_uv_units(px, resolution) * 100.0))


# --- unwrapping ----------------------------------------------------------------------

def _edit_mode(objects: List[bpy.types.Object]):
    """Enter multi-object edit mode for ``objects`` with all faces selected."""
    ensure_object_mode()
    select_only(objects, objects[0])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")


def smart_project(obj: bpy.types.Object, uv_name: str, resolution: int, cfg_uv) -> None:
    obj.data.uv_layers.active = obj.data.uv_layers[uv_name]
    _edit_mode([obj])
    try:
        bpy.ops.uv.smart_project(
            angle_limit=math.radians(cfg_uv.angle_limit_deg),
            margin_method="ADD",
            island_margin=margin_uv_units(cfg_uv.island_margin_px, resolution),
            rotate_method=cfg_uv.rotate_method,
            area_weight=cfg_uv.area_weight,
            correct_aspect=cfg_uv.correct_aspect,
            scale_to_bounds=False,
        )
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")


def lightmap_pack(obj: bpy.types.Object, uv_name: str, resolution: int, cfg_uv) -> None:
    obj.data.uv_layers.active = obj.data.uv_layers[uv_name]
    ensure_object_mode()
    select_only([obj], obj)
    # object mode: packs all faces of the active UV map
    bpy.ops.uv.lightmap_pack(
        PREF_CONTEXT="ALL_FACES",
        PREF_PACK_IN_ONE=True,
        PREF_NEW_UVLAYER=False,
        PREF_BOX_DIV=cfg_uv.lightmap_pack_box_div,
        PREF_MARGIN_DIV=lightmap_pack_margin(cfg_uv.island_margin_px, resolution),
    )


def unwrap_object(obj: bpy.types.Object, cfg, resolution: int, product_tracker=None) -> bool:
    """Create/choose the lightmap UV layer for ``obj``. Returns True if unwrapped."""
    uv_cfg = cfg.uv
    name = uv_cfg.uv_name
    if uv_cfg.method == "EXISTING":
        if name not in obj.data.uv_layers:
            raise LightmapExportError(
                f"Objekt '{obj.name}' hat keinen UV-Layer '{name}' (Methode EXISTING)")
        return False
    layer, created = ensure_lightmap_uv(obj, name, product_tracker)
    if not created:
        log.info("UV-Layer '%s' von '%s' wird neu entfaltet", name, obj.name)
    if uv_cfg.method == "SMART_PROJECT":
        smart_project(obj, name, resolution, uv_cfg)
    elif uv_cfg.method == "LIGHTMAP_PACK":
        lightmap_pack(obj, name, resolution, uv_cfg)
    else:
        raise LightmapExportError(f"Unbekannte UV-Methode {uv_cfg.method}")
    return True


# --- atlas packing ---------------------------------------------------------------------

def uv_array(mesh: bpy.types.Mesh, uv_name: str) -> np.ndarray:
    layer = mesh.uv_layers[uv_name]
    n = len(mesh.loops)
    arr = np.empty(n * 2, dtype=np.float32)
    layer.uv.foreach_get("vector", arr)
    return arr.reshape(n, 2)


def set_uv_array(mesh: bpy.types.Mesh, uv_name: str, arr: np.ndarray) -> None:
    mesh.uv_layers[uv_name].uv.foreach_set("vector", np.ascontiguousarray(arr, dtype=np.float32).ravel())
    mesh.update()


def _triangle_areas(mesh: bpy.types.Mesh, uv_name: str, obj: Optional[bpy.types.Object] = None) -> Tuple[float, float]:
    """Return (world surface area, uv area) of the mesh."""
    mesh.calc_loop_triangles()
    tris = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("loops", tris)
    tris = tris.reshape(-1, 3)
    verts = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", verts)
    verts = verts.reshape(-1, 3)
    if obj is not None:
        m = np.array(obj.matrix_world, dtype=np.float32)
        verts = verts @ m[:3, :3].T + m[:3, 3]
    loop_verts = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", loop_verts)
    p = verts[loop_verts[tris]]
    world_area = float(np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1).sum() * 0.5)
    uv = uv_array(mesh, uv_name)[tris]
    d1 = uv[:, 1] - uv[:, 0]
    d2 = uv[:, 2] - uv[:, 0]
    uv_area = float(np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() * 0.5)
    return world_area, uv_area


def prescale_for_texel_density(objects: List[bpy.types.Object], uv_name: str) -> Dict[str, float]:
    """Scale each object's UVs so that UV area is proportional to world area."""
    factors: Dict[str, float] = {}
    densities = []
    for o in objects:
        wa, ua = _triangle_areas(o.data, uv_name, o)
        if wa <= 1e-12 or ua <= 1e-12:
            factors[o.name] = 1.0
            continue
        densities.append((o, wa, ua))
    if not densities:
        return factors
    ref = max(wa / ua for _, wa, ua in densities)  # object with the least UV area per world area
    for o, wa, ua in densities:
        s = math.sqrt((wa / ua) / ref)   # scale UV side length
        factors[o.name] = s
        if abs(s - 1.0) > 1e-4:
            arr = uv_array(o.data, uv_name) * s
            set_uv_array(o.data, uv_name, arr)
    return factors


def pack_atlas(objects: List[bpy.types.Object], uv_name: str, resolution: int, margin_px: float,
               rotate: bool = True) -> None:
    for o in objects:
        o.data.uv_layers.active = o.data.uv_layers[uv_name]
    _edit_mode(objects)
    try:
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.pack_islands(
            udim_source="CLOSEST_UDIM",
            rotate=rotate,
            rotate_method="CARDINAL",
            scale=True,
            merge_overlap=False,
            margin_method="ADD",
            margin=margin_uv_units(margin_px, resolution),
            pin=False,
            shape_method="CONCAVE",
        )
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")


# --- pipeline steps ----------------------------------------------------------------------

def step_create_lightmap_uvs(ctx: PipelineContext) -> None:
    cfg = ctx.cfg
    res = cfg.bake.resolution
    name = cfg.uv.uv_name
    done_meshes = set()
    for o in ctx.objects:
        before = [u.name for u in o.data.uv_layers]
        if o.data.name in done_meshes:
            continue  # shared mesh data: unwrap once
        unwrap_object(o, cfg, res, ctx.product)
        done_meshes.add(o.data.name)
        after = [u.name for u in o.data.uv_layers]
        for b in before:
            if b not in after:
                raise LightmapExportError(f"UV-Layer '{b}' von '{o.name}' ist verloren gegangen")
        # never change which UV layer is used for rendering/original textures
        if before:
            render_layer = next((u for u in o.data.uv_layers if u.name != name and u.name in before), None)
            if render_layer is not None and not any(u.active_render for u in o.data.uv_layers if u.name != name):
                render_layer.active_render = True
    if cfg.atlas.mode == "SHARED_ATLAS" and cfg.uv.method != "EXISTING":
        groups = ctx.extra.get("atlas_groups") or [list(ctx.objects)]
        for group in groups:
            unique = []
            seen = set()
            for o in group:
                if o.data.name not in seen:
                    seen.add(o.data.name)
                    unique.append(o)
            if cfg.atlas.texel_density_weighting:
                factors = prescale_for_texel_density(unique, name)
                log.info("Texeldichte-Vorskalierung: %s", {k: round(v, 3) for k, v in factors.items()})
            pack_atlas(unique, name, res, cfg.uv.island_margin_px)
    ctx.extra["uv_name"] = name
    log.info("Lightmap-UV '%s' für %d Objekte bereit (Methode %s)", name, len(ctx.objects), cfg.uv.method)


def step_validate_uvs(ctx: PipelineContext) -> None:
    from . import uv_validate
    cfg = ctx.cfg
    name = cfg.uv.uv_name
    res = min(cfg.bake.resolution, 2048)
    results: Dict[str, Dict] = {}
    if cfg.atlas.mode == "SHARED_ATLAS":
        groups = [[o for o in ctx.objects]]
        labels = ["atlas"]
    else:
        groups = [[o] for o in ctx.objects]
        labels = [o.name for o in ctx.objects]
    for label, group in zip(labels, groups):
        report = uv_validate.validate_layout([(o.data, name) for o in group], res, cfg.uv.min_spacing_px)
        results[label] = report
        for w in uv_validate.report_warnings(label, report):
            ctx.warn(w)
        if report["invalid"] > 0:
            raise LightmapExportError(f"UV-Layer '{name}' von '{label}' enthält ungültige Koordinaten (NaN/Inf)")
    ctx.result.uv_validation = results
