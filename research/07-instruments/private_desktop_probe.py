#!/usr/bin/env python3
"""Bounded private-Win32-desktop launcher for the pinned GIANTS Editor.

It never switches a desktop, activates a window, injects input, installs hooks,
changes ACLs, or starts Editor on the default desktop.  This is a research
instrument, not a security sandbox.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import runpy
import signal
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from ctypes import wintypes
from pathlib import Path

import windows_save_probe as save
import windows_script_probe as script

READ, CREATE = 0x0001, 0x0002
UOI_NAME, STARTF_FORCEOFFFEEDBACK = 2, 0x80
CREATE_SUSPENDED, CREATE_NO_WINDOW, CREATE_UNICODE_ENVIRONMENT = 4, 0x08000000, 0x400
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 9, 0x2000
WAIT_OBJECT_0, WAIT_TIMEOUT = 0, 258


class ProbeError(RuntimeError):
    pass


class SI(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("reserved", wintypes.LPWSTR),
        ("desktop", wintypes.LPWSTR),
        ("title", wintypes.LPWSTR),
        ("x", wintypes.DWORD),
        ("y", wintypes.DWORD),
        ("cx", wintypes.DWORD),
        ("cy", wintypes.DWORD),
        ("xchars", wintypes.DWORD),
        ("ychars", wintypes.DWORD),
        ("fill", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("show", wintypes.WORD),
        ("reserved2", wintypes.WORD),
        ("reserved3", ctypes.POINTER(ctypes.c_byte)),
        ("stdin", wintypes.HANDLE),
        ("stdout", wintypes.HANDLE),
        ("stderr", wintypes.HANDLE),
    ]


class PI(ctypes.Structure):
    _fields_ = [
        ("process", wintypes.HANDLE),
        ("thread", wintypes.HANDLE),
        ("pid", wintypes.DWORD),
        ("tid", wintypes.DWORD),
    ]


class Basic(ctypes.Structure):
    _fields_ = [
        ("process_time", ctypes.c_int64),
        ("job_time", ctypes.c_int64),
        ("flags", wintypes.DWORD),
        ("min_ws", ctypes.c_size_t),
        ("max_ws", ctypes.c_size_t),
        ("active_limit", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority", wintypes.DWORD),
        ("scheduling", wintypes.DWORD),
    ]


class Io(ctypes.Structure):
    _fields_ = [
        ("read_ops", ctypes.c_uint64),
        ("write_ops", ctypes.c_uint64),
        ("other_ops", ctypes.c_uint64),
        ("read", ctypes.c_uint64),
        ("written", ctypes.c_uint64),
        ("other", ctypes.c_uint64),
    ]


class JobLimits(ctypes.Structure):
    _fields_ = [
        ("basic", Basic),
        ("io", Io),
        ("process_limit", ctypes.c_size_t),
        ("job_limit", ctypes.c_size_t),
        ("peak_process", ctypes.c_size_t),
        ("peak_job", ctypes.c_size_t),
    ]


def err(text):
    raise ProbeError(f"{text} (Win32 error {ctypes.get_last_error()})")


def winapi():
    if os.name != "nt":
        raise ProbeError("requires Windows")
    k, u, cb = save.configure_api()
    k.CreateProcessW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.POINTER(SI),
        ctypes.POINTER(PI),
    )
    k.CreateProcessW.restype = wintypes.BOOL
    k.ResumeThread.argtypes = (wintypes.HANDLE,)
    k.ResumeThread.restype = wintypes.DWORD
    k.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    k.CreateJobObjectW.restype = wintypes.HANDLE
    k.SetInformationJobObject.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    )
    k.SetInformationJobObject.restype = wintypes.BOOL
    k.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    k.AssignProcessToJobObject.restype = wintypes.BOOL
    k.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    k.GetExitCodeProcess.restype = wintypes.BOOL
    k.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    k.TerminateProcess.restype = wintypes.BOOL
    k.GetCurrentThreadId.argtypes = ()
    k.GetCurrentThreadId.restype = wintypes.DWORD
    u.GetThreadDesktop.argtypes = (wintypes.DWORD,)
    u.GetThreadDesktop.restype = wintypes.HANDLE
    u.CreateDesktopW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
    )
    u.CreateDesktopW.restype = wintypes.HANDLE
    u.OpenDesktopW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    )
    u.OpenDesktopW.restype = wintypes.HANDLE
    u.CloseDesktop.argtypes = (wintypes.HANDLE,)
    u.CloseDesktop.restype = wintypes.BOOL
    u.OpenInputDesktop.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    u.OpenInputDesktop.restype = wintypes.HANDLE
    u.GetUserObjectInformationW.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    u.GetUserObjectInformationW.restype = wintypes.BOOL
    u.SetThreadDesktop.argtypes = (wintypes.HANDLE,)
    u.SetThreadDesktop.restype = wintypes.BOOL
    cb = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    u.EnumDesktopWindows.argtypes = (wintypes.HANDLE, cb, wintypes.LPARAM)
    u.EnumDesktopWindows.restype = wintypes.BOOL
    u.GetWindowThreadProcessId.argtypes = (
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    )
    u.GetWindowThreadProcessId.restype = wintypes.DWORD
    u.GetForegroundWindow.argtypes = ()
    u.GetForegroundWindow.restype = wintypes.HWND
    u.GetProcessWindowStation.argtypes = ()
    u.GetProcessWindowStation.restype = wintypes.HANDLE
    u.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    u.GetWindowTextW.restype = ctypes.c_int
    u.GetMenu.argtypes = (wintypes.HWND,)
    u.GetMenu.restype = wintypes.HMENU
    return k, u, cb


def close(k, h):
    if h and not k.CloseHandle(h):
        err("CloseHandle failed")


def desk_name(u, desk):
    size = wintypes.DWORD()
    u.GetUserObjectInformationW(desk, UOI_NAME, None, 0, ctypes.byref(size))
    if not size.value:
        err("GetUserObjectInformationW size failed")
    text = ctypes.create_unicode_buffer(size.value // 2)
    if not u.GetUserObjectInformationW(
        desk, UOI_NAME, text, size.value, ctypes.byref(size)
    ):
        err("GetUserObjectInformationW name failed")
    return text.value


def current_desk(k, u):
    handle = u.GetThreadDesktop(k.GetCurrentThreadId())
    if not handle:
        err("GetThreadDesktop failed")
    return desk_name(u, handle)


def window_station(u):
    station = u.GetProcessWindowStation()
    if not station:
        err("GetProcessWindowStation failed")
    return desk_name(u, station)


def snapshot(u, callback, editor_pid=None):
    desk = u.OpenInputDesktop(0, False, READ)
    if not desk:
        err("OpenInputDesktop failed")
    try:
        editor_hwnds = []

        @callback
        def scan(hwnd, _):
            pid = wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if editor_pid and pid.value == editor_pid:
                editor_hwnds.append(int(hwnd))
            return True

        if not u.EnumDesktopWindows(desk, scan, 0):
            err("EnumDesktopWindows input failed")
        front = u.GetForegroundWindow()
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(front, ctypes.byref(pid))
        return {
            "input_desktop": desk_name(u, desk),
            "foreground_hwnd": int(front or 0),
            "foreground_pid": pid.value,
            "editor_hwnds_on_input": editor_hwnds,
        }
    finally:
        if not u.CloseDesktop(desk):
            err("CloseDesktop input failed")


def private_hwnds(u, callback, desk, pid):
    result = []

    @callback
    def scan(hwnd, _):
        owner = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            result.append(int(hwnd))
        return True

    ctypes.set_last_error(0)
    enumerated = u.EnumDesktopWindows(desk, scan, 0)
    enum_error = ctypes.get_last_error()
    if not enumerated and (enum_error != 0 or result):
        err("EnumDesktopWindows private failed")
    return result


def private_frame(k, u, callback, desk, pid, title):
    binary = save.verify_process(k, pid)
    matches = []
    for hwnd in private_hwnds(u, callback, desk, pid):
        text = ctypes.create_unicode_buffer(32768)
        u.GetWindowTextW(hwnd, text, len(text))
        if text.value == title:
            matches.append(hwnd)
    if len(matches) != 1:
        raise ProbeError("expected exactly one named Editor frame on private desktop")
    owner_tid = u.GetWindowThreadProcessId(matches[0], ctypes.byref(wintypes.DWORD()))
    ctypes.set_last_error(0)
    owner_desktop = u.GetThreadDesktop(owner_tid)
    owner_error = ctypes.get_last_error()
    actual_name = desk_name(u, owner_desktop) if owner_desktop else None
    expected_name = desk_name(u, desk)
    if actual_name != expected_name and not (
        owner_desktop is None and owner_error == 5
    ):
        raise ProbeError(
            "selected Editor frame thread desktop mismatch: "
            + json.dumps(
                {
                    "hwnd": matches[0],
                    "tid": owner_tid,
                    "pid": pid,
                    "actual_desktop": actual_name,
                    "expected_desktop": expected_name,
                    "last_error": owner_error,
                    "controller_desktop": current_desk(k, u),
                }
            )
        )
    script.find_script(u, u.GetMenu(matches[0]))
    return {
        "hwnd": f"0x{matches[0]:x}",
        "binary_sha256": binary["sha256"],
        "owner_thread_id": owner_tid,
        "owner_desktop": actual_name,
        "owner_desktop_query_error": owner_error if owner_desktop is None else 0,
        "membership_evidence": "EnumDesktopWindows with explicit private desktop handle",
        "private_desktop": expected_name,
        "is_window_visible": bool(u.IsWindowVisible(matches[0])),
        "is_iconic": bool(u.IsIconic(matches[0])),
    }


def new_job(k):
    job = k.CreateJobObjectW(None, None)
    if not job:
        err("CreateJobObjectW failed")
    info = JobLimits()
    info.basic.flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not k.SetInformationJobObject(
        job,
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        close(k, job)
        err("SetInformationJobObject failed")
    return job


def start_editor(k, desktop, editor_args):
    exe = Path(editor_args[0]).resolve(strict=True)
    if save.sha256(exe) != save.EXPECTED_SHA256:
        raise ProbeError("Editor executable hash differs from pinned build")
    si = SI(
        cb=ctypes.sizeof(SI),
        desktop=f"WinSta0\\{desktop}",
        flags=STARTF_FORCEOFFFEEDBACK,
    )
    pi, command = (
        PI(),
        ctypes.create_unicode_buffer(
            subprocess.list2cmdline([str(exe), *editor_args[1:]])
        ),
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
        ctypes.byref(si),
        ctypes.byref(pi),
    ):
        err("CreateProcessW private Editor failed")
    return pi


def server(args):
    run = Path(args.run).resolve(strict=True)
    root = Path(__file__).resolve().parents[6] / ".docs/giants-editor-invisible/private"
    root = root.resolve(strict=True)
    if not run.is_relative_to(root) or run.name not in ("gate-native", "water-native"):
        raise ProbeError(
            "run must be a prepared native case under the pinned private root"
        )
    spec = json.loads((run / "spec.json").read_text(encoding="utf-8"))
    if {"scene", "target", "mode", "run"} - set(spec):
        raise ProbeError("spec.json lacks required identity fields")
    if spec["mode"] != "native" or Path(spec["run"]).resolve() != run:
        raise ProbeError("spec identity does not name this native run")
    scene = Path(spec["scene"]).resolve(strict=True)
    if not scene.is_relative_to(run):
        raise ProbeError("scene is outside run directory")
    k, u, cb = winapi()
    if window_station(u) != "WinSta0":
        raise ProbeError("private desktop requires WinSta0")
    original_handle = u.GetThreadDesktop(k.GetCurrentThreadId())
    if not original_handle:
        err("GetThreadDesktop original failed")
    original = desk_name(u, original_handle)
    name = "GiantsProbe_" + uuid.uuid4().hex
    desk = job = process = thread = None
    try:
        stale = (
            "session.json",
            "ready.xml",
            "fresh-ready.xml",
            "private-desktop-telemetry.jsonl",
            "private-desktop-summary.json",
        )
        if any((run / item).exists() for item in stale):
            raise ProbeError(
                "stale session or receipt exists; archive it before launch"
            )
        started_ns, overall_deadline = time.time_ns(), time.monotonic() + 180
        desk = u.CreateDesktopW(name, None, None, 0, CREATE | READ, None)
        if not desk:
            err("CreateDesktopW failed")
        if current_desk(k, u) != original:
            if not u.SetThreadDesktop(original_handle):
                err("SetThreadDesktop original failed")
            if current_desk(k, u) != original:
                raise ProbeError("launcher cannot return to its original desktop")
        before = snapshot(u, cb)
        if before["input_desktop"] == name:
            raise ProbeError("new desktop is unexpectedly input desktop")
        ready_name = "fresh-ready.xml" if args.fresh else "ready.xml"
        lua = Path(__file__).with_name("fidelity_scene_probe.lua").resolve(strict=True)
        code = (
            f"MCP_PROBE_ROOT={str(run.as_posix() + '/').__repr__()};"
            f"MCP_EXPECTED_SCENE={scene.as_posix().__repr__()};"
            f"MCP_EXPECTED_TARGET={str(spec['target']).__repr__()};"
            f"MCP_MUTATE_TRANSLATION={'false' if args.fresh else 'true'};"
            f"MCP_READY_FILE={ready_name.__repr__()};source({lua.as_posix().__repr__()})"
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
            str((run / "editor.xml").resolve(strict=True)),
        ]
        job = new_job(k)
        pi = start_editor(k, name, editor_args)
        process, thread = pi.process, pi.thread
        if not k.AssignProcessToJobObject(job, process):
            err("AssignProcessToJobObject failed")
        initial = snapshot(u, cb, pi.pid)
        if (
            initial["input_desktop"] != before["input_desktop"]
            or initial["editor_hwnds_on_input"]
            or initial["foreground_pid"] == pi.pid
        ):
            raise ProbeError("containment monitor detected unsafe state before resume")
        if k.ResumeThread(thread) == 0xFFFFFFFF:
            err("ResumeThread failed")
        close(k, thread)
        thread = None
        title = "GIANTS Editor 64bit 10.0.14 - " + scene.as_posix()
        ready, deadline = run / ready_name, min(time.monotonic() + 45, overall_deadline)
        report, raw = (
            run / "private-desktop-summary.json",
            run / "private-desktop-telemetry.jsonl",
        )
        while k.WaitForSingleObject(process, 50) == WAIT_TIMEOUT:
            state = snapshot(u, cb, pi.pid)
            sample = {
                "time_ns": time.time_ns(),
                "private_hwnds": private_hwnds(u, cb, desk, pi.pid),
                **state,
            }
            with raw.open("a", encoding="utf-8") as f:
                f.write(json.dumps(sample) + "\n")
            if (
                state["input_desktop"] != before["input_desktop"]
                or state["editor_hwnds_on_input"]
                or state["foreground_pid"] == pi.pid
            ):
                raise ProbeError(
                    "containment monitor detected Editor on the input desktop or foreground"
                )
            if (
                ready.is_file()
                and ready.stat().st_mtime_ns >= started_ns
                and sample["private_hwnds"]
            ):
                marker = ET.parse(ready).getroot()
                if (
                    marker.findtext("ok") != "true"
                    or marker.findtext("op") != "ready"
                    or marker.findtext("scene") != scene.as_posix()
                ):
                    raise ProbeError(
                        "ready receipt does not identify the prepared scene"
                    )
                if not u.SetThreadDesktop(desk):
                    err("SetThreadDesktop private verification failed")
                try:
                    frame = private_frame(k, u, cb, desk, pi.pid, title)
                finally:
                    if not u.SetThreadDesktop(original_handle):
                        err("SetThreadDesktop after private verification failed")
                break
            if time.monotonic() >= deadline:
                raise ProbeError("45 second ready deadline elapsed")
        else:
            raise ProbeError("Editor exited before ready")
        session = {
            "pid": pi.pid,
            "title": title,
            "private_frame": frame,
            "desktop": name,
            "fresh": args.fresh,
            "run": str(run),
            "input_before": before,
        }
        session["fidelity_lua_sha256"] = hashlib.sha256(lua.read_bytes()).hexdigest()
        (run / "session.json").write_text(
            json.dumps(session, indent=2), encoding="utf-8"
        )
        (run / "next.txt").write_text("1", encoding="utf-8")
        while k.WaitForSingleObject(process, 50) == WAIT_TIMEOUT:
            if time.monotonic() >= overall_deadline:
                raise ProbeError("180 second server lifetime cap elapsed")
            state = snapshot(u, cb, pi.pid)
            with raw.open("a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "time_ns": time.time_ns(),
                            "private_hwnds": private_hwnds(u, cb, desk, pi.pid),
                            **state,
                        }
                    )
                    + "\n"
                )
            if (
                state["input_desktop"] != before["input_desktop"]
                or state["editor_hwnds_on_input"]
                or state["foreground_pid"] == pi.pid
            ):
                raise ProbeError("containment monitor detected unsafe state")
        final = snapshot(u, cb, pi.pid)
        if (
            final["input_desktop"] != before["input_desktop"]
            or final["editor_hwnds_on_input"]
            or final["foreground_pid"] == pi.pid
        ):
            raise ProbeError("final containment sample is unsafe")
        with raw.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "time_ns": time.time_ns(),
                        "private_hwnds": [],
                        "private_enumeration": "not_needed_after_confirmed_process_exit",
                        "final": True,
                        **final,
                    }
                )
                + "\n"
            )
        code = wintypes.DWORD()
        if not k.GetExitCodeProcess(process, ctypes.byref(code)):
            err("GetExitCodeProcess failed")
        report.write_text(
            json.dumps(
                {
                    "status": "exited",
                    "pid": pi.pid,
                    "exit_code": code.value,
                    "input_before": before,
                    "input_final": final,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        if thread:
            close(k, thread)
        if process:
            if k.WaitForSingleObject(process, 0) == WAIT_TIMEOUT:
                k.TerminateProcess(process, 1)
                k.WaitForSingleObject(process, 5000)
            close(k, process)
        if job:
            close(k, job)
        if desk and not u.CloseDesktop(desk):
            err("CloseDesktop private failed")


def controller(args):
    if args.op == "launch":
        raise ProbeError("controller rejects launch")
    host = Path(args.host).resolve(strict=True)
    root = (
        Path(__file__).resolve().parents[6] / ".docs/giants-editor-invisible/private"
    ).resolve(strict=True)
    if host != root / "host.py" or args.case not in ("gate-native", "water-native"):
        raise ProbeError(
            "controller accepts only the reviewed private host and native cases"
        )
    k, u, _ = winapi()
    original = u.GetThreadDesktop(k.GetCurrentThreadId())
    if not original:
        err("GetThreadDesktop controller original failed")
    desk = u.OpenDesktopW(args.desktop, 0, False, READ)
    if not desk:
        err("OpenDesktopW private failed")
    try:
        run = root / args.case
        session = json.loads((run / "session.json").read_text(encoding="utf-8"))
        if session.get("desktop") != args.desktop or not args.desktop.startswith(
            "GiantsProbe_"
        ):
            raise ProbeError(
                "controller desktop does not match the active private session"
            )
        input_desk = u.OpenInputDesktop(0, False, READ)
        if not input_desk:
            err("OpenInputDesktop controller failed")
        try:
            input_name = desk_name(u, input_desk)
        finally:
            if not u.CloseDesktop(input_desk):
                err("CloseDesktop controller input failed")
        if input_name == args.desktop:
            raise ProbeError("controller refuses the input desktop")
        if not u.SetThreadDesktop(desk):
            err("SetThreadDesktop private failed")
        private_frame(
            k,
            u,
            ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
            desk,
            int(session["pid"]),
            str(session["title"]),
        )
        sys.argv = [
            str(host),
            args.case,
            "native-save" if args.op == "native-save" else "request",
            *args.arguments,
        ]
        runpy.run_path(str(host), run_name="__main__")
    finally:
        if not u.SetThreadDesktop(original):
            err("SetThreadDesktop controller original failed")
        if not u.CloseDesktop(desk):
            err("CloseDesktop controller private failed")


class PrivateDesktopSession:
    """Parent-side server holder. It never creates or switches a desktop."""

    def __init__(self, run, contained_root=None):
        self.run, self.root, self.process = (
            Path(run),
            Path(contained_root or Path(run).parent),
            None,
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def launch(self, fresh=False):
        if self.process and self.process.poll() is None:
            raise ProbeError("a session is already active")
        stale = (
            "session.json",
            "ready.xml",
            "fresh-ready.xml",
            "private-desktop-telemetry.jsonl",
            "private-desktop-summary.json",
        )
        if any((self.run / item).exists() for item in stale):
            raise ProbeError(
                "stale session or receipt exists; archive it before launch"
            )
        with (
            (self.run / "server-stdout.txt").open("w", encoding="utf-8") as out,
            (self.run / "server-stderr.txt").open("w", encoding="utf-8") as errors,
        ):
            self.process = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "_server",
                    "--run",
                    str(self.run),
                    "--contained-root",
                    str(self.root),
                    *(["--fresh"] if fresh else []),
                ],
                creationflags=CREATE_NO_WINDOW,
                stdout=out,
                stderr=errors,
            )
        deadline, receipt = time.monotonic() + 45, self.run / "session.json"
        while time.monotonic() < deadline:
            if receipt.is_file():
                return json.loads(receipt.read_text(encoding="utf-8"))
            if self.process.poll() is not None:
                raise ProbeError("server exited before session receipt")
            time.sleep(0.05)
        raise ProbeError("session receipt deadline elapsed")

    def invoke(self, desktop, host, case, op, *arguments):
        return subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "controller",
                "--desktop",
                desktop,
                "--host",
                str(host),
                "--case",
                case,
                "--op",
                op,
                "--contained-root",
                str(self.root),
                *arguments,
            ],
            creationflags=CREATE_NO_WINDOW,
            check=True,
        )

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            self.process.wait(timeout=6)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("inspect-default")
    launch = subs.add_parser("launch")
    launch.add_argument("--run", required=True)
    launch.add_argument("--contained-root")
    launch.add_argument("--fresh", action="store_true")
    srv = subs.add_parser("_server")
    srv.add_argument("--run", required=True)
    srv.add_argument("--contained-root", required=True)
    srv.add_argument("--fresh", action="store_true")
    ctl = subs.add_parser("controller")
    ctl.add_argument("--desktop", required=True)
    ctl.add_argument("--host", required=True)
    ctl.add_argument("--case", required=True)
    ctl.add_argument("--op", choices=("native-save", "request"), required=True)
    ctl.add_argument("--contained-root")
    ctl.add_argument("arguments", nargs="*")
    args = parser.parse_args()
    if args.command in ("_server", "launch"):
        server(args)
    elif args.command == "controller":
        controller(args)
    else:
        k, u, cb = winapi()
        print(
            json.dumps(
                {
                    "window_station": window_station(u),
                    "process_desktop": current_desk(k, u),
                    **snapshot(u, cb),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    try:
        main()
    except ProbeError as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
