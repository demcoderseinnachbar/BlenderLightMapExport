# SPDX-License-Identifier: GPL-3.0-or-later
"""Reproducible synthetic test geometry.

Usage inside Blender::

    blender.exe --background --factory-startup --python scripts/generate_test_scenes.py -- [--out DIR] [--scene NAME]

Without ``--scene`` every scene is generated and saved as ``<DIR>/<name>.blend``
(default ``build/synthetic``). The functions are also imported directly by the
test-suite.
"""

from __future__ import annotations

import math
import os
import sys
from typing import Dict, List

import bpy

SCENES: Dict[str, "callable"] = {}


def scene(name):
    def deco(func):
        SCENES[name] = func
        return func
    return deco


# --- helpers -------------------------------------------------------------------------

def reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.engine = "CYCLES"


def material(name: str, color=(0.8, 0.8, 0.8, 1.0), roughness: float = 0.6, emission: float = 0.0,
             texture: bpy.types.Image = None, uv_map: str = "") -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    if emission > 0:
        bsdf.inputs["Emission Color"].default_value = color
        bsdf.inputs["Emission Strength"].default_value = emission
    if texture is not None:
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = texture
        tex.location = (-400, 300)
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        if uv_map:
            uvn = mat.node_tree.nodes.new("ShaderNodeUVMap")
            uvn.uv_map = uv_map
            uvn.location = (-650, 300)
            mat.node_tree.links.new(uvn.outputs["UV"], tex.inputs["Vector"])
    return mat


def checker_image(name: str = "Checker", size: int = 64) -> bpy.types.Image:
    img = bpy.data.images.get(name)
    if img is None:
        img = bpy.data.images.new(name, size, size)
        img.generated_type = "COLOR_GRID"
    return img


def _add(primitive, name: str, mat: bpy.types.Material = None, **kw) -> bpy.types.Object:
    primitive(**kw)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    if mat is not None:
        obj.data.materials.append(mat)
    return obj


def sun(name: str = "Sun", energy: float = 3.0, rotation=(50, 0, 30)) -> bpy.types.Object:
    data = bpy.data.lights.new(name, "SUN")
    data.energy = energy
    obj = bpy.data.objects.new(name, data)
    obj.rotation_euler = [math.radians(v) for v in rotation]
    bpy.context.scene.collection.objects.link(obj)
    return obj


def point(name: str, location, energy: float = 500.0, color=(1, 1, 1)) -> bpy.types.Object:
    data = bpy.data.lights.new(name, "POINT")
    data.energy = energy
    data.color = color
    data.shadow_soft_size = 0.1
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)
    return obj


# --- scenes ----------------------------------------------------------------------------

@scene("cube")
def cube(with_light: bool = True) -> List[bpy.types.Object]:
    """Simple cube with one material on a ground plane."""
    objs = [_add(bpy.ops.mesh.primitive_cube_add, "Cube", material("MatCube", (0.8, 0.3, 0.2, 1)), size=1.0,
                 location=(0, 0, 0.5))]
    if with_light:
        sun()
    return objs


@scene("plane")
def plane(with_light: bool = True) -> List[bpy.types.Object]:
    """Single subdivided plane."""
    obj = _add(bpy.ops.mesh.primitive_grid_add, "Plane", material("MatPlane", (0.7, 0.7, 0.7, 1)),
               x_subdivisions=8, y_subdivisions=8, size=4.0)
    if with_light:
        sun()
        point("Point", (1.0, -1.0, 1.5), 200)
    return [obj]


@scene("room")
def room(with_light: bool = True) -> List[bpy.types.Object]:
    """Room: floor, ceiling and four walls as separate objects plus a point light."""
    s = 4.0
    h = 2.5
    mat_floor = material("MatFloor", (0.6, 0.5, 0.4, 1))
    mat_wall = material("MatWall", (0.85, 0.85, 0.8, 1))
    objs = [
        _add(bpy.ops.mesh.primitive_plane_add, "Floor", mat_floor, size=s, location=(0, 0, 0)),
        _add(bpy.ops.mesh.primitive_plane_add, "Ceiling", mat_wall, size=s, location=(0, 0, h),
             rotation=(math.pi, 0, 0)),
        _add(bpy.ops.mesh.primitive_plane_add, "WallNorth", mat_wall, size=s, location=(0, s / 2, h / 2),
             rotation=(math.pi / 2, 0, 0)),
        _add(bpy.ops.mesh.primitive_plane_add, "WallSouth", mat_wall, size=s, location=(0, -s / 2, h / 2),
             rotation=(-math.pi / 2, 0, 0)),
        _add(bpy.ops.mesh.primitive_plane_add, "WallEast", mat_wall, size=s, location=(s / 2, 0, h / 2),
             rotation=(0, -math.pi / 2, 0)),
        _add(bpy.ops.mesh.primitive_plane_add, "WallWest", mat_wall, size=s, location=(-s / 2, 0, h / 2),
             rotation=(0, math.pi / 2, 0)),
    ]
    for o in objs[2:]:
        o.scale = (1, h / s, 1)
    objs.append(_add(bpy.ops.mesh.primitive_cube_add, "Box", material("MatBox", (0.2, 0.4, 0.8, 1)), size=0.8,
                     location=(0.6, -0.4, 0.4)))
    if with_light:
        point("Lamp", (0, 0, h - 0.3), 300)
    return objs


