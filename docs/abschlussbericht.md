# Abschlussbericht BlenderLightMapExport

Stand: 26.10.2026, Blender 5.2.3 LTS (Windows 11, NVIDIA RTX 5070 Ti).

## 1. Implementierte Funktionen

**Kern (eine Implementierung für Add-on, API und Batch)**

- Import von GLB/glTF, FBX, OBJ, USD und .blend; Arbeiten auf der aktuellen Szene oder einer Datei.
- UV-Channel `LightmapUV` per Daten-API, bestehende UV-Layer, Render-UV und Koordinaten bleiben unverändert (getestet).
- UV-Methoden: Smart UV Project (Angle Limit, Area Weight, Ausrichtung, Island Margin in Pixeln), Lightmap Pack, vorhandener Channel. Island Margin wird als Bruchteil des Endlayouts übergeben und entspricht damit Pixeln der Lightmap; bei sehr vielen Inseln wird der Rand mit Warnung reduziert.
- UV-Prüfung (rasterbasiert, numpy): Überlappung, Bereich 0..1, NaN/Inf, Mindestabstand zwischen Inseln; Inselerkennung über Mesh-Kanten mit identischen UVs.
- Cycles-Baking: Diffuse Beleuchtung ohne Materialfarbe (Standard), Combined, Ambient Occlusion; Direct/Indirect schaltbar; Auflösung 256 bis 8192; Samples; Bake Margin in Pixeln; CPU/GPU/Auto (OptiX, CUDA, HIP, oneAPI); Geräteeinstellungen werden zurückgesetzt.
- Mehrere Material-Slots pro Objekt, Objekte ohne Material (neutrales Material wird zugewiesen und gemeldet), geteilte Materialien (temporäre Bake-Kopien, Vorschau-Kopien pro Objekt), Instanzen (gemeinsame Lightmap mit Warnung).
- Beleuchtung: Szene, Automatisch (Standard-Setup nur wenn kein Licht), Standard-Setup; temporäres Setup wird rückstandslos entfernt.
- Modus A (eine Lightmap pro Objekt, Unterordner `Lightmaps/`) und Modus B (gemeinsamer Atlas über `pack_islands` mit Texeldichte-Vorskalierung).
- Lightmap-Dateien PNG 16/8 Bit (linear) oder EXR (HDR), Warnung bei Clipping; optionales Denoising über Compositor (OpenImageDenoise).
- Materialvorschau als Node-Gruppe `BLME_LightmapShader` (Emission = Basisfarbe × Lightmap; Combined; AO), umschaltbar, vollständig wiederherstellbar (Nodes und Links identisch, getestet).
- Export GLB, glTF, FBX, USD, OBJ mit Capabilities und Warnungen; OBJ mit vier expliziten Strategien statt stillem UV-Verlust; glTF optional mit Lightmap als `occlusionTexture` (TEXCOORD_1).
- Metadaten: Sidecar `<Modell>.lightmaps.json` plus Custom Properties (Dict und JSON-String) am Objekt; glTF-Export-Hook schreibt Zusammenfassung in `asset.extras`.
- Reimport: Zuordnung über Sidecar, Custom Properties oder Dateinamen; UV-Name wird bei glTF über den Index wiederhergestellt; glTF-Import-Hook für automatische Zuweisung beim normalen Blender-Import mit aktivierter Extension; eigener Operator für alle Formate; optionale Reimport-Prüfung direkt nach dem Export.
- Zustandssicherung: Snapshot der Render-/Bake-/Bild-/View-Einstellungen, Welt, Compositor, UV-Aktivzustand, Selektion, Modus; Undo-Tracker für temporäre und produktive Änderungen; Rollback bei Fehlern (getestet).

**Blender-Add-on (Extension)**: N-Panel „Lightmap Exporter“ mit Basic/Advanced, Presets, Status-/Ergebnis-Panel, Werkzeuge; modaler Operator mit Fortschrittsbalken, Hintergrund-Bake über Blender-Job und Esc-Abbruch (Fallback blockierend); Operatoren für Vorschau, Wiederherstellung, Import mit Lightmaps (auch im File-Import-Menü), Konfiguration speichern/laden; Preferences.

