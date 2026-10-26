# SPDX-License-Identifier: GPL-3.0-or-later
"""Lightmap material preview without touching the original node graph.

For every material of a lightmapped object three nodes are added:

* ``BLME_UV``        – UV Map node pointing to the lightmap UV channel
* ``BLME_Lightmap``  – Image Texture node with the lightmap (Non-Color)
* ``BLME_Shader``    – group node ``BLME_LightmapShader`` placed between the
                       original shader and the Material Output

The group mixes the original shader with an emission of
``BaseColor * Lightmap`` (diffuse lighting), ``Lightmap`` (combined) or a
diffuse BSDF of ``BaseColor * AO`` (ambient occlusion). ``Preview`` = 0 shows
the original material, 1 the lightmap. The original link into the Material
Output is stored on the material and restored by :func:`restore_material`.
"""

from __future__ import annotations

import contextlib
from typing import Dict, Iterable, List, Optional, Tuple

import bpy

from .log import get_logger
from .pipeline import PipelineContext

log = get_logger("materials")

GROUP_NAME = "BLME_LightmapShader"
NODE_UV = "BLME_UV"
NODE_IMAGE = "BLME_Lightmap"
NODE_GROUP = "BLME_Shader"
PROP_RESTORE = "BLME_restore"
PROP_ORIGINAL_MATERIAL = "BLME_original_material"
BAKE_TYPE_VALUE = {"DIFFUSE_LIGHTING": 0.0, "COMBINED": 1.0, "AO": 2.0}
# mode -> (Preview, Albedo): Preview 0 shows the original shader, Albedo 0 hides the base colour
MODE_VALUE = {"ORIGINAL": 0.0, "PREVIEW": 1.0, "BAKED_EXTERNAL": 1.0, "LIGHTMAP_ONLY": 1.0}
MODE_ALBEDO = {"ORIGINAL": 1.0, "PREVIEW": 1.0, "BAKED_EXTERNAL": 1.0, "LIGHTMAP_ONLY": 0.0}


# --- node group --------------------------------------------------------------------

def _upgrade_group(ng: bpy.types.ShaderNodeTree) -> None:
    """Add the 'Albedo' input to groups created by older versions."""
    names = [s.name for s in ng.interface.items_tree if s.item_type == "SOCKET" and s.in_out == "INPUT"]
    if "Albedo" in names:
        return
    s = ng.interface.new_socket("Albedo", in_out="INPUT", socket_type="NodeSocketFloat")
    s.default_value, s.min_value, s.max_value = 1.0, 0.0, 1.0
    gin = next((n for n in ng.nodes if n.bl_idname == "NodeGroupInput"), None)
    mul = next((n for n in ng.nodes if n.label == "BaseColor * Lightmap"), None)
    if gin is None or mul is None:
        return
    alb = ng.nodes.new("ShaderNodeMix"); alb.data_type = "RGBA"; alb.blend_type = "MIX"
    alb.label = "Albedo on/off"; alb.location = (mul.location.x - 250, mul.location.y + 150)
    alb.inputs[6].default_value = (1.0, 1.0, 1.0, 1.0)
    ng.links.new(gin.outputs["Albedo"], alb.inputs["Factor"])
    ng.links.new(gin.outputs["Base Color"], alb.inputs[7])
    ng.links.new(alb.outputs[2], mul.inputs[6])


