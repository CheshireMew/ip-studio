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
RECORD_SCHEMA_VERSION = "1.0"
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
        }
    ]
    for index, reference in enumerate(brief["references"], start=2):
        path = Path(reference["path"]).resolve()
        image_references.append(
            {
                "index": index,
                "role": reference["role"],
                "path": str(path),
                "sha256": _sha256_file(path),
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


def _archive_final(
    kit: Path,
    brief_path: Path,
    image_path: Path,
) -> dict[str, Any]:
    original = _load_json(brief_path)
    bundle = build_visual_bundle(kit, original, brief_path.parent)
    brief = bundle["brief"]
    media_type, extension = _detect_image(image_path)

    destination = (
        kit.resolve()
        / "derivatives"
        / brief["kind"]
        / brief["visual_id"]
    )
    if destination.exists():
        raise VisualError(f"refusing to overwrite existing visual: {destination}")

    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    stage = parent / f".{brief['visual_id']}.{uuid.uuid4().hex}.staging"
    stage.mkdir(parents=False, exist_ok=False)

    archived_brief = copy.deepcopy(brief)
    archived_references: list[dict[str, Any]] = []
    inputs_dir = stage / "inputs"
    for index, reference in enumerate(brief["references"], start=2):
        source = Path(reference["path"])
        ref_media_type, ref_extension = _detect_image(source)
        archived_name = (
            f"{index:02d}-{_filename_token(reference['role'])}{ref_extension}"
        )
        archived_relative = Path("inputs") / archived_name
        inputs_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, stage / archived_relative)
        archived_brief["references"][index - 2]["path"] = str(
            archived_relative
        ).replace("\\", "/")
        archived_references.append(
            {
                "index": index,
                "role": reference["role"],
                "file": str(archived_relative).replace("\\", "/"),
                "sha256": _sha256_file(stage / archived_relative),
                "bytes": (stage / archived_relative).stat().st_size,
                "media_type": ref_media_type,
            }
        )

    brief_bytes = _json_bytes(archived_brief)
    (stage / "visual-brief.json").write_bytes(brief_bytes)
    profile_snapshot = Path(str(bundle["profile"])).read_bytes()
    (stage / "character-profile.snapshot.json").write_bytes(profile_snapshot)
    prompt_bytes = (str(bundle["prompt"]) + "\n").encode("utf-8")
    (stage / "generation-prompt.txt").write_bytes(prompt_bytes)
    output_name = f"final{extension}"
    shutil.copyfile(image_path, stage / output_name)
    output_hash = _sha256_file(stage / output_name)

    master_path = Path(str(bundle["master_reference"])).resolve()
    try:
        master_relative = str(master_path.relative_to(kit.resolve())).replace(
            "\\", "/"
        )
    except ValueError as error:
        raise VisualError("character master must stay inside the kit") from error

    record = {
        "record_schema_version": RECORD_SCHEMA_VERSION,
        "visual_id": brief["visual_id"],
        "kind": brief["kind"],
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
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
            "input_references": [
                {
                    "index": 1,
                    "role": "approved-character-master",
                    "file": master_relative,
                    "sha256": bundle["master_sha256"],
                },
                *archived_references,
            ],
        },
        "output": {
            "file": output_name,
            "sha256": output_hash,
            "bytes": (stage / output_name).stat().st_size,
            "media_type": media_type,
        },
    }
    (stage / "visual-record.json").write_bytes(_json_bytes(record))
    os.replace(stage, destination)
    return _check_visual(destination, kit.resolve())


