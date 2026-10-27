# SPDX-License-Identifier: MIT
"""Cycles baking: device selection, bake targets per material slot, bake calls."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import bpy
import numpy as np

from .log import get_logger
from .pipeline import LightmapExportError, PipelineContext
from .state import ensure_object_mode, select_only
from . import naming

log = get_logger("bake")

BAKE_NODE = "BLME_BakeTarget"
BAKE_UV_NODE = "BLME_BakeUV"
TEMP_MATERIAL = "BLME_TempBakeMaterial"
DEFAULT_MATERIAL_PREFIX = "BLME_Material_"
GPU_BACKENDS = ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL")


# --- devices ---------------------------------------------------------------------

def _cycles_prefs():
    addon = bpy.context.preferences.addons.get("cycles")
    return addon.preferences if addon else None


def available_gpu_backends() -> Dict[str, List[str]]:
    prefs = _cycles_prefs()
    if prefs is None:
        return {}
    original = prefs.compute_device_type
    found: Dict[str, List[str]] = {}
    for backend in GPU_BACKENDS:
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        try:
            prefs.get_devices()
        except Exception:
            continue
        names = [d.name for d in prefs.devices if d.type == backend]
        if names:
            found[backend] = names
    try:
        prefs.compute_device_type = original
        prefs.get_devices()
    except Exception:
        pass
    return found


def gpu_available() -> bool:
    return bool(available_gpu_backends())


def describe_devices() -> str:
    backends = available_gpu_backends()
    if not backends:
        return "CPU"
    return "; ".join(f"{b}: {', '.join(n)}" for b, n in backends.items())


def select_device(mode: str, tracker=None) -> Tuple[str, str]:
    """Configure Cycles for ``mode`` (AUTO/CPU/GPU). Returns (cycles_device, backend)."""
    prefs = _cycles_prefs()
    if mode == "CPU" or prefs is None:
        return "CPU", "CPU"
    backends = available_gpu_backends()
    if not backends:
        if mode == "GPU":
            raise LightmapExportError("GPU-Baking angefordert, aber Cycles findet kein GPU-Gerät")
        return "CPU", "CPU"
    backend = next(b for b in GPU_BACKENDS if b in backends)
    original_type = prefs.compute_device_type
    prefs.compute_device_type = backend
    prefs.get_devices()
    original_use = [(d.id, d.use) for d in prefs.devices]
    for d in prefs.devices:
        d.use = d.type == backend
    if tracker is not None:
        def _restore():
            try:
                prefs.compute_device_type = original_type
                prefs.get_devices()
                use_map = dict(original_use)
                for d in prefs.devices:
                    if d.id in use_map:
                        d.use = use_map[d.id]
            except Exception:
                pass
        tracker.add_callback(_restore)
    return "GPU", backend


def step_select_device(ctx: PipelineContext) -> None:
    device, backend = select_device(ctx.cfg.bake.device, ctx.temp)
    ctx.device_info = {"device": device, "backend": backend}
    ctx.result.device_used = backend
    log.info("Render-Gerät: %s (%s)", device, backend)


# --- bake targets ----------------------------------------------------------------

class BakeTarget:
    def __init__(self, image_name: str, objects: List[bpy.types.Object], is_atlas: bool) -> None:
        self.image_name = image_name
        self.objects = objects
        self.is_atlas = is_atlas
        self.image: Optional[bpy.types.Image] = None


def group_objects(ctx: PipelineContext) -> List[BakeTarget]:
    cfg = ctx.cfg
    if cfg.atlas.mode == "SHARED_ATLAS":
        name = f"{ctx.base_name}_lightmap"
        return [BakeTarget(name, list(ctx.objects), True)]
    targets: List[BakeTarget] = []
    by_mesh: Dict[str, List[bpy.types.Object]] = {}
    for o in ctx.objects:
        by_mesh.setdefault(o.data.name, []).append(o)
    names = naming.unique_names([group[0].name for group in by_mesh.values()])
    for mesh_name, group in by_mesh.items():
        first = group[0]
        if len(group) > 1:
            ctx.warn(f"Objekte {[o.name for o in group]} teilen sich Mesh '{mesh_name}': es wird eine gemeinsame "
                     f"Lightmap anhand von '{first.name}' gebacken (Instanzen können nicht einzeln beleuchtet werden)")
        targets.append(BakeTarget(f"{names[first.name]}_lightmap", group, False))
    return targets


def _create_image(name: str, resolution: int, product_tracker) -> bpy.types.Image:
    existing = bpy.data.images.get(name)
    if existing is not None:
        bpy.data.images.remove(existing)
    img = bpy.data.images.new(name, resolution, resolution, float_buffer=True, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    img.generated_color = (0.0, 0.0, 0.0, 1.0)
    product_tracker.add_image(img, keep=True)
    return img


def _prepare_material_slots(ctx: PipelineContext, target: BakeTarget, bake_object: bpy.types.Object,
                            uv_name: str, materials_in_other_targets: Dict[str, str]) -> None:
    """Make sure every slot of ``bake_object`` has a material with an active bake node."""
    obj = bake_object
    bake_tracker = ctx.extra["bake_tracker"]
    if not obj.material_slots:
        # Objects without material get a neutral material so that the lightmap
        # can be baked and displayed. It is kept (rolled back only on failure).
        mat = _default_material(obj)
        obj.data.materials.append(mat)
        mesh = obj.data
        ctx.warn(f"Objekt '{obj.name}' hat kein Material, neutrales Material '{mat.name}' wurde zugewiesen")

        def _remove_slot(o=obj, material=mat):
            remove_material_slot(o, material)
        ctx.product.add_callback(_remove_slot)
    for index, slot in enumerate(obj.material_slots):
        mat = slot.material
        if mat is None:
            mat = _default_material(obj, index)
            slot.material = mat
            ctx.warn(f"Material-Slot {index} von '{obj.name}' war leer, neutrales Material '{mat.name}' zugewiesen")

            def _clear_slot(o=obj, i=index, m=mat):
                if i < len(o.material_slots) and o.material_slots[i].material == m:
                    o.material_slots[i].material = None
                if m.users == 0:
                    bpy.data.materials.remove(m)
            ctx.product.add_callback(_clear_slot)
        if not mat.use_nodes or mat.node_tree is None:
            mat.use_nodes = True
        # shared between targets with different images -> temporary copy for the bake only
        owner = materials_in_other_targets.get(mat.name)
        if owner is not None and owner != target.image_name:
            cp = mat.copy()
            cp.name = f"{mat.name}_BLME_bakecopy"
            slot.material = cp
            bake_tracker.add_material_copy(obj, index, mat, cp)
            mat = cp
        else:
            materials_in_other_targets[mat.name] = target.image_name
        nt = mat.node_tree
        node = nt.nodes.get(BAKE_NODE)
        if node is None:
            node = nt.nodes.new("ShaderNodeTexImage")
            node.name = BAKE_NODE
            node.label = "Lightmap bake target (temporary)"
            uvn = nt.nodes.new("ShaderNodeUVMap")
            uvn.name = BAKE_UV_NODE
            nt.links.new(uvn.outputs["UV"], node.inputs["Vector"])
            node.location = (-600, 600)
            uvn.location = (-850, 600)
            bake_tracker.add_nodes(mat, [BAKE_NODE, BAKE_UV_NODE])
        nt.nodes[BAKE_UV_NODE].uv_map = uv_name
        node.image = target.image
        for n in nt.nodes:
            n.select = False
        node.select = True
        nt.nodes.active = node


def remove_material_slot(obj: bpy.types.Object, material: bpy.types.Material) -> bool:
    """Remove the slot of ``material`` from ``obj`` (mesh.materials.pop leaves an empty slot)."""
    ensure_object_mode()
    index = next((i for i, s in enumerate(obj.material_slots) if s.material == material), -1)
    if index < 0:
        return False
    obj.active_material_index = index
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.object.material_slot_remove()
    if material.users == 0:
        bpy.data.materials.remove(material)
    return True


def _default_material(obj: bpy.types.Object, index: int = -1) -> bpy.types.Material:
    name = f"{DEFAULT_MATERIAL_PREFIX}{obj.name}" + (f"_{index}" if index >= 0 else "")
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
    return mat


def step_prepare_bake_targets(ctx: PipelineContext) -> None:
    cfg = ctx.cfg
    uv_name = cfg.uv.uv_name
    targets = group_objects(ctx)
    shared: Dict[str, str] = {}
    from .state import TempTracker
    bake_tracker = TempTracker()
    ctx.extra["bake_tracker"] = bake_tracker
    ctx.temp.add_callback(bake_tracker.cleanup)  # safety net if the bake step never runs
    for t in targets:
        t.image = _create_image(t.image_name, cfg.bake.resolution, ctx.product)
        ctx.images[t.image_name] = t.image
        ctx.image_objects[t.image_name] = [o.name for o in t.objects]
        for o in t.objects:
            _prepare_material_slots(ctx, t, o, uv_name, shared)
    ctx.extra["bake_targets"] = targets
    log.info("%d Bake-Ziel(e) vorbereitet", len(targets))
    # scene configuration + bypass of preview materials for the whole bake stage
    from . import materials
    from .pipeline import Step
    configure_scene_for_bake(ctx)
    restore = materials.bypass_objects(ctx.objects)
    ctx.extra["bake_bypass_restore"] = restore
    ctx.temp.add_callback(_restore_bypass, ctx)   # safety net for failures/cancels
    return [Step(name=f"bake:{t.image_name}", label=f"Backe {t.image_name} ({len(t.objects)} Objekte)",
                 func=_make_bake_step(t), weight=10.0 / max(1, len(targets)), stage="bake",
                 bake_image=t.image_name) for t in targets]


def _restore_bypass(ctx: PipelineContext) -> None:
    restore = ctx.extra.pop("bake_bypass_restore", None)
    if restore is not None:
        restore()


def _make_bake_step(target: "BakeTarget"):
    def _step(ctx: PipelineContext) -> None:
        bake_target(ctx, target)
    return _step


# --- bake execution ----------------------------------------------------------------

def bake_kwargs(cfg) -> Dict[str, object]:
    b = cfg.bake
    if b.type == "DIFFUSE_LIGHTING":
        passes = set()
        if b.use_direct:
            passes.add("DIRECT")
        if b.use_indirect:
            passes.add("INDIRECT")
        return {"type": "DIFFUSE", "pass_filter": passes}
    if b.type == "COMBINED":
        passes = {"DIFFUSE", "GLOSSY", "TRANSMISSION", "EMIT"}
        if b.use_direct:
            passes.add("DIRECT")
        if b.use_indirect:
            passes.add("INDIRECT")
        return {"type": "COMBINED", "pass_filter": passes}
    if b.type == "AO":
        return {"type": "AO", "pass_filter": set()}
    raise LightmapExportError(f"Unbekannter Bake-Typ {b.type}")


def configure_scene_for_bake(ctx: PipelineContext) -> None:
    sc = ctx.scene
    b = ctx.cfg.bake
    sc.render.engine = "CYCLES"
    sc.cycles.device = ctx.device_info.get("device", "CPU")
    sc.cycles.samples = b.samples
    sc.cycles.use_denoising = False  # not supported for baking anyway
    bake = sc.render.bake
    bake.target = "IMAGE_TEXTURES"
    bake.use_selected_to_active = False
    bake.use_clear = True
    bake.margin = int(b.margin_px)
    bake.margin_type = b.margin_type
    bake.use_pass_direct = b.use_direct
    bake.use_pass_indirect = b.use_indirect
    bake.use_pass_color = False
    if b.type == "AO" and b.ao_distance > 0 and sc.world is not None:
        world = sc.world
        old = world.light_settings.distance
        world.light_settings.distance = b.ao_distance
        ctx.temp.add_callback(lambda w=world, v=old: setattr(w.light_settings, "distance", v))


def bake_target(ctx: PipelineContext, target: BakeTarget) -> None:
    """Bake one image (blocking). Used by the headless runner."""
    kwargs = prepare_bake_call(ctx, target)
    try:
        result = bpy.ops.object.bake(**kwargs)
    except RuntimeError as exc:
        raise LightmapExportError(f"Cycles-Bake für '{target.image_name}' fehlgeschlagen: {exc}") from exc
    if "FINISHED" not in result:
        raise LightmapExportError(f"Cycles-Bake für '{target.image_name}' wurde nicht abgeschlossen: {result}")


def _bake_objects(target: BakeTarget) -> List[bpy.types.Object]:
    """Objects to select for the bake (one per mesh datablock)."""
    seen = set()
    objs = []
    for o in target.objects:
        if o.data.name in seen:
            continue
        seen.add(o.data.name)
        objs.append(o)
    return objs


def prepare_bake_call(ctx: PipelineContext, target: BakeTarget) -> Dict[str, object]:
    """Select the objects of ``target`` and return the keyword arguments for ``bpy.ops.object.bake``."""
    uv_name = ctx.cfg.uv.uv_name
    ensure_object_mode()
    objs = _bake_objects(target)
    for o in objs:
        o.data.uv_layers.active = o.data.uv_layers[uv_name]
    select_only(objs, objs[0], ctx.view_layer)
    kwargs = bake_kwargs(ctx.cfg)
    log.info("Backe '%s' (%d Objekte, %s, %d Samples, %dpx)", target.image_name, len(objs),
             kwargs["type"], ctx.cfg.bake.samples, ctx.cfg.bake.resolution)
    return dict(type=kwargs["type"], pass_filter=kwargs["pass_filter"], uv_layer=uv_name,
                margin=int(ctx.cfg.bake.margin_px), margin_type=ctx.cfg.bake.margin_type,
                use_clear=True, target="IMAGE_TEXTURES", save_mode="INTERNAL")


def step_bake_finish(ctx: PipelineContext) -> None:
    """Restore bypassed preview materials, remove bake nodes/copies and verify the images."""
    _restore_bypass(ctx)
    tracker = ctx.extra.get("bake_tracker")
    if tracker is not None:
        tracker.cleanup()
    if not ctx.images:
        raise LightmapExportError("Keine Bake-Ziele vorhanden")
    verify_bakes(ctx)


def step_bake_all(ctx: PipelineContext) -> None:
    """Blocking convenience: bake every prepared target, then finish."""
    for t in ctx.extra.get("bake_targets", []):
        ctx.check_cancel()
        bake_target(ctx, t)
    step_bake_finish(ctx)


def verify_bakes(ctx: PipelineContext) -> None:
    from .images import image_stats
    for name, img in ctx.images.items():
        stats = image_stats(img)
        ctx.extra.setdefault("image_stats", {})[name] = stats
        if stats["max"] <= 0.0:
            ctx.warn(f"Lightmap '{name}' ist komplett schwarz, prüfe Beleuchtung und UVs")
        elif stats["nonzero"] < 0.05:
            ctx.warn(f"Lightmap '{name}': nur {stats['nonzero'] * 100:.1f} % der Pixel sind belegt. Zu viele kleine "
                     f"UV-Inseln für {ctx.cfg.bake.resolution} px – Auflösung erhöhen, Island Margin verringern oder "
                     f"Angle Limit erhöhen.")
        log.info("Lightmap '%s': Mittel %.4f, Max %.4f, belegt %.1f %%", name, stats["mean"], stats["max"],
                 stats["nonzero"] * 100)
