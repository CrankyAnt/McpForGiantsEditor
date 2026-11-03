#!/usr/bin/env python3
"""Read one owned Editor process with the pinned Sysinternals Handle tool."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import subprocess
import time
import winreg
from collections import Counter
from ctypes import wintypes
from pathlib import Path

import desktop_research_controller as controller
import windows_save_probe as save

EXPECTED_HANDLE_SHA256 = (
    "24bafcc570cc9bbb6b6e6652a57a519e0464e3996891aaba6f55299cce20b04f"
)
HANDLE_TIMEOUT_SECONDS = 15
CREATE_NO_WINDOW = 0x08000000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
TYPE_LINE = re.compile(r"^\s*(.+?):\s*(\d+)\s*$")
TOTAL_LINE = re.compile(r"Total handles:\s*(\d+)")
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


def parse_handle_output(text: str) -> tuple[dict[str, int], int]:
    """Aggregate duplicate Handle type rows and validate the declared total."""
    types: Counter[str] = Counter()
    total: int | None = None
    for line in text.splitlines():
        match = TYPE_LINE.match(line)
        if match and match.group(1).strip() != "Total handles":
            types[match.group(1).strip()] += int(match.group(2))
        match = TOTAL_LINE.search(line)
        if match:
            if total is not None:
                raise ProbeError("Handle output contains multiple total rows")
            total = int(match.group(1))
    if total is None:
        raise ProbeError("Handle output lacks Total handles")
    normalized = dict(sorted(types.items()))
    if sum(normalized.values()) != total:
        raise ProbeError("Handle type sum does not match Total handles")
    return normalized, total


def verify_handle_tool(path: Path) -> dict[str, str]:
    resolved = path.resolve(strict=True)
    digest = sha256(resolved)
    if digest != EXPECTED_HANDLE_SHA256:
        raise ProbeError("Handle executable SHA-256 does not match pinned 5.0 binary")
    return {"path": str(resolved), "sha256": digest, "version": "5.0"}


def require_accepted_eula() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Sysinternals\Handle"
        ) as key:
            value, _ = winreg.QueryValueEx(key, "EulaAccepted")
    except FileNotFoundError as exc:
        raise ProbeError("Sysinternals Handle EULA has not been accepted") from exc
    if value != 1:
        raise ProbeError("Sysinternals Handle EulaAccepted must equal 1")


def output_paths(run: Path, filename: str) -> tuple[Path, Path]:
    supplied = Path(filename)
    if supplied.name != filename or not OUTPUT_NAME.fullmatch(filename):
        raise ProbeError("--output must be a simple .json filename")
    if filename.split(".", 1)[0].upper() in RESERVED_DOS_NAMES:
        raise ProbeError("--output uses a reserved Windows device filename")
    resolved_run = run.resolve(strict=True)
    normalized = run / supplied
    raw = normalized.with_name(normalized.stem + ".raw.txt")
    if (
        normalized.resolve(strict=False).parent != resolved_run
        or raw.resolve(strict=False).parent != resolved_run
    ):
        raise ProbeError("--output resolves outside the selected case")
    if (
        normalized.exists()
        or normalized.is_symlink()
        or raw.exists()
        or raw.is_symlink()
    ):
        raise ProbeError("refusing to overwrite an existing Handle receipt")
    return raw, normalized


def process_is_active(kernel, process) -> None:
    code = wintypes.DWORD()
    if not kernel.GetExitCodeProcess(process, ctypes.byref(code)):
        raise ProbeError("GetExitCodeProcess failed")
    if code.value != STILL_ACTIVE:
        raise ProbeError("owned Editor exited before Handle observation completed")


def handle_command(executable: Path, pid: int) -> list[str]:
    command = [str(executable), "-nobanner", "-s", "-p", str(pid)]
    if "-c" in command or "-a" in command:
        raise AssertionError("Handle command must remain read-only")
    return command


def observe(case: str, handle_exe: Path, output: str) -> dict:
    if os.name != "nt":
        raise ProbeError("requires Windows")
    tool = verify_handle_tool(handle_exe)
    require_accepted_eula()
    with controller.owned(case) as (
        run,
        session,
        kernel,
        _user,
        _callback,
        _desk,
        _frame,
    ):
        raw_path, normalized_path = output_paths(run, output)
        pid = int(session["pid"])
        editor = save.verify_process(kernel, pid)
        process = kernel.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not process:
            raise ProbeError("cannot open owned Editor PID for liveness pinning")
        try:
            process_is_active(kernel, process)
            command = handle_command(handle_exe.resolve(strict=True), pid)
            started_utc_ns, started_monotonic_ns = time.time_ns(), time.monotonic_ns()
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=HANDLE_TIMEOUT_SECONDS,
                    creationflags=CREATE_NO_WINDOW,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ProbeError(
                    "Handle observation timed out after 15 seconds"
                ) from exc
            ended_utc_ns, ended_monotonic_ns = time.time_ns(), time.monotonic_ns()
            if completed.returncode != 0:
                raise ProbeError("Handle observation returned a non-zero exit code")
            types, total = parse_handle_output(completed.stdout)
            process_is_active(kernel, process)
            with raw_path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(completed.stdout)
            receipt = {
                "case": case,
                "pid": pid,
                "editor": editor,
                "handle_tool": tool,
                "command": command,
                "started_utc_ns": started_utc_ns,
                "started_monotonic_ns": started_monotonic_ns,
                "ended_utc_ns": ended_utc_ns,
                "ended_monotonic_ns": ended_monotonic_ns,
                "elapsed_ms": (ended_monotonic_ns - started_monotonic_ns) / 1_000_000,
                "raw_file": raw_path.name,
                "total": total,
                "type_counts": types,
            }
            with normalized_path.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(receipt, stream, indent=2, sort_keys=True)
                stream.write("\n")
            return receipt
        finally:
            if not kernel.CloseHandle(process):
                raise ProbeError("cannot close liveness pin handle")


def cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--handle-exe", type=Path, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(observe(args.case, args.handle_exe, args.output), indent=2))
    except (OSError, ProbeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(cli())
