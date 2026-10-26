# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate the Utah Teapot mesh from the original Bezier patch data.

Source data: ``examples/teapot/teapot_bezier.txt`` – the original non-rational
Bezier teapot (28 bicubic patches, Martin Newell / Jim Blinn), as distributed
by the University of Utah (file by Thomas V. Thompson II, 2000).

Usage inside Blender::

    blender.exe --background --factory-startup --python scripts/generate_teapot.py -- [--subdiv 12] [--out examples/teapot/utah_teapot.glb]

The tessellation is deterministic: every patch is evaluated on a
``subdiv x subdiv`` grid, patches are welded, normals recalculated and the
model is rotated to Blender's Z-up convention and scaled to about 2 m.
"""

from __future__ import annotations

import math
import os
import re
import sys
from typing import List, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DATA_FILE = os.path.join(REPO_ROOT, "examples", "teapot", "teapot_bezier.txt")
DEFAULT_OUT = os.path.join(REPO_ROOT, "examples", "teapot", "utah_teapot.glb")

_PT = re.compile(r"pt\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\)")


def parse_patches(path: str) -> List[List[Tuple[float, float, float]]]:
    text = open(path, encoding="utf-8").read()
    patches = []
    for block in text.split("surface(")[1:]:
        pts = [(float(x), float(y), float(z)) for x, y, z in _PT.findall(block)]
        if len(pts) != 16:
            raise ValueError(f"Patch mit {len(pts)} statt 16 Kontrollpunkten")
        patches.append(pts)
    if not patches:
        raise ValueError(f"Keine Patches in {path}")
    return patches


def _bernstein(t: float):
    s = 1.0 - t
    return (s * s * s, 3 * t * s * s, 3 * t * t * s, t * t * t)


def evaluate_patch(ctrl, u: float, v: float):
    bu = _bernstein(u)
    bv = _bernstein(v)
    x = y = z = 0.0
    for i in range(4):
        for j in range(4):
            w = bu[i] * bv[j]
            px, py, pz = ctrl[i * 4 + j]
            x += w * px
            y += w * py
            z += w * pz
    return x, y, z


def tessellate(patches, subdiv: int):
    verts = []
    faces = []
    n = subdiv + 1
    for ctrl in patches:
        base = len(verts)
        for i in range(n):
            u = i / subdiv
            for j in range(n):
                v = j / subdiv
                verts.append(evaluate_patch(ctrl, u, v))
        for i in range(subdiv):
            for j in range(subdiv):
                a = base + i * n + j
                faces.append((a, a + 1, a + n + 1, a + n))
    return verts, faces


def build_object(subdiv: int = 12, name: str = "UtahTeapot"):
    import bpy
    import bmesh
    patches = parse_patches(DATA_FILE)
    verts, faces = tessellate(patches, subdiv)
    mesh = bpy.data.meshes.new(name)
    # original data is Y-up; convert to Z-up and scale: the teapot is ~3.15 units tall
    scale = 2.0 / 3.15
    converted = [(x * scale, -z * scale, y * scale) for x, y, z in verts]
    mesh.from_pydata(converted, [], faces)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    # drop degenerate faces (patch seams collapse to lines at the poles)
    degenerate = [f for f in bm.faces if f.calc_area() < 1e-10]
    if degenerate:
        bmesh.ops.delete(bm, geom=degenerate, context="FACES")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    mesh.validate()
    for p in mesh.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.new("TeapotCeramic")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.85, 0.82, 0.75, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.35
    mesh.materials.append(mat)
    return obj


def main(argv) -> int:
    import argparse
    import bpy
    parser = argparse.ArgumentParser()
    parser.add_argument("--subdiv", type=int, default=12)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--blend", default="", help="Zusätzlich als .blend speichern")
    args = parser.parse_args(argv)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj = build_object(args.subdiv)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=args.out, export_format="GLB", use_selection=True, export_apply=True)
    print(f"[generate_teapot] {len(obj.data.vertices)} Vertices, {len(obj.data.polygons)} Flächen -> {args.out}")
    if args.blend:
        bpy.ops.wm.save_as_mainfile(filepath=args.blend)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []))
