# SPDX-License-Identifier: GPL-3.0-or-later
"""GUI smoke test: runs the modal *Bake & Export* operator in a real Blender window.

Usage (opens a Blender window that closes itself after the run)::

    blender.exe --factory-startup --python scripts/ui_smoke_test.py -- [--out DIR] [--keep-open]

Writes ``build/ui_smoke_report.json`` with the operator status, bound materials,
loaded images, output files and the viewport shading after the run.
Exit code 0 on success, 1 on failure (printed as ``[UI_SMOKE] RESULT ...``).
"""

import json
import os
import sys
import time
import traceback

import bpy

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT_DIR = os.path.join(REPO_ROOT, "build", "ui_smoke")
KEEP_OPEN = "--keep-open" in ARGS
if "--out" in ARGS:
    OUT_DIR = ARGS[ARGS.index("--out") + 1]
REPORT = os.path.join(REPO_ROOT, "build", "ui_smoke_report.json")
TIMEOUT = 240.0

R = {"log": [], "ok": False}
T0 = time.time()


def log(msg):
    R["log"].append(f"{time.time() - T0:5.1f}s {msg}")
    print("[UI_SMOKE]", msg, flush=True)


def finish():
    try:
        s = bpy.context.scene.blme
        from blender_lightmap_export.core import materials
        R.update(last_error=s.last_error, last_summary=s.last_summary, status=s.status_text,
                 last_warnings=s.last_warnings.splitlines())
        mats = {}
        for o in bpy.data.objects:
            if o.type != "MESH":
                continue
            for slot in o.material_slots:
                m = slot.material
                if m is None:
                    continue
                node = m.node_tree.nodes.get(materials.NODE_IMAGE)
                img = node.image if node else None
                mats[f"{o.name}/{m.name}"] = {
                    "bound": materials.is_bound(m),
                    "image": img.name if img else None,
                    "image_file_exists": bool(img and img.filepath and os.path.isfile(bpy.path.abspath(img.filepath))),
                    "image_size": list(img.size) if img else None,
                    "image_file": img.filepath if img else None,
                }
        R["materials"] = mats
        R["viewport_shading"] = [sp.shading.type for w in bpy.context.window_manager.windows
                                 for a in w.screen.areas if a.type == "VIEW_3D" for sp in a.spaces if sp.type == "VIEW_3D"]
        R["files"] = sorted(os.listdir(OUT_DIR)) if os.path.isdir(OUT_DIR) else []
        R["ok"] = (not s.last_error and not s.is_running and bool(mats) and all(v["bound"] and v["image_file_exists"] and v["image_size"] == [256, 256] for v in mats.values())
                   and "Scene.glb" in R["files"] and all(t == "MATERIAL" for t in R["viewport_shading"]))
    except Exception:
        R["finish_error"] = traceback.format_exc()
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(R, fh, indent=1, default=str)
    log(f"RESULT {'OK' if R['ok'] else 'FAILED'} -> {REPORT}")
    if not KEEP_OPEN:
        bpy.ops.wm.quit_blender()
    return None


def poll():
    s = bpy.context.scene.blme
    if s.is_running and time.time() - T0 < TIMEOUT:
        return 0.25
    log(f"operator finished: status={s.status_text!r} error={s.last_error!r}")
    finish()
    return None


def start():
    try:
        import blender_lightmap_export as pkg
        try:
            pkg.register()
        except ValueError:
            pass  # already registered (extension enabled)
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        from scripts import generate_test_scenes as gen
        objs = gen.multi_material()
        bpy.ops.object.select_all(action="SELECT")
        bpy.context.view_layer.objects.active = objs[0]
        s = bpy.context.scene.blme
        s.output_dir = OUT_DIR
        s.preset = "PREVIEW"
        s.resolution = "256"
        s.samples = 8
        s.denoise = False
        s.export_format = "GLB"
        s.export_scope = "SELECTED"
        win = bpy.context.window_manager.windows[0]
        area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
        region = next(r for r in area.regions if r.type == "WINDOW")
        R["viewport_shading_before"] = area.spaces[0].shading.type
        with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
            res = bpy.ops.blme.run("INVOKE_DEFAULT", mode="FULL")
        R["invoke_result"] = str(res)
        log(f"blme.run INVOKE_DEFAULT -> {res}")
        if "RUNNING_MODAL" not in res:
            finish()
            return None
        bpy.app.timers.register(poll, first_interval=0.5)
    except Exception:
        R["start_error"] = traceback.format_exc()
        log("start error:\n" + R["start_error"])
        finish()
    return None


if bpy.app.background:
    print("[UI_SMOKE] Dieses Skript braucht ein Blender-Fenster (ohne --background starten).")
    sys.exit(2)
bpy.app.timers.register(start, first_interval=1.5)
