"""Derive privacy-safe evidence from prepared GIANTS Editor runtime receipts.

The analyzer reads ignored run directories. It never starts Editor and writes
only a compact JSON receipt without process identifiers, window handles, paths,
or raw vendor log content.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

EXPECTED_HOOKS = {
    "CreateWindowExA",
    "CreateWindowExW",
    "MessageBoxA",
    "MessageBoxW",
    "NtUserCreateWindowEx",
    "SetWindowPos",
    "ShowWindow",
    "ShowWindowAsync",
}
EXPECTED_PROBE_CHILDREN = 2
REDACTED_ERROR = re.compile(
    r"[A-Za-z]:\\[^\r\n]+|/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+"
)


def clean_error(value: object) -> str:
    text = str(value or "").splitlines()[0].strip()
    return REDACTED_ERROR.sub("<path>", text)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def window_creation_succeeded(row: dict) -> bool:
    if "success" in row:
        return row["success"] not in (False, 0, "0", None)
    return bool(row.get("hwnd")) and row.get("hwnd") != "0x0"


def payloads(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            payload = row.get("message", {}).get("payload", {})
            if isinstance(payload, dict):
                rows.append(payload)
        except json.JSONDecodeError:
            continue
    return rows


def telemetry(path: Path, pid: int) -> dict:
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    phases = {row.get("phase") for row in rows}
    state_rows = [row for row in rows if "input_desktop" in row]
    return {
        "row_count": len(rows),
        "state_row_count": len(state_rows),
        "missing_input_state_fields": len(rows) - len(state_rows),
        "all_input_desktops_default": bool(state_rows)
        and all(row.get("input_desktop") == "Default" for row in state_rows),
        "all_editor_windows_on_input_empty": bool(state_rows)
        and all(not row.get("editor_hwnds_on_input") for row in state_rows),
        "all_foreground_pids_are_other": bool(state_rows)
        and all(row.get("foreground_pid") != pid for row in state_rows),
        "phases": sorted(phase for phase in phases if phase is not None),
        "has_suspended_phase": "suspended" in phases,
        "has_exited_phase": "exited" in phases,
    }


def config_renderer(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return ET.parse(path).findtext("./graphic/renderer")
    except ET.ParseError:
        return None


def log_backend(
    path: Path, summary_pid: int, correlation_path: Path | None = None
) -> dict:
    if not path.exists():
        return {
            "correlated": False,
            "reason": "editor_log_missing",
            "last_render_driver": None,
            "audio_driver": None,
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    manual_correlation = None
    if correlation_path and correlation_path.exists():
        try:
            manual_correlation = load_json(correlation_path)
        except json.JSONDecodeError:
            manual_correlation = None
    pid_match = re.search(r"^PID:\s*(\d+)\s*$", text, re.MULTILINE)
    log_pid = int(pid_match.group(1)) if pid_match else None
    correlated = (
        manual_correlation.get("correlated")
        if manual_correlation is not None and "correlated" in manual_correlation
        else log_pid == summary_pid
    )
    audio_section = re.search(
        r"^Audio System\s*$([\s\S]*?)(?=^\S|\Z)", text, re.MULTILINE
    )
    render_sections = list(
        re.finditer(r"^Render System\s*$([\s\S]*?)(?=^\S|\Z)", text, re.MULTILINE)
    )
    audio = (
        re.search(r"^\s+Driver:\s*(.+)$", audio_section.group(1), re.MULTILINE)
        if audio_section
        else None
    )
    render = (
        re.search(r"^\s+Driver:\s*(.+)$", render_sections[-1].group(1), re.MULTILINE)
        if render_sections
        else None
    )
    return {
        "correlated": correlated,
        "reason": (
            "manual_mtime_receipt"
            if manual_correlation is not None and correlated
            else "summary_pid_matches_log_pid"
            if correlated
            else "log_pid_unavailable"
            if log_pid is None
            else "log_pid_mismatch"
        ),
        "last_render_driver": render.group(1).strip()
        if correlated and render
        else None,
        "audio_driver": audio.group(1).strip() if correlated and audio else None,
    }


def lua_result(run: Path, summary: dict, spec: dict) -> dict:
    result_path = run / "result.xml"
    suspended = [
        json.loads(line)["time_ns"]
        for line in (run / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(line).get("phase") == "suspended"
    ]
    reference_ns = summary.get("started_ns") or (min(suspended) if suspended else None)
    fresh = bool(
        result_path.exists()
        and reference_ns
        and result_path.stat().st_mtime_ns >= reference_ns
    )
    if not result_path.exists():
        return {
            "exists": False,
            "parseable": False,
            "ok": False,
            "scene_correlated": False,
            "fresh_mtime_provable": False,
            "fresh_mtime_reason": "result_missing_or_unparseable",
        }
    try:
        root = ET.parse(result_path).getroot()
    except ET.ParseError:
        return {
            "exists": True,
            "parseable": False,
            "ok": False,
            "scene_correlated": False,
            "fresh_mtime_provable": False,
            "fresh_mtime_reason": "result_missing_or_unparseable",
        }
    scene = (root.findtext("scene") or "").replace("\\", "/")
    expected_scene = str(spec.get("scene", "")).replace("\\", "/")
    return {
        "exists": True,
        "parseable": True,
        "ok": root.findtext("ok") == "true",
        "scene_correlated": bool(scene and scene == expected_scene),
        "scene_file": Path(scene).name if scene else None,
        "root_value": root.findtext("root"),
        "children_value": root.findtext("children"),
        "expected_children_value": EXPECTED_PROBE_CHILDREN,
        "fresh_mtime_provable": fresh,
        "fresh_mtime_reason": "recorded_suspended_sample_before_resume"
        if reference_ns
        else "no_recorded_reference",
    }


def classify(summary: dict, events: dict) -> str:
    if summary.get("result_ready") and (
        events["successful_create_windows"] or events["native_windows_created"]
    ):
        return "gui_startup_succeeded_non_headless"
    if events["canvas_error_writes"]:
        return "backend_rejected_before_lua"
    if events["window_denied_events"] or not summary.get("result_ready", False):
        return "lua_startup_not_reached"
    return "instrument_error"


def analyze_case(run: Path) -> dict:
    summary = load_json(run / "summary.json")
    spec = load_json(run / "spec.json")
    rows = payloads(run / "frida-messages.jsonl")
    create = [row for row in rows if row.get("event") == "create_window"]
    native = [row for row in rows if row.get("event") == "native_window_created"]
    hooks = sorted(
        {
            row.get("name")
            for row in rows
            if row.get("event") == "hook_installed" and row.get("name")
        }
    )
    errors = []
    error_path = run / "frida-errors.jsonl"
    if error_path.exists():
        for line in error_path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line).get("error")
            except json.JSONDecodeError:
                value = None
            if value:
                errors.append(clean_error(value))
    if summary.get("error"):
        errors.append(clean_error(summary["error"]))
    pid = summary.get("pid")
    input_hashes = summary.get("input_hashes_before_start") or {}
    event_counts = {
        "successful_create_windows": sum(
            window_creation_succeeded(row) for row in create
        ),
        "create_window_events": len(create),
        "native_windows_created": sum(
            bool(row.get("hwnd")) and row.get("hwnd") != "0x0" for row in native
        ),
        "native_window_events": len(native),
        "window_denied_events": sum(
            row.get("event") == "window_creation_denied" for row in rows
        ),
        "hooks_ready": sum(row.get("event") == "instrumentation_ready" for row in rows),
        "installed_win32u_api_count": len(set(hooks) & EXPECTED_HOOKS),
        "installed_win32u_api_names": hooks,
        "trace_event_counts": {
            event: sum(row.get("event") == event for row in rows)
            for event in sorted({row.get("event") for row in rows if row.get("event")})
        },
        "renderer_config_events": [
            {key: row[key] for key in ("before", "after") if key in row}
            for row in rows
            if row.get("event") == "renderer_config_constructed"
        ],
        "renderer_factory_enums": [
            row["enum"]
            for row in rows
            if row.get("event") == "renderer_factory_enter" and "enum" in row
        ],
        "canvas_error_writes": [
            row.get("message")
            for row in rows
            if row.get("event") == "canvas_error_write" and row.get("message")
        ],
    }
    return {
        "case": run.name,
        "mode": summary.get("mode"),
        "requested_renderer": config_renderer(run / "input-editor.xml") or "unknown",
        "status": summary.get("status"),
        "classification": classify(summary, event_counts),
        "result_ready": summary.get("result_ready"),
        "exit_code_recorded": summary.get("exit_code"),
        "event_counts": event_counts,
        "hooks_coverage": {
            "expected_count": len(EXPECTED_HOOKS),
            "all_expected_installed": set(hooks) >= EXPECTED_HOOKS,
        },
        "controller_errors": sorted(set(errors)),
        "script_errors": [
            clean_error(json.loads(line)["message"].get("description"))
            for line in (run / "frida-messages.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if json.loads(line)["message"].get("type") == "error"
        ],
        "individual_run": {
            "mode": summary.get("mode"),
            "input_hashes_before_start": dict(sorted(input_hashes.items())),
        },
        "lua_probe": lua_result(run, summary, spec),
        "telemetry": telemetry(run / "telemetry.jsonl", pid),
        "desktop_cleanup": {
            "cleanup_errors": summary.get("cleanup_errors", []),
            "absent_after_close": summary.get("desktop_absent_after_close"),
            "open_error_after_close": summary.get("desktop_open_error_after_close"),
            "cleanup_confirmed": summary.get("desktop_absent_after_close") is True
            and summary.get("desktop_open_error_after_close") == 2,
        },
        "backend": log_backend(
            run / "editor_log.txt", pid, run / "log-correlation.json"
        ),
        "config_snapshot": {
            "input_editor_xml_exists": (run / "input-editor.xml").exists(),
            "input_editor_xml_sha256": digest(run / "input-editor.xml")
            if (run / "input-editor.xml").exists()
            else None,
            "input_hash_matches_recorded": digest(run / "input-editor.xml")
            == input_hashes.get("editor.xml")
            if (run / "input-editor.xml").exists()
            else None,
            "input_renderer": config_renderer(run / "input-editor.xml"),
            "post_renderer": config_renderer(run / "editor.xml"),
        },
    }


def system_check(root: Path) -> dict:
    try:
        import subprocess

        output = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq editor.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=True,
            creationflags=0x08000000,
        ).stdout.splitlines()
        count = sum(line.startswith('"') for line in output)
        return {
            "requested": True,
            "editor_process_count": count,
            "no_editor_processes": count == 0,
            "normal_config_sha256": digest(
                Path.home() / "AppData/Local/GIANTS Editor 64bit 10.0.14/editor.xml"
            ),
            "normal_config_unchanged": digest(
                Path.home() / "AppData/Local/GIANTS Editor 64bit 10.0.14/editor.xml"
            )
            == "31720002d6f6639a6d340ff4d7bb4e558f5ccd1001209c169d1f79f3345871cf",
        }
    except (OSError, subprocess.CalledProcessError) as exc:
        return {"requested": True, "error": type(exc).__name__}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(".docs/giants-editor-headless/runtime")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-system", action="store_true")
    args = parser.parse_args()
    runs = sorted(
        path
        for path in args.root.iterdir()
        if path.is_dir() and (path / "summary.json").exists()
    )
    cases = [analyze_case(path) for path in runs]
    binary_hashes = sorted(
        {
            item["individual_run"]["input_hashes_before_start"].get("editor.exe")
            for item in cases
        }
    )
    output = {
        "format": 1,
        "experiment": "giants_editor_headless_runtime",
        "case_count": len(cases),
        "cases": cases,
        "coverage": {
            "program_binary_sha256": binary_hashes[0]
            if len(binary_hashes) == 1
            else None,
            "program_binary_hashes_consistent": len(binary_hashes) == 1
            and None not in binary_hashes,
            "all_desktops_default": all(
                case["telemetry"]["all_input_desktops_default"] for case in cases
            ),
            "all_editor_windows_absent_on_input": all(
                case["telemetry"]["all_editor_windows_on_input_empty"] for case in cases
            ),
            "all_foreground_pids_are_other": all(
                case["telemetry"]["all_foreground_pids_are_other"] for case in cases
            ),
            "all_desktop_cleanup_confirmed": all(
                case["desktop_cleanup"]["cleanup_confirmed"] for case in cases
            ),
            "successful_lua_results": sum(case["lua_probe"]["ok"] for case in cases),
            "cases_with_successful_gui_windows": sum(
                case["classification"] == "gui_startup_succeeded_non_headless"
                for case in cases
            ),
            "cases_with_any_successful_gui_windows": sum(
                bool(case["event_counts"]["successful_create_windows"])
                or bool(case["event_counts"]["native_windows_created"])
                for case in cases
            ),
            "successful_create_window_events": sum(
                case["event_counts"]["successful_create_windows"] for case in cases
            ),
            "native_window_created_events": sum(
                case["event_counts"]["native_windows_created"] for case in cases
            ),
        },
        "limitations": [
            "Receipt freshness uses the recorded suspended-process sample before ResumeThread when summary.started_ns is absent.",
            "The Lua fixture exposes root and child counts; it does not identify child node names.",
            "Backend fields are omitted when the editor log PID does not match the run summary PID.",
            "The classification records observed startup outcomes and does not claim absolute impossibility.",
        ],
    }
    if args.verify_system:
        output["system_check"] = system_check(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"output": str(args.output), "case_count": len(cases)}))


if __name__ == "__main__":
    main()
