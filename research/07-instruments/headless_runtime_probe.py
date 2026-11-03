#!/usr/bin/env python3
"""Run one reviewed GIANTS Editor true-headless experiment on a private desktop.

The launcher never switches desktops, activates a window, injects input, or
falls back to the default desktop.  It starts only the pinned Editor binary on
a fresh private Win32 desktop.  Frida attaches while the primary thread is
suspended, before the process can create a frame.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
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
CREATE_SUSPENDED = private.CREATE_SUSPENDED
CREATE_UNICODE_ENVIRONMENT = private.CREATE_UNICODE_ENVIRONMENT
STARTF_USESHOWWINDOW, SW_HIDE = 0x00000001, 0
WAIT_TIMEOUT = private.WAIT_TIMEOUT
CASE_RE = r"[a-z][a-z0-9-]{0,47}"
MODES = (
    "baseline",
    "sw-hide",
    "force-hidden",
    "deny-windows",
    "deny-editor-frame",
    "force-null",
    "force-d3d12",
    "force-gnm",
    "force-ps5",
    "force-nvn",
    "force-metal",
    "force-null-tracking",
)
RESULT_FILES = (
    "result.xml",
    "input-editor.xml",
    "frida-messages.jsonl",
    "frida-errors.jsonl",
    "telemetry.jsonl",
    "summary.json",
    "summary.json.tmp",
)
TOOLING_ROOT = Path(r"C:\TMP\giants-headless-tooling")
PYTHON_REAL = Path(sys.executable)


class ProbeError(RuntimeError):
    """The reviewed experiment did not meet its containment contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, sort_keys=True) + "\n")


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
    os.replace(temporary, path)


def cleanup_call(summary: dict[str, Any], label: str, action) -> Any:
    try:
        return action()
    except Exception as exc:  # noqa: BLE001 - preserve cleanup evidence
        summary.setdefault("cleanup_errors", []).append(label + ": " + str(exc))
        return None


def repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def runtime_root() -> Path:
    return (repo_root() / ".docs/giants-editor-headless/runtime").resolve()


def case_dir(case: str) -> Path:
    if not re.fullmatch(CASE_RE, case):
        raise ProbeError("case must match " + CASE_RE)
    root = runtime_root()
    if not root.is_dir():
        raise ProbeError("headless runtime root is missing")
    run = (root / case).resolve()
    if not run.is_relative_to(root):
        raise ProbeError("case resolves outside the dedicated runtime root")
    if not run.is_dir():
        raise ProbeError(
            "case must be prepared as a new directory under the runtime root"
        )
    return run


def load_case(
    case: str, mode: str, extra_args_file: str | None
) -> tuple[Path, dict[str, Any], Path, list[str], dict[str, str]]:
    run = case_dir(case)
    existing = [name for name in RESULT_FILES if (run / name).exists()]
    if existing:
        raise ProbeError("case contains prior output: " + ", ".join(existing))
    spec_path = run / "spec.json"
    config = run / "editor.xml"
    lua = run / "probe.lua"
    hooks = Path(__file__).with_name("headless_runtime_hooks.js").resolve()
    for path in (spec_path, config, lua, hooks):
        if not path.is_file():
            raise ProbeError("required reviewed input is missing: " + str(path))
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProbeError("spec.json is not JSON") from exc
    if not isinstance(spec, dict) or not isinstance(spec.get("scene"), str):
        raise ProbeError("spec.json requires a string scene")
    if spec.get("mode") != mode:
        raise ProbeError("selected mode does not match the prepared case spec")
    scene = Path(spec["scene"]).resolve(strict=True)
    if not scene.is_relative_to(run):
        raise ProbeError("spec scene must be beneath its prepared case directory")
    target = spec.get("target")
    if target is not None and not isinstance(target, str):
        raise ProbeError("spec target must be a string when supplied")
    extra = spec.get("extra_args", [])
    if not isinstance(extra, list) or not all(isinstance(item, str) for item in extra):
        raise ProbeError("spec extra_args must be an array of strings")
    if extra_args_file:
        path = Path(extra_args_file).resolve(strict=True)
        if not path.is_relative_to(run):
            raise ProbeError("extra arguments file must be beneath its prepared case")
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProbeError("extra arguments file is not JSON") from exc
        if not isinstance(loaded, list) or not all(
            isinstance(item, str) for item in loaded
        ):
            raise ProbeError("extra arguments JSON must be an array of strings")
        if loaded != extra:
            raise ProbeError(
                "extra arguments file does not match prepared spec extra_args"
            )
    inputs = {
        str(path.relative_to(run)): sha256(path) for path in (spec_path, config, lua)
    }
    inputs["hooks"] = sha256(hooks)
    inputs["editor.exe"] = save.sha256(save.EXPECTED_EXE)
    if inputs["editor.exe"] != save.EXPECTED_SHA256:
        raise ProbeError("Editor executable hash differs from pinned build")
    return run, spec, scene, extra, inputs


