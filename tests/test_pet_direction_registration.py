import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


ASSEMBLER = Path(__file__).resolve().parents[1] / "scripts" / "pet" / "assemble_extended_atlas.py"
VALIDATE_BLIND = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "pet"
    / "validate_direction_blind_verdicts.py"
)
MEASURE_CONTINUITY = (
    Path(__file__).resolve().parents[1] / "scripts" / "pet" / "measure_direction_continuity.py"
)


def make_strip(path: Path, *, pose_width: int) -> None:
    strip = Image.new("RGB", (2176, 724), "#FF00FF")
    draw = ImageDraw.Draw(strip)
    slot_width = strip.width // 8
    for index in range(8):
        left = index * slot_width + (slot_width - pose_width) // 2
        draw.rectangle((left, 400, left + pose_width - 1, 599), fill=(40 + index, 60, 90))
    strip.save(path)


class PetDirectionRegistrationTest(unittest.TestCase):
    def prepare_row_9(self, root: Path) -> tuple[Path, Path, Path, Path]:
        base = root / "base.png"
        neutral = root / "neutral.png"
        source = root / "row-9.png"
        registered = root / "row-9-registered.png"
        registration = root / "row-9-registration.json"

        Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(base)
        neutral_image = Image.new("RGBA", (192, 208), (0, 0, 0, 0))
        ImageDraw.Draw(neutral_image).rectangle((40, 18, 151, 197), fill="white")
        neutral_image.save(neutral)
        make_strip(source, pose_width=120)

        subprocess.run(
            [
                sys.executable,
                str(ASSEMBLER),
                "--base-atlas",
                str(base),
                "--look-row-9",
                str(source),
                "--neutral-cell",
                str(neutral),
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
        return base, neutral, registered, registration

    def test_final_assembly_keeps_approved_row_9_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            base, neutral, registered, registration = self.prepare_row_9(root)
            row_10 = root / "row-10.png"
            output = root / "extended.png"
            make_strip(row_10, pose_width=120)

            subprocess.run(
                [
                    sys.executable,
                    str(ASSEMBLER),
                    "--base-atlas",
                    str(base),
                    "--registered-row-9",
                    str(registered),
                    "--row-9-registration",
                    str(registration),
                    "--look-row-10",
                    str(row_10),
                    "--neutral-cell",
                    str(neutral),
                    "--chroma-key",
                    "#FF00FF",
                    "--output",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            with Image.open(registered) as approved, Image.open(output) as atlas:
                final_row_9 = atlas.crop((0, 9 * 208, 1536, 10 * 208))
                self.assertEqual(approved.convert("RGBA").tobytes(), final_row_9.tobytes())

    def test_row_10_that_cannot_fit_requires_resynthesis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            base, neutral, registered, registration = self.prepare_row_9(root)
            row_10 = root / "row-10-too-wide.png"
            output = root / "extended.png"
            make_strip(row_10, pose_width=230)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ASSEMBLER),
                    "--base-atlas",
                    str(base),
                    "--registered-row-9",
                    str(registered),
                    "--row-9-registration",
                    str(registration),
                    "--look-row-10",
                    str(row_10),
                    "--neutral-cell",
                    str(neutral),
                    "--chroma-key",
                    "#FF00FF",
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("resynthesize the complete row 10", completed.stderr)

    def test_cardinal_ambiguity_fails_but_intermediate_ambiguity_only_warns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
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

            results = {}
            for gate in ("hard", "review"):
                answer_key = root / f"answer-{gate}.json"
                output = root / f"result-{gate}.json"
                answer_key.write_text(
                    json.dumps(
                        {
                            "pairs": [
                                {
                                    "pair": "pair-1",
                                    "axis": "horizontal",
                                    "gate": gate,
                                    "A": {
                                        "expected_direction": "screen-right",
                                        "source_direction": "090" if gate == "hard" else "022.5",
                                    },
                                    "B": {
                                        "expected_direction": "screen-left",
                                        "source_direction": "270" if gate == "hard" else "337.5",
                                    },
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(VALIDATE_BLIND),
                        "--answer-key",
                        str(answer_key),
                        "--verdicts",
                        str(verdicts),
                        "--json-out",
                        str(output),
                    ],
                    capture_output=True,
                    text=True,
                )
                results[gate] = (completed.returncode, json.loads(output.read_text()))

        self.assertNotEqual(results["hard"][0], 0)
        self.assertFalse(results["hard"][1]["ok"])
        self.assertEqual(results["review"][0], 0)
        self.assertTrue(results["review"][1]["ok"])
        self.assertTrue(results["review"][1]["reviewRequired"])

    def test_continuity_measurement_reports_evidence_without_auto_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
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
                draw.rectangle((left, top, left + size, top + size), fill="white")
            atlas.save(atlas_path)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(MEASURE_CONTINUITY),
                    str(atlas_path),
                    "--json-out",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            result = json.loads(output.read_text())

        self.assertEqual(completed.returncode, 0)
        self.assertTrue(result["ok"])
        self.assertTrue(result["reviewRequired"])
        self.assertGreater(len(result["warnings"]), 0)


if __name__ == "__main__":
    unittest.main()
