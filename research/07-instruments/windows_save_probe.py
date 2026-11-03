#!/usr/bin/env python3
"""Inspect one pinned GIANTS Editor window before an optional Save command.

The default action is read-only. ``--send-save`` sends only WM_COMMAND/6001 to
the one verified main-frame window. It never activates, focuses, launches, or
injects input into the Editor. A successful dispatch only means the window
procedure returned before the timeout. It is not evidence that the scene was
saved. A later experiment must use independent file readback and onSave
evidence.

Win32 signatures and result handling follow Microsoft documentation:
https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendmessagetimeoutw
https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumwindows
https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-menuiteminfow
https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-queryfullprocessimagenamew
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import sys
from ctypes import wintypes
from pathlib import Path
from xml.etree import ElementTree

EXPECTED_SHA256 = "c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d"
EXPECTED_EXE = Path(
    r"C:\Program Files\GIANTS Software\GIANTS_Editor_10.0.14\editor.exe"
)
SAVE_COMMAND_ID = 6001
WM_COMMAND = 0x0111
SMTO_ABORTIFHUNG = 0x0002
SMTO_ERRORONEXIT = 0x0020
SAVE_TIMEOUT_MS = 2_000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MIIM_STATE = 0x00000001
MIIM_ID = 0x00000002
MIIM_SUBMENU = 0x00000004
MIIM_FTYPE = 0x00000100
MIIM_STRING = 0x00000040
MFS_DISABLED = 0x00000003

DWORD_PTR = ctypes.c_size_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
LRESULT = ctypes.c_ssize_t
HMENU = wintypes.HMENU
HBITMAP = wintypes.HBITMAP


class ProbeError(RuntimeError):
    """The process or window did not meet this instrument's safety checks."""


class MENUITEMINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("fMask", wintypes.UINT),
        ("fType", wintypes.UINT),
        ("fState", wintypes.UINT),
        ("wID", wintypes.UINT),
        ("hSubMenu", HMENU),
        ("hbmpChecked", HBITMAP),
        ("hbmpUnchecked", HBITMAP),
        ("dwItemData", DWORD_PTR),
        ("dwTypeData", wintypes.LPWSTR),
        ("cch", wintypes.UINT),
        ("hbmpItem", HBITMAP),
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def error_code() -> int:
    return ctypes.get_last_error()


def handle_value(handle) -> int:
    if isinstance(handle, ctypes.c_void_p):
        return int(handle.value or 0)
    return int(handle or 0)


def configure_api():
    """Return typed kernel32/user32 functions without making a UI call."""
    if os.name != "nt":
        raise ProbeError("windows_save_probe.py requires Windows")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.SetLastError.argtypes = (wintypes.DWORD,)
    kernel32.SetLastError.restype = None

    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, LPARAM)
    user32.EnumWindows.argtypes = (enum_proc, LPARAM)
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = (
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    )
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetMenu.argtypes = (wintypes.HWND,)
    user32.GetMenu.restype = HMENU
    user32.GetMenuItemCount.argtypes = (HMENU,)
    user32.GetMenuItemCount.restype = ctypes.c_int
    user32.GetMenuItemInfoW.argtypes = (
        HMENU,
        wintypes.UINT,
        wintypes.BOOL,
        ctypes.POINTER(MENUITEMINFOW),
    )
    user32.GetMenuItemInfoW.restype = wintypes.BOOL
    user32.IsIconic.argtypes = (wintypes.HWND,)
    user32.IsIconic.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.SendMessageTimeoutW.argtypes = (
        wintypes.HWND,
        wintypes.UINT,
        WPARAM,
        LPARAM,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.POINTER(DWORD_PTR),
    )
    user32.SendMessageTimeoutW.restype = LRESULT
    return kernel32, user32, enum_proc


def process_image_path(kernel32, pid: int) -> Path:
    process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not process:
        raise ProbeError(
            f"cannot open PID {pid} for executable inspection (Win32 error {error_code()})"
        )
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buffer))
        if not kernel32.QueryFullProcessImageNameW(
            process, 0, buffer, ctypes.byref(size)
        ):
            raise ProbeError(
                f"cannot read executable path for PID {pid} (Win32 error {error_code()})"
            )
        return Path(buffer.value)
    finally:
        if not kernel32.CloseHandle(process):
            raise ProbeError(
                f"cannot close process handle (Win32 error {error_code()})"
            )


