from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import character_kit  # noqa: E402
import visual_kit  # noqa: E402


MASTER_IMAGE = (
    ROOT
    / "assets"
    / "visual-languages"
    / "minimal-handdrawn"
    / "examples"
    / "information-well.png"
)


def completed_profile() -> dict:
    profile = character_kit._draft_template("workflow-character", "流程角色", "zh-CN")
    profile["identity"] = {
        "purpose": "解释复杂内容",
        "audience": "普通读者",
        "traits": ["清楚", "可靠"],
        "desired_impression": "亲切而准确",
        "symbolic_core": "把复杂关系变成可见动作",
    }
    profile["anatomy"].update(
        {
            "form_category": "stylized-human",
            "species_or_archetype": "年轻的人类讲解员",
            "age_impression": "青年",
            "overall_build": "圆润紧凑",
            "proportion_system": "三头身",
            "silhouette": "圆头、短躯干和清楚的双臂",
        }
    )
    for key in character_kit.HEAD_KEYS:
        profile["anatomy"]["head"][key] = f"固定的{key}"
    for key in character_kit.BODY_KEYS:
        profile["anatomy"]["body"][key] = f"固定的{key}"
    profile["surface"] = {
        "base_covering": "干净的哑光皮肤与布料",
        "palette": [
            {
                "id": "navy",
                "name": "深蓝",
                "hex": "#1F2937",
                "role": "主色",
                "placement": "头发与外套",
                "coverage": "约六成",
            },
            {
                "id": "orange",
                "name": "橙色",
                "hex": "#E26D5A",
                "role": "强调色",
                "placement": "胸前徽记",
                "coverage": "约一成",
            },
        ],
        "markings": [],
        "materials": [
            {
                "id": "matte-cloth",
                "name": "哑光布",
                "areas": "外套和裤子",
                "appearance": "平整、无高光",
            }
        ],
    }
    profile["wardrobe"] = {
        "summary": "深蓝短外套",
        "layering_order": "身体、内搭、外套",
        "pieces": [],
    }
    profile["signature_elements"] = [
        {
            "name": "橙色方形徽记",
            "meaning": "把信息压成清楚结构",
            "geometry": "圆角方形",
            "relative_scale": "胸宽四分之一",
            "palette_ids": ["orange"],
            "material_ids": ["matte-cloth"],
            "attachment": "缝在外套胸口",
            "placement": "左胸",
            "front_view": "完整可见",
            "side_view": "随胸廓转折",
            "back_view": "不可见",
            "movement_behavior": "随外套一起移动",
        }
    ]
    profile["view_model"] = {
        "front": "双眼、徽记和外套开口完整可见",
        "side": "鼻尖、后脑和外套厚度保持三头身比例",
        "back": "后脑和外套背面没有新增图案",
        "occlusion_and_overlap": "手臂在躯干前方时仍保留徽记边界",
        "always_visible_landmarks": ["圆头轮廓", "深蓝外套"],
    }
    profile["rendering"] = {
        "style_family": "简洁二次元插画",
        "shape_language": "圆角几何",
        "linework": "稳定深色轮廓",
        "color_treatment": "有限纯色",
        "lighting_and_shading": "轻微单向阴影",
        "texture": "低纹理",
        "detail_density": "中低密度",
    }
    profile["consistency"] = {
        "fixed": ["$.anatomy", "$.surface", "$.signature_elements[0]"],
        "flexible": ["表情和临时动作"],
        "revision_required": ["$.anatomy.proportion_system"],
    }
    profile["provenance"] = {
        "decisions": [
            {
                "path": "$.identity.symbolic_core",
                "source": "user_confirmed",
                "note": "测试中代表用户已确认的身份结论",
            }
        ]
    }
    return profile


