# SPDX-License-Identifier: GPL-3.0-or-later
"""Download (or verify) the external example models.

Works with plain Python 3 *or* inside Blender::

    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\5.2\\python\\bin\\python.exe" scripts/fetch_example_models.py [--verify-only]

Every model folder gets a ``SOURCE.json`` with URL, SHA-256, size and download
date. ``--verify-only`` checks the files in the repository against the recorded
hashes without downloading.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.request

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
EXAMPLES = os.path.join(REPO_ROOT, "examples")

MODELS = {
    "car": {
        "name": "Toy Car",
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/legalcode",
        "authors": "Guido Odendahl (Modell), Eric Chadwick (Erweiterungen, Szene)",
        "source_url": "https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/ToyCar",
        "files": {
            "ToyCar.glb": "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/ToyCar/glTF-Binary/ToyCar.glb",
            "ToyCar.metadata.json": "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/ToyCar/metadata.json",
        },
    },
    "ship": {
        "name": "Dutch Ship Large 01",
        "license": "CC0-1.0",
        "license_url": "https://polyhaven.com/license",
        "authors": "James Ray Cock (Modell, Texturen, Cleanup), Rico Cilliers (Segel, Texturen), "
                   "Nicolò Zubbini (Originalmodell)",
        "source_url": "https://polyhaven.com/a/dutch_ship_large_01",
        "api_url": "https://api.polyhaven.com/files/dutch_ship_large_01",
        "resolution": "1k",
        "files": {},  # filled from the Poly Haven API
    },
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: str) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "BlenderLightMapExport/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as out:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)


def polyhaven_files(info: dict) -> dict:
    req = urllib.request.Request(info["api_url"], headers={"User-Agent": "BlenderLightMapExport/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    res = info["resolution"]
    entry = data["gltf"][res]["gltf"]
    files = {os.path.basename(entry["url"]): entry["url"]}
    for rel, inc in entry.get("include", {}).items():
        files[rel.replace("\\", "/")] = inc["url"]
    return files


def fetch(model_key: str, verify_only: bool = False) -> dict:
    info = MODELS[model_key]
    folder = os.path.join(EXAMPLES, model_key)
    source_path = os.path.join(folder, "SOURCE.json")
    recorded = json.load(open(source_path, encoding="utf-8")) if os.path.isfile(source_path) else None
    if verify_only:
        if recorded is None:
            raise SystemExit(f"{model_key}: SOURCE.json fehlt, bitte zuerst ohne --verify-only ausführen")
        problems = []
        for rel, meta in recorded["files"].items():
            path = os.path.join(folder, rel)
            if not os.path.isfile(path):
                problems.append(f"fehlt: {rel}")
            elif sha256(path) != meta["sha256"]:
                problems.append(f"Hash weicht ab: {rel}")
        if problems:
            raise SystemExit(f"{model_key}: " + "; ".join(problems))
        print(f"[fetch_example_models] {model_key}: {len(recorded['files'])} Dateien geprüft, OK")
        return recorded
    files = dict(info["files"])
    if "api_url" in info:
        files.update(polyhaven_files(info))
    result = {
        "name": info["name"], "license": info["license"], "license_url": info["license_url"],
        "authors": info["authors"], "source_url": info["source_url"],
        "downloaded": time.strftime("%Y-%m-%d"), "files": {},
    }
    for rel, url in files.items():
        dest = os.path.join(folder, rel)
        print(f"[fetch_example_models] {model_key}: {rel} <- {url}")
        download(url, dest)
        result["files"][rel] = {"url": url, "sha256": sha256(dest), "bytes": os.path.getsize(dest)}
    with open(source_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"[fetch_example_models] {model_key}: {len(result['files'])} Dateien, SOURCE.json geschrieben")
    return result


def main(argv) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--model", choices=sorted(MODELS), default="")
    args = parser.parse_args(argv)
    for key in ([args.model] if args.model else sorted(MODELS)):
        fetch(key, verify_only=args.verify_only)
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    sys.exit(main(argv))
