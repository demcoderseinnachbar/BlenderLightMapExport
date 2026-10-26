# Testbericht

Erzeugt: 2026-10-26 19:51:10  
Blender: 5.2.3 LTS  
Gerät: OPTIX: NVIDIA GeForce RTX 5070 Ti; CUDA: NVIDIA GeForce RTX 5070 Ti  
Optionen: (Standard)

| Status | Anzahl |
|---|---|
| passed | 113 |
| failed | 1 |

Status-Bedeutung: `passed` = automatisch ausgeführt und bestanden, `skipped` = implementiert, aber in diesem Lauf nicht ausgeführt (Grund in der Tabelle), `failed`/`error` = ausgeführt und fehlgeschlagen.

## tests.test_api

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `APITests.test_export_lightmap_from_file` | passed | 0.806 |  |
| `APITests.test_import_model_and_find_metadata` | passed | 0.336 |  |
| `APITests.test_invalid_config_raises` | passed | 0.059 |  |
| `APITests.test_missing_input_file` | passed | 0.06 |  |
| `APITests.test_run_pipeline_on_scene_objects_with_preset` | passed | 11.145 |  |
| `APITests.test_unsupported_input_format` | passed | 0.06 |  |

## tests.test_baking

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `BakingTests.test_ao_bake` | passed | 0.304 |  |
| `BakingTests.test_auto_device_selected` | passed | 0.295 |  |
| `BakingTests.test_bake_margin_adds_padding` | passed | 0.59 |  |
| `BakingTests.test_combined_bake` | passed | 0.279 |  |
| `BakingTests.test_cpu_bake_png` | passed | 0.109 |  |
| `BakingTests.test_denoise` | passed | 0.807 |  |
| `BakingTests.test_direct_only_vs_indirect` | passed | 0.538 |  |
| `BakingTests.test_exr_output` | passed | 0.333 |  |
| `BakingTests.test_failure_rolls_back_products` | passed | 0.071 |  |
| `BakingTests.test_gpu_bake_matches_cpu` | passed | 0.44 |  |
| `BakingTests.test_hdr_warning_for_png` | passed | 0.325 |  |
| `BakingTests.test_instances_share_lightmap_with_warning` | passed | 0.342 |  |
| `BakingTests.test_lighting_changes_result` | passed | 0.54 |  |
| `BakingTests.test_missing_lights_warning_in_scene_mode` | passed | 0.285 |  |
| `BakingTests.test_multi_light_scene` | passed | 11.892 |  |
| `BakingTests.test_multi_material_object` | passed | 0.293 |  |
| `BakingTests.test_multiple_objects_per_object_mode` | passed | 0.939 |  |
| `BakingTests.test_object_without_material` | passed | 0.319 |  |
| `BakingTests.test_object_without_material_rolled_back_on_failure` | passed | 0.309 |  |
| `BakingTests.test_png_matches_in_memory_values_when_ldr` | passed | 0.285 |  |
| `BakingTests.test_scene_state_restored` | passed | 0.269 |  |
| `BakingTests.test_shared_atlas` | passed | 1.445 |  |
| `BakingTests.test_shared_material_gets_per_object_copy` | passed | 0.511 |  |

## tests.test_batch

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `BatchArgumentTests.test_build_config_errors` | passed | 0.061 |  |
| `BatchArgumentTests.test_build_config_overrides_and_preset` | passed | 0.06 |  |
| `BatchArgumentTests.test_collect_inputs` | passed | 0.062 |  |
| `BatchArgumentTests.test_main_config_error_exit_2` | passed | 0.06 |  |
| `BatchArgumentTests.test_main_empty_folder_exit_2` | passed | 0.061 |  |
| `BatchArgumentTests.test_main_in_process_single_file` | passed | 0.325 |  |
| `BatchArgumentTests.test_main_missing_input_exit_3` | passed | 0.062 |  |
| `BatchSubprocessTests.test_bat_file` | passed | 2.811 |  |
| `BatchSubprocessTests.test_config_file_and_unsupported_format` | passed | 5.668 |  |
| `BatchSubprocessTests.test_folder_with_broken_file_exit_1_but_others_succeed` | passed | 3.453 |  |
| `BatchSubprocessTests.test_repeated_run_overwrites` | passed | 7.428 |  |
| `BatchSubprocessTests.test_single_file_exit_0` | passed | 2.754 |  |
| `BatchSubprocessTests.test_stop_on_error` | passed | 2.081 |  |

## tests.test_config

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `ConfigTests.test_defaults_are_valid` | passed | 0.0 |  |
| `ConfigTests.test_example_config_in_repo_is_valid` | passed | 0.0 |  |
| `ConfigTests.test_invalid_values_reported` | passed | 0.0 |  |
| `ConfigTests.test_load_preset_keeps_explicit_values` | passed | 0.006 |  |
| `ConfigTests.test_missing_and_broken_file` | passed | 0.001 |  |
| `ConfigTests.test_presets` | passed | 0.0 |  |
| `ConfigTests.test_roundtrip_json` | passed | 0.0 |  |
| `ConfigTests.test_type_coercion` | passed | 0.0 |  |
| `ConfigTests.test_unknown_key_strict` | passed | 0.0 |  |

