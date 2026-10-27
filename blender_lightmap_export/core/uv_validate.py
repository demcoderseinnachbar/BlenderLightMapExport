# SPDX-License-Identifier: MIT
"""Raster based UV layout validation (overlaps, bounds, NaN, island spacing).

The layout is rasterised into a ``resolution x resolution`` grid. A pixel is
counted for a triangle only when its centre is strictly inside the triangle,
so pixels on shared edges of adjacent triangles are not counted twice and
every double count is a real overlap.

Island spacing is checked on an island-id raster: if two different island ids
occur within ``min_spacing_px`` of each other, the spacing is reported.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np

import bpy

from .log import get_logger

log = get_logger("uv_validate")


def _mesh_uv_triangles(mesh: bpy.types.Mesh, uv_name: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (uv per loop [n,2], triangle loop indices [m,3], position id per loop [n]).

    The position id merges vertices that sit at the same 3D location, so meshes
    with split vertices (typical after glTF/FBX import) are treated like
    connected geometry.
    """
    layer = mesh.uv_layers[uv_name]
    n = len(mesh.loops)
    uv = np.empty(n * 2, dtype=np.float64)
    layer.uv.foreach_get("vector", uv)
    uv = uv.reshape(n, 2)
    mesh.calc_loop_triangles()
    tris = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get("loops", tris)
    loop_verts = np.empty(n, dtype=np.int64)
    mesh.loops.foreach_get("vertex_index", loop_verts)
    co = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
    mesh.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    extent = float(np.abs(co).max()) if len(co) else 1.0
    quant = max(extent, 1e-6) * 1e-6
    pos_ids = np.unique(np.round(co / quant).astype(np.int64), axis=0, return_inverse=True)[1].ravel()
    return uv, tris.reshape(-1, 3), pos_ids[loop_verts]


def _island_ids(uv: np.ndarray, tris: np.ndarray, loop_verts: np.ndarray, quant: float = 1e-5) -> np.ndarray:
    """Union-find island id per triangle.

    Two triangles belong to the same island when they share a mesh edge *and*
    the UV coordinates of that edge are identical on both sides (no UV seam).
    Islands that merely touch in UV space therefore stay separate.
    """
    m = len(tris)
    if m == 0:
        return np.zeros(0, dtype=np.int64)
    q = np.round(uv / quant).astype(np.int64)
    edges = np.stack([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]], axis=1).reshape(-1, 2)  # [3m,2] loops
    va = loop_verts[edges[:, 0]]
    vb = loop_verts[edges[:, 1]]
    swap = va > vb
    lo = np.where(swap, edges[:, 1], edges[:, 0])
    hi = np.where(swap, edges[:, 0], edges[:, 1])
    keys = np.column_stack([loop_verts[lo], loop_verts[hi], q[lo], q[hi]])
    _, inverse = np.unique(keys, axis=0, return_inverse=True)
    inverse = inverse.ravel()
    tri_of_edge = np.repeat(np.arange(m), 3)
    parent = np.arange(m)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    order = np.argsort(inverse, kind="stable")
    sorted_keys = inverse[order]
    sorted_tris = tri_of_edge[order]
    start = 0
    n_edges = len(sorted_keys)
    while start < n_edges:
        end = start + 1
        while end < n_edges and sorted_keys[end] == sorted_keys[start]:
            end += 1
        if end - start > 1:
            root = find(sorted_tris[start])
            for i in range(start + 1, end):
                r = find(sorted_tris[i])
                if r != root:
                    parent[r] = root
        start = end
    roots = np.array([find(i) for i in range(m)], dtype=np.int64)
    _, island = np.unique(roots, return_inverse=True)
    return island.ravel() + 1  # 0 is reserved for "empty"


