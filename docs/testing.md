# Teststrategie

## Ausführen

```bat
run_tests.bat                       rem alle Tests
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --factory-startup --python scripts\ui_smoke_test.py   rem GUI-Rauchtest (öffnet kurz ein Fenster)
run_tests.bat --no-slow             rem ohne Subprozess-/Modelltests (etwa 40 s)
run_tests.bat --no-gpu              rem GPU-Tests überspringen
run_tests.bat -k test_export        rem Filter nach Namen (mehrfach möglich)
run_tests.bat --verbose
```

Der Runner (`scripts/run_tests.py`) läuft innerhalb von Blender (`unittest`, keine externen Abhängigkeiten), schreibt `build/test_report.json` und `docs/test_report.md` und gibt Exit-Code 0 (alles grün) oder 1 zurück.

## Testarten und Status-Bedeutung

| Status im Bericht | Bedeutung |
|---|---|
| `passed` | automatisch ausgeführt und bestanden |
| `skipped` | implementiert, in diesem Lauf nicht ausgeführt (Grund in der Tabelle: `--no-slow`, fehlende GPU, fehlende Modelle) |
| `failed` / `error` | ausgeführt und fehlgeschlagen |

Markierungen: `@slow` (Subprozesse, Beispielmodelle, Denoise), `@requires_gpu`, `@needs_models`.

## Abdeckung

| Datei | Bereich | Prüft |
|---|---|---|
| `test_config.py` | Konfiguration | Defaults, JSON-Roundtrip, Validierung, Presets, fehlerhafte Dateien, `config.example.json` |
| `test_state.py` | Zustand | Snapshot/Restore auch bei Exception, TempTracker für Objekte, Bilder, Node-Gruppen, Materialkopien |
| `test_uv.py` | UV | LightmapUV erzeugt, bestehende Layer und Koordinaten unverändert, Objekt ohne UVs, Gültigkeit, Überlappung (positiv/negativ), NaN, Bereich, Island Margin in Pixeln messbar, Lightmap Pack, EXISTING, Atlas ohne Überlappung, Texeldichte, Margin-Reduktion |
| `test_baking.py` | Bake | CPU/GPU/Auto, PNG/EXR, Dateigröße/Auflösung, nicht leer, Licht ändert Ergebnis, Direct/Indirect, Multi-Material, ohne Material, mehrere Objekte, Atlas, geteiltes Material, Instanzen, AO, Combined, Bake Margin, Denoise, Zustand nach Lauf, Rollback bei Fehler, Mehrlicht-Szene |
| `test_materials.py` | Material | Binden/Wiederherstellen (Nodes und Links identisch), Modi, Bypass, Bake-Typ, Vorschau tatsächlich renderbar |
| `test_ui.py` | Add-on | Registrierung/Deregistrierung, Property↔Config, Operatoren (Bake, Fehlerfälle, Konfig-I/O, Vorschau) |
| `test_export.py` | Export/Reimport | GLB, glTF, FBX, USD, OBJ-Strategien; Sidecar; Custom-Property- und Dateinamen-Fallback; Occlusion-Option; Reimport-Prüfung; Atlas; **glTF-Import-Hook mit installierter Extension in frischem Blender**; Sichtbarkeit per Cycles-Render |
| `test_batch.py` | Batch | Argumente, Exit-Codes 0/1/2/3, Einzeldatei, Ordner mit defekter Datei, Stop-on-Error, Wiederholung, Config-Datei, nicht unterstütztes Format, `start_export.bat` |
| `test_api.py` | API | `export_lightmap`, Overrides, Fehler, Import, Metadatensuche |
| `test_integration_models.py` | Integration | Teapot (GLB, Lightmap Pack/EXR/glTF), Toy Car (GLB, USD), Dutch Ship (FBX, Atlas): vollständiger Workflow bis zum Sichtbarkeitsrender; Hash-Prüfung der Modelle |

## Manuell zu prüfende Funktionen (nicht headless automatisierbar)

| Funktion | Prüfung | Status |
|---|---|---|
| Modaler Operator mit Hintergrund-Bake | `scripts/ui_smoke_test.py` startet Blender mit Fenster, ruft *Bake & Export* über `INVOKE_DEFAULT` auf, wartet auf das Ende und schreibt `build/ui_smoke_report.json` | **automatisch verifiziert** (26.10.2026: Bake-Job, Speichern, Materialbindung, Export erfolgreich, Viewport auf Material Preview umgeschaltet) |
| Esc-Abbruch während des Bakes, Fortschrittsanzeige in der Statusleiste | Panel: *Bake & Export* mit Preset „Produktion“, Esc drücken; Szene unverändert nach Abbruch | **nicht verifiziert** (interaktiv) |
| Panel-Layout Basic/Advanced, Status-Panel, Werkzeuge | Sichtkontrolle | **nicht verifiziert** |
| glTF-Import über Dateidialog mit automatischer Zuweisung | *File > Import > glTF 2.0* auf `build/integration/...glb` | automatisch über Subprozess-Test geprüft (`test_gltf_hook_with_installed_extension`), Dialog selbst nicht |
| Lightmap-Vorschau im Viewport (Material Preview / Rendered) | Sichtkontrolle | Render-Ergebnis automatisch geprüft, Viewport nicht |

## Ergebnis des letzten Laufs

Siehe [test_report.md](test_report.md) (vom Runner erzeugt).
