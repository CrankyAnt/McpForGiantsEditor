#!/usr/bin/env python3
"""Observe fence hooks in one owned, already-running GIANTS Editor session.

The caller must impose an outer process timeout because Frida attach and RPC
calls do not provide a reliable bounded timeout through this API.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import sys
import time
import traceback
from ctypes import wintypes
from pathlib import Path
from typing import Any

import desktop_endurance_probe as endurance
import desktop_research_controller as controller
import windows_save_probe as save

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
OUTPUT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}\.json$")
RESERVED_DOS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class ProbeError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def output_paths(run: Path, filename: str) -> tuple[Path, Path]:
    supplied = Path(filename)
    if supplied.name != filename or not OUTPUT_NAME.fullmatch(filename):
        raise ProbeError("--output must be a simple .json filename")
    if filename.split(".", 1)[0].upper() in RESERVED_DOS_NAMES:
        raise ProbeError("--output uses a reserved Windows device filename")
    resolved_run = run.resolve(strict=True)
    output = run / supplied
    ready = output.with_name(output.stem + ".ready.json")
    if (
        output.resolve(strict=False).parent != resolved_run
        or ready.resolve(strict=False).parent != resolved_run
    ):
        raise ProbeError("--output resolves outside the selected case")
    if output.exists() or output.is_symlink() or ready.exists() or ready.is_symlink():
        raise ProbeError("refusing to overwrite an existing trace receipt")
    return output, ready


def import_frida(tools: Path | None):
    if tools is not None:
        resolved = tools.resolve(strict=True)
        if not resolved.is_dir():
            raise ProbeError("--tools must name a directory")
        sys.path.insert(0, str(resolved))
    try:
        import frida  # type: ignore
    except ImportError as exc:
        raise ProbeError(
            "Frida is not importable; pass an explicit --tools directory"
        ) from exc
    return frida


def process_is_active(kernel, process) -> None:
    code = wintypes.DWORD()
    if not kernel.GetExitCodeProcess(process, ctypes.byref(code)):
        raise ProbeError("GetExitCodeProcess failed")
    if code.value != STILL_ACTIVE:
        raise ProbeError("owned Editor exited during the fence observation")


def write_new_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def observe(
    case: str, tools: Path | None, duration_seconds: int, output_name: str
) -> tuple[int, dict[str, Any]]:
    if os.name != "nt":
        raise ProbeError("requires Windows")
    if not 1 <= duration_seconds <= 60:
        raise ProbeError("--duration-seconds must be between 1 and 60")
    run = endurance.case_dir(case)
    output, ready = output_paths(run, output_name)
    source = Path(__file__).with_name("editor_fence_trace.js").resolve(strict=True)
    frida = import_frida(tools)
    receipt: dict[str, Any] = {
        "status": "failed",
        "case": case,
        "duration_seconds": duration_seconds,
        "source": {"path": str(source), "sha256": sha256(source)},
        "frida_version": getattr(frida, "__version__", None),
        "started_utc_ns": time.time_ns(),
        "started_monotonic_ns": time.monotonic_ns(),
        "messages": [],
        "errors": [],
    }
    session = script = process = None
    try:
        with controller.owned(case) as (
            _run,
            owned_session,
            kernel,
            _user,
            _callback,
            _desktop,
            _frame,
        ):
            pid = int(owned_session["pid"])
            receipt["pid"] = pid
            receipt["editor"] = save.verify_process(kernel, pid)
            process = kernel.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not process:
                raise ProbeError("cannot open owned Editor PID for liveness pinning")
            process_is_active(kernel, process)
            if not controller.lock_state()["unlocked"]:
                raise ProbeError("session is not unlocked before Frida attach")
            session = frida.attach(pid)
            script = session.create_script(source.read_text(encoding="utf-8"))

            def on_message(message, data):
                value: dict[str, Any] = {"utc_ns": time.time_ns(), "message": message}
                if data is not None:
                    value["data_hex"] = bytes(data).hex()
                receipt["messages"].append(value)
                if isinstance(message, dict) and message.get("type") == "error":
                    receipt["errors"].append(value)

            script.on("message", on_message)
            script.load()
            write_new_json(
                ready,
                {
                    "case": case,
                    "pid": pid,
                    "editor": receipt["editor"],
                    "frida_version": receipt["frida_version"],
                    "source_sha256": receipt["source"]["sha256"],
                    "hooks_loaded_utc_ns": time.time_ns(),
                },
            )
            deadline = time.monotonic() + duration_seconds
            while time.monotonic() < deadline:
                state = controller.lock_state()
                if not state["unlocked"]:
                    raise ProbeError(
                        "session is no longer unlocked during fence observation"
                    )
                time.sleep(0.1)
            process_is_active(kernel, process)
            try:
                receipt["trace"] = script.exports_sync.summary()
            except Exception as exc:  # Frida reports RPC failures as Python exceptions
                raise ProbeError("Frida summary RPC failed: " + str(exc)) from exc
            if isinstance(receipt["trace"], dict) and receipt["trace"].get("truncated"):
                raise ProbeError("Frida trace reports truncation")
            if receipt["errors"]:
                raise ProbeError("Frida emitted one or more script errors")
            receipt["status"] = "completed"
    except Exception as exc:  # noqa: BLE001 - retain observer and RPC failure evidence
        receipt["error"] = str(exc)
        receipt["traceback"] = traceback.format_exc()
    finally:
        if script is not None:
            try:
                script.unload()
            except Exception as exc:  # noqa: BLE001 - cleanup must not mask trace evidence
                receipt.setdefault("cleanup_errors", []).append(
                    "script unload: " + str(exc)
                )
        if session is not None:
            try:
                session.detach()
            except Exception as exc:  # noqa: BLE001 - cleanup must not mask trace evidence
                receipt.setdefault("cleanup_errors", []).append(
                    "session detach: " + str(exc)
                )
        if process is not None:
            try:
                if not kernel.CloseHandle(process):
                    receipt.setdefault("cleanup_errors", []).append(
                        "process handle close returned false"
                    )
            except Exception as exc:  # noqa: BLE001 - cleanup must not mask trace evidence
                receipt.setdefault("cleanup_errors", []).append(
                    "process handle close: " + str(exc)
                )
        receipt["ended_utc_ns"] = time.time_ns()
        receipt["ended_monotonic_ns"] = time.monotonic_ns()
        if receipt.get("cleanup_errors"):
            receipt["status"] = "failed"
        write_new_json(output, receipt)
    return (0 if receipt["status"] == "completed" else 3), receipt


def cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--tools", type=Path)
    parser.add_argument("--duration-seconds", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        code, receipt = observe(
            args.case, args.tools, args.duration_seconds, args.output
        )
    except (OSError, ProbeError) as exc:
        parser.error(str(exc))
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(cli())