def normalized_path(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path.resolve(strict=True))))


def verify_fixture(expected_title: str, scene: Path) -> None:
    """Restrict reusable message probes to the explicitly named test fixture."""
    prefix = "GIANTS Editor 64bit 10.0.14 - "
    if not scene.is_absolute() or scene.name != "native-save-fixture.i3d":
        raise ProbeError("require the absolute native-save-fixture.i3d scratch path")
    if not expected_title.startswith(prefix):
        raise ProbeError("expected title is not the pinned Editor main-frame title")
    try:
        if normalized_path(Path(expected_title[len(prefix) :])) != normalized_path(
            scene
        ):
            raise ProbeError("window title does not name the explicit fixture path")
        root = ElementTree.parse(scene).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        raise ProbeError(f"cannot verify scratch fixture: {exc}") from exc
    nodes = list(root.find("Scene")) if root.find("Scene") is not None else []
    if (
        root.tag != "i3D"
        or len(nodes) != 1
        or nodes[0].tag != "TransformGroup"
        or nodes[0].get("name") != "MCP_Save_Probe"
        or len(nodes[0])
        or any(
            len(root.find(tag))
            for tag in ("Files", "Materials", "Shapes")
            if root.find(tag) is not None
        )
    ):
        raise ProbeError("only the isolated one-TransformGroup fixture is allowed")


def verify_process(kernel32, pid: int) -> dict[str, str]:
    actual = process_image_path(kernel32, pid)
    try:
        expected_path = normalized_path(EXPECTED_EXE)
        actual_path = normalized_path(actual)
    except OSError as exc:
        raise ProbeError(f"cannot resolve Editor executable path: {exc}") from exc
    if actual_path != expected_path:
        raise ProbeError(
            "PID executable path is not the pinned GIANTS Editor 10.0.14 path"
        )
    digest = sha256(actual)
    if digest != EXPECTED_SHA256:
        raise ProbeError(
            "PID executable SHA-256 does not match the inspected GIANTS Editor 10.0.14 build"
        )
    return {"path": str(actual), "sha256": digest}


def get_window_title(user32, hwnd) -> str:
    buffer = ctypes.create_unicode_buffer(32768)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value


def matching_main_windows(
    user32, enum_proc, pid: int, expected_title: str
) -> list[object]:
    matches: list[object] = []

    @enum_proc
    def collect(hwnd, _lparam):
        owner_pid = wintypes.DWORD()
        if not user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_pid)):
            return True
        if owner_pid.value == pid and get_window_title(user32, hwnd) == expected_title:
            matches.append(hwnd)
        return True

    ctypes.set_last_error(0)
    if not user32.EnumWindows(collect, 0):
        raise ProbeError(
            f"cannot enumerate top-level windows (Win32 error {error_code()})"
        )
    return matches


def menu_item(user32, menu, position: int) -> dict[str, object]:
    mask = MIIM_STATE | MIIM_ID | MIIM_SUBMENU | MIIM_FTYPE | MIIM_STRING
    info = MENUITEMINFOW(cbSize=ctypes.sizeof(MENUITEMINFOW), fMask=mask)
    if not user32.GetMenuItemInfoW(menu, position, True, ctypes.byref(info)):
        raise ProbeError(
            f"cannot inspect menu item {position} (Win32 error {error_code()})"
        )
    label = ""
    if info.cch:
        buffer = ctypes.create_unicode_buffer(info.cch + 1)
        info.dwTypeData = ctypes.cast(buffer, wintypes.LPWSTR)
        info.cch = len(buffer)
        if not user32.GetMenuItemInfoW(menu, position, True, ctypes.byref(info)):
            raise ProbeError(
                f"cannot read menu label at position {position} (Win32 error {error_code()})"
            )
        label = buffer.value
    return {
        "label": label,
        "id": int(info.wID),
        "state": int(info.fState),
        "submenu": info.hSubMenu,
    }