def ensure_group() -> bpy.types.ShaderNodeTree:
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is not None and ng.bl_idname == "ShaderNodeTree":
        _upgrade_group(ng)
        return ng
    ng = bpy.data.node_groups.new(GROUP_NAME, "ShaderNodeTree")
    ng.use_fake_user = True
    iface = ng.interface
    iface.new_socket("Shader", in_out="INPUT", socket_type="NodeSocketShader")
    s = iface.new_socket("Base Color", in_out="INPUT", socket_type="NodeSocketColor")
    s.default_value = (1.0, 1.0, 1.0, 1.0)
    s = iface.new_socket("Lightmap", in_out="INPUT", socket_type="NodeSocketColor")
    s.default_value = (1.0, 1.0, 1.0, 1.0)
    s = iface.new_socket("Preview", in_out="INPUT", socket_type="NodeSocketFloat")
    s.default_value, s.min_value, s.max_value = 1.0, 0.0, 1.0
    s = iface.new_socket("Lightmap Type", in_out="INPUT", socket_type="NodeSocketFloat")
    s.default_value, s.min_value, s.max_value = 0.0, 0.0, 2.0
    s = iface.new_socket("Strength", in_out="INPUT", socket_type="NodeSocketFloat")
    s.default_value, s.min_value, s.max_value = 1.0, 0.0, 100.0
    s = iface.new_socket("Albedo", in_out="INPUT", socket_type="NodeSocketFloat")
    s.default_value, s.min_value, s.max_value = 1.0, 0.0, 1.0
    iface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")

    n = ng.nodes
    gin = n.new("NodeGroupInput"); gin.location = (-900, 0)
    gout = n.new("NodeGroupOutput"); gout.location = (700, 0)

    # Albedo = 0 -> white instead of the base colour (shows the pure lightmap)
    alb = n.new("ShaderNodeMix"); alb.data_type = "RGBA"; alb.blend_type = "MIX"
    alb.label = "Albedo on/off"; alb.location = (-750, 350)
    alb.inputs[6].default_value = (1.0, 1.0, 1.0, 1.0)
    ng.links.new(gin.outputs["Albedo"], alb.inputs["Factor"])
    ng.links.new(gin.outputs["Base Color"], alb.inputs[7])

    mul = n.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0; mul.location = (-500, 200); mul.label = "BaseColor * Lightmap"
    ng.links.new(alb.outputs[2], mul.inputs[6])
    ng.links.new(gin.outputs["Lightmap"], mul.inputs[7])

    emit_lit = n.new("ShaderNodeEmission"); emit_lit.location = (-200, 300); emit_lit.label = "Diffuse lighting"
    ng.links.new(mul.outputs[2], emit_lit.inputs["Color"])
    ng.links.new(gin.outputs["Strength"], emit_lit.inputs["Strength"])

    emit_comb = n.new("ShaderNodeEmission"); emit_comb.location = (-200, 100); emit_comb.label = "Combined"
    ng.links.new(gin.outputs["Lightmap"], emit_comb.inputs["Color"])
    ng.links.new(gin.outputs["Strength"], emit_comb.inputs["Strength"])

    diff_ao = n.new("ShaderNodeBsdfDiffuse"); diff_ao.location = (-200, -100); diff_ao.label = "AO"
    ng.links.new(mul.outputs[2], diff_ao.inputs["Color"])

    t1 = n.new("ShaderNodeMath"); t1.operation = "MINIMUM"; t1.inputs[1].default_value = 1.0; t1.location = (-500, -300)
    ng.links.new(gin.outputs["Lightmap Type"], t1.inputs[0])
    t2 = n.new("ShaderNodeMath"); t2.operation = "SUBTRACT"; t2.inputs[1].default_value = 1.0; t2.use_clamp = True
    t2.location = (-500, -450)
    ng.links.new(gin.outputs["Lightmap Type"], t2.inputs[0])

    mix_a = n.new("ShaderNodeMixShader"); mix_a.location = (100, 200)
    ng.links.new(t1.outputs[0], mix_a.inputs["Fac"])
    ng.links.new(emit_lit.outputs[0], mix_a.inputs[1])
    ng.links.new(emit_comb.outputs[0], mix_a.inputs[2])
    mix_b = n.new("ShaderNodeMixShader"); mix_b.location = (300, 100)
    ng.links.new(t2.outputs[0], mix_b.inputs["Fac"])
    ng.links.new(mix_a.outputs[0], mix_b.inputs[1])
    ng.links.new(diff_ao.outputs[0], mix_b.inputs[2])
    mix_final = n.new("ShaderNodeMixShader"); mix_final.location = (500, 0)
    ng.links.new(gin.outputs["Preview"], mix_final.inputs["Fac"])
    ng.links.new(gin.outputs["Shader"], mix_final.inputs[1])
    ng.links.new(mix_b.outputs[0], mix_final.inputs[2])
    ng.links.new(mix_final.outputs[0], gout.inputs[0])
    return ng


# --- per material ------------------------------------------------------------------