def _check_visual(folder: Path, kit: Path) -> dict[str, Any]:
    folder = folder.resolve()
    kit = kit.resolve()
    if not folder.is_dir():
        raise VisualError(f"visual folder does not exist: {folder}")

    record = _load_json(folder / "visual-record.json")
    required_record = {
        "record_schema_version",
        "visual_id",
        "kind",
        "created_at",
        "character",
        "brief",
        "generation",
        "output",
    }
    _require_object(record, "$record", required_record)
    if record["record_schema_version"] != RECORD_SCHEMA_VERSION:
        _fail("$record.record_schema_version", f"must equal {RECORD_SCHEMA_VERSION}")

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
    brief_record = _require_object(
        record["brief"],
        "$record.brief",
        {"file", "sha256"},
    )
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
        kit,
        "scene",
        "验证角色包仍可读取；不生成图片。",
    )

    brief_path = _safe_relative(folder, brief_record["file"], "brief file")
    brief_bytes = brief_path.read_bytes()
    if _sha256_bytes(brief_bytes) != brief_record["sha256"]:
        raise VisualError("visual-brief.json SHA-256 mismatch")
    brief = _validate_brief(_load_json(brief_path), folder)
    if brief["visual_id"] != record["visual_id"]:
        raise VisualError("record and brief visual_id mismatch")
    if brief["kind"] != record["kind"]:
        raise VisualError("record and brief kind mismatch")
    if current_character["character_id"] != character_record["character_id"]:
        raise VisualError("record character_id does not match the current kit")

    snapshot_path = _safe_relative(
        folder,
        character_record["profile_snapshot"],
        "profile snapshot",
    )
    snapshot_bytes = snapshot_path.read_bytes()
    if (
        _sha256_bytes(snapshot_bytes)
        != character_record["profile_snapshot_sha256"]
    ):
        raise VisualError("character profile snapshot SHA-256 mismatch")
    snapshot = character_kit.validate_locked_profile(
        _load_json(snapshot_path)
    )
    if snapshot["character_id"] != character_record["character_id"]:
        raise VisualError("profile snapshot character_id mismatch")
    revision = snapshot["revision"]
    expected_revision = character_record["revision"]
    if f"r{revision:03d}" != expected_revision:
        raise VisualError("profile snapshot revision mismatch")
    try:
        author_profile = {
            key: snapshot[key] for key in character_kit.AUTHOR_KEY_ORDER
        }
    except KeyError as error:
        raise VisualError(
            f"profile snapshot is missing author field: {error.args[0]}"
        ) from error
    canonical_profile = json.dumps(
        author_profile,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if (
        _sha256_bytes(canonical_profile)
        != character_record["profile_sha256"]
    ):
        raise VisualError("profile snapshot canonical SHA-256 mismatch")

    master_path = _safe_relative(
        kit,
        character_record["master_reference"],
        "master reference",
    )
    master_media_type, _ = _detect_image(master_path)
    if snapshot["assets"]["master_reference"] != character_record[
        "master_reference"
    ]:
        raise VisualError("profile snapshot master reference mismatch")
    if snapshot["assets"]["sha256"] != character_record["master_sha256"]:
        raise VisualError("profile snapshot master SHA-256 mismatch")
    if snapshot["assets"]["bytes"] != master_path.stat().st_size:
        raise VisualError("profile snapshot master byte size mismatch")
    if snapshot["assets"]["media_type"] != master_media_type:
        raise VisualError("profile snapshot master media type mismatch")
    if _sha256_file(master_path) != character_record["master_sha256"]:
        raise VisualError("archived character master SHA-256 mismatch")

    prompt_path = _safe_relative(
        folder,
        generation_record["prompt_file"],
        "generation prompt",
    )
    prompt_bytes = prompt_path.read_bytes()
    prompt_hash = _sha256_bytes(prompt_bytes.rstrip(b"\r\n"))
    if prompt_hash != generation_record["prompt_sha256"]:
        raise VisualError("generation prompt SHA-256 mismatch")

    input_references = generation_record["input_references"]
    expected_count = 1 + len(brief["references"])
    if not isinstance(input_references, list) or len(
        input_references
    ) != expected_count:
        raise VisualError(
            f"record must contain {expected_count} input references"
        )
    for position, item in enumerate(input_references):
        expected_keys = (
            {"index", "role", "file", "sha256"}
            if position == 0
            else {
                "index",
                "role",
                "file",
                "sha256",
                "bytes",
                "media_type",
            }
        )
        item = _require_object(
            item,
            f"$record.generation.input_references[{position}]",
            expected_keys,
        )
        expected_index = position + 1
        if item["index"] != expected_index:
            raise VisualError(
                f"input reference index mismatch at position {position}"
            )
        if item["index"] == 1:
            candidate = master_path
            if item["role"] != "approved-character-master":
                raise VisualError("first input reference role mismatch")
        else:
            candidate = _safe_relative(folder, item["file"], "input reference")
            brief_reference = brief["references"][position - 1]
            if item["role"] != brief_reference["role"]:
                raise VisualError(
                    f"input reference role mismatch at index {item['index']}"
                )
            if candidate != Path(brief_reference["path"]).resolve():
                raise VisualError(
                    f"input reference path mismatch at index {item['index']}"
                )
        media_type, _ = _detect_image(candidate)
        if _sha256_file(candidate) != item["sha256"]:
            raise VisualError(
                f"input reference SHA-256 mismatch at index {item['index']}"
            )
        if item["index"] != 1:
            if candidate.stat().st_size != item["bytes"]:
                raise VisualError(
                    f"input reference byte size mismatch at index {item['index']}"
                )
            if media_type != item["media_type"]:
                raise VisualError(
                    f"input reference media type mismatch at index {item['index']}"
                )

    output = _safe_relative(folder, output_record["file"], "output image")
    media_type, _ = _detect_image(output)
    if media_type != output_record["media_type"]:
        raise VisualError("output media type mismatch")
    if output.stat().st_size != output_record["bytes"]:
        raise VisualError("output byte size mismatch")
    if _sha256_file(output) != output_record["sha256"]:
        raise VisualError("output SHA-256 mismatch")

    return {
        "status": "PASS",
        "visual": str(folder),
        "visual_id": record["visual_id"],
        "kind": record["kind"],
        "character_id": record["character"]["character_id"],
        "character_revision": record["character"]["revision"],
        "image": str(output),
        "record": str(folder / "visual-record.json"),
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


def _command_finalize(args: argparse.Namespace) -> int:
    result = _archive_final(
        Path(args.kit),
        Path(args.brief),
        Path(args.image),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _command_check(args: argparse.Namespace) -> int:
    result = _check_visual(Path(args.visual), Path(args.kit))
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

    finalize_parser = subparsers.add_parser(
        "finalize", help="Archive an approved visual without changing identity."
    )
    finalize_parser.add_argument("kit")
    finalize_parser.add_argument("--brief", required=True)
    finalize_parser.add_argument("--image", required=True)
    finalize_parser.set_defaults(handler=_command_finalize)

    check_parser = subparsers.add_parser(
        "check", help="Verify one archived derivative visual."
    )
    check_parser.add_argument("visual")
    check_parser.add_argument("--kit", required=True)
    check_parser.set_defaults(handler=_command_check)
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