@scene("row")
def row(with_light: bool = True) -> List[bpy.types.Object]:
    """Several objects next to each other (different sizes for texel density tests)."""
    objs = [
        _add(bpy.ops.mesh.primitive_cube_add, "RowCube", material("MatA", (0.9, 0.2, 0.2, 1)), size=1.0,
             location=(-2.0, 0, 0.5)),
        _add(bpy.ops.mesh.primitive_uv_sphere_add, "RowSphere", material("MatB", (0.2, 0.9, 0.2, 1)), radius=0.5,
             location=(0, 0, 0.5), segments=16, ring_count=8),
        _add(bpy.ops.mesh.primitive_cylinder_add, "RowCylinder", material("MatC", (0.2, 0.2, 0.9, 1)), radius=0.4,
             depth=1.0, location=(2.0, 0, 0.5), vertices=16),
        _add(bpy.ops.mesh.primitive_plane_add, "RowGround", material("MatGround", (0.5, 0.5, 0.5, 1)), size=8.0),
    ]
    if with_light:
        sun()
    return objs


@scene("multi_material")
def multi_material(with_light: bool = True) -> List[bpy.types.Object]:
    """Cube with three material slots assigned to different faces."""
    obj = _add(bpy.ops.mesh.primitive_cube_add, "MultiMat", None, size=1.0, location=(0, 0, 0.5))
    for name, col in (("MatRed", (0.8, 0.1, 0.1, 1)), ("MatGreen", (0.1, 0.8, 0.1, 1)), ("MatBlue", (0.1, 0.1, 0.8, 1))):
        obj.data.materials.append(material(name, col))
    for i, poly in enumerate(obj.data.polygons):
        poly.material_index = i % 3
    ground = _add(bpy.ops.mesh.primitive_plane_add, "MultiGround", material("MatGround", (0.5, 0.5, 0.5, 1)), size=4.0)
    if with_light:
        sun()
    return [obj, ground]


@scene("existing_uvs")
def existing_uvs(with_light: bool = True) -> List[bpy.types.Object]:
    """Cube with two UV layers and a textured material that uses the first one."""
    img = checker_image()
    obj = _add(bpy.ops.mesh.primitive_cube_add, "TexturedCube", None, size=1.0, location=(0, 0, 0.5))
    obj.data.uv_layers.new(name="Detail")
    obj.data.uv_layers.active = obj.data.uv_layers["UVMap"]
    obj.data.uv_layers["UVMap"].active_render = True
    obj.data.materials.append(material("MatTextured", texture=img, uv_map="UVMap"))
    if with_light:
        sun()
    return [obj]


@scene("no_uvs")
def no_uvs(with_light: bool = True) -> List[bpy.types.Object]:
    """Monkey without any UV layer and without material."""
    obj = _add(bpy.ops.mesh.primitive_monkey_add, "NoUV", None, size=1.5, location=(0, 0, 0.8))
    while obj.data.uv_layers:
        obj.data.uv_layers.remove(obj.data.uv_layers[0])
    if with_light:
        sun()
    return [obj]


@scene("multi_lights")
def multi_lights() -> List[bpy.types.Object]:
    """Room with several coloured light sources."""
    objs = room(with_light=False)
    point("RedLamp", (-1.2, 1.2, 2.0), 250, (1.0, 0.3, 0.3))
    point("BlueLamp", (1.2, -1.2, 2.0), 250, (0.3, 0.3, 1.0))
    spot_data = bpy.data.lights.new("Spot", "SPOT")
    spot_data.energy = 400
    spot_data.spot_size = math.radians(60)
    spot = bpy.data.objects.new("Spot", spot_data)
    spot.location = (0, 0, 2.3)
    bpy.context.scene.collection.objects.link(spot)
    area_data = bpy.data.lights.new("Area", "AREA")
    area_data.energy = 80
    area_data.size = 1.0
    area = bpy.data.objects.new("Area", area_data)
    area.location = (1.5, 1.5, 2.2)
    bpy.context.scene.collection.objects.link(area)
    return objs


@scene("shared_material")
def shared_material(with_light: bool = True) -> List[bpy.types.Object]:
    """Two separate objects that share one material (per-object lightmaps need copies)."""
    mat = material("MatShared", (0.7, 0.7, 0.3, 1))
    objs = [
        _add(bpy.ops.mesh.primitive_cube_add, "SharedA", mat, size=1.0, location=(-1, 0, 0.5)),
        _add(bpy.ops.mesh.primitive_cube_add, "SharedB", mat, size=1.0, location=(1, 0, 0.5)),
    ]
    if with_light:
        sun()
    return objs


@scene("instances")
def instances(with_light: bool = True) -> List[bpy.types.Object]:
    """Two objects sharing the same mesh datablock."""
    a = _add(bpy.ops.mesh.primitive_cube_add, "InstA", material("MatInst", (0.3, 0.7, 0.7, 1)), size=1.0,
             location=(-1, 0, 0.5))
    b = bpy.data.objects.new("InstB", a.data)
    b.location = (1.5, 0, 0.5)
    bpy.context.scene.collection.objects.link(b)
    if with_light:
        sun()
    return [a, b]


def build(name: str, **kw) -> List[bpy.types.Object]:
    if name not in SCENES:
        raise KeyError(f"Unbekannte Testszene '{name}', verfügbar: {', '.join(SCENES)}")
    return SCENES[name](**kw)


def main(argv: List[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="generate_test_scenes.py")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                      "build", "synthetic"))
    parser.add_argument("--scene", default="")
    args = parser.parse_args(argv)
    names = [args.scene] if args.scene else list(SCENES)
    os.makedirs(args.out, exist_ok=True)
    for name in names:
        reset()
        build(name)
        path = os.path.join(args.out, f"{name}.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        print(f"[generate_test_scenes] {name}: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []))
