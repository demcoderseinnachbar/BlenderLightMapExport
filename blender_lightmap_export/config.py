# SPDX-License-Identifier: GPL-3.0-or-later
"""Configuration dataclasses shared by UI, Python API and batch processing.

All settings are plain Python (no ``bpy`` dependency) so they can be loaded
from JSON, validated and serialised outside of Blender as well.
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Dict, List, Optional


class ConfigError(ValueError):
    """Raised for invalid configuration values."""


# --- allowed values ----------------------------------------------------------

UV_METHODS = ("SMART_PROJECT", "LIGHTMAP_PACK", "EXISTING")
UV_ROTATE_METHODS = ("AXIS_ALIGNED", "AXIS_ALIGNED_X", "AXIS_ALIGNED_Y")
BAKE_TYPES = ("DIFFUSE_LIGHTING", "COMBINED", "AO")
BAKE_DEVICES = ("AUTO", "CPU", "GPU")
BAKE_MARGIN_TYPES = ("EXTEND", "ADJACENT_FACES")
LIGHTING_MODES = ("SCENE", "AUTO", "DEFAULT_RIG")
ATLAS_MODES = ("PER_OBJECT", "SHARED_ATLAS")
IMAGE_FORMATS = ("PNG16", "PNG8", "EXR")
EXPORT_FORMATS = ("GLB", "GLTF", "FBX", "USD", "OBJ", "NONE")
EXPORT_SCOPES = ("SELECTED", "SCENE")
OBJ_UV_STRATEGIES = ("WARN_KEEP_ORIGINAL", "REPLACE_WITH_LIGHTMAP_UV", "TWO_FILES", "ERROR")
RESOLUTION_MIN = 256
RESOLUTION_MAX = 8192

IMAGE_EXTENSIONS = {"PNG16": ".png", "PNG8": ".png", "EXR": ".exr"}
EXPORT_EXTENSIONS = {"GLB": ".glb", "GLTF": ".gltf", "FBX": ".fbx", "USD": ".usdc", "OBJ": ".obj"}

SUPPORTED_INPUT_EXTENSIONS = (".glb", ".gltf", ".fbx", ".obj", ".usd", ".usda", ".usdc", ".usdz", ".blend")


# --- dataclasses --------------------------------------------------------------

@dataclass
class UVSettings:
    method: str = "SMART_PROJECT"
    uv_name: str = "LightmapUV"
    island_margin_px: float = 8.0
    angle_limit_deg: float = 66.0
    area_weight: float = 0.0
    rotate_method: str = "AXIS_ALIGNED"
    correct_aspect: bool = True
    validate: bool = True
    min_spacing_px: float = 1.0
    # With thousands of islands a pixel margin can consume the whole texture.
    # When enabled the margin is reduced so that margins use at most
    # ``max_margin_fraction`` of the texture side (a warning reports it).
    auto_reduce_margin: bool = True
    max_margin_fraction: float = 0.5
    # LIGHTMAP_PACK specific
    lightmap_pack_box_div: int = 12


@dataclass
class BakeSettings:
    type: str = "DIFFUSE_LIGHTING"
    resolution: int = 1024
    samples: int = 64
    margin_px: int = 12
    margin_type: str = "EXTEND"
    device: str = "AUTO"
    denoise: bool = False
    use_direct: bool = True
    use_indirect: bool = True
    ao_distance: float = 0.0  # 0 = Blender default (world AO distance)


@dataclass
class LightingSettings:
    mode: str = "AUTO"
    sun_energy: float = 3.0
    sun_rotation_deg: List[float] = field(default_factory=lambda: [50.0, 0.0, 30.0])
    world_strength: float = 0.3
    world_color: List[float] = field(default_factory=lambda: [0.8, 0.85, 1.0])


@dataclass
class AtlasSettings:
    mode: str = "PER_OBJECT"
    atlas_name: str = "Atlas"
    texel_density_weighting: bool = True


@dataclass
class ImageSettings:
    format: str = "PNG16"
    lightmap_subdir: str = "Lightmaps"
    always_use_subdir: bool = False


@dataclass
class ExportSettings:
    format: str = "GLB"
    scope: str = "SELECTED"
    overwrite: bool = True
    preserve_materials: bool = True
    apply_lightmap_preview: bool = True
    export_after_bake: bool = True
    reimport_check: bool = False
    obj_uv_strategy: str = "WARN_KEEP_ORIGINAL"
    gltf_lightmap_as_occlusion: bool = False
    base_name: str = ""
    write_sidecar: bool = True


@dataclass
class ExportConfig:
    output_dir: str = ""
    input_file: str = ""
    preset: str = ""
    log_level: str = "INFO"
    uv: UVSettings = field(default_factory=UVSettings)
    bake: BakeSettings = field(default_factory=BakeSettings)
    lighting: LightingSettings = field(default_factory=LightingSettings)
    atlas: AtlasSettings = field(default_factory=AtlasSettings)
    image: ImageSettings = field(default_factory=ImageSettings)
    export: ExportSettings = field(default_factory=ExportSettings)

    # --- serialisation -------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_json())

    @classmethod
    def from_dict(cls, data: Dict[str, Any], strict: bool = True) -> "ExportConfig":
        return _from_dict(cls, data, strict=strict, path="")

    @classmethod
    def load(cls, path: str, strict: bool = True) -> "ExportConfig":
        if not os.path.isfile(path):
            raise ConfigError(f"Konfigurationsdatei nicht gefunden: {path}")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Konfigurationsdatei ist kein gültiges JSON ({path}): {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigError(f"Konfigurationsdatei muss ein JSON-Objekt enthalten: {path}")
        cfg = cls.from_dict(data, strict=strict)
        if cfg.preset:
            apply_preset(cfg, cfg.preset, override_explicit=False, explicit=data.get("bake", {}))
        return cfg

    def copy(self) -> "ExportConfig":
        return ExportConfig.from_dict(self.to_dict())

    # --- validation ----------------------------------------------------------
    def validate(self) -> List[str]:
        """Return a list of human readable problems (empty if valid)."""
        problems: List[str] = []

        def check(value, allowed, name):
            if value not in allowed:
                problems.append(f"{name}: '{value}' ist ungültig, erlaubt: {', '.join(allowed)}")

        check(self.uv.method, UV_METHODS, "uv.method")
        check(self.uv.rotate_method, UV_ROTATE_METHODS, "uv.rotate_method")
        check(self.bake.type, BAKE_TYPES, "bake.type")
        check(self.bake.device, BAKE_DEVICES, "bake.device")
        check(self.bake.margin_type, BAKE_MARGIN_TYPES, "bake.margin_type")
        check(self.lighting.mode, LIGHTING_MODES, "lighting.mode")
        check(self.atlas.mode, ATLAS_MODES, "atlas.mode")
        check(self.image.format, IMAGE_FORMATS, "image.format")
        check(self.export.format, EXPORT_FORMATS, "export.format")
        check(self.export.scope, EXPORT_SCOPES, "export.scope")
        check(self.export.obj_uv_strategy, OBJ_UV_STRATEGIES, "export.obj_uv_strategy")

        if not self.uv.uv_name.strip():
            problems.append("uv.uv_name darf nicht leer sein")
        if not (RESOLUTION_MIN <= self.bake.resolution <= RESOLUTION_MAX):
            problems.append(f"bake.resolution muss zwischen {RESOLUTION_MIN} und {RESOLUTION_MAX} liegen")
        if self.bake.samples < 1:
            problems.append("bake.samples muss mindestens 1 sein")
        if self.bake.margin_px < 0:
            problems.append("bake.margin_px darf nicht negativ sein")
        if self.uv.island_margin_px < 0:
            problems.append("uv.island_margin_px darf nicht negativ sein")
        if not (0.0 < self.uv.angle_limit_deg <= 89.0):
            problems.append("uv.angle_limit_deg muss zwischen 0 und 89 Grad liegen")
        if not (0.0 <= self.uv.area_weight <= 1.0):
            problems.append("uv.area_weight muss zwischen 0 und 1 liegen")
        if self.bake.type == "DIFFUSE_LIGHTING" and not (self.bake.use_direct or self.bake.use_indirect):
            problems.append("bake: mindestens einer von use_direct/use_indirect muss aktiv sein")
        if self.export.format != "NONE" and not self.output_dir:
            problems.append("output_dir muss gesetzt sein")
        return problems

    def validate_or_raise(self) -> None:
        problems = self.validate()
        if problems:
            raise ConfigError("Ungültige Konfiguration:\n  - " + "\n  - ".join(problems))

    # --- helpers -------------------------------------------------------------
    @property
    def lightmap_extension(self) -> str:
        return IMAGE_EXTENSIONS[self.image.format]

    @property
    def export_extension(self) -> str:
        return EXPORT_EXTENSIONS.get(self.export.format, "")


# --- presets ------------------------------------------------------------------

PRESETS: Dict[str, Dict[str, Any]] = {
    "PREVIEW": {"samples": 16, "resolution": 512, "denoise": False},
    "MEDIUM": {"samples": 64, "resolution": 1024, "denoise": True},
    "HIGH": {"samples": 256, "resolution": 2048, "denoise": True},
    "PRODUCTION": {"samples": 1024, "resolution": 4096, "denoise": True},
}


def apply_preset(cfg: ExportConfig, name: str, override_explicit: bool = True,
                 explicit: Optional[Dict[str, Any]] = None) -> ExportConfig:
    """Apply a quality preset to ``cfg.bake``.

    With ``override_explicit=False`` values that were explicitly present in
    ``explicit`` (the raw ``bake`` dict of a JSON file) are kept.
    """
    key = (name or "").upper()
    if key not in PRESETS:
        raise ConfigError(f"Unbekanntes Preset '{name}', erlaubt: {', '.join(PRESETS)}")
    explicit = explicit or {}
    for attr, value in PRESETS[key].items():
        if not override_explicit and attr in explicit:
            continue
        setattr(cfg.bake, attr, value)
    cfg.preset = key
    return cfg


# --- generic dict -> dataclass ---------------------------------------------------

def _from_dict(cls, data: Dict[str, Any], strict: bool, path: str):
    if not isinstance(data, dict):
        raise ConfigError(f"'{path or cls.__name__}' muss ein Objekt sein")
    kwargs: Dict[str, Any] = {}
    known = {f.name: f for f in fields(cls)}
    for key, value in data.items():
        if key not in known:
            if strict:
                raise ConfigError(f"Unbekannter Konfigurationsschlüssel: '{path + key}'")
            continue
        ftype = known[key].type
        sub = _dataclass_for_field(cls, key)
        if sub is not None:
            kwargs[key] = _from_dict(sub, value, strict, path + key + ".")
        else:
            kwargs[key] = _coerce(value, ftype, path + key)
    return cls(**kwargs)


def _dataclass_for_field(cls, name):
    default_factory = next((f.default_factory for f in fields(cls) if f.name == name), None)
    if default_factory is not None and default_factory is not dataclasses.MISSING:
        try:
            inst = default_factory()
        except TypeError:
            return None
        if is_dataclass(inst):
            return type(inst)
    return None


def _coerce(value, ftype, path):
    tname = ftype if isinstance(ftype, str) else getattr(ftype, "__name__", str(ftype))
    try:
        if tname == "int":
            if isinstance(value, bool):
                raise TypeError
            return int(value)
        if tname == "float":
            return float(value)
        if tname == "bool":
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "on")
            return bool(value)
        if tname == "str":
            return "" if value is None else str(value)
    except (TypeError, ValueError):
        raise ConfigError(f"'{path}': Wert {value!r} hat den falschen Typ (erwartet {tname})")
    return value


def default_config_dict() -> Dict[str, Any]:
    return ExportConfig().to_dict()