def start_editor(
    k, desktop: str, editor_args: list[str], show_hidden: bool
) -> private.PI:
    """Reuse the private launcher, adding only the reviewed SW_HIDE variant."""
    if not show_hidden:
        return private.start_editor(k, desktop, editor_args)
    exe = Path(editor_args[0]).resolve(strict=True)
    if save.sha256(exe) != save.EXPECTED_SHA256:
        raise ProbeError("Editor executable hash differs from pinned build")
    startup = private.SI(
        cb=ctypes.sizeof(private.SI),
        desktop=f"WinSta0\\{desktop}",
        flags=private.STARTF_FORCEOFFFEEDBACK | STARTF_USESHOWWINDOW,
        show=SW_HIDE,
    )
    process = private.PI()
    command = ctypes.create_unicode_buffer(
        subprocess.list2cmdline([str(exe), *editor_args[1:]])
    )
    if not k.CreateProcessW(
        str(exe),
        command,
        None,
        None,
        False,
        CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT,
        None,
        str(exe.parent),
        ctypes.byref(startup),
        ctypes.byref(process),
    ):
        private.err("CreateProcessW private Editor failed")
    return process


def import_frida():
    if not PYTHON_REAL.is_file():
        raise ProbeError("the configured real Python runtime is unavailable")
    if not TOOLING_ROOT.is_dir():
        raise ProbeError("the configured Frida 17.24.0 tooling root is unavailable")
    if str(TOOLING_ROOT) not in sys.path:
        sys.path.insert(0, str(TOOLING_ROOT))
    try:
        import frida  # type: ignore
    except ImportError as exc:
        raise ProbeError(
            "Frida 17.24.0 is not importable from the configured tooling root"
        ) from exc
    return frida


def monitored_snapshot(user32, callback, desktop, editor_pid: int) -> dict[str, Any]:
    state = private.snapshot(user32, callback, editor_pid)
    return {
        "private_hwnds": private.private_hwnds(user32, callback, desktop, editor_pid),
        **state,
    }


def unsafe(state: dict[str, Any], before_input: str, pid: int) -> bool:
    return (
        state["input_desktop"] != before_input
        or bool(state["editor_hwnds_on_input"])
        or state["foreground_pid"] == pid
    )


def valid_result(path: Path, started_ns: int, scene: Path) -> bool:
    if not path.is_file() or path.stat().st_mtime_ns < started_ns:
        return False
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return False
    return (
        root.tag == "probe"
        and root.findtext("ok") == "true"
        and root.findtext("scene") == scene.as_posix()
        and int(root.findtext("root", "0")) > 0
        and int(root.findtext("children", "0")) > 0
    )


