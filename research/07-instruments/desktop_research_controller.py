"""Bounded commands and read-only observation for an owned endurance session.

The controller never retries a dispatch. It prints a JSON result for a returned
failure, then exits with status 3 so callers cannot mistake uncertainty for success.
"""

import argparse
import ctypes
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from ctypes import wintypes as w
from pathlib import Path

import desktop_endurance_probe as e
import private_desktop_probe as p
import windows_save_probe as save
import windows_script_probe as scripts


def lock_state():
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    api = ctypes.WinDLL("wtsapi32", use_last_error=True)
    k.GetCurrentProcessId.restype = w.DWORD
    k.ProcessIdToSessionId.argtypes = (w.DWORD, ctypes.POINTER(w.DWORD))
    session = w.DWORD()
    if not k.ProcessIdToSessionId(k.GetCurrentProcessId(), ctypes.byref(session)):
        raise p.ProbeError("session query failed")
    api.WTSQuerySessionInformationW.argtypes = (
        w.HANDLE,
        w.DWORD,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(w.DWORD),
    )
    api.WTSQuerySessionInformationW.restype = w.BOOL
    api.WTSFreeMemory.argtypes = (ctypes.c_void_p,)
    value = ctypes.c_void_p()
    size = w.DWORD()
    if not api.WTSQuerySessionInformationW(
        None, session.value, 25, ctypes.byref(value), ctypes.byref(size)
    ):
        raise p.ProbeError("WTS session flags query failed")
    try:
        if size.value < 232 or ctypes.c_uint32.from_address(value.value).value != 1:
            raise p.ProbeError("unexpected WTSINFOEX layout")
        flags = ctypes.c_int32.from_address(value.value + 16).value
        return {
            "utc_ns": time.time_ns(),
            "monotonic_ns": time.monotonic_ns(),
            "flags": flags,
            "locked": flags == 0,
            "unlocked": flags == 1,
        }
    finally:
        api.WTSFreeMemory(value)


@contextmanager
def owned(case):
    run = e.case_dir(case)
    session = json.loads((run / "session.json").read_text(encoding="utf-8"))
    spec = json.loads((run / "spec.json").read_text(encoding="utf-8"))
    if Path(session["scene"]).resolve() != Path(spec["scene"]).resolve():
        raise p.ProbeError("session scene mismatch")
    if not session["desktop"].startswith(e.DESKTOP_PREFIX):
        raise p.ProbeError("unexpected desktop prefix")
    k, u, cb = p.winapi()
    e.configure_extra_api(k, u)
    original = u.GetThreadDesktop(k.GetCurrentThreadId())
    desk = u.OpenDesktopW(session["desktop"], 0, False, p.READ)
    if not desk:
        raise p.ProbeError("owned desktop unavailable")
    try:
        if not u.SetThreadDesktop(desk):
            raise p.ProbeError("private controller attach failed")
        frame = p.private_frame(k, u, cb, desk, session["pid"], session["title"])
        yield run, session, k, u, cb, desk, int(frame["hwnd"], 16)
    finally:
        if not u.SetThreadDesktop(original):
            raise p.ProbeError("controller desktop restore failed")
        if not u.CloseDesktop(desk):
            raise p.ProbeError("controller desktop close failed")


def send(u, hwnd, command):
    value = save.DWORD_PTR()
    ctypes.set_last_error(0)
    started = time.monotonic()
    result = u.SendMessageTimeoutW(
        hwnd,
        save.WM_COMMAND,
        save.WPARAM(command),
        save.LPARAM(0),
        save.SMTO_ABORTIFHUNG | save.SMTO_ERRORONEXIT,
        3000,
        ctypes.byref(value),
    )
    return {
        "returned": bool(result),
        "last_error": ctypes.get_last_error(),
        "elapsed_ms": (time.monotonic() - started) * 1000,
        "command": command,
    }


def emit_result(result):
    """Print one result and make an unreturned native call visible to callers."""
    result["utc_ns"] = time.time_ns()
    print(json.dumps(result))
    return 3 if result.get("returned") is False else 0


