# SPDX-License-Identifier: MIT
"""Saving and restoring Blender state around pipeline runs.

Two mechanisms are provided:

* :class:`SceneStateSnapshot` – captures render/bake/image settings, selection,
  mode and UV layer activity so they can be restored even after exceptions.
* :class:`TempTracker` – records every datablock the pipeline creates
  temporarily (lights, collections, images, node groups, material copies,
  nodes added to existing materials) so that they can be removed or reverted
  reliably.
"""

from __future__ import annotations

import contextlib
from typing import Any, Dict, List, Optional, Tuple

import bpy

from .log import get_logger

log = get_logger("state")


# --- scene snapshot -----------------------------------------------------------

_BAKE_PROPS = (
    "use_pass_direct", "use_pass_indirect", "use_pass_color", "use_pass_emit",
    "use_pass_diffuse", "use_pass_glossy", "use_pass_transmission",
    "margin", "margin_type", "use_clear", "use_selected_to_active", "target",
    "use_split_materials", "max_ray_distance", "cage_extrusion",
)
_CYCLES_PROPS = ("device", "samples", "use_denoising", "bake_type", "use_adaptive_sampling",
                 "adaptive_threshold", "time_limit", "seed")
_IMAGE_PROPS = ("file_format", "color_depth", "color_mode", "exr_codec", "compression", "quality")
_RENDER_PROPS = ("engine", "resolution_x", "resolution_y", "resolution_percentage", "filepath",
                 "use_compositing", "film_transparent", "use_file_extension")
_VIEW_PROPS = ("view_transform", "look", "exposure", "gamma")
_WORLD_PROPS = ("light_settings.distance",)


def _get_path(obj, path: str):
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def _set_path(obj, path: str, value) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


class SceneStateSnapshot:
    """Snapshot of scene settings relevant for baking and exporting."""

    def __init__(self, context: Optional[bpy.types.Context] = None) -> None:
        self.context = context or bpy.context
        self.scene = self.context.scene
        self.data: Dict[str, Any] = {}
        self.uv_state: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
        self.selection: List[str] = []
        self.active: Optional[str] = None
        self.mode: str = "OBJECT"
        self.world_name: Optional[str] = None
        self.compositing_group: Optional[str] = None
        self.hidden_render: Dict[str, bool] = {}
        self.capture()

    # ..........................................................................
    def capture(self) -> None:
        sc = self.scene
        d = self.data
        for p in _RENDER_PROPS:
            d["render." + p] = getattr(sc.render, p)
        for p in _BAKE_PROPS:
            d["bake." + p] = getattr(sc.render.bake, p)
        for p in _CYCLES_PROPS:
            if hasattr(sc.cycles, p):
                d["cycles." + p] = getattr(sc.cycles, p)
        for p in _IMAGE_PROPS:
            try:
                d["image." + p] = getattr(sc.render.image_settings, p)
            except AttributeError:
                pass
        for p in _VIEW_PROPS:
            try:
                d["view." + p] = getattr(sc.view_settings, p)
            except AttributeError:
                pass
        d["use_nodes"] = getattr(sc, "use_nodes", False)
        ng = getattr(sc, "compositing_node_group", None)
        self.compositing_group = ng.name if ng else None
        self.world_name = sc.world.name if sc.world else None
        for mesh in bpy.data.meshes:
            act = mesh.uv_layers.active.name if mesh.uv_layers.active else None
            ren = next((u.name for u in mesh.uv_layers if u.active_render), None)
            self.uv_state[mesh.name] = (act, ren)
        vl = self.context.view_layer
        self.selection = [o.name for o in vl.objects if o.select_get(view_layer=vl)]
        self.active = vl.objects.active.name if vl.objects.active else None
        self.mode = self.context.mode if hasattr(self.context, "mode") else "OBJECT"
        self.hidden_render = {o.name: o.hide_render for o in bpy.data.objects}

    # ..........................................................................
    def restore(self) -> None:
        sc = self.scene
        d = self.data
        # leave edit mode first
        try:
            if bpy.context.mode != "OBJECT" and bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode="OBJECT")
        except Exception as exc:  # pragma: no cover
            log.warning("Konnte Objektmodus nicht wiederherstellen: %s", exc)
        for key, value in d.items():
            try:
                if key.startswith("render."):
                    setattr(sc.render, key[7:], value)
                elif key.startswith("bake."):
                    setattr(sc.render.bake, key[5:], value)
                elif key.startswith("cycles."):
                    setattr(sc.cycles, key[7:], value)
                elif key.startswith("image."):
                    setattr(sc.render.image_settings, key[6:], value)
                elif key.startswith("view."):
                    setattr(sc.view_settings, key[5:], value)
                elif key == "use_nodes":
                    sc.use_nodes = value
            except Exception as exc:
                log.debug("Einstellung %s nicht wiederherstellbar: %s", key, exc)
        try:
            sc.compositing_node_group = bpy.data.node_groups.get(self.compositing_group) if self.compositing_group else None
        except Exception:
            pass
        if self.world_name is not None:
            w = bpy.data.worlds.get(self.world_name)
            if w is not None:
                sc.world = w
        for mesh_name, (act, ren) in self.uv_state.items():
            mesh = bpy.data.meshes.get(mesh_name)
            if mesh is None:
                continue
            if act and act in mesh.uv_layers:
                mesh.uv_layers.active = mesh.uv_layers[act]
            if ren and ren in mesh.uv_layers:
                mesh.uv_layers[ren].active_render = True
        for name, hidden in self.hidden_render.items():
            o = bpy.data.objects.get(name)
            if o is not None and o.hide_render != hidden:
                o.hide_render = hidden
        vl = self.context.view_layer
        try:
            for o in vl.objects:
                o.select_set(o.name in self.selection, view_layer=vl)
            vl.objects.active = bpy.data.objects.get(self.active) if self.active else None
        except Exception as exc:
            log.debug("Selektion nicht wiederherstellbar: %s", exc)


