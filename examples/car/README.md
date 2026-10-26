# Toy Car

| | |
|---|---|
| **Modellname** | Toy Car (Khronos glTF Sample Assets) |
| **Urheber** | Guido Odendahl (Automodell), Eric Chadwick (Material-Erweiterungen, Szenenaufbau) |
| **Original-URL** | <https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/ToyCar> |
| **Lizenz** | CC0 1.0 Universal (Public Domain Dedication), <https://creativecommons.org/publicdomain/zero/1.0/legalcode>. Lizenzangaben laut `ToyCar.metadata.json` des Repositories. |
| **Download-Datum** | 26.10.2026 |
| **SHA-256** | siehe `SOURCE.json` |

## Dateien

- `ToyCar.glb`: unverändertes Original (5,4 MB, glTF-Binary). 3 Meshes (`ToyCar`, `Fabric`, `Glass`), 3 Materialien, 108 936 Dreiecke, 8 Texturen (512 bis 1024 px), vorhandene UV-Koordinaten, 8 Kameras.
- `ToyCar.metadata.json`: Lizenz-Metadaten aus dem Khronos-Repository.
- `SOURCE.json`: Download-URL, Hashes und Datum (von `scripts/fetch_example_models.py` erzeugt).

## Änderungen gegenüber dem Original

Keine. Das Modell nutzt die glTF-Erweiterungen `KHR_materials_clearcoat`, `KHR_materials_transmission`, `KHR_materials_sheen` und `KHR_texture_transform`, die Blender beim Import in Principled-BSDF-Parameter übersetzt.

## Hinweise für Lightmap-Tests

- Das Material `Glass` ist rein transmissiv. Eine Diffuse-Lightmap ist dafür erwartungsgemäß schwarz; das System meldet das als Warnung.
- Die Lightmaps der drei Meshes enthalten Werte über 1.0 (direktes Sonnenlicht). Für HDR-Daten EXR wählen, PNG wird auf 1.0 begrenzt.
