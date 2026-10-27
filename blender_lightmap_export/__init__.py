# SPDX-License-Identifier: MIT
"""BlenderLightMapExport – Lightmap baking and export for Blender 5.2 LTS.

The package works in two ways:

* as a Blender extension (``bl_ext.<repo>.blender_lightmap_export``) with a
  user interface registered through :func:`register`;
* as a plain Python package imported from ``sys.path`` in headless runs
  (``scripts/batch_export.py``) – in that case nothing needs to be registered,
  the core API in :mod:`blender_lightmap_export.api` is used directly.

Both entry points share the same core implementation in ``core/`` and
``formats/``.
"""

from . import api, config  # noqa: F401  (public API re-export)
from .config import ExportConfig  # noqa: F401
from .api import (  # noqa: F401
    export_lightmap,
    run_pipeline,
    bake_lightmaps,
    export_scene,
    apply_lightmaps,
    restore_materials,
    import_with_lightmaps,
    LightmapExportError,
)

__version__ = "0.1.0"

# --- glTF add-on hooks ------------------------------------------------------
# The bundled glTF exporter/importer looks for these names on enabled add-on
# modules. They must live at package top level.
try:
    from .formats.gltf_hooks import (  # noqa: F401
        glTF2ExportUserExtension,
        glTF2ImportUserExtension,
        draw_import,
    )
except Exception:  # pragma: no cover - keeps the package importable without hooks
    pass


def register():
    """Register UI classes. Only called when running as an add-on/extension."""
    from . import ui

    ui.register()


def unregister():
    from . import ui

    ui.unregister()
