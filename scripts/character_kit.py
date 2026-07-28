#!/usr/bin/env python3
"""Create, prompt from, finalize, version, and verify IP Studio character kits."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "2.0"
CHARACTER_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
REFERENCE_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
PROVENANCE_PATH_RE = re.compile(
    r"^\$\.[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\[\d+\])?"
    r"(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[\d+\])?)*$"
)

AUTHOR_KEY_ORDER = (
    "schema_version",
    "character_id",
    "display_name",
    "language",
    "status",
    "identity",
    "anatomy",
    "surface",
    "wardrobe",
    "signature_elements",
    "view_model",
    "rendering",
    "consistency",
    "provenance",
)
AUTHOR_KEYS = set(AUTHOR_KEY_ORDER)
SYSTEM_KEYS = {"revision", "assets"}

IDENTITY_KEYS = {
    "purpose",
    "audience",
    "traits",
    "desired_impression",
    "symbolic_core",
}
ANATOMY_KEYS = {
    "form_category",
    "species_or_archetype",
    "age_impression",
    "overall_build",
    "proportion_system",
    "silhouette",
    "head",
    "body",
    "appendages",
}
HEAD_KEYS = {
    "head_shape",
    "ears_horns_or_top_features",
    "hair_fur_or_crown",
    "face_layout",
    "eyes",
    "eyebrows",
    "nose_or_muzzle",
    "mouth",
    "distinctive_markings",
}
BODY_KEYS = {
    "neck_and_shoulders",
    "torso",
    "arms_or_forelimbs",
    "hands_or_paws",
    "hips_and_legs",
    "feet_or_base",
}
APPENDAGE_KEY_ORDER = (
    "name",
    "count",
    "geometry",
    "relative_size",
    "attachment_point",
    "resting_shape",
    "tip_shape",
    "movement_behavior",
)
APPENDAGE_KEYS = set(APPENDAGE_KEY_ORDER)
SURFACE_KEYS = {
    "base_covering",
    "palette",
    "markings",
    "materials",
}
PALETTE_KEYS = {"id", "name", "hex", "role", "placement", "coverage"}
MARKING_KEYS = {"name", "area", "shape", "boundary", "palette_ids"}
MATERIAL_KEYS = {"id", "name", "areas", "appearance"}
WARDROBE_KEYS = {"summary", "layering_order", "pieces"}
PIECE_KEY_ORDER = (
    "name",
    "layer",
    "coverage",
    "cut_and_shape",
    "palette_ids",
    "material_ids",
    "closure_and_attachment",
    "trim_and_seams",
    "front_view",
    "side_view",
    "back_view",
)
PIECE_KEYS = set(PIECE_KEY_ORDER)
SIGNATURE_KEY_ORDER = (
    "name",
    "meaning",
    "geometry",
    "relative_scale",
    "palette_ids",
    "material_ids",
    "attachment",
    "placement",
    "front_view",
    "side_view",
    "back_view",
    "movement_behavior",
)
SIGNATURE_KEYS = set(SIGNATURE_KEY_ORDER)
VIEW_KEYS = {
    "front",
    "side",
    "back",
    "occlusion_and_overlap",
    "always_visible_landmarks",
}
RENDERING_KEYS = {
    "style_family",
    "shape_language",
    "linework",
    "color_treatment",
    "lighting_and_shading",
    "texture",
    "detail_density",
}
CONSISTENCY_KEYS = {"fixed", "flexible", "revision_required"}
PROVENANCE_KEYS = {"decisions"}
DECISION_KEYS = {"path", "source", "note"}


def _text_property(description: str = "") -> dict[str, Any]:
    value: dict[str, Any] = {"type": "string", "minLength": 1}
    if description:
        value["description"] = description
    return value


def _text_list_property(
    minimum: int = 0,
    maximum: int = 50,
) -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": minimum,
        "maxItems": maximum,
        "items": {"type": "string", "minLength": 1},
    }


def _path_list_property(
    minimum: int = 0,
    maximum: int = 50,
) -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": minimum,
        "maxItems": maximum,
        "items": {
            "type": "string",
            "pattern": PROVENANCE_PATH_RE.pattern,
        },
    }


def _strict_object_schema(
    required_keys: set[str],
    properties: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(required_keys),
        "properties": properties,
    }


PROFILE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "IP Studio Character Profile",
    "type": "object",
    "additionalProperties": False,
    "required": sorted(AUTHOR_KEYS),
    "properties": {
        "schema_version": {
            "const": SCHEMA_VERSION,
            "description": "角色档案合同版本。",
        },
        "character_id": {
            "type": "string",
            "pattern": CHARACTER_ID_RE.pattern,
            "description": "稳定的小写英文、数字和连字符标识。",
        },
        "display_name": {
            "type": "string",
            "minLength": 1,
            "description": "用户看到的角色名。",
        },
        "language": {
            "type": "string",
            "minLength": 2,
            "description": "档案内容和说明使用的语言，例如 zh-CN 或 en。",
        },
        "status": {
            "enum": ["draft", "locked"],
            "description": "草稿由 Agent 填写，定稿时由脚本锁定。",
        },
        "identity": {
            **_strict_object_schema(
                IDENTITY_KEYS,
                {
                "purpose": {"type": "string", "minLength": 1},
                "audience": {"type": "string", "minLength": 1},
                "traits": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
                "desired_impression": {"type": "string", "minLength": 1},
                "symbolic_core": {"type": "string", "minLength": 1},
                },
            )
        },
        "anatomy": {
            **_strict_object_schema(
                ANATOMY_KEYS,
                {
                    "form_category": {
                        "enum": [
                            "stylized-human",
                            "animal",
                            "anthropomorphic",
                            "object",
                            "fantasy-creature",
                        ]
                    },
                    "species_or_archetype": _text_property(),
                    "age_impression": _text_property(),
                    "overall_build": _text_property(),
                    "proportion_system": _text_property(),
                    "silhouette": _text_property(),
                    "head": _strict_object_schema(
                        HEAD_KEYS,
                        {key: _text_property() for key in HEAD_KEYS},
                    ),
                    "body": _strict_object_schema(
                        BODY_KEYS,
                        {key: _text_property() for key in BODY_KEYS},
                    ),
                    "appendages": {
                        "type": "array",
                        "minItems": 0,
                        "maxItems": 8,
                        "items": _strict_object_schema(
                            APPENDAGE_KEYS,
                            {
                                "name": _text_property(),
                                "count": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 16,
                                },
                                **{
                                    key: _text_property()
                                    for key in APPENDAGE_KEYS
                                    if key not in {"name", "count"}
                                },
                            },
                        ),
                    },
                },
            )
        },
        "surface": {
            **_strict_object_schema(
                SURFACE_KEYS,
                {
                    "base_covering": _text_property(),
                "palette": {
                    "type": "array",
                    "minItems": 1,
                        "maxItems": 12,
                        "items": _strict_object_schema(
                            PALETTE_KEYS,
                            {
                                "id": {
                                    "type": "string",
                                    "pattern": REFERENCE_ID_RE.pattern,
                                },
                            "name": {"type": "string", "minLength": 1},
                            "hex": {
                                "type": "string",
                                "pattern": HEX_COLOR_RE.pattern,
                            },
                            "role": {"type": "string", "minLength": 1},
                                "placement": _text_property(),
                                "coverage": _text_property(),
                            },
                        ),
                },
                    "markings": {
                        "type": "array",
                        "minItems": 0,
                        "maxItems": 16,
                        "items": _strict_object_schema(
                            MARKING_KEYS,
                            {
                                "name": _text_property(),
                                "area": _text_property(),
                                "shape": _text_property(),
                                "boundary": _text_property(),
                                "palette_ids": _text_list_property(1, 8),
                            },
                        ),
                    },
                    "materials": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 12,
                        "items": _strict_object_schema(
                            MATERIAL_KEYS,
                            {
                                "id": {
                                    "type": "string",
                                    "pattern": REFERENCE_ID_RE.pattern,
                                },
                                "name": _text_property(),
                                "areas": _text_property(),
                                "appearance": _text_property(),
                            },
                        ),
                    },
                },
            )
        },
        "wardrobe": {
            **_strict_object_schema(
                WARDROBE_KEYS,
                {
                    "summary": _text_property(),
                    "layering_order": _text_property(),
                    "pieces": {
                        "type": "array",
                        "minItems": 0,
                        "maxItems": 16,
                        "items": _strict_object_schema(
                            PIECE_KEYS,
                            {
                                "name": _text_property(),
                                "layer": _text_property(),
                                "coverage": _text_property(),
                                "cut_and_shape": _text_property(),
                                "palette_ids": _text_list_property(1, 8),
                                "material_ids": _text_list_property(1, 8),
                                "closure_and_attachment": _text_property(),
                                "trim_and_seams": _text_property(),
                                "front_view": _text_property(),
                                "side_view": _text_property(),
                                "back_view": _text_property(),
                            },
                        ),
                    },
                },
            )
        },
        "signature_elements": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 6,
            "items": _strict_object_schema(
                SIGNATURE_KEYS,
                {
                            "name": {"type": "string", "minLength": 1},
                            "meaning": {"type": "string", "minLength": 1},
                    "geometry": _text_property(),
                    "relative_scale": _text_property(),
                    "palette_ids": _text_list_property(1, 8),
                    "material_ids": _text_list_property(1, 8),
                    "attachment": _text_property(),
                    "placement": _text_property(),
                    "front_view": _text_property(),
                    "side_view": _text_property(),
                    "back_view": _text_property(),
                    "movement_behavior": _text_property(),
                },
            ),
        },
        "view_model": {
            **_strict_object_schema(
                VIEW_KEYS,
                {
                    "front": _text_property(),
                    "side": _text_property(),
                    "back": _text_property(),
                    "occlusion_and_overlap": _text_property(),
                    "always_visible_landmarks": _text_list_property(1, 20),
                },
            )
        },
        "rendering": {
            **_strict_object_schema(
                RENDERING_KEYS,
                {key: _text_property() for key in RENDERING_KEYS},
            )
        },
        "consistency": {
            **_strict_object_schema(
                CONSISTENCY_KEYS,
                {
                    "fixed": _path_list_property(3, 40),
                    "flexible": _text_list_property(1, 40),
                    "revision_required": _path_list_property(1, 40),
                },
            )
        },
        "provenance": {
            **_strict_object_schema(
                PROVENANCE_KEYS,
                {
                    "decisions": {
                    "type": "array",
                        "minItems": 1,
                        "maxItems": 100,
                        "items": _strict_object_schema(
                            DECISION_KEYS,
                            {
                                "path": {
                                    "type": "string",
                                    "pattern": r"^\$\.",
                                },
                                "source": {
                                    "enum": [
                                        "user_confirmed",
                                        "agent_inferred",
                                    ]
                                },
                                "note": _text_property(),
                            },
                        ),
                    }
                },
            )
        },
        "revision": {
            "type": "integer",
            "minimum": 1,
            "readOnly": True,
        },
        "assets": {
            "type": "object",
            "readOnly": True,
            "additionalProperties": False,
            "required": ["master_reference", "sha256", "bytes", "media_type"],
            "properties": {
                "master_reference": {"type": "string", "minLength": 1},
                "sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
                "bytes": {"type": "integer", "minimum": 1},
                "media_type": {
                    "enum": ["image/png", "image/jpeg", "image/webp"]
                },
            },
        },
    },
}


class ProfileError(ValueError):
    """Raised when a character profile or kit violates its contract."""


def _format_path(parts: list[str | int]) -> str:
    rendered = "$"
    for part in parts:
        if isinstance(part, int):
            rendered += f"[{part}]"
        else:
            rendered += f".{part}"
    return rendered


def _fail(parts: list[str | int], message: str) -> None:
    raise ProfileError(f"{_format_path(parts)}: {message}")


def _require_object(
    value: Any,
    parts: list[str | int],
    expected_keys: set[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(parts, "must be an object")
    unknown = sorted(set(value) - expected_keys)
    missing = sorted(expected_keys - set(value))
    if unknown:
        _fail(parts, "contains unsupported fields: " + ", ".join(unknown))
    if missing:
        _fail(parts, "is missing fields: " + ", ".join(missing))
    return value


def _require_text(value: Any, parts: list[str | int], max_length: int = 10000) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(parts, "must be a non-empty string")
    if len(value) > max_length:
        _fail(parts, f"must not exceed {max_length} characters")
    return value.strip()


def _require_text_list(
    value: Any,
    parts: list[str | int],
    minimum: int,
    maximum: int = 50,
) -> list[str]:
    if not isinstance(value, list):
        _fail(parts, "must be an array")
    if not minimum <= len(value) <= maximum:
        _fail(parts, f"must contain {minimum}-{maximum} items")
    cleaned: list[str] = []
    for index, item in enumerate(value):
        cleaned.append(_require_text(item, parts + [index], 1000))
    return cleaned


def _require_reference_list(
    value: Any,
    parts: list[str | int],
    valid_ids: set[str],
    reference_kind: str,
    minimum: int = 1,
    maximum: int = 8,
) -> list[str]:
    cleaned = _require_text_list(value, parts, minimum, maximum)
    duplicates = sorted(
        item for item in set(cleaned) if cleaned.count(item) > 1
    )
    if duplicates:
        _fail(parts, "contains duplicate references: " + ", ".join(duplicates))
    for index, item in enumerate(cleaned):
        if item not in valid_ids:
            _fail(
                parts + [index],
                f"references unknown {reference_kind} id: {item}",
            )
    return cleaned


_PATH_MISSING = object()


def _resolve_path(profile: dict[str, Any], path: str) -> Any:
    current: Any = profile
    for token in path[2:].split("."):
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?", token)
        if match is None or not isinstance(current, dict):
            return _PATH_MISSING
        key, index_text = match.groups()
        if key not in current:
            return _PATH_MISSING
        current = current[key]
        if index_text is not None:
            if not isinstance(current, list):
                return _PATH_MISSING
            index = int(index_text)
            if index >= len(current):
                return _PATH_MISSING
            current = current[index]
    return current


def _path_exists(profile: dict[str, Any], path: str) -> bool:
    return _resolve_path(profile, path) is not _PATH_MISSING


def _require_profile_path_list(
    value: Any,
    parts: list[str | int],
    profile: dict[str, Any],
    minimum: int,
    maximum: int,
) -> list[str]:
    cleaned = _require_text_list(value, parts, minimum, maximum)
    duplicates = sorted(
        item for item in set(cleaned) if cleaned.count(item) > 1
    )
    if duplicates:
        _fail(parts, "contains duplicate paths: " + ", ".join(duplicates))
    for index, path in enumerate(cleaned):
        if not PROVENANCE_PATH_RE.fullmatch(path):
            _fail(
                parts + [index],
                "must be a JSON path such as $.anatomy.head",
            )
        if path.startswith((
            "$.consistency",
            "$.provenance",
            "$.revision",
            "$.assets",
            "$.status",
        )):
            _fail(
                parts + [index],
                "must point to character identity content",
            )
        if not _path_exists(profile, path):
            _fail(parts + [index], "does not resolve to a profile field")
    return cleaned


def _validate_author_profile(data: Any, allow_system_fields: bool) -> dict[str, Any]:
    if not isinstance(data, dict):
        _fail([], "profile must be an object")

    allowed_keys = AUTHOR_KEYS | (SYSTEM_KEYS if allow_system_fields else set())
    unknown = sorted(set(data) - allowed_keys)
    missing = sorted(AUTHOR_KEYS - set(data))
    if unknown:
        _fail([], "contains unsupported fields: " + ", ".join(unknown))
    if missing:
        _fail([], "is missing fields: " + ", ".join(missing))

    profile = copy.deepcopy(data)
    if profile["schema_version"] != SCHEMA_VERSION:
        _fail(["schema_version"], f"must equal {SCHEMA_VERSION}")

    character_id = _require_text(profile["character_id"], ["character_id"], 64)
    if not CHARACTER_ID_RE.fullmatch(character_id):
        _fail(
            ["character_id"],
            "must use lowercase letters, numbers, and single hyphens",
        )
    profile["character_id"] = character_id
    profile["display_name"] = _require_text(
        profile["display_name"], ["display_name"], 200
    )
    profile["language"] = _require_text(profile["language"], ["language"], 32)
    if profile["status"] not in {"draft", "locked"}:
        _fail(["status"], "must be draft or locked")

    identity = _require_object(profile["identity"], ["identity"], IDENTITY_KEYS)
    for key in ("purpose", "audience", "desired_impression", "symbolic_core"):
        identity[key] = _require_text(identity[key], ["identity", key], 2000)
    identity["traits"] = _require_text_list(
        identity["traits"], ["identity", "traits"], 1, 8
    )

    anatomy = _require_object(
        profile["anatomy"], ["anatomy"], ANATOMY_KEYS
    )
    form_categories = {
        "stylized-human",
        "animal",
        "anthropomorphic",
        "object",
        "fantasy-creature",
    }
    if anatomy["form_category"] not in form_categories:
        _fail(
            ["anatomy", "form_category"],
            "must be one of: " + ", ".join(sorted(form_categories)),
        )
    for key in (
        "species_or_archetype",
        "age_impression",
        "overall_build",
        "proportion_system",
        "silhouette",
    ):
        anatomy[key] = _require_text(anatomy[key], ["anatomy", key], 3000)

    head = _require_object(
        anatomy["head"], ["anatomy", "head"], HEAD_KEYS
    )
    for key in HEAD_KEYS:
        head[key] = _require_text(
            head[key], ["anatomy", "head", key], 2000
        )

    body = _require_object(
        anatomy["body"], ["anatomy", "body"], BODY_KEYS
    )
    for key in BODY_KEYS:
        body[key] = _require_text(
            body[key], ["anatomy", "body", key], 2000
        )

    appendages = anatomy["appendages"]
    if not isinstance(appendages, list) or len(appendages) > 8:
        _fail(["anatomy", "appendages"], "must contain 0-8 appendages")
    cleaned_appendages: list[dict[str, Any]] = []
    for index, item in enumerate(appendages):
        appendage = _require_object(
            item,
            ["anatomy", "appendages", index],
            APPENDAGE_KEYS,
        )
        count = appendage["count"]
        if (
            not isinstance(count, int)
            or isinstance(count, bool)
            or not 1 <= count <= 16
        ):
            _fail(
                ["anatomy", "appendages", index, "count"],
                "must be an integer from 1 to 16",
            )
        cleaned: dict[str, Any] = {"count": count}
        for key in APPENDAGE_KEY_ORDER:
            if key == "count":
                continue
            cleaned[key] = _require_text(
                appendage[key],
                ["anatomy", "appendages", index, key],
                2000,
            )
        cleaned_appendages.append(
            {key: cleaned[key] for key in APPENDAGE_KEY_ORDER}
        )
    anatomy["appendages"] = cleaned_appendages

    surface = _require_object(
        profile["surface"], ["surface"], SURFACE_KEYS
    )
    surface["base_covering"] = _require_text(
        surface["base_covering"], ["surface", "base_covering"], 3000
    )

    palette = surface["palette"]
    if not isinstance(palette, list) or not 1 <= len(palette) <= 12:
        _fail(["surface", "palette"], "must contain 1-12 colors")
    cleaned_palette: list[dict[str, str]] = []
    palette_ids: set[str] = set()
    for index, item in enumerate(palette):
        color = _require_object(
            item, ["surface", "palette", index], PALETTE_KEYS
        )
        color_id = _require_text(
            color["id"], ["surface", "palette", index, "id"], 32
        )
        if not REFERENCE_ID_RE.fullmatch(color_id):
            _fail(
                ["surface", "palette", index, "id"],
                "must use lowercase letters, numbers, and hyphens",
            )
        if color_id in palette_ids:
            _fail(
                ["surface", "palette", index, "id"],
                f"duplicates palette id: {color_id}",
            )
        palette_ids.add(color_id)
        name = _require_text(
            color["name"], ["surface", "palette", index, "name"], 200
        )
        hex_value = _require_text(
            color["hex"], ["surface", "palette", index, "hex"], 7
        ).upper()
        if not HEX_COLOR_RE.fullmatch(hex_value):
            _fail(
                ["surface", "palette", index, "hex"],
                "must use #RRGGBB",
            )
        role = _require_text(
            color["role"], ["surface", "palette", index, "role"], 1000
        )
        placement = _require_text(
            color["placement"],
            ["surface", "palette", index, "placement"],
            2000,
        )
        coverage = _require_text(
            color["coverage"],
            ["surface", "palette", index, "coverage"],
            1000,
        )
        cleaned_palette.append(
            {
                "id": color_id,
                "name": name,
                "hex": hex_value,
                "role": role,
                "placement": placement,
                "coverage": coverage,
            }
        )
    surface["palette"] = cleaned_palette

    materials = surface["materials"]
    if not isinstance(materials, list) or not 1 <= len(materials) <= 12:
        _fail(["surface", "materials"], "must contain 1-12 materials")
    cleaned_materials: list[dict[str, str]] = []
    material_ids: set[str] = set()
    for index, item in enumerate(materials):
        material = _require_object(
            item, ["surface", "materials", index], MATERIAL_KEYS
        )
        material_id = _require_text(
            material["id"], ["surface", "materials", index, "id"], 32
        )
        if not REFERENCE_ID_RE.fullmatch(material_id):
            _fail(
                ["surface", "materials", index, "id"],
                "must use lowercase letters, numbers, and hyphens",
            )
        if material_id in material_ids:
            _fail(
                ["surface", "materials", index, "id"],
                f"duplicates material id: {material_id}",
            )
        material_ids.add(material_id)
        cleaned_materials.append(
            {
                "id": material_id,
                "name": _require_text(
                    material["name"],
                    ["surface", "materials", index, "name"],
                    200,
                ),
                "areas": _require_text(
                    material["areas"],
                    ["surface", "materials", index, "areas"],
                    2000,
                ),
                "appearance": _require_text(
                    material["appearance"],
                    ["surface", "materials", index, "appearance"],
                    2000,
                ),
            }
        )
    surface["materials"] = cleaned_materials

    markings = surface["markings"]
    if not isinstance(markings, list) or len(markings) > 16:
        _fail(["surface", "markings"], "must contain 0-16 markings")
    cleaned_markings: list[dict[str, Any]] = []
    for index, item in enumerate(markings):
        marking = _require_object(
            item, ["surface", "markings", index], MARKING_KEYS
        )
        cleaned_markings.append(
            {
                "name": _require_text(
                    marking["name"],
                    ["surface", "markings", index, "name"],
                    200,
                ),
                "area": _require_text(
                    marking["area"],
                    ["surface", "markings", index, "area"],
                    2000,
                ),
                "shape": _require_text(
                    marking["shape"],
                    ["surface", "markings", index, "shape"],
                    2000,
                ),
                "boundary": _require_text(
                    marking["boundary"],
                    ["surface", "markings", index, "boundary"],
                    2000,
                ),
                "palette_ids": _require_reference_list(
                    marking["palette_ids"],
                    ["surface", "markings", index, "palette_ids"],
                    palette_ids,
                    "palette",
                ),
            }
        )
    surface["markings"] = cleaned_markings

    wardrobe = _require_object(
        profile["wardrobe"], ["wardrobe"], WARDROBE_KEYS
    )
    wardrobe["summary"] = _require_text(
        wardrobe["summary"], ["wardrobe", "summary"], 3000
    )
    wardrobe["layering_order"] = _require_text(
        wardrobe["layering_order"], ["wardrobe", "layering_order"], 3000
    )
    pieces = wardrobe["pieces"]
    if not isinstance(pieces, list) or len(pieces) > 16:
        _fail(["wardrobe", "pieces"], "must contain 0-16 pieces")
    cleaned_pieces: list[dict[str, Any]] = []
    for index, item in enumerate(pieces):
        piece = _require_object(
            item, ["wardrobe", "pieces", index], PIECE_KEYS
        )
        cleaned_piece: dict[str, Any] = {}
        for key in PIECE_KEY_ORDER:
            if key in {"palette_ids", "material_ids"}:
                continue
            cleaned_piece[key] = _require_text(
                piece[key],
                ["wardrobe", "pieces", index, key],
                2000,
            )
        cleaned_piece["palette_ids"] = _require_reference_list(
            piece["palette_ids"],
            ["wardrobe", "pieces", index, "palette_ids"],
            palette_ids,
            "palette",
        )
        cleaned_piece["material_ids"] = _require_reference_list(
            piece["material_ids"],
            ["wardrobe", "pieces", index, "material_ids"],
            material_ids,
            "material",
        )
        cleaned_pieces.append(
            {key: cleaned_piece[key] for key in PIECE_KEY_ORDER}
        )
    wardrobe["pieces"] = cleaned_pieces

    signature_elements = profile["signature_elements"]
    if (
        not isinstance(signature_elements, list)
        or not 1 <= len(signature_elements) <= 6
    ):
        _fail(
            ["signature_elements"],
            "must contain 1-6 elements",
        )
    cleaned_elements: list[dict[str, Any]] = []
    for index, item in enumerate(signature_elements):
        element = _require_object(
            item,
            ["signature_elements", index],
            SIGNATURE_KEYS,
        )
        cleaned_element: dict[str, Any] = {}
        for key in SIGNATURE_KEY_ORDER:
            if key in {"palette_ids", "material_ids"}:
                continue
            cleaned_element[key] = _require_text(
                element[key],
                ["signature_elements", index, key],
                2000,
            )
        cleaned_element["palette_ids"] = _require_reference_list(
            element["palette_ids"],
            ["signature_elements", index, "palette_ids"],
            palette_ids,
            "palette",
        )
        cleaned_element["material_ids"] = _require_reference_list(
            element["material_ids"],
            ["signature_elements", index, "material_ids"],
            material_ids,
            "material",
        )
        cleaned_elements.append(
            {key: cleaned_element[key] for key in SIGNATURE_KEY_ORDER}
        )
    profile["signature_elements"] = cleaned_elements

    view_model = _require_object(
        profile["view_model"], ["view_model"], VIEW_KEYS
    )
    for key in VIEW_KEYS - {"always_visible_landmarks"}:
        view_model[key] = _require_text(
            view_model[key], ["view_model", key], 3000
        )
    view_model["always_visible_landmarks"] = _require_text_list(
        view_model["always_visible_landmarks"],
        ["view_model", "always_visible_landmarks"],
        1,
        20,
    )

    rendering = _require_object(
        profile["rendering"], ["rendering"], RENDERING_KEYS
    )
    for key in RENDERING_KEYS:
        rendering[key] = _require_text(
            rendering[key], ["rendering", key], 2000
        )

    consistency = _require_object(
        profile["consistency"], ["consistency"], CONSISTENCY_KEYS
    )
    consistency["fixed"] = _require_profile_path_list(
        consistency["fixed"],
        ["consistency", "fixed"],
        profile,
        3,
        40,
    )
    consistency["flexible"] = _require_text_list(
        consistency["flexible"], ["consistency", "flexible"], 1, 40
    )
    consistency["revision_required"] = _require_profile_path_list(
        consistency["revision_required"],
        ["consistency", "revision_required"],
        profile,
        1,
        40,
    )

    provenance = _require_object(
        profile["provenance"], ["provenance"], PROVENANCE_KEYS
    )
    decisions = provenance["decisions"]
    if not isinstance(decisions, list) or not 1 <= len(decisions) <= 100:
        _fail(["provenance", "decisions"], "must contain 1-100 decisions")
    cleaned_decisions: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for index, item in enumerate(decisions):
        decision = _require_object(
            item, ["provenance", "decisions", index], DECISION_KEYS
        )
        path = _require_text(
            decision["path"],
            ["provenance", "decisions", index, "path"],
            500,
        )
        if not PROVENANCE_PATH_RE.fullmatch(path):
            _fail(
                ["provenance", "decisions", index, "path"],
                "must be a JSON path such as $.signature_elements[0].attachment",
            )
        if path.startswith("$.provenance"):
            _fail(
                ["provenance", "decisions", index, "path"],
                "must point to a character conclusion, not provenance itself",
            )
        if not _path_exists(profile, path):
            _fail(
                ["provenance", "decisions", index, "path"],
                "does not resolve to a profile field",
            )
        if path in seen_paths:
            _fail(
                ["provenance", "decisions", index, "path"],
                "duplicates another provenance decision path",
            )
        seen_paths.add(path)
        source = decision["source"]
        if source not in {"user_confirmed", "agent_inferred"}:
            _fail(
                ["provenance", "decisions", index, "source"],
                "must be user_confirmed or agent_inferred",
            )
        cleaned_decisions.append(
            {
                "path": path,
                "source": source,
                "note": _require_text(
                    decision["note"],
                    ["provenance", "decisions", index, "note"],
                    2000,
                ),
            }
        )
    provenance["decisions"] = cleaned_decisions

    return profile


def _validate_locked_profile(data: Any) -> dict[str, Any]:
    profile = _validate_author_profile(data, allow_system_fields=True)
    if profile["status"] != "locked":
        _fail(["status"], "finalized profile must be locked")
    if not any(
        decision["source"] == "user_confirmed"
        for decision in profile["provenance"]["decisions"]
    ):
        _fail(
            ["provenance", "decisions"],
            "locked profile must record at least one user approval",
        )

    revision = profile.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        _fail(["revision"], "must be a positive integer")

    assets = _require_object(
        profile.get("assets"),
        ["assets"],
        {"master_reference", "sha256", "bytes", "media_type"},
    )
    assets["master_reference"] = _require_text(
        assets["master_reference"], ["assets", "master_reference"], 500
    )
    sha256 = _require_text(assets["sha256"], ["assets", "sha256"], 64)
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        _fail(["assets", "sha256"], "must be a lowercase SHA-256 digest")
    if (
        not isinstance(assets["bytes"], int)
        or isinstance(assets["bytes"], bool)
        or assets["bytes"] < 1
    ):
        _fail(["assets", "bytes"], "must be a positive integer")
    if assets["media_type"] not in {"image/png", "image/jpeg", "image/webp"}:
        _fail(["assets", "media_type"], "is not a supported raster media type")
    return profile


def validate_locked_profile(data: Any) -> dict[str, Any]:
    """Validate and normalize an archived locked character profile."""

    return _validate_locked_profile(data)


def _author_profile_only(profile: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(profile[key]) for key in AUTHOR_KEY_ORDER}


def _draft_template(
    character_id: str,
    display_name: str,
    language: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "character_id": character_id,
        "display_name": display_name,
        "language": language,
        "status": "draft",
        "identity": {
            "purpose": "",
            "audience": "",
            "traits": [],
            "desired_impression": "",
            "symbolic_core": "",
        },
        "anatomy": {
            "form_category": "",
            "species_or_archetype": "",
            "age_impression": "",
            "overall_build": "",
            "proportion_system": "",
            "silhouette": "",
            "head": {
                "head_shape": "",
                "ears_horns_or_top_features": "",
                "hair_fur_or_crown": "",
                "face_layout": "",
                "eyes": "",
                "eyebrows": "",
                "nose_or_muzzle": "",
                "mouth": "",
                "distinctive_markings": "",
            },
            "body": {
                "neck_and_shoulders": "",
                "torso": "",
                "arms_or_forelimbs": "",
                "hands_or_paws": "",
                "hips_and_legs": "",
                "feet_or_base": "",
            },
            "appendages": [],
        },
        "surface": {
            "base_covering": "",
            "palette": [],
            "markings": [],
            "materials": [],
        },
        "wardrobe": {
            "summary": "",
            "layering_order": "",
            "pieces": [],
        },
        "signature_elements": [],
        "view_model": {
            "front": "",
            "side": "",
            "back": "",
            "occlusion_and_overlap": "",
            "always_visible_landmarks": [],
        },
        "rendering": {
            "style_family": "",
            "shape_language": "",
            "linework": "",
            "color_treatment": "",
            "lighting_and_shading": "",
            "texture": "",
            "detail_density": "",
        },
        "consistency": {
            "fixed": [],
            "flexible": [],
            "revision_required": [],
        },
        "provenance": {"decisions": []},
    }


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ProfileError(f"file does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise ProfileError(
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
        raise ProfileError(
            f"could not write {path}; staged data remains at {temporary}: {error}"
        ) from error


def _write_new_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise ProfileError(f"refusing to overwrite existing file: {path}") from error


def _detect_image(path: Path) -> tuple[str, str]:
    if not path.is_file():
        raise ProfileError(f"master image does not exist: {path}")
    with path.open("rb") as handle:
        header = handle.read(16)
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise ProfileError("master image must be a valid PNG, JPEG, or WebP file")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_asset_path(kit: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ProfileError("assets.master_reference must stay inside the kit")
    kit_resolved = kit.resolve()
    resolved = (kit / candidate).resolve()
    try:
        resolved.relative_to(kit_resolved)
    except ValueError as error:
        raise ProfileError("assets.master_reference escapes the kit") from error
    return resolved


def _path_label(
    profile: dict[str, Any],
    path: str,
    chinese: bool,
) -> str:
    labels_zh = {
        "$.identity": "角色定位与象征核心",
        "$.anatomy": "完整形体结构",
        "$.anatomy.form_category": "角色形态类别",
        "$.anatomy.species_or_archetype": "物种或角色原型",
        "$.anatomy.proportion_system": "头身与相对比例",
        "$.anatomy.silhouette": "主轮廓",
        "$.anatomy.head": "头部与脸部几何",
        "$.anatomy.body": "躯干与四肢结构",
        "$.anatomy.appendages": "尾巴、翅膀等附肢结构",
        "$.surface": "颜色、纹样与材质地图",
        "$.surface.palette": "配色与每种颜色的落点",
        "$.surface.markings": "固定纹样和色块边界",
        "$.surface.materials": "材质区域与表面表现",
        "$.wardrobe": "服装层级、版型与连接",
        "$.signature_elements": "全部标志性元素",
        "$.view_model": "正面、侧面与背面结构",
        "$.rendering": "完整绘制方式",
        "$.rendering.style_family": "最终绘制风格类别",
    }
    labels_en = {
        "$.identity": "role, audience, and symbolic core",
        "$.anatomy": "complete anatomy and construction",
        "$.anatomy.form_category": "character form category",
        "$.anatomy.species_or_archetype": "species or archetype",
        "$.anatomy.proportion_system": "head-to-body and relative proportions",
        "$.anatomy.silhouette": "primary silhouette",
        "$.anatomy.head": "head and facial geometry",
        "$.anatomy.body": "torso and limb construction",
        "$.anatomy.appendages": "tail, wing, or other appendage construction",
        "$.surface": "color, marking, and material map",
        "$.surface.palette": "palette and exact color placement",
        "$.surface.markings": "fixed markings and color boundaries",
        "$.surface.materials": "material zones and surface appearance",
        "$.wardrobe": "wardrobe layers, cut, and attachment",
        "$.signature_elements": "all signature elements",
        "$.view_model": "front, side, and back construction",
        "$.rendering": "complete rendering treatment",
        "$.rendering.style_family": "final rendering style family",
    }
    direct = (labels_zh if chinese else labels_en).get(path)
    if direct:
        return direct

    signature_match = re.fullmatch(r"\$\.signature_elements\[(\d+)\]", path)
    if signature_match:
        index = int(signature_match.group(1))
        element = profile["signature_elements"][index]
        return (
            f"标志性元素“{element['name']}”"
            if chinese
            else f"signature element “{element['name']}”"
        )

    final_key = re.sub(r"\[\d+\]$", "", path.rsplit(".", 1)[-1])
    return final_key.replace("_", " ")


def _render_guide(profile: dict[str, Any]) -> str:
    revision_label = f"r{profile['revision']:03d}"
    identity = profile["identity"]
    anatomy = profile["anatomy"]
    head = anatomy["head"]
    body = anatomy["body"]
    surface = profile["surface"]
    wardrobe = profile["wardrobe"]
    view_model = profile["view_model"]
    rendering = profile["rendering"]
    consistency = profile["consistency"]
    assets = profile["assets"]
    chinese = str(profile["language"]).lower().startswith("zh")

    palette = "\n".join(
        (
            f"- **{item['name']}** `{item['hex']}`（`{item['id']}`）："
            f"{item['role']}；落点：{item['placement']}；面积关系：{item['coverage']}"
            if chinese
            else (
                f"- **{item['name']}** `{item['hex']}` (`{item['id']}`): "
                f"{item['role']}; placement: {item['placement']}; "
                f"coverage: {item['coverage']}"
            )
        )
        for item in surface["palette"]
    )
    materials = "\n".join(
        (
            f"- **{item['name']}**（`{item['id']}`）：{item['areas']}；"
            f"外观：{item['appearance']}"
            if chinese
            else (
                f"- **{item['name']}** (`{item['id']}`): {item['areas']}; "
                f"appearance: {item['appearance']}"
            )
        )
        for item in surface["materials"]
    )
    markings = "\n".join(
        (
            f"- **{item['name']}**：{item['area']}；形状：{item['shape']}；"
            f"边界：{item['boundary']}；颜色：{', '.join(item['palette_ids'])}"
            if chinese
            else (
                f"- **{item['name']}**: {item['area']}; shape: {item['shape']}; "
                f"boundary: {item['boundary']}; "
                f"colors: {', '.join(item['palette_ids'])}"
            )
        )
        for item in surface["markings"]
    )
    appendages = "\n".join(
        (
            f"- **{item['name']} ×{item['count']}**：{item['geometry']}；"
            f"相对尺寸：{item['relative_size']}；根部：{item['attachment_point']}；"
            f"静止形态：{item['resting_shape']}；末端：{item['tip_shape']}；"
            f"运动：{item['movement_behavior']}"
            if chinese
            else (
                f"- **{item['name']} ×{item['count']}**: {item['geometry']}; "
                f"relative size: {item['relative_size']}; "
                f"root: {item['attachment_point']}; "
                f"resting shape: {item['resting_shape']}; "
                f"tip: {item['tip_shape']}; movement: {item['movement_behavior']}"
            )
        )
        for item in anatomy["appendages"]
    )
    pieces = "\n".join(
        (
            f"- **{item['name']}**（{item['layer']}）：覆盖 {item['coverage']}；"
            f"版型 {item['cut_and_shape']}；颜色 {', '.join(item['palette_ids'])}；"
            f"材质 {', '.join(item['material_ids'])}；连接 {item['closure_and_attachment']}；"
            f"边缘与缝线 {item['trim_and_seams']}；正面 {item['front_view']}；"
            f"侧面 {item['side_view']}；背面 {item['back_view']}"
            if chinese
            else (
                f"- **{item['name']}** ({item['layer']}): covers {item['coverage']}; "
                f"cut {item['cut_and_shape']}; colors {', '.join(item['palette_ids'])}; "
                f"materials {', '.join(item['material_ids'])}; "
                f"closure {item['closure_and_attachment']}; "
                f"trim and seams {item['trim_and_seams']}; "
                f"front {item['front_view']}; side {item['side_view']}; "
                f"back {item['back_view']}"
            )
        )
        for item in wardrobe["pieces"]
    )
    signature = "\n".join(
        (
            f"- **{item['name']}**：含义 {item['meaning']}；几何 {item['geometry']}；"
            f"相对尺寸 {item['relative_scale']}；颜色 {', '.join(item['palette_ids'])}；"
            f"材质 {', '.join(item['material_ids'])}；连接 {item['attachment']}；"
            f"位置 {item['placement']}；正面 {item['front_view']}；"
            f"侧面 {item['side_view']}；背面 {item['back_view']}；"
            f"运动 {item['movement_behavior']}"
            if chinese
            else (
                f"- **{item['name']}**: meaning {item['meaning']}; "
                f"geometry {item['geometry']}; scale {item['relative_scale']}; "
                f"colors {', '.join(item['palette_ids'])}; "
                f"materials {', '.join(item['material_ids'])}; "
                f"attachment {item['attachment']}; placement {item['placement']}; "
                f"front {item['front_view']}; side {item['side_view']}; "
                f"back {item['back_view']}; movement {item['movement_behavior']}"
            )
        )
        for item in profile["signature_elements"]
    )
    fixed = "\n".join(
        f"- {_path_label(profile, item, chinese)}"
        for item in consistency["fixed"]
    )
    flexible = "\n".join(f"- {item}" for item in consistency["flexible"])
    revision_required = "\n".join(
        f"- {_path_label(profile, item, chinese)}"
        for item in consistency["revision_required"]
    )
    landmarks = "\n".join(
        f"- {item}" for item in view_model["always_visible_landmarks"]
    )
    confirmed = "\n".join(
        f"- {item['note']}"
        for item in profile["provenance"]["decisions"]
        if item["source"] == "user_confirmed"
    )
    inferred = "\n".join(
        f"- {item['note']}"
        for item in profile["provenance"]["decisions"]
        if item["source"] == "agent_inferred"
    )

    if chinese:
        return f"""<!-- 由 character-profile.json 自动生成；请在角色档案中更新角色设定。 -->
