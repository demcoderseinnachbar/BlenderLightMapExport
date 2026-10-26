# Testmodelle

## Externe Beispielmodelle

| Modell | Datei | Urheber | Lizenz | Quelle | Download | Änderungen |
|---|---|---|---|---|---|---|
| Utah Teapot | `examples/teapot/utah_teapot.glb` (aus `teapot_bezier.txt` erzeugt) | Martin Newell (1975), Bezier-Daten Newell/Blinn, Datei T. V. Thompson II | „freely available for any use, including commercial use“ (University of Utah) | <https://users.cs.utah.edu/~dejohnso/models/teapot_bezier>, <https://graphics.cs.utah.edu/teapot/> | 26.10.2026 | Tessellation (12 Unterteilungen), Z-up, 2 m, neutrales Material, keine UVs |
| Toy Car | `examples/car/ToyCar.glb` | Guido Odendahl, Eric Chadwick | CC0-1.0 | <https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/ToyCar> | 26.10.2026 | keine |
| Dutch Ship Large 01 | `examples/ship/dutch_ship_large_01_1k.gltf` + `.bin` + `textures/` | James Ray Cock, Rico Cilliers, Nicolò Zubbini | CC0-1.0 (Poly Haven) | <https://polyhaven.com/a/dutch_ship_large_01> | 26.10.2026 | keine (1k-Variante) |

Details, Hashes und Lizenztexte: `examples/<modell>/README.md` und `SOURCE.json`. Prüfen der Hashes:

```bat
"C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" scripts\fetch_example_models.py --verify-only
```

Eigenschaften, die die Modelle abdecken:

| Modell | Meshes | Materialien | Polygone | UVs vorhanden | Besonderheit |
|---|---|---|---|---|---|
| Teapot | 1 | 1 | 8 064 Dreiecke | nein | gekrümmte Flächen, offener Boden |
| Toy Car | 3 | 3 (Clearcoat, Transmission, Sheen, 8 Texturen) | 108 936 | ja | Glas liefert schwarze Diffuse-Lightmap (gemeldet), HDR-Werte |
| Dutch Ship | 3 | 3 (Rumpf, Takelage, Segel) | 110 616 | ja | komplexe Aufbauten, tausende UV-Inseln, Alpha-Segel |

## Synthetische Testgeometrien

`scripts/generate_test_scenes.py` erzeugt reproduzierbar (Funktionsname = Szenenname):

| Szene | Inhalt |
|---|---|
| `cube` | Würfel mit Material und Sonne |
| `plane` | Unterteilte Ebene, Sonne und Punktlicht |
| `room` | Boden, Decke, vier Wände, Box, Deckenlampe |
| `row` | Würfel, Kugel, Zylinder, Boden (unterschiedliche Größen) |
| `multi_material` | Würfel mit drei Material-Slots plus Boden |
| `existing_uvs` | Würfel mit zwei UV-Layern und texturiertem Material |
| `no_uvs` | Suzanne ohne UV-Layer und ohne Material |
| `multi_lights` | Raum mit Punkt-, Spot- und Flächenlichtern in Farbe |
| `shared_material` | Zwei Objekte mit demselben Material |
| `instances` | Zwei Objekte mit demselben Mesh |

Alle Szenen als .blend erzeugen:

```bat
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --factory-startup --python scripts\generate_test_scenes.py -- --out build\synthetic
```