def main(args: argparse.Namespace) -> int:
    run, spec, scene, extra_args, input_hashes = load_case(
        args.case, args.mode, args.extra_args
    )
    if args.timeout < 1 or args.timeout > 60:
        raise ProbeError("timeout must be between 1 and 60 seconds")
    k, u, callback = private.winapi()
    if private.window_station(u) != "WinSta0":
        raise ProbeError("private desktop requires WinSta0")
    original = u.GetThreadDesktop(k.GetCurrentThreadId())
    if not original:
        private.err("GetThreadDesktop original failed")
    original_name = private.desk_name(u, original)
    desktop_name = "GiantsHeadless_" + uuid.uuid4().hex
    started_ns = time.time_ns()
    summary: dict[str, Any] = {
        "case": args.case,
        "mode": args.mode,
        "scene": str(scene),
        "target": spec.get("target"),
        "input_hashes_before_start": input_hashes,
        "program_instrument_sha256": sha256(Path(__file__).resolve()),
        "requested_renderer": ET.parse(run / "editor.xml")
        .getroot()
        .findtext("graphic/renderer"),
        "desktop": desktop_name,
        "controller_desktop": original_name,
        "status": "failed",
    }
    result = run / "result.xml"
    message_log = run / "frida-messages.jsonl"
    error_log = run / "frida-errors.jsonl"
    telemetry = run / "telemetry.jsonl"
    desk = job = process = thread = session = script = None
    pid: int | None = None
    try:
        input_config = run / "input-editor.xml"
        with (
            (run / "editor.xml").open("rb") as source,
            input_config.open("xb") as destination,
        ):
            shutil.copyfileobj(source, destination)
        summary["input_config_filename"] = input_config.name
        desk = u.CreateDesktopW(desktop_name, None, None, 0, CREATE | READ, None)
        if not desk:
            private.err("CreateDesktopW failed")
        if private.current_desk(k, u) != original_name:
            if not u.SetThreadDesktop(original):
                private.err("SetThreadDesktop original failed")
            if private.current_desk(k, u) != original_name:
                raise ProbeError("launcher cannot return to its original desktop")
        before = private.snapshot(u, callback)
        summary["input_before"] = before
        if before["input_desktop"] == desktop_name:
            raise ProbeError("new private desktop is unexpectedly the input desktop")
        lua_code = (
            "HEADLESS_PROBE_ROOT="
            + repr(scene.parent.as_posix() + "/")
            + ";source("
            + repr((run / "probe.lua").as_posix())
            + ")"
        )
        editor_args = [
            str(save.EXPECTED_EXE),
            str(scene),
            "-noVersionSelection",
            "-supressChangelog",
            "-disableTextureStreaming",
            "-runScriptCode",
            lua_code,
            "-configXML",
            str((run / "editor.xml").resolve()),
            *extra_args,
        ]
        summary["editor_args"] = editor_args
        job = private.new_job(k)
        pi = start_editor(k, desktop_name, editor_args, args.mode == "sw-hide")
        process, thread, pid = pi.process, pi.thread, int(pi.pid)
        summary["pid"] = pid
        if not k.AssignProcessToJobObject(job, process):
            private.err("AssignProcessToJobObject failed")
        state = monitored_snapshot(u, callback, desk, pid)
        append_jsonl(
            telemetry, {"time_ns": time.time_ns(), "phase": "suspended", **state}
        )
        if unsafe(state, before["input_desktop"], pid):
            raise ProbeError("containment monitor detected unsafe state before resume")
        frida = import_frida()
        hook_source = (
            "const PROBE_MODE = "
            + json.dumps(args.mode)
            + ";\n"
            + Path(__file__)
            .with_name("headless_runtime_hooks.js")
            .read_text(encoding="utf-8")
        )
        session = frida.attach(pid)
        script = session.create_script(hook_source)
        instrumentation_ready = threading.Event()

        def on_message(message, data):
            record: dict[str, Any] = {"time_ns": time.time_ns(), "message": message}
            if data is not None:
                record["data_hex"] = bytes(data).hex()
            append_jsonl(message_log, record)
            if message.get("type") == "error":
                append_jsonl(error_log, record)
            payload = message.get("payload") if isinstance(message, dict) else None
            if (
                isinstance(payload, dict)
                and payload.get("event") == "instrumentation_ready"
            ):
                instrumentation_ready.set()

        script.on("message", on_message)
        script.load()
        if not instrumentation_ready.wait(timeout=2):
            raise ProbeError("Frida did not report instrumentation_ready before resume")
        if k.ResumeThread(thread) == 0xFFFFFFFF:
            private.err("ResumeThread failed")
        private.close(k, thread)
        thread = None
        deadline = time.monotonic() + args.timeout
        result_seen_ns: int | None = None
        while k.WaitForSingleObject(process, 50) == WAIT_TIMEOUT:
            state = monitored_snapshot(u, callback, desk, pid)
            append_jsonl(
                telemetry, {"time_ns": time.time_ns(), "phase": "running", **state}
            )
            if unsafe(state, before["input_desktop"], pid):
                raise ProbeError(
                    "containment monitor detected input desktop, Editor input window, or Editor foreground"
                )
            if result_seen_ns is None and valid_result(result, started_ns, scene):
                result_seen_ns = time.time_ns()
                append_jsonl(
                    telemetry, {"time_ns": result_seen_ns, "phase": "lua-result-ready"}
                )
            if time.monotonic() >= deadline:
                raise ProbeError("headless runtime timeout elapsed")
        state = monitored_snapshot(u, callback, desk, pid)
        append_jsonl(telemetry, {"time_ns": time.time_ns(), "phase": "exited", **state})
        if unsafe(state, before["input_desktop"], pid):
            raise ProbeError("final containment monitor sample is unsafe")
        exit_code = wintypes.DWORD()
        if not k.GetExitCodeProcess(process, ctypes.byref(exit_code)):
            private.err("GetExitCodeProcess failed")
        summary.update(
            {
                "exit_code": exit_code.value,
                "input_final": state,
                "result_ready": valid_result(result, started_ns, scene),
                "result_seen_ns": result_seen_ns,
            }
        )
        if not summary["result_ready"]:
            raise ProbeError(
                "Editor exited without a fresh parseable Lua result.xml receipt"
            )
        if exit_code.value != 0:
            raise ProbeError("Editor exited with a non-zero code")
        summary["status"] = "completed"
        return 0
    except Exception as exc:  # noqa: BLE001 - records unexpected controller failure
        summary["error"] = str(exc)
        summary["traceback"] = traceback.format_exc()
        append_jsonl(
            error_log,
            {
                "time_ns": time.time_ns(),
                "error": str(exc),
                "traceback": summary["traceback"],
            },
        )
        return 1
    finally:
        process_alive = (
            bool(process) and k.WaitForSingleObject(process, 0) == WAIT_TIMEOUT
        )
        if script and process_alive:
            try:
                script.unload()
            except Exception as exc:  # noqa: BLE001 - cleanup evidence
                summary.setdefault("cleanup_errors", []).append(
                    "Frida script unload: " + str(exc)
                )
        if session and process_alive:
            try:
                session.detach()
            except Exception as exc:  # noqa: BLE001 - cleanup evidence
                summary.setdefault("cleanup_errors", []).append(
                    "Frida detach: " + str(exc)
                )
        if thread:
            cleanup_call(
                summary, "CloseHandle thread", lambda: private.close(k, thread)
            )
        if process:
            if k.WaitForSingleObject(process, 0) == WAIT_TIMEOUT:
                terminated = cleanup_call(
                    summary, "TerminateProcess", lambda: k.TerminateProcess(process, 1)
                )
                if not terminated:
                    summary.setdefault("cleanup_errors", []).append(
                        "TerminateProcess returned false (Win32 error "
                        + str(ctypes.get_last_error())
                        + ")"
                    )
                waited = cleanup_call(
                    summary,
                    "WaitForSingleObject after TerminateProcess",
                    lambda: k.WaitForSingleObject(process, 5000),
                )
                if waited != private.WAIT_OBJECT_0:
                    summary.setdefault("cleanup_errors", []).append(
                        "terminated process did not reach WAIT_OBJECT_0"
                    )
                else:
                    exit_code = wintypes.DWORD()
                    if k.GetExitCodeProcess(process, ctypes.byref(exit_code)):
                        summary["terminated_exit_code"] = exit_code.value
                    else:
                        summary.setdefault("cleanup_errors", []).append(
                            "GetExitCodeProcess after terminate failed (Win32 error "
                            + str(ctypes.get_last_error())
                            + ")"
                        )
                summary["terminated_by_launcher"] = True
            cleanup_call(
                summary, "CloseHandle process", lambda: private.close(k, process)
            )
        if job:
            cleanup_call(summary, "CloseHandle job", lambda: private.close(k, job))
        if desk:
            current = cleanup_call(
                summary,
                "GetThreadDesktop during cleanup",
                lambda: private.current_desk(k, u),
            )
            if current != original_name and not u.SetThreadDesktop(original):
                summary.setdefault("cleanup_errors", []).append(
                    "SetThreadDesktop original failed (Win32 error "
                    + str(ctypes.get_last_error())
                    + ")"
                )
            if not u.CloseDesktop(desk):
                summary.setdefault("cleanup_errors", []).append(
                    "CloseDesktop private failed (Win32 error "
                    + str(ctypes.get_last_error())
                    + ")"
                )
            reopened = u.OpenDesktopW(desktop_name, 0, False, READ)
            open_error = ctypes.get_last_error()
            summary["desktop_absent_after_close"] = (
                not bool(reopened) and open_error == 2
            )
            summary["desktop_open_error_after_close"] = open_error
            if reopened:
                u.CloseDesktop(reopened)
        summary["ended_ns"] = time.time_ns()
        write_json_atomic(run / "summary.json", summary)


def cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument(
        "--extra-args", help="Reviewed JSON array under the selected case directory"
    )
    args = parser.parse_args()
    try:
        return main(args)
    except ProbeError as exc:
        parser.error(str(exc))
    except OSError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(cli())
