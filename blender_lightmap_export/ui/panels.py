# SPDX-License-Identifier: MIT
"""Sidebar panels (View3D > N > Lightmap Exporter)."""

from __future__ import annotations

import bpy

from ..core import metadata


class BLME_PT_base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lightmap Exporter"


class BLME_PT_main(BLME_PT_base, bpy.types.Panel):
    bl_label = "Lightmap Exporter"
    bl_idname = "BLME_PT_main"

    def draw(self, context):
        layout = self.layout
        s = context.scene.blme
        row = layout.row(align=True)
        row.prop(s, "show_advanced", text="Basic", toggle=True, invert_checkbox=True)
        row.prop(s, "show_advanced", text="Advanced", toggle=True)

        col = layout.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(s, "export_format")
        col.prop(s, "output_dir")
        col.prop(s, "uv_method")
        if s.uv_method == "EXISTING" or s.show_advanced:
            col.prop(s, "uv_name")
        col.prop(s, "resolution")
        col.prop(s, "island_margin_px")
        col.prop(s, "preset")

        if s.is_running:
            box = layout.box()
            box.progress(factor=s.progress, text=s.status_text or "Läuft ...", type="BAR")
            box.label(text="Esc im 3D-Viewport bricht ab", icon="INFO")
        else:
            row = layout.row(align=True)
            row.scale_y = 1.4
            op = row.operator("blme.run", text="Bake", icon="RENDER_STILL")
            op.mode = "BAKE"
            op = row.operator("blme.run", text="Bake & Export", icon="EXPORT")
            op.mode = "FULL"
            row = layout.row(align=True)
            op = row.operator("blme.run", text="Nur Export", icon="FILE_TICK")
            op.mode = "EXPORT"
            sel = [o for o in context.selected_objects if o.type == "MESH"]
            if s.export_scope == "SELECTED" and not sel:
                n = len([o for o in context.scene.objects if o.type == "MESH"])
                layout.label(text=f"Keine Auswahl: alle {n} Mesh-Objekte der Szene", icon="INFO")
            elif s.export_scope == "SELECTED":
                layout.label(text=f"{len(sel)} Mesh-Objekt(e) ausgewählt", icon="MESH_DATA")


class BLME_PT_advanced(BLME_PT_base, bpy.types.Panel):
    bl_label = "Erweiterte Einstellungen"
    bl_idname = "BLME_PT_advanced"
    bl_parent_id = "BLME_PT_main"

    @classmethod
    def poll(cls, context):
        return context.scene.blme.show_advanced

    def draw(self, context):
        layout = self.layout
        s = context.scene.blme
        layout.use_property_split = True
        layout.use_property_decorate = False

        box = layout.box()
        box.label(text="UV", icon="UV")
        box.prop(s, "angle_limit_deg")
        box.prop(s, "area_weight")
        box.prop(s, "rotate_method")
        box.prop(s, "validate_uvs")
        box.prop(s, "atlas_mode")

        box = layout.box()
        box.label(text="Bake", icon="RENDER_STILL")
        box.prop(s, "bake_type")
        box.prop(s, "samples")
        box.prop(s, "bake_margin_px")
        box.prop(s, "device")
        box.prop(s, "denoise")
        row = box.row(align=True)
        row.prop(s, "use_direct", toggle=True)
        row.prop(s, "use_indirect", toggle=True)
        box.prop(s, "lighting_mode")

        box = layout.box()
        box.label(text="Export", icon="EXPORT")
        box.prop(s, "export_scope")
        box.prop(s, "image_format")
        box.prop(s, "base_name")
        box.prop(s, "overwrite")
        box.prop(s, "apply_lightmap_preview")
        box.prop(s, "reimport_check")
        if s.export_format == "OBJ":
            box.prop(s, "obj_uv_strategy")
            box.label(text="OBJ transportiert nur ein UV-Set", icon="ERROR")
        if s.export_format in ("GLB", "GLTF"):
            box.prop(s, "gltf_lightmap_as_occlusion")

        row = layout.row(align=True)
        row.operator("blme.save_config", icon="FILE_TICK")
        row.operator("blme.load_config", icon="FILEBROWSER")


class BLME_PT_status(BLME_PT_base, bpy.types.Panel):
    bl_label = "Status und Ergebnis"
    bl_idname = "BLME_PT_status"
    bl_parent_id = "BLME_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        s = context.scene.blme
        if s.last_error:
            box = layout.box()
            box.alert = True
            for line in s.last_error.splitlines()[:6]:
                box.label(text=line, icon="ERROR")
        if s.last_summary:
            box = layout.box()
            for line in s.last_summary.splitlines():
                box.label(text=line)
            shading = next((sp.shading.type for a in context.screen.areas if a.type == "VIEW_3D"
                            for sp in a.spaces if sp.type == "VIEW_3D"), None)
            if shading == "SOLID":
                box.label(text="Solid-Shading zeigt keine Lightmap", icon="ERROR")
                box.operator("blme.material_preview", icon="SHADING_TEXTURE")
            else:
                box.label(text="Sichtbar in Material Preview / Rendered", icon="SHADING_TEXTURE")
            row = box.row(align=True)
            op = row.operator("blme.apply_preview", text="Nur Lightmap")
            op.mode = "LIGHTMAP_ONLY"
            op = row.operator("blme.apply_preview", text="Mit Farbe")
            op.mode = "PREVIEW"
            op = row.operator("blme.apply_preview", text="Original")
            op.mode = "ORIGINAL"
        if s.last_warnings:
            box = layout.box()
            box.label(text="Warnungen", icon="INFO")
            for line in s.last_warnings.splitlines()[:12]:
                box.label(text=line[:90])
        if s.last_files:
            box = layout.box()
            box.label(text="Dateien", icon="FILE")
            for line in s.last_files.splitlines()[:12]:
                box.label(text=line[-80:])
            box.operator("blme.open_output", icon="FILE_FOLDER")
        if not (s.last_error or s.last_summary):
            layout.label(text="Noch kein Durchlauf", icon="INFO")


class BLME_PT_tools(BLME_PT_base, bpy.types.Panel):
    bl_label = "Werkzeuge"
    bl_idname = "BLME_PT_tools"
    bl_parent_id = "BLME_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Anzeige (ausgewählte Objekte):")
        op = col.operator("blme.apply_preview", text="Nur Lightmap", icon="LIGHT_DATA")
        op.mode = "LIGHTMAP_ONLY"
        op = col.operator("blme.apply_preview", text="Lightmap × Materialfarbe", icon="HIDE_OFF")
        op.mode = "PREVIEW"
        op = col.operator("blme.apply_preview", text="Original (Nodes bleiben)", icon="HIDE_ON")
        op.mode = "ORIGINAL"
        col.operator("blme.restore_materials", icon="LOOP_BACK")
        col.operator("blme.material_preview", icon="SHADING_TEXTURE")
        layout.separator()
        layout.operator("blme.import_with_lightmaps", icon="IMPORT")
        layout.operator("blme.select_lightmapped", icon="RESTRICT_SELECT_OFF")
        obj = context.active_object
        if obj is not None and obj.type == "MESH":
            meta = metadata.read_object_metadata(obj)
            if meta:
                box = layout.box()
                box.label(text=f"{obj.name}", icon="MESH_DATA")
                box.label(text=f"Lightmap: {meta.get('file', '?')}")
                box.label(text=f"UV: {meta.get('uv_name', '?')}  Typ: {meta.get('bake_type', '?')}")


CLASSES = (BLME_PT_main, BLME_PT_advanced, BLME_PT_status, BLME_PT_tools)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
