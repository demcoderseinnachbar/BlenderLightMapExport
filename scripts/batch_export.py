# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless batch export (single file or whole folder).

Usage::

    blender.exe --background --python scripts/batch_export.py -- --input <file|dir> --output <dir>
                [--config config.json] [--format GLB] [--preset HIGH] [--recursive]
                [--set bake.samples=32 --set uv.island_margin_px=4 ...] [--continue-on-error]
                [--log export.log] [--report export_report.json]

Exit codes:
    0  all files processed successfully
    1  at least one file failed (others may have succeeded)
    2  configuration / argument error
    3  environment error (Blender, input path not found)

The script uses exactly the same core pipeline as the add-on UI and the Python
API (``blender_lightmap_export.api``). Every input file is processed in a fresh
empty scene so one broken model cannot influence the next one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

EXIT_OK, EXIT_FAILED, EXIT_CONFIG, EXIT_ENV = 0, 1, 2, 3


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="batch_export.py", description="BlenderLightMapExport Batch")
    parser.add_argument("paths", nargs="*", help="[Eingabe] [Ausgabeordner] (Alternative zu --input/--output)")
    parser.add_argument("--input", "-i", required=False, help="Eingabedatei oder Ordner")
    parser.add_argument("--output", "-o", required=False, help="Ausgabeordner")
    parser.add_argument("--config", "-c", default="", help="JSON-Konfiguration (config.example.json als Vorlage)")
    parser.add_argument("--format", "-f", default="", help="Exportformat (GLB, GLTF, FBX, USD, OBJ, NONE)")
    parser.add_argument("--preset", "-p", default="", help="Qualitäts-Preset (PREVIEW, MEDIUM, HIGH, PRODUCTION)")
    parser.add_argument("--set", dest="overrides", action="append", default=[],
                        help="Einzelwert überschreiben, z. B. --set bake.samples=32")
    parser.add_argument("--recursive", "-r", action="store_true", help="Unterordner einbeziehen")
    parser.add_argument("--continue-on-error", action="store_true", default=True)
    parser.add_argument("--stop-on-error", dest="continue_on_error", action="store_false")
    parser.add_argument("--per-file-subdir", action="store_true",
                        help="Pro Eingabedatei einen eigenen Unterordner im Ausgabeordner anlegen")
    parser.add_argument("--log", default="", help="Logdatei (Standard: <output>/export.log)")
    parser.add_argument("--report", default="", help="JSON-Bericht (Standard: <output>/export_report.json)")
    parser.add_argument("--dry-run", action="store_true", help="Nur Dateien auflisten")
    args = parser.parse_args(argv)
    if args.paths:
        if not args.input:
            args.input = args.paths[0]
        if len(args.paths) > 1 and not args.output:
            args.output = args.paths[1]
    return args


def _coerce(value: str):
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def build_config(args):
    from blender_lightmap_export.config import ExportConfig, ConfigError, apply_preset
    if args.config:
        cfg = ExportConfig.load(args.config)
    else:
        cfg = ExportConfig()
    if args.output:
        cfg.output_dir = args.output
    if args.input:
        cfg.input_file = args.input
    if args.format:
        cfg.export.format = args.format.upper()
    if args.preset:
        apply_preset(cfg, args.preset)
    for item in args.overrides:
        if "=" not in item:
            raise ConfigError(f"--set erwartet schlüssel=wert, erhalten: {item}")
        key, value = item.split("=", 1)
        target = cfg
        parts = key.strip().split(".")
        for part in parts[:-1]:
            if not hasattr(target, part):
                raise ConfigError(f"Unbekannter Konfigurationsschlüssel: {key}")
            target = getattr(target, part)
        if not hasattr(target, parts[-1]):
            raise ConfigError(f"Unbekannter Konfigurationsschlüssel: {key}")
        setattr(target, parts[-1], _coerce(value.strip()))
    if not cfg.output_dir:
        raise ConfigError("Ausgabeordner fehlt (--output oder output_dir in der Konfiguration)")
    if not cfg.input_file:
        raise ConfigError("Eingabe fehlt (--input oder input_file in der Konfiguration)")
    cfg.validate_or_raise()
    return cfg


def collect_inputs(path: str, recursive: bool):
    from blender_lightmap_export.config import SUPPORTED_INPUT_EXTENSIONS
    path = os.path.abspath(path)
    if os.path.isfile(path):
        return [path], []
    if not os.path.isdir(path):
        return [], []
    files, skipped = [], []
    walker = os.walk(path) if recursive else [(path, [], os.listdir(path))]
    for root, _dirs, names in walker:
        for name in sorted(names):
            full = os.path.join(root, name)
            if not os.path.isfile(full):
                continue
            if name.lower().endswith(SUPPORTED_INPUT_EXTENSIONS) and not name.lower().endswith(".lightmaps.json"):
                files.append(full)
            else:
                skipped.append(full)
    return files, skipped