def validate_layout(meshes: Sequence[Tuple[bpy.types.Mesh, str]], resolution: int = 1024,
                    min_spacing_px: float = 1.0, check_spacing: bool = True) -> Dict[str, object]:
    res = int(max(16, min(resolution, 4096)))
    count = np.zeros((res, res), dtype=np.int32)
    ids = np.zeros((res, res), dtype=np.int32)
    report: Dict[str, object] = {
        "resolution": res, "triangles": 0, "islands": 0, "invalid": 0,
        "out_of_bounds_loops": 0, "covered_pixels": 0, "overlap_pixels": 0,
        "overlap_fraction": 0.0, "spacing_violation_pixels": 0, "min_spacing_px": min_spacing_px,
        "coverage_fraction": 0.0, "objects": [],
    }
    island_offset = 0
    for mesh, uv_name in meshes:
        if uv_name not in mesh.uv_layers:
            report["objects"].append({"mesh": mesh.name, "error": f"UV-Layer {uv_name} fehlt"})
            continue
        uv, tris, loop_verts = _mesh_uv_triangles(mesh, uv_name)
        bad = ~np.isfinite(uv)
        n_bad = int(bad.any(axis=1).sum())
        report["invalid"] += n_bad
        if n_bad:
            uv = np.where(bad, 0.0, uv)
        oob = ((uv < -1e-4) | (uv > 1.0 + 1e-4)).any(axis=1)
        report["out_of_bounds_loops"] += int(oob.sum())
        report["triangles"] += int(len(tris))
        if len(tris) == 0:
            continue
        islands = _island_ids(uv, tris, loop_verts) + island_offset
        island_offset = int(islands.max())
        _rasterize(uv, tris, islands, res, count, ids)
        report["objects"].append({"mesh": mesh.name, "triangles": int(len(tris)),
                                  "islands": int(len(np.unique(islands)))})
    report["islands"] = island_offset
    covered = int((count > 0).sum())
    overlap = int((count > 1).sum())
    report["covered_pixels"] = covered
    report["overlap_pixels"] = overlap
    report["overlap_fraction"] = (overlap / covered) if covered else 0.0
    report["coverage_fraction"] = covered / float(res * res)
    if check_spacing and min_spacing_px > 0 and island_offset > 1:
        report["spacing_violation_pixels"] = _spacing_violations(ids, min_spacing_px)
    return report


def _rasterize(uv: np.ndarray, tris: np.ndarray, islands: np.ndarray, res: int,
               count: np.ndarray, ids: np.ndarray) -> None:
    p = uv[tris] * res  # [m,3,2] in pixel space
    mins = np.floor(p.min(axis=1)).astype(np.int64)
    maxs = np.ceil(p.max(axis=1)).astype(np.int64)
    for i in range(len(tris)):
        x0, y0 = max(mins[i, 0], 0), max(mins[i, 1], 0)
        x1, y1 = min(maxs[i, 0], res - 1), min(maxs[i, 1], res - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs = np.arange(x0, x1 + 1) + 0.5
        ys = np.arange(y0, y1 + 1) + 0.5
        gx, gy = np.meshgrid(xs, ys)
        (ax, ay), (bx, by), (cx, cy) = p[i]
        det = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
        if abs(det) < 1e-12:
            continue
        w0 = ((bx - gx) * (cy - gy) - (cx - gx) * (by - gy)) / det
        w1 = ((cx - gx) * (ay - gy) - (ax - gx) * (cy - gy)) / det
        w2 = 1.0 - w0 - w1
        eps = 1e-9
        inside = (w0 > eps) & (w1 > eps) & (w2 > eps)
        if not inside.any():
            continue
        sub_c = count[y0:y1 + 1, x0:x1 + 1]
        sub_i = ids[y0:y1 + 1, x0:x1 + 1]
        sub_c[inside] += 1
        sub_i[inside] = islands[i]


def _spacing_violations(ids: np.ndarray, min_spacing_px: float) -> int:
    k = int(np.ceil(min_spacing_px))
    if k <= 0:
        return 0
    violations = np.zeros(ids.shape, dtype=bool)
    nz = ids > 0
    h, w = ids.shape
    for dy in range(-k, k + 1):
        for dx in range(-k, k + 1):
            if dx == 0 and dy == 0:
                continue
            if dx * dx + dy * dy > k * k + 1e-6:
                continue
            ys = slice(max(0, dy), h + min(0, dy))
            xs = slice(max(0, dx), w + min(0, dx))
            ys2 = slice(max(0, -dy), h + min(0, -dy))
            xs2 = slice(max(0, -dx), w + min(0, -dx))
            a = ids[ys, xs]
            b = ids[ys2, xs2]
            diff = (a != b) & (a > 0) & (b > 0)
            violations[ys, xs] |= diff
    return int((violations & nz).sum())


def report_warnings(label: str, report: Dict[str, object]) -> List[str]:
    warnings: List[str] = []
    covered = int(report["covered_pixels"]) or 1
    if report["invalid"]:
        warnings.append(f"UVs '{label}': {report['invalid']} ungültige (NaN/Inf) UV-Koordinaten")
    if report["out_of_bounds_loops"]:
        warnings.append(f"UVs '{label}': {report['out_of_bounds_loops']} UV-Ecken liegen außerhalb von 0..1")
    threshold = max(4, int(0.001 * covered))
    if int(report["overlap_pixels"]) > threshold:
        warnings.append(f"UVs '{label}': {report['overlap_pixels']} Pixel überlappen "
                        f"({report['overlap_fraction'] * 100:.2f} % der belegten Fläche)")
    if int(report["spacing_violation_pixels"]) > threshold:
        warnings.append(f"UVs '{label}': UV-Inseln liegen näher als {report['min_spacing_px']} px "
                        f"beieinander ({report['spacing_violation_pixels']} Pixel betroffen)")
    return warnings
