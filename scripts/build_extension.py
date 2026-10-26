# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the installable extension ZIP and (optionally) verify it installs.

Usage::

    blender.exe --command extension build --source-dir blender_lightmap_export --output-dir build
    blender.exe --background --python scripts/build_extension.py -- [--verify] [--out DIR]

``--verify`` installs the ZIP into the user extension repository, enables it,
checks that the UI classes are registered and removes it again.
"""

from __future__ import annotations

import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SOURCE_DIR = os.path.join(REPO_ROOT, "blender_lightmap_export")
EXT_ID = "blender_lightmap_export"


def build(out_dir: str) -> str:
    import bpy
    os.makedirs(out_dir, exist_ok=True)
    cmd = [bpy.app.binary_path, "--command", "extension", "build", "--source-dir", SOURCE_DIR,
           "--output-dir", out_dir]
    print("[build_extension]", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print(res.stderr)
        raise SystemExit(f"Extension build fehlgeschlagen (Exit {res.returncode})")
    zips = sorted((f for f in os.listdir(out_dir) if f.startswith(EXT_ID) and f.endswith(".zip")),
                  key=lambda f: os.path.getmtime(os.path.join(out_dir, f)))
    if not zips:
        raise SystemExit("Keine ZIP-Datei erzeugt")
    return os.path.join(out_dir, zips[-1])


def verify(zip_path: str) -> None:
    import bpy
    module = f"bl_ext.user_default.{EXT_ID}"
    print("[build_extension] installiere", zip_path)
    bpy.ops.extensions.package_install_files(filepath=zip_path, repo="user_default", enable_on_install=True)
    import addon_utils
    enabled = any(m.__name__ == module for m in addon_utils.modules() if addon_utils.check(m.__name__)[1])
    try:
        if module not in sys.modules:
            bpy.ops.preferences.addon_enable(module=module)
        assert module in sys.modules, "Extension-Modul wurde nicht geladen"
        assert hasattr(bpy.types, "BLME_PT_main"), "Panel nicht registriert"
        assert hasattr(bpy.ops.blme, "run"), "Operator nicht registriert"
        assert hasattr(bpy.types.Scene, "blme"), "Scene-Properties nicht registriert"
        mod = sys.modules[module]
        assert hasattr(mod, "glTF2ImportUserExtension"), "glTF-Import-Hook fehlt"
        prefs = bpy.context.preferences.addons.get(module)
        assert prefs is not None and prefs.preferences is not None, "Preferences nicht verfügbar"
        print("[build_extension] Extension geladen als", module, "(enabled:", enabled, ")")
    finally:
        uninstall()
    assert not hasattr(bpy.types, "BLME_PT_main"), "Panel nach Deaktivierung noch registriert"
    print("[build_extension] Verifikation erfolgreich, Extension wieder entfernt")


def uninstall() -> None:
    import bpy
    module = f"bl_ext.user_default.{EXT_ID}"
    try:
        bpy.ops.preferences.addon_disable(module=module)
    except Exception as exc:
        print("[build_extension] addon_disable:", exc)
    try:
        bpy.ops.extensions.package_uninstall(repo_index=_repo_index("user_default"), pkg_id=EXT_ID)
    except Exception as exc:
        print("[build_extension] package_uninstall:", exc)


def _repo_index(module: str) -> int:
    import bpy
    for i, r in enumerate(bpy.context.preferences.extensions.repos):
        if r.module == module:
            return i
    raise SystemExit(f"Extension-Repository '{module}' nicht gefunden")


def main(argv):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(REPO_ROOT, "build"))
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    zip_path = build(args.out)
    print("[build_extension] ZIP:", zip_path)
    if args.verify:
        verify(zip_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []))
