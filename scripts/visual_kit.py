#!/usr/bin/env python3
"""Build prompts and plans for IP Studio static visuals."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import character_kit


SKILL_ROOT = Path(__file__).resolve().parents[1]
ARTICLE_COVER_TEMPLATE = SKILL_ROOT / "references" / "cover-prompt.md"
SCHEMA_VERSION = "1.0"
ARTICLE_PLAN_SCHEMA_VERSION = "1.0"
VISUAL_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
RATIO_RE = re.compile(r"^[1-9]\d*:[1-9]\d*$")

KINDS = {
    "avatar",
    "profile-banner",
    "profile-card",
    "cover",
    "explainer",
    "article-illustration",
}
TOP_KEYS = {
    "schema_version",
    "visual_id",
    "kind",
    "language",
    "prompt_text",
    "visual_language",
    "content",
    "message",
    "brand",
    "composition",
    "character_action",
    "references",
    "decisions",
}
CONTENT_KEYS = {"source_label", "source_text"}
MESSAGE_KEYS = {
    "core_object",
    "audience_gap",
    "mechanism_or_change",
    "takeaway",
}
BRAND_KEYS = {"role", "name", "visual_cues"}
COMPOSITION_KEYS = {
    "aspect_ratio",
    "structure",
    "title",
    "subtitle",
    "labels",
    "conclusion",
    "palette",
    "style_notes",
}
ACTION_KEYS = {"role", "action", "affected_object", "visible_result"}
REFERENCE_KEYS = {"role", "path"}
DECISION_KEYS = {"path", "source", "note"}

STRUCTURES = {
    "avatar": {"badge", "portrait"},
    "profile-banner": {"brand-narrative"},
    "profile-card": {"identity-card"},
    "cover": {"single-narrative"},
    "explainer": {
        "comparison",
        "process",
        "system",
        "matrix",
        "problem-result",
        "timeline",
        "funnel",
        "combination",
    },
    "article-illustration": {
        "conceptual-metaphor",
        "process",
        "structural-relation",
        "comparison",
        "local-scene",
    },
}
DEFAULTS = {
    "avatar": ("1:1", "badge"),
    "profile-banner": ("3:1", "brand-narrative"),
    "profile-card": ("4:5", "identity-card"),
    "cover": ("5:2", "single-narrative"),
    "explainer": ("4:5", "process"),
    "article-illustration": ("16:9", "conceptual-metaphor"),
}
STYLE_PROFILE_SCHEMA_VERSION = "1.0"
STYLE_PROFILE_TOP_KEYS = {
    "schema_version",
    "visual_language",
    "display_name",
    "available_for",
    "generation_text",
    "prompt",
}
STYLE_PROFILE_PROMPT_KEYS = {
    "palette",
    "typography",
    "composition",
    "scene_families",
    "character_integration",
    "logo_policy",
    "content_boundaries",
    "quality_checks",
}
STYLE_PROFILE_PALETTE_KEYS = {"hex", "role", "usage"}
STYLE_PROFILE_SCENE_KEYS = {"id", "use_when", "visual_method"}
STYLE_PROFILE_LOGO_ORDER = ("default", "exact", "placement")
STYLE_PROFILE_LOGO_KEYS = set(STYLE_PROFILE_LOGO_ORDER)
VISUAL_LANGUAGES: dict[str, dict[str, Any]] = {
    "minimal-handdrawn": {
        "display_name": "极简手绘 IP",
        "mode": "reference-pack",
        "available_for": {
            "cover",
            "explainer",
            "article-illustration",
        },
        "references": (
            {
                "role": "minimal-handdrawn-style",
                "path": "assets/visual-languages/minimal-handdrawn/examples/information-well.png",
            },
            {
                "role": "minimal-handdrawn-style",
                "path": "assets/visual-languages/minimal-handdrawn/examples/idea-press.png",
            },
            {
                "role": "minimal-handdrawn-style",
                "path": "assets/visual-languages/minimal-handdrawn/examples/content-fermentation.png",
            },
            {
                "role": "minimal-handdrawn-style",
                "path": "assets/visual-languages/minimal-handdrawn/examples/trust-bridge.png",
            },
        ),
        "source_notice": "assets/visual-languages/minimal-handdrawn/SOURCE.md",
    },
    "okx-editorial": {
        "display_name": "OKX Editorial",
        "mode": "prompt-profile",
        "available_for": {
            "profile-banner",
            "profile-card",
            "cover",
            "explainer",
            "article-illustration",
        },
        "profile": "assets/visual-languages/okx-editorial/style-profile.json",
        "default_references": (
            {
                "role": "默认使用的 OKX 白色标记；保持原比例和结构，不重画",
                "path": (
                    "assets/visual-languages/okx-editorial/logos/"
                    "okx-mark-white.png"
                ),
            },
        ),
        "source_notice": "assets/visual-languages/okx-editorial/SOURCE.md",
        "style_guide": "assets/visual-languages/okx-editorial/STYLE.md",
    },
    "binance-editorial": {
        "display_name": "Binance Editorial",
        "mode": "prompt-profile",
        "available_for": {
            "profile-banner",
            "profile-card",
            "cover",
            "explainer",
            "article-illustration",
        },
        "profile": "assets/visual-languages/binance-editorial/style-profile.json",
        "default_references": (
            {
                "role": (
                    "适用于深色背景的 Binance 黄色标记；根据最终底色与"
                    "下一张标记二选一使用，保持原比例和结构，不重画"
                ),
                "path": (
                    "assets/visual-languages/binance-editorial/logos/"
                    "binance-mark-yellow.png"
                ),
            },
            {
                "role": (
                    "适用于黄色或浅色背景的 Binance 黑色标记；根据最终底色与"
                    "上一张标记二选一使用，保持原比例和结构，不重画"
                ),
                "path": (
                    "assets/visual-languages/binance-editorial/logos/"
                    "binance-mark-black.png"
                ),
            },
        ),
        "source_notice": "assets/visual-languages/binance-editorial/SOURCE.md",
        "style_guide": "assets/visual-languages/binance-editorial/STYLE.md",
    },
}
BUILT_IN_REFERENCE_ROLES = frozenset(
    reference["role"]
    for language in VISUAL_LANGUAGES.values()
    for reference in language.get("references", ())
)
ARTICLE_PLAN_TOP_KEYS = {
    "schema_version",
    "set_id",
    "language",
    "article",
    "brand",
    "visual_language",
    "palette",
    "style_notes",
    "shots",
}
ARTICLE_PLAN_ARTICLE_KEYS = {"source_label", "source_text"}
ARTICLE_PLAN_SHOT_KEYS = {
    "visual_id",
    "placement_after",
    "source_excerpt",
    "message",
    "structure",
    "character_action",
    "title",
    "subtitle",
    "labels",
    "conclusion",
    "decisions",
}


class VisualError(ValueError):
    """Raised when a visual brief, style profile, or article plan is invalid."""


def _fail(path: str, message: str) -> None:
    raise VisualError(f"{path}: {message}")


def _require_object(
    value: Any,
    path: str,
    expected: set[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown:
        _fail(path, "contains unsupported fields: " + ", ".join(unknown))
    if missing:
        _fail(path, "is missing fields: " + ", ".join(missing))
    return value


def _text(
    value: Any,
    path: str,
    *,
    optional: bool = False,
    maximum: int = 10000,
) -> str:
    if not isinstance(value, str):
        _fail(path, "must be a string")
    cleaned = value.strip()
    if not cleaned and not optional:
        _fail(path, "must not be empty")
    if len(cleaned) > maximum:
        _fail(path, f"must not exceed {maximum} characters")
    return cleaned


def _verbatim_text(
    value: Any,
    path: str,
    *,
    optional: bool = False,
    maximum: int = 100000,
) -> str:
    if not isinstance(value, str):
        _fail(path, "must be a string")
    if not value.strip() and not optional:
        _fail(path, "must not be empty")
    if len(value) > maximum:
        _fail(path, f"must not exceed {maximum} characters")
    return value


def _text_list(
    value: Any,
    path: str,
    minimum: int,
    maximum: int,
) -> list[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        _fail(path, f"must contain {minimum}-{maximum} items")
    return [
        _text(item, f"{path}[{index}]", maximum=500)
        for index, item in enumerate(value)
    ]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise VisualError(f"file does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise VisualError(
            f"invalid JSON in {path}: line {error.lineno}, column {error.colno}"
        ) from error


def _detect_image(path: Path) -> tuple[str, str]:
    if not path.is_file():
        raise VisualError(f"image does not exist: {path}")
    with path.open("rb") as handle:
        header = handle.read(16)
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise VisualError(f"unsupported raster image: {path}")


def _resolve_reference(path_text: str, base_dir: Path) -> Path:
    candidate = Path(path_text)
    resolved = candidate if candidate.is_absolute() else base_dir / candidate
    resolved = resolved.resolve()
    _detect_image(resolved)
    return resolved


def _style_reference_manifest(style: str) -> dict[str, Any]:
    language = VISUAL_LANGUAGES.get(style)
    if language is None or language["mode"] != "reference-pack":
        raise VisualError(f"unsupported visual language: {style}")
    references: list[dict[str, str]] = []
    for reference in language["references"]:
        path = (SKILL_ROOT / reference["path"]).resolve()
        _detect_image(path)
        references.append({"role": reference["role"], "path": str(path)})
    source_notice = (SKILL_ROOT / language["source_notice"]).resolve()
    if not source_notice.is_file():
        raise VisualError(
            f"missing visual language source notice: {source_notice}"
        )
    result = {
        "status": "PASS",
        "visual_language": style,
        "brief_references": references,
        "source_notice": str(source_notice),
    }
    if language.get("style_guide"):
        style_guide = (SKILL_ROOT / language["style_guide"]).resolve()
        if not style_guide.is_file():
            raise VisualError(
                f"missing visual language style guide: {style_guide}"
            )
        result["style_guide"] = str(style_guide)
    return result


def _validate_style_profile_data(data: Any, style: str) -> dict[str, Any]:
    language = VISUAL_LANGUAGES.get(style)
    if language is None or language["mode"] != "prompt-profile":
        raise VisualError(f"unsupported prompt-profile visual language: {style}")
    profile = copy.deepcopy(
        _require_object(data, "$style_profile", STYLE_PROFILE_TOP_KEYS)
    )
    if profile["schema_version"] != STYLE_PROFILE_SCHEMA_VERSION:
        _fail(
            "$style_profile.schema_version",
            f"must equal {STYLE_PROFILE_SCHEMA_VERSION}",
        )
    profile["visual_language"] = _text(
        profile["visual_language"],
        "$style_profile.visual_language",
        maximum=64,
    )
    if profile["visual_language"] != style:
        _fail(
            "$style_profile.visual_language",
            f"must equal {style}",
        )
    profile["display_name"] = _text(
        profile["display_name"],
        "$style_profile.display_name",
        maximum=100,
    )
    profile["generation_text"] = _verbatim_text(
        profile["generation_text"],
        "$style_profile.generation_text",
        maximum=2000,
    )
    available_for = _text_list(
        profile["available_for"],
        "$style_profile.available_for",
        1,
        len(KINDS),
    )
    if set(available_for) != set(language["available_for"]):
        _fail(
            "$style_profile.available_for",
            "must match the registered visual kinds",
        )
    profile["available_for"] = available_for

    prompt = _require_object(
        profile["prompt"],
        "$style_profile.prompt",
        STYLE_PROFILE_PROMPT_KEYS,
    )
    palette = prompt["palette"]
    if not isinstance(palette, list) or not 2 <= len(palette) <= 8:
        _fail("$style_profile.prompt.palette", "must contain 2-8 colors")
    cleaned_palette: list[dict[str, str]] = []
    for index, item in enumerate(palette):
        color = _require_object(
            item,
            f"$style_profile.prompt.palette[{index}]",
            STYLE_PROFILE_PALETTE_KEYS,
        )
        hex_value = _text(
            color["hex"],
            f"$style_profile.prompt.palette[{index}].hex",
            maximum=7,
        ).upper()
        if not HEX_COLOR_RE.fullmatch(hex_value):
            _fail(
                f"$style_profile.prompt.palette[{index}].hex",
                "must use #RRGGBB",
            )
        cleaned_palette.append(
            {
                "hex": hex_value,
                "role": _text(
                    color["role"],
                    f"$style_profile.prompt.palette[{index}].role",
                    maximum=100,
                ),
                "usage": _text(
                    color["usage"],
                    f"$style_profile.prompt.palette[{index}].usage",
                    maximum=500,
                ),
            }
        )
    prompt["palette"] = cleaned_palette
    for key in (
        "typography",
        "composition",
        "character_integration",
        "content_boundaries",
        "quality_checks",
    ):
        prompt[key] = _text_list(
            prompt[key],
            f"$style_profile.prompt.{key}",
            1,
            12,
        )
    scenes = prompt["scene_families"]
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 8:
        _fail("$style_profile.prompt.scene_families", "must contain 1-8 scenes")
    cleaned_scenes: list[dict[str, str]] = []
    seen_scene_ids: set[str] = set()
    for index, item in enumerate(scenes):
        scene = _require_object(
            item,
            f"$style_profile.prompt.scene_families[{index}]",
            STYLE_PROFILE_SCENE_KEYS,
        )
        scene_id = _text(
            scene["id"],
            f"$style_profile.prompt.scene_families[{index}].id",
            maximum=64,
        )
        if not VISUAL_ID_RE.fullmatch(scene_id) or scene_id in seen_scene_ids:
            _fail(
                f"$style_profile.prompt.scene_families[{index}].id",
                "must be unique lowercase kebab-case",
            )
        seen_scene_ids.add(scene_id)
        cleaned_scenes.append(
            {
                "id": scene_id,
                "use_when": _text(
                    scene["use_when"],
                    f"$style_profile.prompt.scene_families[{index}].use_when",
                    maximum=500,
                ),
                "visual_method": _text(
                    scene["visual_method"],
                    f"$style_profile.prompt.scene_families[{index}].visual_method",
                    maximum=1000,
                ),
            }
        )
    prompt["scene_families"] = cleaned_scenes
    logo = _require_object(
        prompt["logo_policy"],
        "$style_profile.prompt.logo_policy",
        STYLE_PROFILE_LOGO_KEYS,
    )
    prompt["logo_policy"] = {
        key: _text(
            logo[key],
            f"$style_profile.prompt.logo_policy.{key}",
            maximum=1000,
        )
        for key in STYLE_PROFILE_LOGO_ORDER
    }
    profile["prompt"] = prompt
    return profile


def _load_style_profile(style: str) -> tuple[dict[str, Any], Path]:
    language = VISUAL_LANGUAGES.get(style)
    if language is None or language["mode"] != "prompt-profile":
        raise VisualError(f"unsupported prompt-profile visual language: {style}")
    path = (SKILL_ROOT / language["profile"]).resolve()
    return _validate_style_profile_data(_load_json(path), style), path


def _style_profile_manifest(style: str) -> dict[str, Any]:
    profile, path = _load_style_profile(style)
    language = VISUAL_LANGUAGES[style]
    source_notice = (SKILL_ROOT / language["source_notice"]).resolve()
    style_guide = (SKILL_ROOT / language["style_guide"]).resolve()
    for label, source in (
        ("source notice", source_notice),
        ("style guide", style_guide),
    ):
        if not source.is_file():
            raise VisualError(f"missing visual language {label}: {source}")
    return {
        "status": "PASS",
        "visual_language": style,
        "profile": profile,
        "profile_path": str(path),
        "profile_sha256": _sha256_file(path),
        "source_notice": str(source_notice),
        "style_guide": str(style_guide),
    }


def _selected_visual_language(brief: dict[str, Any]) -> str:
    return brief["visual_language"]


def _with_default_visual_language_references(
    brief: dict[str, Any],
) -> dict[str, Any]:
    """Prepend exact default brand marks without loading style examples."""
    selected = _selected_visual_language(brief)
    if selected == "default":
        return brief
    defaults = VISUAL_LANGUAGES[selected].get("default_references", ())
    if not defaults:
        return brief

    prepared = copy.deepcopy(brief)
    supplied_by_path = {
        Path(reference["path"]).resolve(): reference
        for reference in prepared["references"]
    }
    combined: list[dict[str, str]] = []
    seen_paths: set[Path] = set()
    for reference in defaults:
        path = (SKILL_ROOT / reference["path"]).resolve()
        _detect_image(path)
        combined.append({"role": reference["role"], "path": str(path)})
        seen_paths.add(path)
    for path, reference in supplied_by_path.items():
        if path not in seen_paths:
            combined.append(reference)
            seen_paths.add(path)
    if len(combined) > 12:
        _fail(
            "$.references",
            "must contain at most 12 images after default brand marks are added",
        )
    prepared["references"] = combined
    return prepared


def _validate_visual_language_references(
    brief: dict[str, Any],
    kind: str,
) -> None:
    selected = _selected_visual_language(brief)
    if selected == "default":
        return
    language = VISUAL_LANGUAGES[selected]
    if kind not in language["available_for"]:
        allowed = ", ".join(sorted(language["available_for"]))
        _fail(
            "$.visual_language",
            f"{selected} is only available for: {allowed}",
        )
    if language["mode"] == "prompt-profile":
        _load_style_profile(selected)
        return
    expected = {
        (
            reference["role"],
            str((SKILL_ROOT / reference["path"]).resolve()),
        )
        for reference in language["references"]
    }
    actual = {
        (reference["role"], reference["path"])
        for reference in brief["references"]
        if reference["role"] in BUILT_IN_REFERENCE_ROLES
    }
    if actual != expected:
        _fail(
            "$.references",
            f"{selected} requires its complete built-in reference pack from "
            f"style-references {selected}",
        )


def _validate_brief(data: Any, base_dir: Path) -> dict[str, Any]:
    if isinstance(data, dict) and "visual_language" not in data:
        data = {**data, "visual_language": "default"}
    if isinstance(data, dict) and "prompt_text" not in data:
        data = {**data, "prompt_text": ""}
    brief = copy.deepcopy(_require_object(data, "$", TOP_KEYS))
    if brief["schema_version"] != SCHEMA_VERSION:
        _fail("$.schema_version", f"must equal {SCHEMA_VERSION}")

    visual_id = _text(brief["visual_id"], "$.visual_id", maximum=64)
    if not VISUAL_ID_RE.fullmatch(visual_id):
        _fail(
            "$.visual_id",
            "must use lowercase letters, numbers, and single hyphens",
        )
    brief["visual_id"] = visual_id

    kind = _text(brief["kind"], "$.kind", maximum=32)
    if kind not in KINDS:
        _fail("$.kind", "must be one of: " + ", ".join(sorted(KINDS)))
    brief["kind"] = kind
    brief["language"] = _text(
        brief["language"], "$.language", maximum=32
    )
    brief["prompt_text"] = _verbatim_text(
        brief["prompt_text"], "$.prompt_text", optional=True, maximum=100000
    )
    visual_language = _text(
        brief["visual_language"],
        "$.visual_language",
        maximum=64,
    )
    if visual_language != "default" and visual_language not in VISUAL_LANGUAGES:
        allowed = ", ".join(["default", *sorted(VISUAL_LANGUAGES)])
        _fail("$.visual_language", f"must be one of: {allowed}")
    brief["visual_language"] = visual_language

    content = _require_object(brief["content"], "$.content", CONTENT_KEYS)
    prompt_is_complete = bool(brief["prompt_text"].strip())
    content["source_label"] = _text(
        content["source_label"],
        "$.content.source_label",
        optional=prompt_is_complete,
        maximum=500,
    )
    content["source_text"] = _verbatim_text(
        content["source_text"],
        "$.content.source_text",
        optional=prompt_is_complete,
        maximum=100000,
    )

    message = _require_object(brief["message"], "$.message", MESSAGE_KEYS)
    for key in MESSAGE_KEYS:
        message[key] = _text(
            message[key], f"$.message.{key}", optional=True, maximum=3000
        )

    brand = _require_object(brief["brand"], "$.brand", BRAND_KEYS)
    if brand["role"] not in {"core", "auxiliary", "none"}:
        _fail("$.brand.role", "must be core, auxiliary, or none")
    brand["name"] = _text(
        brand["name"], "$.brand.name", optional=True, maximum=500
    )
    brand["visual_cues"] = _text(
        brand["visual_cues"],
        "$.brand.visual_cues",
        optional=True,
        maximum=3000,
    )
    if brand["role"] == "core" and not brand["name"]:
        _fail("$.brand.name", "is required when brand.role is core")

    composition = _require_object(
        brief["composition"], "$.composition", COMPOSITION_KEYS
    )
    ratio = _text(
        composition["aspect_ratio"],
        "$.composition.aspect_ratio",
        maximum=16,
    )
    if not RATIO_RE.fullmatch(ratio):
        _fail(
            "$.composition.aspect_ratio",
            "must use positive integer width:height, such as 16:9",
        )
    composition["aspect_ratio"] = ratio

    structure = _text(
        composition["structure"], "$.composition.structure", maximum=64
    )
    if structure not in STRUCTURES[kind]:
        _fail(
            "$.composition.structure",
            f"must be one of: {', '.join(sorted(STRUCTURES[kind]))}",
        )
    composition["structure"] = structure
    composition["title"] = _text(
        composition["title"],
        "$.composition.title",
        optional=True,
        maximum=80,
    )
    composition["subtitle"] = _text(
        composition["subtitle"],
        "$.composition.subtitle",
        optional=True,
        maximum=120,
    )
    composition["conclusion"] = _text(
        composition["conclusion"],
        "$.composition.conclusion",
        optional=True,
        maximum=200,
    )
    labels = _text_list(
        composition["labels"], "$.composition.labels", 0, 5
    )
    composition["labels"] = labels

    palette = _text_list(
        composition["palette"], "$.composition.palette", 0, 5
    )
    for index, color in enumerate(palette):
        if not HEX_COLOR_RE.fullmatch(color):
            _fail(
                f"$.composition.palette[{index}]",
                "must use #RRGGBB",
            )
    if kind == "cover" and len(palette) > 4:
        _fail("$.composition.palette", "must contain 2-4 colors for a cover")
    composition["palette"] = [item.upper() for item in palette]
    composition["style_notes"] = _text(
        composition["style_notes"],
        "$.composition.style_notes",
        optional=True,
        maximum=3000,
    )

    action = _require_object(
        brief["character_action"], "$.character_action", ACTION_KEYS
    )
    for key in ACTION_KEYS:
        action[key] = _text(
            action[key], f"$.character_action.{key}", optional=True, maximum=3000
        )

    references = brief["references"]
    if not isinstance(references, list) or len(references) > 12:
        _fail("$.references", "must contain 0-12 image references")
    cleaned_references: list[dict[str, str]] = []
    seen_paths: set[Path] = set()
    for index, item in enumerate(references):
        reference = _require_object(
            item, f"$.references[{index}]", REFERENCE_KEYS
        )
        role = _text(
            reference["role"], f"$.references[{index}].role", maximum=100
        )
        path_text = _text(
            reference["path"], f"$.references[{index}].path", maximum=1000
        )
        resolved = _resolve_reference(path_text, base_dir)
        if resolved in seen_paths:
            _fail(f"$.references[{index}].path", "duplicates another reference")
        seen_paths.add(resolved)
        cleaned_references.append({"role": role, "path": str(resolved)})
    brief["references"] = cleaned_references
    _validate_visual_language_references(brief, kind)

    decisions = brief["decisions"]
    if not isinstance(decisions, list) or not 0 <= len(decisions) <= 50:
        _fail("$.decisions", "must contain 0-50 decisions")
    cleaned_decisions: list[dict[str, str]] = []
    for index, item in enumerate(decisions):
        decision = _require_object(
            item, f"$.decisions[{index}]", DECISION_KEYS
        )
        source = decision["source"]
        if source not in {"user_confirmed", "agent_inferred"}:
            _fail(
                f"$.decisions[{index}].source",
                "must be user_confirmed or agent_inferred",
            )
        cleaned_decisions.append(
            {
                "path": _text(
                    decision["path"],
                    f"$.decisions[{index}].path",
                    maximum=300,
                ),
                "source": source,
                "note": _text(
                    decision["note"],
                    f"$.decisions[{index}].note",
                    maximum=2000,
                ),
            }
        )
    brief["decisions"] = cleaned_decisions
    return brief


def _brief_template(kind: str, visual_id: str, language: str) -> dict[str, Any]:
    ratio, structure = DEFAULTS[kind]
    return {
        "schema_version": SCHEMA_VERSION,
        "visual_id": visual_id,
        "kind": kind,
        "language": language,
        "prompt_text": "",
        "visual_language": "default",
        "content": {"source_label": "", "source_text": ""},
        "message": {
            "core_object": "",
            "audience_gap": "",
            "mechanism_or_change": "",
            "takeaway": "",
        },
        "brand": {"role": "none", "name": "", "visual_cues": ""},
        "composition": {
            "aspect_ratio": ratio,
            "structure": structure,
            "title": "",
            "subtitle": "",
            "labels": [],
            "conclusion": "",
            "palette": [],
            "style_notes": "",
        },
        "character_action": {
            "role": "",
            "action": "",
            "affected_object": "",
            "visible_result": "",
        },
        "references": [],
        "decisions": [],
    }


def _uses_visual_language(brief: dict[str, Any], language: str) -> bool:
    return _selected_visual_language(brief) == language


def _render_article_cover_task(brief: dict[str, Any]) -> str:
    if not ARTICLE_COVER_TEMPLATE.is_file():
        raise VisualError(
            f"article cover prompt template does not exist: {ARTICLE_COVER_TEMPLATE}"
        )
    template = ARTICLE_COVER_TEMPLATE.read_text(encoding="utf-8").rstrip("\r\n")
    replacements = {
        "{{aspect_ratio}}": brief["composition"]["aspect_ratio"],
        "{{upload_materials}}": "\n".join(
            [
                "- 第 1 张图片是个人 IP 角色参考图。",
                *[
                    f"- 第 {index} 张图片用于：{reference['role']}。"
                    for index, reference in enumerate(
                        brief["references"], start=2
                    )
                ],
            ]
        ),
        "{{content_material}}": brief["content"]["source_text"],
    }
    for placeholder, value in replacements.items():
        if template.count(placeholder) != 1:
            raise VisualError(
                f"article cover prompt template must contain {placeholder} exactly once"
            )
        template = template.replace(placeholder, value)
    return template


def _render_task(brief: dict[str, Any]) -> str:
    """Return the exact concise prompt that will be shown before generation."""
    brief = _with_default_visual_language_references(brief)
    prompt_text = brief.get("prompt_text", "")
    if prompt_text.strip():
        return prompt_text

    if brief["kind"] == "cover" and _selected_visual_language(brief) == "default":
        return _render_article_cover_task(brief)

    kind_labels = {
        "avatar": "社交头像",
        "profile-banner": "主页横幅",
        "profile-card": "IP 资料卡",
        "cover": "文章封面",
        "explainer": "说明图",
        "article-illustration": "正文插图",
    }
    lines = [
        f"请使用第 1 张图片中的已批准角色形象，生成一张 "
        f"{brief['composition']['aspect_ratio']} {kind_labels[brief['kind']]}。"
    ]
    for index, reference in enumerate(brief["references"], start=2):
        lines.append(f"第 {index} 张图片用于：{reference['role']}。")

    visual_language = _selected_visual_language(brief)
    if visual_language != "default":
        language = VISUAL_LANGUAGES[visual_language]
        if language["mode"] == "prompt-profile":
            profile, _ = _load_style_profile(visual_language)
            lines.append(f"视觉风格：{profile['generation_text']}")
        else:
            lines.append(f"用户选择的视觉风格：{language['display_name']}。")

    lines.extend(
        [
            (
                "以下原文是完整内容材料，不是必须逐字放进画面的排版稿。"
                "生成前先自行判断：这张图最值得让人看懂什么、哪些信息必须保留、"
                "哪些可以省略，以及什么版式最适合表达。不要机械地把原文全部塞进"
                "图片。完成判断后直接生成图片，不输出分析过程。"
            ),
            f"完整内容材料：{brief['content']['source_label']}",
            brief["content"]["source_text"],
        ]
    )
    return "\n".join(lines)


def build_visual_bundle(
    kit: Path,
    brief_data: Any,
    base_dir: Path,
) -> dict[str, Any]:
    brief = _with_default_visual_language_references(
        _validate_brief(brief_data, base_dir)
    )
    task = _render_task(brief)
    visual_language = _selected_visual_language(brief)
    character = character_kit.build_prompt_bundle(
        kit.resolve(),
        "scene",
        task,
    )
    master = Path(str(character["master_reference"])).resolve()
    image_references = [
        {
            "index": 1,
            "role": "approved-character-master",
            "path": str(master),
        }
    ]
    for brief_index, reference in enumerate(brief["references"]):
        path = Path(reference["path"]).resolve()
        image_references.append(
            {
                "index": brief_index + 2,
                "role": reference["role"],
                "path": str(path),
            }
        )
    return {
        "status": "PASS",
        "visual_id": brief["visual_id"],
        "kind": brief["kind"],
        "visual_language": visual_language,
        "character_id": character["character_id"],
        "character_revision": character["character_revision"],
        "requires_user_confirmation": True,
        "image_references": image_references,
        "prompt": task,
        "brief": brief,
    }


def build_one_off_visual_bundle(
    character_reference: Path,
    brief_data: Any,
    base_dir: Path,
) -> dict[str, Any]:
    brief = _with_default_visual_language_references(
        _validate_brief(brief_data, base_dir)
    )
    reference = character_reference.resolve()
    if not reference.is_file():
        raise VisualError(f"character reference does not exist: {reference}")
    task = _render_task(brief)
    image_references = [
        {
            "index": 1,
            "role": "provided-character-reference",
            "path": str(reference),
        }
    ]
    for brief_index, item in enumerate(brief["references"]):
        path = Path(item["path"]).resolve()
        image_references.append(
            {
                "index": brief_index + 2,
                "role": item["role"],
                "path": str(path),
            }
        )
    return {
        "status": "PASS",
        "mode": "one-off",
        "visual_id": brief["visual_id"],
        "kind": brief["kind"],
        "visual_language": _selected_visual_language(brief),
        "requires_user_confirmation": True,
        "image_references": image_references,
        "prompt": task,
        "brief": brief,
    }


def _article_plan_template(set_id: str, language: str) -> dict[str, Any]:
    return {
        "schema_version": ARTICLE_PLAN_SCHEMA_VERSION,
        "set_id": set_id,
        "language": language,
        "article": {"source_label": "", "source_text": ""},
        "brand": {"role": "none", "name": "", "visual_cues": ""},
        "visual_language": "default",
        "palette": ["#F4E8D0", "#1F2937", "#E26D5A"],
        "style_notes": "",
        "shots": [
            {
                "visual_id": "",
                "placement_after": "",
                "source_excerpt": "",
                "message": {
                    "core_object": "",
                    "audience_gap": "",
                    "mechanism_or_change": "",
                    "takeaway": "",
                },
                "structure": "conceptual-metaphor",
                "character_action": {
                    "role": "",
                    "action": "",
                    "affected_object": "",
                    "visible_result": "",
                },
                "title": "",
                "subtitle": "",
                "labels": [],
                "conclusion": "",
                "decisions": [],
            }
        ],
    }


def _shot_brief(plan: dict[str, Any], shot: dict[str, Any]) -> dict[str, Any]:
    references: list[dict[str, str]] = []
    if (
        plan["visual_language"] != "default"
        and VISUAL_LANGUAGES[plan["visual_language"]]["mode"]
        == "reference-pack"
    ):
        references = _style_reference_manifest(plan["visual_language"])[
            "brief_references"
        ]
    return {
        "schema_version": SCHEMA_VERSION,
        "visual_id": shot["visual_id"],
        "kind": "article-illustration",
        "language": plan["language"],
        "visual_language": plan["visual_language"],
        "content": copy.deepcopy(plan["article"]),
        "message": copy.deepcopy(shot["message"]),
        "brand": copy.deepcopy(plan["brand"]),
        "composition": {
            "aspect_ratio": "16:9",
            "structure": shot["structure"],
            "title": shot["title"],
            "subtitle": shot["subtitle"],
            "labels": copy.deepcopy(shot["labels"]),
            "conclusion": shot["conclusion"],
            "palette": copy.deepcopy(plan["palette"]),
            "style_notes": plan["style_notes"],
        },
        "character_action": copy.deepcopy(shot["character_action"]),
        "references": copy.deepcopy(references),
        "decisions": copy.deepcopy(shot["decisions"]),
    }


def _validate_article_plan(data: Any) -> dict[str, Any]:
    plan = copy.deepcopy(_require_object(data, "$plan", ARTICLE_PLAN_TOP_KEYS))
    if plan["schema_version"] != ARTICLE_PLAN_SCHEMA_VERSION:
        raise VisualError("unsupported article illustration plan schema")
    plan["set_id"] = _text(plan["set_id"], "$.set_id", maximum=64)
    if not VISUAL_ID_RE.fullmatch(plan["set_id"]):
        raise VisualError("set_id must use lowercase letters, numbers, and hyphens")
    plan["language"] = _text(plan["language"], "$.language", maximum=32)
    article = _require_object(plan["article"], "$.article", ARTICLE_PLAN_ARTICLE_KEYS)
    article["source_label"] = _text(article["source_label"], "$.article.source_label", maximum=500)
    article["source_text"] = _text(article["source_text"], "$.article.source_text", maximum=200000)
    brand = _require_object(plan["brand"], "$.brand", BRAND_KEYS)
    if brand["role"] not in {"core", "auxiliary", "none"}:
        raise VisualError("article plan brand role must be core, auxiliary, or none")
    brand["name"] = _text(brand["name"], "$.brand.name", optional=True, maximum=500)
    brand["visual_cues"] = _text(brand["visual_cues"], "$.brand.visual_cues", optional=True, maximum=3000)
    if brand["role"] == "core" and not brand["name"]:
        raise VisualError("brand name is required when brand role is core")
    allowed_languages = {"default", *VISUAL_LANGUAGES}
    if plan["visual_language"] not in allowed_languages:
        allowed = ", ".join(sorted(allowed_languages))
        raise VisualError(f"visual_language must be one of: {allowed}")
    palette = _text_list(plan["palette"], "$.palette", 2, 5)
    if any(not HEX_COLOR_RE.fullmatch(color) for color in palette):
        raise VisualError("article plan palette must use #RRGGBB colors")
    plan["palette"] = [color.upper() for color in palette]
    plan["style_notes"] = _text(plan["style_notes"], "$.style_notes", maximum=3000)
    shots = plan["shots"]
    if not isinstance(shots, list) or not 1 <= len(shots) <= 30:
        raise VisualError("article plan must contain 1-30 cognitive-anchor shots")

    seen_ids: set[str] = set()
    previous_position = -1
    normalized_shots: list[dict[str, Any]] = []
    for index, raw_shot in enumerate(shots):
        shot = _require_object(raw_shot, f"$.shots[{index}]", ARTICLE_PLAN_SHOT_KEYS)
        visual_id = _text(shot["visual_id"], f"$.shots[{index}].visual_id", maximum=64)
        if not VISUAL_ID_RE.fullmatch(visual_id) or visual_id in seen_ids:
            raise VisualError("article shot visual_id must be unique lowercase kebab-case")
        seen_ids.add(visual_id)
        shot["visual_id"] = visual_id
        shot["placement_after"] = _text(shot["placement_after"], f"$.shots[{index}].placement_after", maximum=1000)
        excerpt = _text(shot["source_excerpt"], f"$.shots[{index}].source_excerpt", maximum=5000)
        position = article["source_text"].find(excerpt, previous_position + 1)
        if position < 0:
            raise VisualError(
                f"shot {visual_id} source_excerpt must occur in article order after the previous shot"
            )
        previous_position = position
        shot["source_excerpt"] = excerpt
        brief = _validate_brief(_shot_brief(plan, shot), SKILL_ROOT)
        normalized = copy.deepcopy(shot)
        normalized["message"] = brief["message"]
        normalized["character_action"] = brief["character_action"]
        normalized["structure"] = brief["composition"]["structure"]
        normalized["title"] = brief["composition"]["title"]
        normalized["subtitle"] = brief["composition"]["subtitle"]
        normalized["labels"] = brief["composition"]["labels"]
        normalized["conclusion"] = brief["composition"]["conclusion"]
        normalized["decisions"] = brief["decisions"]
        normalized_shots.append(normalized)
    plan["shots"] = normalized_shots
    return plan


def _materialize_article_plan(plan_path: Path, output: Path) -> dict[str, Any]:
    plan = _validate_article_plan(_load_json(plan_path))
    if output.exists():
        raise VisualError(f"refusing to overwrite article brief directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = output.parent / f".{output.name}.{uuid.uuid4().hex}.staging"
    stage.mkdir(parents=False, exist_ok=False)
    (stage / "article-plan.json").write_bytes(_json_bytes(plan))
    created: list[str] = []
    for index, shot in enumerate(plan["shots"], start=1):
        brief = _validate_brief(_shot_brief(plan, shot), SKILL_ROOT)
        path = stage / f"{index:02d}-{shot['visual_id']}.json"
        path.write_bytes(_json_bytes(brief))
        created.append(path.name)
    os.replace(stage, output)
    return {
        "status": "CREATED",
        "set_id": plan["set_id"],
        "shot_count": len(created),
        "briefs": [str((output / name).resolve()) for name in created],
    }


def _schema() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kinds": sorted(KINDS),
        "required_top_level_fields": sorted(TOP_KEYS),
        "aspect_ratio": {
            "format": "positive-integer-width:positive-integer-height",
            "restricted": False,
            "defaults": {
                key: value[0] for key, value in DEFAULTS.items()
            },
        },
        "allowed_structures": {
            key: sorted(value) for key, value in STRUCTURES.items()
        },
        "contracts": {
            "content": sorted(CONTENT_KEYS),
            "message": sorted(MESSAGE_KEYS),
            "brand": sorted(BRAND_KEYS),
            "composition": sorted(COMPOSITION_KEYS),
            "character_action": sorted(ACTION_KEYS),
            "reference": sorted(REFERENCE_KEYS),
            "decision": sorted(DECISION_KEYS),
        },
        "visual_languages": {
            name: {
                "display_name": language["display_name"],
                "mode": language["mode"],
                "available_for": sorted(language["available_for"]),
                "reference_roles": sorted(
                    {
                        reference["role"]
                        for reference in language.get("references", ())
                    }
                ),
                "reference_count": len(language.get("references", ())),
                "profile": language.get("profile"),
            }
            for name, language in VISUAL_LANGUAGES.items()
        },
    }


def _command_schema(_: argparse.Namespace) -> int:
    print(json.dumps(_schema(), ensure_ascii=False, indent=2))
    return 0


def _command_style_references(args: argparse.Namespace) -> int:
    print(
        json.dumps(
            _style_reference_manifest(args.visual_language),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _command_style_profile(args: argparse.Namespace) -> int:
    print(
        json.dumps(
            _style_profile_manifest(args.visual_language),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _command_draft(args: argparse.Namespace) -> int:
    output = Path(args.output)
    if output.exists():
        raise VisualError(f"refusing to overwrite existing file: {output}")
    if args.kind not in KINDS:
        raise VisualError("unsupported kind")
    if not VISUAL_ID_RE.fullmatch(args.visual_id):
        raise VisualError("visual-id must use lowercase letters, numbers, and hyphens")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write(
            _json_bytes(
                _brief_template(args.kind, args.visual_id, args.language)
            )
        )
    print(
        json.dumps(
            {"status": "CREATED", "brief": str(output.resolve())},
            ensure_ascii=False,
        )
    )
    return 0


def _command_prompt(args: argparse.Namespace) -> int:
    brief_path = Path(args.brief)
    bundle = build_visual_bundle(
        Path(args.kit),
        _load_json(brief_path),
        brief_path.parent,
    )
    printable = {key: value for key, value in bundle.items() if key != "brief"}
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0


def _command_prompt_once(args: argparse.Namespace) -> int:
    brief_path = Path(args.brief)
    bundle = build_one_off_visual_bundle(
        Path(args.character_reference),
        _load_json(brief_path),
        brief_path.parent,
    )
    printable = {key: value for key, value in bundle.items() if key != "brief"}
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0


def _command_plan_schema(_: argparse.Namespace) -> int:
    result = {
        "schema_version": ARTICLE_PLAN_SCHEMA_VERSION,
        "required_top_level_fields": sorted(ARTICLE_PLAN_TOP_KEYS),
        "article_fields": sorted(ARTICLE_PLAN_ARTICLE_KEYS),
        "shot_fields": sorted(ARTICLE_PLAN_SHOT_KEYS),
        "structures": sorted(STRUCTURES["article-illustration"]),
        "visual_languages": ["default", *sorted(VISUAL_LANGUAGES)],
        "shot_count_rule": "one shot per distinct cognitive anchor; no fixed default count",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _command_plan_draft(args: argparse.Namespace) -> int:
    output = Path(args.output)
    if output.exists():
        raise VisualError(f"refusing to overwrite existing file: {output}")
    if not VISUAL_ID_RE.fullmatch(args.set_id):
        raise VisualError("set-id must use lowercase letters, numbers, and hyphens")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write(_json_bytes(_article_plan_template(args.set_id, args.language)))
    print(json.dumps({"status": "CREATED", "plan": str(output.resolve())}, ensure_ascii=False))
    return 0


def _command_materialize_plan(args: argparse.Namespace) -> int:
    result = _materialize_article_plan(Path(args.plan), Path(args.output))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    schema_parser = subparsers.add_parser(
        "schema", help="Print the visual brief contract."
    )
    schema_parser.set_defaults(handler=_command_schema)

    style_parser = subparsers.add_parser(
        "style-references",
        help="Print absolute image references for a built-in visual language.",
    )
    style_parser.add_argument(
        "visual_language",
        choices=sorted(
            name
            for name, language in VISUAL_LANGUAGES.items()
            if language["mode"] == "reference-pack"
        ),
    )
    style_parser.set_defaults(handler=_command_style_references)

    profile_parser = subparsers.add_parser(
        "style-profile",
        help="Print the JSON prompt profile for a built-in visual language.",
    )
    profile_parser.add_argument(
        "visual_language",
        choices=sorted(
            name
            for name, language in VISUAL_LANGUAGES.items()
            if language["mode"] == "prompt-profile"
        ),
    )
    profile_parser.set_defaults(handler=_command_style_profile)

    draft_parser = subparsers.add_parser(
        "draft", help="Create a non-destructive visual brief draft."
    )
    draft_parser.add_argument("output")
    draft_parser.add_argument("--kind", required=True, choices=sorted(KINDS))
    draft_parser.add_argument("--visual-id", required=True)
    draft_parser.add_argument("--language", default="zh-CN")
    draft_parser.set_defaults(handler=_command_draft)

    prompt_parser = subparsers.add_parser(
        "prompt", help="Validate a brief and derive the full generation prompt."
    )
    prompt_parser.add_argument("kit")
    prompt_parser.add_argument("--brief", required=True)
    prompt_parser.set_defaults(handler=_command_prompt)

    prompt_once_parser = subparsers.add_parser(
        "prompt-once",
        help=(
            "Build a one-off generation prompt from a supplied character reference "
            "without creating a character kit."
        ),
    )
    prompt_once_parser.add_argument("character_reference")
    prompt_once_parser.add_argument("--brief", required=True)
    prompt_once_parser.set_defaults(handler=_command_prompt_once)

    plan_schema_parser = subparsers.add_parser(
        "plan-schema", help="Print the whole-article illustration-plan contract."
    )
    plan_schema_parser.set_defaults(handler=_command_plan_schema)

    plan_draft_parser = subparsers.add_parser(
        "plan-draft", help="Create a non-destructive article illustration plan draft."
    )
    plan_draft_parser.add_argument("output")
    plan_draft_parser.add_argument("--set-id", required=True)
    plan_draft_parser.add_argument("--language", default="zh-CN")
    plan_draft_parser.set_defaults(handler=_command_plan_draft)

    materialize_parser = subparsers.add_parser(
        "materialize-plan",
        help="Validate one article plan and create ordered visual briefs.",
    )
    materialize_parser.add_argument("plan")
    materialize_parser.add_argument("--output", required=True)
    materialize_parser.set_defaults(handler=_command_materialize_plan)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except (VisualError, character_kit.ProfileError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"ERROR: filesystem operation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