def completed_brief(visual_id: str) -> dict:
    brief = visual_kit._brief_template("article-illustration", visual_id, "zh-CN")
    brief["content"] = {
        "source_label": "文章",
        "source_text": "先识别问题。然后把复杂机制拆成动作。最后检查结果。",
    }
    brief["message"] = {
        "core_object": "复杂机制",
        "audience_gap": "读者看不见机制如何变化",
        "mechanism_or_change": "角色把机制拆成连续动作",
        "takeaway": "动作让关系可见",
    }
    brief["composition"].update(
        {
            "title": "让关系变成动作",
            "subtitle": "",
            "labels": ["机制", "动作"],
            "conclusion": "",
            "palette": ["#F4E8D0", "#1F2937", "#E26D5A"],
            "style_notes": "信息层级清楚，角色承担关系",
        }
    )
    brief["character_action"] = {
        "role": "讲解者",
        "action": "拆分并连接部件",
        "affected_object": "复杂机制",
        "visible_result": "机制变成三步动作",
    }
    brief["decisions"] = [
        {
            "path": "$.message",
            "source": "agent_inferred",
            "note": "由内容真源提炼",
        }
    ]
    return brief


def article_plan() -> dict:
    plan = visual_kit._article_plan_template("workflow-article", "zh-CN")
    plan["article"] = {
        "source_label": "完整测试文章",
        "source_text": "先识别问题。然后把复杂机制拆成动作。最后检查结果。",
    }
    plan["style_notes"] = "统一留白和线条，避免重复解释"
    plan["shots"] = []
    anchors = [
        ("article-problem", "先识别问题。", "问题识别", "local-scene"),
        ("article-mechanism", "然后把复杂机制拆成动作。", "机制拆解", "process"),
    ]
    for visual_id, excerpt, title, structure in anchors:
        brief = completed_brief(visual_id)
        plan["shots"].append(
            {
                "visual_id": visual_id,
                "placement_after": excerpt,
                "source_excerpt": excerpt,
                "message": brief["message"],
                "structure": structure,
                "character_action": brief["character_action"],
                "title": title,
                "subtitle": "",
                "labels": ["输入", "结果"],
                "conclusion": "",
                "decisions": brief["decisions"],
            }
        )
    return plan


class RepositoryWorkspaceTests(unittest.TestCase):
    def test_workspace_is_anchored_to_ip_studio_when_called_elsewhere(self) -> None:
        with tempfile.TemporaryDirectory() as foreign_workspace:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "character_kit.py"),
                    "workspace",
                    "--character-id",
                    "nyxie",
                ],
                cwd=foreign_workspace,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        result = json.loads(completed.stdout)
        output_root = ROOT / "ip-studio-output"
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(Path(result["repository_root"]), ROOT)
        self.assertEqual(Path(result["output_root"]), output_root)
        self.assertEqual(Path(result["character_kit"]), output_root / "nyxie")
        self.assertEqual(
            Path(result["work_area"]), output_root / "_work" / "nyxie"
        )

    def test_workspace_rejects_an_unsafe_character_id(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "character_kit.py"),
                "workspace",
                "--character-id",
                "../outside",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("character-id must be", completed.stderr)

    def test_locked_character_resolves_from_chinese_name_or_english_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary) / "ip-studio-output"
            kit = output_root / "nyxie"
            profile = completed_profile()
            profile["character_id"] = "nyxie"
            profile["display_name"] = "夜希"
            profile_path = Path(temporary) / "nyxie-profile.json"
            profile_path.write_bytes(character_kit._json_bytes(profile))
            character_kit._finalize(kit, profile_path, MASTER_IMAGE)

            with mock.patch.object(character_kit, "OUTPUT_ROOT", output_root):
                chinese = character_kit._resolve_character("夜希")
                english = character_kit._resolve_character("Nyxie")

        self.assertEqual(chinese["character_id"], "nyxie")
        self.assertEqual(english["character_kit"], str(kit.resolve()))

    def test_unknown_locked_character_fails_instead_of_inventing_a_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(
                character_kit,
                "OUTPUT_ROOT",
                Path(temporary) / "ip-studio-output",
            ):
                with self.assertRaisesRegex(
                    character_kit.ProfileError,
                    "locked character not found",
                ):
                    character_kit._resolve_character("不存在的角色")


class ProductionWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.kit = self.root / "kit"
        self.profile_path = self.root / "profile.json"
        self.profile_path.write_bytes(character_kit._json_bytes(completed_profile()))
        character_kit._finalize(self.kit, self.profile_path, MASTER_IMAGE)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_json(self, name: str, data: dict) -> Path:
        path = self.root / name
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def test_scene_prompt_uses_the_master_instead_of_dumping_the_profile(self) -> None:
        task = "用夜希的形象给这段文章配一幅 16:9 横版正文插图。"
        bundle = character_kit.build_prompt_bundle(self.kit, "scene", task)

        self.assertTrue(bundle["requires_user_confirmation"])
        self.assertIn("第 1 张图片是已批准的", bundle["prompt"])
        self.assertIn(task, bundle["prompt"])
        self.assertNotIn("受众", bundle["prompt"])
        self.assertNotIn("侧面", bundle["prompt"])
        self.assertNotIn("背面", bundle["prompt"])
        self.assertNotIn("一致性约束", bundle["prompt"])
        self.assertLess(len(bundle["prompt"]), 300)

    def test_master_prompt_rebuilds_an_established_identity(self) -> None:
        profile = completed_profile()
        profile["anatomy"]["proportion_system"] = "正常动漫比例，约七头身"
        profile_path = self._write_json("normal-anime-profile.json", profile)

        bundle = character_kit.build_prompt_bundle(profile_path, "master")

        self.assertTrue(bundle["requires_user_confirmation"])
        self.assertIn("已经确定的角色档案", bundle["prompt"])
        self.assertIn("不是从零设计", bundle["prompt"])
        self.assertIn("正式动漫角色主参考图", bundle["prompt"])
        self.assertIn("有张力姿态", bundle["prompt"])
        self.assertIn("明确重心", bundle["prompt"])
        self.assertIn("有表现力的表情", bundle["prompt"])
        self.assertIn("不使用Q版", bundle["prompt"])
        self.assertNotIn("中性站姿、干净浅色背景", bundle["prompt"])
        self.assertNotIn("正面或轻微三分之四视角", bundle["prompt"])

    def test_documented_creation_flow_approves_image_before_profile(self) -> None:
        skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        image_stage = skill_text.index("### 1. 先得到可判断的角色形象")
        profile_stage = skill_text.index("### 2. 从获批图片建立身份真源")

        self.assertLess(image_stage, profile_stage)
        self.assertIn("从零创建时不要先创建或填写 `character-profile.json`", skill_text)
        self.assertIn("只有用户认可第一张形象", skill_text)

    def test_character_design_preserves_source_art_anchors(self) -> None:
        skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        method_text = (ROOT / "references" / "character-system.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("已经形成的美术锚点", skill_text)
        self.assertIn("必须继承的认知资产", skill_text)
        self.assertIn("不为了显得原创而改变四肢、器官和人体连接方式", skill_text)
        self.assertIn("IP 角色首先是一套能够被反复看见、反复画出", method_text)
        self.assertIn("不因为常见而需要回避", method_text)
        self.assertIn("所有方向共享同一组固定美术锚点", method_text)
        self.assertNotIn("把设计压到一个主要轮廓特征", method_text)
        self.assertNotIn("每个方向必须改变角色形态", method_text)

    def test_documented_one_off_image_bypasses_profiles_and_prompt_expansion(self) -> None:
        skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("**一次性角色图**", skill_text)
        self.assertIn("不得创建工作区、角色档案、角色包、版本、历史或一致性测试", skill_text)
        self.assertIn("用户说明图片以后可能用于某个项目，不等于要求现在建立角色包", skill_text)
        self.assertIn("有参考图时由图片承担已经可见的角色外观", skill_text)
        self.assertIn("不把头脸、发型、身体、服装、配色、材质、标志物或视角结构重新翻译成文字", skill_text)
        self.assertIn("脚本返回的路径、角色编号、Schema、状态和其它内部字段不展示", skill_text)

    def test_static_prompt_returns_only_generation_inputs_without_derivative_writes(self) -> None:
        brief = completed_brief("direct-delivery")
        brief["prompt_text"] = "使用角色参考图，为文章生成一张 16:9 正文插图。"
        brief_path = self._write_json("direct-delivery.json", brief)
        command = [sys.executable, str(ROOT / "scripts" / "visual_kit.py")]
        derivatives = self.kit / "derivatives"

        self.assertFalse(derivatives.exists())
        completed = subprocess.run(
            [*command, "prompt", str(self.kit), "--brief", str(brief_path)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        result = json.loads(completed.stdout)

        self.assertEqual(
            set(result),
            {
                "status",
                "visual_id",
                "kind",
                "visual_language",
                "character_id",
                "character_revision",
                "requires_user_confirmation",
                "image_references",
                "prompt",
            },
        )
        self.assertEqual(result["prompt"], brief["prompt_text"])
        self.assertEqual(
            result["image_references"],
            [
                {
                    "index": 1,
                    "role": "approved-character-master",
                    "path": str((self.kit / "master" / "master-r001.png").resolve()),
                }
            ],
        )
        self.assertFalse(derivatives.exists())
        for archive_key in (
            "style_profile",
            "profile",
            "profile_sha256",
            "master_reference",
            "master_sha256",
            "prompt_sha256",
            "prompt_characters",
        ):
            self.assertNotIn(archive_key, result)

    def test_static_visual_cli_has_no_archive_revision_or_check_commands(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "visual_kit.py"), "--help"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        for command in (
            "revision-prompt",
            "finalize",
            "revise",
            "migrate-visual",
            "check",
            "finalize-set",
            "check-set",
        ):
            self.assertNotIn(command, completed.stdout)
        for command in ("prompt", "prompt-once", "materialize-plan"):
            self.assertIn(command, completed.stdout)

    def test_documented_static_edit_uses_previous_image_without_a_revision_chain(self) -> None:
        skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        method_text = (ROOT / "references" / "visual-production.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("不再增加“认可候选后归档”的第二轮确认", skill_text)
        self.assertIn("把上一张成图直接作为编辑输入", skill_text)
        self.assertIn("不创建 `r001`、`r002` 或父子修订记录", skill_text)
        self.assertIn("不保存输入副本、快照、哈希、视觉记录或静态图片版本", method_text)

    def test_okx_json_profile_feeds_prompt_without_archive_metadata_or_style_images(self) -> None:
        command = [sys.executable, str(ROOT / "scripts" / "visual_kit.py")]
        produced = subprocess.run(
            [*command, "style-profile", "okx-editorial"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        manifest = json.loads(produced.stdout)
        brief = completed_brief("okx-cli-chain")
        brief["visual_language"] = "okx-editorial"
        brief["brand"] = {
            "role": "core",
            "name": "OKX",
            "visual_cues": "黑白与霓虹黄绿色",
        }
        brief_path = self._write_json("okx-cli-visual.json", brief)

        consumed = subprocess.run(
            [*command, "prompt", str(self.kit), "--brief", str(brief_path)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        bundle = json.loads(consumed.stdout)

        self.assertEqual(len(bundle["image_references"]), 2)
        self.assertEqual(bundle["image_references"][0]["role"], "approved-character-master")
        self.assertIn("OKX 白色标记", bundle["image_references"][1]["role"])
        self.assertTrue(
            bundle["image_references"][1]["path"].endswith(
                "okx-mark-white.png"
            )
        )
        self.assertEqual(bundle["visual_language"], "okx-editorial")
        self.assertEqual(len(manifest["profile_sha256"]), 64)
        self.assertNotIn("style_profile", bundle)
        self.assertIn("OKX 品牌编辑视觉", bundle["prompt"])
        self.assertIn("这张图最值得让人看懂什么", bundle["prompt"])
        self.assertNotIn('"scene_families"', bundle["prompt"])
        self.assertTrue(bundle["requires_user_confirmation"])
        self.assertNotIn("okx-editorial-style", bundle["prompt"])

        self.assertFalse((self.kit / "derivatives").exists())

    def test_binance_profile_matches_okx_direct_generation_contract(self) -> None:
        command = [sys.executable, str(ROOT / "scripts" / "visual_kit.py")]
        produced = subprocess.run(
            [*command, "style-profile", "binance-editorial"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        manifest = json.loads(produced.stdout)
        brief = completed_brief("binance-cli-chain")
        brief["visual_language"] = "binance-editorial"
        brief["brand"] = {
            "role": "core",
            "name": "Binance",
            "visual_cues": "品牌黄、深黑与白色",
        }
        brief_path = self._write_json("binance-cli-visual.json", brief)

        consumed = subprocess.run(
            [*command, "prompt", str(self.kit), "--brief", str(brief_path)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        bundle = json.loads(consumed.stdout)

        self.assertEqual(len(bundle["image_references"]), 3)
        self.assertEqual(
            bundle["image_references"][0]["role"],
            "approved-character-master",
        )
        self.assertTrue(
            bundle["image_references"][1]["path"].endswith(
                "binance-mark-yellow.png"
            )
        )
        self.assertTrue(
            bundle["image_references"][2]["path"].endswith(
                "binance-mark-black.png"
            )
        )
        self.assertEqual(bundle["visual_language"], "binance-editorial")
        self.assertEqual(len(manifest["profile_sha256"]), 64)
        self.assertNotIn("style_profile", bundle)
        self.assertIn("币安品牌编辑视觉", bundle["prompt"])
        self.assertIn("不要机械地把原文全部塞进图片", bundle["prompt"])
        self.assertNotIn("#F0B90B", bundle["prompt"])
        self.assertTrue(bundle["requires_user_confirmation"])
        self.assertNotIn("binance-editorial-style", bundle["prompt"])

        self.assertFalse((self.kit / "derivatives").exists())

    def test_article_plan_materializes_ordered_briefs_without_set_archive(self) -> None:
        plan_path = self._write_json("article-plan.json", article_plan())
        briefs_dir = self.root / "article-briefs"
        materialized = visual_kit._materialize_article_plan(plan_path, briefs_dir)
        self.assertEqual(
            [Path(brief).stem.removeprefix("01-").removeprefix("02-") for brief in materialized["briefs"]],
            ["article-problem", "article-mechanism"],
        )
        self.assertEqual(materialized["shot_count"], 2)
        self.assertFalse((self.kit / "derivatives").exists())

    def test_calibration_requires_repeated_failure_and_expires_on_character_revision(self) -> None:
        with self.assertRaisesRegex(character_kit.ProfileError, "at least twice"):
            character_kit._calibration_job(
                self.kit, "hands-test", "hands", "抓握时手指漂移", 1
            )
        job = character_kit._calibration_job(
            self.kit, "hands-test", "hands", "抓握时手指漂移", 2
        )
        job_path = self._write_json("calibration-job.json", job)
        registered = character_kit._register_calibration(
            self.kit, job_path, MASTER_IMAGE, "已检查身份和手部结构"
        )
        self.assertTrue(registered["active"])
        self.assertEqual(
            len(character_kit._active_calibration_references(self.kit, "hands")["references"]),
            1,
        )

        next_profile = character_kit._author_profile_only(
            character_kit._read_current_profile(self.kit)
        )
        next_profile_path = self._write_json("profile-r2.json", next_profile)
        character_kit._finalize(self.kit, next_profile_path, MASTER_IMAGE)
        self.assertEqual(
            character_kit._active_calibration_references(self.kit, "hands")["references"],
            [],
        )

if __name__ == "__main__":
    unittest.main()
