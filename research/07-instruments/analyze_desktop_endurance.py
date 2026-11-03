#!/usr/bin/env python3
"""Analyze a GIANTS Editor endurance case without exposing private identifiers.

The analyzer reads completed or still-growing case files.  It never touches the
Editor process and writes nothing unless ``--output`` is supplied explicitly.
Missing files and incomplete observations remain visible in the result.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import statistics
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path
from typing import Any

WINDOW_SECONDS = 60.0
PNG_SIZE = (512, 512)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, "missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"invalid:{type(exc).__name__}"
    if isinstance(value, dict):
        return value, None
    return None, "invalid:object_required"


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    records: list[dict[str, Any]] = []
    errors = {"blank": 0, "invalid": 0, "non_object": 0}
    if not path.is_file():
        return records, {"missing": 1, **errors}
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                errors["blank"] += 1
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                errors["invalid"] += 1
                continue
            if isinstance(value, dict):
                records.append(value)
            else:
                errors["non_object"] += 1
    return records, errors


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    return (
        statistics.quantiles(values, n=100, method="inclusive")[int(fraction * 100) - 1]
        if len(values) > 1
        else values[0]
    )


def latency_stats(values: Iterable[Any]) -> dict[str, float | int | None]:
    numbers = sorted(
        number for value in values if (number := finite_number(value)) is not None
    )
    return {
        "count": len(numbers),
        "median_ms": statistics.median(numbers) if numbers else None,
        "p95_ms": percentile(numbers, 0.95),
        "max_ms": max(numbers) if numbers else None,
    }


def scene_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return Path(value.replace("\\", "/")).name or None


def parse_receipt(path: Path, expected_scene: Path | None = None) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "missing", "file": path.name}
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return {"status": "invalid", "file": path.name, "error": type(exc).__name__}

    def text(name: str) -> str | None:
        return root.findtext(name)

    ok_text = text("ok")
    ok = True if ok_text == "true" else False if ok_text == "false" else None
    result: dict[str, Any] = {
        "status": "observed",
        "file": path.name,
        "ok": ok,
        "op": text("op"),
        "seq": int(text("seq")) if (text("seq") or "").isdigit() else None,
        "scene_basename": scene_name(text("scene")),
        "heartbeat": finite_number(text("heartbeat")),
        "update_calls": finite_number(text("updateCalls")),
        "call_returned": None
        if text("callReturned") is None
        else text("callReturned") == "true",
    }
    actual_scene = text("scene")
    result["scene_matches_expected"] = expected_scene is None or (
        actual_scene is not None
        and Path(actual_scene).resolve() == expected_scene.resolve()
    )
    coordinates = {axis: finite_number(text(axis)) for axis in "xyz"}
    if any(value is not None for value in coordinates.values()):
        result["translation"] = coordinates
    return result


def slope(points: list[tuple[float, float]]) -> float | None:
    if len(points) < 2:
        return None
    mean_x = statistics.mean(x for x, _ in points)
    mean_y = statistics.mean(y for _, y in points)
    denominator = sum((x - mean_x) ** 2 for x, _ in points)
    return (
        sum((x - mean_x) * (y - mean_y) for x, y in points) / denominator
        if denominator
        else None
    )


def window_metrics(
    samples: list[dict[str, Any]], metric: str, end: float
) -> dict[str, Any]:
    first = [s for s in samples if 0 <= s["elapsed_s"] <= WINDOW_SECONDS]
    post_warmup = [
        s for s in samples if WINDOW_SECONDS < s["elapsed_s"] <= 2 * WINDOW_SECONDS
    ]
    last = [
        s for s in samples if max(0.0, end - WINDOW_SECONDS) <= s["elapsed_s"] <= end
    ]
    final_steady = [
        s
        for s in samples
        if max(0.0, end - 70.0) <= s["elapsed_s"] <= max(0.0, end - 10.0)
    ]

    def values(group: list[dict[str, Any]]) -> list[tuple[float, float]]:
        return [
            (s["elapsed_s"], value)
            for s in group
            if (value := finite_number(s.get(metric))) is not None
        ]

    def summary(group: list[dict[str, Any]]) -> dict[str, Any]:
        points = values(group)
        vals = [value for _, value in points]
        return {
            "samples": len(vals),
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
            "slope_per_second": slope(points),
        }

    return {
        "first_60s": summary(first),
        "post_warmup_60s": summary(post_warmup),
        "last_60s": summary(last),
        "final_steady_60s_before_teardown": summary(final_steady),
    }


def resource_correlations(
    samples: list[dict[str, Any]], operations: list[dict[str, Any]]
) -> dict[str, Any]:
    usable = [
        sample
        for sample in samples
        if finite_number(sample.get("elapsed_s")) is not None
    ]
    groups: dict[str, list[dict[str, float]]] = {}
    for operation in operations:
        elapsed = finite_number(operation.get("elapsed_s"))
        if elapsed is None or operation.get("action") not in {"request", "save"}:
            continue
        before = [sample for sample in usable if sample["elapsed_s"] <= elapsed]
        after = [sample for sample in usable if sample["elapsed_s"] >= elapsed]
        if not before or not after:
            continue
        left, right = before[-1], after[0]
        key = str(operation.get("op") or operation.get("action"))
        delta: dict[str, float] = {}
        for metric in ("working_set_bytes", "private_usage_bytes", "handle_count"):
            before_value = finite_number(left.get(metric))
            after_value = finite_number(right.get(metric))
            if before_value is not None and after_value is not None:
                delta[metric] = after_value - before_value
        if delta:
            groups.setdefault(key, []).append(delta)
    result: dict[str, Any] = {}
    for key, deltas in groups.items():
        result[key] = {
            "pairs": len(deltas),
            "delta_median": {
                metric: statistics.median(values)
                for metric in (
                    "working_set_bytes",
                    "private_usage_bytes",
                    "handle_count",
                )
                if (values := [delta[metric] for delta in deltas if metric in delta])
            },
            "interpretation": "nearest telemetry deltas are descriptive evidence, not causal attribution",
        }
    return result


def telemetry_metrics(
    records: list[dict[str, Any]],
    owned_pid: int | None = None,
    operations: list[dict[str, Any]] | None = None,
    callback_status: str = "no_callback_records",
) -> dict[str, Any]:
    samples = [
        record
        for record in records
        if finite_number(record.get("monotonic_ns")) is not None
        and record.get("phase") in {"running", "suspended"}
    ]
    samples.sort(key=lambda record: record["monotonic_ns"])
    if not samples:
        return {"sample_count": 0, "status": "missing"}
    start = float(samples[0]["monotonic_ns"])
    normalized = [
        dict(record, elapsed_s=(float(record["monotonic_ns"]) - start) / 1e9)
        for record in samples
    ]
    gaps = [b["elapsed_s"] - a["elapsed_s"] for a, b in itertools.pairwise(normalized)]
    input_states: dict[str, int] = {}
    private_window_samples = 0
    modal_window_samples = 0
    disabled_window_samples = 0
    heartbeat_values: list[float] = []
    containment = {
        "safe_observation_count": 0,
        "editor_on_input_count": 0,
        "foreground_owned_count": 0,
        "unknown_count": 0,
    }
    for record in normalized:
        input_state = (
            record.get("input") if isinstance(record.get("input"), dict) else {}
        )
        state = input_state.get("state")
        input_states[state or "missing"] = input_states.get(state or "missing", 0) + 1
        editor_hwnds = input_state.get("editor_hwnds_on_input")
        foreground_pid = input_state.get("foreground_pid")
        if isinstance(editor_hwnds, list) and editor_hwnds:
            containment["editor_on_input_count"] += 1
        if owned_pid is not None and foreground_pid == owned_pid:
            containment["foreground_owned_count"] += 1
        if (
            state == "input_unavailable"
            or not isinstance(editor_hwnds, list)
            or owned_pid is None
            or editor_hwnds
            or foreground_pid == owned_pid
        ):
            containment["unknown_count"] += 1
        else:
            containment["safe_observation_count"] += 1
        windows = record.get("private_windows")
        if isinstance(windows, list):
            private_window_samples += 1
            modal_window_samples += sum(
                1
                for window in windows
                if isinstance(window, dict)
                and window.get("visible")
                and window.get("owner_hwnd") not in (None, "0x0", "0")
            )
            disabled_window_samples += sum(
                1
                for window in windows
                if isinstance(window, dict) and window.get("enabled") is False
            )
        for value in (
            record.get("callbacks", {}).values()
            if isinstance(record.get("callbacks"), dict)
            else ()
        ):
            if (number := finite_number(value)) is not None:
                heartbeat_values.append(number)
    end = normalized[-1]["elapsed_s"]
    return {
        "status": "observed",
        "sample_count": len(normalized),
        "elapsed_seconds": end,
        "utc_ns_range": [samples[0].get("utc_ns"), samples[-1].get("utc_ns")],
        "monotonic_ns_range": [
            samples[0].get("monotonic_ns"),
            samples[-1].get("monotonic_ns"),
        ],
        "sample_gap_seconds": {
            "count": len(gaps),
            "median": statistics.median(gaps) if gaps else None,
            "max": max(gaps) if gaps else None,
        },
        "input_state_counts": input_states,
        "containment_observations": containment,
        "source_callbacks": {
            "observed_values": heartbeat_values,
            "zero_count": sum(value == 0 for value in heartbeat_values),
            "nonzero_count": sum(value != 0 for value in heartbeat_values),
            "counter_status": callback_status,
            "interpretation": "observed callback values only; zero does not prove liveness",
        },
        "private_window_observations": {
            "samples_with_inventory": private_window_samples,
            "modal_like_window_count": modal_window_samples,
            "disabled_window_count": disabled_window_samples,
        },
        "memory": {
            metric: window_metrics(normalized, metric, end)
            for metric in ("working_set_bytes", "private_usage_bytes", "handle_count")
        },
        "resource_correlations": resource_correlations(normalized, operations or []),
    }


def operation_metrics(
    run: Path, operations: list[dict[str, Any]], expected_scene: Path | None
) -> dict[str, Any]:
    actions = [
        record for record in operations if record.get("action") in {"request", "save"}
    ]
    counts: dict[str, int] = {}
    for record in actions:
        key = str(record.get("op") or record.get("action"))
        counts[key] = counts.get(key, 0) + 1
    host = latency_stats(record.get("latency_ms") for record in actions)
    native = latency_stats(
        record.get("reply", {}).get("elapsed_ms")
        for record in actions
        if isinstance(record.get("reply"), dict)
    )
    replies: list[dict[str, Any]] = []
    saves: list[dict[str, Any]] = []
    last_mutate: int | None = None
    expected_translation: dict[str, float] = {"x": 0.0, "y": 0.0, "z": 0.0}

    def identity(
        receipt: dict[str, Any],
        expected_op: str,
        expected_seq: int | None,
        returned: bool,
    ) -> bool:
        return bool(
            returned
            and receipt.get("status") == "observed"
            and receipt.get("ok") is True
            and receipt.get("op") == expected_op
            and (expected_seq is None or receipt.get("seq") == expected_seq)
            and receipt.get("scene_matches_expected") is True
            and receipt.get("call_returned") is not False
        )

    def attach_translation(receipt: dict[str, Any]) -> None:
        actual = receipt.get("translation")
        receipt["translation_expected"] = expected_translation.copy()
        receipt["translation_matches_expected"] = isinstance(actual, dict) and all(
            finite_number(actual.get(axis)) is not None
            and abs(float(actual[axis]) - expected_translation[axis]) <= 1e-5
            for axis in "xyz"
        )

    for record in actions:
        action = record.get("action")
        sequence = record.get("seq")
        if (
            action == "request"
            and record.get("op") == "mutate"
            and isinstance(sequence, int)
        ):
            last_mutate = sequence
            expected_translation = {"x": sequence * 0.001, "y": -1.5, "z": 2.125}
        if action == "request" and isinstance(sequence, int):
            receipt = parse_receipt(
                run / f"response-{sequence:06d}.xml", expected_scene
            )
            returned = (
                bool(record.get("reply", {}).get("returned"))
                if isinstance(record.get("reply"), dict)
                else False
            )
            receipt["correlated_seq"] = sequence
            receipt["correlated_op"] = record.get("op")
            receipt["command_returned"] = returned
            receipt["receipt_valid"] = identity(
                receipt, str(record.get("op")), sequence, returned
            )
            receipt["freshness"] = (
                "unknown"
                if receipt.get("status") == "observed"
                else receipt.get("status")
            )
            attach_translation(receipt)
            replies.append(receipt)
        elif action == "save":
            save_seq = record.get("save_seq")
            receipt = (
                parse_receipt(run / f"save-{int(save_seq):06d}.xml", expected_scene)
                if isinstance(save_seq, int)
                else {"status": "missing"}
            )
            returned = (
                bool(record.get("reply", {}).get("returned"))
                if isinstance(record.get("reply"), dict)
                else False
            )
            receipt["correlated_save_seq"] = save_seq
            receipt["latest_mutate_seq"] = last_mutate
            receipt["command_returned"] = returned
            receipt["receipt_valid"] = identity(receipt, "save", None, returned)
            receipt["freshness"] = (
                "unknown"
                if receipt.get("status") == "observed"
                else receipt.get("status")
            )
            attach_translation(receipt)
            receipt["translation_matches_latest_mutation"] = receipt[
                "translation_matches_expected"
            ]
            saves.append(receipt)
    all_receipts = replies + saves
    missing = sum(item.get("status") == "missing" for item in all_receipts)
    invalid = sum(
        item.get("status") in {"invalid", "observed"}
        and not item.get("receipt_valid", False)
        for item in all_receipts
    )
    returned_false = sum(item.get("command_returned") is False for item in all_receipts)
    heartbeat_values = [
        item["heartbeat"]
        for item in replies + saves
        if finite_number(item.get("heartbeat")) is not None
    ]
    update_call_values = [
        item["update_calls"]
        for item in all_receipts
        if finite_number(item.get("update_calls")) is not None
    ]
    return {
        "record_count": len(operations),
        "operation_count": len(actions),
        "command_counts": counts,
        "host_latency_ms": host,
        "native_latency_ms": native,
        "replies": replies,
        "saves": saves,
        "source_callback_heartbeat": {
            "observed_count": len(heartbeat_values),
            "zero_count": sum(value == 0 for value in heartbeat_values),
            "nonzero_count": sum(value != 0 for value in heartbeat_values),
            "update_calls_observed": update_call_values,
            "counter_status": (
                "phase_validated_observation_only"
                if update_call_values
                else "invalid_phase"
            ),
            "liveness_claim": "none",
            "interpretation": "observed callback values only; zero does not prove liveness",
        },
        "missing_or_invalid_receipts": {
            "missing": missing,
            "invalid_or_identity_failed": invalid,
            "command_returned_false": returned_false,
        },
    }


def wts_metrics(
    operations: list[dict[str, Any]], operation_result: dict[str, Any]
) -> dict[str, Any]:
    transitions = [
        record for record in operations if record.get("event") == "wts_transition"
    ]
    lock_seen = next(
        (record for record in operations if record.get("event") == "lock_seen"), None
    )
    finished = next(
        (
            record
            for record in operations
            if record.get("event") == "locked_active_work_finished"
        ),
        None,
    )
    unlocked = next(
        (record for record in operations if record.get("event") == "unlock_seen"), None
    )
    action_records = [
        record for record in operations if record.get("action") in {"request", "save"}
    ]
    locked_actions = [
        record
        for record in action_records
        if record.get("wts_before") == 0 and record.get("wts_after") == 0
    ]
    lock_start = finite_number(lock_seen.get("elapsed_s")) if lock_seen else None
    work_finish = finite_number(finished.get("elapsed_s")) if finished else None
    out_of_window = []
    in_window_actions = []
    for record in locked_actions:
        elapsed_action = finite_number(record.get("elapsed_s"))
        in_window = (
            elapsed_action is not None
            and lock_start is not None
            and work_finish is not None
            and lock_start <= elapsed_action <= work_finish
        )
        if in_window:
            in_window_actions.append(record)
        else:
            out_of_window.append(
                {
                    "action": record.get("action"),
                    "op": record.get("op"),
                    "seq": record.get("seq"),
                    "save_seq": record.get("save_seq"),
                    "elapsed_s": elapsed_action,
                }
            )
    valid_replies = [
        item
        for item in operation_result.get("replies", [])
        if item.get("receipt_valid")
    ]
    valid_saves = [
        item for item in operation_result.get("saves", []) if item.get("receipt_valid")
    ]
    valid_locked_actions = [
        record
        for record in in_window_actions
        if (
            record.get("action") == "request"
            and any(
                item.get("correlated_seq") == record.get("seq")
                for item in valid_replies
            )
        )
        or (
            record.get("action") == "save"
            and any(
                item.get("correlated_save_seq") == record.get("save_seq")
                for item in valid_saves
            )
        )
    ]
    locked_action_counts: dict[str, int] = {}
    for record in valid_locked_actions:
        key = str(record.get("op") or record.get("action"))
        locked_action_counts[key] = locked_action_counts.get(key, 0) + 1
    elapsed = finite_number(finished.get("lock_elapsed_s")) if finished else None
    proved = bool(
        lock_seen
        and finished
        and unlocked
        and elapsed is not None
        and elapsed <= 90
        and locked_actions
        and not out_of_window
        and len(valid_locked_actions) == len(in_window_actions)
    )
    return {
        "flags_0_is_locked": True,
        "flags_1_is_unlocked": True,
        "transitions": [
            {"flags": record.get("flags"), "elapsed_s": record.get("elapsed_s")}
            for record in transitions
        ],
        "lock_seen": bool(lock_seen),
        "locked_active_work_finished": bool(finished),
        "unlock_seen": bool(unlocked),
        "active_finish_lock_elapsed_s": elapsed,
        "unlock_lock_elapsed_s": finite_number(unlocked.get("lock_elapsed_s"))
        if unlocked
        else None,
        "locked_action_count_pre_and_post_flags_0": len(locked_actions),
        "locked_action_count_inside_active_window": len(in_window_actions),
        "locked_actions_out_of_window": out_of_window,
        "any_locked_action_out_of_window": bool(out_of_window),
        "valid_locked_action_count": len(valid_locked_actions),
        "valid_locked_action_counts_by_op": locked_action_counts,
        "proved_successful_during_lock": proved,
        "status": "proved" if proved else "uncertain",
    }


def png_metrics(run: Path) -> dict[str, Any]:
    paths = sorted(run.glob("view-*.png"))
    decoded = 0
    dimensions: list[list[int]] = []
    errors: list[str] = []
    try:
        from PIL import Image
    except ImportError:
        return {
            "status": "unavailable",
            "file_count": len(paths),
            "reason": "Pillow unavailable",
        }
    for path in paths:
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                dimensions.append([int(image.width), int(image.height)])
            decoded += 1
        except (OSError, SyntaxError, ValueError) as exc:
            errors.append(f"{path.name}:{type(exc).__name__}")
    return {
        "status": "observed",
        "file_count": len(paths),
        "decoded_count": decoded,
        "dimensions": dimensions,
        "all_512x512": bool(paths)
        and decoded == len(paths)
        and all(tuple(size) == PNG_SIZE for size in dimensions),
        "errors": errors,
    }


def config_metrics(run: Path) -> dict[str, Any]:
    names = ("editor.xml", "input-editor.xml")
    hashes = {
        name: sha256(run / name) if (run / name).is_file() else None for name in names
    }
    return {
        "hashes": hashes,
        "input_matches_editor": bool(
            hashes["editor.xml"] and hashes["editor.xml"] == hashes["input-editor.xml"]
        ),
        "status": "observed" if all(hashes.values()) else "incomplete",
    }


def analyze(run: Path) -> dict[str, Any]:
    summary, summary_status = read_json(run / "summary.json")
    telemetry, telemetry_errors = read_jsonl(run / "telemetry.jsonl")
    operations, operation_errors = read_jsonl(run / "operations.jsonl")
    experiment, experiment_status = read_json(run / "experiment-result.json")
    spec, _ = read_json(run / "spec.json")
    expected_scene = None
    if isinstance(spec, dict) and isinstance(spec.get("scene"), str):
        expected_scene = Path(spec["scene"]).resolve()
    session, _ = read_json(run / "session.json")
    owned_pid = (
        session.get("pid")
        if isinstance(session, dict) and isinstance(session.get("pid"), int)
        else None
    )
    operation_result = operation_metrics(run, operations, expected_scene)
    telemetry_result = telemetry_metrics(
        telemetry,
        owned_pid,
        operations,
        operation_result["source_callback_heartbeat"]["counter_status"],
    )
    telemetry_range = telemetry_result.get("monotonic_ns_range")
    telemetry_utc_range = telemetry_result.get("utc_ns_range")
    duration_monotonic = (
        [summary.get("started_monotonic_ns"), summary.get("ended_monotonic_ns")]
        if summary and summary.get("started_monotonic_ns") is not None
        else telemetry_range
    )
    duration_utc = (
        [summary.get("started_utc_ns"), summary.get("ended_utc_ns")]
        if summary and summary.get("started_utc_ns") is not None
        else telemetry_utc_range
    )
    clean_exit = bool(
        summary
        and summary.get("status") == "completed"
        and summary.get("editor_exit_code") == 0
        and not summary.get("terminated_by_launcher")
    )
    receipt_failures = operation_result["missing_or_invalid_receipts"]
    receipt_failure_count = sum(
        int(value)
        for value in receipt_failures.values()
        if isinstance(value, (int, float))
    )
    wts_result = wts_metrics(operations, operation_result)
    complete = bool(
        summary_status is None
        and experiment_status is None
        and experiment
        and experiment.get("status") == "passed"
        and clean_exit
        and receipt_failure_count == 0
    )
    return {
        "format": 1,
        "case": run.name,
        "status": "complete" if complete else "incomplete",
        "source_files": {
            "summary": summary_status or "observed",
            "experiment_result": experiment_status or "observed",
            "telemetry": telemetry_errors,
            "operations": operation_errors,
        },
        "duration": {
            "actual_monotonic_ns": duration_monotonic,
            "utc_ns": duration_utc,
            "editor_exit_code": summary.get("editor_exit_code") if summary else None,
            "clean_exit_proven": clean_exit,
            "receipt_failure_count": receipt_failure_count,
        },
        "telemetry": telemetry_result,
        "operations": operation_result,
        "wts": wts_result,
        "config_snapshot": config_metrics(run),
        "png": png_metrics(run),
        "experiment_result_observed": {
            key: value
            for key, value in (experiment or {}).items()
            if key not in {"pid", "desktop", "scene", "path"}
        },
        "limitations": [
            "Private desktop callback heartbeat values are observations and do not prove callback liveness.",
            "First and last 60 second memory ranges and slopes describe this case only; they do not establish a universal leak claim.",
            "Raw PIDs, HWNDs, window titles, and full paths are omitted from this result.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, help="Write the JSON result here instead of stdout."
    )
    args = parser.parse_args()
    run = args.case.resolve()
    if not run.is_dir():
        parser.error(f"case directory does not exist: {run}")
    result = analyze(run)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
