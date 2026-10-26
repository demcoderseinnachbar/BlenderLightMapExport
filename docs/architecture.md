# Architektur

## Überblick

```
 Blender-Panel (ui/)      Python-API (api.py)      Batch (scripts/batch_export.py, start_export.bat)
        │                        │                               │
        └──────── ExportConfig (config.py, JSON) ────────────────┘
                                 │
                     core/pipeline.py: build_steps()
                                 │
   ┌─────────────────────────────┴───────────────────────────────┐
   │ SyncRunner (headless/API)         ModalRunner (UI-Operator) │
   └─────────────────────────────┬───────────────────────────────┘
                                 ▼
   import → collect → paths → device → lighting → uv → uv_validate
   → bake_targets → bake:<Bild> … → bake_finish → denoise → save
   → materials → metadata_props → export → sidecar → reimport_check
```

Es gibt genau eine Implementierung jedes Schritts. Die UI unterscheidet sich nur dadurch, dass sie die Schritte über einen Timer abarbeitet und Bake-Schritte als Blender-Job (`bpy.ops.object.bake('INVOKE_DEFAULT')`) startet. Ohne Fenster (Background) läuft derselbe Operator blockierend über den SyncRunner.

## Module

| Modul | Aufgabe |
|---|---|
| `config.py` | Dataclasses `ExportConfig`, `UVSettings`, `BakeSettings`, `LightingSettings`, `AtlasSettings`, `ImageSettings`, `ExportSettings`; Validierung; Presets; JSON |
| `api.py` | Öffentliche Funktionen, Fehlerklasse `LightmapExportError` |
| `core/pipeline.py` | `Step`, `PipelineContext`, `PipelineResult`, `LightmapInfo`, `build_steps`, `SyncRunner`, `finish_run` |
| `core/state.py` | `SceneStateSnapshot` (Render-, Bake-, Bild-, View-Settings, Welt, Compositor-Gruppe, UV-Aktivzustand, Selektion, Modus, hide_render) und `TempTracker` (Undo-Stack für temporäre Datablocks, Materialkopien, Nodes, UV-Layer, Callbacks) |
| `core/io_import.py` | Import nach Endung, liefert neue Objekte |
| `core/lighting.py` | Lichtanalyse, temporäres Standard-Setup (Collection, Sonne, Welt) |
| `core/uv.py` | `LightmapUV` anlegen, Smart UV Project (zwei Durchläufe: Inseln zählen, dann machbarer Rand), Lightmap Pack, Atlas-Packing mit Texeldichte-Vorskalierung |
| `core/uv_validate.py` | Rasterisierung des UV-Layouts mit numpy: Überlappung, Bereich, NaN, Inselabstand; Inseln über Mesh-Kanten mit identischen UVs (Vertex-Positionen, nicht Indizes) |
| `core/baking.py` | Geräteauswahl (OptiX > CUDA > HIP > oneAPI > CPU), Bake-Ziele je Material-Slot, temporäre Materialkopien für geteilte Materialien, Bake-Aufruf, Verifikation |
| `core/images.py` | Statistiken, Speichern (PNG16/PNG8/EXR, linear), Denoising über Compositor-Node-Gruppe |
| `core/materials.py` | Node-Gruppe `BLME_LightmapShader`, Binden/Umschalten/Wiederherstellen, Bypass für Exporter |
| `core/metadata.py` | Objekt-Properties, Sidecar-JSON, Zuordnung beim Import, Reimport-Prüfung |
| `formats/base.py` | `FormatCapabilities`, `BaseExporter`, Registry |
| `formats/gltf.py`, `fbx.py`, `usd.py`, `obj.py` | Exporteraufrufe und Strategien |
| `formats/gltf_hooks.py` | `glTF2ExportUserExtension`, `glTF2ImportUserExtension` |
| `ui/` | `BLME_Settings` (Scene-PropertyGroup), Operatoren, Panels, Preferences |

## Zustandssicherung

- `SceneStateSnapshot` wird vor dem ersten Schritt erstellt und in `finish_run` immer wiederhergestellt (auch bei Exceptions und Abbruch).
- Zwei `TempTracker`: `ctx.temp` (temporäre Dinge: Lichter, Welt, Bake-Nodes, Materialkopien für den Bake, Compositor-Gruppe, Geräteeinstellungen) wird immer rückgängig gemacht; `ctx.product` (neue UV-Layer, Bilder, Standardmaterialien für Objekte ohne Material) nur bei Fehlern.
- Bake-spezifische temporäre Änderungen liegen in einem dritten Tracker, der direkt nach dem Bake aufgeräumt wird, bevor die Vorschau gebunden wird.
- Cycles-Geräteeinstellungen (Preferences) werden nach dem Lauf zurückgesetzt.

## Materialaufbau der Vorschau

```
[Original-Shader] ──┐
                    ├─> [BLME_Shader: Gruppe BLME_LightmapShader] ──> Material Output
[BLME_UV: LightmapUV] -> [BLME_Lightmap: Image, Non-Color] ──┘
       Base Color des Original-BSDF ───────────────────────────┘
```

Gruppen-Eingänge: Shader, Base Color, Lightmap, Preview (0 = Original, 1 = Lightmap), Lightmap Type (0 Diffuse Lighting, 1 Combined, 2 AO), Strength. Die ursprüngliche Verbindung zum Output wird als Property `BLME_restore` am Material gespeichert. Beim Export wird die Gruppe umgangen, damit Exporter den Original-BSDF sehen. Beim Bake ebenfalls, damit keine Emission gebacken wird.

## Namensregeln

- Basisname: `export.base_name`, sonst Eingabedatei, sonst .blend-Datei, sonst Objektname (ein Objekt), sonst `Scene`.
- Lightmap: `<Basisname>_lightmap.<ext>` (eine Lightmap) oder `Lightmaps/<Objekt>_lightmap.<ext>`; unsichere Zeichen werden ersetzt, Kollisionen nummeriert.
- Sidecar: `<Basisname>.lightmaps.json`.

## Erweiterung um ein Format

1. Klasse von `BaseExporter` ableiten, `capabilities` setzen, `export()` und `import_file()` implementieren, mit `@register_exporter("NAME")` registrieren.
2. In `formats/base.py` `_ensure_loaded` importieren.
3. `EXPORT_FORMATS` und `EXPORT_EXTENSIONS` in `config.py` ergänzen, Enum in `ui/properties.py`.
4. Roundtrip-Test in `tests/test_export.py`.
