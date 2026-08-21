from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import visual_kit  # noqa: E402


def style_references(language: str = "minimal-handdrawn") -> list[dict[str, str]]:
    return visual_kit._style_reference_manifest(language)[
        "brief_references"
    ]


def completed_brief(kind: str = "article-illustration") -> dict:
    brief = visual_kit._brief_template(kind, "minimal-language-test", "zh-CN")
    brief["content"] = {
        "source_label": "测试内容真源",
        "source_text": "把堆积的信息压缩成一个能执行的动作。",
    }
    brief["message"] = {
        "core_object": "信息",
        "audience_gap": "信息为什么没有变成行动",
        "mechanism_or_change": "角色把信息压成可执行对象",
        "takeaway": "简化后才能行动",
    }
    brief["composition"].update(
        {
            "title": "把信息压成行动",
            "subtitle": "",
            "labels": [],
            "conclusion": "",
            "palette": ["#111111", "#F28C28", "#D94B4B"],
            "style_notes": "保持克制",
        }
    )
    if kind == "explainer":
        brief["composition"]["labels"] = ["输入", "压缩", "行动"]
        brief["composition"]["conclusion"] = "简化后才能行动"
    brief["character_action"] = {
        "role": "执行者",
        "action": "推动压机",
        "affected_object": "堆积的信息纸张",
        "visible_result": "纸张变成一块行动砖",
    }
    brief["decisions"] = [
        {
            "path": "$.message",
            "source": "agent_inferred",
            "note": "从测试内容真源提炼",
        }
    ]
    return brief


class MinimalHanddrawnContractTests(unittest.TestCase):
    def test_manifest_returns_real_absolute_style_inputs(self) -> None:
        manifest = visual_kit._style_reference_manifest("minimal-handdrawn")

        self.assertEqual(manifest["status"], "PASS")
        self.assertEqual(len(manifest["brief_references"]), 4)
        for reference in manifest["brief_references"]:
            path = Path(reference["path"])
            self.assertTrue(path.is_absolute())
            self.assertTrue(path.is_file())
            self.assertEqual(reference["role"], "minimal-handdrawn-style")
        self.assertTrue(Path(manifest["source_notice"]).is_file())

    def test_complete_style_pack_switches_the_render_contract(self) -> None:
        brief = completed_brief()
        brief["visual_language"] = "minimal-handdrawn"
        brief["references"] = style_references()

        validated = visual_kit._validate_brief(copy.deepcopy(brief), ROOT)
        prompt = visual_kit._render_task(validated)

        self.assertTrue(
            visual_kit._uses_visual_language(validated, "minimal-handdrawn")
        )
        self.assertEqual(len(validated["references"]), 4)
        self.assertIn("用户选择的视觉风格：极简手绘 IP", prompt)
        self.assertIn("第 5 张图片用于：minimal-handdrawn-style", prompt)
        self.assertNotIn("轻量概念图解与二次元插画结合", prompt)
        self.assertNotIn("35%", prompt)

    def test_default_article_contract_stays_available(self) -> None:
        validated = visual_kit._validate_brief(completed_brief(), ROOT)
        prompt = visual_kit._render_task(validated)

        self.assertFalse(
            visual_kit._uses_visual_language(validated, "minimal-handdrawn")
        )
        self.assertIn("16:9 正文插图", prompt)
        self.assertNotIn("轻量概念图解与二次元插画结合", prompt)
        self.assertNotIn("推动压机", prompt)

    def test_cover_and_explainer_have_dedicated_minimal_contracts(self) -> None:
        expected = {"cover": "5:2 文章封面", "explainer": "4:5 说明图"}
        for kind, marker in expected.items():
            with self.subTest(kind=kind):
                brief = completed_brief(kind)
                brief["visual_language"] = "minimal-handdrawn"
                brief["references"] = style_references()
                validated = visual_kit._validate_brief(brief, ROOT)
                prompt = visual_kit._render_task(validated)

                self.assertIn(marker, prompt)
                self.assertIn("用户选择的视觉风格：极简手绘 IP", prompt)
                self.assertNotIn("精致二次元插画结合", prompt)

    def test_one_style_reference_cannot_activate_the_language(self) -> None:
        brief = completed_brief()
        brief["visual_language"] = "minimal-handdrawn"
        brief["references"] = style_references()[:1]

        with self.assertRaisesRegex(
            visual_kit.VisualError,
            "requires its complete built-in reference pack",
        ):
            visual_kit._validate_brief(brief, ROOT)

    def test_profile_visuals_reject_the_content_visual_language(self) -> None:
        brief = completed_brief("avatar")
        brief["visual_language"] = "minimal-handdrawn"
        brief["references"] = style_references()[:2]

        with self.assertRaisesRegex(
            visual_kit.VisualError,
            "only available for: article-illustration, cover, explainer",
        ):
            visual_kit._validate_brief(brief, ROOT)


