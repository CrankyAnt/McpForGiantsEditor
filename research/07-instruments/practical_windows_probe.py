"""Research-only native commands for the two isolated FS25 practical fixtures.

Does not launch, restore or activate Editor. Mutating calls require a minimized
Editor with another process in the foreground. Completion needs Lua/file receipts.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import time
from ctypes import wintypes
from pathlib import Path
from xml.etree import ElementTree

import windows_save_probe as base
import windows_script_probe as script

SCRATCH = Path(__file__).resolve().parents[6] / ".docs/giants-editor-practical"
ASSETS = {
    "water-trailer": "waterTrailer550.i3d",
    "animated-gate": "sentinelGarage_gate_animation.i3d",
}


TARGET_NAMES = {
    "water-trailer": "agi550_main_component1",
    "animated-gate": "sentinelGarageSliding01",
}


def verify_copy(label, title):
    if label not in ASSETS:
        raise base.ProbeError("unsupported practical fixture")
    run = (SCRATCH / label).resolve(strict=True)
    scene = (run / "asset" / ASSETS[label]).resolve(strict=True)
    if not scene.is_relative_to(SCRATCH.resolve(strict=True)):
        raise base.ProbeError("fixture resolves outside practical scratch root")
    prefix = "GIANTS Editor 64bit 10.0.14 - "
    if not title.startswith(prefix):
        raise base.ProbeError("unexpected Editor title prefix")
    if base.normalized_path(Path(title[len(prefix) :])) != base.normalized_path(scene):
        raise base.ProbeError("Editor title does not name the practical scratch copy")
    spec = json.loads((run / "spec.json").read_text(encoding="utf-8"))
    if spec["target_name"] != TARGET_NAMES[label]:
        raise base.ProbeError("scratch target name mismatch")
    if spec["label"] != label or base.normalized_path(
        Path(spec["scene"])
    ) != base.normalized_path(scene):
        raise base.ProbeError("scratch preparation manifest mismatch")
    if not (run / "before.i3d").is_file() or not (run / "source-hashes.json").is_file():
        raise base.ProbeError("missing scratch baseline")
    return scene


def foreground_state(user, hwnd, pid):
    user.GetForegroundWindow.argtypes = ()
    user.GetForegroundWindow.restype = wintypes.HWND
    front = user.GetForegroundWindow()
    owner = wintypes.DWORD()
    user.GetWindowThreadProcessId(front, ctypes.byref(owner))
    return {
        "iconic": bool(user.IsIconic(hwnd)),
        "foreground_pid": owner.value,
        "foreground_hwnd": base.handle_value(front),
        "foreground_is_editor": owner.value == pid,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", choices=sorted(ASSETS), required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--expected-title", required=True)
    parser.add_argument(
        "--action", choices=["inspect", "script", "save"], default="inspect"
    )
    parser.add_argument("--expect-exit", action="store_true")
    args = parser.parse_args()
    if args.expect_exit and args.action != "script":
        parser.error("--expect-exit requires a script dispatch")
    if args.pid <= 0:
        parser.error("positive PID required")
    scene = verify_copy(args.fixture, args.expected_title)
    if args.expect_exit:
        run = scene.parent.parent
        pending = [
            p
            for p in run.glob("request-*.xml")
            if not (run / p.name.replace("request-", "response-")).exists()
        ]
        if (
            len(pending) != 1
            or ElementTree.parse(pending[0]).getroot().get("op") != "quit"
        ):
            raise base.ProbeError(
                "exit exemption requires exactly one pending quit request"
            )
    kernel, user, callback = base.configure_api()
    binary = base.verify_process(kernel, args.pid)
    windows = base.matching_main_windows(user, callback, args.pid, args.expected_title)
    if len(windows) != 1:
        raise base.ProbeError("expected exactly one matching scratch Editor frame")
    hwnd = windows[0]
    item = script.find_script(user, user.GetMenu(hwnd))
    saves = base.save_menu_items(user, user.GetMenu(hwnd))
    if len(saves) != 1 or saves[0]["state"] & base.MFS_DISABLED:
        raise base.ProbeError("expected exactly one enabled native Save entry")
    before = foreground_state(user, hwnd, args.pid)
    result = {
        "action": args.action,
        "fixture": args.fixture,
        "scene": scene.name,
        "binary_sha256": binary["sha256"],
        "script_id": item["id"],
        "before": before,
    }
    failure = False
    started = time.monotonic()
    if args.action != "inspect":
        if (
            not before["iconic"]
            or before["foreground_is_editor"]
            or before["foreground_pid"] == 0
        ):
            raise base.ProbeError(
                "require minimized Editor and another foreground process"
            )
        if args.action == "save":
            dispatch = base.dispatch_save(kernel, user, hwnd)
            result["dispatch"] = dispatch
            failure = dispatch["status"] != "returned"
        else:
            value = base.DWORD_PTR()
            ctypes.set_last_error(0)
            returned = user.SendMessageTimeoutW(
                hwnd,
                base.WM_COMMAND,
                base.WPARAM(item["id"]),
                base.LPARAM(0),
                base.SMTO_ABORTIFHUNG | base.SMTO_ERRORONEXIT,
                base.SAVE_TIMEOUT_MS,
                ctypes.byref(value),
            )
            result["dispatch"] = {
                "returned": bool(returned),
                "last_error": ctypes.get_last_error(),
            }
            failure = not returned
    result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
    result["after"] = foreground_state(user, hwnd, args.pid)
    result["foreground_unchanged"] = (
        before["foreground_hwnd"] == result["after"]["foreground_hwnd"]
    )
    result["independent_receipt_required"] = True
    print(json.dumps(result, indent=2))
    if failure:
        raise SystemExit(3)
    if (
        args.action != "inspect"
        and not args.expect_exit
        and (
            not result["after"]["iconic"]
            or result["after"]["foreground_is_editor"]
            or not result["foreground_unchanged"]
        )
    ):
        raise SystemExit(4)


if __name__ == "__main__":
    try:
        main()
    except (base.ProbeError, OSError, KeyError, ValueError) as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}))
        raise SystemExit(2)
