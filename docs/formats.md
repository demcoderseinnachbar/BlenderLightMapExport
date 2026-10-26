# Exportformate: Fähigkeiten und Grenzen

Alle Aussagen wurden mit Blender 5.2.3 LTS per Export und Reimport geprüft (siehe `tests/test_export.py`).

| Eigenschaft | GLB / glTF | FBX | USD (.usdc) | OBJ |
|---|---|---|---|---|
| Zweiter UV-Channel | ja (`TEXCOORD_1`) | ja | ja (`primvars:LightmapUV`) | **nein** |
| UV-Namen bleiben erhalten | **nein** (`UVMap.001` nach Import) | ja | ja | – |
| Custom Properties | ja (`extras`) | ja (nur einfache Typen, deshalb zusätzlich JSON-String) | ja (`userProperties`) | nein |
| Texturen | GLB eingebettet, glTF separat | kopiert neben die Datei | Ordner `textures/` | kopiert neben die Datei |
| Lightmap im Material des Formats | optional als `occlusionTexture` (TEXCOORD_1) | nein | nein | nein |
| Automatische Zuordnung in Blender | glTF-Import-Hook **oder** Operator | Operator | Operator | Operator (nur Strategie REPLACE/TWO_FILES) |
| Geometrie nach Reimport | trianguliert | unverändert | unverändert | unverändert |

## GLB / glTF

- Beide UV-Sets werden geschrieben. Der Importer vergibt generische Namen; das Add-on benennt den Layer anhand von `uv_index` aus Sidecar/extras zurück in `LightmapUV`.
- `export_extras=True` überträgt die Objekt-Properties `BLME_lightmap` (Dict) und `BLME_lightmap_json`. Zusätzlich schreibt der Export-Hook eine Zusammenfassung in `asset.extras.BLME_lightmaps`.
- Option *Lightmap als Occlusion* (`export.gltf_lightmap_as_occlusion`): Über den offiziellen Node „glTF Material Output“ wird die Lightmap als `occlusionTexture` mit `texCoord: 1` eingebettet. Standard-Viewer (three.js, Babylon.js, Khronos Sample Viewer) zeigen sie dann ohne Add-on als Verdeckung. Nur sinnvoll für AO oder LDR-Daten: glTF interpretiert allein den Rotkanal im Bereich 0..1. Für Diffuse-Lighting-Lightmaps (HDR, farbig) gibt es keinen glTF-Standard; sie werden ausschließlich über Sidecar/extras transportiert.
- Der glTF-Exporter trianguliert; Polygonzahlen ändern sich, Geometrie bleibt erhalten.

## FBX

- UV-Namen und zweiter Channel sind verlässlich. Custom Properties vom Typ Dict kommen als unbrauchbarer String zurück, deshalb wird die JSON-Kopie `BLME_lightmap_json` gelesen.
- Materialien werden als Phong/Lambert mit Texturpfaden geschrieben; die Lightmap ist kein Teil des FBX-Materials.

## USD

- UV-Layer werden als benannte Primvars exportiert (`rename_uvmaps=False`), Custom Properties als `userProperties:*`.
- Materialien als `UsdPreviewSurface`; Texturen im Ordner `textures/`.

## OBJ

OBJ transportiert genau ein UV-Set (den aktiven UV-Layer) und keine Metadaten. Das System verliert nie stillschweigend Daten, sondern verlangt eine Strategie (`export.obj_uv_strategy`):

| Strategie | Dateiinhalt | Reimport-Zuordnung |
|---|---|---|
| `WARN_KEEP_ORIGINAL` (Standard) | Original-UVs, Lightmap-UV fehlt; Warnung im Log und Hinweis in der Sidecar | nicht möglich (Objekt wird als „unmatched“ gemeldet) |
| `REPLACE_WITH_LIGHTMAP_UV` | nur Lightmap-UVs (Index 0); Originaltexturen passen in der OBJ nicht mehr | ja (Sidecar `uv_index: 0`) |
| `TWO_FILES` | `<Name>.obj` mit Original-UVs und `<Name>_lightmapuv.obj` mit Lightmap-UVs | ja für die zweite Datei (teilt die Sidecar) |
| `ERROR` | Export wird abgebrochen | – |

Die Blender-Szene behält in allen Fällen beide UV-Layer.

## Sidecar-Datei `<Modell>.lightmaps.json`

```json
{
  "format": "BlenderLightMapExport", "version": 1,
  "model": "Model.glb", "export_format": "GLB",
  "bake": {"type": "DIFFUSE_LIGHTING", "resolution": 1024, "samples": 64, "margin_px": 12, "denoise": true, "device": "OPTIX"},
  "uv": {"name": "LightmapUV", "method": "SMART_PROJECT", "island_margin_px": 8.0},
  "image": {"format": "PNG16", "colorspace": "linear"},
  "atlas": "PER_OBJECT",
  "lightmaps": [{"image": "Wall_lightmap", "file": "Lightmaps/Wall_lightmap.png", "objects": ["Wall"], "resolution": 1024, "uv_index_by_object": {"Wall": 1}, "stats": {"mean": 0.31, "max": 1.2}}],
  "objects": {"Wall": {"mesh": "Wall", "lightmap": "Lightmaps/Wall_lightmap.png", "uv_name": "LightmapUV", "uv_index": 1, "materials": ["MatWall"], "original_uv_names": ["UVMap"]}},
  "warnings": []
}
```

Pfade sind relativ zur Modelldatei. Die Datei ist für andere Engines/Werkzeuge gedacht, die die Lightmap selbst einbinden wollen (Albedo × Lightmap bei Diffuse-Lighting-Bakes, linearer Farbraum).

## Allgemeine Grenzen

- Kein Format transportiert die Blender-Vorschau-Nodes. Die Wiederherstellung übernimmt immer das Add-on (Hook oder Operator).
- Modifikatoren werden beim Export angewendet (FBX/OBJ/USD) bzw. nicht (glTF, `export_apply=False`, damit die Lightmap-UVs der Basismesh-Topologie entsprechen). Generatormodifikatoren (Mirror, Array) erzeugen überlappende Lightmap-UVs und werden mit Warnung gemeldet.
- Instanzen (geteilte Mesh-Daten) erhalten eine gemeinsame Lightmap.