class PromptHygieneTests(unittest.TestCase):
    def test_prompt_text_is_the_exact_generation_prompt(self) -> None:
        brief = visual_kit._brief_template(
            "article-illustration", "exact-prompt", "zh-CN"
        )
        brief["prompt_text"] = "使用角色参考图，为这段内容生成一张 16:9 插图。"

        validated = visual_kit._validate_brief(brief, ROOT)
        prompt = visual_kit._render_task(validated)

        self.assertEqual(prompt, brief["prompt_text"])
        self.assertEqual(validated["content"]["source_label"], "")
        self.assertEqual(validated["content"]["source_text"], "")

    def test_legacy_brief_fallback_uses_only_material_and_output(self) -> None:
        validated = visual_kit._validate_brief(completed_brief(), ROOT)
        prompt = visual_kit._render_task(validated)

        self.assertIn("测试内容真源", prompt)
        self.assertIn("把堆积的信息压缩成一个能执行的动作。", prompt)
        self.assertNotIn("信息为什么没有变成行动", prompt)
        self.assertNotIn("推动压机", prompt)
        self.assertNotIn("保持克制", prompt)

    def test_default_cover_uses_the_template_and_selected_content(self) -> None:
        brief = completed_brief("cover")
        brief["composition"]["aspect_ratio"] = "16:9"
        brief["composition"]["title"] = "这不是预先规定的标题"
        brief["content"]["source_text"] = (
            "PuppetLoom 把分层角色素材变成可验证、可校准的动态角色。\n\n"
        )

        validated = visual_kit._validate_brief(brief, ROOT)
        prompt = visual_kit._render_task(validated)

        self.assertIn("直接生成一张 16:9 横版二次元封面图", prompt)
        self.assertIn("自动提炼一个包含核心对象与关键变化的主标题", prompt)
        self.assertIn("完成判断后直接生成最终封面，不输出分析过程", prompt)
        self.assertIn(brief["content"]["source_text"], prompt)
        self.assertNotIn(brief["composition"]["title"], prompt)
        self.assertNotIn(brief["character_action"]["action"], prompt)
        self.assertNotIn("为页面标题保留", prompt)
        self.assertNotIn("不要生成任何文字", prompt)

    def test_every_visual_kind_accepts_any_positive_integer_ratio(self) -> None:
        for kind in sorted(visual_kit.KINDS):
            with self.subTest(kind=kind):
                brief = completed_brief(kind)
                brief["composition"]["aspect_ratio"] = "37:11"
                validated = visual_kit._validate_brief(brief, ROOT)
                self.assertEqual(
                    validated["composition"]["aspect_ratio"], "37:11"
                )

    def test_one_off_cover_uses_supplied_character_without_a_kit(self) -> None:
        reference = (
            ROOT
            / "assets"
            / "visual-languages"
            / "okx-editorial"
            / "logos"
            / "okx-mark-white.png"
        )
        brief = completed_brief("cover")
        brief["composition"]["aspect_ratio"] = "16:9"

        bundle = visual_kit.build_one_off_visual_bundle(
            reference,
            brief,
            ROOT,
        )

        self.assertEqual(bundle["mode"], "one-off")
        self.assertEqual(bundle["image_references"][0]["path"], str(reference))
        self.assertEqual(
            bundle["image_references"][0]["role"],
            "provided-character-reference",
        )
        self.assertIn("16:9 横版二次元封面图", bundle["prompt"])

    def test_prompt_once_cli_returns_the_same_one_off_contract(self) -> None:
        reference = (
            ROOT
            / "assets"
            / "visual-languages"
            / "okx-editorial"
            / "logos"
            / "okx-mark-white.png"
        )
        brief = completed_brief("cover")
        brief["composition"]["aspect_ratio"] = "16:9"
        with tempfile.TemporaryDirectory() as directory:
            brief_path = Path(directory) / "cover.json"
            brief_path.write_text(
                json.dumps(brief, ensure_ascii=False),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "visual_kit.py"),
                    "prompt-once",
                    str(reference),
                    "--brief",
                    str(brief_path),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["mode"], "one-off")
        self.assertEqual(payload["image_references"][0]["path"], str(reference))
        self.assertIn("16:9 横版二次元封面图", payload["prompt"])

    def test_schema_reports_defaults_without_ratio_restrictions(self) -> None:
        schema = visual_kit._schema()

        self.assertFalse(schema["aspect_ratio"]["restricted"])
        self.assertNotIn("archive_contract", schema)
        self.assertEqual(schema["aspect_ratio"]["defaults"]["cover"], "5:2")
        self.assertNotIn("allowed_ratios", schema)


