# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic, file-system safe names for exported files."""

from __future__ import annotations

import os
import re
from typing import Dict, Iterable, Set

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WS = re.compile(r"\s+")

LIGHTMAP_SUFFIX = "_lightmap"
SIDECAR_SUFFIX = ".lightmaps.json"


def sanitize(name: str, fallback: str = "object") -> str:
    """Make ``name`` safe for use as a file name component."""
    name = _INVALID.sub("_", name or "")
    name = _WS.sub("_", name.strip())
    name = name.strip("._")
    return name or fallback


def unique_names(names: Iterable[str]) -> Dict[str, str]:
    """Map every input name to a unique sanitized name (stable order)."""
    used: Set[str] = set()
    result: Dict[str, str] = {}
    for name in names:
        base = sanitize(name)
        candidate = base
        i = 2
        while candidate.lower() in used:
            candidate = f"{base}_{i}"
            i += 1
        used.add(candidate.lower())
        result[name] = candidate
    return result


def base_name_from_path(path: str, fallback: str = "Scene") -> str:
    if not path:
        return fallback
    stem = os.path.splitext(os.path.basename(path))[0]
    return sanitize(stem, fallback)


def lightmap_file_name(stem: str, ext: str) -> str:
    return f"{sanitize(stem)}{LIGHTMAP_SUFFIX}{ext}"


def sidecar_file_name(base_name: str) -> str:
    return f"{sanitize(base_name)}{SIDECAR_SUFFIX}"


def relpath(path: str, start: str) -> str:
    """Relative path with forward slashes (falls back to absolute on other drives)."""
    try:
        rel = os.path.relpath(path, start)
    except ValueError:
        rel = os.path.abspath(path)
    return rel.replace("\\", "/")