def save_menu_items(user32, menu) -> list[dict[str, object]]:
    if not menu:
        raise ProbeError("the verified window has no standard Win32 menu")
    found: list[dict[str, object]] = []
    visited: set[int] = set()

    def walk(current_menu, path: list[str]) -> None:
        key = handle_value(current_menu)
        if not key or key in visited:
            return
        visited.add(key)
        count = user32.GetMenuItemCount(current_menu)
        if count == -1:
            raise ProbeError(f"cannot count menu items (Win32 error {error_code()})")
        for position in range(count):
            item = menu_item(user32, current_menu, position)
            item_path = path + [str(item["label"])]
            if item["id"] == SAVE_COMMAND_ID:
                found.append(
                    {
                        "path": item_path,
                        "id": SAVE_COMMAND_ID,
                        "state": item["state"],
                        "label": item["label"],
                    }
                )
            if item["submenu"]:
                walk(item["submenu"], item_path)

    walk(menu, [])
    return found


def dispatch_save(kernel32, user32, hwnd) -> dict[str, object]:
    result = DWORD_PTR()
    ctypes.set_last_error(0)
    kernel32.SetLastError(0)
    dispatched = user32.SendMessageTimeoutW(
        hwnd,
        WM_COMMAND,
        WPARAM(SAVE_COMMAND_ID),
        LPARAM(0),
        SMTO_ABORTIFHUNG | SMTO_ERRORONEXIT,
        SAVE_TIMEOUT_MS,
        ctypes.byref(result),
    )
    if dispatched:
        return {
            "status": "returned",
            "timeout_ms": SAVE_TIMEOUT_MS,
            "window_result": result.value,
        }
    last_error = error_code()
    return {
        "status": "failed-or-timed-out",
        "timeout_ms": SAVE_TIMEOUT_MS,
        "last_error": last_error,
        "last_error_is_zero": last_error == 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pid", type=int, required=True, help="GIANTS Editor PID to inspect"
    )
    parser.add_argument(
        "--expected-title", required=True, help="exact non-Untitled main-window title"
    )
    parser.add_argument(
        "--send-save",
        action="store_true",
        help="after all checks, dispatch only WM_COMMAND/6001",
    )
    parser.add_argument(
        "--expected-scene",
        type=Path,
        required=True,
        help="absolute disposable fixture path",
    )
    args = parser.parse_args()
    if args.pid <= 0:
        parser.error("--pid must be positive")
    if not args.expected_title.strip():
        parser.error("--expected-title must be non-empty")
    if "untitled" in args.expected_title.casefold():
        parser.error("--expected-title must name a saved scene, not an Untitled scene")
    return args


def main() -> None:
    args = parse_args()
    verify_fixture(args.expected_title, args.expected_scene)
    kernel32, user32, enum_proc = configure_api()
    binary = verify_process(kernel32, args.pid)
    windows = matching_main_windows(user32, enum_proc, args.pid, args.expected_title)
    if len(windows) != 1:
        raise ProbeError(
            f"expected exactly one top-level window titled {args.expected_title!r}; found {len(windows)}"
        )
    hwnd = windows[0]
    title = get_window_title(user32, hwnd)
    if not title or "untitled" in title.casefold():
        raise ProbeError("refusing an untitled scene")
    save_items = save_menu_items(user32, user32.GetMenu(hwnd))
    if len(save_items) != 1:
        raise ProbeError(
            f"expected exactly one menu item with command ID {SAVE_COMMAND_ID}; found {len(save_items)}"
        )
    save_item = save_items[0]
    if save_item["state"] & MFS_DISABLED:
        raise ProbeError("Save command 6001 is disabled")

    output: dict[str, object] = {
        "mode": "send-save" if args.send_save else "inspect",
        "binary": binary,
        "window": {
            "hwnd": f"0x{handle_value(hwnd):x}",
            "title": title,
            "is_iconic": bool(user32.IsIconic(hwnd)),
            "is_visible": bool(user32.IsWindowVisible(hwnd)),
        },
        "save_menu": save_item,
        "dispatch": {"status": "not-requested"},
        "limitation": "Menu state and message dispatch do not prove that the scene was saved.",
    }
    if args.send_save:
        output["dispatch"] = dispatch_save(kernel32, user32, hwnd)
    print(json.dumps(output, indent=2, sort_keys=True))
    if args.send_save and output["dispatch"]["status"] != "returned":
        raise SystemExit(3)


if __name__ == "__main__":
    try:
        main()
    except ProbeError as exc:
        print(
            json.dumps({"status": "refused", "reason": str(exc)}, indent=2),
            file=sys.stderr,
        )
        raise SystemExit(2)
