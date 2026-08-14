from __future__ import annotations

import copy
import json
import shutil
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

    def test_visual_revision_keeps_parent_and_uses_previous_image(self) -> None:
        brief_path = self._write_json("visual-r1.json", completed_brief("revision-test"))
        first = visual_kit._archive_final(self.kit, brief_path, MASTER_IMAGE)
        revised_brief = completed_brief("revision-test")
        revised_brief["composition"]["title"] = "只改这个标题"
        revised_path = self._write_json("visual-r2.json", revised_brief)

        with self.assertRaisesRegex(
            visual_kit.VisualError, "newly locked character revision"
        ):
            visual_kit._revision_bundle(
                self.kit,
                Path(first["visual"]),
                revised_brief,
                self.root,
                "character-revision",
                "错误地把局部修改声明成角色升版",
            )

        prompt_bundle, _ = visual_kit._revision_bundle(
            self.kit,
            Path(first["visual"]),
            revised_brief,
            self.root,
            "local-rendering",
            "删掉旧标题，其他不变",
        )
        second = visual_kit._revise_visual(
            self.kit,
            Path(first["visual"]),
            revised_path,
            MASTER_IMAGE,
            "local-rendering",
            "删掉旧标题，其他不变",
        )

        self.assertEqual(first["revision"], "r001")
        self.assertEqual(second["revision"], "r002")
        self.assertTrue(Path(first["visual"], "revisions", "r001", "final.png").is_file())
        self.assertEqual(prompt_bundle["image_references"][1]["role"], "previous-visual")
        record = json.loads(Path(second["record"]).read_text(encoding="utf-8"))
        self.assertEqual(record["revision"]["change_scope"], "local-rendering")
        self.assertEqual(record["generation"]["input_references"][1]["source"], "previous-visual")

    def test_cli_prompt_finalize_and_check_share_one_archive_contract(self) -> None:
        brief = completed_brief("cli-chain")
        brief["prompt_text"] = "使用角色参考图，为文章生成一张 16:9 正文插图。"
        brief_path = self._write_json("cli-visual.json", brief)
        command = [sys.executable, str(ROOT / "scripts" / "visual_kit.py")]
        prompt = subprocess.run(
            [*command, "prompt", str(self.kit), "--brief", str(brief_path)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        prompt_result = json.loads(prompt.stdout)
        self.assertEqual(prompt_result["image_references"][0]["role"], "approved-character-master")
        self.assertTrue(prompt_result["requires_user_confirmation"])
        self.assertEqual(prompt_result["prompt"], brief["prompt_text"])
        self.assertNotIn("读者看不见机制如何变化", prompt_result["prompt"])

        finalized = subprocess.run(
            [
                *command,
                "finalize",
                str(self.kit),
                "--brief",
                str(brief_path),
                "--image",
                str(MASTER_IMAGE),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        finalized_result = json.loads(finalized.stdout)
        checked = subprocess.run(
            [
                *command,
                "check",
                finalized_result["visual"],
                "--kit",
                str(self.kit),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        checked_result = json.loads(checked.stdout)
        self.assertEqual(checked_result["record"], finalized_result["record"])
        self.assertTrue(Path(checked_result["image"]).is_file())

    def test_okx_json_profile_feeds_prompt_and_archive_without_style_images(self) -> None:
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

        self.assertEqual(len(bundle["image_references"]), 1)
        self.assertEqual(bundle["image_references"][0]["role"], "approved-character-master")
        self.assertEqual(bundle["visual_language"], "okx-editorial")
        self.assertEqual(
            bundle["style_profile"]["sha256"],
            manifest["profile_sha256"],
        )
        self.assertIn("OKX Editorial", bundle["prompt"])
        self.assertNotIn('"scene_families"', bundle["prompt"])
        self.assertTrue(bundle["requires_user_confirmation"])
        self.assertNotIn("okx-editorial-style", bundle["prompt"])

        archived = visual_kit._archive_final(self.kit, brief_path, MASTER_IMAGE)
        checked = visual_kit._check_visual(Path(archived["visual"]), self.kit)
        record = json.loads(Path(checked["record"]).read_text(encoding="utf-8"))
        style_record = record["visual_language"]
        self.assertEqual(style_record["name"], "okx-editorial")
        self.assertEqual(len(style_record["profile_sha256"]), 64)
        self.assertTrue(
            (Path(checked["record"]).parent / style_record["profile_file"]).is_file()
        )

    def test_binance_profile_matches_okx_prompt_and_archive_chain(self) -> None:
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

        self.assertEqual(len(bundle["image_references"]), 1)
        self.assertEqual(
            bundle["image_references"][0]["role"],
            "approved-character-master",
        )
        self.assertEqual(bundle["visual_language"], "binance-editorial")
        self.assertEqual(
            bundle["style_profile"]["sha256"],
            manifest["profile_sha256"],
        )
        self.assertIn("Binance Editorial", bundle["prompt"])
        self.assertNotIn("#F0B90B", bundle["prompt"])
        self.assertTrue(bundle["requires_user_confirmation"])
        self.assertNotIn("binance-editorial-style", bundle["prompt"])

        archived = visual_kit._archive_final(self.kit, brief_path, MASTER_IMAGE)
        checked = visual_kit._check_visual(Path(archived["visual"]), self.kit)
        record = json.loads(Path(checked["record"]).read_text(encoding="utf-8"))
        style_record = record["visual_language"]
        self.assertEqual(style_record["name"], "binance-editorial")
        self.assertEqual(len(style_record["profile_sha256"]), 64)
        self.assertTrue(
            (Path(checked["record"]).parent / style_record["profile_file"]).is_file()
        )

    def test_article_plan_materializes_and_set_consumes_real_visuals(self) -> None:
        plan_path = self._write_json("article-plan.json", article_plan())
        briefs_dir = self.root / "article-briefs"
        materialized = visual_kit._materialize_article_plan(plan_path, briefs_dir)
        self.assertEqual(materialized["shot_count"], 2)
        for brief_name in materialized["briefs"]:
            visual_kit._archive_final(self.kit, Path(brief_name), MASTER_IMAGE)

        result = visual_kit._finalize_article_set(self.kit, plan_path)

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["shot_count"], 2)
        self.assertEqual(
            [Path(image).parent.parent.parent.name for image in result["images"]],
            ["article-problem", "article-mechanism"],
        )

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

    def test_legacy_visual_requires_explicit_migration_and_is_archived(self) -> None:
        brief_path = self._write_json("legacy-source.json", completed_brief("migration-test"))
        produced = visual_kit._archive_final(self.kit, brief_path, MASTER_IMAGE)
        legacy_root = self.root / "legacy-flat-visual"
        shutil.copytree(Path(produced["visual"]) / "revisions" / "r001", legacy_root)
        record_path = legacy_root / "visual-record.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["record_schema_version"] = visual_kit.LEGACY_RECORD_SCHEMA_VERSION
        record.pop("revision")
        record.pop("visual_language")
        legacy_inputs = []
        for item in record["generation"]["input_references"]:
            legacy = {
                key: item[key]
                for key in ("index", "role", "file", "sha256")
            }
            if item["index"] != 1:
                legacy.update(
                    {"bytes": item["bytes"], "media_type": item["media_type"]}
                )
            legacy_inputs.append(legacy)
        record["generation"]["input_references"] = legacy_inputs
        record_path.write_bytes(visual_kit._json_bytes(record))

        with self.assertRaisesRegex(visual_kit.VisualError, "migrate-visual"):
            visual_kit._check_visual(legacy_root, self.kit)
        migrated = visual_kit._migrate_visual(legacy_root, self.kit)

        self.assertEqual(migrated["revision"], "r001")
        self.assertTrue(Path(migrated["legacy_archive"]).is_dir())
        self.assertTrue((legacy_root / "current.json").is_file())


if __name__ == "__main__":
    unittest.main()
