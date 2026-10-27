# SPDX-License-Identifier: MIT
"""Light analysis and the temporary default light rig."""

from __future__ import annotations

import math
from typing import Dict, List

import bpy

from .log import get_logger
from .pipeline import PipelineContext

log = get_logger("lighting")

RIG_COLLECTION = "BLME_TempLights"
RIG_WORLD = "BLME_TempWorld"


def world_emits_light(world: bpy.types.World) -> bool:
    if world is None:
        return False
    if world.use_nodes and world.node_tree:
        for node in world.node_tree.nodes:
            if node.bl_idname == "ShaderNodeBackground":
                strength = node.inputs["Strength"].default_value
                color_linked = node.inputs["Color"].is_linked
                color = node.inputs["Color"].default_value
                if node.inputs["Strength"].is_linked:
                    return True
                if strength > 0 and (color_linked or max(color[:3]) > 0.0):
                    # only counts if the background is connected to the output
                    return any(l.to_node.bl_idname == "ShaderNodeOutputWorld" for l in node.outputs[0].links)
        return False
    return max(world.color[:3]) > 0.0


def analyze(scene: bpy.types.Scene, view_layer: bpy.types.ViewLayer) -> Dict[str, object]:
    lights = [o for o in view_layer.objects if o.type == "LIGHT" and not o.hide_render]
    emissive_mats = 0
    for m in bpy.data.materials:
        if m.use_nodes and m.node_tree:
            for n in m.node_tree.nodes:
                if n.bl_idname == "ShaderNodeEmission" and n.inputs["Strength"].default_value > 0:
                    emissive_mats += 1
                    break
    return {
        "lights": [o.name for o in lights],
        "world_emits": world_emits_light(scene.world),
        "emissive_materials": emissive_mats,
    }


def create_default_rig(ctx: PipelineContext) -> List[bpy.types.Object]:
    """Create sun + sky world in a temporary collection (removed after the run)."""
    cfg = ctx.cfg.lighting
    scene = ctx.scene
    coll = bpy.data.collections.new(RIG_COLLECTION)
    scene.collection.children.link(coll)
    ctx.temp.add_collection(coll)

    sun_data = bpy.data.lights.new("BLME_Sun", type="SUN")
    sun_data.energy = cfg.sun_energy
    sun_data.angle = math.radians(2.0)
    sun = bpy.data.objects.new("BLME_Sun", sun_data)
    sun.rotation_euler = [math.radians(v) for v in cfg.sun_rotation_deg]
    coll.objects.link(sun)
    ctx.temp.add_light_data(sun_data)

    world = bpy.data.worlds.new(RIG_WORLD)
    world.use_nodes = True
    bg = next((n for n in world.node_tree.nodes if n.bl_idname == "ShaderNodeBackground"), None)
    if bg is not None:
        bg.inputs["Color"].default_value = (*cfg.world_color[:3], 1.0)
        bg.inputs["Strength"].default_value = cfg.world_strength
    ctx.temp.add_world(world)
    scene.world = world  # restored by the scene snapshot
    log.info("Temporäres Licht-Setup erzeugt (Sonne %.1f, Himmel %.2f)", cfg.sun_energy, cfg.world_strength)
    return [sun]


def step_prepare_lighting(ctx: PipelineContext) -> None:
    mode = ctx.cfg.lighting.mode
    info = analyze(ctx.scene, ctx.view_layer)
    has_light = bool(info["lights"]) or bool(info["world_emits"]) or info["emissive_materials"] > 0
    ctx.extra["lighting"] = info
    if ctx.cfg.bake.type == "AO":
        log.info("AO-Bake: Lichtquellen werden nicht benötigt")
        return
    if mode == "SCENE":
        if not has_light:
            ctx.warn("Die Szene enthält keine Lichtquellen und keine Welt-Emission, die Lightmap wird dunkel")
        return
    if mode == "AUTO":
        if has_light:
            log.info("Vorhandene Beleuchtung wird verwendet: %d Lichter, Welt=%s",
                     len(info["lights"]), info["world_emits"])
            return
        log.info("Keine Lichtquellen gefunden, Standard-Licht-Setup wird erzeugt")
        create_default_rig(ctx)
        return
    if mode == "DEFAULT_RIG":
        for name in info["lights"]:
            o = bpy.data.objects.get(name)
            if o is not None:
                o.hide_render = True   # restored by the snapshot
        create_default_rig(ctx)