# {profile['display_name']}

当前版本：**{revision_label}**<br>
角色标识：`{profile['character_id']}`

## 角色定位

- 用途：{identity['purpose']}
- 受众：{identity['audience']}
- 性格信号：{'、'.join(identity['traits'])}
- 希望留下的印象：{identity['desired_impression']}
- 象征核心：{identity['symbolic_core']}

## 形体结构

- 形态类别：{anatomy['form_category']}
- 物种或原型：{anatomy['species_or_archetype']}
- 年龄感：{anatomy['age_impression']}
- 整体体型：{anatomy['overall_build']}
- 比例系统：{anatomy['proportion_system']}
- 主轮廓：{anatomy['silhouette']}

### 头部与脸

- 头型：{head['head_shape']}
- 耳朵、角或顶部结构：{head['ears_horns_or_top_features']}
- 头发、毛簇或冠部：{head['hair_fur_or_crown']}
- 五官布局：{head['face_layout']}
- 眼睛：{head['eyes']}
- 眉部：{head['eyebrows']}
- 鼻部或口鼻部：{head['nose_or_muzzle']}
- 嘴部：{head['mouth']}
- 独特纹样：{head['distinctive_markings']}

### 身体

- 颈部与肩部：{body['neck_and_shoulders']}
- 躯干：{body['torso']}
- 手臂或前肢：{body['arms_or_forelimbs']}
- 手或爪：{body['hands_or_paws']}
- 髋部与腿：{body['hips_and_legs']}
- 足部或底座：{body['feet_or_base']}

