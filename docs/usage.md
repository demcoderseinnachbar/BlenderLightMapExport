# Benutzerhandbuch

## 1. Blender-Panel

*3D-Viewport > Sidebar (N) > Lightmap Exporter*

### Basic

| Feld | Bedeutung |
|---|---|
| Format | GLB, glTF, FBX, USD, OBJ oder „Kein Export“ (nur backen) |
| Zielverzeichnis | Ausgabeordner; relative Pfade (`//export`) beziehen sich auf die .blend-Datei |
| UV-Methode | Smart UV Project (Standard), Lightmap Pack, vorhandener Channel |
| Auflösung | 256 bis 8192 px |
| Island Margin (px) | Abstand zwischen UV-Inseln in Pixeln der Lightmap |
| Qualität | Preset: Vorschau (16 Samples, 512 px), Mittel (64, 1024, Denoise), Hoch (256, 2048, Denoise), Produktion (1024, 4096, Denoise), Benutzerdefiniert |

Buttons: **Bake** (UVs, Bake, Lightmap-Datei, Vorschau), **Bake & Export**, **Nur Export** (nutzt bereits gebackene Lightmaps).

Bei Umfang „Auswahl“ gilt: Ist nichts ausgewählt, werden alle sichtbaren Mesh-Objekte der Szene selektiert und verarbeitet (das Panel zeigt das vorher an). Der pro Material gewählte Anzeigemodus (Nur Lightmap, Lightmap × Materialfarbe, Original) bleibt bei erneutem Bake, Atlas-Bake, Export und Reimport erhalten; nur neu gebundene Materialien starten mit „Lightmap × Materialfarbe“.

**Sichtbarkeit:** Die Lightmap-Vorschau ist eine Material-Node-Schaltung. Blender zeigt sie nur im Viewport-Shading **Material Preview** oder **Rendered**, nicht in **Solid**. Nach einem erfolgreichen Bake schaltet das Add-on 3D-Viewports, die auf Solid stehen, automatisch auf Material Preview um (abschaltbar in den Preferences); das Status-Panel weist darauf hin und bietet den Button *Viewport: Material Preview*.

Während eines Laufs zeigt das Panel einen Fortschrittsbalken mit dem aktuellen Schritt. Bei aktivem Hintergrund-Bake erscheint Blenders Bake-Fortschritt in der Statusleiste; `Esc` im 3D-Viewport bricht ab. Nach dem Lauf stehen Zusammenfassung, Warnungen und Dateien im Unterpanel **Status und Ergebnis**.

### Advanced

| Bereich | Felder |
|---|---|
| UV | Angle Limit, Area Weight, Ausrichtung der Inseln, UVs prüfen, Eine Lightmap pro Objekt / Gemeinsamer Atlas |
| Bake | Bake-Typ (Diffuse Beleuchtung ohne Farbe, Combined, AO), Samples, Bake Margin (px), Gerät (Auto/GPU/CPU), Denoising, Direktes/Indirektes Licht, Beleuchtung (Automatisch, Nur Szene, Standard-Setup) |
| Export | Umfang (Auswahl/Szene), Texturformat (PNG 16 Bit, PNG 8 Bit, EXR), Dateiname, Überschreiben, Lightmap-Vorschau zuweisen, Reimport prüfen, OBJ-UV-Strategie, glTF: Lightmap als Occlusion |

**Konfiguration speichern/laden** schreibt bzw. liest dieselbe JSON wie der Batch.

### Werkzeuge

- Anzeige der ausgewählten Objekte: *Nur Lightmap* (reine Beleuchtung ohne Materialfarbe, ideal zum Beurteilen des Bakes), *Lightmap × Materialfarbe* (Standard nach dem Bake), *Original (Nodes bleiben)*. Dieselben drei Schalter stehen im Status-Panel direkt nach dem Bake. Der Viewport wird dabei auf Material Preview gestellt, falls er auf Solid steht.
- *Originalmaterialien wiederherstellen*: entfernt alle Vorschau-Nodes und stellt die ursprüngliche Verknüpfung zum Material Output wieder her.
- *Mit Lightmaps importieren*: importiert GLB/glTF/FBX/USD/OBJ und weist Lightmaps zu (auch unter *File > Import > Modell mit Lightmaps*).
- *Objekte mit Lightmap auswählen*.

## 2. Semantik der wichtigsten Einstellungen

### Island Margin (Pixel)

