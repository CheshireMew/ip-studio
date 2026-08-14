from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
IP_STUDIO_ROOT = ROOT / "skills" / "ip-studio"
PET_STUDIO_ROOT = ROOT / "skills" / "pet-studio"
sys.path.insert(0, str(PET_STUDIO_ROOT / "scripts"))
sys.path.insert(0, str(IP_STUDIO_ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import character_kit  # noqa: E402
import pet_kit  # noqa: E402
from pet import prepare_pet_run  # noqa: E402
from test_production_workflows import MASTER_IMAGE, completed_profile  # noqa: E402


class PetStudioPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.kit = self.root / "kit"
        profile = self.root / "profile.json"
        profile.write_bytes(character_kit._json_bytes(completed_profile()))
        character_kit._finalize(self.kit, profile, MASTER_IMAGE)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_default_workspace_is_owned_by_pet_studio_not_the_caller(self) -> None:
        destination = prepare_pet_run.default_output_dir("nyxie")

        self.assertTrue(destination.is_relative_to(PET_STUDIO_ROOT))
        self.assertEqual(
            destination.parent,
            PET_STUDIO_ROOT / "pet-studio-output" / "_work" / "codex-v2",
        )

    def test_codex_adapter_keeps_identity_lineage_confirmation_and_motion_contract(self) -> None:
        run = self.root / "pet-run"
        completed = subprocess.run(
            [
                sys.executable,
                str(PET_STUDIO_ROOT / "scripts" / "pet_kit.py"),
                "prepare",
                str(self.kit),
                "--adapter",
                "codex-v2",
                "--output-dir",
                str(run),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        result = json.loads(completed.stdout)
        request = json.loads((run / "pet_request.json").read_text(encoding="utf-8"))
        jobs = json.loads((run / "imagegen-jobs.json").read_text(encoding="utf-8"))["jobs"]
        contract = json.loads((run / "motion-contract.json").read_text(encoding="utf-8"))

        self.assertEqual(result["adapter"], "codex-v2")
        self.assertEqual(request["adapter"]["id"], "codex-v2")
        self.assertEqual(request["source_character"]["character_id"], "workflow-character")
        self.assertEqual(request["source_character"]["revision"], "r001")
        self.assertEqual(len(request["source_character"]["profile_sha256"]), 64)
        self.assertEqual(len(request["source_character"]["master_sha256"]), 64)
        self.assertTrue(all(job["requires_user_confirmation"] for job in jobs))
        self.assertEqual(contract["motion_id"], "codex-pet-v2")
        self.assertEqual(len(contract["clips"]), 25)
        self.assertEqual(len(contract["groups"]), 11)

    def test_generated_prompts_are_single_precise_handoffs(self) -> None:
        run = self.root / "prompt-run"
        subprocess.run(
            [
                sys.executable,
                str(PET_STUDIO_ROOT / "scripts" / "pet_kit.py"),
                "prepare",
                str(self.kit),
                "--output-dir",
                str(run),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        prompts = list((run / "prompts").rglob("*.md"))
        self.assertGreater(len(prompts), 10)
        for path in prompts:
            prompt = path.read_text(encoding="utf-8")
            self.assertLess(len(prompt), 1400, path)
            self.assertNotIn("PRE-RETURN CHECK", prompt)
            self.assertNotIn("HARD LAYOUT", prompt)
            self.assertNotIn("State requirements:", prompt)
        look_row = (run / "prompts" / "rows" / "look-row-9.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("000, 022.5, 045, 067.5, 090, 112.5, 135, 157.5", look_row)


class PetStudioDirectionQATests(unittest.TestCase):
    def _direction_strip(self, path: Path, height: int) -> None:
        strip = Image.new("RGB", (2176, 724), "#FF00FF")
        draw = ImageDraw.Draw(strip)
        slot_width = strip.width // 8
        for index in range(8):
            left = index * slot_width + 64
            draw.rectangle(
                (left, 650 - height, left + 140, 649),
                fill=(20 + index, 40, 80),
            )
        strip.save(path)

    def test_final_assembly_preserves_the_approved_first_direction_row(self) -> None:
        script = PET_STUDIO_ROOT / "scripts" / "pet" / "assemble_extended_atlas.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            atlas = root / "base.png"
            neutral_path = root / "neutral.png"
            row_9 = root / "row-9.png"
            row_10 = root / "row-10.png"
            registered = root / "registered.png"
            registration = root / "registration.json"
            output = root / "extended.png"
            Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(atlas)
            neutral = Image.new("RGBA", (192, 208), (0, 0, 0, 0))
            ImageDraw.Draw(neutral).rectangle((40, 18, 151, 197), fill="white")
            neutral.save(neutral_path)
            self._direction_strip(row_9, 500)
            self._direction_strip(row_10, 480)

            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--base-atlas",
                    str(atlas),
                    "--look-row-9",
                    str(row_9),
                    "--neutral-cell",
                    str(neutral_path),
                    "--chroma-key",
                    "#FF00FF",
                    "--registered-row-output",
                    str(registered),
                    "--registration-manifest-output",
                    str(registration),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--base-atlas",
                    str(atlas),
                    "--registered-row-9",
                    str(registered),
                    "--row-9-registration",
                    str(registration),
                    "--look-row-10",
                    str(row_10),
                    "--neutral-cell",
                    str(neutral_path),
                    "--chroma-key",
                    "#FF00FF",
                    "--output",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            with Image.open(registered) as approved, Image.open(output) as final:
                approved_bytes = approved.convert("RGBA").tobytes()
                final_bytes = final.crop((0, 9 * 208, 1536, 10 * 208)).convert("RGBA").tobytes()

        self.assertEqual(approved_bytes, final_bytes)

    def test_cardinal_ambiguity_is_a_hard_gate_but_intermediate_is_review(self) -> None:
        script = PET_STUDIO_ROOT / "scripts" / "pet" / "validate_direction_blind_verdicts.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            verdicts = root / "verdicts.json"
            verdicts.write_text(
                json.dumps(
                    {
                        "pairs": [
                            {"pair": "pair-1", "A": "ambiguous", "B": "ambiguous", "reason": "test"}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            results = []
            for gate in ("hard", "review"):
                answer = root / f"answer-{gate}.json"
                output = root / f"result-{gate}.json"
                answer.write_text(
                    json.dumps(
                        {
                            "pairs": [
                                {
                                    "pair": "pair-1",
                                    "axis": "horizontal",
                                    "gate": gate,
                                    "A": {"expected_direction": "screen-right", "source_direction": "090"},
                                    "B": {"expected_direction": "screen-left", "source_direction": "270"},
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(script),
                        "--answer-key",
                        str(answer),
                        "--verdicts",
                        str(verdicts),
                        "--json-out",
                        str(output),
                    ],
                    capture_output=True,
                    text=True,
                )
                results.append((completed.returncode, json.loads(output.read_text(encoding="utf-8"))))

        self.assertEqual(results[0][0], 1)
        self.assertFalse(results[0][1]["ok"])
        self.assertEqual(results[1][0], 0)
        self.assertTrue(results[1][1]["ok"])
        self.assertTrue(results[1][1]["reviewRequired"])

    def test_direction_sheet_uses_normal_size_pairs_and_marks_two_hard_gates(self) -> None:
        script = PET_STUDIO_ROOT / "scripts" / "pet" / "make_direction_blind_qa_sheet.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            atlas = root / "atlas.png"
            sheet = root / "blind.png"
            answer = root / "answer.json"
            Image.new("RGBA", (1536, 2288), (0, 0, 0, 0)).save(atlas)
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    str(atlas),
                    "--output",
                    str(sheet),
                    "--answer-key",
                    str(answer),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            with Image.open(sheet) as opened:
                self.assertEqual(opened.width, 384)
            pairs = json.loads(answer.read_text(encoding="utf-8"))["pairs"]

        self.assertEqual(len(pairs), 14)
        self.assertEqual([pair["gate"] for pair in pairs].count("hard"), 2)
        self.assertEqual([pair["gate"] for pair in pairs].count("review"), 12)

    def test_continuity_outlier_requests_review_without_becoming_a_fake_failure(self) -> None:
        script = PET_STUDIO_ROOT / "scripts" / "pet" / "measure_direction_continuity.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            atlas_path = root / "atlas.png"
            output = root / "continuity.json"
            atlas = Image.new("RGBA", (1536, 2288), (0, 0, 0, 0))
            draw = ImageDraw.Draw(atlas)
            for index in range(16):
                row = 9 + index // 8
                column = index % 8
                size = 120 if index == 4 else 50
                left = column * 192 + 20
                top = row * 208 + 20
                draw.rectangle((left, top, left + size, top + size), fill=(0, 0, 0, 255))
            atlas.save(atlas_path)
            subprocess.run(
                [sys.executable, str(script), str(atlas_path), "--json-out", str(output)],
                check=True,
                capture_output=True,
                text=True,
            )
            result = json.loads(output.read_text(encoding="utf-8"))

        self.assertTrue(result["ok"])
        self.assertTrue(result["reviewRequired"])
        self.assertGreater(len(result["warnings"]), 0)


class PetStudioInstallTests(unittest.TestCase):
    def test_install_replacement_backs_up_the_existing_pet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "run"
            package = run / "package" / "nyxie"
            package.mkdir(parents=True)
            (run / "pet-run-record.json").write_text("{}", encoding="utf-8")
            (package / "pet.json").write_text('{"id":"nyxie"}', encoding="utf-8")
            (package / "spritesheet.webp").write_bytes(b"new-pet")
            codex_home = root / "codex-home"
            installed = codex_home / "pets" / "nyxie"
            installed.mkdir(parents=True)
            (installed / "pet.json").write_text('{"id":"nyxie"}', encoding="utf-8")
            (installed / "spritesheet.webp").write_bytes(b"old-pet")
            final = {"package": str(package), "pet_id": "nyxie"}

            with mock.patch.object(pet_kit, "_check_final", return_value=final), mock.patch.dict(
                os.environ, {"CODEX_HOME": str(codex_home)}, clear=False
            ):
                with self.assertRaisesRegex(pet_kit.PetError, "--replace-installed"):
                    pet_kit._install(run, False)
                result = pet_kit._install(run, True)

            backups = list((codex_home / "pets" / ".pet-studio-backups" / "nyxie").iterdir())
            backup_bytes = (backups[0] / "spritesheet.webp").read_bytes()

        self.assertEqual(result["action"], "replaced-with-backup")
        self.assertEqual(len(backups), 1)
        self.assertEqual(backup_bytes, b"old-pet")


if __name__ == "__main__":
    unittest.main()