### 附肢

{appendages or '- 无额外附肢；身体结构已在上方完整说明。'}

## 表面、颜色与材质

- 基础表面：{surface['base_covering']}

### 配色

{palette}

### 纹样与色块边界

{markings or '- 无额外纹样；颜色边界由基础表面与配色落点决定。'}

### 材质

{materials}

## 服装结构

- 总体：{wardrobe['summary']}
- 穿着层级：{wardrobe['layering_order']}

{pieces or '- 无独立服装部件；角色外观由身体表面与标志性元素构成。'}

### 标志性元素

{signature}

## 各视角复原

- 正面：{view_model['front']}
- 侧面：{view_model['side']}
- 背面：{view_model['back']}
- 遮挡与前后关系：{view_model['occlusion_and_overlap']}

### 各角度仍要能识别的锚点

{landmarks}

## 绘制方式

- 风格类别：{rendering['style_family']}
- 形状语言：{rendering['shape_language']}
- 线条：{rendering['linework']}
- 色彩处理：{rendering['color_treatment']}
- 光影：{rendering['lighting_and_shading']}
- 纹理：{rendering['texture']}
- 细节密度：{rendering['detail_density']}

## 一致性边界

### 始终保留

{fixed}

### 可以变化

{flexible}

### 改变后需要升版