class OkxEditorialContractTests(unittest.TestCase):
    def test_manifest_returns_valid_json_profile_without_image_inputs(self) -> None:
        manifest = visual_kit._style_profile_manifest("okx-editorial")

        self.assertEqual(manifest["status"], "PASS")
        self.assertNotIn("brief_references", manifest)
        self.assertEqual(manifest["profile"]["visual_language"], "okx-editorial")
        self.assertIn(
            "OKX 品牌编辑视觉",
            manifest["profile"]["generation_text"],
        )
        self.assertEqual(
            manifest["profile"]["prompt"]["palette"][-1]["hex"],
            "#BBFF2F",
        )
        self.assertTrue(Path(manifest["profile_path"]).is_file())
        self.assertEqual(len(manifest["profile_sha256"]), 64)
        self.assertTrue(Path(manifest["source_notice"]).is_file())
        self.assertTrue(Path(manifest["style_guide"]).is_file())
        provenance = ROOT / "assets" / "visual-languages" / "okx-editorial"
        self.assertEqual(len(list((provenance / "examples").glob("*.png"))), 7)
        self.assertTrue((provenance / "logos" / "okx-mark-white.png").is_file())

    def test_json_profile_switches_prompt_without_style_images(self) -> None:
        brief = completed_brief("explainer")
        brief["composition"]["aspect_ratio"] = "1:1"
        brief["visual_language"] = "okx-editorial"
        brief["brand"] = {
            "role": "core",
            "name": "OKX",
            "visual_cues": "黑白与霓虹黄绿色",
        }

        validated = visual_kit._validate_brief(copy.deepcopy(brief), ROOT)
        prompt = visual_kit._render_task(validated)

        self.assertTrue(
            visual_kit._uses_visual_language(validated, "okx-editorial")
        )
        self.assertEqual(validated["composition"]["aspect_ratio"], "1:1")
        self.assertEqual(validated["references"], [])
        self.assertIn("OKX 品牌编辑视觉", prompt)
        self.assertIn("第 2 张图片用于：默认使用的 OKX 白色标记", prompt)
        self.assertIn("这张图最值得让人看懂什么", prompt)
        self.assertIn("哪些信息必须保留、哪些可以省略", prompt)
        self.assertIn("什么版式最适合表达", prompt)
        self.assertNotIn("#BBFF2F", prompt)
        self.assertNotIn('"scene_families"', prompt)
        self.assertNotIn("不能出现白边、毛边、漂浮感或独立清晰度", prompt)
        for copied_reference_text in ("AI CapEx", "MRVL", "618", "双币赢"):
            self.assertNotIn(copied_reference_text, prompt)

    def test_okx_profile_does_not_require_style_references(self) -> None:
        brief = completed_brief()
        brief["visual_language"] = "okx-editorial"

        validated = visual_kit._validate_brief(brief, ROOT)

        self.assertEqual(validated["references"], [])
        self.assertEqual(validated["visual_language"], "okx-editorial")

    def test_okx_language_rejects_avatar(self) -> None:
        brief = completed_brief("avatar")
        brief["visual_language"] = "okx-editorial"

        with self.assertRaisesRegex(
            visual_kit.VisualError,
            "okx-editorial is only available for",
        ):
            visual_kit._validate_brief(brief, ROOT)

    def test_article_plan_materializes_okx_profile_without_references(self) -> None:
        plan = visual_kit._article_plan_template("okx-plan", "zh-CN")
        plan["article"] = {
            "source_label": "测试文章",
            "source_text": "资金进入系统后开始流动。",
        }
        plan["brand"] = {
            "role": "core",
            "name": "OKX",
            "visual_cues": "黑白与霓虹黄绿色",
        }
        plan["visual_language"] = "okx-editorial"
        plan["style_notes"] = "只使用一个视觉中心"
        brief = completed_brief()
        plan["shots"] = [
            {
                "visual_id": "okx-flow",
                "placement_after": "资金进入系统后开始流动。",
                "source_excerpt": "资金进入系统后开始流动。",
                "message": brief["message"],
                "structure": "process",
                "character_action": brief["character_action"],
                "title": "资金开始流动",
                "subtitle": "",
                "labels": ["进入", "使用"],
                "conclusion": "",
                "decisions": brief["decisions"],
            }
        ]

        validated = visual_kit._validate_article_plan(plan)
        shot = visual_kit._shot_brief(validated, validated["shots"][0])

        self.assertEqual(shot["visual_language"], "okx-editorial")
        self.assertEqual(shot["references"], [])


