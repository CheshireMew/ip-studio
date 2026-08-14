#!/usr/bin/env python3
"""Run Pet Studio's built-in Codex v2 adapter."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
SUITE_ROOT = SKILL_ROOT.parent
IP_STUDIO_SCRIPTS = SUITE_ROOT / "ip-studio" / "scripts"
MOTION_STUDIO_SCRIPTS = SUITE_ROOT / "motion-studio" / "scripts"
for dependency, label in (
    (IP_STUDIO_SCRIPTS, "ip-studio"),
    (MOTION_STUDIO_SCRIPTS, "motion-studio"),
):
    if not dependency.is_dir():
        raise RuntimeError(
            f"pet-studio requires the sibling {label} skill and its scripts"
        )
    sys.path.insert(0, str(dependency))

import character_kit
import motion_kit


SCHEMA_VERSION = "2.0"
RECORD_SCHEMA_VERSION = "2.0"
ADAPTER_ID = "codex-v2"
PET_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
PET_SCRIPTS = Path(__file__).resolve().parent / "pet"
EXPECTED_JOB_IDS = (
    "base",
    "idle",
    "running-right",
    "running-left",
    "waving",
    "jumping",
    "failed",
    "waiting",
    "running",
    "review",
    "look-cardinals",
    "look-row-9",
    "look-row-10",
)
STANDARD_STATES = EXPECTED_JOB_IDS[1:10]
LOOK_DIRECTIONS = (
    ("000", "up"),
    ("022.5", "up-right"),
    ("045", "up-right"),
    ("067.5", "up-right"),
    ("090", "right"),
    ("112.5", "down-right"),
    ("135", "down-right"),
    ("157.5", "down-right"),
    ("180", "down"),
    ("202.5", "down-left"),
    ("225", "down-left"),
    ("247.5", "down-left"),
    ("270", "left"),
    ("292.5", "up-left"),
    ("315", "up-left"),
    ("337.5", "up-left"),
)
REQUIRED_FINAL_FILES = (
    "final/spritesheet.webp",
    "final/validation-standard.json",
    "final/spritesheet-extended.webp",
    "final/validation-extended.json",
    "qa/chroma-despill-extended.json",
    "qa/contact-sheet.png",
    "qa/contact-sheet-extended.png",
    "qa/look-directions.png",
    "qa/direction-semantics.json",
    "qa/direction-blind-pairs.png",
    "qa/direction-blind-answer-key.json",
    "qa/direction-blind-verdicts-1.json",
    "qa/direction-blind-verdicts-2.json",
    "qa/direction-blind-verdicts-3.json",
    "qa/direction-blind-verdicts.json",
    "qa/direction-blind-validation.json",
    "qa/look-continuity.json",
    "qa/review.json",
    "qa/final-visual-qa.json",
)


def _build_codex_pet_contract(display_name: str) -> dict[str, Any]:
    """Describe Codex v2 through Motion Studio's platform-neutral contract."""
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
                "cells": [
                    {
                        "row": 0,
                        "column": column,
                        "clip_id": state,
                        "frame": column,
                    }
                    for column in range(frames)
                ],
            }
        )

    direction_names = dict(LOOK_DIRECTIONS)
    for group_id, _row, directions, purpose in LOOK_ROWS:
        cells: list[dict[str, Any]] = []
        for column, degrees in enumerate(directions):
            clip_id = f"look-{degrees.replace('.', '-')}"
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

    return motion_kit.validate_contract(
        {
            "schema_version": motion_kit.SCHEMA_VERSION,
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


class PetError(ValueError):
    """Raised when a pet run or package violates the Pet Studio contract."""


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise PetError(f"file does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise PetError(
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
        raise PetError(
            f"could not write {path}; staged data remains at {temporary}: {error}"
        ) from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_path(root: Path, relative: str, label: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PetError(f"{label} must stay inside the pet run")
    root = root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise PetError(f"{label} escapes the pet run") from error
    return resolved


def _detect_image(path: Path) -> str:
    if not path.is_file():
        raise PetError(f"image does not exist: {path}")
    with path.open("rb") as handle:
        header = handle.read(16)
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    raise PetError(f"unsupported raster image: {path}")


def _run_pet_script(name: str, *arguments: str) -> str:
    script = PET_SCRIPTS / name
    if not script.is_file():
        raise PetError(f"bundled pet script is missing: {script}")
    completed = subprocess.run(
        [sys.executable, str(script), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise PetError(f"{name} failed: {detail}")
    return completed.stdout.strip()


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    value = re.sub(r"-{2,}", "-", value)
    if not PET_ID_RE.fullmatch(value):
        raise PetError(
            "pet id must use lowercase letters, numbers, and single hyphens"
        )
    return value


def _profile_identity(profile: dict[str, Any]) -> str:
    anatomy = profile["anatomy"]
    head = anatomy["head"]
    body = anatomy["body"]
    surface = profile["surface"]
    wardrobe = profile["wardrobe"]
    rendering = profile["rendering"]
    view = profile["view_model"]

    appendages = "；".join(
        (
            f"{item['name']}×{item['count']}：{item['geometry']}，"
            f"相对尺寸{item['relative_size']}，根部{item['attachment_point']}，"
            f"静止路径{item['resting_shape']}，末端{item['tip_shape']}，"
            f"运动{item['movement_behavior']}"
        )
        for item in anatomy["appendages"]
    ) or "无额外附肢"
    palette = "；".join(
        (
            f"{item['name']} {item['hex']} 用于{item['placement']}，"
            f"面积关系{item['coverage']}"
        )
        for item in surface["palette"]
    )
    markings = "；".join(
        (
            f"{item['name']}位于{item['area']}，形状{item['shape']}，"
            f"边界{item['boundary']}，颜色ID{','.join(item['palette_ids'])}"
        )
        for item in surface["markings"]
    ) or "无额外纹样"
    materials = "；".join(
        f"{item['name']}覆盖{item['areas']}，表面{item['appearance']}"
        for item in surface["materials"]
    )
    pieces = "；".join(
        (
            f"{item['name']}：{item['layer']}，覆盖{item['coverage']}，"
            f"版型{item['cut_and_shape']}，颜色ID{','.join(item['palette_ids'])}，"
            f"材质ID{','.join(item['material_ids'])}，连接"
            f"{item['closure_and_attachment']}，边缘{item['trim_and_seams']}，"
            f"正面{item['front_view']}，侧面{item['side_view']}，"
            f"背面{item['back_view']}"
        )
        for item in wardrobe["pieces"]
    ) or "无独立服装部件"
    signatures = "；".join(
        (
            f"{item['name']}：几何{item['geometry']}，相对尺寸"
            f"{item['relative_scale']}，颜色ID{','.join(item['palette_ids'])}，"
            f"材质ID{','.join(item['material_ids'])}，连接{item['attachment']}，"
            f"位置{item['placement']}，正面{item['front_view']}，"
            f"侧面{item['side_view']}，背面{item['back_view']}，"
            f"运动{item['movement_behavior']}"
        )
        for item in profile["signature_elements"]
    )

    return "\n".join(
        [
            (
                f"{profile['display_name']}；{anatomy['form_category']}，"
                f"{anatomy['species_or_archetype']}；年龄感"
                f"{anatomy['age_impression']}；体型{anatomy['overall_build']}；"
                f"比例{anatomy['proportion_system']}；轮廓"
                f"{anatomy['silhouette']}。"
            ),
            (
                f"头脸：头型{head['head_shape']}；顶部"
                f"{head['ears_horns_or_top_features']}；毛发或冠部"
                f"{head['hair_fur_or_crown']}；五官布局{head['face_layout']}；"
                f"眼睛{head['eyes']}；眉部{head['eyebrows']}；"
                f"鼻口{head['nose_or_muzzle']}；嘴{head['mouth']}；"
                f"固定脸部纹样{head['distinctive_markings']}。"
            ),
            (
                f"身体：颈肩{body['neck_and_shoulders']}；躯干{body['torso']}；"
                f"前肢{body['arms_or_forelimbs']}；手爪{body['hands_or_paws']}；"
                f"髋腿{body['hips_and_legs']}；足部{body['feet_or_base']}。"
            ),
            f"附肢：{appendages}。",
            f"基础表面：{surface['base_covering']}。配色：{palette}。",
            f"纹样：{markings}。材质：{materials}。",
            (
                f"服装：{wardrobe['summary']}；层级{wardrobe['layering_order']}；"
                f"部件：{pieces}。"
            ),
            f"标志物：{signatures}。",
            (
                "桌宠缩放：所有固定点、箍、扣、吊带、链、圆环和配件之间的"
                "连接路径在 192×208 像素仍要连续可辨；可以加粗过细连接件，"
                "但不改变它们的几何关系、颜色、身体落点或安装方式。独立配件"
                "继续独立摆动，不变成身体的一部分，也不画成无连接漂浮物。"
            ),
            (
                f"各视角：正面{view['front']}；侧面{view['side']}；"
                f"背面{view['back']}；遮挡{view['occlusion_and_overlap']}；"
                f"持续可见锚点{ '、'.join(view['always_visible_landmarks']) }。"
            ),
            (
                f"画法：{rendering['style_family']}；形状"
                f"{rendering['shape_language']}；线条{rendering['linework']}；"
                f"色彩{rendering['color_treatment']}；光影"
                f"{rendering['lighting_and_shading']}；纹理"
                f"{rendering['texture']}；细节{rendering['detail_density']}。"
            ),
        ]
    )


def _compact_profile_identity(profile: dict[str, Any]) -> str:
    anatomy = profile["anatomy"]
    head = anatomy["head"]
    signature_names = "、".join(
        item["name"] for item in profile["signature_elements"]
    )
    return (
        f"{profile['display_name']}，{anatomy['species_or_archetype']}；"
        f"轮廓{anatomy['silhouette']}；比例{anatomy['proportion_system']}；"
        f"头部{head['hair_fur_or_crown']}，眼睛{head['eyes']}；"
        f"服装{profile['wardrobe']['summary']}；身份标志{signature_names}。"
    )


def _next_run_dir(kit: Path, pet_id: str) -> Path:
    root = kit / "derivatives" / "pets" / pet_id / "adapters" / ADAPTER_ID / "runs"
    revision = 1
    if root.is_dir():
        revisions = [
            int(match.group(1))
            for path in root.iterdir()
            if path.is_dir()
            and (match := re.fullmatch(r"r(\d{3})", path.name)) is not None
        ]
        if revisions:
            revision = max(revisions) + 1
    return root / f"r{revision:03d}"


def _rewrite_stage_paths(value: Any, old: str, new: str) -> Any:
    if isinstance(value, dict):
        return {
            key: _rewrite_stage_paths(item, old, new)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_rewrite_stage_paths(item, old, new) for item in value]
    if isinstance(value, str):
        return value.replace(old, new)
    return value


def _prepare(args: argparse.Namespace) -> dict[str, Any]:
    if args.adapter != ADAPTER_ID:
        raise PetError(
            f"unsupported built-in adapter: {args.adapter}; available: {ADAPTER_ID}"
        )
    kit = Path(args.kit).expanduser().resolve()
    scene_bundle = character_kit.build_prompt_bundle(
        kit,
        "scene",
        "将这个已锁定角色适配为 Codex v2 桌宠；身份结构保持不变。",
    )
    profile_path = Path(str(scene_bundle["profile"]))
    profile = character_kit.validate_locked_profile(_load_json(profile_path))
    master = Path(str(scene_bundle["master_reference"])).resolve()
    _detect_image(master)

    pet_id = _slug(args.pet_id or profile["character_id"])
    display_name = args.display_name.strip() or profile["display_name"]
    description = (
        args.description.strip()
        or f"{display_name} 的 Codex v2 桌宠，保留已锁定角色身份。"
    )
    style_notes = args.style_notes.strip() or (
        f"{profile['rendering']['style_family']}；"
        f"{profile['rendering']['shape_language']}；"
        f"{profile['rendering']['linework']}；"
        f"{profile['rendering']['color_treatment']}"
    )
    identity = _compact_profile_identity(profile)
    destination = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else _next_run_dir(kit, pet_id).resolve()
    )
    if destination.exists():
        raise PetError(f"refusing to overwrite existing pet run: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.staging"

    command = [
        "--pet-name",
        display_name,
        "--pet-id",
        pet_id,
        "--display-name",
        display_name,
        "--description",
        description,
        "--reference",
        str(master),
        "--output-dir",
        str(stage),
        "--pet-notes",
        identity,
        "--style-preset",
        args.style_preset,
        "--style-notes",
        style_notes,
        "--chroma-key",
        args.chroma_key,
    ]
    for reference in args.reference:
        command.extend(["--reference", str(Path(reference).expanduser().resolve())])

    try:
        _run_pet_script("prepare_pet_run.py", *command)
        references = stage / "references"
        shutil.copy2(profile_path, references / "character-profile.snapshot.json")
        shutil.copy2(kit / "character-guide.md", references / "character-guide.snapshot.md")
        (references / "character-identity.txt").write_text(
            identity + "\n",
            encoding="utf-8",
        )

        request_path = stage / "pet_request.json"
        request = _load_json(request_path)
        request["schema_version"] = SCHEMA_VERSION
        request["adapter"] = {
            "id": ADAPTER_ID,
            "runtime": "Codex spriteVersionNumber 2",
        }
        request["source_character"] = {
            "character_id": profile["character_id"],
            "revision": f"r{profile['revision']:03d}",
            "kit": str(kit),
            "profile_snapshot": "references/character-profile.snapshot.json",
            "profile_sha256": scene_bundle["profile_sha256"],
            "guide_snapshot": "references/character-guide.snapshot.md",
            "guide_sha256": _sha256(references / "character-guide.snapshot.md"),
            "identity_spec": "references/character-identity.txt",
            "identity_spec_sha256": _sha256(references / "character-identity.txt"),
            "master_source": str(master),
            "master_sha256": scene_bundle["master_sha256"],
            "master_run_reference": str(
                Path(request["references"][0]["copied_path"])
                .resolve()
                .relative_to(stage.resolve())
            ).replace("\\", "/"),
        }
        motion_contract = _build_codex_pet_contract(display_name)
        _atomic_write(stage / "motion-contract.json", _json_bytes(motion_contract))
        request["motion_contract"] = {
            "path": "motion-contract.json",
            "sha256": motion_kit.contract_digest(motion_contract),
        }
        _atomic_write(request_path, _json_bytes(request))

        record = {
            "record_schema_version": RECORD_SCHEMA_VERSION,
            "status": "prepared",
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "pet_id": pet_id,
            "display_name": display_name,
            "adapter": copy.deepcopy(request["adapter"]),
            "source_character": copy.deepcopy(request["source_character"]),
            "motion_contract": copy.deepcopy(request["motion_contract"]),
            "package": None,
            "installation": None,
        }
        _atomic_write(stage / "pet-run-record.json", _json_bytes(record))

        stage_text = str(stage)
        destination_text = str(destination)
        for json_path in (
            stage / "pet_request.json",
            stage / "imagegen-jobs.json",
            stage / "pet-run-record.json",
            stage / "motion-contract.json",
        ):
            data = _rewrite_stage_paths(
                _load_json(json_path),
                stage_text,
                destination_text,
            )
            _atomic_write(json_path, _json_bytes(data))
        os.replace(stage, destination)
        return _check_prepared(destination)
    except Exception as error:
        failed = destination if destination.exists() else stage
        archived: Path | None = None
        if failed.exists():
            archive_root = destination.parent / ".pet-studio-failed"
            archive_root.mkdir(parents=True, exist_ok=True)
            archived = archive_root / (
                f"{destination.name}.{uuid.uuid4().hex}.failed"
            )
            os.replace(failed, archived)
        archive_note = (
            f" Failure evidence was archived at {archived}."
            if archived is not None
            else ""
        )
        raise PetError(
            f"pet preparation failed; no final run was created.{archive_note} {error}"
        ) from error


def _job_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        raise PetError("imagegen-jobs.json jobs must be an array")
    mapped: dict[str, dict[str, Any]] = {}
    for job in jobs:
        if not isinstance(job, dict) or not isinstance(job.get("id"), str):
            raise PetError("imagegen-jobs.json contains an invalid job")
        if job.get("requires_user_confirmation") is not True:
            raise PetError(
                f"image job {job['id']} must require user confirmation before generation"
            )
        if job["id"] in mapped:
            raise PetError(f"duplicate image job: {job['id']}")
        mapped[job["id"]] = job
    if tuple(mapped) != EXPECTED_JOB_IDS:
        raise PetError(
            "image job order must be: " + ", ".join(EXPECTED_JOB_IDS)
        )
    return mapped


def _check_source_character(run: Path, request: dict[str, Any]) -> dict[str, Any]:
    source = request.get("source_character")
    if not isinstance(source, dict):
        raise PetError("pet_request.json is missing source_character")
    required = {
        "character_id",
        "revision",
        "kit",
        "profile_snapshot",
        "profile_sha256",
        "guide_snapshot",
        "guide_sha256",
        "identity_spec",
        "identity_spec_sha256",
        "master_source",
        "master_sha256",
        "master_run_reference",
    }
    if set(source) != required:
        raise PetError("source_character fields do not match the contract")

    profile_path = _safe_path(run, source["profile_snapshot"], "profile snapshot")
    profile = character_kit.validate_locked_profile(_load_json(profile_path))
    if profile["character_id"] != source["character_id"]:
        raise PetError("source character id does not match its snapshot")
    if f"r{profile['revision']:03d}" != source["revision"]:
        raise PetError("source character revision does not match its snapshot")
    author = {
        key: profile[key] for key in character_kit.AUTHOR_KEY_ORDER
    }
    canonical = json.dumps(
        author,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != source["profile_sha256"]:
        raise PetError("character profile snapshot SHA-256 mismatch")

    for field, digest_field, label in (
        ("guide_snapshot", "guide_sha256", "guide snapshot"),
        ("identity_spec", "identity_spec_sha256", "identity spec"),
    ):
        path = _safe_path(run, source[field], label)
        if _sha256(path) != source[digest_field]:
            raise PetError(f"{label} SHA-256 mismatch")

    master = Path(source["master_source"]).expanduser().resolve()
    if master.exists():
        _detect_image(master)
        if _sha256(master) != source["master_sha256"]:
            raise PetError("source character master SHA-256 mismatch")
    run_master = _safe_path(
        run,
        source["master_run_reference"],
        "master run reference",
    )
    _detect_image(run_master)
    if _sha256(run_master) != source["master_sha256"]:
        raise PetError("copied character master SHA-256 mismatch")
    return source


def _check_motion_contract(run: Path, request: dict[str, Any]) -> dict[str, Any]:
    metadata = request.get("motion_contract")
    if not isinstance(metadata, dict) or set(metadata) != {"path", "sha256"}:
        raise PetError("pet_request.json motion_contract fields do not match the contract")
    path = _safe_path(run, metadata["path"], "motion contract")
    contract = motion_kit.validate_contract(_load_json(path))
    if motion_kit.contract_digest(contract) != metadata["sha256"]:
        raise PetError("normalized motion contract SHA-256 mismatch")
    if contract["motion_id"] != "codex-pet-v2":
        raise PetError("Codex pet motion contract must use codex-pet-v2")
    clip_ids = [clip["id"] for clip in contract["clips"]]
    look_ids = [f"look-{degrees.replace('.', '-')}" for degrees, _name in LOOK_DIRECTIONS]
    if clip_ids != [*STANDARD_STATES, *look_ids]:
        raise PetError("Codex pet motion clips do not match the v2 adapter")
    group_ids = [group["id"] for group in contract["groups"]]
    if group_ids != [*STANDARD_STATES, "look-row-9", "look-row-10"]:
        raise PetError("Codex pet motion groups do not match the v2 adapter")
    return metadata


def _check_prepared(run: Path) -> dict[str, Any]:
    run = run.expanduser().resolve()
    if not run.is_dir():
        raise PetError(f"pet run does not exist: {run}")
    request = _load_json(run / "pet_request.json")
    if request.get("schema_version") != SCHEMA_VERSION:
        raise PetError(f"pet request schema_version must equal {SCHEMA_VERSION}")
    if request.get("adapter") != {
        "id": ADAPTER_ID,
        "runtime": "Codex spriteVersionNumber 2",
    }:
        raise PetError("pet request adapter does not match the Codex v2 contract")
    if request.get("sprite_version_number") != 2:
        raise PetError("pet request must use sprite_version_number 2")
    atlas = request.get("atlas")
    if not isinstance(atlas, dict) or (
        atlas.get("columns"),
        atlas.get("rows"),
        atlas.get("cell_width"),
        atlas.get("cell_height"),
        atlas.get("width"),
        atlas.get("height"),
    ) != (8, 11, 192, 208, 1536, 2288):
        raise PetError("pet request atlas contract must be 8x11 at 192x208")
    source = _check_source_character(run, request)
    motion_contract = _check_motion_contract(run, request)

    manifest = _load_json(run / "imagegen-jobs.json")
    jobs = _job_map(manifest)
    for job_id, job in jobs.items():
        prompt = _safe_path(run, job["prompt_file"], f"{job_id} prompt")
        if not prompt.is_file() or not prompt.read_text(encoding="utf-8").strip():
            raise PetError(f"{job_id} prompt is missing or empty")
        dependencies_complete = all(
            jobs[dependency].get("status") == "complete"
            for dependency in job.get("depends_on", [])
        )
        if dependencies_complete or job.get("status") == "complete":
            for item in job.get("input_images", []):
                path = _safe_path(run, item["path"], f"{job_id} input image")
                _detect_image(path)
        if job.get("status") == "complete":
            output = _safe_path(run, job["output_path"], f"{job_id} output")
            _detect_image(output)

    record = _load_json(run / "pet-run-record.json")
    if record.get("record_schema_version") != RECORD_SCHEMA_VERSION:
        raise PetError("pet-run-record.json has an unsupported schema")
    if record.get("pet_id") != request.get("pet_id"):
        raise PetError("pet run record and request pet_id mismatch")
    if record.get("adapter") != request.get("adapter"):
        raise PetError("pet run record and request adapter mismatch")
    if record.get("source_character") != source:
        raise PetError("pet run record source_character mismatch")
    if record.get("motion_contract") != motion_contract:
        raise PetError("pet run record motion_contract mismatch")

    ready = [
        job_id
        for job_id, job in jobs.items()
        if job.get("status") != "complete"
        and all(jobs[dependency].get("status") == "complete" for dependency in job["depends_on"])
    ]
    return {
        "status": "PASS",
        "stage": record.get("status"),
        "run": str(run),
        "pet_id": request["pet_id"],
        "display_name": request["display_name"],
        "adapter": request["adapter"]["id"],
        "character_id": source["character_id"],
        "character_revision": source["revision"],
        "motion_contract": str(
            _safe_path(run, motion_contract["path"], "motion contract")
        ),
        "completed_jobs": [
            job_id for job_id, job in jobs.items() if job.get("status") == "complete"
        ],
        "ready_jobs": ready,
    }


def _build_standard_intermediate(run: Path) -> None:
    """Build and validate the complete nine-row intermediate before publishing it."""
    stage = run / "qa" / f".standard-build.{uuid.uuid4().hex}.staging"
    staged_frames = stage / "frames"
    staged_final = stage / "final"
    staged_qa = stage / "qa"
    stage.mkdir(parents=True, exist_ok=False)
    try:
        _run_pet_script(
            "extract_strip_frames.py",
            "--decoded-dir",
            str(run / "decoded"),
            "--output-dir",
            str(staged_frames),
            "--states",
            "all",
            "--method",
            "auto",
        )
        _run_pet_script(
            "inspect_frames.py",
            "--frames-root",
            str(staged_frames),
            "--json-out",
            str(staged_qa / "review.json"),
            "--require-components",
        )
        _run_pet_script(
            "compose_atlas.py",
            "--frames-root",
            str(staged_frames),
            "--output",
            str(staged_final / "spritesheet.png"),
            "--webp-output",
            str(staged_final / "spritesheet.webp"),
        )
        _run_pet_script(
            "validate_atlas.py",
            str(staged_final / "spritesheet.webp"),
            "--json-out",
            str(staged_final / "validation-standard.json"),
        )
        _run_pet_script(
            "make_contact_sheet.py",
            str(staged_final / "spritesheet.webp"),
            "--output",
            str(staged_qa / "contact-sheet.png"),
        )
        _run_pet_script(
            "render_animation_previews.py",
            "--frames-root",
            str(staged_frames),
            "--output-dir",
            str(staged_qa / "previews"),
        )
    except Exception as error:
        failed_root = run / "qa" / ".pet-studio-failed"
        failed_root.mkdir(parents=True, exist_ok=True)
        archived = failed_root / f"standard-build.{uuid.uuid4().hex}.failed"
        os.replace(stage, archived)
        raise PetError(
            "standard pet intermediate failed; canonical outputs were not changed. "
            f"Failure evidence was archived at {archived}: {error}"
        ) from error

    for report_path in (
        staged_qa / "review.json",
        staged_final / "validation-standard.json",
    ):
        report = _rewrite_stage_paths(
            _load_json(report_path),
            str(stage),
            str(run),
        )
        _atomic_write(report_path, _json_bytes(report))

    destinations = (
        (staged_frames, run / "frames"),
        (staged_final, run / "final"),
        (staged_qa / "review.json", run / "qa" / "review.json"),
        (staged_qa / "contact-sheet.png", run / "qa" / "contact-sheet.png"),
        (staged_qa / "previews", run / "qa" / "previews"),
    )
    conflicts = [destination for _, destination in destinations if destination.exists()]
    if conflicts:
        failed_root = run / "qa" / ".pet-studio-failed"
        failed_root.mkdir(parents=True, exist_ok=True)
        archived = failed_root / f"standard-build.{uuid.uuid4().hex}.failed"
        os.replace(stage, archived)
        raise PetError(
            "refusing to replace existing standard intermediates: "
            + ", ".join(str(path) for path in conflicts)
            + f". New staged evidence was archived at {archived}"
        )
    for source, destination in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
    archived_root = run / "qa" / ".pet-studio-staging-records"
    archived_root.mkdir(parents=True, exist_ok=True)
    os.replace(
        stage,
        archived_root / f"standard-build.{uuid.uuid4().hex}.complete",
    )


def _replacement_closure(
    jobs: dict[str, dict[str, Any]],
    job_id: str,
) -> set[str]:
    affected = {job_id}
    changed = True
    while changed:
        changed = False
        for candidate, job in jobs.items():
            if candidate in affected:
                continue
            if any(dependency in affected for dependency in job["depends_on"]):
                affected.add(candidate)
                changed = True
    return affected


def _archive_completed_job(
    run: Path,
    manifest: dict[str, Any],
    jobs: dict[str, dict[str, Any]],
    job_id: str,
) -> None:
    if (run / "package").exists() or (run / "pet-package-record.json").exists():
        raise PetError(
            "a finalized pet run cannot replace visual jobs; create a new pet run instead"
        )
    affected = _replacement_closure(jobs, job_id)
    relative_paths: set[str] = {
        jobs[affected_job]["output_path"].replace("\\", "/")
        for affected_job in affected
    }
    if job_id == "base":
        relative_paths.update(
            {
                "references/canonical-base.png",
                "qa/look-mechanics.md",
                "qa/rows",
            }
        )
    affected_standard = affected.intersection(STANDARD_STATES)
    for state in affected_standard:
        relative_paths.add(f"qa/rows/{state}")
    if affected_standard:
        relative_paths.update(
            {
                "frames",
                "final/spritesheet.png",
                "final/spritesheet.webp",
                "final/validation-standard.json",
                "qa/review.json",
                "qa/contact-sheet.png",
                "qa/previews",
            }
        )
    if "look-cardinals" in affected:
        relative_paths.update(
            {
                "decoded/look-anchors",
                "decoded/look-anchors-approved.png",
                "qa/cardinal-anchors.json",
            }
        )
    if "look-row-9" in affected:
        relative_paths.update(
            {
                "qa/look-row-9-registered.png",
                "qa/look-row-9-registration.json",
            }
        )
    if affected.intersection({"look-cardinals", "look-row-9", "look-row-10"}):
        relative_paths.update(
            {
                "final/spritesheet-extended.png",
                "final/spritesheet-extended.webp",
                "final/spritesheet-extended.json",
                "final/validation-extended.json",
                "qa/chroma-despill-extended.json",
                "qa/contact-sheet-extended.png",
                "qa/look-directions.png",
                "qa/direction-semantics.json",
                "qa/direction-blind-pairs.png",
                "qa/direction-blind-answer-key.json",
                "qa/direction-blind-verdicts-1.json",
                "qa/direction-blind-verdicts-2.json",
                "qa/direction-blind-verdicts-3.json",
                "qa/direction-blind-verdicts.json",
                "qa/direction-blind-validation.json",
                "qa/look-continuity.json",
                "qa/final-visual-qa.json",
            }
        )

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = (
        run
        / "history"
        / "pet-job-replacements"
        / f"{timestamp}-{job_id}-{uuid.uuid4().hex}"
    )
    archive.mkdir(parents=True, exist_ok=False)

    for affected_job in affected:
        job = jobs[affected_job]
        job["status"] = "pending"
        for field in ("source_path", "completed_at", "qa_note"):
            job.pop(field, None)
    _atomic_write(run / "imagegen-jobs.json", _json_bytes(manifest))

    moved: list[str] = []
    moved_directories: list[Path] = []
    for relative in sorted(relative_paths, key=lambda value: (value.count("/"), value)):
        source = _safe_path(run, relative, f"replacement artifact {relative}")
        if any(parent == source or parent in source.parents for parent in moved_directories):
            continue
        if not source.exists():
            continue
        destination = archive / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
        moved.append(relative)
        if destination.is_dir():
            moved_directories.append(source)
    _atomic_write(
        archive / "replacement-record.json",
        _json_bytes(
            {
                "replaced_job": job_id,
                "affected_jobs": [
                    candidate
                    for candidate in EXPECTED_JOB_IDS
                    if candidate in affected
                ],
                "moved_artifacts": moved,
                "archived_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
        ),
    )


def _mark_job(
    run: Path,
    job_id: str,
    source_path: Path,
    qa_note: str,
    approve_cardinals: bool,
    replace_complete: bool,
) -> dict[str, Any]:
    prepared = _check_prepared(run)
    run = run.resolve()
    manifest_path = run / "imagegen-jobs.json"
    manifest = _load_json(manifest_path)
    jobs = _job_map(manifest)
    if job_id not in jobs:
        raise PetError(f"unknown image job: {job_id}")
    job = jobs[job_id]
    qa_note = qa_note.strip()
    if not qa_note:
        raise PetError("--qa-note must record the visual selection evidence")
    if job_id == "look-cardinals" and not approve_cardinals:
        raise PetError(
            "look-cardinals requires --approve-cardinals after normal-size semantic review"
        )
    if job_id == "look-row-9" and not (run / "qa" / "look-mechanics.md").is_file():
        raise PetError("qa/look-mechanics.md is required before look-row-9")
    source_path = source_path.expanduser().resolve()
    _detect_image(source_path)
    if job.get("status") == "complete":
        if not replace_complete:
            raise PetError(
                f"image job is already complete: {job_id}; "
                "use --replace-complete only after visual QA rejects it"
            )
        _archive_completed_job(run, manifest, jobs, job_id)
        manifest = _load_json(manifest_path)
        jobs = _job_map(manifest)
        job = jobs[job_id]
    elif replace_complete:
        raise PetError(
            f"--replace-complete requires a completed image job: {job_id}"
        )
    incomplete = [
        dependency
        for dependency in job["depends_on"]
        if jobs[dependency].get("status") != "complete"
    ]
    if incomplete:
        raise PetError(
            f"{job_id} is not ready; incomplete dependencies: {', '.join(incomplete)}"
        )
    output = _safe_path(run, job["output_path"], f"{job_id} output")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, output)

    if job_id == "base":
        canonical = run / "references" / "canonical-base.png"
        shutil.copy2(output, canonical)
    elif job_id in STANDARD_STATES:
        row_qa = run / "qa" / "rows" / job_id
        _run_pet_script(
            "extract_strip_frames.py",
            "--decoded-dir",
            str(run / "decoded"),
            "--output-dir",
            str(row_qa / "frames"),
            "--states",
            job_id,
            "--method",
            "auto",
        )
        _run_pet_script(
            "inspect_frames.py",
            "--frames-root",
            str(row_qa / "frames"),
            "--json-out",
            str(row_qa / "review.json"),
            "--states",
            job_id,
            "--require-components",
        )
        standard_will_be_complete = all(
            state == job_id or jobs[state].get("status") == "complete"
            for state in STANDARD_STATES
        )
        if standard_will_be_complete:
            _build_standard_intermediate(run)
    elif job_id == "look-cardinals":
        chroma = _load_json(run / "pet_request.json")["chroma_key"]["hex"]
        _run_pet_script(
            "extract_cardinal_anchors.py",
            "--strip",
            str(output),
            "--output-dir",
            str(run / "decoded" / "look-anchors"),
            "--chroma-key",
            chroma,
            "--json-out",
            str(run / "qa" / "cardinal-anchors.json"),
        )
        _run_pet_script(
            "compose_cardinal_anchor_strip.py",
            "--anchors-dir",
            str(run / "decoded" / "look-anchors"),
            "--output",
            str(run / "decoded" / "look-anchors-approved.png"),
        )
    elif job_id == "look-row-9":
        chroma = _load_json(run / "pet_request.json")["chroma_key"]["hex"]
        _run_pet_script(
            "assemble_extended_atlas.py",
            "--base-atlas",
            str(run / "final" / "spritesheet.webp"),
            "--look-row-9",
            str(output),
            "--neutral-cell",
            str(run / "frames" / "idle" / "00.png"),
            "--chroma-key",
            chroma,
            "--chroma-threshold",
            "96",
            "--registered-row-output",
            str(run / "qa" / "look-row-9-registered.png"),
            "--registration-manifest-output",
            str(run / "qa" / "look-row-9-registration.json"),
        )
    elif job_id == "look-row-10":
        chroma = _load_json(run / "pet_request.json")["chroma_key"]["hex"]
        _run_pet_script(
            "assemble_extended_atlas.py",
            "--base-atlas",
            str(run / "final" / "spritesheet.webp"),
            "--registered-row-9",
            str(run / "qa" / "look-row-9-registered.png"),
            "--row-9-registration",
            str(run / "qa" / "look-row-9-registration.json"),
            "--look-row-10",
            str(output),
            "--neutral-cell",
            str(run / "frames" / "idle" / "00.png"),
            "--chroma-key",
            chroma,
            "--chroma-threshold",
            "96",
            "--output",
            str(run / "final" / "spritesheet-extended.png"),
            "--webp-output",
            str(run / "final" / "spritesheet-extended.webp"),
            "--manifest-output",
            str(run / "final" / "spritesheet-extended.json"),
        )

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    job["status"] = "complete"
    job["source_path"] = str(source_path)
    job["completed_at"] = now
    job["qa_note"] = qa_note
    _atomic_write(manifest_path, _json_bytes(manifest))
    return _check_prepared(run)


def _validate_semantics(path: Path) -> dict[str, Any]:
    data = _load_json(path)
    directions = data.get("directions")
    if not isinstance(directions, list) or len(directions) != len(LOOK_DIRECTIONS):
        raise PetError("direction-semantics.json must contain all 16 directions")
    expected = dict(LOOK_DIRECTIONS)
    seen: set[str] = set()
    for entry in directions:
        if not isinstance(entry, dict):
            raise PetError("direction-semantics.json contains an invalid entry")
        label = entry.get("direction")
        if label not in expected or label in seen:
            raise PetError(f"invalid or duplicate direction semantic: {label}")
        seen.add(label)
        if entry.get("expected") != expected[label]:
            raise PetError(f"direction {label} expected label mismatch")
        if entry.get("verdict") not in {"pass", "warning"}:
            raise PetError(f"direction {label} has a failing semantic verdict")
        if not str(entry.get("observed", "")).strip() or not str(
            entry.get("reason", "")
        ).strip():
            raise PetError(f"direction {label} lacks visible semantic evidence")
    if data.get("ok") is not True:
        raise PetError("direction-semantics.json must have ok: true")
    return data


def _check_completion_inputs(run: Path) -> dict[str, Any]:
    prepared = _check_prepared(run)
    run = run.resolve()
    manifest = _load_json(run / "imagegen-jobs.json")
    jobs = _job_map(manifest)
    incomplete = [
        job_id for job_id, job in jobs.items() if job.get("status") != "complete"
    ]
    if incomplete:
        raise PetError("pet run has incomplete visual jobs: " + ", ".join(incomplete))

    for relative in REQUIRED_FINAL_FILES:
        if not _safe_path(run, relative, relative).is_file():
            raise PetError(f"required final pet artifact is missing: {relative}")
    for state in STANDARD_STATES:
        preview = run / "qa" / "previews" / f"{state}.gif"
        if not preview.is_file():
            raise PetError(f"animation preview is missing: {preview}")

    request = _load_json(run / "pet_request.json")
    chroma = request["chroma_key"]["hex"]
    atlas = run / "final" / "spritesheet-extended.webp"
    _run_pet_script(
        "validate_atlas.py",
        str(atlas),
        "--chroma-key",
        chroma,
        "--require-v2",
    )
    validation = _load_json(run / "final" / "validation-extended.json")
    if (
        validation.get("ok") is not True
        or validation.get("sprite_version_number") != 2
        or (validation.get("width"), validation.get("height")) != (1536, 2288)
    ):
        raise PetError("final v2 atlas validation did not pass")
    despill = _load_json(run / "qa" / "chroma-despill-extended.json")
    if (
        despill.get("ok") is not True
        or despill.get("algorithm") != "edge-local-chroma-spill-suppression"
    ):
        raise PetError("final chroma despill validation did not pass")
    review = _load_json(run / "qa" / "review.json")
    if review.get("ok") is not True:
        raise PetError("standard frame review did not pass")
    if Path(str(review.get("frames_root", ""))).resolve() != (run / "frames"):
        raise PetError("standard frame review does not reference canonical frames")
    standard_validation = _load_json(run / "final" / "validation-standard.json")
    if standard_validation.get("ok") is not True:
        raise PetError("standard atlas validation did not pass")
    if Path(str(standard_validation.get("file", ""))).resolve() != (
        run / "final" / "spritesheet.webp"
    ):
        raise PetError("standard atlas validation does not reference the canonical atlas")
    _validate_semantics(run / "qa" / "direction-semantics.json")
    continuity = _load_json(run / "qa" / "look-continuity.json")
    if continuity.get("ok") is not True:
        raise PetError("look continuity report did not pass")
    final_visual = _load_json(run / "qa" / "final-visual-qa.json")
    if (
        final_visual.get("ok") is not True
        or final_visual.get("visual_qa") != "pass"
        or not str(final_visual.get("reviewer", "")).strip()
    ):
        raise PetError("independent final visual QA did not pass")

    blind = _load_json(run / "qa" / "direction-blind-validation.json")
    if blind.get("ok") is not True:
        raise PetError("blind direction validation did not pass its cardinal gates")

    return {
        **prepared,
        "atlas": str(atlas),
        "atlas_sha256": _sha256(atlas),
    }


def _finalize(run: Path) -> dict[str, Any]:
    completion = _check_completion_inputs(run)
    run = run.resolve()
    request = _load_json(run / "pet_request.json")
    pet_id = request["pet_id"]
    package = run / "package" / pet_id
    if package.exists():
        raise PetError(f"refusing to overwrite existing pet package: {package}")
    stage = package.parent / f".{pet_id}.{uuid.uuid4().hex}.staging"
    stage.mkdir(parents=True, exist_ok=False)
    atlas_source = run / "final" / "spritesheet-extended.webp"
    shutil.copy2(atlas_source, stage / "spritesheet.webp")
    manifest = {
        "id": pet_id,
        "displayName": request["display_name"],
        "description": request["description"],
        "spriteVersionNumber": 2,
        "spritesheetPath": "spritesheet.webp",
    }
    _atomic_write(stage / "pet.json", _json_bytes(manifest))
    os.replace(stage, package)

    package_record = {
        "record_schema_version": RECORD_SCHEMA_VERSION,
        "pet_id": pet_id,
        "adapter": request["adapter"],
        "source_character": request["source_character"],
        "motion_contract": request["motion_contract"],
        "sprite_version_number": 2,
        "spritesheet": "spritesheet.webp",
        "spritesheet_sha256": _sha256(package / "spritesheet.webp"),
        "pet_manifest": "pet.json",
        "pet_manifest_sha256": _sha256(package / "pet.json"),
        "finalized_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    _atomic_write(run / "pet-package-record.json", _json_bytes(package_record))

    record_path = run / "pet-run-record.json"
    record = _load_json(record_path)
    record["status"] = "final"
    record["package"] = {
        "path": str(package),
        "spritesheet_sha256": package_record["spritesheet_sha256"],
        "pet_manifest_sha256": package_record["pet_manifest_sha256"],
    }
    _atomic_write(record_path, _json_bytes(record))
    summary = {
        "ok": True,
        "spriteVersionNumber": 2,
        "run": str(run),
        "character_id": request["source_character"]["character_id"],
        "character_revision": request["source_character"]["revision"],
        "motion_contract": str(run / request["motion_contract"]["path"]),
        "spritesheet": completion["atlas"],
        "spritesheet_sha256": completion["atlas_sha256"],
        "package": str(package),
        "contact_sheet": str(run / "qa" / "contact-sheet-extended.png"),
        "direction_sheet": str(run / "qa" / "look-directions.png"),
    }
    _atomic_write(run / "qa" / "run-summary.json", _json_bytes(summary))
    return _check_final(run)


def _check_final(run: Path) -> dict[str, Any]:
    completion = _check_completion_inputs(run)
    run = run.resolve()
    request = _load_json(run / "pet_request.json")
    pet_id = request["pet_id"]
    package = run / "package" / pet_id
    pet_manifest = _load_json(package / "pet.json")
    expected_manifest = {
        "id": pet_id,
        "displayName": request["display_name"],
        "description": request["description"],
        "spriteVersionNumber": 2,
        "spritesheetPath": "spritesheet.webp",
    }
    if pet_manifest != expected_manifest:
        raise PetError("packaged pet.json does not match the run request")
    packaged_sheet = package / "spritesheet.webp"
    _detect_image(packaged_sheet)
    if _sha256(packaged_sheet) != completion["atlas_sha256"]:
        raise PetError("packaged spritesheet does not match the approved final atlas")
    package_record = _load_json(run / "pet-package-record.json")
    if package_record.get("source_character") != request["source_character"]:
        raise PetError("pet package source character record mismatch")
    if package_record.get("adapter") != request["adapter"]:
        raise PetError("pet package adapter record mismatch")
    if package_record.get("motion_contract") != request["motion_contract"]:
        raise PetError("pet package motion contract record mismatch")
    if package_record.get("spritesheet_sha256") != _sha256(packaged_sheet):
        raise PetError("pet package spritesheet SHA-256 mismatch")

    record = _load_json(run / "pet-run-record.json")
    if record.get("status") != "final":
        raise PetError("pet-run-record.json is not final")
    return {
        **completion,
        "status": "PASS",
        "stage": "final",
        "package": str(package),
        "pet_manifest": str(package / "pet.json"),
        "spritesheet": str(packaged_sheet),
    }


def _install(run: Path, replace_installed: bool) -> dict[str, Any]:
    final = _check_final(run)
    run = run.resolve()
    package = Path(final["package"])
    pet_id = final["pet_id"]
    codex_root = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser().resolve()
    pets_root = codex_root / "pets"
    pets_root.mkdir(parents=True, exist_ok=True)
    destination = pets_root / pet_id
    source_hash = _sha256(package / "spritesheet.webp")

    def stage_install() -> Path:
        stage_path = pets_root / f".{pet_id}.{uuid.uuid4().hex}.installing"
        stage_path.mkdir(parents=False, exist_ok=False)
        shutil.copy2(package / "pet.json", stage_path / "pet.json")
        shutil.copy2(
            package / "spritesheet.webp",
            stage_path / "spritesheet.webp",
        )
        return stage_path

    if destination.is_dir():
        existing_sheet = destination / "spritesheet.webp"
        existing_manifest = destination / "pet.json"
        if (
            existing_sheet.is_file()
            and existing_manifest.is_file()
            and _sha256(existing_sheet) == source_hash
        ):
            action = "already-installed"
        else:
            if not replace_installed:
                raise PetError(
                    f"an installed pet already uses id {pet_id}; "
                    "rerun install with --replace-installed after approving replacement"
                )
            timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = (
                pets_root
                / ".pet-studio-backups"
                / pet_id
                / timestamp
            )
            backup.parent.mkdir(parents=True, exist_ok=True)
            os.replace(destination, backup)
            stage = stage_install()
            try:
                os.replace(stage, destination)
            except Exception:
                if not destination.exists() and backup.exists():
                    os.replace(backup, destination)
                raise
            action = "replaced-with-backup"
    elif destination.exists():
        raise PetError(f"installed pet target is not a directory: {destination}")
    else:
        stage = stage_install()
        os.replace(stage, destination)
        action = "installed"

    record_path = run / "pet-run-record.json"
    record = _load_json(record_path)
    record["installation"] = {
        "path": str(destination),
        "spritesheet_sha256": source_hash,
        "action": action,
        "installed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    _atomic_write(record_path, _json_bytes(record))
    return {
        "status": "PASS",
        "action": action,
        "pet_id": pet_id,
        "installed_pet": str(destination),
        "spritesheet_sha256": source_hash,
    }


def _schema() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "skill": "pet-studio",
        "built_in_adapters": [ADAPTER_ID],
        "sprite_version_number": 2,
        "atlas": {
            "columns": 8,
            "rows": 11,
            "cell_width": 192,
            "cell_height": 208,
            "width": 1536,
            "height": 2288,
        },
        "visual_jobs": list(EXPECTED_JOB_IDS),
        "normalized_motion_contract": {
            "schema_version": motion_kit.SCHEMA_VERSION,
            "motion_id": "codex-pet-v2",
            "role": "fixed Codex platform adapter",
        },
        "look_directions": [
            {"degrees": degrees, "expected": expected}
            for degrees, expected in LOOK_DIRECTIONS
        ],
        "commands": [
            "schema",
            "prepare",
            "ready",
            "accept-job",
            "finalize",
            "check",
            "install",
        ],
    }


def _print(value: Any) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    schema_parser = subparsers.add_parser("schema")
    schema_parser.set_defaults(handler=lambda _args: _print(_schema()))

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("kit")
    prepare.add_argument("--adapter", default=ADAPTER_ID, choices=(ADAPTER_ID,))
    prepare.add_argument("--output-dir", default="")
    prepare.add_argument("--pet-id", default="")
    prepare.add_argument("--display-name", default="")
    prepare.add_argument("--description", default="")
    prepare.add_argument("--reference", action="append", default=[])
    prepare.add_argument(
        "--style-preset",
        default="auto",
        choices=(
            "auto",
            "pixel",
            "plush",
            "clay",
            "sticker",
            "flat-vector",
            "3d-toy",
            "painterly",
            "brand-inspired",
        ),
    )
    prepare.add_argument("--style-notes", default="")
    prepare.add_argument("--chroma-key", default="auto")
    prepare.set_defaults(handler=lambda args: _print(_prepare(args)))

    ready = subparsers.add_parser("ready")
    ready.add_argument("run")
    ready.set_defaults(
        handler=lambda args: _print(
            {
                key: value
                for key, value in _check_prepared(Path(args.run)).items()
                if key in {"status", "run", "completed_jobs", "ready_jobs"}
            }
        )
    )

    accept = subparsers.add_parser("accept-job")
    accept.add_argument("run")
    accept.add_argument("--job", required=True, choices=EXPECTED_JOB_IDS)
    accept.add_argument("--source", required=True)
    accept.add_argument("--qa-note", required=True)
    accept.add_argument("--approve-cardinals", action="store_true")
    accept.add_argument(
        "--replace-complete",
        action="store_true",
        help=(
            "Archive a visually rejected completed job and every dependent artifact "
            "before accepting this replacement."
        ),
    )
    accept.set_defaults(
        handler=lambda args: _print(
            _mark_job(
                Path(args.run),
                args.job,
                Path(args.source),
                args.qa_note,
                args.approve_cardinals,
                args.replace_complete,
            )
        )
    )

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("run")
    finalize.set_defaults(handler=lambda args: _print(_finalize(Path(args.run))))

    check = subparsers.add_parser("check")
    check.add_argument("run")
    check.add_argument("--stage", choices=("prepared", "final"), default="final")
    check.set_defaults(
        handler=lambda args: _print(
            _check_prepared(Path(args.run))
            if args.stage == "prepared"
            else _check_final(Path(args.run))
        )
    )

    install = subparsers.add_parser("install")
    install.add_argument("run")
    install.add_argument("--replace-installed", action="store_true")
    install.set_defaults(
        handler=lambda args: _print(
            _install(Path(args.run), args.replace_installed)
        )
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except (PetError, character_kit.ProfileError, motion_kit.MotionError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"ERROR: filesystem operation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