{revision_required}

## 主参考图

`{assets['master_reference']}`

SHA-256：`{assets['sha256']}`

## 决策来源

### 用户确认

{confirmed or '- 当前版本未记录单独的用户确认项。'}

### Agent 补全

{inferred or '- 当前版本没有由 Agent 补全的结构。'}

以后生成角色视觉时，同时读取 `character-profile.json` 和这张主参考图，并从档案生成身份提示词；姿势、动作、场景与画幅只作为当次任务输入。侧面和背面说明用于保持结构，不代表默认生成多视图设定图。
"""

    return f"""<!-- Generated from character-profile.json; update the profile to change the character. -->
# {profile['display_name']}

Current revision: **{revision_label}**<br>
Character ID: `{profile['character_id']}`

## Role

- Purpose: {identity['purpose']}
- Audience: {identity['audience']}
- Traits: {', '.join(identity['traits'])}
- Intended impression: {identity['desired_impression']}
- Symbolic core: {identity['symbolic_core']}

## Anatomy and construction

- Form category: {anatomy['form_category']}
- Species or archetype: {anatomy['species_or_archetype']}
- Age impression: {anatomy['age_impression']}
- Overall build: {anatomy['overall_build']}
- Proportion system: {anatomy['proportion_system']}
- Silhouette: {anatomy['silhouette']}