class BinanceEditorialContractTests(unittest.TestCase):
    def test_manifest_returns_profile_provenance_and_contrast_marks(self) -> None:
        manifest = visual_kit._style_profile_manifest("binance-editorial")

        self.assertEqual(manifest["status"], "PASS")
        self.assertNotIn("brief_references", manifest)
        self.assertEqual(
            manifest["profile"]["visual_language"],
            "binance-editorial",
        )
        self.assertIn(
            "币安品牌编辑视觉",
            manifest["profile"]["generation_text"],
        )
        self.assertEqual(
            manifest["profile"]["prompt"]["palette"][0]["hex"],
            "#F0B90B",
        )
        self.assertEqual(len(manifest["profile_sha256"]), 64)
        self.assertTrue(Path(manifest["profile_path"]).is_file())
        self.assertTrue(Path(manifest["source_notice"]).is_file())
        self.assertTrue(Path(manifest["style_guide"]).is_file())
        provenance = ROOT / "assets" / "visual-languages" / "binance-editorial"
        self.assertEqual(len(list((provenance / "examples").glob("*.png"))), 5)
        self.assertTrue(
            (provenance / "logos" / "binance-mark-yellow.png").is_file()
        )
        self.assertTrue(
            (provenance / "logos" / "binance-mark-black.png").is_file()
        )

    def test_json_profile_compiles_without_loading_source_examples(self) -> None:
        brief = completed_brief("explainer")
        brief["composition"]["aspect_ratio"] = "1:1"
        brief["visual_language"] = "binance-editorial"
        brief["brand"] = {
            "role": "core",
            "name": "Binance",
            "visual_cues": "品牌黄、深黑与白色",
        }

        validated = visual_kit._validate_brief(copy.deepcopy(brief), ROOT)
        prompt = visual_kit._render_task(validated)

        self.assertTrue(
            visual_kit._uses_visual_language(validated, "binance-editorial")
        )
        self.assertEqual(validated["references"], [])
        self.assertIn("币安品牌编辑视觉", prompt)
        self.assertIn("第 2 张图片用于：适用于深色背景的 Binance 黄色标记", prompt)
        self.assertIn("第 3 张图片用于：适用于黄色或浅色背景的 Binance 黑色标记", prompt)
        self.assertIn("这张图最值得让人看懂什么", prompt)
        self.assertIn("不要机械地把原文全部塞进图片", prompt)
        self.assertNotIn("#F0B90B", prompt)
        self.assertNotIn('"scene_families"', prompt)
        self.assertNotIn("没有真实资料时不虚构产品截图", prompt)
        for copied_reference_text in (
            "UNITAS",
            "网球套装",
            "服务费直降",
            "代币化股票",
            "WiseInvest",
        ):
            self.assertNotIn(copied_reference_text, prompt)

    def test_registered_kinds_match_profile_and_avatar_is_rejected(self) -> None:
        for kind in (
            "profile-banner",
            "profile-card",
            "cover",
            "explainer",
            "article-illustration",
        ):
            with self.subTest(kind=kind):
                brief = completed_brief(kind)
                brief["visual_language"] = "binance-editorial"
                validated = visual_kit._validate_brief(brief, ROOT)
                self.assertEqual(validated["visual_language"], "binance-editorial")

        avatar = completed_brief("avatar")
        avatar["visual_language"] = "binance-editorial"
        with self.assertRaisesRegex(
            visual_kit.VisualError,
            "binance-editorial is only available for",
        ):
            visual_kit._validate_brief(avatar, ROOT)


if __name__ == "__main__":
    unittest.main()
