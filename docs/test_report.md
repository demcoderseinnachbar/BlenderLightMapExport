# Testbericht

Erzeugt: 2026-10-26 18:47:46  
Blender: 5.2.3 LTS  
Gerät: OPTIX: NVIDIA GeForce RTX 5070 Ti; CUDA: NVIDIA GeForce RTX 5070 Ti  
Optionen: -k test_bat_file -k test_main_missing -k BatchArgument

| Status | Anzahl |
|---|---|
| passed | 8 |

Status-Bedeutung: `passed` = automatisch ausgeführt und bestanden, `skipped` = implementiert, aber in diesem Lauf nicht ausgeführt (Grund in der Tabelle), `failed`/`error` = ausgeführt und fehlgeschlagen.

## tests

| Test | Status | Sekunden | Hinweis |
|---|---|---|---|
| `test_batch.BatchArgumentTests.test_build_config_errors` | passed | 0.089 |  |
| `test_batch.BatchArgumentTests.test_build_config_overrides_and_preset` | passed | 0.061 |  |
| `test_batch.BatchArgumentTests.test_collect_inputs` | passed | 0.078 |  |
| `test_batch.BatchArgumentTests.test_main_config_error_exit_2` | passed | 0.064 |  |
| `test_batch.BatchArgumentTests.test_main_empty_folder_exit_2` | passed | 0.06 |  |
| `test_batch.BatchArgumentTests.test_main_in_process_single_file` | passed | 0.789 |  |
| `test_batch.BatchArgumentTests.test_main_missing_input_exit_3` | passed | 0.062 |  |
| `test_batch.BatchSubprocessTests.test_bat_file` | passed | 2.6 |  |