@contextlib.contextmanager
def preserved_scene_state(context: Optional[bpy.types.Context] = None):
    snap = SceneStateSnapshot(context)
    try:
        yield snap
    finally:
        snap.restore()


# --- temporary datablock tracking --------------------------------------------

class TempTracker:
    """Tracks temporary changes so they can be undone in reverse order."""

    def __init__(self) -> None:
        self._undo: List[Tuple[str, Any]] = []
        self.keep_images: bool = True

    # registration ...............................................................
    def add_object(self, obj: bpy.types.Object) -> bpy.types.Object:
        self._undo.append(("object", obj.name))
        return obj

    def add_collection(self, coll: bpy.types.Collection) -> bpy.types.Collection:
        self._undo.append(("collection", coll.name))
        return coll

    def add_light_data(self, light: bpy.types.Light) -> bpy.types.Light:
        self._undo.append(("light", light.name))
        return light

    def add_image(self, img: bpy.types.Image, keep: bool = True) -> bpy.types.Image:
        self._undo.append(("image", (img.name, keep)))
        return img

    def add_node_group(self, ng: bpy.types.NodeTree) -> bpy.types.NodeTree:
        self._undo.append(("node_group", ng.name))
        return ng

    def add_world(self, world: bpy.types.World) -> bpy.types.World:
        self._undo.append(("world", world.name))
        return world

    def add_material_copy(self, obj: bpy.types.Object, slot_index: int,
                          original: bpy.types.Material, copy: bpy.types.Material) -> None:
        self._undo.append(("material_copy", (obj.name, slot_index, original.name, copy.name)))

    def add_mesh_copy(self, obj: bpy.types.Object, original: bpy.types.Mesh, copy: bpy.types.Mesh) -> None:
        self._undo.append(("mesh_copy", (obj.name, original.name, copy.name)))

    def add_nodes(self, material: bpy.types.Material, node_names: List[str]) -> None:
        self._undo.append(("nodes", (material.name, list(node_names))))

    def add_uv_layer(self, mesh: bpy.types.Mesh, uv_name: str) -> None:
        self._undo.append(("uv_layer", (mesh.name, uv_name)))

    def add_callback(self, func, *args) -> None:
        self._undo.append(("callback", (func, args)))

    # undo .......................................................................
    def cleanup(self, remove_images: bool = False) -> None:
        while self._undo:
            kind, payload = self._undo.pop()
            try:
                self._undo_one(kind, payload, remove_images)
            except Exception as exc:  # pragma: no cover - never fail cleanup
                log.warning("Aufräumen von %s fehlgeschlagen: %s", kind, exc)

    def _undo_one(self, kind: str, payload, remove_images: bool) -> None:
        if kind == "object":
            o = bpy.data.objects.get(payload)
            if o is not None:
                data = o.data
                bpy.data.objects.remove(o, do_unlink=True)
                if data is not None and getattr(data, "users", 1) == 0:
                    coll = _data_collection(data)
                    if coll is not None:
                        coll.remove(data)
        elif kind == "collection":
            c = bpy.data.collections.get(payload)
            if c is not None:
                for o in list(c.objects):
                    bpy.data.objects.remove(o, do_unlink=True)
                bpy.data.collections.remove(c)
        elif kind == "light":
            lt = bpy.data.lights.get(payload)
            if lt is not None and lt.users == 0:
                bpy.data.lights.remove(lt)
        elif kind == "image":
            name, keep = payload
            if remove_images or not keep:
                img = bpy.data.images.get(name)
                if img is not None:
                    bpy.data.images.remove(img)
        elif kind == "node_group":
            ng = bpy.data.node_groups.get(payload)
            if ng is not None:
                bpy.data.node_groups.remove(ng)
        elif kind == "world":
            w = bpy.data.worlds.get(payload)
            if w is not None:
                bpy.data.worlds.remove(w)
        elif kind == "material_copy":
            obj_name, slot_index, orig_name, copy_name = payload
            o = bpy.data.objects.get(obj_name)
            orig = bpy.data.materials.get(orig_name)
            cp = bpy.data.materials.get(copy_name)
            if o is not None and orig is not None and slot_index < len(o.material_slots):
                o.material_slots[slot_index].material = orig
            if cp is not None and cp.users == 0:
                bpy.data.materials.remove(cp)
        elif kind == "mesh_copy":
            obj_name, orig_name, copy_name = payload
            o = bpy.data.objects.get(obj_name)
            orig = bpy.data.meshes.get(orig_name)
            cp = bpy.data.meshes.get(copy_name)
            if o is not None and orig is not None:
                o.data = orig
            if cp is not None and cp.users == 0:
                bpy.data.meshes.remove(cp)
        elif kind == "nodes":
            mat_name, names = payload
            mat = bpy.data.materials.get(mat_name)
            if mat is not None and mat.node_tree is not None:
                for n in names:
                    node = mat.node_tree.nodes.get(n)
                    if node is not None:
                        mat.node_tree.nodes.remove(node)
        elif kind == "uv_layer":
            mesh_name, uv_name = payload
            mesh = bpy.data.meshes.get(mesh_name)
            if mesh is not None and uv_name in mesh.uv_layers:
                mesh.uv_layers.remove(mesh.uv_layers[uv_name])
        elif kind == "callback":
            func, args = payload
            func(*args)


def _data_collection(data):
    mapping = {
        bpy.types.Mesh: bpy.data.meshes,
        bpy.types.Light: bpy.data.lights,
        bpy.types.Camera: bpy.data.cameras,
        bpy.types.Curve: bpy.data.curves,
    }
    for typ, coll in mapping.items():
        if isinstance(data, typ):
            return coll
    return None


# --- helpers used by several modules -------------------------------------------

def ensure_object_mode() -> None:
    if bpy.context.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError:
            pass


def select_only(objects, active=None, view_layer=None) -> None:
    vl = view_layer or bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False, view_layer=vl)
    for o in objects:
        try:
            o.select_set(True, view_layer=vl)
        except RuntimeError:
            pass
    vl.objects.active = active if active is not None else (objects[0] if objects else None)