def _output_node(nt: bpy.types.ShaderNodeTree) -> Optional[bpy.types.Node]:
    outs = [n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]
    if not outs:
        return None
    return next((n for n in outs if n.is_active_output), outs[0])


def _find_base_color(nt: bpy.types.ShaderNodeTree, shader_node: Optional[bpy.types.Node]):
    """Return (socket_or_None, default_rgba) for the base color of the original shader."""
    candidates = []
    if shader_node is not None:
        candidates.append(shader_node)
    candidates += [n for n in nt.nodes if n.bl_idname in ("ShaderNodeBsdfPrincipled", "ShaderNodeBsdfDiffuse")]
    for node in candidates:
        for sock_name in ("Base Color", "Color"):
            sock = node.inputs.get(sock_name)
            if sock is None or sock.type != "RGBA":
                continue
            if sock.is_linked:
                return sock.links[0].from_socket, None
            return None, tuple(sock.default_value)
    return None, (1.0, 1.0, 1.0, 1.0)


def bind_material(mat: bpy.types.Material, image: bpy.types.Image, uv_name: str,
                  bake_type: str, mode: Optional[str] = None) -> bool:
    """Insert (or update) the lightmap preview nodes in ``mat``.

    ``mode`` None keeps the display mode of an existing binding (re-bake, re-import,
    atlas update ...); a fresh binding starts with ``PREVIEW``. An explicit mode
    (``PREVIEW``, ``LIGHTMAP_ONLY``, ``ORIGINAL``) always wins.
    """
    if not mat.use_nodes or mat.node_tree is None:
        mat.use_nodes = True
    nt = mat.node_tree
    out = _output_node(nt)
    if out is None:
        out = nt.nodes.new("ShaderNodeOutputMaterial")
    ensure_group()  # also upgrades groups created by older versions
    group = nt.nodes.get(NODE_GROUP)
    fresh = group is None
    if fresh:
        surface_link = out.inputs["Surface"].links[0] if out.inputs["Surface"].is_linked else None
        shader_node = surface_link.from_node if surface_link else None
        mat[PROP_RESTORE] = {
            "from_node": shader_node.name if shader_node else "",
            "from_socket": surface_link.from_socket.identifier if surface_link else "",
            "output": out.name,
        }
        group = nt.nodes.new("ShaderNodeGroup")
        group.name = NODE_GROUP
        group.label = "Lightmap preview"
        group.node_tree = ensure_group()
        group.location = (out.location.x - 250, out.location.y)
        out.location.x += 250
        uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.name = NODE_UV; uvn.location = (group.location.x - 600, group.location.y - 300)
        imn = nt.nodes.new("ShaderNodeTexImage"); imn.name = NODE_IMAGE; imn.label = "Lightmap"
        imn.location = (group.location.x - 350, group.location.y - 300)
        imn.interpolation = "Linear"
        nt.links.new(uvn.outputs["UV"], imn.inputs["Vector"])
        nt.links.new(imn.outputs["Color"], group.inputs["Lightmap"])
        if shader_node is not None:
            nt.links.new(surface_link.from_socket, group.inputs["Shader"])
        base_socket, base_value = _find_base_color(nt, shader_node)
        if base_socket is not None:
            nt.links.new(base_socket, group.inputs["Base Color"])
        elif base_value is not None:
            group.inputs["Base Color"].default_value = base_value
        nt.links.new(group.outputs[0], out.inputs["Surface"])
    nt.nodes[NODE_UV].uv_map = uv_name
    nt.nodes[NODE_IMAGE].image = image
    if image.colorspace_settings.name != "Non-Color":
        image.colorspace_settings.name = "Non-Color"
    group.inputs["Lightmap Type"].default_value = BAKE_TYPE_VALUE.get(bake_type, 0.0)
    if mode is None and fresh:
        mode = "PREVIEW"
    if mode is not None:
        group.inputs["Preview"].default_value = MODE_VALUE.get(mode, 1.0)
        if "Albedo" in group.inputs:
            group.inputs["Albedo"].default_value = MODE_ALBEDO.get(mode, 1.0)
    return fresh


