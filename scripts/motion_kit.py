#!/usr/bin/env python3
"""Prepare, produce, package, and verify discrete 2D character motion assets."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

import character_kit
from motion.image_pipeline import process_group_sheet, sha256


SCHEMA_VERSION = "1.0"
RECORD_SCHEMA_VERSION = "1.0"
ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
CLIP_KINDS = {"static", "loop", "oneshot", "transition"}
REGISTRATIONS = {"bottom-center", "source-grid"}
SLOT_DETECTIONS = {"equal-grid", "content-projection"}


class MotionError(ValueError):
    """Raised when a motion contract or run is incomplete or inconsistent."""


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise MotionError(f"file does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise MotionError(
            f"invalid JSON in {path}: line {error.lineno}, column {error.colno}"
        ) from error


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception as error:
        raise MotionError(f"could not write {path}: {error}") from error


def _require_text(value: Any, label: str, maximum: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MotionError(f"{label} must be non-empty text")
    value = value.strip()
    if len(value) > maximum:
        raise MotionError(f"{label} is longer than {maximum} characters")
    return value


def _strict_object(value: Any, label: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MotionError(f"{label} must be an object")
    if set(value) != keys:
        missing = sorted(keys - set(value))
        extra = sorted(set(value) - keys)
        raise MotionError(f"{label} fields mismatch; missing={missing}, extra={extra}")
    return value


def _positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise MotionError(f"{label} must be a positive integer")
    return value


def _validate_id(value: Any, label: str) -> str:
    value = _require_text(value, label, 64)
    if not ID_RE.fullmatch(value):
        raise MotionError(
            f"{label} must use lowercase letters, numbers, and single hyphens"
        )
    return value


def validate_contract(value: Any) -> dict[str, Any]:
    contract = _strict_object(
        value,
        "motion contract",
        {
            "schema_version",
            "motion_id",
            "display_name",
            "target",
            "canvas",
            "clips",
            "groups",
        },
    )
    if contract["schema_version"] != SCHEMA_VERSION:
        raise MotionError(f"motion schema_version must equal {SCHEMA_VERSION}")
    _validate_id(contract["motion_id"], "motion_id")
    _require_text(contract["display_name"], "display_name", 160)

    target = _strict_object(
        contract["target"],
        "target",
        {
            "surface",
            "runtime",
            "actor_role",
            "camera",
            "state_source",
            "direction_source",
            "consumer",
            "observable_result",
        },
    )
    for key in target:
        _require_text(target[key], f"target.{key}")

    canvas = _strict_object(
        contract["canvas"],
        "canvas",
        {
            "cell_width",
            "cell_height",
            "anchor_x",
            "anchor_y",
            "sprite_bounds_width",
            "sprite_bounds_height",
            "chroma_key",
            "runtime_format",
            "preview_formats",
        },
    )
    for key in (
        "cell_width",
        "cell_height",
        "sprite_bounds_width",
        "sprite_bounds_height",
    ):
        _positive_int(canvas[key], f"canvas.{key}")
    for key in ("anchor_x", "anchor_y"):
        if not isinstance(canvas[key], int) or isinstance(canvas[key], bool):
            raise MotionError(f"canvas.{key} must be an integer")
    if not 0 <= canvas["anchor_x"] < canvas["cell_width"]:
        raise MotionError("canvas.anchor_x must stay inside the cell")
    if not 0 <= canvas["anchor_y"] < canvas["cell_height"]:
        raise MotionError("canvas.anchor_y must stay inside the cell")
    if canvas["sprite_bounds_width"] > canvas["cell_width"]:
        raise MotionError("canvas.sprite_bounds_width must fit inside the cell")
    if canvas["sprite_bounds_height"] > canvas["cell_height"]:
        raise MotionError("canvas.sprite_bounds_height must fit inside the cell")
    chroma = _require_text(canvas["chroma_key"], "canvas.chroma_key", 7)
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", chroma):
        raise MotionError("canvas.chroma_key must be #RRGGBB")
    _require_text(canvas["runtime_format"], "canvas.runtime_format", 120)
    if canvas["preview_formats"] != ["apng", "lossless-webp"]:
        raise MotionError(
            "canvas.preview_formats must be ['apng', 'lossless-webp']; GIF is share-only"
        )

    if not isinstance(contract["clips"], list) or not contract["clips"]:
        raise MotionError("clips must contain at least one runtime clip")
    clips: dict[str, dict[str, Any]] = {}
    for index, raw_clip in enumerate(contract["clips"]):
        clip = _strict_object(
            raw_clip,
            f"clips[{index}]",
            {
                "id",
                "state",
                "direction",
                "kind",
                "frame_count",
                "durations_ms",
                "semantic",
                "effect_events",
            },
        )
        clip_id = _validate_id(clip["id"], f"clips[{index}].id")
        if clip_id in clips:
            raise MotionError(f"duplicate clip id: {clip_id}")
        _require_text(clip["state"], f"clips[{index}].state", 120)
        _require_text(clip["direction"], f"clips[{index}].direction", 120)
        if clip["kind"] not in CLIP_KINDS:
            raise MotionError(f"unsupported clip kind: {clip['kind']}")
        frame_count = _positive_int(
            clip["frame_count"], f"clips[{index}].frame_count"
        )
        if clip["kind"] == "static" and frame_count != 1:
            raise MotionError(f"static clip {clip_id} must contain one frame")
        durations = clip["durations_ms"]
        if (
            not isinstance(durations, list)
            or len(durations) != frame_count
            or any(
                not isinstance(duration, int)
                or isinstance(duration, bool)
                or duration <= 0
                for duration in durations
            )
        ):
            raise MotionError(
                f"clip {clip_id} durations_ms must contain one positive integer per frame"
            )
        _require_text(clip["semantic"], f"clips[{index}].semantic")
        if not isinstance(clip["effect_events"], list):
            raise MotionError(f"clip {clip_id} effect_events must be an array")
        event_ids: set[str] = set()
        for event_index, raw_event in enumerate(clip["effect_events"]):
            event = _strict_object(
                raw_event,
                f"clip {clip_id} event {event_index}",
                {"id", "frame", "meaning"},
            )
            event_id = _validate_id(event["id"], f"clip {clip_id} event id")
            if event_id in event_ids:
                raise MotionError(f"duplicate effect event {event_id} in {clip_id}")
            event_ids.add(event_id)
            if (
                not isinstance(event["frame"], int)
                or isinstance(event["frame"], bool)
                or not 0 <= event["frame"] < frame_count
            ):
                raise MotionError(f"effect event frame is outside clip {clip_id}")
            _require_text(event["meaning"], f"clip {clip_id} event meaning")
        clips[clip_id] = clip

    if not isinstance(contract["groups"], list) or not contract["groups"]:
        raise MotionError("groups must contain at least one coherent source sheet")
    mapped_frames: set[tuple[str, int]] = set()
    group_ids: set[str] = set()
    for index, raw_group in enumerate(contract["groups"]):
        group = _strict_object(
            raw_group,
            f"groups[{index}]",
            {"id", "rows", "columns", "registration", "slot_detection", "cells"},
        )
        group_id = _validate_id(group["id"], f"groups[{index}].id")
        if group_id in group_ids:
            raise MotionError(f"duplicate group id: {group_id}")
        group_ids.add(group_id)
        rows = _positive_int(group["rows"], f"group {group_id} rows")
        columns = _positive_int(group["columns"], f"group {group_id} columns")
        if group["registration"] not in REGISTRATIONS:
            raise MotionError(f"unsupported registration in group {group_id}")
        if group["slot_detection"] not in SLOT_DETECTIONS:
            raise MotionError(f"unsupported slot detection in group {group_id}")
        if not isinstance(group["cells"], list) or len(group["cells"]) != rows * columns:
            raise MotionError(
                f"group {group_id} must map every one of its {rows * columns} cells"
            )
        positions: set[tuple[int, int]] = set()
        for cell_index, raw_cell in enumerate(group["cells"]):
            cell = _strict_object(
                raw_cell,
                f"group {group_id} cell {cell_index}",
                {"row", "column", "clip_id", "frame"},
            )
            row = cell["row"]
            column = cell["column"]
            if (
                not isinstance(row, int)
                or isinstance(row, bool)
                or not 0 <= row < rows
                or not isinstance(column, int)
                or isinstance(column, bool)
                or not 0 <= column < columns
            ):
                raise MotionError(f"cell position is outside group {group_id}")
            position = (row, column)
            if position in positions:
                raise MotionError(f"duplicate cell position in group {group_id}")
            positions.add(position)
            clip_id = cell["clip_id"]
            if clip_id not in clips:
                raise MotionError(f"group {group_id} references unknown clip {clip_id}")
            frame = cell["frame"]
            if (
                not isinstance(frame, int)
                or isinstance(frame, bool)
                or not 0 <= frame < clips[clip_id]["frame_count"]
            ):
                raise MotionError(f"group {group_id} maps an invalid frame of {clip_id}")
            identity = (clip_id, frame)
            if identity in mapped_frames:
                raise MotionError(f"clip frame is mapped more than once: {identity}")
            mapped_frames.add(identity)

    expected_frames = {
        (clip_id, frame)
        for clip_id, clip in clips.items()
        for frame in range(clip["frame_count"])
    }
    if mapped_frames != expected_frames:
        missing = sorted(expected_frames - mapped_frames)
        raise MotionError(f"some runtime clip frames have no source cell: {missing}")
    return copy.deepcopy(contract)


def _contract_digest(contract: dict[str, Any]) -> str:
    canonical = json.dumps(
        validate_contract(contract),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def contract_digest(contract: dict[str, Any]) -> str:
    """Return the canonical digest shared with platform adapters."""
    return _contract_digest(contract)


def _cells_for_rows(clip_ids: list[str], frame_counts: dict[str, int]) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for row, clip_id in enumerate(clip_ids):
        for frame in range(frame_counts[clip_id]):
            cells.append(
                {"row": row, "column": frame, "clip_id": clip_id, "frame": frame}
            )
    return cells


def build_codex_pet_contract(display_name: str) -> dict[str, Any]:
    """Expose Codex v2 as one fixed adapter of the shared motion contract."""
    from pet.prepare_pet_run import LOOK_ROWS, ROWS

    clips: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    for state, _row, frames, purpose in ROWS:
        clips.append(
            {
                "id": state,
                "state": state,
                "direction": (
                    "screen-right"
                    if state == "running-right"
                    else "screen-left" if state == "running-left" else "none"
                ),
                "kind": "loop",
                "frame_count": frames,
                "durations_ms": [120] * frames,
                "semantic": purpose,
                "effect_events": [],
            }
        )
        groups.append(
            {
                "id": state,
                "rows": 1,
                "columns": frames,
                "registration": "bottom-center",
                "slot_detection": "equal-grid",
                "cells": _cells_for_rows([state], {state: frames}),
            }
        )
    direction_names = {
        "000": "up",
        "022.5": "up-right",
        "045": "up-right",
        "067.5": "up-right",
        "090": "right",
        "112.5": "down-right",
        "135": "down-right",
        "157.5": "down-right",
        "180": "down",
        "202.5": "down-left",
        "225": "down-left",
        "247.5": "down-left",
        "270": "left",
        "292.5": "up-left",
        "315": "up-left",
        "337.5": "up-left",
    }
    for group_id, _row, directions, purpose in LOOK_ROWS:
        cells: list[dict[str, Any]] = []
        for column, degrees in enumerate(directions):
            clip_id = f"look-{degrees.replace('.', '-') }"
            clips.append(
                {
                    "id": clip_id,
                    "state": "look",
                    "direction": direction_names[degrees],
                    "kind": "static",
                    "frame_count": 1,
                    "durations_ms": [120],
                    "semantic": f"{purpose}; {degrees} degrees clockwise from up",
                    "effect_events": [],
                }
            )
            cells.append(
                {"row": 0, "column": column, "clip_id": clip_id, "frame": 0}
            )
        groups.append(
            {
                "id": group_id,
                "rows": 1,
                "columns": 8,
                "registration": "bottom-center",
                "slot_detection": "equal-grid",
                "cells": cells,
            }
        )
    return validate_contract(
        {
            "schema_version": SCHEMA_VERSION,
            "motion_id": "codex-pet-v2",
            "display_name": f"{display_name} Codex v2 pet motion",
            "target": {
                "surface": "Codex desktop pet",
                "runtime": "Codex spriteVersionNumber 2",
                "actor_role": "stateful-application-character",
                "camera": "front-facing desktop overlay",
                "state_source": "Codex application pet state",
                "direction_source": "pointer-relative look direction",
                "consumer": "Codex v2 pet spritesheet loader",
                "observable_result": "the selected pet state and gaze appear in Codex",
            },
            "canvas": {
                "cell_width": 192,
                "cell_height": 208,
                "anchor_x": 96,
                "anchor_y": 198,
                "sprite_bounds_width": 182,
                "sprite_bounds_height": 198,
                "chroma_key": "#FF00FF",
                "runtime_format": "Codex v2 8x11 lossless WebP atlas",
                "preview_formats": ["apng", "lossless-webp"],
            },
            "clips": clips,
            "groups": groups,
        }
    )


def _draft_contract(motion_id: str, display_name: str) -> dict[str, Any]:
    clip_id = "required-state"
    return {
        "schema_version": SCHEMA_VERSION,
        "motion_id": _validate_id(motion_id, "motion_id"),
        "display_name": _require_text(display_name, "display_name", 160),
        "target": {
            "surface": "replace with the actual surface",
            "runtime": "replace with the actual runtime",
            "actor_role": "replace with the actor's real role",
            "camera": "replace with the actual camera",
            "state_source": "replace with the real state producer",
            "direction_source": "none, or the real direction producer",
            "consumer": "replace with the real runtime consumer",
            "observable_result": "replace with what the user will actually see",
        },
        "canvas": {
            "cell_width": 192,
            "cell_height": 192,
            "anchor_x": 96,
            "anchor_y": 160,
            "sprite_bounds_width": 176,
            "sprite_bounds_height": 152,
            "chroma_key": "#FF00FF",
            "runtime_format": "transparent PNG atlas",
            "preview_formats": ["apng", "lossless-webp"],
        },
        "clips": [
            {
                "id": clip_id,
                "state": "replace with a real runtime state",
                "direction": "none",
                "kind": "static",
                "frame_count": 1,
                "durations_ms": [120],
                "semantic": "replace with the visible state meaning",
                "effect_events": [],
            }
        ],
        "groups": [
            {
                "id": "required-state-sheet",
                "rows": 1,
                "columns": 1,
                "registration": "bottom-center",
                "slot_detection": "equal-grid",
                "cells": [
                    {"row": 0, "column": 0, "clip_id": clip_id, "frame": 0}
                ],
            }
        ],
    }


def _next_run_dir(kit: Path, motion_id: str) -> Path:
    root = kit / "derivatives" / "motion" / motion_id / "runs"
    revisions = []
    if root.is_dir():
        revisions = [
            int(match.group(1))
            for path in root.iterdir()
            if path.is_dir()
            and (match := re.fullmatch(r"r(\d{3})", path.name)) is not None
        ]
    revision = max(revisions, default=0) + 1
    return root / f"r{revision:03d}"


def _safe_path(root: Path, relative: str, label: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise MotionError(f"{label} must stay inside the motion run")
    root = root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise MotionError(f"{label} escapes the motion run") from error
    return resolved


def _relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")


def _rewrite_paths(value: Any, old: str, new: str) -> Any:
    if isinstance(value, dict):
        return {key: _rewrite_paths(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_paths(item, old, new) for item in value]
    if isinstance(value, str):
        return value.replace(old, new)
    return value


def _group_task(contract: dict[str, Any], group: dict[str, Any]) -> str:
    clips = {clip["id"]: clip for clip in contract["clips"]}
    ordered = sorted(group["cells"], key=lambda item: (item["row"], item["column"]))
    layout = "；".join(
        f"第{item['row'] + 1}行第{item['column'] + 1}格="
        f"{item['clip_id']}第{item['frame'] + 1}帧"
        for item in ordered
    )
    meanings = "\n".join(
        f"- {clip_id}：{clips[clip_id]['semantic']}；方向 {clips[clip_id]['direction']}"
        for clip_id in dict.fromkeys(item["clip_id"] for item in ordered)
    )
    return (
        f"为目标 {contract['target']['surface']} 制作角色动态素材组 {group['id']}。\n"
        f"必须在同一张完整图片中直接生成 {group['rows']} 行 × {group['columns']} 列的全部姿势，"
        "不要按方向或按帧分别生成，不要从其它图片拼接脸、眼睛、头发、手脚或服装局部。"
        "每格都是同一个完整角色，身份、脸型、头身比、服装结构、配色和配饰位置一致。\n"
        f"格子语义：{layout}。\n动作要求：\n{meanings}\n"
        f"背景使用完全平坦的 {contract['canvas']['chroma_key']}，角色和配件中不得出现接近该颜色的区域。"
        "格子等宽等高但成品不得出现网格线、标签、数字、文字、地面阴影、场景、速度线或跨格残影。"
        "角色完整、不裁切，相邻动作保持相同表观尺寸。轻微整人位置变化可以保留，"
        "不得用局部重绘或内部像素替换伪造稳定。"
    )


def _create_guide(path: Path, group: dict[str, Any], canvas: dict[str, Any]) -> None:
    scale = min(1.0, 1536 / (group["columns"] * canvas["cell_width"]))
    cell_width = max(96, round(canvas["cell_width"] * scale))
    cell_height = max(96, round(canvas["cell_height"] * scale))
    image = Image.new(
        "RGB",
        (group["columns"] * cell_width, group["rows"] * cell_height),
        canvas["chroma_key"],
    )
    draw = ImageDraw.Draw(image)
    for cell in group["cells"]:
        left = cell["column"] * cell_width
        top = cell["row"] * cell_height
        right = left + cell_width - 1
        bottom = top + cell_height - 1
        draw.rectangle((left, top, right, bottom), outline=(60, 60, 60), width=2)
        center = left + cell_width // 2
        baseline = top + round(canvas["anchor_y"] / canvas["cell_height"] * cell_height)
        draw.line((center - 10, baseline, center + 10, baseline), fill=(40, 40, 40), width=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _prepare(kit: Path, contract_path: Path, output_dir: Path | None = None) -> dict[str, Any]:
    kit = kit.expanduser().resolve()
    contract = validate_contract(_load_json(contract_path.expanduser().resolve()))
    character = character_kit.build_prompt_bundle(
        kit,
        "scene",
        f"把已锁定角色适配为 {contract['target']['surface']} 的离散 2D 动态素材。",
    )
    destination = (
        output_dir.expanduser().resolve()
        if output_dir is not None
        else _next_run_dir(kit, contract["motion_id"]).resolve()
    )
    if destination.exists():
        raise MotionError(f"refusing to overwrite existing motion run: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.staging"
    try:
        references = stage / "references"
        references.mkdir(parents=True, exist_ok=False)
        profile_source = Path(character["profile"])
        master_source = Path(character["master_reference"])
        shutil.copy2(profile_source, references / "character-profile.snapshot.json")
        master_copy = references / f"master{master_source.suffix.lower()}"
        shutil.copy2(master_source, master_copy)
        _atomic_write(stage / "motion-contract.json", _json_bytes(contract))
        clips = {clip["id"]: clip for clip in contract["clips"]}
        jobs: list[dict[str, Any]] = []
        for group in contract["groups"]:
            task = _group_task(contract, group)
            bundle = character_kit.build_prompt_bundle(kit, "scene", task)
            prompt_path = stage / "prompts" / f"{group['id']}.md"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(bundle["prompt"] + "\n", encoding="utf-8")
            guide = stage / "guides" / f"{group['id']}.png"
            _create_guide(guide, group, contract["canvas"])
            jobs.append(
                {
                    "id": group["id"],
                    "status": "pending",
                    "requires_user_confirmation": True,
                    "prompt_file": _relative(prompt_path, stage),
                    "input_images": [
                        {"path": _relative(master_copy, stage), "role": "locked-character-master"},
                        {"path": _relative(guide, stage), "role": "layout-only-do-not-copy-marks"},
                    ],
                    "output": None,
                    "qa_note": None,
                }
            )
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "motion_id": contract["motion_id"],
            "contract_sha256": _contract_digest(contract),
            "jobs": jobs,
        }
        _atomic_write(stage / "imagegen-jobs.json", _json_bytes(manifest))
        record = {
            "record_schema_version": RECORD_SCHEMA_VERSION,
            "status": "prepared",
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "motion_id": contract["motion_id"],
            "contract_sha256": _contract_digest(contract),
            "source_character": {
                "character_id": character["character_id"],
                "revision": character["character_revision"],
                "profile_sha256": character["profile_sha256"],
                "master_sha256": character["master_sha256"],
            },
            "package": None,
        }
        _atomic_write(stage / "motion-run-record.json", _json_bytes(record))
        os.replace(stage, destination)
        return _check_prepared(destination)
    except Exception as error:
        if stage.exists():
            archive = destination.parent / ".ip-studio-failed"
            archive.mkdir(parents=True, exist_ok=True)
            os.replace(stage, archive / f"{destination.name}.{uuid.uuid4().hex}.failed")
        if isinstance(error, MotionError):
            raise
        raise MotionError(f"motion preparation failed: {error}") from error


def _job_map(manifest: dict[str, Any], contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        raise MotionError("imagegen-jobs.json jobs must be an array")
    mapped: dict[str, dict[str, Any]] = {}
    for index, raw_job in enumerate(jobs):
        job = _strict_object(
            raw_job,
            f"image job {index}",
            {
                "id",
                "status",
                "requires_user_confirmation",
                "prompt_file",
                "input_images",
                "output",
                "qa_note",
            },
        )
        job_id = _validate_id(job["id"], f"image job {index} id")
        if job_id in mapped:
            raise MotionError(f"duplicate image job: {job_id}")
        if job["status"] not in {"pending", "complete"}:
            raise MotionError(f"unsupported image job status: {job['status']}")
        if job["requires_user_confirmation"] is not True:
            raise MotionError(
                f"image job {job_id} must require user confirmation before generation"
            )
        if not isinstance(job["input_images"], list) or not job["input_images"]:
            raise MotionError(f"image job {job_id} must contain input images")
        for image_index, item in enumerate(job["input_images"]):
            _strict_object(
                item,
                f"image job {job_id} input {image_index}",
                {"path", "role"},
            )
            _require_text(item["path"], f"image job {job_id} input path")
            _require_text(item["role"], f"image job {job_id} input role")
        if job["status"] == "pending" and (job["output"] is not None or job["qa_note"] is not None):
            raise MotionError(f"pending image job {job_id} cannot contain accepted output")
        if job["status"] == "complete":
            _require_text(job["output"], f"image job {job_id} output")
            _require_text(job["qa_note"], f"image job {job_id} qa_note")
        mapped[job_id] = job
    expected = [group["id"] for group in contract["groups"]]
    if list(mapped) != expected:
        raise MotionError("image jobs must exactly match motion contract groups")
    return mapped


def _check_character_snapshot(run: Path, record: dict[str, Any]) -> None:
    profile_path = run / "references" / "character-profile.snapshot.json"
    profile = character_kit.validate_locked_profile(_load_json(profile_path))
    source = record["source_character"]
    if profile["character_id"] != source["character_id"]:
        raise MotionError("character snapshot id mismatch")
    author = {key: profile[key] for key in character_kit.AUTHOR_KEY_ORDER}
    canonical = json.dumps(
        author, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != source["profile_sha256"]:
        raise MotionError("character profile snapshot SHA-256 mismatch")
    masters = list((run / "references").glob("master.*"))
    if len(masters) != 1 or sha256(masters[0]) != source["master_sha256"]:
        raise MotionError("character master snapshot SHA-256 mismatch")


def _check_prepared(run: Path) -> dict[str, Any]:
    run = run.expanduser().resolve()
    if not run.is_dir():
        raise MotionError(f"motion run does not exist: {run}")
    contract = validate_contract(_load_json(run / "motion-contract.json"))
    digest = _contract_digest(contract)
    manifest = _load_json(run / "imagegen-jobs.json")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise MotionError("unsupported image job manifest schema")
    if manifest.get("contract_sha256") != digest:
        raise MotionError("image job manifest contract SHA-256 mismatch")
    jobs = _job_map(manifest, contract)
    for job_id, job in jobs.items():
        prompt = _safe_path(run, job["prompt_file"], f"{job_id} prompt")
        if not prompt.is_file() or not prompt.read_text(encoding="utf-8").strip():
            raise MotionError(f"{job_id} prompt is missing or empty")
        for item in job["input_images"]:
            image = _safe_path(run, item["path"], f"{job_id} input image")
            if not image.is_file():
                raise MotionError(f"{job_id} input image is missing")
        if job["status"] == "complete":
            output = _safe_path(run, job["output"], f"{job_id} output")
            report = _load_json(output / "qa" / f"{job_id}.json")
            if not report.get("ok"):
                raise MotionError(f"{job_id} processing report did not pass")
            if report.get("internal_pixel_replacement") is not False:
                raise MotionError(f"{job_id} used forbidden internal pixel replacement")
            source = _safe_path(run, report["source"], f"{job_id} source sheet")
            if sha256(source) != report["source_sha256"]:
                raise MotionError(f"{job_id} source sheet SHA-256 mismatch")
            atlas = _safe_path(run, report["atlas"], f"{job_id} atlas")
            if sha256(atlas) != report["atlas_sha256"]:
                raise MotionError(f"{job_id} atlas SHA-256 mismatch")
            _safe_path(run, report["background_qa"], f"{job_id} background QA").stat()
            group = next(item for item in contract["groups"] if item["id"] == job_id)
            expected_frames = {
                (cell["clip_id"], cell["frame"]) for cell in group["cells"]
            }
            reported_frames: set[tuple[str, int]] = set()
            for frame in report["frames"]:
                identity = (frame["clip_id"], frame["frame"])
                reported_frames.add(identity)
                path = _safe_path(run, frame["path"], f"{job_id} frame")
                if not path.is_file():
                    raise MotionError(f"{job_id} frame is missing: {identity}")
                if frame.get("internal_pixel_replacement") is not False:
                    raise MotionError(f"{job_id} frame used internal pixel replacement")
            if reported_frames != expected_frames:
                raise MotionError(f"{job_id} reported frames do not match its contract cells")
            for preview in report["previews"]:
                _safe_path(run, preview["apng"], f"{job_id} APNG preview").stat()
                _safe_path(run, preview["webp"], f"{job_id} WebP preview").stat()
    record = _load_json(run / "motion-run-record.json")
    if record.get("record_schema_version") != RECORD_SCHEMA_VERSION:
        raise MotionError("unsupported motion run record schema")
    if record.get("contract_sha256") != digest:
        raise MotionError("motion run record contract SHA-256 mismatch")
    _check_character_snapshot(run, record)
    return {
        "status": "PASS",
        "stage": record["status"],
        "run": str(run),
        "motion_id": contract["motion_id"],
        "character_id": record["source_character"]["character_id"],
        "completed_jobs": [job_id for job_id, job in jobs.items() if job["status"] == "complete"],
        "ready_jobs": [job_id for job_id, job in jobs.items() if job["status"] == "pending"],
    }


def _accept_sheet(
    run: Path,
    job_id: str,
    source: Path,
    qa_note: str,
    replace_complete: bool = False,
) -> dict[str, Any]:
    run = run.expanduser().resolve()
    prepared = _check_prepared(run)
    if prepared["stage"] == "final":
        raise MotionError("finalized motion runs cannot replace source sheets; prepare a new run")
    contract = validate_contract(_load_json(run / "motion-contract.json"))
    manifest_path = run / "imagegen-jobs.json"
    manifest = _load_json(manifest_path)
    jobs = _job_map(manifest, contract)
    if job_id not in jobs:
        raise MotionError(f"unknown image job: {job_id}")
    job = jobs[job_id]
    if job["status"] == "complete" and not replace_complete:
        raise MotionError(f"job {job_id} is complete; use --replace-complete to replace it")
    source = source.expanduser().resolve()
    if not source.is_file():
        raise MotionError(f"generated sheet does not exist: {source}")
    _require_text(qa_note, "qa_note")
    group = next(item for item in contract["groups"] if item["id"] == job_id)
    clips = {clip["id"]: clip for clip in contract["clips"]}
    destination = run / "production" / job_id
    stage = run / ".staging" / f"{job_id}.{uuid.uuid4().hex}"
    try:
        stage.mkdir(parents=True, exist_ok=False)
        source_copy = stage / "source" / f"generated{source.suffix.lower()}"
        source_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, source_copy)
        process_group_sheet(source_copy, group, clips, contract["canvas"], stage)
        if destination.exists():
            history = run / "history" / "job-replacements"
            history.mkdir(parents=True, exist_ok=True)
            os.replace(destination, history / f"{job_id}.{uuid.uuid4().hex}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        old = str(stage.resolve())
        new = str(destination.resolve())
        report_path = stage / "qa" / f"{job_id}.json"
        report = _rewrite_paths(_load_json(report_path), old, new)
        report["source"] = _relative(Path(report["source"]), run)
        report["atlas"] = _relative(Path(report["atlas"]), run)
        report["background_qa"] = _relative(Path(report["background_qa"]), run)
        for frame in report["frames"]:
            frame["path"] = _relative(Path(frame["path"]), run)
        for preview in report["previews"]:
            preview["apng"] = _relative(Path(preview["apng"]), run)
            preview["webp"] = _relative(Path(preview["webp"]), run)
        _atomic_write(report_path, _json_bytes(report))
        os.replace(stage, destination)
        job["status"] = "complete"
        job["output"] = _relative(destination, run)
        job["qa_note"] = qa_note.strip()
        _atomic_write(manifest_path, _json_bytes(manifest))
        record_path = run / "motion-run-record.json"
        record = _load_json(record_path)
        record["status"] = "producing"
        _atomic_write(record_path, _json_bytes(record))
        return _check_prepared(run)
    except Exception as error:
        if stage.exists():
            failed = run / "history" / "failed-jobs"
            failed.mkdir(parents=True, exist_ok=True)
            os.replace(stage, failed / f"{job_id}.{uuid.uuid4().hex}.failed")
        if isinstance(error, MotionError):
            raise
        raise MotionError(f"could not accept generated sheet {job_id}: {error}") from error


def _package_manifest(run: Path, contract: dict[str, Any], package: Path) -> dict[str, Any]:
    clips: list[dict[str, Any]] = []
    for clip in contract["clips"]:
        frames = sorted((package / "frames" / clip["id"]).glob("*.png"))
        if len(frames) != clip["frame_count"]:
            raise MotionError(f"package frame count mismatch for {clip['id']}")
        clips.append(
            {
                **clip,
                "frames": [
                    {"path": _relative(frame, package), "sha256": sha256(frame)}
                    for frame in frames
                ],
            }
        )
    atlases = []
    for group in contract["groups"]:
        atlas = package / "atlases" / f"{group['id']}.png"
        atlases.append(
            {"group_id": group["id"], "path": _relative(atlas, package), "sha256": sha256(atlas)}
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "motion_id": contract["motion_id"],
        "display_name": contract["display_name"],
        "target": contract["target"],
        "canvas": contract["canvas"],
        "contract_sha256": _contract_digest(contract),
        "clips": clips,
        "atlases": atlases,
    }


def _check_package(package: Path) -> dict[str, Any]:
    package = package.resolve()
    manifest = _load_json(package / "motion-manifest.json")
    contract = validate_contract(_load_json(package / "motion-contract.json"))
    if manifest.get("contract_sha256") != _contract_digest(contract):
        raise MotionError("package manifest contract SHA-256 mismatch")
    if manifest.get("motion_id") != contract["motion_id"]:
        raise MotionError("package motion id mismatch")
    for atlas in manifest.get("atlases", []):
        path = _safe_path(package, atlas["path"], "package atlas")
        if sha256(path) != atlas["sha256"]:
            raise MotionError("package atlas SHA-256 mismatch")
    for clip in manifest.get("clips", []):
        for frame in clip["frames"]:
            path = _safe_path(package, frame["path"], "package frame")
            if sha256(path) != frame["sha256"]:
                raise MotionError("package frame SHA-256 mismatch")
    return {
        "status": "PASS",
        "package": str(package),
        "motion_id": contract["motion_id"],
        "clip_count": len(manifest["clips"]),
        "atlas_count": len(manifest["atlases"]),
    }


def _finalize(run: Path) -> dict[str, Any]:
    run = run.expanduser().resolve()
    checked = _check_prepared(run)
    if checked["ready_jobs"]:
        raise MotionError("all coherent source sheets must be accepted before finalize")
    contract = validate_contract(_load_json(run / "motion-contract.json"))
    package = run / "package" / contract["motion_id"]
    if package.exists():
        raise MotionError(f"motion package already exists: {package}")
    stage = run / ".staging" / f"package.{uuid.uuid4().hex}"
    try:
        stage.mkdir(parents=True, exist_ok=False)
        shutil.copy2(run / "motion-contract.json", stage / "motion-contract.json")
        (stage / "atlases").mkdir(parents=True, exist_ok=True)
        for group in contract["groups"]:
            production = run / "production" / group["id"]
            shutil.copy2(
                production / "atlases" / f"{group['id']}.png",
                stage / "atlases" / f"{group['id']}.png",
            )
        for clip in contract["clips"]:
            source = next(
                run / "production" / group["id"] / "frames" / clip["id"]
                for group in contract["groups"]
                if any(cell["clip_id"] == clip["id"] for cell in group["cells"])
            )
            shutil.copytree(source, stage / "frames" / clip["id"])
        manifest = _package_manifest(run, contract, stage)
        _atomic_write(stage / "motion-manifest.json", _json_bytes(manifest))
        package.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage, package)
        result = _check_package(package)
        record_path = run / "motion-run-record.json"
        record = _load_json(record_path)
        record["status"] = "final"
        record["package"] = {
            "path": _relative(package, run),
            "manifest_sha256": sha256(package / "motion-manifest.json"),
        }
        _atomic_write(record_path, _json_bytes(record))
        return {**result, "run": str(run)}
    except Exception as error:
        if stage.exists():
            failed = run / "history" / "failed-finalize"
            failed.mkdir(parents=True, exist_ok=True)
            os.replace(stage, failed / f"package.{uuid.uuid4().hex}.failed")
        if isinstance(error, MotionError):
            raise
        raise MotionError(f"motion finalize failed: {error}") from error


def _check(run: Path, stage: str) -> dict[str, Any]:
    result = _check_prepared(run)
    if stage == "final":
        record = _load_json(run / "motion-run-record.json")
        if record["status"] != "final" or not isinstance(record["package"], dict):
            raise MotionError("motion run is not finalized")
        package = _safe_path(run, record["package"]["path"], "motion package")
        final = _check_package(package)
        if sha256(package / "motion-manifest.json") != record["package"]["manifest_sha256"]:
            raise MotionError("motion package manifest SHA-256 mismatch")
        return {**result, **final, "stage": "final"}
    return result


def _schema() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "clip_kinds": sorted(CLIP_KINDS),
        "registrations": sorted(REGISTRATIONS),
        "slot_detections": sorted(SLOT_DETECTIONS),
        "commands": ["schema", "draft", "prepare", "ready", "accept-sheet", "finalize", "check"],
        "gif_policy": "GIF is only a temporary share preview; runtime and color QA use PNG, APNG, or lossless WebP.",
    }


def _print(value: Any) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and verify runtime-grounded IP Studio 2D character motion."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("schema").set_defaults(handler=lambda _args: _print(_schema()))

    draft = subparsers.add_parser("draft")
    draft.add_argument("--motion-id", required=True)
    draft.add_argument("--display-name", required=True)
    draft.add_argument("--output", type=Path, required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("kit", type=Path)
    prepare.add_argument("--contract", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path)

    ready = subparsers.add_parser("ready")
    ready.add_argument("run", type=Path)

    accept = subparsers.add_parser("accept-sheet")
    accept.add_argument("run", type=Path)
    accept.add_argument("--job", required=True)
    accept.add_argument("--source", type=Path, required=True)
    accept.add_argument("--qa-note", required=True)
    accept.add_argument("--replace-complete", action="store_true")

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("run", type=Path)

    check = subparsers.add_parser("check")
    check.add_argument("run", type=Path)
    check.add_argument("--stage", choices=("prepared", "final"), default="prepared")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        if args.command == "draft":
            if args.output.exists():
                raise MotionError(f"refusing to overwrite existing file: {args.output}")
            _atomic_write(args.output, _json_bytes(_draft_contract(args.motion_id, args.display_name)))
            return _print({"status": "PASS", "contract": str(args.output.resolve())})
        if args.command == "prepare":
            return _print(_prepare(args.kit, args.contract, args.output_dir))
        if args.command == "ready":
            return _print(_check_prepared(args.run))
        if args.command == "accept-sheet":
            return _print(
                _accept_sheet(
                    args.run,
                    args.job,
                    args.source,
                    args.qa_note,
                    args.replace_complete,
                )
            )
        if args.command == "finalize":
            return _print(_finalize(args.run))
        if args.command == "check":
            return _print(_check(args.run, args.stage))
        return _print(_schema())
    except (MotionError, character_kit.ProfileError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
