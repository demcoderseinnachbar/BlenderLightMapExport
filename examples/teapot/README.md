# Utah Teapot

| | |
|---|---|
| **Modellname** | Utah Teapot (Newell Teapot) |
| **Urheber** | Martin Newell (Originalmodell, 1975, University of Utah); Bezier-Datensatz von Jim Blinn / Martin Newell; Datei `teapot_bezier.txt` zusammengestellt von Thomas V. Thompson II (28.01.2000) |
| **Original-URL** | Datensatz: <https://users.cs.utah.edu/~dejohnso/models/teapot_bezier> (Übersicht: <https://users.cs.utah.edu/~dejohnso/models/teapot.html>) |
| **Nutzungserlaubnis** | Offizielle Seite der University of Utah (<https://graphics.cs.utah.edu/teapot/>): „The Utah Teapot model files are freely available for any use, including commercial use.“ Die Daten werden „as is“ ohne Gewährleistung bereitgestellt. Es handelt sich um eine ausdrückliche Freigabe für jede Nutzung, nicht um eine formale CC0-Widmung. Die Universität bittet darum, abgeleitete Versionen als Utah-Teapot-Variante zu kennzeichnen. |
| **Download-Datum** | 26.10.2026 |
| **SHA-256 (teapot_bezier.txt)** | `22d59967e342b8e6f2b4e78e8db50a44f5aa370661f069b478ae8d0d76d9395e` |

## Dateien

- `teapot_bezier.txt`: unveränderte Originaldaten, 28 bikubische Bezier-Patches (448 Kontrollpunkte), Y-up.
- `utah_teapot.glb`: aus den Patches erzeugtes Mesh (4175 Vertices, 4032 Quads, als GLB trianguliert).

## Änderungen gegenüber dem Original

Die GLB-Datei wird mit `scripts/generate_teapot.py` deterministisch aus den Patches erzeugt:

- Tessellation mit 12 Unterteilungen pro Patch, Patches verschweißt (`remove_doubles`), degenerierte Polflächen entfernt.
- Umrechnung von Y-up nach Z-up, Skalierung auf etwa 2 m Höhe.
- Neutrales Material `TeapotCeramic` (Principled BSDF, keine Texturen).
- Das Modell hat **keine UV-Koordinaten** und entspricht dem Original ohne Bodenfläche (die 1975er Daten enthalten keinen Boden).

Neu erzeugen:

```bat
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --factory-startup --python scripts\generate_teapot.py -- --subdiv 12
```