**Python-API**: `export_lightmap`, `run_pipeline`, `bake_lightmaps`, `export_scene`, `apply_lightmaps`, `restore_materials`, `import_model`, `import_with_lightmaps`, `find_lightmap_metadata`; `ExportConfig` als Dataclass mit JSON und Validierung.

**Batch**: `start_export.bat` und `scripts/batch_export.py` (Einzeldatei, Ordner, rekursiv, Konfigurationsdatei, Overrides, Logdatei, JSON-Bericht, Exit-Codes 0/1/2/3, Fehlerisolation pro Datei).

**Beispielmodelle**: Utah Teapot (aus Original-Bezier-Daten generiert), Toy Car (Khronos, CC0), Dutch Ship Large 01 (Poly Haven, CC0, 1k) mit README, `SOURCE.json` (URL, SHA-256, Datum) und Hash-Prüfung; zehn synthetische Testszenen.

## 2. Erfolgreiche Tests (tatsächlich ausgeführt)

Letzter Gesamtlauf: **112 Tests, 112 bestanden, 0 übersprungen, 0 fehlgeschlagen** (`run_tests.bat`, rund 2 Minuten, GPU OptiX aktiv). Vollständige Tabelle: [test_report.md](test_report.md).

| Bereich | Tests | Enthält |
|---|---|---|
| Konfiguration | 8 | Validierung, Presets, Fehlerdateien, config.example.json |
| Zustand | 6 | Snapshot/Restore inkl. Exception, Tracker |
| UV | 15 | Erzeugung, Erhalt, Gültigkeit, Overlap, NaN, Bereich, Pixel-Margin, Lightmap Pack, Atlas, Texeldichte, Margin-Reduktion |
| Baking | 24 | CPU und GPU, PNG/EXR, Licht- und Passabhängigkeit, Multi-Material, Atlas, geteilte Materialien, AO/Combined, Bake Margin, Denoise, Rollback |
| Materialien | 7 | Binden/Wiederherstellen, Modi, Bypass, Render der Vorschau |
| UI | 8 | Registrierung, Property↔Config, Operatoren |
| Export/Reimport | 20 | GLB, glTF, FBX, USD, OBJ-Strategien, Sidecar, Fallbacks, Occlusion, Reimport-Prüfung, **Import-Hook mit installierter ZIP in frischem Blender**, Sichtbarkeitsrender |
| Batch | 13 | Argumente, Exit-Codes, Subprozesse, defekte Dateien, Wiederholung, .bat |
| API | 5 | Komfortfunktion, Overrides, Fehler |
| Integration | 6 | Teapot (GLB; Lightmap Pack/EXR/glTF), Toy Car (GLB, USD), Dutch Ship (FBX, Atlas), Modell-Hashes |

Jeder Integrationstest durchläuft: Import → Prüfung vorhandener UVs → LightmapUV → Unwrap → Cycles-Bake → Datei → Export → Reimport-Prüfung → frische Szene → Import mit automatischer Zuweisung → Prüfung der UV-Layer, Materialbindung, Bilddatei und ein Cycles-Render ohne Lichter, in dem die Lightmap-Emission sichtbar sein muss.

## 3. Fehlgeschlagene, übersprungene und nicht verifizierte Punkte

- Fehlgeschlagen: keine.
- Übersprungen im Abschlusslauf: keine (GPU und Modelle vorhanden). Ohne GPU oder mit `--no-slow` werden die entsprechend markierten Tests als `skipped` ausgewiesen.
- **Automatisch in der Oberfläche verifiziert:** der modale Operator mit Hintergrund-Bake über den Blender-Job (`scripts/ui_smoke_test.py`, Blender mit Fenster, Ergebnis in `build/ui_smoke_report.json`): Bake, Speichern, Materialbindung, Export und das Umschalten des Viewports auf Material Preview.
- **Nicht verifiziert (nur interaktiv prüfbar):** Esc-Abbruch während des Bakes, Fortschrittsanzeige in der Statusleiste, Panel-Darstellung, Viewport-Anzeige per Sichtkontrolle, glTF-Import über den Dateidialog (der Hook selbst ist per Subprozess getestet). Checkliste in [testing.md](testing.md). Schlägt der Hintergrund-Bake in der Oberfläche fehl, kann er in den Preferences abgeschaltet werden.

