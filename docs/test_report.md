# Testbericht

Erzeugt: 2026-10-26 19:51:30  
Blender: 5.2.3 LTS  
Gerät: OPTIX: NVIDIA GeForce RTX 5070 Ti; CUDA: NVIDIA GeForce RTX 5070 Ti  
Optionen: -k test_materials

| Status | Anzahl |
|---|---|
| passed | 9 |

Status-Bedeutung: `passed` = automatisch ausgeführt und bestanden, `skipped` = implementiert, aber in diesem Lauf nicht ausgeführt (Grund in der Tabelle), `failed`/`error` = ausgeführt und fehlgeschlagen.

## tests.test_materials

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `MaterialTests.test_bake_type_value` | passed | 0.539 |  |
| `MaterialTests.test_bind_and_restore` | passed | 0.359 |  |
| `MaterialTests.test_group_node_renders` | passed | 0.364 |  |
| `MaterialTests.test_lightmap_only_ignores_base_colour` | passed | 0.408 |  |
| `MaterialTests.test_mode_switch` | passed | 0.283 |  |
| `MaterialTests.test_old_group_is_upgraded` | passed | 0.281 |  |
| `MaterialTests.test_original_materials_context` | passed | 0.275 |  |
| `MaterialTests.test_preview_disabled_leaves_materials` | passed | 0.28 |  |
| `MaterialTests.test_rebake_updates_existing_binding` | passed | 0.494 |  |

