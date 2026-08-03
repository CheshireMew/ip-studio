from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import visual_kit  # noqa: E402


def style_references() -> list[dict[str, str]]:
    return visual_kit._style_reference_manifest("minimal-handdrawn")[
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
            self.assertEqual(reference["role"], visual_kit.MINIMAL_HANDDRAWN_ROLE)
        self.assertTrue(Path(manifest["source_notice"]).is_file())

    def test_complete_style_pack_switches_the_render_contract(self) -> None:
        brief = completed_brief()
        brief["references"] = style_references()

        validated = visual_kit._validate_brief(copy.deepcopy(brief), ROOT)
        prompt = visual_kit._render_task(validated)

        self.assertTrue(visual_kit._uses_minimal_handdrawn(validated))
        self.assertEqual(len(validated["references"]), 4)
        self.assertIn("极简手绘正文插图", prompt)
        self.assertIn("至少保留约 35% 纯白空白", prompt)
        self.assertIn("不要生成卡片墙", prompt)
        self.assertIn("第 5 张图片用于：minimal-handdrawn-style", prompt)
        self.assertNotIn("轻量概念图解与二次元插画结合", prompt)

    def test_default_article_contract_stays_available(self) -> None:
        validated = visual_kit._validate_brief(completed_brief(), ROOT)
        prompt = visual_kit._render_task(validated)

        self.assertFalse(visual_kit._uses_minimal_handdrawn(validated))
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
            "requires at least two complete style references",
        ):
            visual_kit._validate_brief(brief, ROOT)

    def test_profile_visuals_reject_the_content_visual_language(self) -> None:
        brief = completed_brief("avatar")
        brief["references"] = style_references()[:2]

        with self.assertRaisesRegex(
            visual_kit.VisualError,
            "only available for cover, explainer, or article-illustration",
        ):
            visual_kit._validate_brief(brief, ROOT)


if __name__ == "__main__":
    unittest.main()
