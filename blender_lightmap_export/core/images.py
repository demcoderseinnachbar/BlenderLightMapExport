# SPDX-License-Identifier: MIT
"""Image statistics, saving (PNG/EXR, linear) and compositor based denoising."""

from __future__ import annotations

import os
from typing import Dict

import bpy
import numpy as np

from .log import get_logger
from .pipeline import LightmapExportError, LightmapInfo, PipelineContext
from . import naming

log = get_logger("images")

DENOISE_GROUP = "BLME_Denoise"


def image_pixels(img: bpy.types.Image) -> np.ndarray:
    w, h = img.size
    arr = np.empty(w * h * img.channels, dtype=np.float32)
    img.pixels.foreach_get(arr)
    return arr.reshape(h, w, img.channels)


def image_stats(img: bpy.types.Image) -> Dict[str, float]:
    px = image_pixels(img)
    if px.size == 0:
        return {"mean": 0.0, "max": 0.0, "min": 0.0, "nonzero": 0.0}
    rgb = px[..., :3]
    lum = rgb.mean(axis=2)
    return {
        "mean": float(rgb.mean()),
        "max": float(rgb.max()),
        "min": float(rgb.min()),
        "nonzero": float((lum > 1e-4).mean()),
    }


def save_image(img: bpy.types.Image, path: str, image_format: str, scene: bpy.types.Scene) -> str:
    """Save ``img`` as linear PNG (8/16 bit) or half-float EXR; relink the image to the file."""
    settings = scene.render.image_settings
    settings.color_mode = "RGB"
    if image_format in ("PNG16", "PNG8"):
        settings.file_format = "PNG"
        settings.color_depth = "16" if image_format == "PNG16" else "8"
        settings.compression = 15
    elif image_format == "EXR":
        settings.file_format = "OPEN_EXR"
        settings.color_depth = "16"
        settings.exr_codec = "ZIP"
    else:
        raise LightmapExportError(f"Unbekanntes Bildformat {image_format}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # NOTE: never assign colorspace_settings here - on a generated float image
    # this discards the baked buffer (Blender regenerates the image).
    # Non-Color images are written without view transform (verified: pixel means survive the roundtrip).
    try:
        img.save_render(path, scene=scene)
    except RuntimeError as exc:
        raise LightmapExportError(f"Lightmap konnte nicht gespeichert werden ({path}): {exc}") from exc
    if not os.path.isfile(path):
        raise LightmapExportError(f"Lightmap wurde nicht geschrieben: {path}")
    # make the datablock file-backed so that the scene references the saved file
    img.filepath = path
    img.source = "FILE"
    img.reload()
    if img.colorspace_settings.name != "Non-Color":
        img.colorspace_settings.name = "Non-Color"
    return path


def step_save_images(ctx: PipelineContext) -> None:
    cfg = ctx.cfg
    ext = cfg.lightmap_extension
    targets = ctx.extra.get("bake_targets", [])
    stats_all = ctx.extra.get("image_stats", {})
    single = len(targets) == 1
    names = naming.unique_names([t.image_name for t in targets])
    for t in targets:
        img = ctx.images[t.image_name]
        if single:
            file_name = naming.lightmap_file_name(ctx.base_name, ext)
        else:
            stem = names[t.image_name]
            if stem.endswith("_lightmap"):
                stem = stem[: -len("_lightmap")]
            file_name = naming.lightmap_file_name(stem, ext)
        path = os.path.join(ctx.lightmap_dir, file_name)
        if os.path.exists(path) and not cfg.export.overwrite:
            raise LightmapExportError(f"Lightmap-Datei existiert bereits und Überschreiben ist deaktiviert: {path}")
        stats = stats_all.get(t.image_name) or image_stats(img)
        if cfg.image.format.startswith("PNG") and stats["max"] > 1.0:
            ctx.warn(f"Lightmap '{t.image_name}' enthält Werte über 1.0 (Max {stats['max']:.2f}); "
                     f"PNG schneidet diese ab. EXR verwenden, um HDR-Beleuchtung zu erhalten.")
        save_image(img, path, cfg.image.format, ctx.scene)
        info = LightmapInfo(
            image_name=img.name,
            file_path=path,
            relative_path=naming.relpath(path, ctx.output_dir),
            objects=[o.name for o in t.objects],
            resolution=cfg.bake.resolution,
            uv_name=cfg.uv.uv_name,
            uv_index_by_object={o.name: _uv_index(o, cfg.uv.uv_name) for o in t.objects},
            bake_type=cfg.bake.type,
            image_format=cfg.image.format,
            colorspace="linear",
            stats={k: round(float(v), 5) for k, v in stats.items()},
            is_atlas=t.is_atlas,
        )
        ctx.result.lightmaps.append(info)
        log.info("Gespeichert: %s", path)


def _uv_index(obj, name):
    for i, u in enumerate(obj.data.uv_layers):
        if u.name == name:
            return i
    return -1


# --- denoising ------------------------------------------------------------------------

def denoise_image(img: bpy.types.Image, scene: bpy.types.Scene, tracker=None) -> None:
    """Denoise ``img`` in place using the compositor Denoise node (OpenImageDenoise)."""
    w, h = img.size
    ng = bpy.data.node_groups.get(DENOISE_GROUP)
    if ng is None:
        ng = bpy.data.node_groups.new(DENOISE_GROUP, "CompositorNodeTree")
        if tracker is not None:
            tracker.add_node_group(ng)
    for n in list(ng.nodes):
        ng.nodes.remove(n)
    for item in list(ng.interface.items_tree):
        ng.interface.remove(item)
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    src = ng.nodes.new("CompositorNodeImage")
    src.image = img
    dn = ng.nodes.new("CompositorNodeDenoise")
    if "HDR" in dn.inputs:
        dn.inputs["HDR"].default_value = True
    out = ng.nodes.new("NodeGroupOutput")
    ng.links.new(src.outputs["Image"], dn.inputs["Image"])
    ng.links.new(dn.outputs["Image"], out.inputs[0])

    tmp_path = os.path.join(bpy.app.tempdir or os.path.dirname(bpy.data.filepath) or os.getcwd(),
                            f"blme_denoise_{abs(hash(img.name)) % 100000}.exr")
    r = scene.render
    r.engine = "BLENDER_WORKBENCH"
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.use_compositing = True
    r.image_settings.file_format = "OPEN_EXR"
    r.image_settings.color_depth = "32"
    r.image_settings.color_mode = "RGB"
    r.filepath = tmp_path
    scene.compositing_node_group = ng
    if hasattr(scene, "use_nodes"):
        scene.use_nodes = True
    bpy.ops.render.render(write_still=True)
    if not os.path.isfile(tmp_path):
        raise LightmapExportError("Denoising: Compositor hat keine Ausgabedatei erzeugt")
    tmp = bpy.data.images.load(tmp_path)
    try:
        tmp.colorspace_settings.name = "Non-Color"
        if tuple(tmp.size) != (w, h):
            raise LightmapExportError("Denoising: Ausgabegröße stimmt nicht mit der Lightmap überein")
        src_px = image_pixels(tmp)
        dst = image_pixels(img)
        dst[..., :3] = src_px[..., :3]
        img.pixels.foreach_set(dst.ravel())
        img.update()
    finally:
        bpy.data.images.remove(tmp)
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def step_denoise(ctx: PipelineContext) -> None:
    if not ctx.cfg.bake.denoise:
        return
    for name, img in ctx.images.items():
        ctx.check_cancel()
        log.info("Entrausche '%s'", name)
        denoise_image(img, ctx.scene, ctx.temp)
        ctx.extra.setdefault("image_stats", {})[name] = image_stats(img)