## tests.test_export

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `ExportTests.test_available_formats` | passed | 0.062 |  |
| `ExportTests.test_export_only_after_bake` | passed | 0.292 |  |
| `ExportTests.test_fbx_custom_props_without_sidecar` | passed | 0.344 |  |
| `ExportTests.test_fbx_roundtrip` | passed | 0.608 |  |
| `ExportTests.test_file_name_convention_fallback` | passed | 0.274 |  |
| `ExportTests.test_glb_custom_property_fallback_without_sidecar` | passed | 0.325 |  |
| `ExportTests.test_glb_roundtrip_with_auto_assignment` | passed | 0.603 |  |
| `ExportTests.test_glb_without_apply_only_metadata` | passed | 0.313 |  |
| `ExportTests.test_gltf_hook_with_installed_extension` | passed | 4.885 |  |
| `ExportTests.test_gltf_lightmap_as_occlusion` | passed | 0.367 |  |
| `ExportTests.test_gltf_separate_roundtrip` | passed | 0.438 |  |
| `ExportTests.test_obj_error_strategy` | passed | 0.278 |  |
| `ExportTests.test_obj_replace_with_lightmap_uv` | passed | 0.358 |  |
| `ExportTests.test_obj_two_files` | passed | 0.324 |  |
| `ExportTests.test_obj_warn_keep_original` | passed | 0.308 |  |
| `ExportTests.test_overwrite_disabled` | passed | 0.486 |  |
| `ExportTests.test_reimport_check_option` | passed | 0.51 |  |
| `ExportTests.test_shared_atlas_export_roundtrip` | passed | 2.473 |  |
| `ExportTests.test_usd_roundtrip` | passed | 0.613 |  |

## tests.test_integration_models

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `IntegrationModelTests.test_car_workflow_glb_per_object` | passed | 11.265 |  |
| `IntegrationModelTests.test_car_workflow_usd` | passed | 10.877 |  |
| `IntegrationModelTests.test_example_models_hashes` | passed | 0.162 |  |
| `IntegrationModelTests.test_ship_workflow_fbx_atlas` | passed | 10.806 |  |
| `IntegrationModelTests.test_teapot_lightmap_pack_exr` | passed | 0.749 |  |
| `IntegrationModelTests.test_teapot_workflow_glb` | passed | 1.315 |  |

## tests.test_materials

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `MaterialTests.test_bake_type_value` | passed | 0.285 |  |
| `MaterialTests.test_bind_and_restore` | passed | 0.273 |  |
| `MaterialTests.test_group_node_renders` | passed | 0.319 |  |
| `MaterialTests.test_lightmap_only_ignores_base_colour` | failed | 0.326 | AssertionError: 0.7764706611633301 not greater than 1.0000000298023224 : (0.7764706611633301, 0.3333333432674408) |
| `MaterialTests.test_mode_switch` | passed | 0.278 |  |
| `MaterialTests.test_old_group_is_upgraded` | passed | 0.275 |  |
| `MaterialTests.test_original_materials_context` | passed | 0.273 |  |
| `MaterialTests.test_preview_disabled_leaves_materials` | passed | 0.267 |  |
| `MaterialTests.test_rebake_updates_existing_binding` | passed | 0.483 |  |

## tests.test_state

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `StateTests.test_snapshot_restores_on_exception` | passed | 0.061 |  |
| `StateTests.test_snapshot_restores_render_settings` | passed | 0.061 |  |
| `StateTests.test_snapshot_restores_selection_and_uv` | passed | 0.063 |  |
| `StateTests.test_temp_tracker_keeps_images_by_default` | passed | 0.06 |  |
| `StateTests.test_temp_tracker_material_and_mesh_copies` | passed | 0.06 |  |
| `StateTests.test_temp_tracker_removes_objects_and_data` | passed | 0.061 |  |

## tests.test_ui

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `UITests.test_apply_and_restore_operators` | passed | 0.282 |  |
| `UITests.test_export_requires_baked_lightmaps` | passed | 0.06 |  |
| `UITests.test_registration_and_panels` | passed | 0.062 |  |
| `UITests.test_run_operator_blocking_in_background` | passed | 0.27 |  |
| `UITests.test_run_operator_reports_config_error` | passed | 0.063 |  |
| `UITests.test_run_operator_requires_selection` | passed | 0.06 |  |
| `UITests.test_save_and_load_config_operators` | passed | 0.063 |  |
| `UITests.test_settings_roundtrip` | passed | 0.06 |  |

## tests.test_uv

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `UVTests.test_existing_method_requires_layer` | passed | 0.062 |  |
| `UVTests.test_existing_method_uses_layer` | passed | 0.062 |  |
| `UVTests.test_feasible_margin` | passed | 0.062 |  |
| `UVTests.test_island_margin_in_pixels` | passed | 0.106 |  |
| `UVTests.test_lightmap_pack_method` | passed | 0.072 |  |
| `UVTests.test_lightmap_uv_created_and_existing_preserved` | passed | 0.068 |  |
| `UVTests.test_many_islands_reduce_margin_with_warning` | passed | 5.651 |  |
| `UVTests.test_margin_conversion` | passed | 0.067 |  |
| `UVTests.test_nan_detected` | passed | 0.067 |  |
| `UVTests.test_object_without_uvs` | passed | 0.107 |  |
| `UVTests.test_out_of_bounds_detected` | passed | 0.063 |  |
| `UVTests.test_overlap_is_detected` | passed | 0.076 |  |
| `UVTests.test_shared_atlas_packs_without_overlap` | passed | 1.04 |  |
| `UVTests.test_texel_density_prescale` | passed | 0.077 |  |
| `UVTests.test_uv_coordinates_valid_and_no_overlap` | passed | 0.121 |  |

