# SPDX-License-Identifier: MIT
"""Add-on preferences."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, StringProperty

ADDON_ID = __package__.rsplit(".", 1)[0]  # root package of the extension


class BLME_Preferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    auto_apply_on_gltf_import: BoolProperty(
        name="Lightmaps beim glTF-Import automatisch zuweisen",
        description="Beim normalen Import (File > Import > glTF) Lightmaps über Sidecar-Datei oder "
                    "Metadaten erkennen und als Vorschau zuweisen",
        default=True,
    )
    use_background_bake: BoolProperty(
        name="Bake im Hintergrund (Oberfläche bleibt bedienbar)",
        description="Nutzt Blenders eigenen Bake-Job mit Fortschrittsanzeige in der Statusleiste. "
                    "Deaktivieren, falls der Hintergrund-Bake in der Oberfläche Probleme macht",
        default=True,
    )
    switch_viewport_shading: BoolProperty(
        name="Nach dem Bake Viewport auf Material Preview umschalten",
        description="Im Solid-Shading sind Material-Nodes und damit die Lightmap nicht sichtbar. "
                    "Schaltet 3D-Viewports, die auf Solid stehen, nach einem erfolgreichen Lauf auf Material Preview",
        default=True,
    )
    default_output_dir: StringProperty(
        name="Standard-Ausgabeverzeichnis", subtype="DIR_PATH", default="//export",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "auto_apply_on_gltf_import")
        layout.prop(self, "use_background_bake")
        layout.prop(self, "switch_viewport_shading")
        layout.prop(self, "default_output_dir")


def get_prefs(context=None):
    context = context or bpy.context
    addon = context.preferences.addons.get(ADDON_ID)
    return addon.preferences if addon else None


def register():
    bpy.utils.register_class(BLME_Preferences)


def unregister():
    bpy.utils.unregister_class(BLME_Preferences)
