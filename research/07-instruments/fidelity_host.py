"""Research executor for the prepared fidelity cases, not a general MCP host.

No UI Save is synthesized here. Initial controls allow only inspection and quit;
observation mutations require a baseline or fresh readback process. Respect the
user's visible-access instruction in addition to the scratch launch-block flag.
"""

import ctypes
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as E
from pathlib import Path

repo = Path(__file__).resolve().parents[6]
root = repo / ".docs/giants-editor-fidelity"
ins = repo / "docs/research/skills/fs25-modding/giants-editor-mcp/instruments"
sys.path.insert(0, str(ins))
import windows_save_probe as b
import windows_script_probe as script

case = sys.argv[1]
action = sys.argv[2]
assert case in {
    a + "-" + m for a in ("water", "gate") for m in ("baseline", "native", "manual")
}
run = root / case
spec = json.loads((run / "spec.json").read_text())
scene = Path(spec["scene"])
assert scene.resolve().is_relative_to(root.resolve())
title = "GIANTS Editor 64bit 10.0.14 - " + scene.as_posix()
if action == "launch":
    if (root / "VISIBLE-ACCESS-DEFERRED.txt").exists():
        raise RuntimeError("visible_editor_access_deferred_by_user")
    fresh = "fresh" in sys.argv[3:]
    if fresh:
        callback = E.parse(run / "save-001.xml").getroot()
        assert (
            callback.findtext("ok") == "true"
            and callback.findtext("path") == scene.as_posix()
        ), "fresh control requires verified Save receipt"
    marker = run / ("fresh-ready.xml" if fresh else "ready.xml")
    assert not marker.exists(), "existing ready marker"
    code = (
        "MCP_PROBE_ROOT="
        + repr(run.as_posix() + "/")
        + ";MCP_EXPECTED_SCENE="
        + repr(scene.as_posix())
        + ";MCP_EXPECTED_TARGET="
        + repr(spec["target"])
        + ";MCP_MUTATE_TRANSLATION="
        + ("false" if fresh else "true")
        + ";MCP_READY_FILE="
        + repr(marker.name)
        + ";source("
        + repr((ins / "fidelity_scene_probe.lua").as_posix())
        + ")"
    )
    args = [
        str(b.EXPECTED_EXE),
        str(scene),
        "-noVersionSelection",
        "-supressChangelog",
        "-disableTextureStreaming",
        "-runScriptCode",
        code,
        "-configXML",
        str(run / "editor.xml"),
    ]
    assert b.sha256(b.EXPECTED_EXE) == b.EXPECTED_SHA256
    if fresh:
        archive = run / "initial-observations"
        archive.mkdir(exist_ok=False)
        for pattern in (
            "request-*.xml",
            "response-*.xml",
            "dispatch-*.json",
            "samples.xml",
            "inspect.xml",
        ):
            for item in run.glob(pattern):
                item.rename(archive / item.name)
    prefix = "fresh" if fresh else "initial"
    started = time.time_ns()
    with (
        (run / (prefix + "-stdout.txt")).open("w") as out,
        (run / (prefix + "-stderr.txt")).open("w") as err,
    ):
        p = subprocess.Popen(args, cwd=run, stdout=out, stderr=err)
    (run / (prefix + "-pid.txt")).write_text(str(p.pid))
    for _ in range(90):
        if (
            marker.exists()
            and marker.stat().st_mtime_ns >= started
            and E.parse(marker).getroot().findtext("ok") == "true"
        ):
            break
        if p.poll() is not None:
            raise RuntimeError("Editor exited before ready")
        time.sleep(0.5)
    else:
        raise RuntimeError("Ready timeout, do not relaunch blindly")
    (run / "session.json").write_text(
        json.dumps({"pid": p.pid, "title": title, "fresh": fresh})
    )
    (run / "next.txt").write_text("1")
    print(json.dumps({"case": case, "pid": p.pid, "ready": True, "fresh": fresh}))
    sys.exit(0)
session = json.loads((run / "session.json").read_text())
if action == "native-save":
    if session["fresh"] or spec["mode"] != "native":
        raise RuntimeError("Save allowed only in initial native control")
    for pending in run.glob("request-*.xml"):
        if E.parse(pending).getroot().get("op") != "inspect":
            raise RuntimeError("Save forbidden after observation commands")
    for receipt in run.glob("dispatch-*.json"):
        if json.loads(receipt.read_text())["op"] != "inspect":
            raise RuntimeError("Save forbidden after recorded observation commands")
if action == "request":
    op = sys.argv[3]
    if (
        not session["fresh"]
        and spec["mode"] in ("native", "manual")
        and op not in ("inspect", "quit")
    ):
        raise RuntimeError(
            "initial Save controls allow inspect and quit only; observe in fresh process"
        )
k, u, cb = b.configure_api()
b.verify_process(k, session["pid"])
w = b.matching_main_windows(u, cb, session["pid"], title)
assert len(w) == 1
hwnd = w[0]
if action == "native-save":
    assert spec["mode"] == "native"
    assert not (run / "save-001.xml").exists()
    started = time.time_ns()
    result = b.dispatch_save(k, u, hwnd)
    result["started_unix_ns"] = started
    (run / "native-save.json").write_text(json.dumps(result, indent=2))
    assert result["status"] == "returned"
    assert (run / "save-001.xml").exists() and (
        run / "save-001.xml"
    ).stat().st_mtime_ns >= started
    print(json.dumps(result))
    sys.exit(0)
if action == "request":
    n = int((run / "next.txt").read_text())
    prefix = "fresh-" if session["fresh"] else ""
    attrs = {"op": sys.argv[3]}
    for text in sys.argv[4:]:
        key, value = text.split("=", 1)
        attrs[key] = value
    # The Lua bridge uses the same sequence filenames per process. Archive prior
    # process receipts before a fresh launch rather than accepting stale output.
    response = run / f"response-{n:03}.xml"
    assert not response.exists(), "old response; archive before fresh process"
    temp = run / "request.tmp"
    E.ElementTree(E.Element("request", attrs)).write(temp, encoding="utf-8")
    request = run / f"request-{n:03}.xml"
    assert not request.exists()
    temp.replace(request)
    item = script.find_script(u, u.GetMenu(hwnd))
    result = b.DWORD_PTR()
    started = time.time_ns()
    ctypes.set_last_error(0)
    returned = u.SendMessageTimeoutW(
        hwnd,
        b.WM_COMMAND,
        b.WPARAM(item["id"]),
        b.LPARAM(0),
        b.SMTO_ABORTIFHUNG | b.SMTO_ERRORONEXIT,
        10000,
        ctypes.byref(result),
    )
    (run / f"dispatch-{n:03}.json").write_text(
        json.dumps(
            {
                "returned": bool(returned),
                "started_unix_ns": started,
                "op": attrs["op"],
                "script_id": item["id"],
                "last_error": ctypes.get_last_error(),
            },
            indent=2,
        )
    )
    assert returned and response.exists() and response.stat().st_mtime_ns >= started, (
        "uncertain request, no retry"
    )
    value = E.parse(response).getroot()
    assert value.findtext("ok") == "true", E.tostring(value, encoding="unicode")[:800]
    assert value.findtext("requestId") == str(n)
    (run / "next.txt").write_text(str(n + 1))
    print(
        json.dumps(
            {
                "case": case,
                "request": n,
                "op": attrs["op"],
                "ok": True,
                "response": response.name,
            }
        )
    )
    sys.exit(0)
raise ValueError(action)
