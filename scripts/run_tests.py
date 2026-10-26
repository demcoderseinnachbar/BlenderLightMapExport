# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the unittest suite inside Blender.

Usage::

    blender.exe --background --factory-startup --python scripts/run_tests.py -- [options]

Options:
    -k PATTERN      only run tests whose id contains PATTERN (repeatable)
    --no-gpu        skip tests marked @requires_gpu
    --no-slow       skip tests marked @slow
    --no-models     skip tests that need the example models
    --report PATH   write a JSON report (default: build/test_report.json)
    --md PATH       write a Markdown report (default: docs/test_report.md)
    --verbose       verbose unittest output

Exit code: 0 all tests passed, 1 failures/errors, 2 setup problem.
"""

import argparse
import json
import os
import sys
import time
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="run_tests.py")
    parser.add_argument("-k", dest="patterns", action="append", default=[])
    parser.add_argument("--no-gpu", action="store_true")
    parser.add_argument("--no-slow", action="store_true")
    parser.add_argument("--no-models", action="store_true")
    parser.add_argument("--report", default=os.path.join(REPO_ROOT, "build", "test_report.json"))
    parser.add_argument("--md", default=os.path.join(REPO_ROOT, "docs", "test_report.md"))
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
        self._start = {}

    def startTest(self, test):
        self._start[test.id()] = time.perf_counter()
        super().startTest(test)

    def _record(self, test, status, detail=""):
        self.records.append({
            "id": test.id(),
            "status": status,
            "seconds": round(time.perf_counter() - self._start.get(test.id(), time.perf_counter()), 3),
            "detail": detail,
            "doc": (test.shortDescription() or ""),
        })

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "failed", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "error", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skipped", reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._record(test, "expected_failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._record(test, "unexpected_success")


def write_markdown(path, records, meta):
    import collections
    by_module = collections.OrderedDict()
    for r in records:
        mod = r["id"].split(".")[0] if "." in r["id"] else r["id"]
        by_module.setdefault(mod, []).append(r)
    counts = collections.Counter(r["status"] for r in records)
    lines = ["# Testbericht", "",
             f"Erzeugt: {meta['date']}  ", f"Blender: {meta['blender']}  ", f"Gerät: {meta['device']}  ",
             f"Optionen: {meta['options']}", "",
             "| Status | Anzahl |", "|---|---|"]
    for k in ("passed", "failed", "error", "skipped", "expected_failure", "unexpected_success"):
        if counts.get(k):
            lines.append(f"| {k} | {counts[k]} |")
    lines += ["", "Status-Bedeutung: `passed` = automatisch ausgeführt und bestanden, `skipped` = implementiert, "
                  "aber in diesem Lauf nicht ausgeführt (Grund in der Tabelle), `failed`/`error` = ausgeführt und fehlgeschlagen.", ""]
    for mod, recs in by_module.items():
        lines += [f"## {mod}", "", "| Test | Status | Sekunden | Hinweis |", "|---|---|---|---|"]
        for r in recs:
            name = r["id"].split(".", 1)[1] if "." in r["id"] else r["id"]
            detail = (r["detail"] or "").strip().splitlines()
            hint = detail[-1][:140] if detail else ""
            hint = hint.replace("|", "\\|")
            lines.append(f"| `{name}` | {r['status']} | {r['seconds']} | {hint} |")
        lines.append("")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parse_args(argv)
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    os.environ["BLME_TEST_NO_GPU"] = "1" if args.no_gpu else ""
    os.environ["BLME_TEST_NO_SLOW"] = "1" if args.no_slow else ""
    os.environ["BLME_TEST_NO_MODELS"] = "1" if args.no_models else ""

    try:
        import bpy  # noqa: F401
    except ImportError:
        print("Dieses Skript muss innerhalb von Blender ausgeführt werden.")
        sys.exit(2)

    loader = unittest.TestLoader()
    suite = loader.discover(os.path.join(REPO_ROOT, "tests"), pattern="test_*.py", top_level_dir=REPO_ROOT)

    if args.patterns:
        def _filter(s):
            out = unittest.TestSuite()
            for t in s:
                if isinstance(t, unittest.TestSuite):
                    out.addTest(_filter(t))
                elif any(p in t.id() for p in args.patterns):
                    out.addTest(t)
            return out
        suite = _filter(suite)

    runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1, resultclass=RecordingResult, stream=sys.stdout)
    t0 = time.perf_counter()
    result = runner.run(suite)
    elapsed = time.perf_counter() - t0

    import bpy
    try:
        from blender_lightmap_export.core import baking
        device = baking.describe_devices()
    except Exception as exc:  # pragma: no cover
        device = f"unbekannt ({exc})"
    meta = {
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "blender": bpy.app.version_string,
        "device": device,
        "options": " ".join(argv) or "(Standard)",
        "elapsed": round(elapsed, 2),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
    }
    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "tests": result.records}, fh, indent=1)
    write_markdown(args.md, result.records, meta)
    print(f"\nTests: {result.testsRun}, Fehler: {len(result.failures) + len(result.errors)}, "
          f"übersprungen: {len(result.skipped)}, Dauer: {elapsed:.1f} s")
    print(f"Bericht: {args.report}\nMarkdown: {args.md}")
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