### Head and face

- Head shape: {head['head_shape']}
- Ears, horns, or top features: {head['ears_horns_or_top_features']}
- Hair, fur, or crown: {head['hair_fur_or_crown']}
- Face layout: {head['face_layout']}
- Eyes: {head['eyes']}
- Eyebrows: {head['eyebrows']}
- Nose or muzzle: {head['nose_or_muzzle']}
- Mouth: {head['mouth']}
- Distinctive markings: {head['distinctive_markings']}

### Body

- Neck and shoulders: {body['neck_and_shoulders']}
- Torso: {body['torso']}
- Arms or forelimbs: {body['arms_or_forelimbs']}
- Hands or paws: {body['hands_or_paws']}
- Hips and legs: {body['hips_and_legs']}
- Feet or base: {body['feet_or_base']}

### Appendages

{appendages or '- No additional appendages; the body structure above is complete.'}

## Surface, color, and material

- Base covering: {surface['base_covering']}

### Palette

{palette}

### Markings and color boundaries

{markings or '- No additional markings; boundaries follow the base covering and palette placement.'}

### Materials

{materials}

## Wardrobe construction

- Summary: {wardrobe['summary']}
- Layering order: {wardrobe['layering_order']}

{pieces or '- No separate wardrobe pieces; the appearance comes from the body surface and signature elements.'}