def get_mode(mat: bpy.types.Material) -> Optional[str]:
    """Current display mode of a bound material (None if not bound)."""
    nt = mat.node_tree if mat else None
    group = nt.nodes.get(NODE_GROUP) if nt else None
    if group is None:
        return None
    if group.inputs["Preview"].default_value < 0.5:
        return "ORIGINAL"
    if "Albedo" in group.inputs and group.inputs["Albedo"].default_value < 0.5:
        return "LIGHTMAP_ONLY"
    return "PREVIEW"


def set_mode(mat: bpy.types.Material, mode: str) -> bool:
    nt = mat.node_tree
    if nt is None:
        return False
    group = nt.nodes.get(NODE_GROUP)
    if group is None:
        return False
    ensure_group()
    group.inputs["Preview"].default_value = MODE_VALUE.get(mode, 1.0)
    if "Albedo" in group.inputs:
        group.inputs["Albedo"].default_value = MODE_ALBEDO.get(mode, 1.0)
    return True


def restore_material(mat: bpy.types.Material) -> bool:
    """Remove the preview nodes and restore the original output link."""
    nt = mat.node_tree
    if nt is None or nt.nodes.get(NODE_GROUP) is None:
        if PROP_RESTORE in mat:
            del mat[PROP_RESTORE]
        return False
    info = dict(mat.get(PROP_RESTORE, {}))
    out = nt.nodes.get(info.get("output", "")) or _output_node(nt)
    for name in (NODE_GROUP, NODE_IMAGE, NODE_UV):
        node = nt.nodes.get(name)
        if node is not None:
            nt.nodes.remove(node)
    if out is not None:
        from_node = nt.nodes.get(info.get("from_node", ""))
        if from_node is not None:
            sock = next((s for s in from_node.outputs if s.identifier == info.get("from_socket")), None)
            if sock is None and from_node.outputs:
                sock = from_node.outputs[0]
            if sock is not None:
                nt.links.new(sock, out.inputs["Surface"])
        out.location.x -= 250
    if PROP_RESTORE in mat:
        del mat[PROP_RESTORE]
    return True


def is_bound(mat: bpy.types.Material) -> bool:
    return mat is not None and mat.node_tree is not None and mat.node_tree.nodes.get(NODE_GROUP) is not None


@contextlib.contextmanager
def bypassed(mat: bpy.types.Material):
    """Temporarily link the original shader straight into the output (for exporters)."""
    nt = mat.node_tree
    group = nt.nodes.get(NODE_GROUP) if nt else None
    if group is None:
        yield
        return
    out = _output_node(nt)
    shader_link = group.inputs["Shader"].links[0] if group.inputs["Shader"].is_linked else None
    if out is None or shader_link is None:
        yield
        return
    from_socket = shader_link.from_socket
    nt.links.new(from_socket, out.inputs["Surface"])
    try:
        yield
    finally:
        nt.links.new(group.outputs[0], out.inputs["Surface"])


def bypass_objects(objects: Iterable[bpy.types.Object]):
    """Bypass preview bindings of all materials of ``objects``; returns a restore callable."""
    stack = contextlib.ExitStack()
    seen = set()
    for o in objects:
        for slot in getattr(o, "material_slots", []):
            m = slot.material
            if m is not None and m.name not in seen and is_bound(m):
                seen.add(m.name)
                stack.enter_context(bypassed(m))
    return stack.close


@contextlib.contextmanager
def original_materials(objects: Iterable[bpy.types.Object]):
    """Context manager: all materials of ``objects`` show their original graph."""
    mats = []
    seen = set()
    for o in objects:
        for slot in getattr(o, "material_slots", []):
            m = slot.material
            if m is not None and m.name not in seen and is_bound(m):
                seen.add(m.name)
                mats.append(m)
    with contextlib.ExitStack() as stack:
        for m in mats:
            stack.enter_context(bypassed(m))
        yield


# --- objects ------------------------------------------------------------------------------

def _materials_shared_across_images(objects_by_image: Dict[str, List[bpy.types.Object]]) -> Dict[str, set]:
    usage: Dict[str, set] = {}
    for image_name, objs in objects_by_image.items():
        for o in objs:
            for slot in o.material_slots:
                if slot.material is not None:
                    usage.setdefault(slot.material.name, set()).add(image_name)
    return {m: imgs for m, imgs in usage.items() if len(imgs) > 1}


