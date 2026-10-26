# Testbericht

Erzeugt: 2026-10-26 19:01:34  
Blender: 5.2.3 LTS  
Gerät: OPTIX: NVIDIA GeForce RTX 5070 Ti; CUDA: NVIDIA GeForce RTX 5070 Ti  
Optionen: (Standard)

| Status | Anzahl |
|---|---|
| passed | 112 |

Status-Bedeutung: `passed` = automatisch ausgeführt und bestanden, `skipped` = implementiert, aber in diesem Lauf nicht ausgeführt (Grund in der Tabelle), `failed`/`error` = ausgeführt und fehlgeschlagen.

## tests

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `test_api.APITests.test_export_lightmap_from_file` | passed | 0.782 |  |
| `test_api.APITests.test_import_model_and_find_metadata` | passed | 0.358 |  |
| `test_api.APITests.test_invalid_config_raises` | passed | 0.06 |  |
| `test_api.APITests.test_missing_input_file` | passed | 0.06 |  |
| `test_api.APITests.test_run_pipeline_on_scene_objects_with_preset` | passed | 13.122 |  |
| `test_api.APITests.test_unsupported_input_format` | passed | 0.059 |  |
| `test_baking.BakingTests.test_ao_bake` | passed | 0.289 |  |
| `test_baking.BakingTests.test_auto_device_selected` | passed | 0.281 |  |
| `test_baking.BakingTests.test_bake_margin_adds_padding` | passed | 0.492 |  |
| `test_baking.BakingTests.test_combined_bake` | passed | 0.282 |  |
| `test_baking.BakingTests.test_cpu_bake_png` | passed | 0.106 |  |
| `test_baking.BakingTests.test_denoise` | passed | 0.77 |  |
| `test_baking.BakingTests.test_direct_only_vs_indirect` | passed | 0.545 |  |
| `test_baking.BakingTests.test_exr_output` | passed | 0.379 |  |
| `test_baking.BakingTests.test_failure_rolls_back_products` | passed | 0.063 |  |
| `test_baking.BakingTests.test_gpu_bake_matches_cpu` | passed | 0.362 |  |
| `test_baking.BakingTests.test_hdr_warning_for_png` | passed | 0.287 |  |
| `test_baking.BakingTests.test_instances_share_lightmap_with_warning` | passed | 0.298 |  |
| `test_baking.BakingTests.test_lighting_changes_result` | passed | 0.481 |  |
| `test_baking.BakingTests.test_missing_lights_warning_in_scene_mode` | passed | 0.275 |  |
| `test_baking.BakingTests.test_multi_light_scene` | passed | 11.826 |  |
| `test_baking.BakingTests.test_multi_material_object` | passed | 0.313 |  |
| `test_baking.BakingTests.test_multiple_objects_per_object_mode` | passed | 0.938 |  |
| `test_baking.BakingTests.test_object_without_material` | passed | 0.35 |  |
| `test_baking.BakingTests.test_object_without_material_rolled_back_on_failure` | passed | 0.355 |  |
| `test_baking.BakingTests.test_png_matches_in_memory_values_when_ldr` | passed | 0.268 |  |
| `test_baking.BakingTests.test_scene_state_restored` | passed | 0.268 |  |
| `test_baking.BakingTests.test_shared_atlas` | passed | 1.349 |  |
| `test_baking.BakingTests.test_shared_material_gets_per_object_copy` | passed | 0.48 |  |
| `test_batch.BatchArgumentTests.test_build_config_errors` | passed | 0.062 |  |
| `test_batch.BatchArgumentTests.test_build_config_overrides_and_preset` | passed | 0.059 |  |
| `test_batch.BatchArgumentTests.test_collect_inputs` | passed | 0.062 |  |
| `test_batch.BatchArgumentTests.test_main_config_error_exit_2` | passed | 0.061 |  |
| `test_batch.BatchArgumentTests.test_main_empty_folder_exit_2` | passed | 0.062 |  |
| `test_batch.BatchArgumentTests.test_main_in_process_single_file` | passed | 0.325 |  |
| `test_batch.BatchArgumentTests.test_main_missing_input_exit_3` | passed | 0.061 |  |
| `test_batch.BatchSubprocessTests.test_bat_file` | passed | 2.729 |  |
| `test_batch.BatchSubprocessTests.test_config_file_and_unsupported_format` | passed | 5.656 |  |
| `test_batch.BatchSubprocessTests.test_folder_with_broken_file_exit_1_but_others_succeed` | passed | 3.215 |  |
| `test_batch.BatchSubprocessTests.test_repeated_run_overwrites` | passed | 7.399 |  |
| `test_batch.BatchSubprocessTests.test_single_file_exit_0` | passed | 2.612 |  |
| `test_batch.BatchSubprocessTests.test_stop_on_error` | passed | 2.048 |  |
| `test_config.ConfigTests.test_defaults_are_valid` | passed | 0.0 |  |
| `test_config.ConfigTests.test_example_config_in_repo_is_valid` | passed | 0.0 |  |
| `test_config.ConfigTests.test_invalid_values_reported` | passed | 0.0 |  |
| `test_config.ConfigTests.test_load_preset_keeps_explicit_values` | passed | 0.011 |  |
| `test_config.ConfigTests.test_missing_and_broken_file` | passed | 0.001 |  |
| `test_config.ConfigTests.test_presets` | passed | 0.0 |  |
| `test_config.ConfigTests.test_roundtrip_json` | passed | 0.0 |  |
| `test_config.ConfigTests.test_type_coercion` | passed | 0.0 |  |
| `test_config.ConfigTests.test_unknown_key_strict` | passed | 0.0 |  |
| `test_export.ExportTests.test_available_formats` | passed | 0.06 |  |
| `test_export.ExportTests.test_export_only_after_bake` | passed | 0.307 |  |
| `test_export.ExportTests.test_fbx_custom_props_without_sidecar` | passed | 0.365 |  |
| `test_export.ExportTests.test_fbx_roundtrip` | passed | 0.593 |  |
| `test_export.ExportTests.test_file_name_convention_fallback` | passed | 0.264 |  |
| `test_export.ExportTests.test_glb_custom_property_fallback_without_sidecar` | passed | 0.342 |  |
| `test_export.ExportTests.test_glb_roundtrip_with_auto_assignment` | passed | 0.597 |  |
| `test_export.ExportTests.test_glb_without_apply_only_metadata` | passed | 0.316 |  |
| `test_export.ExportTests.test_gltf_hook_with_installed_extension` | passed | 4.977 |  |
| `test_export.ExportTests.test_gltf_lightmap_as_occlusion` | passed | 0.291 |  |
| `test_export.ExportTests.test_gltf_separate_roundtrip` | passed | 0.368 |  |
| `test_export.ExportTests.test_obj_error_strategy` | passed | 0.273 |  |
| `test_export.ExportTests.test_obj_replace_with_lightmap_uv` | passed | 0.352 |  |
| `test_export.ExportTests.test_obj_two_files` | passed | 0.319 |  |
| `test_export.ExportTests.test_obj_warn_keep_original` | passed | 0.331 |  |
| `test_export.ExportTests.test_overwrite_disabled` | passed | 0.5 |  |
| `test_export.ExportTests.test_reimport_check_option` | passed | 0.56 |  |
| `test_export.ExportTests.test_shared_atlas_export_roundtrip` | passed | 2.048 |  |
| `test_export.ExportTests.test_usd_roundtrip` | passed | 0.706 |  |
| `test_integration_models.IntegrationModelTests.test_car_workflow_glb_per_object` | passed | 11.427 |  |
| `test_integration_models.IntegrationModelTests.test_car_workflow_usd` | passed | 11.126 |  |
| `test_integration_models.IntegrationModelTests.test_example_models_hashes` | passed | 0.155 |  |
| `test_integration_models.IntegrationModelTests.test_ship_workflow_fbx_atlas` | passed | 10.537 |  |
| `test_integration_models.IntegrationModelTests.test_teapot_lightmap_pack_exr` | passed | 0.816 |  |
| `test_integration_models.IntegrationModelTests.test_teapot_workflow_glb` | passed | 1.154 |  |
| `test_materials.MaterialTests.test_bake_type_value` | passed | 0.266 |  |
| `test_materials.MaterialTests.test_bind_and_restore` | passed | 0.277 |  |
| `test_materials.MaterialTests.test_group_node_renders` | passed | 0.321 |  |
| `test_materials.MaterialTests.test_mode_switch` | passed | 0.317 |  |
| `test_materials.MaterialTests.test_original_materials_context` | passed | 0.289 |  |
| `test_materials.MaterialTests.test_preview_disabled_leaves_materials` | passed | 0.284 |  |
| `test_materials.MaterialTests.test_rebake_updates_existing_binding` | passed | 0.493 |  |
| `test_state.StateTests.test_snapshot_restores_on_exception` | passed | 0.06 |  |
| `test_state.StateTests.test_snapshot_restores_render_settings` | passed | 0.063 |  |
| `test_state.StateTests.test_snapshot_restores_selection_and_uv` | passed | 0.065 |  |
| `test_state.StateTests.test_temp_tracker_keeps_images_by_default` | passed | 0.07 |  |
| `test_state.StateTests.test_temp_tracker_material_and_mesh_copies` | passed | 0.086 |  |
| `test_state.StateTests.test_temp_tracker_removes_objects_and_data` | passed | 0.074 |  |
| `test_ui.UITests.test_apply_and_restore_operators` | passed | 0.311 |  |
| `test_ui.UITests.test_export_requires_baked_lightmaps` | passed | 0.066 |  |
| `test_ui.UITests.test_registration_and_panels` | passed | 0.065 |  |
| `test_ui.UITests.test_run_operator_blocking_in_background` | passed | 0.297 |  |
| `test_ui.UITests.test_run_operator_reports_config_error` | passed | 0.094 |  |
| `test_ui.UITests.test_run_operator_requires_selection` | passed | 0.073 |  |
| `test_ui.UITests.test_save_and_load_config_operators` | passed | 0.073 |  |
| `test_ui.UITests.test_settings_roundtrip` | passed | 0.063 |  |
| `test_uv.UVTests.test_existing_method_requires_layer` | passed | 0.062 |  |
| `test_uv.UVTests.test_existing_method_uses_layer` | passed | 0.062 |  |
| `test_uv.UVTests.test_feasible_margin` | passed | 0.06 |  |
| `test_uv.UVTests.test_island_margin_in_pixels` | passed | 0.103 |  |
| `test_uv.UVTests.test_lightmap_pack_method` | passed | 0.072 |  |
| `test_uv.UVTests.test_lightmap_uv_created_and_existing_preserved` | passed | 0.068 |  |
| `test_uv.UVTests.test_many_islands_reduce_margin_with_warning` | passed | 5.647 |  |
| `test_uv.UVTests.test_margin_conversion` | passed | 0.068 |  |
| `test_uv.UVTests.test_nan_detected` | passed | 0.063 |  |
| `test_uv.UVTests.test_object_without_uvs` | passed | 0.108 |  |
| `test_uv.UVTests.test_out_of_bounds_detected` | passed | 0.062 |  |
| `test_uv.UVTests.test_overlap_is_detected` | passed | 0.078 |  |
| `test_uv.UVTests.test_shared_atlas_packs_without_overlap` | passed | 1.076 |  |
| `test_uv.UVTests.test_texel_density_prescale` | passed | 0.079 |  |
| `test_uv.UVTests.test_uv_coordinates_valid_and_no_overlap` | passed | 0.118 |  |
