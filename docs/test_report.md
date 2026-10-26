# Testbericht

Erzeugt: 2026-10-26 18:31:04  
Blender: 5.2.3 LTS  
Gerät: OPTIX: NVIDIA GeForce RTX 5070 Ti; CUDA: NVIDIA GeForce RTX 5070 Ti  
Optionen: (Standard)

| Status | Anzahl |
|---|---|
| passed | 57 |
| skipped | 1 |

Status-Bedeutung: `passed` = automatisch ausgeführt und bestanden, `skipped` = implementiert, aber in diesem Lauf nicht ausgeführt (Grund in der Tabelle), `failed`/`error` = ausgeführt und fehlgeschlagen.

## tests

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `test_baking.BakingTests.test_ao_bake` | passed | 0.584 |  |
| `test_baking.BakingTests.test_auto_device_selected` | passed | 0.294 |  |
| `test_baking.BakingTests.test_bake_margin_adds_padding` | passed | 0.549 |  |
| `test_baking.BakingTests.test_combined_bake` | passed | 0.337 |  |
| `test_baking.BakingTests.test_cpu_bake_png` | passed | 0.124 |  |
| `test_baking.BakingTests.test_denoise` | passed | 0.976 |  |
| `test_baking.BakingTests.test_direct_only_vs_indirect` | passed | 0.562 |  |
| `test_baking.BakingTests.test_exr_output` | passed | 0.295 |  |
| `test_baking.BakingTests.test_failure_rolls_back_products` | passed | 0.074 |  |
| `test_baking.BakingTests.test_gpu_bake_matches_cpu` | passed | 0.363 |  |
| `test_baking.BakingTests.test_hdr_warning_for_png` | passed | 0.279 |  |
| `test_baking.BakingTests.test_instances_share_lightmap_with_warning` | passed | 0.287 |  |
| `test_baking.BakingTests.test_lighting_changes_result` | passed | 0.597 |  |
| `test_baking.BakingTests.test_missing_lights_warning_in_scene_mode` | passed | 0.279 |  |
| `test_baking.BakingTests.test_multi_light_scene` | passed | 2.833 |  |
| `test_baking.BakingTests.test_multi_material_object` | passed | 0.283 |  |
| `test_baking.BakingTests.test_multiple_objects_per_object_mode` | passed | 1.002 |  |
| `test_baking.BakingTests.test_object_without_material` | passed | 0.331 |  |
| `test_baking.BakingTests.test_object_without_material_rolled_back_on_failure` | passed | 0.334 |  |
| `test_baking.BakingTests.test_png_matches_in_memory_values_when_ldr` | passed | 0.291 |  |
| `test_baking.BakingTests.test_scene_state_restored` | passed | 0.27 |  |
| `test_baking.BakingTests.test_shared_atlas` | passed | 1.284 |  |
| `test_baking.BakingTests.test_shared_material_gets_per_object_copy` | passed | 0.554 |  |
| `test_config.ConfigTests.test_defaults_are_valid` | passed | 0.0 |  |
| `test_config.ConfigTests.test_example_config_in_repo_is_valid` | skipped | 0.0 | config.example.json noch nicht vorhanden |
| `test_config.ConfigTests.test_invalid_values_reported` | passed | 0.0 |  |
| `test_config.ConfigTests.test_load_preset_keeps_explicit_values` | passed | 0.008 |  |
| `test_config.ConfigTests.test_missing_and_broken_file` | passed | 0.001 |  |
| `test_config.ConfigTests.test_presets` | passed | 0.0 |  |
| `test_config.ConfigTests.test_roundtrip_json` | passed | 0.0 |  |
| `test_config.ConfigTests.test_type_coercion` | passed | 0.0 |  |
| `test_config.ConfigTests.test_unknown_key_strict` | passed | 0.0 |  |
| `test_materials.MaterialTests.test_bake_type_value` | passed | 0.269 |  |
| `test_materials.MaterialTests.test_bind_and_restore` | passed | 0.285 |  |
| `test_materials.MaterialTests.test_group_node_renders` | passed | 0.328 |  |
| `test_materials.MaterialTests.test_mode_switch` | passed | 0.295 |  |
| `test_materials.MaterialTests.test_original_materials_context` | passed | 0.272 |  |
| `test_materials.MaterialTests.test_preview_disabled_leaves_materials` | passed | 0.28 |  |
| `test_materials.MaterialTests.test_rebake_updates_existing_binding` | passed | 0.51 |  |
| `test_state.StateTests.test_snapshot_restores_on_exception` | passed | 0.06 |  |
| `test_state.StateTests.test_snapshot_restores_render_settings` | passed | 0.063 |  |
| `test_state.StateTests.test_snapshot_restores_selection_and_uv` | passed | 0.063 |  |
| `test_state.StateTests.test_temp_tracker_keeps_images_by_default` | passed | 0.059 |  |
| `test_state.StateTests.test_temp_tracker_material_and_mesh_copies` | passed | 0.061 |  |
| `test_state.StateTests.test_temp_tracker_removes_objects_and_data` | passed | 0.06 |  |
| `test_uv.UVTests.test_existing_method_requires_layer` | passed | 0.062 |  |
| `test_uv.UVTests.test_existing_method_uses_layer` | passed | 0.083 |  |
| `test_uv.UVTests.test_island_margin_in_pixels` | passed | 0.099 |  |
| `test_uv.UVTests.test_lightmap_pack_method` | passed | 0.071 |  |
| `test_uv.UVTests.test_lightmap_uv_created_and_existing_preserved` | passed | 0.067 |  |
| `test_uv.UVTests.test_margin_conversion` | passed | 0.06 |  |
| `test_uv.UVTests.test_nan_detected` | passed | 0.062 |  |
| `test_uv.UVTests.test_object_without_uvs` | passed | 0.102 |  |
| `test_uv.UVTests.test_out_of_bounds_detected` | passed | 0.064 |  |
| `test_uv.UVTests.test_overlap_is_detected` | passed | 0.078 |  |
| `test_uv.UVTests.test_shared_atlas_packs_without_overlap` | passed | 0.233 |  |
| `test_uv.UVTests.test_texel_density_prescale` | passed | 0.073 |  |
| `test_uv.UVTests.test_uv_coordinates_valid_and_no_overlap` | passed | 0.121 |  |