def bind_objects(objects_by_image: Dict[str, List[bpy.types.Object]], images: Dict[str, bpy.types.Image],
                 uv_name: str, bake_type: str, mode: Optional[str] = None, warn=None) -> int:
    """Bind the lightmap of every image to the materials of its objects (``mode`` None = keep).

    Materials shared by objects that have *different* lightmaps are replaced on
    those objects by per-object copies (``<Material>_LM_<Object>``); the
    original material datablock stays untouched and the copy remembers it in a
    custom property, so :func:`restore_objects` can put the original back.
    """
    shared = _materials_shared_across_images(objects_by_image)
    count = 0
    for image_name, objs in objects_by_image.items():
        image = images[image_name]
        for o in objs:
            for index, slot in enumerate(o.material_slots):
                mat = slot.material
                if mat is None:
                    continue
                if mat.name in shared:
                    orig_name = mat.get(PROP_ORIGINAL_MATERIAL, mat.name)
                    copy_name = f"{orig_name}_LM_{o.name}"
                    cp = bpy.data.materials.get(copy_name)
                    if cp is None:
                        cp = mat.copy()
                        cp.name = copy_name
                        cp[PROP_ORIGINAL_MATERIAL] = orig_name
                        if warn:
                            warn(f"Material '{orig_name}' wird von mehreren Lightmaps genutzt, "
                                 f"'{o.name}' erhält die Kopie '{copy_name}'")
                    slot.material = cp
                    mat = cp
                bind_material(mat, image, uv_name, bake_type, mode)
                count += 1
    return count


def restore_objects(objects: Iterable[bpy.types.Object]) -> int:
    count = 0
    for o in objects:
        for slot in getattr(o, "material_slots", []):
            mat = slot.material
            if mat is None:
                continue
            orig_name = mat.get(PROP_ORIGINAL_MATERIAL)
            if orig_name and orig_name in bpy.data.materials and orig_name != mat.name:
                slot.material = bpy.data.materials[orig_name]
                if mat.users == 0:
                    bpy.data.materials.remove(mat)
                count += 1
                continue
            if restore_material(mat):
                count += 1
    return count


def apply_from_metadata(objects: Iterable[bpy.types.Object], mode: Optional[str] = "PREVIEW") -> int:
    """(Re)apply lightmaps from the ``BLME_lightmap`` custom property of each object.

    ``mode``: PREVIEW (Basisfarbe × Lightmap), LIGHTMAP_ONLY (nur Lightmap), ORIGINAL,
    None = vorhandenen Modus beibehalten.
    """
    from .metadata import read_object_metadata, resolve_lightmap_image
    by_image: Dict[str, List[bpy.types.Object]] = {}
    images: Dict[str, bpy.types.Image] = {}
    uv_name = "LightmapUV"
    bake_type = "DIFFUSE_LIGHTING"
    for o in objects:
        meta = read_object_metadata(o)
        if not meta:
            continue
        img = resolve_lightmap_image(meta, o)
        if img is None:
            log.warning("Lightmap für '%s' nicht gefunden (%s)", o.name, meta.get("file"))
            continue
        images[img.name] = img
        by_image.setdefault(img.name, []).append(o)
        uv_name = meta.get("uv_name", uv_name)
        bake_type = meta.get("bake_type", bake_type)
        if uv_name not in o.data.uv_layers and 0 <= int(meta.get("uv_index", -1)) < len(o.data.uv_layers):
            # glTF loses UV names: rename by index
            o.data.uv_layers[int(meta["uv_index"])].name = uv_name
    return bind_objects(by_image, images, uv_name, bake_type, mode)


def step_apply_materials(ctx: PipelineContext) -> None:
    if not ctx.cfg.export.apply_lightmap_preview:
        log.info("Lightmap-Vorschau deaktiviert, Materialien bleiben unverändert")
        return
    by_image = {name: [bpy.data.objects[n] for n in names] for name, names in ctx.image_objects.items()}
    # mode None: a material that already shows "Nur Lightmap" or "Original" keeps that setting
    n = bind_objects(by_image, ctx.images, ctx.cfg.uv.uv_name, ctx.cfg.bake.type, None, warn=ctx.warn)
    ctx.extra["bound_materials"] = n
    log.info("Lightmap-Vorschau auf %d Material-Slots angewendet", n)
