"""Derive a small receipt from prepared private-desktop runs and visible fidelity runs.

The reader never starts Editor and stores no raw telemetry rows, window handles, or process identifiers.
"""

import argparse
import ctypes
import hashlib
import json
import statistics
import subprocess
from itertools import pairwise
from pathlib import Path
from xml.etree import ElementTree as ET

from analyze_fidelity import compare_samples, image_pair, source_hash_check

CASES = ("gate-native", "water-native")
VISIBLE_ROOT_NAME = "giants-editor-fidelity"
EXPECTED_SAMPLES = {
    "gate-native": {"initial": 49, "fresh": 97},
    "water-native": {"initial": 50, "fresh": 62},
}
EXPECTED_IMAGES = {
    "gate": ("start.png", "middle.png", "end.png"),
    "water": ("view.png",),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(path: Path, scene: str, operation: str) -> dict:
    if not path.exists():
        return {"exists": False, "valid": False}
    root = ET.parse(path).getroot()
    actual_scene = (root.findtext("scene") or "").replace("\\", "/").casefold()
    expected = scene.replace("\\", "/").casefold()
    path_value = (root.findtext("path") or "").replace("\\", "/").casefold()
    return {
        "exists": True,
        "valid": (
            root.findtext("ok") == "true"
            and root.findtext("op") == operation
            and actual_scene == expected
            and (operation == "ready" or path_value == expected)
        ),
        "ok": root.findtext("ok") == "true",
        "operation_matches": root.findtext("op") == operation,
        "scene_matches": actual_scene == expected,
        **({"path_matches": path_value == expected} if operation == "save" else {}),
    }


def telemetry_summary(run: Path, pid: int, phase: str) -> dict:
    folder = run / "initial" if phase == "initial" else run
    rows = [
        json.loads(line)
        for line in (folder / "private-desktop-telemetry.jsonl")
        .read_text()
        .splitlines()
    ]
    times = [row["time_ns"] for row in rows]
    gaps = [(right - left) / 1_000_000 for left, right in pairwise(times)]
    return {
        "sample_count": len(rows),
        "all_input_desktops_default": all(
            row.get("input_desktop") == "Default" for row in rows
        ),
        "all_input_editor_windows_empty": all(
            not row.get("editor_hwnds_on_input") for row in rows
        ),
        "all_foreground_other": all(row.get("foreground_pid") != pid for row in rows),
        "gap_ms": {
            "minimum": min(gaps),
            "median": statistics.median(gaps),
            "maximum": max(gaps),
        },
    }


def private_frame(case_result: dict) -> dict:
    frames = [phase["session"]["private_frame"] for phase in case_result["phases"]]
    return {
        "count": len(frames),
        "all_membership_evidence_explicit": all(
            item.get("membership_evidence")
            == "EnumDesktopWindows with explicit private desktop handle"
            for item in frames
        ),
        "all_visible": all(item.get("is_window_visible") is True for item in frames),
        "all_not_iconic": all(item.get("is_iconic") is False for item in frames),
        "all_thread_desktop_queries_access_denied": all(
            item.get("owner_desktop") is None
            and item.get("owner_desktop_query_error") == 5
            for item in frames
        ),
        "private_desktops": [item["private_desktop"] for item in frames],
        "binary_sha256": sorted({item["binary_sha256"] for item in frames}),
    }


def compare_asset(case: str, spec: dict, private: Path, visible: Path) -> dict:
    name = Path(spec["scene"]).name
    saved, prior = private / "asset" / name, visible / "asset" / name
    sidecars = {}
    for suffix in (".anim", ".shapes"):
        left, right = (
            saved.with_suffix(saved.suffix + suffix),
            prior.with_suffix(prior.suffix + suffix),
        )
        if not left.exists() and not right.exists():
            sidecars[suffix] = {
                "status": "not_applicable",
                "reason": "no_sidecar_in_fixture",
            }
            continue
        sidecars[suffix] = {
            "private_sha256": digest(left) if left.exists() else None,
            "visible_sha256": digest(right) if right.exists() else None,
            "equal": left.exists()
            and right.exists()
            and left.read_bytes() == right.read_bytes(),
        }
    return {
        "saved_i3d_sha256": digest(saved),
        "visible_saved_i3d_sha256": digest(prior),
        "saved_i3d_equal": saved.read_bytes() == prior.read_bytes(),
        "sidecars": sidecars,
    }


def system_check(root: Path) -> dict:
    result = {
        "requested": True,
        "normal_config": {"exists": False, "hash_matches_baseline": False},
    }
    config = (
        Path.home() / "AppData" / "Local" / "GIANTS Editor 64bit 10.0.14" / "editor.xml"
    )
    baseline = root.parent / "baseline-desktop.json"
    if config.exists() and baseline.exists():
        expected = json.loads(baseline.read_text(encoding="utf-8"))[
            "editor_config_sha256"
        ]
        result["normal_config"] = {
            "exists": True,
            "sha256": digest(config),
            "hash_matches_baseline": digest(config) == expected,
        }
    try:
        from private_desktop_probe import READ, winapi

        _, user32, _ = winapi()
        queries = []
        for case in CASES:
            for phase in json.loads((root / case / "case-result.json").read_text())[
                "phases"
            ]:
                name = phase["session"]["private_frame"]["private_desktop"]
                ctypes.set_last_error(0)
                handle = user32.OpenDesktopW(name, 0, False, READ)
                error = ctypes.get_last_error()
                queries.append(
                    {"name": name, "opened": bool(handle), "open_error": error}
                )
                if handle:
                    user32.CloseDesktop(handle)
        result["private_desktop_queries"] = queries
        result["private_desktops_absent_after_run"] = all(
            not item["opened"] and item["open_error"] == 2 for item in queries
        )
        listing = subprocess.run(
            [
                "tasklist",
                "/FI",
                "IMAGENAME eq editor.exe",
                "/FO",
                "CSV",
                "/NH",
            ],
            capture_output=True,
            text=True,
            check=True,
            creationflags=0x08000000,
        ).stdout.splitlines()
        result["editor_process_count"] = sum(line.startswith('"') for line in listing)
        result["no_editor_processes"] = result["editor_process_count"] == 0
    except OSError as exc:
        result["private_desktops_absent_after_run"] = False
        result["system_check_error"] = type(exc).__name__
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(".docs/giants-editor-invisible/private")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-system", action="store_true")
    args = parser.parse_args()
    visible_root = args.root.parent.parent / VISIBLE_ROOT_NAME
    cases = {}
    for case in CASES:
        run = args.root / case
        spec = json.loads((run / "spec.json").read_text(encoding="utf-8"))
        result = json.loads((run / "case-result.json").read_text(encoding="utf-8"))
        phases = {}
        for phase, receipt_name in (
            ("initial", "ready.xml"),
            ("fresh", "fresh-ready.xml"),
        ):
            folder = run / "initial" if phase == "initial" else run
            pid = next(
                item["session"]["pid"]
                for item in result["phases"]
                if item["phase"]
                == ("initial_save" if phase == "initial" else "fresh_readback")
            )
            phases[phase] = {
                "receipt": receipt(folder / receipt_name, spec["scene"], "ready"),
                "telemetry": telemetry_summary(run, pid, phase),
            }
        phases["initial"]["save_receipt"] = receipt(
            run / "save-001.xml", spec["scene"], "save"
        )
        cases[case] = {
            "asset": spec["label"],
            "mode": spec["mode"],
            "source": source_hash_check(run, spec),
            "prepared_i3d_sha256": digest(run / "before.i3d"),
            "frame": private_frame(result),
            "phases": phases,
            "asset_compare": compare_asset(case, spec, run, visible_root / case),
            "sample_compare": (
                {"status": "not_applicable"}
                if spec["label"] == "water"
                else compare_samples(
                    run / "samples.xml", visible_root / case / "samples.xml"
                )
            ),
            "images": {
                name: image_pair(run / name, visible_root / case / name)
                for name in EXPECTED_IMAGES[spec["label"]]
            },
        }
        if any(not (run / name).exists() for name in EXPECTED_IMAGES[spec["label"]]):
            raise ValueError(f"missing expected image for {case}")
        for phase, expected in EXPECTED_SAMPLES[case].items():
            if phases[phase]["telemetry"]["sample_count"] != expected:
                raise ValueError(f"unexpected telemetry count for {case}/{phase}")
    attempt_dirs = [
        p for case in CASES for p in (args.root / case).glob("attempt-*") if p.is_dir()
    ]
    output = {
        "format": 1,
        "experiment": "giants_editor_invisible_private_startup",
        "runs": 4,
        "cases": cases,
        "coverage": {
            "phase_count": 4,
            "telemetry_samples": sum(
                item["phases"][phase]["telemetry"]["sample_count"]
                for item in cases.values()
                for phase in ("initial", "fresh")
            ),
            "successful_editor_exits": all(
                phase["exit"]["status"] == "exited" and phase["exit"]["exit_code"] == 0
                for item in (
                    json.loads((args.root / case / "case-result.json").read_text())
                    for case in CASES
                )
                for phase in item["phases"]
            ),
            "input_default_and_editor_absent": all(
                phase["telemetry"]["all_input_desktops_default"]
                and phase["telemetry"]["all_input_editor_windows_empty"]
                for case in cases.values()
                for phase in case["phases"].values()
                if isinstance(phase, dict) and "telemetry" in phase
            ),
            "sample_gap_max_ms": max(
                phase["telemetry"]["gap_ms"]["maximum"]
                for case in cases.values()
                for phase in case["phases"].values()
                if isinstance(phase, dict) and "telemetry" in phase
            ),
            "gap_is_not_a_fixed_50ms_guarantee": True,
        },
        "earlier_diagnostics": {
            "archived_attempt_count": len(attempt_dirs),
            "attempts_preserved": bool(attempt_dirs)
            and all(p.is_dir() for p in attempt_dirs),
            "claims_about_unstarted_runs": False,
        },
    }
    if args.verify_system:
        output["system_check"] = system_check(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "runs": 4,
                "telemetry_samples": output["coverage"]["telemetry_samples"],
            }
        )
    )


if __name__ == "__main__":
    main()
