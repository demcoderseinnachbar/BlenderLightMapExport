# BlenderLightMapExport

Blender-Add-on, Python-API und Windows-Batch zum Backen von Lightmaps mit Cycles und zum Export von Modellen mit separaten Lightmap-Dateien.

- Zielversion: **Blender 5.2.3 LTS** (Windows)
- Lizenz: GPL-3.0-or-later (Projektcode); Beispielmodelle haben eigene Lizenzen, siehe `examples/*/README.md`
- Eine Kernimplementierung (`blender_lightmap_export/core`) für Add-on, API und Batch

## Was das System macht

1. Modell importieren (GLB/glTF, FBX, OBJ, USD, .blend) oder die aktuelle Szene verwenden
2. Zusätzlichen UV-Channel `LightmapUV` anlegen (Smart UV Project, Lightmap Pack oder vorhandener Channel), bestehende UVs bleiben unverändert
3. UV-Layout prüfen (Überlappung, Bereich, NaN, Inselabstand)
4. Mit Cycles backen: Diffuse Beleuchtung ohne Materialfarbe (Standard), Combined oder Ambient Occlusion, CPU oder GPU
5. Lightmap als PNG (16 Bit, linear) oder EXR (HDR) neben dem Modell speichern, optional entrauschen
6. Lightmap in Blender als Vorschau anzeigen, ohne die Originalmaterialien zu zerstören
7. Exportieren als GLB, glTF, FBX, USD oder OBJ plus Sidecar-Datei `<Modell>.lightmaps.json`
8. Beim Reimport Lightmaps automatisch erkennen und zuweisen (glTF: beim normalen Blender-Import mit aktiviertem Add-on; alle Formate: Operator „Mit Lightmaps importieren“)

## Schnellstart

Extension installieren: `build/blender_lightmap_export-0.1.0.zip` in Blender über *Edit > Preferences > Get Extensions > Install from Disk* laden (siehe [docs/installation.md](docs/installation.md)). Panel: *3D-Viewport > Sidebar (N) > Lightmap Exporter*.

Batch (Windows):

```bat
start_export.bat C:\Models\model.glb C:\Export
start_export.bat C:\Models C:\Export --format FBX --preset HIGH --recursive
start_export.bat --config config.example.json
```

Python (innerhalb von Blender, Repository im `sys.path`):

```python
from blender_lightmap_export import export_lightmap

result = export_lightmap(
    input_file="C:/Models/model.glb",
    output_dir="C:/Export",
    export_format="GLB",
    resolution=2048,
    samples=128,
    island_margin_px=8,
    bake_margin_px=12,
)
print(result.summary())
```

Tests:

```bat
run_tests.bat                 rem alle Tests (etwa 2 Minuten, GPU wenn vorhanden)
run_tests.bat --no-slow       rem ohne Subprozess- und Modelltests
```

## Dokumentation

| Datei | Inhalt |
|---|---|
| [docs/installation.md](docs/installation.md) | Installation der Extension, Voraussetzungen, Batch-Einrichtung |
| [docs/usage.md](docs/usage.md) | Panel, Einstellungen, Python-API, Batch-Optionen, Reimport |
| [docs/architecture.md](docs/architecture.md) | Module, Pipeline, Zustandssicherung, Materialaufbau |
| [docs/formats.md](docs/formats.md) | Fähigkeiten und Grenzen der Exportformate |
| [docs/test_models.md](docs/test_models.md) | Beispielmodelle, Quellen, Lizenzen |
| [docs/testing.md](docs/testing.md) | Teststrategie, Testarten, manuelle Checkliste |
| [docs/test_report.md](docs/test_report.md) | Vom Testrunner erzeugter Bericht des letzten Laufs |

## Projektstruktur

```text
blender_lightmap_export/   Add-on-Paket (Extension) und Kern
  core/                    Pipeline, UV, Bake, Bilder, Materialien, Metadaten, Zustand
  formats/                 GLB/glTF, FBX, USD, OBJ, glTF-Hooks
  ui/                      Panel, Operatoren, Properties, Preferences
scripts/                   batch_export.py, run_tests.py, generate_test_scenes.py,
                           generate_teapot.py, fetch_example_models.py, build_extension.py
examples/                  Utah Teapot, Toy Car, Dutch Ship (mit Lizenz-READMEs)
tests/                     unittest-Suite (läuft in Blender)
docs/                      Dokumentation
start_export.bat           Batch-Export
run_tests.bat              Tests
config.example.json        Beispielkonfiguration
```
