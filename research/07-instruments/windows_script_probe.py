"""Inspect or invoke only the isolated MCP Probe Dispatch script-menu entry.

No process launch, activation, mouse or keyboard input is performed. A returned
message is not proof of script completion; inspect the independent XML receipt.
"""

import argparse
import ctypes
import json
from ctypes import wintypes
from pathlib import Path

import windows_save_probe as base

LABEL = "MCP Probe Dispatch"


def find_script(user32, menu):
    found = []
    visited = set()

    def walk(current, path):
        key = base.handle_value(current)
        if not key or key in visited:
            return
        visited.add(key)
        count = user32.GetMenuItemCount(current)
        if count < 0:
            raise base.ProbeError("cannot inspect script menu")
        for position in range(count):
            item = base.menu_item(user32, current, position)
            route = path + [item["label"]]
            if item["label"] == LABEL and route[0].replace("&", "") == "Scripts":
                found.append({"id": item["id"], "path": route, "state": item["state"]})
            if item["submenu"]:
                walk(item["submenu"], route)

    walk(menu, [])
    if len(found) != 1 or found[0]["state"] & base.MFS_DISABLED:
        raise base.ProbeError("expected exactly one enabled isolated probe script")
    return found[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--expected-title", required=True)
    parser.add_argument("--invoke", action="store_true")
    parser.add_argument("--expected-scene", type=Path, required=True)
    args = parser.parse_args()
    if args.pid <= 0 or "untitled" in args.expected_title.casefold():
        parser.error("require a positive PID and named fixture document")
    base.verify_fixture(args.expected_title, args.expected_scene)
    kernel, user, callback = base.configure_api()
    binary = base.verify_process(kernel, args.pid)
    windows = base.matching_main_windows(user, callback, args.pid, args.expected_title)
    if len(windows) != 1:
        raise base.ProbeError("expected exactly one matching named Editor frame")
    hwnd = windows[0]
    item = find_script(user, user.GetMenu(hwnd))
    user.GetForegroundWindow.argtypes = ()
    user.GetForegroundWindow.restype = wintypes.HWND
    before = base.handle_value(user.GetForegroundWindow())
    result = {
        "binary_sha256": binary["sha256"],
        "hwnd": hex(base.handle_value(hwnd)),
        "is_iconic_before": bool(user.IsIconic(hwnd)),
        "script": item,
        "mode": "inspect",
        "foreground_before": hex(before),
    }
    if args.invoke:
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
        result.update(
            mode="invoke",
            returned=bool(returned),
            window_result=value.value,
            last_error=ctypes.get_last_error(),
        )
    result["is_iconic_after"] = bool(user.IsIconic(hwnd))
    result["foreground_after"] = hex(base.handle_value(user.GetForegroundWindow()))
    result["completion_requires_independent_receipt"] = True
    print(json.dumps(result, indent=2))
    if args.invoke and not result["returned"]:
        raise SystemExit(3)


if __name__ == "__main__":
    try:
        main()
    except base.ProbeError as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}))
        raise SystemExit(2)