Der Wert wird als Bruchteil des fertigen 0..1-Layouts an Blender übergeben (`margin_method='FRACTION'`, `px / Auflösung`). Dadurch entspricht der Abstand tatsächlich Pixeln der Lightmap. Bei Lightmap Pack wird der Wert in Prozent des UV-Quadrats umgerechnet (maximal 1 %).

Bei sehr vielen UV-Inseln (hochaufgelöste Meshes, niedriges Angle Limit) würde der Rand die gesamte Textur verbrauchen. Standardmäßig (`uv.auto_reduce_margin`) wird der Rand dann so weit reduziert, dass die Ränder höchstens die Hälfte der Texturkante belegen; eine Warnung nennt Inselanzahl und den angewendeten Wert. Abhilfe: Auflösung erhöhen, Angle Limit erhöhen, oder die Reduktion abschalten.

### Bake Margin (Pixel)

Direkt Blenders `bake.margin`: Pixel, um die die gebackenen Inseln nach außen erweitert werden (gegen Nähte beim Filtern). Typisch 8 bis 16 px.

### Bake-Typen

| Typ | Cycles | Inhalt | Anzeige/Verwendung |
|---|---|---|---|
| Diffuse Beleuchtung (Standard) | DIFFUSE, Pässe Direct + Indirect, ohne Color | Einstrahlende Beleuchtung ohne Albedo, linear, HDR | Vorschau: Emission = Basisfarbe × Lightmap. Extern: Albedo × Lightmap |
| Combined | COMBINED | Vollständiges Shading | Vorschau: Emission = Lightmap |
| AO | AO | Verdeckung 0..1 | Vorschau: Diffuse BSDF mit Basisfarbe × AO; glTF optional als Occlusion |

Hinweis zu Cycles: Die Diffuse-Beleuchtung wird über die Diffuse-Komponente des Materials berechnet. Flächen mit **rein schwarzer** Basisfarbe oder ohne Diffuse-Anteil (Glas, reines Metall) ergeben dort eine schwarze Lightmap. Für ein materialunabhängiges Ergebnis vor dem Bake eine neutrale Basisfarbe verwenden.

### Texturformate und Farbraum

Lightmaps werden **linear** gespeichert (Farbraum Non-Color). PNG 16 Bit ist verlustfrei, schneidet aber Werte über 1.0 ab (Warnung im Log). EXR (Half Float) bewahrt HDR-Werte. Beim Laden werden die Dateien als Non-Color interpretiert.

### Beleuchtung

- *Automatisch*: vorhandene Lichter/Welt werden genutzt; fehlen sie, wird ein temporäres Setup (Sonne + Himmelslicht) erzeugt und nach dem Bake rückstandslos entfernt.
- *Nur Szene*: nie ein Setup erzeugen (Warnung, wenn kein Licht vorhanden ist).
- *Standard-Setup*: immer das Standardlicht; vorhandene Lichter werden nur für den Bake auf „hide_render“ gesetzt und danach zurückgesetzt.

### Pro Objekt oder Atlas

- *Eine pro Objekt*: jedes Objekt bekommt `<Objekt>_lightmap.<ext>` (bei mehreren Objekten im Unterordner `Lightmaps/`). Objekte mit geteilten Mesh-Daten teilen sich eine Lightmap (Warnung).
- *Gemeinsamer Atlas*: alle Objekte werden gemeinsam gepackt (Vorskalierung nach Weltoberfläche für gleichmäßige Texeldichte) und in eine Datei `<Basisname>_lightmap.<ext>` gebacken.

Materialien, die von Objekten mit unterschiedlichen Lightmaps geteilt werden, erhalten pro Objekt eine Kopie `<Material>_LM_<Objekt>`. Das Originalmaterial bleibt unverändert; *Originalmaterialien wiederherstellen* setzt die Zuordnung zurück.

## 3. Python-API

Innerhalb von Blender (Extension aktiviert oder Repository im `sys.path`):