def snapshot_png(u, hwnd, dest):
    # The caller must run this synchronous API in a killable helper with a host timeout.
    from PIL import Image

    g = ctypes.WinDLL("gdi32", use_last_error=True)
    for name, args, result in [
        ("CreateCompatibleDC", (w.HDC,), w.HDC),
        ("CreateCompatibleBitmap", (w.HDC, ctypes.c_int, ctypes.c_int), w.HBITMAP),
        ("SelectObject", (w.HDC, w.HANDLE), w.HANDLE),
        ("DeleteObject", (w.HANDLE,), w.BOOL),
        ("DeleteDC", (w.HDC,), w.BOOL),
    ]:
        f = getattr(g, name)
        f.argtypes = args
        f.restype = result
    u.GetWindowDC.argtypes = (w.HWND,)
    u.GetWindowDC.restype = w.HDC
    u.ReleaseDC.argtypes = (w.HWND, w.HDC)
    u.ReleaseDC.restype = ctypes.c_int
    u.GetWindowRect.argtypes = (w.HWND, ctypes.POINTER(w.RECT))
    u.GetWindowRect.restype = w.BOOL
    u.PrintWindow.argtypes = (w.HWND, w.HDC, w.UINT)
    u.PrintWindow.restype = w.BOOL

    class Header(ctypes.Structure):
        _fields_ = [
            ("size", w.DWORD),
            ("width", w.LONG),
            ("height", w.LONG),
            ("planes", w.WORD),
            ("bits", w.WORD),
            ("compression", w.DWORD),
            ("image_size", w.DWORD),
            ("xppm", w.LONG),
            ("yppm", w.LONG),
            ("used", w.DWORD),
            ("important", w.DWORD),
        ]

    g.GetDIBits.argtypes = (
        w.HDC,
        w.HBITMAP,
        w.UINT,
        w.UINT,
        ctypes.c_void_p,
        ctypes.POINTER(Header),
        w.UINT,
    )
    g.GetDIBits.restype = ctypes.c_int
    rect = w.RECT()
    assert u.GetWindowRect(hwnd, ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if not (0 < width <= 4096 and 0 < height <= 4096):
        raise p.ProbeError("capture dimensions outside research bound")
    dc = u.GetWindowDC(hwnd)
    memory = g.CreateCompatibleDC(dc)
    bitmap = g.CreateCompatibleBitmap(dc, width, height)
    previous = g.SelectObject(memory, bitmap)
    try:
        g.PatBlt.argtypes = (
            w.HDC,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            w.DWORD,
        )
        g.PatBlt.restype = w.BOOL
        if not g.PatBlt(memory, 0, 0, width, height, 0x42):
            raise p.ProbeError("capture initialization failed")
        returned = bool(u.PrintWindow(hwnd, memory, 0))
        g.SelectObject(memory, previous)
        previous = None
        header = Header(
            size=ctypes.sizeof(Header), width=width, height=-height, planes=1, bits=32
        )
        pixels = ctypes.create_string_buffer(width * height * 4)
        lines = g.GetDIBits(memory, bitmap, 0, height, pixels, ctypes.byref(header), 0)
        if lines != height:
            raise p.ProbeError("capture bitmap extraction failed")
        Image.frombuffer("RGB", (width, height), pixels.raw, "raw", "BGRX", 0, 1).save(
            dest
        )
        return {
            "returned": returned,
            "width": width,
            "height": height,
            "bytes": dest.stat().st_size,
        }
    finally:
        if previous:
            g.SelectObject(memory, previous)
        g.DeleteObject(bitmap)
        g.DeleteDC(memory)
        u.ReleaseDC(hwnd, dc)


def controls(u, parent):
    callback = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    u.EnumChildWindows.argtypes = (w.HWND, callback, w.LPARAM)
    u.EnumChildWindows.restype = w.BOOL
    u.GetDlgCtrlID.argtypes = (w.HWND,)
    u.GetDlgCtrlID.restype = ctypes.c_int
    found = []

    @callback
    def collect(hwnd, _):
        title = ctypes.create_unicode_buffer(4096)
        cls = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(hwnd, title, len(title))
        u.GetClassNameW(hwnd, cls, len(cls))
        found.append(
            {
                "id": u.GetDlgCtrlID(hwnd),
                "text": title.value,
                "class": cls.value,
                "enabled": bool(u.IsWindowEnabled(hwnd)),
            }
        )
        return True

    u.EnumChildWindows(parent, collect, 0)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case")
    parser.add_argument(
        "--action",
        choices=(
            "session-state",
            "inspect",
            "request",
            "save",
            "capture",
            "_capture",
            "dismiss",
        ),
        required=True,
    )
    parser.add_argument(
        "--op",
        choices=(
            "inspect",
            "mutate",
            "render",
            "lua-error",
            "uncaught-error",
            "missing-asset",
            "quit",
            "gc",
            "update-start",
            "update-stop",
        ),
        default="inspect",
    )
    parser.add_argument("--seq", type=int)
    parser.add_argument("--hwnd", type=lambda v: int(v, 0))
    parser.add_argument("--button-id", type=int)
    parser.add_argument("--allow-locked-research", action="store_true")
    args = parser.parse_args()
    if args.action == "session-state":
        print(json.dumps(lock_state()))
        return 0
    if args.action == "capture":
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--case",
            args.case,
            "--action",
            "_capture",
        ]
        if args.hwnd is not None:
            command.extend(["--hwnd", str(args.hwnd)])
        if args.allow_locked_research:
            command.append("--allow-locked-research")
        try:
            child = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=4.5,
                creationflags=0x08000000,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return emit_result({"returned": False, "reason": "capture_helper_timeout"})
        if child.stdout.strip():
            print(child.stdout.strip())
        if child.returncode:
            return child.returncode
        return 0
    state = lock_state()
    if not state["unlocked"] and args.action != "inspect":
        if not state["locked"] or not args.allow_locked_research:
            raise p.ProbeError(
                "non-unlocked session requires explicit bounded research permit"
            )
        permit = json.loads(
            (e.case_dir(args.case) / "lock-window.json").read_text(encoding="utf-8")
        )
        run = e.case_dir(args.case)
        scope = json.loads((run / "lock-scope.json").read_text(encoding="utf-8"))
        session = json.loads((run / "session.json").read_text(encoding="utf-8"))
        import hashlib

        if (
            scope["session_sha256"]
            != hashlib.sha256((run / "session.json").read_bytes()).hexdigest()
            or scope["pid"] != session["pid"]
            or scope["desktop"] != session["desktop"]
        ):
            raise p.ProbeError("lock scope is not bound to this session")
        deadline = permit["deadline_monotonic_ns"]
        now = time.monotonic_ns()
        if not deadline - 90_000_000_000 <= now <= deadline - 5_000_000_000:
            raise p.ProbeError(
                "locked research dispatch window has expired or not begun"
            )
        if (run / "lock-window.json").stat().st_mtime_ns < scope["armed_utc_ns"]:
            raise p.ProbeError("lock permit predates the current armed scope")
    with owned(args.case) as (run, session, _k, u, cb, desk, frame):
        if args.action == "inspect":
            result = {
                "windows": e.private_inventory(u, cb, desk, session["pid"]),
                "session": lock_state(),
                "secondary_controls": {
                    v["hwnd"]: controls(u, int(v["hwnd"], 16))
                    for v in e.private_inventory(u, cb, desk, session["pid"])
                    if int(v["hwnd"], 16) != frame
                },
            }
        elif args.action == "save":
            if not u.IsWindowEnabled(frame):
                raise p.ProbeError(
                    "main frame disabled; pending modal must be inspected first"
                )
            items = save.save_menu_items(u, u.GetMenu(frame))
            if len(items) != 1 or items[0]["state"] & save.MFS_DISABLED:
                raise p.ProbeError("native Save item unavailable")
            result = send(u, frame, 6001)
        elif args.action == "request":
            if args.seq is None or not 1 <= args.seq <= 100000:
                raise p.ProbeError("require bounded request sequence")
            if not u.IsWindowEnabled(frame):
                raise p.ProbeError("main frame disabled; no script dispatch")
            response = run / f"response-{args.seq:06d}.xml"
            if response.exists():
                raise p.ProbeError("stale response for requested sequence")
            item = scripts.find_script(u, u.GetMenu(frame))
            tmp = run / "request.next.xml"
            ET.ElementTree(ET.Element("request", seq=str(args.seq), op=args.op)).write(
                tmp, encoding="utf-8", xml_declaration=True
            )
            tmp.replace(run / "request.xml")
            result = send(u, frame, item["id"])
            result.update(op=args.op, seq=args.seq)
        else:
            windows = e.private_inventory(u, cb, desk, session["pid"])
            target = frame if args.hwnd is None else args.hwnd
            if target not in [int(v["hwnd"], 16) for v in windows]:
                raise p.ProbeError("target is not an owned top-level window")
            if args.action == "_capture":
                dest = run / f"window-{target:x}-{time.time_ns()}.png"
                result = snapshot_png(u, target, dest)
                result["file"] = str(dest)
            else:
                # Dismissal is authorized only after parent review wrote this exact receipt.
                permit = json.loads(
                    (run / "dialog-permit.json").read_text(encoding="utf-8")
                )
                current = next(v for v in windows if int(v["hwnd"], 16) == target)
                required = {
                    "pid": session["pid"],
                    "hwnd": target,
                    "button_id": args.button_id,
                    "title": current["title"],
                    "class": current["class"],
                }
                if any(permit.get(key) != value for key, value in required.items()):
                    raise p.ProbeError("dialog permit identity mismatch")
                buttons = [
                    v
                    for v in controls(u, target)
                    if v["id"] == args.button_id
                    and v["class"].lower() == "button"
                    and v["enabled"]
                    and v["text"] == permit.get("button_text")
                ]
                if len(buttons) != 1:
                    raise p.ProbeError("dialog button identity mismatch")
                u.GetWindow.argtypes = (w.HWND, w.UINT)
                u.GetWindow.restype = w.HWND
                if target == frame or u.GetWindow(target, 4) != frame:
                    raise p.ProbeError("dialog owner is not the verified main frame")
                result = send(u, target, args.button_id)
        return emit_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