def process_file(cfg, input_file: str, output_dir: str, log):
    import bpy
    from blender_lightmap_export import api
    from blender_lightmap_export.core.pipeline import LightmapExportError
    file_cfg = cfg.copy()
    file_cfg.input_file = input_file
    file_cfg.output_dir = output_dir
    bpy.ops.wm.read_factory_settings(use_empty=True)
    entry = {"input": input_file, "output_dir": output_dir, "success": False, "error": "", "warnings": [],
             "lightmaps": [], "exported_files": [], "seconds": 0.0}
    t0 = time.perf_counter()
    try:
        result = api.run_pipeline(file_cfg, progress=lambda f, m: log.info("  %3d %% %s", int(f * 100), m))
        entry.update(success=result.success, warnings=result.warnings,
                     lightmaps=[lm.file_path for lm in result.lightmaps], exported_files=result.exported_files,
                     device=result.device_used)
    except LightmapExportError as exc:
        entry["error"] = str(exc)
    except Exception as exc:  # pragma: no cover
        entry["error"] = f"Unerwarteter Fehler: {exc}"
        log.error(traceback.format_exc())
    entry["seconds"] = round(time.perf_counter() - t0, 2)
    return entry


def main(argv) -> int:
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return EXIT_CONFIG if exc.code else EXIT_OK
    try:
        import bpy  # noqa: F401
    except ImportError:
        print("batch_export.py muss innerhalb von Blender laufen: blender.exe --background --python scripts/batch_export.py -- ...")
        return EXIT_ENV
    from blender_lightmap_export.config import ConfigError
    from blender_lightmap_export.core import log as logmod

    try:
        cfg = build_config(args)
    except ConfigError as exc:
        print(f"[batch_export] Konfigurationsfehler: {exc}")
        return EXIT_CONFIG

    output_dir = os.path.abspath(cfg.output_dir)
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as exc:
        print(f"[batch_export] Ausgabeordner kann nicht angelegt werden: {exc}")
        return EXIT_ENV
    log_path = args.log or os.path.join(output_dir, "export.log")
    report_path = args.report or os.path.join(output_dir, "export_report.json")
    logmod.set_level(cfg.log_level)
    log = logmod.get_logger("batch")
    handler = logmod.add_file_handler(log_path)

    files, skipped = collect_inputs(cfg.input_file, args.recursive)
    if not os.path.exists(cfg.input_file):
        log.error("Eingabe nicht gefunden: %s", cfg.input_file)
        logmod.remove_handler(handler)
        return EXIT_ENV
    if not files:
        log.error("Keine unterstützten Eingabedateien in %s (übersprungen: %d)", cfg.input_file, len(skipped))
        logmod.remove_handler(handler)
        return EXIT_CONFIG
    for s in skipped:
        log.warning("Nicht unterstützt, übersprungen: %s", s)
    log.info("Verarbeite %d Datei(en) -> %s (Format %s)", len(files), output_dir, cfg.export.format)
    if args.dry_run:
        for f in files:
            log.info("  %s", f)
        logmod.remove_handler(handler)
        return EXIT_OK

    import bpy
    entries = []
    t_all = time.perf_counter()
    for i, f in enumerate(files, 1):
        log.info("=== [%d/%d] %s", i, len(files), f)
        target_dir = output_dir
        if args.per_file_subdir or (os.path.isdir(cfg.input_file) and len(files) > 1):
            target_dir = os.path.join(output_dir, os.path.splitext(os.path.basename(f))[0])
        entry = process_file(cfg, f, target_dir, log)
        entries.append(entry)
        if entry["success"]:
            log.info("OK  %s (%.1f s, %d Lightmaps, %d Dateien)", os.path.basename(f), entry["seconds"],
                     len(entry["lightmaps"]), len(entry["exported_files"]))
        else:
            log.error("FEHLER %s: %s", os.path.basename(f), entry["error"])
            if not args.continue_on_error:
                log.error("Abbruch nach erstem Fehler (--stop-on-error)")
                break
    ok = [e for e in entries if e["success"]]
    failed = [e for e in entries if not e["success"]]
    report = {
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "blender": bpy.app.version_string,
        "input": os.path.abspath(cfg.input_file),
        "output_dir": output_dir,
        "config": cfg.to_dict(),
        "total": len(entries), "succeeded": len(ok), "failed": len(failed),
        "skipped_unsupported": skipped,
        "seconds": round(time.perf_counter() - t_all, 2),
        "files": entries,
    }
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    log.info("=== Zusammenfassung: %d erfolgreich, %d fehlgeschlagen, %d nicht unterstützt (%.1f s)",
             len(ok), len(failed), len(skipped), report["seconds"])
    for e in failed:
        log.info("  FEHLER %s: %s", os.path.basename(e["input"]), e["error"])
    log.info("Bericht: %s", report_path)
    logmod.remove_handler(handler)
    return EXIT_OK if not failed else EXIT_FAILED


if __name__ == "__main__":
    code = main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    sys.exit(code)