### Signature elements

{signature}

## View reconstruction

- Front: {view_model['front']}
- Side: {view_model['side']}
- Back: {view_model['back']}
- Occlusion and overlap: {view_model['occlusion_and_overlap']}

### Landmarks visible across angles

{landmarks}

## Rendering

- Style family: {rendering['style_family']}
- Shape language: {rendering['shape_language']}
- Linework: {rendering['linework']}
- Color treatment: {rendering['color_treatment']}
- Lighting and shading: {rendering['lighting_and_shading']}
- Texture: {rendering['texture']}
- Detail density: {rendering['detail_density']}

## Consistency boundaries

### Always preserve

{fixed}

### May vary

{flexible}

### Requires a new revision

{revision_required}

## Master reference

`{assets['master_reference']}`

SHA-256: `{assets['sha256']}`

## Decision provenance

### User confirmed

{confirmed or '- No separately recorded user-confirmed item in this revision.'}

### Agent completed

{inferred or '- No structure was completed by the Agent in this revision.'}

For future visuals, read both `character-profile.json` and this master reference, and derive the identity prompt from the profile. Keep pose, action, scene, framing, and aspect ratio in the current task. Side and back descriptions preserve construction; they do not request a multi-view sheet by default.
"""


def _render_generation_prompt(
    profile: dict[str, Any],
    purpose: str,
    task: str,
) -> str:
    identity = profile["identity"]
    anatomy = profile["anatomy"]
    head = anatomy["head"]
    body = anatomy["body"]
    surface = profile["surface"]
    wardrobe = profile["wardrobe"]
    view_model = profile["view_model"]
    rendering = profile["rendering"]
    consistency = profile["consistency"]
    chinese = str(profile["language"]).lower().startswith("zh")
    palette_labels = {
        item["id"]: f"{item['name']} {item['hex']}"
        for item in surface["palette"]
    }
    material_labels = {
        item["id"]: item["name"] for item in surface["materials"]
    }
    reference_separator = "、" if chinese else ", "

    def color_refs(ids: list[str]) -> str:
        return reference_separator.join(palette_labels[item] for item in ids)

    def material_refs(ids: list[str]) -> str:
        return reference_separator.join(material_labels[item] for item in ids)

    if chinese:
        purpose_text = {
            "master": (
                "制作一张正式主参考图：单角色、完整全身、正面或轻微三分之四视角、"
                "中性自然站姿、干净浅色背景。脸、身体比例、服装层级、配色落点与"
                "全部标志性元素清楚可见。"
            ),
            "consistency": (
                "制作一张一致性测试图：使用与主参考图不同的姿势和表情，以及简单背景；"
                "仍完整保留角色结构、颜色落点、材质、服装连接和标志性元素。"
            ),
            "scene": task,
        }[purpose]
        intro = (
            "以这份角色重建规范作为唯一身份依据。只输出本次任务要求的一张图；"
            "正面、侧面和背面描述共同规定角色结构，不表示要制作多视图排版。"
        )
        if purpose != "master":
            intro += (
                "随输入提供的图片是已批准的唯一主参考图，用它保持角色身份、"
                "比例、颜色和画法。"
            )
        palette = "；".join(
            (
                f"{item['name']} {item['hex']}：{item['role']}，"
                f"落在{item['placement']}，面积关系{item['coverage']}"
            )
            for item in surface["palette"]
        )
        markings = "；".join(
            (
                f"{item['name']}位于{item['area']}，形状{item['shape']}，"
                f"边界{item['boundary']}，颜色{color_refs(item['palette_ids'])}"
            )
            for item in surface["markings"]
        ) or "没有额外纹样"
        materials = "；".join(
            f"{item['name']}用于{item['areas']}，呈现{item['appearance']}"
            for item in surface["materials"]
        )
        appendages = "；".join(
            (
                f"{item['name']}共{item['count']}个，{item['geometry']}，"
                f"相对尺寸{item['relative_size']}，根部{item['attachment_point']}，"
                f"静止时{item['resting_shape']}，末端{item['tip_shape']}，"
                f"运动时{item['movement_behavior']}"
            )
            for item in anatomy["appendages"]
        ) or "没有头部与四肢之外的附肢"
        pieces = "；".join(
            (
                f"{item['name']}属于{item['layer']}，覆盖{item['coverage']}，"
                f"版型{item['cut_and_shape']}，颜色{color_refs(item['palette_ids'])}，"
                f"材质{material_refs(item['material_ids'])}，"
                f"连接方式{item['closure_and_attachment']}，"
                f"边缘与缝线{item['trim_and_seams']}，"
                f"正面{item['front_view']}，侧面{item['side_view']}，"
                f"背面{item['back_view']}"
            )
            for item in wardrobe["pieces"]
        ) or "没有独立服装部件"
        signatures = "；".join(
            (
                f"{item['name']}：含义{item['meaning']}，几何{item['geometry']}，"
                f"相对尺寸{item['relative_scale']}，颜色{color_refs(item['palette_ids'])}，"
                f"材质{material_refs(item['material_ids'])}，"
                f"连接方式{item['attachment']}，位置{item['placement']}；"
                f"正面{item['front_view']}，侧面{item['side_view']}，"
                f"背面{item['back_view']}，运动时{item['movement_behavior']}"
            )
            for item in profile["signature_elements"]
        )
        lines = [
            intro,
            f"本次任务：{purpose_text}",
            (
                f"角色定位：{profile['display_name']}；用途{identity['purpose']}；"
                f"受众{identity['audience']}；性格信号{ '、'.join(identity['traits']) }；"
                f"第一印象{identity['desired_impression']}；"
                f"象征核心{identity['symbolic_core']}。"
            ),
            (
                f"整体形体：{anatomy['form_category']}，"
                f"{anatomy['species_or_archetype']}；年龄感{anatomy['age_impression']}；"
                f"体型{anatomy['overall_build']}；比例{anatomy['proportion_system']}；"
                f"轮廓{anatomy['silhouette']}。"
            ),
            (
                f"头部：头型{head['head_shape']}；顶部结构"
                f"{head['ears_horns_or_top_features']}；头发或毛簇"
                f"{head['hair_fur_or_crown']}；五官布局{head['face_layout']}；"
                f"眼睛{head['eyes']}；眉部{head['eyebrows']}；"
                f"鼻部或口鼻部{head['nose_or_muzzle']}；嘴部{head['mouth']}；"
                f"头部纹样{head['distinctive_markings']}。"
            ),
            (
                f"身体：颈肩{body['neck_and_shoulders']}；躯干{body['torso']}；"
                f"手臂或前肢{body['arms_or_forelimbs']}；手或爪{body['hands_or_paws']}；"
                f"髋腿{body['hips_and_legs']}；足部或底座{body['feet_or_base']}。"
            ),
            f"附肢：{appendages}。",
            f"基础表面：{surface['base_covering']}。",
            f"颜色地图：{palette}。",
            f"纹样地图：{markings}。",
            f"材质地图：{materials}。",
            (
                f"服装：{wardrobe['summary']}；穿着顺序"
                f"{wardrobe['layering_order']}；部件：{pieces}。"
            ),
            f"标志性元素：{signatures}。",
            (
                f"视角结构：正面{view_model['front']}；侧面{view_model['side']}；"
                f"背面{view_model['back']}；遮挡与前后关系"
                f"{view_model['occlusion_and_overlap']}；"
                f"各角度识别锚点{ '、'.join(view_model['always_visible_landmarks']) }。"
            ),
            (
                f"绘制方式：{rendering['style_family']}；形状语言"
                f"{rendering['shape_language']}；线条{rendering['linework']}；"
                f"色彩{rendering['color_treatment']}；光影"
                f"{rendering['lighting_and_shading']}；纹理{rendering['texture']}；"
                f"细节密度{rendering['detail_density']}。"
            ),
            (
                "一致性：以上全部身份结构保持一致；"
                f"当次只允许变化{ '、'.join(consistency['flexible']) }。"
            ),
        ]
        if task and purpose != "scene":
            lines.append(f"本次附加要求：{task}")
        return "\n".join(lines)

    purpose_text = {
        "master": (
            "Create one formal master reference: one full-body character, front "
            "or slight three-quarter view, neutral natural stance, clean light "
            "background, with the face, proportions, wardrobe layers, color "
            "placement, and every signature element clearly visible."
        ),
        "consistency": (
            "Create one consistency test image with a different pose and "
            "expression and a simple background while preserving all identity "
            "construction, color placement, materials, clothing connections, "
            "and signature elements."
        ),
        "scene": task,
    }[purpose]
    intro = (
        "Use this reconstruction specification as the sole character identity. "
        "Output one image for the current task. Front, side, and back descriptions "
        "jointly define construction and do not request a multi-view layout."
    )
    if purpose != "master":
        intro += (
            " The supplied image is the single approved master reference; use it "
            "to preserve identity, proportions, color placement, and rendering."
        )
    palette = "; ".join(
        (
            f"{item['name']} {item['hex']}: {item['role']}, placed on "
            f"{item['placement']}, coverage {item['coverage']}"
        )
        for item in surface["palette"]
    )
    markings = "; ".join(
        (
            f"{item['name']} on {item['area']}, shape {item['shape']}, "
            f"boundary {item['boundary']}, colors {color_refs(item['palette_ids'])}"
        )
        for item in surface["markings"]
    ) or "no additional markings"
    materials = "; ".join(
        f"{item['name']} on {item['areas']}, appearance {item['appearance']}"
        for item in surface["materials"]
    )
    appendages = "; ".join(
        (
            f"{item['name']} ×{item['count']}, {item['geometry']}, "
            f"relative size {item['relative_size']}, rooted at "
            f"{item['attachment_point']}, resting {item['resting_shape']}, "
            f"tip {item['tip_shape']}, movement {item['movement_behavior']}"
        )
        for item in anatomy["appendages"]
    ) or "no appendages beyond the head and limbs"
    pieces = "; ".join(
        (
            f"{item['name']} at {item['layer']}, covers {item['coverage']}, "
            f"cut {item['cut_and_shape']}, colors {color_refs(item['palette_ids'])}, "
            f"materials {material_refs(item['material_ids'])}, closure "
            f"{item['closure_and_attachment']}, trim {item['trim_and_seams']}, "
            f"front {item['front_view']}, side {item['side_view']}, "
            f"back {item['back_view']}"
        )
        for item in wardrobe["pieces"]
    ) or "no separate wardrobe pieces"
    signatures = "; ".join(
        (
            f"{item['name']}: meaning {item['meaning']}, geometry "
            f"{item['geometry']}, relative scale {item['relative_scale']}, "
            f"colors {color_refs(item['palette_ids'])}, "
            f"materials {material_refs(item['material_ids'])}, attachment "
            f"{item['attachment']}, placement {item['placement']}, "
            f"front {item['front_view']}, side {item['side_view']}, "
            f"back {item['back_view']}, movement {item['movement_behavior']}"
        )
        for item in profile["signature_elements"]
    )
    lines = [
        intro,
        f"Current task: {purpose_text}",
        (
            f"Role: {profile['display_name']}; purpose {identity['purpose']}; "
            f"audience {identity['audience']}; traits {', '.join(identity['traits'])}; "
            f"impression {identity['desired_impression']}; "
            f"symbolic core {identity['symbolic_core']}."
        ),
        (
            f"Overall anatomy: {anatomy['form_category']}, "
            f"{anatomy['species_or_archetype']}; age impression "
            f"{anatomy['age_impression']}; build {anatomy['overall_build']}; "
            f"proportions {anatomy['proportion_system']}; "
            f"silhouette {anatomy['silhouette']}."
        ),
        (
            f"Head: shape {head['head_shape']}; top features "
            f"{head['ears_horns_or_top_features']}; hair or fur "
            f"{head['hair_fur_or_crown']}; face layout {head['face_layout']}; "
            f"eyes {head['eyes']}; eyebrows {head['eyebrows']}; "
            f"nose or muzzle {head['nose_or_muzzle']}; mouth {head['mouth']}; "
            f"head markings {head['distinctive_markings']}."
        ),
        (
            f"Body: neck and shoulders {body['neck_and_shoulders']}; "
            f"torso {body['torso']}; arms or forelimbs "
            f"{body['arms_or_forelimbs']}; hands or paws {body['hands_or_paws']}; "
            f"hips and legs {body['hips_and_legs']}; "
            f"feet or base {body['feet_or_base']}."
        ),
        f"Appendages: {appendages}.",
        f"Base surface: {surface['base_covering']}.",
        f"Color map: {palette}.",
        f"Marking map: {markings}.",
        f"Material map: {materials}.",
        (
            f"Wardrobe: {wardrobe['summary']}; layering "
            f"{wardrobe['layering_order']}; pieces: {pieces}."
        ),
        f"Signature elements: {signatures}.",
        (
            f"View construction: front {view_model['front']}; "
            f"side {view_model['side']}; back {view_model['back']}; "
            f"occlusion and overlap {view_model['occlusion_and_overlap']}; "
            f"cross-angle landmarks "
            f"{', '.join(view_model['always_visible_landmarks'])}."
        ),
        (
            f"Rendering: {rendering['style_family']}; shape language "
            f"{rendering['shape_language']}; linework {rendering['linework']}; "
            f"color {rendering['color_treatment']}; light and shading "
            f"{rendering['lighting_and_shading']}; texture "
            f"{rendering['texture']}; detail density "
            f"{rendering['detail_density']}."
        ),
        (
            "Consistency: preserve every identity field above; "
            f"the current task may vary only {', '.join(consistency['flexible'])}."
        ),
    ]
    if task and purpose != "scene":
        lines.append(f"Additional task instruction: {task}")
    return "\n".join(lines)


def _copy_master_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ProfileError(f"refusing to overwrite existing file: {destination}")
    temporary = destination.with_name(
        f".{destination.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with source.open("rb") as source_handle, temporary.open("xb") as target:
            shutil.copyfileobj(source_handle, target, length=1024 * 1024)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, destination)
    except Exception as error:
        raise ProfileError(
            f"could not copy master image; staged data remains at {temporary}: {error}"
        ) from error


def _validate_profile_asset(kit: Path, profile: dict[str, Any]) -> Path:
    master = _safe_asset_path(kit, profile["assets"]["master_reference"])
    media_type, _ = _detect_image(master)
    if media_type != profile["assets"]["media_type"]:
        raise ProfileError(
            f"master media type mismatch: profile says "
            f"{profile['assets']['media_type']}, file is {media_type}"
        )
    actual_size = master.stat().st_size
    if actual_size != profile["assets"]["bytes"]:
        raise ProfileError(
            f"master byte size mismatch: profile says "
            f"{profile['assets']['bytes']}, file is {actual_size}"
        )
    actual_hash = _sha256(master)
    if actual_hash != profile["assets"]["sha256"]:
        raise ProfileError("master SHA-256 does not match character-profile.json")
    return master


def _read_current_profile(kit: Path) -> dict[str, Any] | None:
    profile_path = kit / "character-profile.json"
    if not profile_path.exists():
        return None
    profile = _validate_locked_profile(_load_json(profile_path))
    _validate_profile_asset(kit, profile)
    guide_path = kit / "character-guide.md"
    if not guide_path.is_file():
        raise ProfileError(f"current guide is missing: {guide_path}")
    return profile


def _finalize(kit: Path, profile_path: Path, master_path: Path) -> dict[str, Any]:
    candidate = _validate_author_profile(
        _load_json(profile_path), allow_system_fields=True
    )
    if not any(
        decision["source"] == "user_confirmed"
        for decision in candidate["provenance"]["decisions"]
    ):
        _fail(
            ["provenance", "decisions"],
            "record the user's final approval before locking",
        )

    media_type, extension = _detect_image(master_path)
    source_size = master_path.stat().st_size
    source_hash = _sha256(master_path)

    if kit.exists() and not kit.is_dir():
        raise ProfileError(f"kit path is not a directory: {kit}")

    current: dict[str, Any] | None = None
    if kit.exists():
        current_profile_path = kit / "character-profile.json"
        if current_profile_path.exists():
            _check_kit(kit)
            current = _read_current_profile(kit)
        elif any(kit.iterdir()):
            raise ProfileError(
                "kit directory contains files but has no character-profile.json"
            )
    if current and current["character_id"] != candidate["character_id"]:
        raise ProfileError(
            "candidate character_id does not match the existing character kit"
        )

    revision = 1 if current is None else current["revision"] + 1
    revision_label = f"r{revision:03d}"
    relative_master = f"master/master-{revision_label}{extension}"
    target_master = kit / Path(relative_master)

    if target_master.exists():
        raise ProfileError(f"target master already exists: {target_master}")

    history_dir: Path | None = None
    if current is not None:
        old_label = f"r{current['revision']:03d}"
        history_dir = kit / "history" / old_label
        if history_dir.exists():
            raise ProfileError(f"history revision already exists: {history_dir}")
        if not (kit / "character-guide.md").is_file():
            raise ProfileError("current character-guide.md is missing")

    finalized = _author_profile_only(candidate)
    finalized["status"] = "locked"
    finalized["revision"] = revision
    finalized["assets"] = {
        "master_reference": relative_master,
        "sha256": source_hash,
        "bytes": source_size,
        "media_type": media_type,
    }
    finalized = _validate_locked_profile(finalized)
    guide = _render_guide(finalized).encode("utf-8")
    profile_bytes = _json_bytes(finalized)

    kit.mkdir(parents=True, exist_ok=True)
    if current is not None and history_dir is not None:
        history_dir.mkdir(parents=True, exist_ok=False)
        _write_new_file(
            history_dir / "character-profile.json",
            (kit / "character-profile.json").read_bytes(),
        )
        _write_new_file(
            history_dir / "character-guide.md",
            (kit / "character-guide.md").read_bytes(),
        )

    _copy_master_atomic(master_path, target_master)
    if _sha256(target_master) != source_hash:
        raise ProfileError("copied master image failed SHA-256 verification")

    _atomic_write(kit / "character-guide.md", guide)
    _atomic_write(kit / "character-profile.json", profile_bytes)
    return _check_kit(kit)


def _check_kit(kit: Path) -> dict[str, Any]:
    if not kit.is_dir():
        raise ProfileError(f"kit directory does not exist: {kit}")
    current = _read_current_profile(kit)
    if current is None:
        raise ProfileError("character-profile.json is missing")

    revision = current["revision"]
    guide_text = (kit / "character-guide.md").read_text(encoding="utf-8")
    revision_label = f"r{revision:03d}"
    if revision_label not in guide_text:
        raise ProfileError(
            f"character-guide.md does not describe current revision {revision_label}"
        )

    history: list[str] = []
    for historical_revision in range(1, revision):
        label = f"r{historical_revision:03d}"
        history_dir = kit / "history" / label
        profile_path = history_dir / "character-profile.json"
        guide_path = history_dir / "character-guide.md"
        if not profile_path.is_file() or not guide_path.is_file():
            raise ProfileError(f"history revision is incomplete: {history_dir}")
        historical = _validate_locked_profile(_load_json(profile_path))
        if historical["revision"] != historical_revision:
            raise ProfileError(
                f"history revision mismatch in {profile_path}: "
                f"expected {historical_revision}, got {historical['revision']}"
            )
        if historical["character_id"] != current["character_id"]:
            raise ProfileError(f"history character_id mismatch in {profile_path}")
        _validate_profile_asset(kit, historical)
        if label not in guide_path.read_text(encoding="utf-8"):
            raise ProfileError(f"history guide revision mismatch: {guide_path}")
        history.append(label)

    return {
        "status": "PASS",
        "kit": str(kit.resolve()),
        "character_id": current["character_id"],
        "display_name": current["display_name"],
        "revision": revision_label,
        "master_reference": str(
            _safe_asset_path(
                kit, current["assets"]["master_reference"]
            ).resolve()
        ),
        "history": history,
    }


def _load_prompt_source(
    source: Path,
) -> tuple[dict[str, Any], Path | None, Path]:
    if source.is_dir():
        _check_kit(source)
        profile = _read_current_profile(source)
        if profile is None:
            raise ProfileError("character-profile.json is missing")
        master = _safe_asset_path(
            source, profile["assets"]["master_reference"]
        ).resolve()
        return profile, master, (source / "character-profile.json").resolve()

    data = _load_json(source)
    if isinstance(data, dict) and data.get("status") == "locked":
        profile = _validate_locked_profile(data)
        master = _validate_profile_asset(source.parent, profile).resolve()
        return profile, master, source.resolve()
    profile = _validate_author_profile(data, allow_system_fields=False)
    return profile, None, source.resolve()


def build_prompt_bundle(
    source: Path,
    purpose: str,
    task: str = "",
    reference: Path | None = None,
) -> dict[str, Any]:
    profile, kit_master, profile_path = _load_prompt_source(source)
    task = task.strip()
    if purpose not in {"master", "consistency", "scene"}:
        raise ProfileError(
            "purpose must be master, consistency, or scene"
        )
    if purpose == "scene" and not task:
        raise ProfileError("--task is required when --purpose is scene")

    explicit_reference: Path | None = None
    if reference is not None:
        explicit_reference = Path(reference)
        _detect_image(explicit_reference)
        explicit_reference = explicit_reference.resolve()
        if kit_master is not None and _sha256(explicit_reference) != _sha256(
            kit_master
        ):
            raise ProfileError(
                "--reference does not match the locked kit master image"
            )

    master = kit_master or explicit_reference
    if purpose in {"consistency", "scene"} and master is None:
        raise ProfileError(
            f"--purpose {purpose} requires a locked kit or --reference"
        )

    prompt = _render_generation_prompt(profile, purpose, task)
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    canonical_profile = json.dumps(
        _author_profile_only(profile),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    profile_digest = hashlib.sha256(canonical_profile).hexdigest()
    return {
        "status": "PASS",
        "purpose": purpose,
        "character_id": profile["character_id"],
        "character_revision": (
            f"r{profile['revision']:03d}" if "revision" in profile else None
        ),
        "profile": str(profile_path),
        "profile_sha256": profile_digest,
        "master_reference": str(master) if master else None,
        "master_sha256": _sha256(master) if master else None,
        "prompt_sha256": prompt_sha256,
        "prompt_characters": len(prompt),
        "prompt": prompt,
    }


def _command_prompt(args: argparse.Namespace) -> int:
    result = build_prompt_bundle(
        Path(args.source),
        args.purpose,
        args.task,
        Path(args.reference) if args.reference else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _command_schema(_: argparse.Namespace) -> int:
    print(json.dumps(PROFILE_SCHEMA, ensure_ascii=False, indent=2))
    return 0


def _command_draft(args: argparse.Namespace) -> int:
    output = Path(args.output)
    if output.exists():
        raise ProfileError(f"refusing to overwrite existing file: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    template = _draft_template(
        args.character_id,
        args.display_name,
        args.language,
    )
    _write_new_file(output, _json_bytes(template))
    print(
        json.dumps(
            {"status": "CREATED", "profile": str(output.resolve())},
            ensure_ascii=False,
        )
    )
    return 0


def _command_finalize(args: argparse.Namespace) -> int:
    result = _finalize(
        Path(args.kit),
        Path(args.profile),
        Path(args.master),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _command_check(args: argparse.Namespace) -> int:
    result = _check_kit(Path(args.kit))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    schema_parser = subparsers.add_parser(
        "schema",
        help="Print the machine-readable character profile contract.",
    )
    schema_parser.set_defaults(handler=_command_schema)

    prompt_parser = subparsers.add_parser(
        "prompt",
        help=(
            "Build a complete image-generation prompt from a draft profile "
            "or locked kit."
        ),
    )
    prompt_parser.add_argument(
        "source",
        help="Draft profile JSON, locked character-profile.json, or kit directory.",
    )
    prompt_parser.add_argument(
        "--purpose",
        choices=("master", "consistency", "scene"),
        default="master",
        help="Select the temporary image task wrapped around the identity.",
    )
    prompt_parser.add_argument(
        "--task",
        default="",
        help="Temporary pose, action, scene, framing, or output instruction.",
    )
    prompt_parser.add_argument(
        "--reference",
        default="",
        help=(
            "Approved master image for an unlocked profile; a locked kit "
            "supplies and verifies its own master."
        ),
    )
    prompt_parser.set_defaults(handler=_command_prompt)

    draft_parser = subparsers.add_parser(
        "draft",
        help="Create a non-destructive character profile draft.",
    )
    draft_parser.add_argument("output", help="Path for the new draft JSON file.")
    draft_parser.add_argument(
        "--character-id",
        default="",
        help="Stable lowercase identifier; may be filled later.",
    )
    draft_parser.add_argument(
        "--display-name",
        default="",
        help="User-facing character name; may be filled later.",
    )
    draft_parser.add_argument(
        "--language",
        default="zh-CN",
        help="Profile and guide language, for example zh-CN or en.",
    )
    draft_parser.set_defaults(handler=_command_draft)

    finalize_parser = subparsers.add_parser(
        "finalize",
        help="Validate inputs and lock a new non-destructive kit revision.",
    )
    finalize_parser.add_argument("kit", help="Character kit directory.")
    finalize_parser.add_argument(
        "--profile",
        required=True,
        help="Completed draft profile JSON.",
    )
    finalize_parser.add_argument(
        "--master",
        required=True,
        help="Approved PNG, JPEG, or WebP master image.",
    )
    finalize_parser.set_defaults(handler=_command_finalize)

    check_parser = subparsers.add_parser(
        "check",
        help="Verify the current profile, guide, master, and all history.",
    )
    check_parser.add_argument("kit", help="Character kit directory.")
    check_parser.set_defaults(handler=_command_check)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except ProfileError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"ERROR: filesystem operation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
