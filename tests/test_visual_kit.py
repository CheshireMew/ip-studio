from __future__ import annotations

import copy
import sys
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
        brief["references"] = style_references()

        validated = visual_kit._validate_brief(copy.deepcopy(brief), ROOT)
        prompt = visual_kit._render_task(validated)

        self.assertTrue(
            visual_kit._uses_visual_language(validated, "minimal-handdrawn")
        )
        self.assertEqual(len(validated["references"]), 4)
        self.assertIn("极简手绘正文插图", prompt)
        self.assertIn("至少保留约 35% 纯白空白", prompt)
        self.assertIn("不要生成卡片墙", prompt)
        self.assertIn("第 5 张图片用于：minimal-handdrawn-style", prompt)
        self.assertNotIn("轻量概念图解与二次元插画结合", prompt)

    def test_default_article_contract_stays_available(self) -> None:
        validated = visual_kit._validate_brief(completed_brief(), ROOT)
        prompt = visual_kit._render_task(validated)

        self.assertFalse(
            visual_kit._uses_visual_language(validated, "minimal-handdrawn")
        )
        self.assertIn("轻量概念图解与二次元插画结合", prompt)
        self.assertNotIn("视觉语言已选择“极简手绘 IP”", prompt)

    def test_cover_and_explainer_have_dedicated_minimal_contracts(self) -> None:
        expected = {
            "cover": "横版极简手绘文章封面",
            "explainer": "极简手绘说明图",
        }
        for kind, marker in expected.items():
            with self.subTest(kind=kind):
                brief = completed_brief(kind)
                brief["references"] = style_references()
                validated = visual_kit._validate_brief(brief, ROOT)
                prompt = visual_kit._render_task(validated)

                self.assertIn(marker, prompt)
                self.assertIn("视觉语言已选择“极简手绘 IP”", prompt)
                self.assertNotIn("精致二次元插画结合", prompt)

    def test_one_style_reference_cannot_activate_the_language(self) -> None:
        brief = completed_brief()
        brief["references"] = style_references()[:1]

        with self.assertRaisesRegex(
            visual_kit.VisualError,
            "requires its complete built-in reference pack",
        ):
            visual_kit._validate_brief(brief, ROOT)

    def test_profile_visuals_reject_the_content_visual_language(self) -> None:
        brief = completed_brief("avatar")
        brief["references"] = style_references()[:2]

        with self.assertRaisesRegex(
            visual_kit.VisualError,
            "only available for: article-illustration, cover, explainer",
        ):
            visual_kit._validate_brief(brief, ROOT)


class OkxEditorialContractTests(unittest.TestCase):
    def test_manifest_returns_seven_examples_and_exact_logo(self) -> None:
        manifest = visual_kit._style_reference_manifest("okx-editorial")

        self.assertEqual(manifest["status"], "PASS")
        self.assertEqual(len(manifest["brief_references"]), 8)
        self.assertEqual(
            [item["role"] for item in manifest["brief_references"]].count(
                "okx-editorial-style"
            ),
            7,
        )
        logo = manifest["brief_references"][-1]
        self.assertEqual(logo["role"], "okx-logo-asset")
        self.assertEqual(Path(logo["path"]).name, "okx-mark-white.png")
        for reference in manifest["brief_references"]:
            self.assertTrue(Path(reference["path"]).is_file())
        self.assertTrue(Path(manifest["source_notice"]).is_file())
        self.assertTrue(Path(manifest["style_guide"]).is_file())

    def test_complete_pack_switches_prompt_without_copying_reference_copy(self) -> None:
        brief = completed_brief("explainer")
        brief["composition"]["aspect_ratio"] = "1:1"
        brief["brand"] = {
            "role": "core",
            "name": "OKX",
            "visual_cues": "黑白与霓虹黄绿色",
        }
        brief["references"] = style_references("okx-editorial")

        validated = visual_kit._validate_brief(copy.deepcopy(brief), ROOT)
        prompt = visual_kit._render_task(validated)

        self.assertTrue(
            visual_kit._uses_visual_language(validated, "okx-editorial")
        )
        self.assertEqual(validated["composition"]["aspect_ratio"], "1:1")
        self.assertIn("OKX Editorial", prompt)
        self.assertIn("#BBFF2F", prompt)
        self.assertIn("不能像白边贴纸或后期抠图", prompt)
        self.assertIn("第 9 张图片用于：okx-logo-asset", prompt)
        for copied_reference_text in ("AI CapEx", "MRVL", "618", "双币赢"):
            self.assertNotIn(copied_reference_text, prompt)

    def test_incomplete_pack_cannot_activate_the_language(self) -> None:
        brief = completed_brief()
        brief["references"] = style_references("okx-editorial")[:-1]

        with self.assertRaisesRegex(
            visual_kit.VisualError,
            "okx-editorial requires its complete built-in reference pack",
        ):
            visual_kit._validate_brief(brief, ROOT)

    def test_okx_language_rejects_avatar(self) -> None:
        brief = completed_brief("avatar")
        brief["references"] = style_references("okx-editorial")

        with self.assertRaisesRegex(
            visual_kit.VisualError,
            "okx-editorial is only available for",
        ):
            visual_kit._validate_brief(brief, ROOT)

    def test_article_plan_materializes_okx_pack(self) -> None:
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

        self.assertEqual(len(shot["references"]), 8)
        self.assertEqual(shot["references"][-1]["role"], "okx-logo-asset")


if __name__ == "__main__":
    unittest.main()
