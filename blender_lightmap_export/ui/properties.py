# SPDX-License-Identifier: MIT
"""Scene property group mirroring :class:`ExportConfig` for the UI."""

from __future__ import annotations

import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty,
                       StringProperty)

from ..config import ExportConfig, PRESETS, apply_preset


def _enum(items):
    return [(i, label, desc) for i, label, desc in items]


class BLME_Settings(bpy.types.PropertyGroup):
    # --- UI state ------------------------------------------------------------
    show_advanced: BoolProperty(name="Erweitert", description="Erweiterte Einstellungen anzeigen", default=False)
    preset: EnumProperty(
        name="Qualität",
        items=_enum([
            ("CUSTOM", "Benutzerdefiniert", "Werte aus den erweiterten Einstellungen"),
            ("PREVIEW", "Vorschau", "16 Samples, 512 px"),
            ("MEDIUM", "Mittel", "64 Samples, 1024 px, Denoise"),
            ("HIGH", "Hoch", "256 Samples, 2048 px, Denoise"),
            ("PRODUCTION", "Produktion", "1024 Samples, 4096 px, Denoise"),
        ]),
        default="MEDIUM",
        update=lambda self, ctx: self._apply_preset(),
    )

    # --- export ----------------------------------------------------------------
    output_dir: StringProperty(name="Zielverzeichnis", subtype="DIR_PATH", default="//export")
    export_format: EnumProperty(
        name="Format",
        items=_enum([
            ("GLB", "GLB", "glTF Binary (eine Datei, Texturen eingebettet)"),
            ("GLTF", "glTF", "glTF mit separaten .bin/Texturdateien"),
            ("FBX", "FBX", "Autodesk FBX"),
            ("USD", "USD", "Universal Scene Description (.usdc)"),
            ("OBJ", "OBJ", "Wavefront OBJ (nur ein UV-Set!)"),
            ("NONE", "Kein Export", "Nur backen"),
        ]),
        default="GLB",
    )
    export_scope: EnumProperty(
        name="Umfang",
        items=_enum([("SELECTED", "Auswahl", "Nur ausgewählte Objekte"), ("SCENE", "Szene", "Alle Objekte der Szene")]),
        default="SELECTED",
    )
    overwrite: BoolProperty(name="Vorhandene Dateien überschreiben", default=True)
    apply_lightmap_preview: BoolProperty(name="Lightmap-Vorschau zuweisen", default=True,
                                         description="Nach dem Backen die Lightmap in den Materialien anzeigen")
    reimport_check: BoolProperty(name="Reimport prüfen", default=False,
                                 description="Exportdatei in eine temporäre Szene importieren und prüfen")
    base_name: StringProperty(name="Dateiname", default="", description="Basisname der Exportdatei (leer = automatisch)")
    obj_uv_strategy: EnumProperty(
        name="OBJ-UV-Strategie",
        items=_enum([
            ("WARN_KEEP_ORIGINAL", "Original-UVs (Warnung)", "OBJ erhält die Original-UVs, Lightmap-UV nur in Sidecar"),
            ("REPLACE_WITH_LIGHTMAP_UV", "Lightmap-UV statt Original", "OBJ erhält nur die Lightmap-UVs"),
            ("TWO_FILES", "Zwei Dateien", "Eine OBJ mit Original-UVs, eine mit Lightmap-UVs"),
            ("ERROR", "Abbrechen", "Export abbrechen"),
        ]),
        default="WARN_KEEP_ORIGINAL",
    )
    gltf_lightmap_as_occlusion: BoolProperty(
        name="glTF: Lightmap als Occlusion-Textur", default=False,
        description="Lightmap zusätzlich als occlusionTexture (TEXCOORD_1) einbetten, damit Standard-Viewer sie anzeigen "
                    "(nur sinnvoll für AO / LDR)")

    # --- uv ----------------------------------------------------------------------
    uv_method: EnumProperty(
        name="UV-Methode",
        items=_enum([
            ("SMART_PROJECT", "Smart UV Project", "Automatische Projektion nach Winkel"),
            ("LIGHTMAP_PACK", "Lightmap Pack", "Jede Fläche einzeln packen"),
            ("EXISTING", "Vorhandenen Channel", "Bestehenden UV-Layer mit dem angegebenen Namen verwenden"),
        ]),
        default="SMART_PROJECT",
    )
    uv_name: StringProperty(name="UV-Channel", default="LightmapUV")
    island_margin_px: FloatProperty(name="Island Margin (px)", default=8.0, min=0.0, max=256.0, precision=1)
    angle_limit_deg: FloatProperty(name="Angle Limit (°)", default=66.0, min=1.0, max=89.0)
    area_weight: FloatProperty(name="Area Weight", default=0.0, min=0.0, max=1.0)
    rotate_method: EnumProperty(
        name="Ausrichtung",
        items=_enum([("AXIS_ALIGNED", "Achsen", ""), ("AXIS_ALIGNED_X", "X-Achse", ""), ("AXIS_ALIGNED_Y", "Y-Achse", "")]),
        default="AXIS_ALIGNED",
    )
    validate_uvs: BoolProperty(name="UVs prüfen", default=True)

    # --- bake ----------------------------------------------------------------------
    resolution: EnumProperty(
        name="Auflösung",
        items=_enum([(str(r), f"{r} px", "") for r in (256, 512, 1024, 2048, 4096, 8192)]),
        default="1024",
    )
    samples: IntProperty(name="Samples", default=64, min=1, max=16384)
    bake_margin_px: IntProperty(name="Bake Margin (px)", default=12, min=0, max=256)
    bake_type: EnumProperty(
        name="Bake-Typ",
        items=_enum([
            ("DIFFUSE_LIGHTING", "Diffuse Beleuchtung (ohne Farbe)", "Nur Licht und Schatten, Materialfarbe bleibt separat"),
            ("COMBINED", "Combined", "Vollständiges Shading inklusive Materialfarbe"),
            ("AO", "Ambient Occlusion", "Nur Verdeckung"),
        ]),
        default="DIFFUSE_LIGHTING",
    )
    device: EnumProperty(
        name="Gerät",
        items=_enum([("AUTO", "Automatisch", "GPU wenn verfügbar"), ("GPU", "GPU", ""), ("CPU", "CPU", "")]),
        default="AUTO",
    )
    denoise: BoolProperty(name="Denoising", default=True, description="Nachträgliches Entrauschen (OpenImageDenoise)")
    use_direct: BoolProperty(name="Direktes Licht", default=True)
    use_indirect: BoolProperty(name="Indirektes Licht", default=True)
    lighting_mode: EnumProperty(
        name="Beleuchtung",
        items=_enum([
            ("AUTO", "Automatisch", "Szenenlichter verwenden, sonst Standard-Setup erzeugen"),
            ("SCENE", "Nur Szene", "Ausschließlich vorhandene Lichtquellen"),
            ("DEFAULT_RIG", "Standard-Setup", "Immer temporäres Standardlicht (Szenenlichter werden ignoriert)"),
        ]),
        default="AUTO",
    )
    atlas_mode: EnumProperty(
        name="Lightmaps",
        items=_enum([("PER_OBJECT", "Eine pro Objekt", ""), ("SHARED_ATLAS", "Gemeinsamer Atlas", "")]),
        default="PER_OBJECT",
    )
    image_format: EnumProperty(
        name="Texturformat",
        items=_enum([("PNG16", "PNG 16 Bit", "Linear, geclampt auf 0..1"), ("PNG8", "PNG 8 Bit", ""),
                     ("EXR", "EXR (HDR)", "Half Float, verlustfrei")]),
        default="PNG16",
    )

    # --- status ------------------------------------------------------------------------
    is_running: BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})
    progress: FloatProperty(default=0.0, min=0.0, max=1.0, options={"HIDDEN", "SKIP_SAVE"})
    status_text: StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    last_summary: StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    last_files: StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    last_warnings: StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})
    last_error: StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})

    # --- conversion ----------------------------------------------------------------------
    def _apply_preset(self):
        if self.preset in PRESETS:
            cfg = ExportConfig()
            apply_preset(cfg, self.preset)
            self.samples = cfg.bake.samples
            self.resolution = str(cfg.bake.resolution)
            self.denoise = cfg.bake.denoise

    def to_config(self) -> ExportConfig:
        cfg = ExportConfig()
        cfg.output_dir = bpy.path.abspath(self.output_dir) if self.output_dir else ""
        cfg.export.format = self.export_format
        cfg.export.scope = self.export_scope
        cfg.export.overwrite = self.overwrite
        cfg.export.apply_lightmap_preview = self.apply_lightmap_preview
        cfg.export.reimport_check = self.reimport_check
        cfg.export.base_name = self.base_name
        cfg.export.obj_uv_strategy = self.obj_uv_strategy
        cfg.export.gltf_lightmap_as_occlusion = self.gltf_lightmap_as_occlusion
        cfg.uv.method = self.uv_method
        cfg.uv.uv_name = self.uv_name
        cfg.uv.island_margin_px = self.island_margin_px
        cfg.uv.angle_limit_deg = self.angle_limit_deg
        cfg.uv.area_weight = self.area_weight
        cfg.uv.rotate_method = self.rotate_method
        cfg.uv.validate = self.validate_uvs
        cfg.bake.resolution = int(self.resolution)
        cfg.bake.samples = self.samples
        cfg.bake.margin_px = self.bake_margin_px
        cfg.bake.type = self.bake_type
        cfg.bake.device = self.device
        cfg.bake.denoise = self.denoise
        cfg.bake.use_direct = self.use_direct
        cfg.bake.use_indirect = self.use_indirect
        cfg.lighting.mode = self.lighting_mode
        cfg.atlas.mode = self.atlas_mode
        cfg.image.format = self.image_format
        cfg.preset = self.preset if self.preset != "CUSTOM" else ""
        return cfg

    def from_config(self, cfg: ExportConfig) -> None:
        self.output_dir = cfg.output_dir
        self.export_format = cfg.export.format
        self.export_scope = cfg.export.scope
        self.overwrite = cfg.export.overwrite
        self.apply_lightmap_preview = cfg.export.apply_lightmap_preview
        self.reimport_check = cfg.export.reimport_check
        self.base_name = cfg.export.base_name
        self.obj_uv_strategy = cfg.export.obj_uv_strategy
        self.gltf_lightmap_as_occlusion = cfg.export.gltf_lightmap_as_occlusion
        self.uv_method = cfg.uv.method
        self.uv_name = cfg.uv.uv_name
        self.island_margin_px = cfg.uv.island_margin_px
        self.angle_limit_deg = cfg.uv.angle_limit_deg
        self.area_weight = cfg.uv.area_weight
        self.rotate_method = cfg.uv.rotate_method
        self.validate_uvs = cfg.uv.validate
        self.preset = "CUSTOM"
        self.resolution = str(cfg.bake.resolution) if str(cfg.bake.resolution) in {"256", "512", "1024", "2048", "4096", "8192"} else "1024"
        self.samples = cfg.bake.samples
        self.bake_margin_px = cfg.bake.margin_px
        self.bake_type = cfg.bake.type
        self.device = cfg.bake.device
        self.denoise = cfg.bake.denoise
        self.use_direct = cfg.bake.use_direct
        self.use_indirect = cfg.bake.use_indirect
        self.lighting_mode = cfg.lighting.mode
        self.atlas_mode = cfg.atlas.mode
        self.image_format = cfg.image.format


def register():
    bpy.utils.register_class(BLME_Settings)
    bpy.types.Scene.blme = PointerProperty(type=BLME_Settings)


def unregister():
    del bpy.types.Scene.blme
    bpy.utils.unregister_class(BLME_Settings)