```python
import sys
sys.path.insert(0, r"C:\DEV\Blender\BlenderLightMapExport")
from blender_lightmap_export import api, ExportConfig, export_lightmap

# Komfortfunktion
result = export_lightmap(
    input_file="C:/Models/model.glb",      # leer lassen, um die aktuelle Szene zu verwenden
    output_dir="C:/Export",
    export_format="GLB",                   # GLB | GLTF | FBX | USD | OBJ | NONE
    resolution=2048,
    samples=128,
    island_margin_px=8,
    bake_margin_px=12,
    bake_type="DIFFUSE_LIGHTING",          # COMBINED | AO
    device="AUTO",                         # GPU | CPU
    denoise=True,
    lighting="AUTO",                       # SCENE | DEFAULT_RIG
    atlas_mode="PER_OBJECT",               # SHARED_ATLAS
    image_format="PNG16",                  # PNG8 | EXR
    export__reimport_check=True,           # beliebige Config-Felder mit "__"
)
print(result.summary())
for lm in result.lightmaps:
    print(lm.image_name, lm.file_path, lm.stats)
print(result.exported_files, result.sidecar_path, result.warnings)

# Vollständige Konfiguration
cfg = ExportConfig.load("config.example.json")
cfg.output_dir = "C:/Export"
cfg.bake.resolution = 1024
result = api.run_pipeline(cfg, objects=bpy.context.selected_objects, progress=lambda f, m: print(f, m))

# Teilschritte
api.bake_lightmaps(cfg, objects)       # UVs, Bake, Datei, Vorschau
api.export_scene(cfg, objects)         # Export mit vorhandenen Lightmaps
api.apply_lightmaps(objects, "PREVIEW")        # LIGHTMAP_ONLY | ORIGINAL
api.restore_materials(objects)
report = api.import_with_lightmaps("C:/Export/model.glb")
```

Fehler werfen `LightmapExportError` mit lesbarer Meldung. `result.to_dict()` ist JSON-serialisierbar.

## 4. Batch

```bat
start_export.bat <Eingabe> <Ausgabeordner> [Optionen]
start_export.bat --config config.json [Optionen]
```

| Option | Bedeutung |
|---|---|
| `--format GLB` | Exportformat |
| `--preset HIGH` | Qualitäts-Preset |
| `--set bake.samples=32` | Beliebigen Konfigurationswert überschreiben (mehrfach) |
| `--recursive` | Unterordner einbeziehen |
| `--stop-on-error` | Nach dem ersten Fehler abbrechen (Standard: weiter) |
| `--per-file-subdir` | Pro Datei einen Unterordner (bei Ordnern automatisch) |
| `--log`, `--report` | Pfade für `export.log` und `export_report.json` |
| `--dry-run` | Nur auflisten |

Unterstützte Eingabeformate: `.glb .gltf .fbx .obj .usd .usda .usdc .usdz .blend`. Andere Dateien werden übersprungen und im Bericht als `skipped_unsupported` aufgeführt.

Exit-Codes: `0` alles erfolgreich, `1` mindestens eine Datei fehlgeschlagen, `2` Konfigurations-/Argumentfehler, `3` Umgebungsfehler (Blender nicht gefunden, Eingabe fehlt).

Jede Datei wird in einer frischen Szene verarbeitet. `export_report.json` listet pro Datei Erfolg, Fehler, Warnungen, Lightmaps und Exportdateien.

## 5. Reimport

Ausgabe eines Exports:

```text
Export/
    Model.glb
    Model.lightmaps.json      <- Sidecar: Objekte, Lightmap-Dateien, UV-Name und -Index, Bake-Parameter
    Model_lightmap.png        <- ein Objekt
    Lightmaps/                <- mehrere Objekte
        Wall_lightmap.png
        Floor_lightmap.png
```

Zuordnung beim Import in dieser Reihenfolge: Sidecar → Custom Properties im Modell (`BLME_lightmap`, `BLME_lightmap_json`) → Dateinamenskonvention `<Objekt>_lightmap.png|exr`.

- **glTF/GLB**: Mit aktivierter Extension geschieht die Zuweisung automatisch bei *File > Import > glTF 2.0* (Hook `glTF2ImportUserExtension`). Die UV-Namen gehen in glTF verloren; der Layer wird anhand des gespeicherten Index wieder in `LightmapUV` umbenannt.
- **FBX, USD, OBJ**: Blender bietet keine Import-Hooks. *Mit Lightmaps importieren* (Panel oder *File > Import*) ruft den Standardimporter auf und wendet danach die Zuordnung an. Die Python-Funktion `api.import_with_lightmaps` macht dasselbe.
- Ohne Add-on stellt kein Format die Lightmap-Materialverknüpfung her; dann ist die Sidecar-Datei die Dokumentation für andere Werkzeuge.

Details und Einschränkungen je Format: [formats.md](formats.md).
