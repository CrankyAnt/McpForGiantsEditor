#!/usr/bin/env python3
"""Run a prepared GIANTS Editor endurance case on a private Win32 desktop.

The probe never switches the input desktop, activates a window, injects input,
or changes the lock state.  It records an unavailable input desktop as an
observation, not proof that the workstation is locked.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import sys
import time
import traceback
import uuid
import xml.etree.ElementTree as ET
from ctypes import wintypes
from pathlib import Path
from typing import Any

import private_desktop_probe as private
import windows_save_probe as save

READ, CREATE = private.READ, private.CREATE
WAIT_OBJECT_0, WAIT_TIMEOUT = private.WAIT_OBJECT_0, private.WAIT_TIMEOUT
CASE_RE = r"[a-z][a-z0-9-]{0,47}"
DESKTOP_PREFIX = "GiantsEndurance_"
POLL_SECONDS = 0.2
READY_TIMEOUT_SECONDS = 45
MIN_DURATION_SECONDS, MAX_DURATION_SECONDS = 60, 3600
OUTPUTS = (
    "session.json",
    "lock-window.json",
    "lock-scope.json",
    "ready.xml",
    "done.xml",
    "telemetry.jsonl",
    "summary.json",
    "summary.json.tmp",
    "input-editor.xml",
    "input-probe.lua",
    "input-replacement.xml",
)


class ProbeError(RuntimeError):
    pass


class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
    os.replace(temporary, path)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, sort_keys=True) + "\n")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def endurance_root() -> Path:
    root = (repo_root() / ".docs/giants-editor-desktop/endurance").resolve()
    if not root.is_dir():
        raise ProbeError("prepared endurance root is missing")
    return root


def case_dir(case: str) -> Path:
    if not re.fullmatch(CASE_RE, case):
        raise ProbeError("case must match " + CASE_RE)
    root = endurance_root()
    run = (root / case).resolve()
    if not run.is_relative_to(root) or not run.is_dir():
        raise ProbeError("case must be a prepared directory beneath the endurance root")
    return run


def load_case(
    case: str,
) -> tuple[Path, dict[str, Any], Path, Path, Path, dict[str, str]]:
    run = case_dir(case)
    stale = [name for name in OUTPUTS if (run / name).exists()]
    stale.extend(path.name for path in run.glob("response-*.xml"))
    stale.extend(path.name for path in run.glob("save-*.xml"))
    if stale:
        raise ProbeError("case contains prior output: " + ", ".join(stale))
    spec_path, config = run / "spec.json", run / "editor.xml"
    for path in (spec_path, config):
        if not path.is_file():
            raise ProbeError("required prepared input is missing: " + str(path))
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProbeError("spec.json is not JSON") from exc
    if (
        not isinstance(spec, dict)
        or not isinstance(spec.get("scene"), str)
        or not isinstance(spec.get("target"), str)
    ):
        raise ProbeError("spec.json requires string scene and target values")
    scene = Path(spec["scene"]).resolve(strict=True)
    if not scene.is_relative_to(run):
        raise ProbeError("spec scene must be beneath its prepared case directory")
    bridge = spec.get("bridge", "desktop_endurance_probe.lua")
    if bridge not in ("desktop_endurance_probe.lua", "replacement_scene_probe.lua"):
        raise ProbeError("unsupported research bridge")
    source_lua = Path(__file__).with_name(bridge).resolve(strict=True)
    inputs = {str(item.relative_to(run)): sha256(item) for item in (spec_path, config)}
    if bridge == "replacement_scene_probe.lua":
        replacement_config = run / "replacement.xml"
        if not replacement_config.is_file():
            raise ProbeError("required replacement.xml is missing")
        inputs["replacement.xml"] = sha256(replacement_config)
    inputs[source_lua.name] = sha256(source_lua)
    inputs["editor.exe"] = save.sha256(save.EXPECTED_EXE)
    if inputs["editor.exe"] != save.EXPECTED_SHA256:
        raise ProbeError("Editor executable hash differs from pinned build")
    return run, spec, scene, config, source_lua, inputs


def configure_extra_api(k, u):
    u.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    u.GetClassNameW.restype = ctypes.c_int
    u.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    u.GetWindow.restype = wintypes.HWND
    u.IsWindowEnabled.argtypes = (wintypes.HWND,)
    u.IsWindowEnabled.restype = wintypes.BOOL
    k.GetProcessHandleCount.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    k.GetProcessHandleCount.restype = wintypes.BOOL
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX),
        wintypes.DWORD,
    )
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    return psapi


def private_inventory(u, callback, desktop, pid: int) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []

    @callback
    def scan(hwnd, _):
        owner_pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_pid))
        if owner_pid.value == pid:
            text = ctypes.create_unicode_buffer(32768)
            class_name = ctypes.create_unicode_buffer(256)
            u.GetWindowTextW(hwnd, text, len(text))
            u.GetClassNameW(hwnd, class_name, len(class_name))
            owner = u.GetWindow(hwnd, 4)  # GW_OWNER
            windows.append(
                {
                    "hwnd": f"0x{int(hwnd):x}",
                    "class": class_name.value,
                    "title": text.value,
                    "visible": bool(u.IsWindowVisible(hwnd)),
                    "enabled": bool(u.IsWindowEnabled(hwnd)),
                    "owner_hwnd": f"0x{int(owner or 0):x}",
                }
            )
        return True

    ctypes.set_last_error(0)
    if not u.EnumDesktopWindows(desktop, scan, 0) and ctypes.get_last_error():
        private.err("EnumDesktopWindows private failed")
    return windows


def input_state(u, callback, pid: int) -> dict[str, Any]:
    desktop = u.OpenInputDesktop(0, False, READ)
    if not desktop:
        code = ctypes.get_last_error()
        return {"state": "input_unavailable", "win32_error": code}
    try:
        name = private.desk_name(u, desktop)
        if name != "Default":
            return {"state": "non_default_input", "input_desktop": name}
        editor_hwnds: list[str] = []

        @callback
        def scan(hwnd, _):
            owner = wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid:
                editor_hwnds.append(f"0x{int(hwnd):x}")
            return True

        if not u.EnumDesktopWindows(desktop, scan, 0):
            private.err("EnumDesktopWindows input failed")
        foreground = u.GetForegroundWindow()
        foreground_pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(foreground, ctypes.byref(foreground_pid))
        return {
            "state": "observable",
            "input_desktop": private.desk_name(u, desktop),
            "foreground_hwnd": f"0x{int(foreground or 0):x}",
            "foreground_pid": foreground_pid.value,
            "editor_hwnds_on_input": editor_hwnds,
        }
    finally:
        if not u.CloseDesktop(desktop):
            private.err("CloseDesktop input failed")


def unsafe_input(state: dict[str, Any], desktop_name: str, pid: int) -> bool:
    return state.get("input_desktop") == desktop_name or (
        state.get("state") == "observable"
        and (
            state.get("input_desktop") == desktop_name
            or bool(state.get("editor_hwnds_on_input"))
            or state.get("foreground_pid") == pid
        )
    )


def process_metrics(k, psapi, process) -> dict[str, int | None]:
    handles = wintypes.DWORD()
    counters = PROCESS_MEMORY_COUNTERS_EX(cb=ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX))
    has_handles = bool(k.GetProcessHandleCount(process, ctypes.byref(handles)))
    has_memory = bool(
        psapi.GetProcessMemoryInfo(
            process, ctypes.byref(counters), ctypes.sizeof(counters)
        )
    )
    return {
        "handle_count": handles.value if has_handles else None,
        "working_set_bytes": counters.WorkingSetSize if has_memory else None,
        "private_usage_bytes": counters.PrivateUsage if has_memory else None,
    }


def title_for(scene: Path) -> str:
    return "GIANTS Editor 64bit 10.0.14 - " + scene.as_posix()


def valid_receipt(path: Path, expected_op: str, started_ns: int, scene: Path) -> bool:
    if not path.is_file() or path.stat().st_mtime_ns < started_ns:
        return False
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return False
    return (
        root.findtext("ok") == "true"
        and root.findtext("op") == expected_op
        and root.findtext("scene") == scene.as_posix()
    )


def launch(args: argparse.Namespace) -> int:
    if not MIN_DURATION_SECONDS <= args.duration_seconds <= MAX_DURATION_SECONDS:
        raise ProbeError("duration must be between 60 and 3600 seconds")
    run, spec, scene, config, source_lua, inputs = load_case(args.case)
    k, u, callback = private.winapi()
    psapi = configure_extra_api(k, u)
    if private.window_station(u) != "WinSta0":
        raise ProbeError("private desktop requires WinSta0")
    original = u.GetThreadDesktop(k.GetCurrentThreadId())
    if not original:
        private.err("GetThreadDesktop original failed")
    original_name = private.desk_name(u, original)
    desktop_name = DESKTOP_PREFIX + uuid.uuid4().hex
    started_ns, started_monotonic = time.time_ns(), time.monotonic()
    summary: dict[str, Any] = {
        "status": "failed",
        "case": args.case,
        "scene": str(scene),
        "desktop": desktop_name,
        "controller_desktop": original_name,
        "started_utc_ns": started_ns,
        "started_monotonic_ns": time.monotonic_ns(),
        "duration_seconds": args.duration_seconds,
        "input_hashes_before_start": inputs,
        "instrument_sha256": sha256(Path(__file__).resolve()),
    }
    telemetry, ready, done = (
        run / "telemetry.jsonl",
        run / "ready.xml",
        run / "done.xml",
    )
    desktop = job = process = thread = None
    pid: int | None = None
    try:
        input_config = run / "input-editor.xml"
        with config.open("rb") as source, input_config.open("xb") as destination:
            shutil.copyfileobj(source, destination)
        input_lua = run / "input-probe.lua"
        with source_lua.open("rb") as source, input_lua.open("xb") as destination:
            shutil.copyfileobj(source, destination)
        if spec.get("bridge") == "replacement_scene_probe.lua":
            with (
                (run / "replacement.xml").open("rb") as source,
                (run / "input-replacement.xml").open("xb") as destination,
            ):
                shutil.copyfileobj(source, destination)
        summary["input_lua_filename"] = input_lua.name
        summary["input_config_filename"] = input_config.name
        summary["input_config_sha256"] = sha256(input_config)
        desktop = u.CreateDesktopW(desktop_name, None, None, 0, CREATE | READ, None)
        if not desktop:
            private.err("CreateDesktopW failed")
        if private.current_desk(k, u) != original_name and not u.SetThreadDesktop(
            original
        ):
            private.err("restore original desktop before observation failed")
        before = input_state(u, callback, 0)
        summary["input_before"] = before
        if (
            before.get("state") == "observable"
            and before.get("input_desktop") == desktop_name
        ):
            raise ProbeError("new private desktop is unexpectedly the input desktop")
        code = (
            "PROBE_ROOT=" + repr(run.as_posix() + "/") + ";"
            "PROBE_EXPECTED_SCENE=" + repr(scene.as_posix()) + ";"
            "PROBE_EXPECTED_TARGET=" + repr(spec["target"]) + ";"
            "PROBE_DURATION_SECONDS="
            + repr(args.duration_seconds)
            + ";source("
            + repr(input_lua.as_posix())
            + ")"
        )
        editor_args = [
            str(save.EXPECTED_EXE),
            str(scene),
            "-noVersionSelection",
            "-supressChangelog",
            "-disableTextureStreaming",
            "-runScriptCode",
            code,
            "-configXML",
            str(config.resolve()),
        ]
        summary["editor_args"] = editor_args
        job = private.new_job(k)
        pi = private.start_editor(k, desktop_name, editor_args)
        process, thread, pid = pi.process, pi.thread, int(pi.pid)
        summary["pid"] = pid
        if not k.AssignProcessToJobObject(job, process):
            private.err("AssignProcessToJobObject failed")
        state = input_state(u, callback, pid)
        append_jsonl(
            telemetry,
            {
                "utc_ns": time.time_ns(),
                "monotonic_ns": time.monotonic_ns(),
                "phase": "suspended",
                "input": state,
                "private_windows": private_inventory(u, callback, desktop, pid),
                **process_metrics(k, psapi, process),
            },
        )
        if unsafe_input(state, desktop_name, pid):
            raise ProbeError(
                "containment monitor found the Editor on the observable input desktop before resume"
            )
        if k.ResumeThread(thread) == 0xFFFFFFFF:
            private.err("ResumeThread failed")
        private.close(k, thread)
        thread = None
        ready_deadline = time.monotonic() + READY_TIMEOUT_SECONDS
        frame: dict[str, Any] | None = None
        while k.WaitForSingleObject(process, 0) == WAIT_TIMEOUT:
            now = time.monotonic()
            state = input_state(u, callback, pid)
            sample = {
                "utc_ns": time.time_ns(),
                "monotonic_ns": time.monotonic_ns(),
                "phase": "running",
                "input": state,
                "private_windows": private_inventory(u, callback, desktop, pid),
                **process_metrics(k, psapi, process),
            }
            append_jsonl(telemetry, sample)
            if unsafe_input(state, desktop_name, pid):
                raise ProbeError(
                    "containment monitor found the Editor on the observable input desktop"
                )
            if state.get("state") == "input_unavailable":
                append_jsonl(
                    telemetry,
                    {
                        "utc_ns": time.time_ns(),
                        "monotonic_ns": time.monotonic_ns(),
                        "event": "input_unavailable",
                        "win32_error": state.get("win32_error"),
                    },
                )
            if frame is None and valid_receipt(ready, "ready", started_ns, scene):
                if not u.SetThreadDesktop(desktop):
                    private.err("SetThreadDesktop private frame verification failed")
                try:
                    frame = private.private_frame(
                        k, u, callback, desktop, pid, title_for(scene)
                    )
                    frame["title"] = title_for(scene)
                finally:
                    if not u.SetThreadDesktop(original):
                        private.err(
                            "SetThreadDesktop original after frame verification failed"
                        )
                session = {
                    "pid": pid,
                    "desktop": desktop_name,
                    "title": title_for(scene),
                    "private_frame": frame,
                    "scene": str(scene),
                    "case": args.case,
                    "input_before": before,
                    "instrument_sha256": summary["instrument_sha256"],
                }
                write_json_atomic(run / "session.json", session)
                summary["session_written_utc_ns"] = time.time_ns()
            if frame is None and now >= ready_deadline:
                raise ProbeError("45 second ready receipt deadline elapsed")
            if valid_receipt(done, "done", started_ns, scene):
                summary["done_receipt_seen_utc_ns"] = time.time_ns()
            if now - started_monotonic >= args.duration_seconds:
                summary["duration_cap_reached"] = True
                break
            time.sleep(POLL_SECONDS)
        if frame is None:
            raise ProbeError("Editor exited before a fresh ready receipt")
        if k.WaitForSingleObject(process, 0) == WAIT_OBJECT_0:
            exit_code = wintypes.DWORD()
            if not k.GetExitCodeProcess(process, ctypes.byref(exit_code)):
                private.err("GetExitCodeProcess failed")
            summary["editor_exit_code"] = exit_code.value
        summary["status"] = "completed"
        return 0
    except Exception as exc:  # noqa: BLE001 - retain unexpected native-probe failures
        summary["error"] = str(exc)
        summary["traceback"] = traceback.format_exc()
        return 1
    finally:
        if thread:
            try:
                private.close(k, thread)
            except Exception as exc:  # noqa: BLE001 - preserve cleanup failure evidence
                summary.setdefault("cleanup_errors", []).append(
                    "CloseHandle thread: " + str(exc)
                )
        if process:
            if k.WaitForSingleObject(process, 0) == WAIT_TIMEOUT:
                if k.TerminateProcess(process, 1):
                    summary["terminated_by_launcher"] = True
                    waited = k.WaitForSingleObject(process, 5000)
                    summary["termination_wait_confirmed"] = waited == WAIT_OBJECT_0
                    if waited != WAIT_OBJECT_0:
                        summary.setdefault("cleanup_errors", []).append(
                            "owned process did not exit within termination wait"
                        )
                else:
                    summary.setdefault("cleanup_errors", []).append(
                        "TerminateProcess failed: " + str(ctypes.get_last_error())
                    )
            try:
                private.close(k, process)
            except Exception as exc:  # noqa: BLE001 - preserve cleanup failure evidence
                summary.setdefault("cleanup_errors", []).append(
                    "CloseHandle process: " + str(exc)
                )
        if job:
            try:
                private.close(k, job)
            except Exception as exc:  # noqa: BLE001 - preserve cleanup failure evidence
                summary.setdefault("cleanup_errors", []).append(
                    "CloseHandle job: " + str(exc)
                )
        if desktop:
            if private.current_desk(k, u) != original_name and not u.SetThreadDesktop(
                original
            ):
                summary.setdefault("cleanup_errors", []).append(
                    "SetThreadDesktop original failed: " + str(ctypes.get_last_error())
                )
            if not u.CloseDesktop(desktop):
                summary.setdefault("cleanup_errors", []).append(
                    "CloseDesktop private failed: " + str(ctypes.get_last_error())
                )
            reopened = u.OpenDesktopW(desktop_name, 0, False, READ)
            summary["desktop_absent_after_close"] = (
                not bool(reopened) and ctypes.get_last_error() == 2
            )
            if reopened:
                u.CloseDesktop(reopened)
        summary["ended_utc_ns"] = time.time_ns()
        summary["ended_monotonic_ns"] = time.monotonic_ns()
        write_json_atomic(run / "summary.json", summary)


def cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--duration-seconds", type=int, default=900)
    args = parser.parse_args()
    return launch(args)


if __name__ == "__main__":
    try:
        raise SystemExit(cli())
    except ProbeError as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
