from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import character_kit  # noqa: E402
import motion_kit  # noqa: E402
from pet import prepare_pet_run  # noqa: E402

from test_production_workflows import MASTER_IMAGE, completed_profile  # noqa: E402


class RepositoryOwnedPetWorkspaceTests(unittest.TestCase):
    def test_internal_pet_preparer_does_not_use_the_callers_cwd(self) -> None:
        destination = prepare_pet_run.default_output_dir("nyxie")

        self.assertTrue(destination.is_relative_to(ROOT / "ip-studio-output"))
        self.assertEqual(
            destination.parent,
            ROOT / "ip-studio-output" / "_work" / "codex-pet",
        )


def clip(
    clip_id: str,
    state: str,
    direction: str,
    kind: str,
    frames: int,
    *,
    event_frame: int | None = None,
) -> dict:
    events = []
    if event_frame is not None:
        events.append(
            {
                "id": "apply-effect",
                "frame": event_frame,
                "meaning": "the runtime applies the gameplay result on contact",
            }
        )
    return {
        "id": clip_id,
        "state": state,
        "direction": direction,
        "kind": kind,
        "frame_count": frames,
        "durations_ms": [120] * frames,
        "semantic": f"visible {state} facing {direction}",
        "effect_events": events,
    }


def group(group_id: str, clip_ids: list[str], frames: int) -> dict:
    return {
        "id": group_id,
        "rows": len(clip_ids),
        "columns": frames,
        "registration": "bottom-center",
        "slot_detection": "equal-grid",
        "cells": [
            {"row": row, "column": frame, "clip_id": clip_id, "frame": frame}
            for row, clip_id in enumerate(clip_ids)
            for frame in range(frames)
        ],
    }


def contract(
    motion_id: str,
    actor_role: str,
    clips: list[dict],
    groups: list[dict],
    *,
    surface: str = "top-down game world",
    direction_source: str = "dominant movement input",
) -> dict:
    return {
        "schema_version": motion_kit.SCHEMA_VERSION,
        "motion_id": motion_id,
        "display_name": f"{motion_id} motion",
        "target": {
            "surface": surface,
            "runtime": "Godot 4 test runtime",
            "actor_role": actor_role,
            "camera": "top-down oblique" if "game" in surface else "front-facing UI",
            "state_source": "real controller state",
            "direction_source": direction_source,
            "consumer": "runtime animation consumer",
            "observable_result": "the requested state appears on the character",
        },
        "canvas": {
            "cell_width": 96,
            "cell_height": 96,
            "anchor_x": 48,
            "anchor_y": 84,
            "sprite_bounds_width": 76,
            "sprite_bounds_height": 72,
            "chroma_key": "#FF00FF",
            "runtime_format": "transparent PNG atlas and frames",
            "preview_formats": ["apng", "lossless-webp"],
        },
        "clips": clips,
        "groups": groups,
    }


class MotionWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.kit = self.root / "kit"
        profile = self.root / "profile.json"
        profile.write_bytes(character_kit._json_bytes(completed_profile()))
        character_kit._finalize(self.kit, profile, MASTER_IMAGE)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_contract(self, name: str, value: dict) -> Path:
        path = self.root / f"{name}.json"
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _sheet(self, group_value: dict, name: str, chroma: bool = False) -> Path:
        cell_size = 120
        background = (255, 0, 255, 255) if chroma else (0, 0, 0, 0)
        image = Image.new(
            "RGBA",
            (group_value["columns"] * cell_size, group_value["rows"] * cell_size),
            background,
        )
        draw = ImageDraw.Draw(image)
        for cell in group_value["cells"]:
            left = cell["column"] * cell_size
            top = cell["row"] * cell_size
            shift = (cell["frame"] % 2) * 3
            draw.ellipse(
                (left + 37 + shift, top + 20, left + 83 + shift, top + 82),
                fill=(32 + cell["row"] * 20, 90, 180, 255),
                outline=(15, 30, 60, 255),
                width=3,
            )
            draw.rectangle(
                (left + 50 + shift, top + 78, left + 70 + shift, top + 104),
                fill=(225, 180, 90, 255),
            )
        path = self.root / f"{name}.png"
        image.save(path)
        return path

    def _complete_run(self, value: dict, name: str, chroma: bool = False) -> tuple[Path, dict]:
        contract_path = self._write_contract(name, value)
        run = self.root / f"{name}-run"
        motion_kit._prepare(self.kit, contract_path, run)
        for group_value in value["groups"]:
            motion_kit._accept_sheet(
                run,
                group_value["id"],
                self._sheet(group_value, f"{name}-{group_value['id']}", chroma),
                "same character, complete grid, stable scale and readable state",
            )
        finalized = motion_kit._finalize(run)
        return run, finalized

    def test_player_motion_keeps_direction_clips_and_gameplay_effect_frame(self) -> None:
        directions = ["down", "left", "right", "up"]
        idle_ids = [f"idle-{direction}" for direction in directions]
        walk_ids = [f"walk-{direction}" for direction in directions]
        clips = [clip(item, "idle", item[5:], "static", 1) for item in idle_ids]
        clips += [clip(item, "walk", item[5:], "loop", 2) for item in walk_ids]
        clips.append(
            clip("hoe-down", "hoe", "down", "oneshot", 4, event_frame=2)
        )
        groups = [
            group("idle-directions", idle_ids, 1),
            group("walk-directions", walk_ids, 2),
            group("hoe-down-sheet", ["hoe-down"], 4),
        ]
        value = contract("player-world", "player-controlled", clips, groups)

        run, finalized = self._complete_run(value, "player")

        self.assertEqual(finalized["clip_count"], 9)
        checked = motion_kit._check(run, "final")
        self.assertEqual(checked["stage"], "final")
        manifest = json.loads(
            (Path(finalized["package"]) / "motion-manifest.json").read_text(encoding="utf-8")
        )
        hoe = next(item for item in manifest["clips"] if item["id"] == "hoe-down")
        self.assertEqual(hoe["effect_events"][0]["frame"], 2)
        self.assertTrue(all(Path(finalized["package"], frame["path"]).is_file() for frame in hoe["frames"]))

    def test_scheduled_npc_contract_does_not_invent_animation(self) -> None:
        directions = ["down", "left", "right", "up"]
        clip_ids = [f"pose-{direction}" for direction in directions]
        value = contract(
            "scheduled-npc",
            "scheduled-npc",
            [clip(item, "pose", item[5:], "static", 1) for item in clip_ids],
            [group("direction-poses", clip_ids, 1)],
        )
        run = self.root / "npc-run"
        motion_kit._prepare(self.kit, self._write_contract("npc", value), run)

        stored = json.loads((run / "motion-contract.json").read_text(encoding="utf-8"))
        job_manifest = json.loads(
            (run / "imagegen-jobs.json").read_text(encoding="utf-8")
        )
        self.assertEqual({item["kind"] for item in stored["clips"]}, {"static"})
        self.assertEqual(
            job_manifest["jobs"][0]["id"],
            "direction-poses",
        )
        self.assertTrue(
            all(job["requires_user_confirmation"] for job in job_manifest["jobs"])
        )

    def test_front_facing_ui_motion_needs_no_direction_family(self) -> None:
        clip_ids = ["idle", "listening", "success"]
        ui_group = group("ui-state-sheet", clip_ids, 2)
        ui_group["slot_detection"] = "content-projection"
        value = contract(
            "ui-assistant",
            "stateful-interface-character",
            [clip(item, item, "none", "loop", 2) for item in clip_ids],
            [ui_group],
            surface="application interface character",
            direction_source="none",
        )

        _run, finalized = self._complete_run(value, "ui", chroma=True)

        manifest = json.loads(
            (Path(finalized["package"]) / "motion-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual({item["direction"] for item in manifest["clips"]}, {"none"})
        self.assertEqual(len(manifest["atlases"]), 1)

    def test_codex_pet_prepare_materializes_the_shared_motion_contract(self) -> None:
        run = self.root / "pet-run"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "pet_kit.py"),
            "prepare",
            str(self.kit),
            "--output-dir",
            str(run),
        ]
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        prepared = json.loads(completed.stdout)
        normalized = motion_kit.validate_contract(
            json.loads((run / "motion-contract.json").read_text(encoding="utf-8"))
        )

        self.assertEqual(prepared["motion_contract"], str(run / "motion-contract.json"))
        self.assertEqual(normalized["motion_id"], "codex-pet-v2")
        self.assertEqual(len(normalized["clips"]), 25)
        self.assertEqual(len(normalized["groups"]), 11)
        jobs = json.loads((run / "imagegen-jobs.json").read_text(encoding="utf-8"))["jobs"]
        self.assertTrue(all(job["requires_user_confirmation"] for job in jobs))
        identity = (run / "references" / "character-identity.txt").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("各视角", identity)
        self.assertNotIn("遮挡", identity)
        self.assertLess(len(identity), 500)


if __name__ == "__main__":
    unittest.main()
