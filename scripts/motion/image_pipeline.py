"""Normalize coherent generated motion sheets into runtime frames and previews."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageSequence

from pet.chroma_matte import key_family_mask, matte_chroma_background


def parse_hex_color(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError("chroma key must be a six-digit hex color")
    try:
        return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError as error:
        raise ValueError("chroma key must be a six-digit hex color") from error


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zero_hidden_rgb(image: Image.Image, alpha_cutoff: int = 3) -> Image.Image:
    values = np.array(image.convert("RGBA"), dtype=np.uint8)
    hidden = values[:, :, 3] <= alpha_cutoff
    values[hidden] = 0
    return Image.fromarray(values, mode="RGBA")


def _alpha_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    return image.getchannel("A").getbbox()


def _premultiplied_resize(
    image: Image.Image,
    size: tuple[int, int],
) -> Image.Image:
    return _zero_hidden_rgb(
        image.convert("RGBa")
        .resize(size, Image.Resampling.LANCZOS)
        .convert("RGBA")
    )


def _grid_bounds(length: int, count: int) -> list[tuple[int, int]]:
    edges = [round(index * length / count) for index in range(count + 1)]
    return [(edges[index], edges[index + 1]) for index in range(count)]


def _projection_runs(
    values: list[int],
    minimum: int,
    close_gap: int,
) -> list[tuple[int, int]]:
    active = [value >= minimum for value in values]
    index = 0
    while index < len(active):
        if active[index]:
            index += 1
            continue
        start = index
        while index < len(active) and not active[index]:
            index += 1
        if start > 0 and index < len(active) and index - start <= close_gap:
            for fill in range(start, index):
                active[fill] = True
    runs: list[tuple[int, int]] = []
    index = 0
    while index < len(active):
        if not active[index]:
            index += 1
            continue
        start = index
        while index < len(active) and active[index]:
            index += 1
        runs.append((start, index))
    return runs


def _projection_bounds(
    image: Image.Image,
    columns: int,
    rows: int,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    alpha = np.array(image.getchannel("A"), dtype=np.uint8) > 16
    x_runs = _projection_runs(
        alpha.sum(axis=0).tolist(),
        minimum=max(2, rows),
        close_gap=max(2, image.width // 400),
    )
    y_runs = _projection_runs(
        alpha.sum(axis=1).tolist(),
        minimum=max(2, columns),
        close_gap=max(2, image.height // 400),
    )
    if len(x_runs) != columns or len(y_runs) != rows:
        raise RuntimeError(
            "content-projection could not identify the exact requested grid; "
            f"found {len(x_runs)} columns and {len(y_runs)} rows"
        )

    def centers_to_bounds(
        runs: list[tuple[int, int]], length: int
    ) -> list[tuple[int, int]]:
        centers = [(start + end) // 2 for start, end in runs]
        edges = [0]
        edges.extend((left + right) // 2 for left, right in zip(centers, centers[1:]))
        edges.append(length)
        return [(edges[index], edges[index + 1]) for index in range(len(runs))]

    return centers_to_bounds(x_runs, image.width), centers_to_bounds(y_runs, image.height)


def _save_previews(
    frames: list[Image.Image],
    durations: list[int],
    apng_path: Path,
    webp_path: Path,
) -> None:
    apng_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        apng_path,
        format="PNG",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=1,
        blend=0,
    )
    frames[0].save(
        webp_path,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        lossless=True,
        quality=100,
        method=6,
    )

    with Image.open(apng_path) as preview_source:
        decoded = [
            frame.convert("RGBA").copy()
            for frame in ImageSequence.Iterator(preview_source)
        ]
    if len(decoded) != len(frames):
        raise RuntimeError("APNG preview changed the frame count")
    for index, (source, preview) in enumerate(zip(frames, decoded)):
        if ImageChops.difference(source, preview).getbbox() is not None:
            raise RuntimeError(f"APNG preview changed RGBA frame {index}")


def _save_background_qa(atlas: Image.Image, path: Path) -> None:
    sprite = atlas.copy()
    sprite.thumbnail((800, 440), Image.Resampling.LANCZOS)
    width, height = sprite.size
    sheet = Image.new("RGB", (width * 2, height * 2), (255, 255, 255))
    backgrounds: list[Image.Image] = []
    backgrounds.append(Image.new("RGB", (width, height), (20, 24, 32)))
    backgrounds.append(Image.new("RGB", (width, height), (250, 250, 246)))
    checker = Image.new("RGB", (width, height), (210, 210, 210))
    draw = ImageDraw.Draw(checker)
    size = 16
    for y in range(0, height, size):
        for x in range(0, width, size):
            if (x // size + y // size) % 2:
                draw.rectangle(
                    (x, y, min(width, x + size) - 1, min(height, y + size) - 1),
                    fill=(245, 245, 245),
                )
    backgrounds.append(checker)
    contrast = Image.new("RGB", (width, height), (18, 180, 100))
    contrast_draw = ImageDraw.Draw(contrast)
    contrast_draw.rectangle((width // 2, 0, width, height), fill=(245, 170, 30))
    backgrounds.append(contrast)
    for index, background in enumerate(backgrounds):
        background.paste(sprite, (0, 0), sprite)
        sheet.paste(background, ((index % 2) * width, (index // 2) * height))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def _matte_source(
    source: Image.Image,
    chroma_key: tuple[int, int, int],
) -> tuple[Image.Image, dict[str, Any]]:
    rgba = source.convert("RGBA")
    alpha = np.array(rgba.getchannel("A"), dtype=np.uint8)
    if np.any(alpha < 255):
        return _zero_hidden_rgb(rgba), {
            "algorithm": "source-alpha",
            "remaining_key_family_edge_pixels": 0,
            "transparent_rgb_residue_pixels": 0,
        }
    return matte_chroma_background(rgba, chroma_key=chroma_key)


def _normalize_bottom_center(
    cells: list[Image.Image],
    canvas: dict[str, Any],
) -> tuple[list[Image.Image], float, list[dict[str, Any]]]:
    cell_width = canvas["cell_width"]
    cell_height = canvas["cell_height"]
    sprite_width = canvas["sprite_bounds_width"]
    sprite_height = canvas["sprite_bounds_height"]
    anchor_x = canvas["anchor_x"]
    anchor_y = canvas["anchor_y"]
    cropped: list[tuple[Image.Image, tuple[int, int, int, int]]] = []
    max_width = 0
    max_height = 0
    for index, cell in enumerate(cells):
        bbox = _alpha_bbox(cell)
        if bbox is None:
            raise RuntimeError(f"generated sheet contains an empty cell at {index}")
        item = cell.crop(bbox)
        max_width = max(max_width, item.width)
        max_height = max(max_height, item.height)
        cropped.append((item, bbox))
    scale = min(sprite_width / max_width, sprite_height / max_height, 1.0)

    normalized: list[Image.Image] = []
    records: list[dict[str, Any]] = []
    for item, bbox in cropped:
        width = max(1, round(item.width * scale))
        height = max(1, round(item.height * scale))
        resized = _premultiplied_resize(item, (width, height))
        frame = Image.new("RGBA", (cell_width, cell_height), (0, 0, 0, 0))
        x = int(anchor_x - width / 2)
        y = int(anchor_y - height)
        frame.alpha_composite(resized, (x, y))
        frame = _zero_hidden_rgb(frame)
        normalized.append(frame)
        records.append(
            {
                "source_bbox": list(bbox),
                "whole_sprite_scale": scale,
                "rigid_offset": [x, y],
                "internal_pixel_replacement": False,
            }
        )
    return normalized, scale, records


def _normalize_source_grid(
    cells: list[Image.Image],
    canvas: dict[str, Any],
) -> tuple[list[Image.Image], float, list[dict[str, Any]]]:
    cell_width = canvas["cell_width"]
    cell_height = canvas["cell_height"]
    normalized: list[Image.Image] = []
    records: list[dict[str, Any]] = []
    scales: list[float] = []
    for index, cell in enumerate(cells):
        if _alpha_bbox(cell) is None:
            raise RuntimeError(f"generated sheet contains an empty cell at {index}")
        scale = min(cell_width / cell.width, cell_height / cell.height)
        width = max(1, round(cell.width * scale))
        height = max(1, round(cell.height * scale))
        resized = _premultiplied_resize(cell, (width, height))
        frame = Image.new("RGBA", (cell_width, cell_height), (0, 0, 0, 0))
        x = (cell_width - width) // 2
        y = (cell_height - height) // 2
        frame.alpha_composite(resized, (x, y))
        frame = _zero_hidden_rgb(frame)
        normalized.append(frame)
        scales.append(scale)
        records.append(
            {
                "source_bbox": list(_alpha_bbox(cell) or (0, 0, 0, 0)),
                "whole_slot_scale": scale,
                "rigid_offset": [x, y],
                "internal_pixel_replacement": False,
            }
        )
    return normalized, min(scales), records


def process_group_sheet(
    source_path: Path,
    group: dict[str, Any],
    clips: dict[str, dict[str, Any]],
    canvas: dict[str, Any],
    output_root: Path,
) -> dict[str, Any]:
    """Process one whole generated sheet without recomposing character parts."""
    source = Image.open(source_path).convert("RGBA")
    chroma_key = parse_hex_color(canvas["chroma_key"])
    matted, matte_metrics = _matte_source(source, chroma_key)
    if group["slot_detection"] == "content-projection":
        x_bounds, y_bounds = _projection_bounds(
            matted, group["columns"], group["rows"]
        )
    else:
        x_bounds = _grid_bounds(matted.width, group["columns"])
        y_bounds = _grid_bounds(matted.height, group["rows"])
    cells: list[Image.Image] = []
    for row in range(group["rows"]):
        for column in range(group["columns"]):
            left, right = x_bounds[column]
            top, bottom = y_bounds[row]
            cells.append(matted.crop((left, top, right, bottom)))

    if group["registration"] == "bottom-center":
        normalized, shared_scale, frame_records = _normalize_bottom_center(
            cells, canvas
        )
    else:
        normalized, shared_scale, frame_records = _normalize_source_grid(
            cells, canvas
        )

    cell_width = canvas["cell_width"]
    cell_height = canvas["cell_height"]
    atlas = Image.new(
        "RGBA",
        (group["columns"] * cell_width, group["rows"] * cell_height),
        (0, 0, 0, 0),
    )
    clip_frames: dict[str, list[Image.Image | None]] = {
        clip_id: [None] * clip["frame_count"]
        for clip_id, clip in clips.items()
        if any(cell["clip_id"] == clip_id for cell in group["cells"])
    }
    output_frames: list[dict[str, Any]] = []
    ordered_mappings = sorted(
        group["cells"], key=lambda item: (item["row"], item["column"])
    )
    for mapping, frame, record in zip(ordered_mappings, normalized, frame_records):
        row = mapping["row"]
        column = mapping["column"]
        clip_id = mapping["clip_id"]
        frame_index = mapping["frame"]
        atlas.alpha_composite(frame, (column * cell_width, row * cell_height))
        clip_frames[clip_id][frame_index] = frame
        frame_dir = output_root / "frames" / clip_id
        frame_dir.mkdir(parents=True, exist_ok=True)
        frame_path = frame_dir / f"{frame_index:03d}.png"
        frame.save(frame_path)
        output_frames.append(
            {
                "clip_id": clip_id,
                "frame": frame_index,
                "path": str(frame_path),
                **record,
            }
        )

    atlas = _zero_hidden_rgb(atlas)
    atlas_path = output_root / "atlases" / f"{group['id']}.png"
    atlas_path.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(atlas_path)
    background_qa = output_root / "qa" / f"{group['id']}-backgrounds.png"
    _save_background_qa(atlas, background_qa)

    previews: list[dict[str, str]] = []
    for clip_id, frames in clip_frames.items():
        if any(frame is None for frame in frames):
            raise RuntimeError(f"clip {clip_id} is missing frames after extraction")
        typed_frames = [frame for frame in frames if frame is not None]
        clip = clips[clip_id]
        apng = output_root / "previews" / f"{clip_id}.apng"
        webp = output_root / "previews" / f"{clip_id}.webp"
        _save_previews(typed_frames, clip["durations_ms"], apng, webp)
        previews.append(
            {"clip_id": clip_id, "apng": str(apng), "webp": str(webp)}
        )

    atlas_values = np.array(atlas.convert("RGBA"), dtype=np.uint8)
    visible = atlas_values[:, :, 3] > 8
    family = key_family_mask(atlas_values[:, :, :3], chroma_key) & visible
    distance = np.linalg.norm(
        atlas_values[:, :, :3].astype(np.float32)
        - np.array(chroma_key, dtype=np.float32),
        axis=2,
    )
    residue = family & (distance < 110)
    report = {
        "ok": int(residue.sum()) == 0,
        "group_id": group["id"],
        "source": str(source_path),
        "source_sha256": sha256(source_path),
        "source_size": list(source.size),
        "grid": {
            "rows": group["rows"],
            "columns": group["columns"],
            "slot_detection": group["slot_detection"],
        },
        "registration": group["registration"],
        "shared_whole_sprite_scale": shared_scale,
        "internal_pixel_replacement": False,
        "matte": matte_metrics,
        "visible_chroma_family_pixels": int(family.sum()),
        "visible_chroma_residue_pixels": int(residue.sum()),
        "atlas": str(atlas_path),
        "atlas_sha256": sha256(atlas_path),
        "background_qa": str(background_qa),
        "frames": output_frames,
        "previews": previews,
    }
    report_path = output_root / "qa" / f"{group['id']}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not report["ok"]:
        raise RuntimeError(
            f"visible chroma residue remains in group {group['id']}"
        )
    return report
