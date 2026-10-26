# Testbericht

Erzeugt: 2026-10-26 18:13:21  
Blender: 5.2.3 LTS  
Gerät: unbekannt (cannot import name 'baking' from 'blender_lightmap_export.core' (C:\DEV\Blender\BlenderLightMapExport\blender_lightmap_export\core\__init__.py))  
Optionen: -k test_config -k test_state

| Status | Anzahl |
|---|---|
| passed | 14 |
| skipped | 1 |

Status-Bedeutung: `passed` = automatisch ausgeführt und bestanden, `skipped` = implementiert, aber in diesem Lauf nicht ausgeführt (Grund in der Tabelle), `failed`/`error` = ausgeführt und fehlgeschlagen.

## tests

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `test_config.ConfigTests.test_defaults_are_valid` | passed | 0.0 |  |
| `test_config.ConfigTests.test_example_config_in_repo_is_valid` | skipped | 0.0 | config.example.json noch nicht vorhanden |
| `test_config.ConfigTests.test_invalid_values_reported` | passed | 0.0 |  |
| `test_config.ConfigTests.test_load_preset_keeps_explicit_values` | passed | 0.007 |  |
| `test_config.ConfigTests.test_missing_and_broken_file` | passed | 0.001 |  |
| `test_config.ConfigTests.test_presets` | passed | 0.0 |  |
| `test_config.ConfigTests.test_roundtrip_json` | passed | 0.0 |  |
| `test_config.ConfigTests.test_type_coercion` | passed | 0.0 |  |
| `test_config.ConfigTests.test_unknown_key_strict` | passed | 0.0 |  |
| `test_state.StateTests.test_snapshot_restores_on_exception` | passed | 0.088 |  |
| `test_state.StateTests.test_snapshot_restores_render_settings` | passed | 0.06 |  |
| `test_state.StateTests.test_snapshot_restores_selection_and_uv` | passed | 0.062 |  |
| `test_state.StateTests.test_temp_tracker_keeps_images_by_default` | passed | 0.06 |  |
| `test_state.StateTests.test_temp_tracker_material_and_mesh_copies` | passed | 0.061 |  |
| `test_state.StateTests.test_temp_tracker_removes_objects_and_data` | passed | 0.061 |  |
