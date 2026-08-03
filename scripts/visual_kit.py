#!/usr/bin/env python3
"""Build, archive, and verify IP Studio derivative visuals."""

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

import character_kit


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "1.0"
RECORD_SCHEMA_VERSION = "2.0"
LEGACY_RECORD_SCHEMA_VERSION = "1.0"
CURRENT_SCHEMA_VERSION = "1.0"
ARTICLE_PLAN_SCHEMA_VERSION = "1.0"
ARTICLE_SET_SCHEMA_VERSION = "1.0"
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
ALLOWED_RATIOS = {
    "avatar": {"1:1"},
    "profile-banner": {"3:1", "5:2", "16:9", "4:1"},
    "profile-card": {"4:5", "3:4", "1:1"},
    "cover": {"5:2"},
    "explainer": {"4:5", "3:4", "16:9"},
    "article-illustration": {"16:9"},
}
DEFAULTS = {
    "avatar": ("1:1", "badge"),
    "profile-banner": ("3:1", "brand-narrative"),
    "profile-card": ("4:5", "identity-card"),
    "cover": ("5:2", "single-narrative"),
    "explainer": ("4:5", "process"),
    "article-illustration": ("16:9", "conceptual-metaphor"),
}
MINIMAL_HANDDRAWN_ROLE = "minimal-handdrawn-style"
MINIMAL_HANDDRAWN_KINDS = {"cover", "explainer", "article-illustration"}
MINIMAL_HANDDRAWN_REFERENCE_FILES = (
    "assets/visual-languages/minimal-handdrawn/examples/information-well.png",
    "assets/visual-languages/minimal-handdrawn/examples/idea-press.png",
    "assets/visual-languages/minimal-handdrawn/examples/content-fermentation.png",
    "assets/visual-languages/minimal-handdrawn/examples/trust-bridge.png",
)
REVISION_SCOPES = {
    "local-rendering",
    "content-structure",
    "character-revision",
}
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
    """Raised when a visual brief or archived result violates its contract."""


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


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
    if style != "minimal-handdrawn":
        raise VisualError(f"unsupported visual language: {style}")
    references: list[dict[str, str]] = []
    for relative in MINIMAL_HANDDRAWN_REFERENCE_FILES:
        path = (SKILL_ROOT / relative).resolve()
        _detect_image(path)
        references.append(
            {"role": MINIMAL_HANDDRAWN_ROLE, "path": str(path)}
        )
    source_notice = (
        SKILL_ROOT / "assets/visual-languages/minimal-handdrawn/SOURCE.md"
    ).resolve()
    if not source_notice.is_file():
        raise VisualError(
            f"missing visual language source notice: {source_notice}"
        )
    return {
        "status": "PASS",
        "visual_language": style,
        "brief_references": references,
        "source_notice": str(source_notice),
    }