## 4. Bekannte Einschränkungen

- OBJ transportiert nur ein UV-Set und keine Metadaten (vier explizite Strategien, Dokumentation in formats.md).
- glTF speichert keine UV-Namen; Wiederherstellung über Index und Metadaten. Ohne Add-on stellt kein Format die Materialverknüpfung her.
- Cycles bietet kein Denoising beim Baken; Denoising erfolgt als Nachbearbeitung mit OpenImageDenoise ohne Albedo/Normal-Hilfsbilder.
- Transmissive Materialien (Glas) ergeben bei Diffuse-Lighting-Bakes eine schwarze Lightmap (wird gemeldet).
- Sehr viele UV-Inseln (hochaufgelöste Meshes) erzwingen kleine Ränder; die automatische Reduktion warnt und verweist auf Auflösung/Angle Limit.
- PNG begrenzt HDR-Werte auf 1.0 (Warnung); EXR empfohlen für Diffuse-Lighting-Daten.
- Instanzen (geteilte Mesh-Daten) erhalten eine gemeinsame Lightmap; Generatormodifikatoren können überlappende Lightmap-UVs erzeugen (Warnung).
- Objekte ohne Material erhalten dauerhaft ein neutrales Material `BLME_Material_<Objekt>`.
- Deprecation-Hinweis von Blender zu `Material.use_nodes` (wird in Blender 6.0 entfernt); für 5.2 korrekt.

## 5. Installation (Kurzfassung)

1. `dist/blender_lightmap_export-0.1.0.zip` in Blender über *Edit > Preferences > Get Extensions > Install from Disk* installieren.
2. Panel: 3D-Viewport, Sidebar `N`, Reiter **Lightmap Exporter**.
3. Details: [installation.md](installation.md).

## 6. Batch-Betrieb (Kurzfassung)

```bat
start_export.bat C:\Models\model.glb C:\Export
start_export.bat C:\Models C:\Export --format FBX --preset HIGH --recursive
start_export.bat --config config.example.json
set BLENDER_EXE=D:\Blender\blender.exe   rem abweichender Blender-Pfad
```

Ergebnis: Modelldatei, Lightmaps, Sidecar, `export.log`, `export_report.json`; Exit-Code 0/1/2/3. Details: [usage.md](usage.md), Abschnitt 4.

## 7. Python-Beispiele

```python
import sys; sys.path.insert(0, r"C:\DEV\Blender\BlenderLightMapExport")
from blender_lightmap_export import export_lightmap, api, ExportConfig

result = export_lightmap(input_file="C:/Models/model.glb", output_dir="C:/Export", export_format="GLB",
                         resolution=2048, samples=128, island_margin_px=8, bake_margin_px=12)
print(result.summary(), result.exported_files, result.sidecar_path)

cfg = ExportConfig.load("config.example.json"); cfg.output_dir = "C:/Export"
result = api.run_pipeline(cfg, objects=bpy.context.selected_objects)
api.import_with_lightmaps("C:/Export/model.glb")
```

## 8. Speicherorte

- Extension-ZIP: `dist/blender_lightmap_export-0.1.0.zip` (identisch mit `build/…`, erzeugt durch `scripts/build_extension.py --verify`).
- Beispielkonfiguration: `config.example.json` (Teapot → `export/teapot`, GLB, Preset MEDIUM, Reimport-Prüfung).
- Testbericht: `docs/test_report.md`, `build/test_report.json`.

## 9. Git-Commits

| Meilenstein | Commit |
|---|---|
| 1 Paketgerüst, Konfiguration, Logging, Zustandssicherung, Testrunner | `1a1cf97` |
| 2 UV-Erzeugung, Cycles-Baking, Lightmap-Dateien, Materialvorschau | `68bcd40` |
| 3 Blender-Add-on-Oberfläche | `68e4ce3` |
| 4 Export, Reimport und Lightmap-Metadaten | `871e77a` |
| 5 Python-API, Batch, Beispielkonfiguration | `680fe96` |
| 6 Beispielmodelle und Testgeometrien | `6846d18` |
| 7 Dokumentation, Extension-ZIP, Abschlusstest | siehe `git log` |

Kein Push erfolgt.