def _safe_relative(root: Path, relative: str, label: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise VisualError(f"{label} must stay inside {root}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise VisualError(f"{label} escapes {root}") from error
    return resolved


def _filename_token(value: str) -> str:
    cleaned = re.sub(r"[^\w-]+", "-", value, flags=re.UNICODE)
    cleaned = cleaned.strip("-_")
    return (cleaned or "reference")[:80]


def _validate_brief(data: Any, base_dir: Path) -> dict[str, Any]:
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

    content = _require_object(brief["content"], "$.content", CONTENT_KEYS)
    content["source_label"] = _text(
        content["source_label"], "$.content.source_label", maximum=500
    )
    content["source_text"] = _text(
        content["source_text"], "$.content.source_text", maximum=100000
    )

    message = _require_object(brief["message"], "$.message", MESSAGE_KEYS)
    for key in MESSAGE_KEYS:
        message[key] = _text(
            message[key], f"$.message.{key}", maximum=3000
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
    if not RATIO_RE.fullmatch(ratio) or ratio not in ALLOWED_RATIOS[kind]:
        _fail(
            "$.composition.aspect_ratio",
            f"must be one of: {', '.join(sorted(ALLOWED_RATIOS[kind]))}",
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
        optional=kind == "avatar",
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
        optional=kind != "explainer",
        maximum=200,
    )
    labels = _text_list(
        composition["labels"], "$.composition.labels", 0, 5
    )
    if kind == "explainer" and not 3 <= len(labels) <= 5:
        _fail("$.composition.labels", "must contain 3-5 items for an explainer")
    if kind == "article-illustration" and len(labels) == 1:
        _fail(
            "$.composition.labels",
            "must be empty or contain 2-5 items for an article illustration",
        )
    composition["labels"] = labels

    palette = _text_list(
        composition["palette"], "$.composition.palette", 2, 5
    )
    for index, color in enumerate(palette):
        if not HEX_COLOR_RE.fullmatch(color):
            _fail(
                f"$.composition.palette[{index}]",
                "must use #RRGGBB",
            )
    if kind == "cover" and len(palette) > 4:
        _fail("$.composition.palette", "must contain 2-4 colors for a cover")
    if kind == "avatar" and len(palette) < 3:
        _fail("$.composition.palette", "must contain 3-5 colors for an avatar")
    composition["palette"] = [item.upper() for item in palette]
    composition["style_notes"] = _text(
        composition["style_notes"],
        "$.composition.style_notes",
        maximum=3000,
    )

    if kind == "cover":
        compact_title = re.sub(r"\s+", "", composition["title"])
        if not 6 <= len(compact_title) <= 16:
            _fail(
                "$.composition.title",
                "must contain 6-16 visible characters for a cover",
            )
        if composition["title"].count("\n") > 1:
            _fail("$.composition.title", "must use at most two lines")

    action = _require_object(
        brief["character_action"], "$.character_action", ACTION_KEYS
    )
    for key in ACTION_KEYS:
        action[key] = _text(
            action[key], f"$.character_action.{key}", maximum=3000
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
    minimal_handdrawn_count = sum(
        reference["role"] == MINIMAL_HANDDRAWN_ROLE
        for reference in cleaned_references
    )
    if minimal_handdrawn_count and kind not in MINIMAL_HANDDRAWN_KINDS:
        _fail(
            "$.references",
            "minimal-handdrawn-style is only available for cover, "
            "explainer, or article-illustration",
        )
    if minimal_handdrawn_count == 1:
        _fail(
            "$.references",
            "minimal-handdrawn-style requires at least two complete style "
            "references",
        )

    decisions = brief["decisions"]
    if not isinstance(decisions, list) or not 1 <= len(decisions) <= 50:
        _fail("$.decisions", "must contain 1-50 decisions")
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


def _reference_mapping(brief: dict[str, Any]) -> str:
    lines = [
        "第 1 张图片是角色包中已批准的唯一主参考图。",
    ]
    for index, reference in enumerate(brief["references"], start=2):
        lines.append(f"第 {index} 张图片用于：{reference['role']}。")
    return "\n".join(lines)


def _shared_decisions(brief: dict[str, Any]) -> str:
    message = brief["message"]
    brand = brief["brand"]
    composition = brief["composition"]
    action = brief["character_action"]
    return (
        f"内容真源：{brief['content']['source_label']}\n"
        f"{brief['content']['source_text']}\n\n"
        f"已确定的传播判断：核心对象是“{message['core_object']}”；"
        f"观众原本不容易理解“{message['audience_gap']}”；"
        f"需要表现的机制或变化是“{message['mechanism_or_change']}”；"
        f"看完应记住“{message['takeaway']}”。\n"
        f"品牌角色：{brand['role']}；名称：{brand['name'] or '无独立品牌名'}；"
        f"视觉线索：{brand['visual_cues'] or '服从角色与内容'}。\n"
        f"角色在画面中担任{action['role']}，亲自{action['action']}，"
        f"直接作用于{action['affected_object']}，形成可见结果："
        f"{action['visible_result']}。角色的爪、身体或已连接标志物必须与对象"
        "发生可见接触并造成状态变化，使角色动作承担这段信息关系；"
        "不采用旁站、教鞭或只指向内容的讲解姿势。角色完成动作时，身体、"
        "服装和标志物仍保持角色档案规定的数量、位置与连接方式，同一标志物"
        "只出现档案规定的实例数。\n"
        f"主色：{', '.join(composition['palette'])}；"
        f"补充风格：{composition['style_notes']}。"
    )


def _uses_minimal_handdrawn(brief: dict[str, Any]) -> bool:
    return any(
        reference["role"] == MINIMAL_HANDDRAWN_ROLE
        for reference in brief["references"]
    )


def _minimal_handdrawn_contract() -> str:
    return """视觉语言已选择“极简手绘 IP”。带有 minimal-handdrawn-style 角色的完整图片只用于校准留白、线条密度、色彩职责和角色参与方式，不临摹其中的构图、物体组合、文字或隐喻。

把抽象内容重新翻译成一个动作、一件无需说明就能认出的低技术物件和一个可见结果。整张图是一个连续的物理场景，角色亲自推动因果关系。主体与核心装置合计约占画面 40%–60%，至少保留约 35% 纯白空白。使用细而略有手绘感的黑线和平涂；黑色负责角色与结构，其余 2–3 种强调色各自只负责流动、问题或结果、提示中的一项。表情克制，优先用身体方向和对象反馈表达情绪。短标签贴近对象，能删就删。

不要生成卡片墙、仪表盘、网页界面、嵌套边框、独立小插图拼盘、完整环境、渐变、投影、体积光、写实纹理或无因果作用的装饰图标。"""


def _render_task(brief: dict[str, Any]) -> str:
    kind = brief["kind"]
    composition = brief["composition"]
    title = composition["title"] or "无文字"
    subtitle = composition["subtitle"] or "无"
    labels = "、".join(composition["labels"]) or "无"
    conclusion = composition["conclusion"] or "无"
    mapping = _reference_mapping(brief)
    decisions = _shared_decisions(brief)
    minimal_handdrawn = _uses_minimal_handdrawn(brief)

    if kind == "cover" and minimal_handdrawn:
        return f"""直接生成一张 {composition['aspect_ratio']} 横版极简手绘文章封面，不输出分析过程。

图片对应关系：
{mapping}

{decisions}

{_minimal_handdrawn_contract()}

只采用一个“{composition['structure']}”核心叙事，让具体核心对象、角色动作、物件状态和标题共同表达同一项变化。主标题准确写为“{title}”，最多两行；副标题：{subtitle}。标题与场景共享留白，不叠加海报边框、装饰层或第二场景。品牌为核心时只保留必要名称、logo 或品牌色，品牌为辅助时把它压到相关对象附近。"""

    if kind == "explainer" and minimal_handdrawn:
        return f"""直接生成一张适合手机阅读的 {composition['aspect_ratio']} 极简手绘说明图，不输出分析过程。

图片对应关系：
{mapping}

{decisions}

{_minimal_handdrawn_contract()}

只采用“{composition['structure']}”这一种关系，把 3–5 个关键节点放在同一个装置、路径或连续互动中，不拆成卡片和模块。主标题准确写为“{title}”，最多两行；节点短标签依次为：{labels}；结论写为“{conclusion}”。角色接收输入、完成关键动作并把可见结果传向下一节点，位置、流向和对象状态本身形成阅读顺序。"""

    if kind == "article-illustration" and minimal_handdrawn:
        return f"""直接生成一张 {composition['aspect_ratio']} 横版极简手绘正文插图，不输出分析过程。

图片对应关系：
{mapping}

{decisions}

{_minimal_handdrawn_contract()}

只解释当前内容中最值得图像化的一项关系或变化，采用“{composition['structure']}”表达。优先使用一个物理隐喻场景：角色亲自移动、连接、拆分、选择、阻挡、压制、倒入或取出对象，并让对象的位置、流向或前后状态显示结果。短标题：{title}；副标题：{subtitle}；必要标签：{labels}。隐藏全部文字后仍应能看懂主要动作和结果；画面到此即止。"""

    if kind == "cover":
        return f"""直接生成一张 {composition['aspect_ratio']} 横版二次元文章封面，不输出分析过程。

图片对应关系：
{mapping}

{decisions}

只采用一个“{composition['structure']}”核心视觉叙事。把具体核心对象、视觉隐喻、角色动作和标题共同用于表达同一项关键变化；角色的动作是叙事中的必要因果环节。采用极简符号海报与精致二次元插画结合的风格，保持一个明确焦点和充足呼吸感。主标题准确写为“{title}”，最多两行；副标题：{subtitle}。品牌为核心时让名称、logo 与设计语言进入第一视觉层，品牌为辅助时只融入相关位置。画面只保留一个视觉中心和必要文字，不扩展内容真源之外的品牌、功能或行业符号。"""

    if kind == "explainer":
        return f"""直接生成一张适合推文、社媒传播和手机阅读的 {composition['aspect_ratio']} 说明图，不输出分析过程。

图片对应关系：
{mapping}

{decisions}

只采用“{composition['structure']}”这一种主要图解结构。按“主标题 → 核心结构 → 3–5 个关键模块 → 一句结论”建立明确阅读顺序。主标题准确写为“{title}”，最多两行；模块短标题依次为：{labels}；结论写为“{conclusion}”。每个模块只保留短标题、必要数字和一句极短说明。角色作为信息结构中的行动节点，接收输入、执行动作并把可见结果传到下一环，或作出会改变路径的选择。品牌为核心时让名称、logo 和设计语言进入第一视觉层，品牌为辅助时只融入相关节点。信息量以手机端能顺畅读完为止。"""

    if kind == "article-illustration":
        return f"""直接生成一张 {composition['aspect_ratio']} 横版正文插图，不输出分析过程。

图片对应关系：
{mapping}

{decisions}

只解释当前内容中最值得图像化的一项关系或变化，采用“{composition['structure']}”表达。重点表现对象怎样连接、分工、转换、冲突或改变结果，不陈列一组相关物品。采用轻量概念图解与二次元插画结合的风格，图形语言简洁统一。角色亲自移动、连接、拆分、选择、阻挡或转换对象，或者让机制对角色造成可见的前后变化；角色行为承担一段信息关系。短标题：{title}；副标题：{subtitle}；必要标签：{labels}。文字并非理解所必需时省略。视觉范围到解释清楚这一项内容为止。"""

    if kind == "avatar":
        return f"""直接生成一张 {composition['aspect_ratio']} 社交头像，不输出分析过程。

图片对应关系：
{mapping}

{decisions}

采用“{composition['structure']}”头像构图。角色正面大头或头肩居中，核心轮廓、眼睛、表情、服装领口和标志物在小尺寸仍能辨认；主体全部留在圆形裁切安全区，同时方形显示也完整。画面使用干净背景和高对比色块，不添加标题、说明文字或无关装饰。结果是一张能同时用于圆形与方形平台裁切的完整 1:1 源图。"""

    if kind == "profile-banner":
        return f"""直接生成一张 {composition['aspect_ratio']} 个人或品牌主页横幅，不输出分析过程。

图片对应关系：
{mapping}

{decisions}

采用“{composition['structure']}”构图，让角色以半身、头肩或动态回眸进入一个明确品牌叙事。根据用户提供的平台资料保留头像、按钮和裁切安全区；没有平台资料时采用左下角留空的通用主页安全布局。主标题或标语准确写为“{title}”，副标题：{subtitle}。角色与核心符号发生真实互动并产生可见变化，背景保持干净，文字和装饰不抢角色。"""

    return f"""直接生成一张 {composition['aspect_ratio']} 个人或品牌 IP 资料卡，不输出分析过程。

图片对应关系：
{mapping}

{decisions}

采用“{composition['structure']}”构图。让一个主角色、名称和一句定位形成第一视觉层，再用 2–4 个短标签呈现稳定身份线索。标题准确写为“{title}”，副标题：{subtitle}；标签：{labels}。角色通过真实动作把核心象征带入信息结构，卡片在手机端缩略图中仍能快速识别，背景和装饰服从角色与信息层级。角色档案中的三视图、配色地图和结构清单只用于保持身份，不作为资料卡要展示的内容。"""


def build_visual_bundle(
    kit: Path,
    brief_data: Any,
    base_dir: Path,
) -> dict[str, Any]:
    brief = _validate_brief(brief_data, base_dir)
    task = _render_task(brief)
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
            "sha256": _sha256_file(master),
            "source": "character-master",
            "brief_index": None,
        }
    ]
    for brief_index, reference in enumerate(brief["references"]):
        path = Path(reference["path"]).resolve()
        image_references.append(
            {
                "index": brief_index + 2,
                "role": reference["role"],
                "path": str(path),
                "sha256": _sha256_file(path),
                "source": "brief",
                "brief_index": brief_index,
            }
        )
    return {
        "status": "PASS",
        "visual_id": brief["visual_id"],
        "kind": brief["kind"],
        "character_id": character["character_id"],
        "character_revision": character["character_revision"],
        "profile": character["profile"],
        "profile_sha256": character["profile_sha256"],
        "master_reference": character["master_reference"],
        "master_sha256": character["master_sha256"],
        "prompt_sha256": character["prompt_sha256"],
        "prompt_characters": character["prompt_characters"],
        "image_references": image_references,
        "prompt": character["prompt"],
        "brief": brief,
    }


def _visual_root(kit: Path, brief: dict[str, Any]) -> Path:
    return (
        kit.resolve()
        / "derivatives"
        / brief["kind"]
        / brief["visual_id"]
    )


def _revision_label(value: Any, label: str) -> str:
    rendered = str(value)
    if not re.fullmatch(r"r\d{3,}", rendered) or int(rendered[1:]) < 1:
        raise VisualError(f"{label} must be an rNNN label")
    return rendered


def _current_pointer(root: Path) -> dict[str, Any]:
    if (root / "visual-record.json").is_file():
        raise VisualError(
            "legacy flat visual detected; run migrate-visual before normal use"
        )
    pointer = _require_object(
        _load_json(root / "current.json"),
        "$current",
        {
            "schema_version",
            "visual_id",
            "kind",
            "current_revision",
            "updated_at",
        },
    )
    if pointer["schema_version"] != CURRENT_SCHEMA_VERSION:
        raise VisualError("unsupported visual current pointer schema")
    _revision_label(pointer["current_revision"], "current_revision")
    return pointer


def _revision_bundle(
    kit: Path,
    root: Path,
    brief_data: Any,
    base_dir: Path,
    scope: str,
    note: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if scope not in REVISION_SCOPES:
        raise VisualError("unsupported revision scope")
    note = _text(note, "$revision.note", maximum=1000)
    parent = _check_visual(root, kit)
    bundle = build_visual_bundle(kit, brief_data, base_dir)
    if bundle["visual_id"] != parent["visual_id"] or bundle["kind"] != parent["kind"]:
        raise VisualError("revision brief must keep the existing visual_id and kind")
    same_character_revision = (
        bundle["character_revision"] == parent["character_revision"]
    )
    if scope == "character-revision" and same_character_revision:
        raise VisualError(
            "character-revision scope requires a newly locked character revision"
        )
    if scope != "character-revision" and not same_character_revision:
        raise VisualError(
            "only character-revision scope may change the locked character revision"
        )

    previous = Path(parent["image"]).resolve()
    previous_reference = {
        "index": 2,
        "role": "previous-visual",
        "path": str(previous),
        "sha256": _sha256_file(previous),
        "source": "previous-visual",
        "brief_index": None,
    }
    for item in bundle["image_references"][1:]:
        item["index"] += 1
    bundle["image_references"].insert(1, previous_reference)
    directions = {
        "local-rendering": (
            "这是局部无损编辑。把上一版成图作为编辑底图，只修改新简报和修订说明明确指出的局部；"
            "未点名的构图、角色身份、颜色、物件和信息必须保持不变。"
        ),
        "content-structure": (
            "这是内容或结构重做。以上一版只作为角色和视觉语言连续性参考，按新简报重新组织信息，"
            "不得沿用已被修改的旧重点。"
        ),
        "character-revision": (
            "这是角色版本更新后的重做。新角色主参考图是唯一身份真源；上一版只用于继承这张衍生图的用途和视觉节奏。"
        ),
    }
    prompt = f"{directions[scope]}\n修订说明：{note}\n\n{bundle['prompt']}"
    bundle["prompt"] = prompt
    bundle["prompt_sha256"] = _sha256_bytes(prompt.encode("utf-8"))
    bundle["prompt_characters"] = len(prompt)
    bundle["revision_note"] = note
    return bundle, parent


def _write_revision(
    kit: Path,
    folder: Path,
    bundle: dict[str, Any],
    image_path: Path,
    revision_label: str,
    parent_revision: str | None,
    scope: str,
    note: str,
) -> None:
    brief = bundle["brief"]
    media_type, extension = _detect_image(image_path)
    folder.mkdir(parents=True, exist_ok=False)
    archived_brief = copy.deepcopy(brief)
    archived_references: list[dict[str, Any]] = []
    inputs_dir = folder / "inputs"

    master_path = Path(str(bundle["master_reference"])).resolve()
    try:
        master_relative = str(master_path.relative_to(kit.resolve())).replace(
            "\\", "/"
        )
    except ValueError as error:
        raise VisualError("character master must stay inside the kit") from error

    for reference in bundle["image_references"]:
        source = Path(str(reference["path"])).resolve()
        ref_media_type, ref_extension = _detect_image(source)
        if reference["index"] == 1:
            archived_references.append(
                {
                    "index": 1,
                    "role": "approved-character-master",
                    "source": "character-master",
                    "brief_index": None,
                    "root": "kit",
                    "file": master_relative,
                    "sha256": _sha256_file(master_path),
                    "bytes": master_path.stat().st_size,
                    "media_type": ref_media_type,
                }
            )
            continue
        inputs_dir.mkdir(parents=True, exist_ok=True)
        archived_name = (
            f"{reference['index']:02d}-{_filename_token(reference['role'])}"
            f"{ref_extension}"
        )
        archived_relative = Path("inputs") / archived_name
        shutil.copyfile(source, folder / archived_relative)
        brief_index = reference.get("brief_index")
        if brief_index is not None:
            archived_brief["references"][brief_index]["path"] = str(
                archived_relative
            ).replace("\\", "/")
        archived_references.append(
            {
                "index": reference["index"],
                "role": reference["role"],
                "source": reference.get("source", "brief"),
                "brief_index": brief_index,
                "root": "revision",
                "file": str(archived_relative).replace("\\", "/"),
                "sha256": _sha256_file(folder / archived_relative),
                "bytes": (folder / archived_relative).stat().st_size,
                "media_type": ref_media_type,
            }
        )

    brief_bytes = _json_bytes(archived_brief)
    (folder / "visual-brief.json").write_bytes(brief_bytes)
    profile_snapshot = Path(str(bundle["profile"])).read_bytes()
    (folder / "character-profile.snapshot.json").write_bytes(profile_snapshot)
    prompt_bytes = (str(bundle["prompt"]) + "\n").encode("utf-8")
    (folder / "generation-prompt.txt").write_bytes(prompt_bytes)
    output_name = f"final{extension}"
    shutil.copyfile(image_path, folder / output_name)
    record = {
        "record_schema_version": RECORD_SCHEMA_VERSION,
        "visual_id": brief["visual_id"],
        "kind": brief["kind"],
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "revision": {
            "label": revision_label,
            "number": int(revision_label[1:]),
            "parent": parent_revision,
            "change_scope": scope,
            "note": note,
        },
        "character": {
            "character_id": bundle["character_id"],
            "revision": bundle["character_revision"],
            "profile_sha256": bundle["profile_sha256"],
            "profile_snapshot": "character-profile.snapshot.json",
            "profile_snapshot_sha256": _sha256_bytes(profile_snapshot),
            "master_reference": master_relative,
            "master_sha256": bundle["master_sha256"],
        },
        "brief": {
            "file": "visual-brief.json",
            "sha256": _sha256_bytes(brief_bytes),
        },
        "generation": {
            "prompt_file": "generation-prompt.txt",
            "prompt_sha256": bundle["prompt_sha256"],
            "input_references": archived_references,
        },
        "output": {
            "file": output_name,
            "sha256": _sha256_file(folder / output_name),
            "bytes": (folder / output_name).stat().st_size,
            "media_type": media_type,
        },
    }
    (folder / "visual-record.json").write_bytes(_json_bytes(record))


def _archive_final(
    kit: Path,
    brief_path: Path,
    image_path: Path,
) -> dict[str, Any]:
    bundle = build_visual_bundle(
        kit,
        _load_json(brief_path),
        brief_path.parent,
    )
    root = _visual_root(kit, bundle["brief"])
    if root.exists():
        raise VisualError(f"refusing to overwrite existing visual: {root}")
    root.parent.mkdir(parents=True, exist_ok=True)
    stage = root.parent / f".{root.name}.{uuid.uuid4().hex}.staging"
    revision_dir = stage / "revisions" / "r001"
    revision_dir.parent.mkdir(parents=True, exist_ok=False)
    _write_revision(
        kit.resolve(),
        revision_dir,
        bundle,
        image_path,
        "r001",
        None,
        "initial",
        "initial approved visual",
    )
    pointer = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "visual_id": bundle["visual_id"],
        "kind": bundle["kind"],
        "current_revision": "r001",
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    (stage / "current.json").write_bytes(_json_bytes(pointer))
    os.replace(stage, root)
    return _check_visual(root, kit.resolve())


def _revise_visual(
    kit: Path,
    root: Path,
    brief_path: Path,
    image_path: Path,
    scope: str,
    note: str,
) -> dict[str, Any]:
    bundle, parent = _revision_bundle(
        kit.resolve(),
        root.resolve(),
        _load_json(brief_path),
        brief_path.parent,
        scope,
        note,
    )
    next_number = int(parent["revision"][1:]) + 1
    label = f"r{next_number:03d}"
    destination = root.resolve() / "revisions" / label
    if destination.exists():
        raise VisualError(f"visual revision already exists: {destination}")
    stage = destination.parent / f".{label}.{uuid.uuid4().hex}.staging"
    _write_revision(
        kit.resolve(),
        stage,
        bundle,
        image_path,
        label,
        parent["revision"],
        scope,
        bundle["revision_note"],
    )
    os.replace(stage, destination)
    pointer = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "visual_id": bundle["visual_id"],
        "kind": bundle["kind"],
        "current_revision": label,
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    temporary = root.resolve() / f".current.{uuid.uuid4().hex}.tmp"
    temporary.write_bytes(_json_bytes(pointer))
    os.replace(temporary, root.resolve() / "current.json")
    return _check_visual(root, kit.resolve())


def _check_visual(
    root: Path,
    kit: Path,
    revision_label: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    kit = kit.resolve()
    if not root.is_dir():
        raise VisualError(f"visual folder does not exist: {root}")
    pointer = _current_pointer(root)
    label = _revision_label(
        revision_label or pointer["current_revision"],
        "visual revision",
    )
    folder = root / "revisions" / label
    if not folder.is_dir():
        raise VisualError(f"visual revision does not exist: {folder}")

    record = _require_object(
        _load_json(folder / "visual-record.json"),
        "$record",
        {
            "record_schema_version",
            "visual_id",
            "kind",
            "created_at",
            "revision",
            "character",
            "brief",
            "generation",
            "output",
        },
    )
    if record["record_schema_version"] != RECORD_SCHEMA_VERSION:
        raise VisualError("unsupported visual record schema")
    revision = _require_object(
        record["revision"],
        "$record.revision",
        {"label", "number", "parent", "change_scope", "note"},
    )
    if revision["label"] != label or revision["number"] != int(label[1:]):
        raise VisualError("visual revision metadata mismatch")
    if label == "r001":
        if revision["parent"] is not None or revision["change_scope"] != "initial":
            raise VisualError("r001 must be an initial revision without a parent")
    else:
        expected_parent = f"r{int(label[1:]) - 1:03d}"
        if revision["parent"] != expected_parent:
            raise VisualError("visual revision parent must be the preceding revision")
        if revision["change_scope"] not in REVISION_SCOPES:
            raise VisualError("unsupported visual revision scope")

    character_record = _require_object(
        record["character"],
        "$record.character",
        {
            "character_id",
            "revision",
            "profile_sha256",
            "profile_snapshot",
            "profile_snapshot_sha256",
            "master_reference",
            "master_sha256",
        },
    )
    brief_record = _require_object(record["brief"], "$record.brief", {"file", "sha256"})
    generation_record = _require_object(
        record["generation"],
        "$record.generation",
        {"prompt_file", "prompt_sha256", "input_references"},
    )
    output_record = _require_object(
        record["output"],
        "$record.output",
        {"file", "sha256", "bytes", "media_type"},
    )
    current_character = character_kit.build_prompt_bundle(
        kit, "scene", "验证角色包仍可读取；不生成图片。"
    )
    if current_character["character_id"] != character_record["character_id"]:
        raise VisualError("record character_id does not match the current kit")

    brief_path = _safe_relative(folder, brief_record["file"], "brief file")
    brief_bytes = brief_path.read_bytes()
    if _sha256_bytes(brief_bytes) != brief_record["sha256"]:
        raise VisualError("visual brief SHA-256 mismatch")
    brief = _validate_brief(_load_json(brief_path), folder)
    if brief["visual_id"] != record["visual_id"] or brief["kind"] != record["kind"]:
        raise VisualError("record and brief identity mismatch")
    if pointer["visual_id"] != record["visual_id"] or pointer["kind"] != record["kind"]:
        raise VisualError("current pointer and record identity mismatch")

    snapshot_path = _safe_relative(folder, character_record["profile_snapshot"], "profile snapshot")
    snapshot_bytes = snapshot_path.read_bytes()
    if _sha256_bytes(snapshot_bytes) != character_record["profile_snapshot_sha256"]:
        raise VisualError("character profile snapshot SHA-256 mismatch")
    snapshot = character_kit.validate_locked_profile(_load_json(snapshot_path))
    if snapshot["character_id"] != character_record["character_id"]:
        raise VisualError("profile snapshot character_id mismatch")
    if f"r{snapshot['revision']:03d}" != character_record["revision"]:
        raise VisualError("profile snapshot revision mismatch")
    canonical_profile = json.dumps(
        {key: snapshot[key] for key in character_kit.AUTHOR_KEY_ORDER},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if _sha256_bytes(canonical_profile) != character_record["profile_sha256"]:
        raise VisualError("profile snapshot canonical SHA-256 mismatch")

    master_path = _safe_relative(kit, character_record["master_reference"], "master reference")
    master_media_type, _ = _detect_image(master_path)
    if snapshot["assets"]["master_reference"] != character_record["master_reference"]:
        raise VisualError("profile snapshot master reference mismatch")
    if snapshot["assets"]["sha256"] != character_record["master_sha256"]:
        raise VisualError("profile snapshot master SHA-256 mismatch")
    if snapshot["assets"]["bytes"] != master_path.stat().st_size:
        raise VisualError("profile snapshot master byte size mismatch")
    if snapshot["assets"]["media_type"] != master_media_type:
        raise VisualError("profile snapshot master media type mismatch")
    if _sha256_file(master_path) != character_record["master_sha256"]:
        raise VisualError("archived character master SHA-256 mismatch")

    prompt_path = _safe_relative(folder, generation_record["prompt_file"], "generation prompt")
    if _sha256_bytes(prompt_path.read_bytes().rstrip(b"\r\n")) != generation_record["prompt_sha256"]:
        raise VisualError("generation prompt SHA-256 mismatch")

    input_references = generation_record["input_references"]
    expected_count = 1 + len(brief["references"]) + (0 if label == "r001" else 1)
    if not isinstance(input_references, list) or len(input_references) != expected_count:
        raise VisualError(f"record must contain {expected_count} input references")
    seen_brief_indices: set[int] = set()
    previous_count = 0
    for position, raw_item in enumerate(input_references):
        item = _require_object(
            raw_item,
            f"$record.generation.input_references[{position}]",
            {
                "index",
                "role",
                "source",
                "brief_index",
                "root",
                "file",
                "sha256",
                "bytes",
                "media_type",
            },
        )
        if item["index"] != position + 1:
            raise VisualError("input reference index mismatch")
        candidate = _safe_relative(
            kit if item["root"] == "kit" else folder,
            item["file"],
            "input reference",
        )
        media_type, _ = _detect_image(candidate)
        if candidate.stat().st_size != item["bytes"] or media_type != item["media_type"]:
            raise VisualError("input reference metadata mismatch")
        if _sha256_file(candidate) != item["sha256"]:
            raise VisualError("input reference SHA-256 mismatch")
        if position == 0:
            if (
                item["source"] != "character-master"
                or item["role"] != "approved-character-master"
                or item["brief_index"] is not None
                or candidate != master_path
            ):
                raise VisualError("first input must be the locked character master")
        elif item["source"] == "previous-visual":
            previous_count += 1
            if item["brief_index"] is not None or item["role"] != "previous-visual":
                raise VisualError("invalid previous visual input")
            parent_folder = root / "revisions" / str(revision["parent"])
            parent_record = _load_json(parent_folder / "visual-record.json")
            parent_output = _safe_relative(
                parent_folder, parent_record["output"]["file"], "parent output"
            )
            if _sha256_file(parent_output) != item["sha256"]:
                raise VisualError("previous visual input does not match parent output")
        elif item["source"] == "brief":
            brief_index = item["brief_index"]
            if not isinstance(brief_index, int) or not 0 <= brief_index < len(brief["references"]):
                raise VisualError("invalid brief reference index")
            if brief_index in seen_brief_indices:
                raise VisualError("duplicate brief reference index")
            seen_brief_indices.add(brief_index)
            brief_reference = brief["references"][brief_index]
            if item["role"] != brief_reference["role"] or candidate != Path(brief_reference["path"]).resolve():
                raise VisualError("brief reference does not match archived input")
        else:
            raise VisualError("unsupported input reference source")
    if previous_count != (0 if label == "r001" else 1):
        raise VisualError("revision must contain exactly one previous visual input")
    if seen_brief_indices != set(range(len(brief["references"]))):
        raise VisualError("not every brief reference was archived")

    output = _safe_relative(folder, output_record["file"], "output image")
    media_type, _ = _detect_image(output)
    if media_type != output_record["media_type"] or output.stat().st_size != output_record["bytes"]:
        raise VisualError("output image metadata mismatch")
    if _sha256_file(output) != output_record["sha256"]:
        raise VisualError("output SHA-256 mismatch")
    return {
        "status": "PASS",
        "visual": str(root),
        "visual_id": record["visual_id"],
        "kind": record["kind"],
        "revision": label,
        "current_revision": pointer["current_revision"],
        "character_id": character_record["character_id"],
        "character_revision": character_record["revision"],
        "image": str(output),
        "record": str(folder / "visual-record.json"),
    }


def _check_legacy_visual(folder: Path, kit: Path) -> dict[str, Any]:
    folder = folder.resolve()
    record = _require_object(
        _load_json(folder / "visual-record.json"),
        "$legacy_record",
        {
            "record_schema_version",
            "visual_id",
            "kind",
            "created_at",
            "character",
            "brief",
            "generation",
            "output",
        },
    )
    if record["record_schema_version"] != LEGACY_RECORD_SCHEMA_VERSION:
        raise VisualError("folder is not a legacy flat visual")
    brief_path = _safe_relative(folder, record["brief"]["file"], "legacy brief")
    if _sha256_file(brief_path) != record["brief"]["sha256"]:
        raise VisualError("legacy brief SHA-256 mismatch")
    _validate_brief(_load_json(brief_path), folder)
    output = _safe_relative(folder, record["output"]["file"], "legacy output")
    _detect_image(output)
    if _sha256_file(output) != record["output"]["sha256"]:
        raise VisualError("legacy output SHA-256 mismatch")
    character_kit._check_kit(kit.resolve())
    return {"record": record, "brief": brief_path, "output": output}


def _migrate_visual(root: Path, kit: Path) -> dict[str, Any]:
    root = root.resolve()
    kit = kit.resolve()
    legacy = _check_legacy_visual(root, kit)
    record = copy.deepcopy(legacy["record"])
    stage = root.parent / f".{root.name}.{uuid.uuid4().hex}.migration"
    revision_dir = stage / "revisions" / "r001"
    shutil.copytree(root, revision_dir)
    record["record_schema_version"] = RECORD_SCHEMA_VERSION
    record["revision"] = {
        "label": "r001",
        "number": 1,
        "parent": None,
        "change_scope": "initial",
        "note": "migrated from the former flat visual archive",
    }
    converted: list[dict[str, Any]] = []
    for position, item in enumerate(record["generation"]["input_references"]):
        if position == 0:
            candidate = _safe_relative(kit, item["file"], "legacy character master")
            media_type, _ = _detect_image(candidate)
            converted.append(
                {
                    "index": 1,
                    "role": item["role"],
                    "source": "character-master",
                    "brief_index": None,
                    "root": "kit",
                    "file": item["file"],
                    "sha256": item["sha256"],
                    "bytes": candidate.stat().st_size,
                    "media_type": media_type,
                }
            )
        else:
            converted.append(
                {
                    **item,
                    "source": "brief",
                    "brief_index": position - 1,
                    "root": "revision",
                }
            )
    record["generation"]["input_references"] = converted
    (revision_dir / "visual-record.json").write_bytes(_json_bytes(record))
    pointer = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "visual_id": record["visual_id"],
        "kind": record["kind"],
        "current_revision": "r001",
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    (stage / "current.json").write_bytes(_json_bytes(pointer))
    _check_visual(stage, kit)
    archive_root = root.parent / ".ip-studio-legacy-archives"
    archive_root.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = archive_root / f"{root.name}-{timestamp}"
    if archive.exists():
        raise VisualError(f"legacy archive target already exists: {archive}")
    os.replace(root, archive)
    try:
        os.replace(stage, root)
    except OSError as error:
        raise VisualError(
            f"migration activation failed; original visual remains at {archive}"
        ) from error
    checked = _check_visual(root, kit)
    checked["legacy_archive"] = str(archive)
    return checked


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
    if plan["visual_language"] == "minimal-handdrawn":
        references = _style_reference_manifest("minimal-handdrawn")[
            "brief_references"
        ]
    return {
        "schema_version": SCHEMA_VERSION,
        "visual_id": shot["visual_id"],
        "kind": "article-illustration",
        "language": plan["language"],
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
    if plan["visual_language"] not in {"default", "minimal-handdrawn"}:
        raise VisualError("visual_language must be default or minimal-handdrawn")
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


def _set_pointer(root: Path) -> dict[str, Any]:
    pointer = _require_object(
        _load_json(root / "current.json"),
        "$set_current",
        {"schema_version", "set_id", "current_revision", "updated_at"},
    )
    if pointer["schema_version"] != ARTICLE_SET_SCHEMA_VERSION:
        raise VisualError("unsupported article set pointer schema")
    _revision_label(pointer["current_revision"], "article set current_revision")
    return pointer


def _assert_visual_matches_shot(
    visual: dict[str, Any],
    plan: dict[str, Any],
    shot: dict[str, Any],
) -> None:
    record_path = Path(visual["record"])
    record = _load_json(record_path)
    actual = _validate_brief(
        _load_json(record_path.parent / record["brief"]["file"]),
        record_path.parent,
    )
    expected = _validate_brief(_shot_brief(plan, shot), SKILL_ROOT)
    semantic_fields = (
        "visual_id",
        "kind",
        "language",
        "content",
        "message",
        "brand",
        "composition",
        "character_action",
        "decisions",
    )
    for field in semantic_fields:
        if actual[field] != expected[field]:
            raise VisualError(
                f"visual {shot['visual_id']} no longer matches article plan field {field}"
            )
    if [item["role"] for item in actual["references"]] != [
        item["role"] for item in expected["references"]
    ]:
        raise VisualError(
            f"visual {shot['visual_id']} reference roles do not match the article plan"
        )


def _finalize_article_set(kit: Path, plan_path: Path) -> dict[str, Any]:
    kit = kit.resolve()
    plan = _validate_article_plan(_load_json(plan_path))
    visuals: list[dict[str, Any]] = []
    for shot in plan["shots"]:
        root = kit / "derivatives" / "article-illustration" / shot["visual_id"]
        visual = _check_visual(root, kit)
        _assert_visual_matches_shot(visual, plan, shot)
        visuals.append(visual)
    root = kit / "derivatives" / "article-illustration-set" / plan["set_id"]
    is_new = not root.exists()
    if not is_new:
        current = _set_pointer(root)
        number = int(str(current["current_revision"])[1:]) + 1
    else:
        number = 1
        root.parent.mkdir(parents=True, exist_ok=True)
    label = f"r{number:03d}"
    if is_new:
        stage_root = root.parent / f".{root.name}.{uuid.uuid4().hex}.staging"
        stage = stage_root / "revisions" / label
        stage.mkdir(parents=True, exist_ok=False)
        destination = stage
    else:
        destination = root / "revisions" / label
        if destination.exists():
            raise VisualError(f"article set revision already exists: {destination}")
        stage_root = root
        stage = destination.parent / f".{label}.{uuid.uuid4().hex}.staging"
        stage.mkdir(parents=False, exist_ok=False)
    plan_bytes = _json_bytes(plan)
    (stage / "article-plan.json").write_bytes(plan_bytes)
    shots: list[dict[str, Any]] = []
    for index, (shot, visual) in enumerate(zip(plan["shots"], visuals), start=1):
        visual_root = Path(visual["visual"])
        shots.append(
            {
                "index": index,
                "visual_id": shot["visual_id"],
                "placement_after": shot["placement_after"],
                "source_excerpt_sha256": _sha256_bytes(shot["source_excerpt"].encode("utf-8")),
                "visual_root": str(visual_root.relative_to(kit)).replace("\\", "/"),
                "visual_revision": visual["revision"],
                "image_sha256": _sha256_file(Path(visual["image"])),
            }
        )
    record = {
        "schema_version": ARTICLE_SET_SCHEMA_VERSION,
        "set_id": plan["set_id"],
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "revision": label,
        "plan": {"file": "article-plan.json", "sha256": _sha256_bytes(plan_bytes)},
        "shots": shots,
    }
    (stage / "article-set-record.json").write_bytes(_json_bytes(record))
    pointer = {
        "schema_version": ARTICLE_SET_SCHEMA_VERSION,
        "set_id": plan["set_id"],
        "current_revision": label,
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    if is_new:
        (stage_root / "current.json").write_bytes(_json_bytes(pointer))
        _check_article_set(stage_root, kit)
        os.replace(stage_root, root)
    else:
        os.replace(stage, destination)
        temporary = root / f".current.{uuid.uuid4().hex}.tmp"
        temporary.write_bytes(_json_bytes(pointer))
        os.replace(temporary, root / "current.json")
    return _check_article_set(root, kit)


def _check_article_set(
    root: Path,
    kit: Path,
    revision_label: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    kit = kit.resolve()
    pointer = _set_pointer(root)
    label = _revision_label(
        revision_label or pointer["current_revision"],
        "article set revision",
    )
    folder = root / "revisions" / label
    record = _require_object(
        _load_json(folder / "article-set-record.json"),
        "$set_record",
        {"schema_version", "set_id", "created_at", "revision", "plan", "shots"},
    )
    if record["schema_version"] != ARTICLE_SET_SCHEMA_VERSION or record["revision"] != label:
        raise VisualError("article set record schema or revision mismatch")
    if record["set_id"] != pointer["set_id"]:
        raise VisualError("article set pointer identity mismatch")
    plan_record = _require_object(record["plan"], "$set_record.plan", {"file", "sha256"})
    plan_path = _safe_relative(folder, plan_record["file"], "article plan")
    if _sha256_file(plan_path) != plan_record["sha256"]:
        raise VisualError("article plan SHA-256 mismatch")
    plan = _validate_article_plan(_load_json(plan_path))
    shots = record["shots"]
    if not isinstance(shots, list) or len(shots) != len(plan["shots"]):
        raise VisualError("article set shot count mismatch")
    images: list[str] = []
    for index, (item, planned) in enumerate(zip(shots, plan["shots"]), start=1):
        item = _require_object(
            item,
            f"$set_record.shots[{index - 1}]",
            {
                "index",
                "visual_id",
                "placement_after",
                "source_excerpt_sha256",
                "visual_root",
                "visual_revision",
                "image_sha256",
            },
        )
        if item["index"] != index or item["visual_id"] != planned["visual_id"]:
            raise VisualError("article set shot order or visual_id mismatch")
        if item["placement_after"] != planned["placement_after"]:
            raise VisualError("article set placement mismatch")
        if item["source_excerpt_sha256"] != _sha256_bytes(planned["source_excerpt"].encode("utf-8")):
            raise VisualError("article set excerpt mismatch")
        visual_root = _safe_relative(kit, item["visual_root"], "article visual root")
        visual = _check_visual(visual_root, kit, item["visual_revision"])
        _assert_visual_matches_shot(visual, plan, planned)
        if _sha256_file(Path(visual["image"])) != item["image_sha256"]:
            raise VisualError("article set image SHA-256 mismatch")
        images.append(visual["image"])
    return {
        "status": "PASS",
        "set": str(root),
        "set_id": record["set_id"],
        "revision": label,
        "current_revision": pointer["current_revision"],
        "shot_count": len(images),
        "images": images,
        "plan": str(plan_path),
    }


def _schema() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kinds": sorted(KINDS),
        "required_top_level_fields": sorted(TOP_KEYS),
        "allowed_ratios": {
            key: sorted(value) for key, value in ALLOWED_RATIOS.items()
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
            "minimal-handdrawn": {
                "available_for": sorted(MINIMAL_HANDDRAWN_KINDS),
                "reference_role": MINIMAL_HANDDRAWN_ROLE,
                "reference_count": len(MINIMAL_HANDDRAWN_REFERENCE_FILES),
            }
        },
        "archive_contract": {
            "record_schema_version": RECORD_SCHEMA_VERSION,
            "current_pointer_schema_version": CURRENT_SCHEMA_VERSION,
            "layout": "<visual>/current.json + revisions/rNNN/",
            "revision_scopes": sorted(REVISION_SCOPES),
            "legacy_migration_command": "migrate-visual",
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


def _command_revision_prompt(args: argparse.Namespace) -> int:
    brief_path = Path(args.brief)
    bundle, parent = _revision_bundle(
        Path(args.kit),
        Path(args.visual),
        _load_json(brief_path),
        brief_path.parent,
        args.change_scope,
        args.note,
    )
    printable = {key: value for key, value in bundle.items() if key != "brief"}
    printable["parent_revision"] = parent["revision"]
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0


def _command_finalize(args: argparse.Namespace) -> int:
    result = _archive_final(
        Path(args.kit),
        Path(args.brief),
        Path(args.image),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _command_revise(args: argparse.Namespace) -> int:
    result = _revise_visual(
        Path(args.kit),
        Path(args.visual),
        Path(args.brief),
        Path(args.image),
        args.change_scope,
        args.note,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _command_migrate_visual(args: argparse.Namespace) -> int:
    result = _migrate_visual(Path(args.visual), Path(args.kit))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _command_check(args: argparse.Namespace) -> int:
    result = _check_visual(
        Path(args.visual),
        Path(args.kit),
        args.revision or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _command_plan_schema(_: argparse.Namespace) -> int:
    result = {
        "schema_version": ARTICLE_PLAN_SCHEMA_VERSION,
        "required_top_level_fields": sorted(ARTICLE_PLAN_TOP_KEYS),
        "article_fields": sorted(ARTICLE_PLAN_ARTICLE_KEYS),
        "shot_fields": sorted(ARTICLE_PLAN_SHOT_KEYS),
        "structures": sorted(STRUCTURES["article-illustration"]),
        "visual_languages": ["default", "minimal-handdrawn"],
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


def _command_finalize_set(args: argparse.Namespace) -> int:
    result = _finalize_article_set(Path(args.kit), Path(args.plan))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _command_check_set(args: argparse.Namespace) -> int:
    result = _check_article_set(
        Path(args.set),
        Path(args.kit),
        args.revision or None,
    )
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
        choices=["minimal-handdrawn"],
    )
    style_parser.set_defaults(handler=_command_style_references)

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

    revision_prompt_parser = subparsers.add_parser(
        "revision-prompt",
        help="Build a scope-aware edit prompt with the previous visual as input.",
    )
    revision_prompt_parser.add_argument("kit")
    revision_prompt_parser.add_argument("--visual", required=True)
    revision_prompt_parser.add_argument("--brief", required=True)
    revision_prompt_parser.add_argument(
        "--change-scope", required=True, choices=sorted(REVISION_SCOPES)
    )
    revision_prompt_parser.add_argument("--note", required=True)
    revision_prompt_parser.set_defaults(handler=_command_revision_prompt)

    finalize_parser = subparsers.add_parser(
        "finalize", help="Archive an approved visual without changing identity."
    )
    finalize_parser.add_argument("kit")
    finalize_parser.add_argument("--brief", required=True)
    finalize_parser.add_argument("--image", required=True)
    finalize_parser.set_defaults(handler=_command_finalize)

    revise_parser = subparsers.add_parser(
        "revise", help="Archive a new non-destructive visual revision."
    )
    revise_parser.add_argument("kit")
    revise_parser.add_argument("--visual", required=True)
    revise_parser.add_argument("--brief", required=True)
    revise_parser.add_argument("--image", required=True)
    revise_parser.add_argument(
        "--change-scope", required=True, choices=sorted(REVISION_SCOPES)
    )
    revise_parser.add_argument("--note", required=True)
    revise_parser.set_defaults(handler=_command_revise)

    migrate_parser = subparsers.add_parser(
        "migrate-visual",
        help="Convert one legacy flat visual into the only supported versioned layout.",
    )
    migrate_parser.add_argument("visual")
    migrate_parser.add_argument("--kit", required=True)
    migrate_parser.set_defaults(handler=_command_migrate_visual)

    check_parser = subparsers.add_parser(
        "check", help="Verify one archived derivative visual."
    )
    check_parser.add_argument("visual")
    check_parser.add_argument("--kit", required=True)
    check_parser.add_argument("--revision", default="")
    check_parser.set_defaults(handler=_command_check)

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

    finalize_set_parser = subparsers.add_parser(
        "finalize-set",
        help="Archive an ordered article set from checked visual revisions.",
    )
    finalize_set_parser.add_argument("kit")
    finalize_set_parser.add_argument("--plan", required=True)
    finalize_set_parser.set_defaults(handler=_command_finalize_set)

    check_set_parser = subparsers.add_parser(
        "check-set", help="Verify an article set and every consumed visual revision."
    )
    check_set_parser.add_argument("set")
    check_set_parser.add_argument("--kit", required=True)
    check_set_parser.add_argument("--revision", default="")
    check_set_parser.set_defaults(handler=_command_check_set)
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
