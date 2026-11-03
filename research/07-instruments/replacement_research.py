#!/usr/bin/env python3
"""Bounded copied-asset replacement experiment, never an MCP server.

Only launches owned Editors on inactive private Win32 desktops. Raw copies and
receipts stay beneath the ignored endurance root. Never switches input desktops.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import desktop_endurance_probe as e
import desktop_research_controller as c

INS = Path(__file__).resolve().parent
GAME = Path("D:/Games/Farming Simulator 2025")
TARGET = (
    GAME
    / "data/placeables/brandless/animalHusbandries/specialCalfShed/specialCalfShed.i3d"
)
DONOR = (
    GAME
    / "data/placeables/brandless/constructibles/farmGarageConstructable02/farmGarageConstructable02.i3d"
)
TARGET_NODE = "specialCalfShed01/visuals/instances/gate01/gate01"
DONOR_NODE = "farmGarageBuildable02/visual/visual_lod/farmGarageBuildable02_lod0/phase07/doorLeftSmall_lod0"
BASE = e.endurance_root()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def hashes(directory):
    return {
        str(p.relative_to(directory)): e.sha256(p)
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


def prepare(case, source=None):
    assert c.lock_state()["unlocked"], "session not unlocked"
    assert e.CASE_RE and __import__("re").fullmatch(e.CASE_RE, case)
    run = BASE / case
    assert not run.exists(), "research case already exists"
    run.mkdir()
    if source is None:
        before = {"target": hashes(TARGET.parent), "donor": hashes(DONOR.parent)}
        shutil.copytree(TARGET.parent, run / "asset")
        shutil.copytree(DONOR.parent, run / "donor")
        write_json(run / "source-hashes.json", before)
    else:
        shutil.copytree(source / "asset", run / "asset")
        shutil.copytree(source / "donor", run / "donor")
    template = BASE / "handles-long-minimized1"
    shutil.copytree(template / "scripts", run / "scripts")
    text = (template / "input-editor.xml").read_text(encoding="utf-8")
    text = text.replace(template.as_posix(), run.as_posix())
    (run / "editor.xml").write_text(text, encoding="utf-8", newline="\n")
    write_json(
        run / "spec.json",
        {
            "scene": (run / "asset" / TARGET.name).as_posix(),
            "target": "specialCalfShed01",
            "bridge": "replacement_scene_probe.lua",
        },
    )
    config = ET.Element(
        "replacement",
        targetPath=TARGET_NODE,
        donorPath=DONOR_NODE,
        donorFile=(run / "donor" / DONOR.name).as_posix(),
        replacementName="researchReplacement",
    )
    for key, value in {
        "cameraX": -5.6,
        "cameraY": 2,
        "cameraZ": 7.5,
        "directionX": 0,
        "directionY": 0.5,
        "directionZ": 6,
        "overviewCameraX": 16,
        "overviewCameraY": 12,
        "overviewCameraZ": 23,
        "overviewDirectionX": 16,
        "overviewDirectionY": 9,
        "overviewDirectionZ": 23,
    }.items():
        config.set(key, str(value))
    ET.ElementTree(config).write(
        run / "replacement.xml", encoding="utf-8", xml_declaration=True
    )
    return run


class Session:
    def __init__(self, run):
        self.run = run
        self.case = run.name
        self.sequence = 0
        self.process = None
        self.records = []

    def record(self, kind, **fields):
        item = {"kind": kind, "utc_ns": time.time_ns(), **fields}
        self.records.append(item)
        with (self.run / "operations.jsonl").open(
            "a", encoding="utf-8", newline="\n"
        ) as stream:
            stream.write(json.dumps(item) + "\n")
        print(json.dumps(item), flush=True)

    def start(self):
        with (self.run / "launcher-output.txt").open("w", encoding="utf-8") as output:
            self.process = subprocess.Popen(
                [
                    sys.executable,
                    str(INS / "desktop_endurance_probe.py"),
                    "--case",
                    self.case,
                    "--duration-seconds",
                    "600",
                ],
                stdout=output,
                stderr=subprocess.STDOUT,
                creationflags=0x08000000,
            )
        deadline = time.monotonic() + 50
        while not (self.run / "session.json").exists():
            assert self.process.poll() is None, "launcher exited before ready"
            assert time.monotonic() < deadline, "ready deadline"
            time.sleep(0.15)
        with c.owned(self.case) as (_, _, _, u, _, _, frame):
            u.ShowWindow.argtypes = (c.w.HWND, ctypes.c_int)
            u.ShowWindow(frame, 7)
            assert u.IsIconic(frame), "minimization failed"
        self.record("started_minimized")

    def publish(self, op, **fields):
        assert c.lock_state()["unlocked"], "session not unlocked"
        self.sequence += 1
        seq = self.sequence
        assert not (self.run / f"response-{seq:06d}.xml").exists()
        ET.ElementTree(
            ET.Element(
                "request", seq=str(seq), op=op, **{k: str(v) for k, v in fields.items()}
            )
        ).write(self.run / "request.next.xml", encoding="utf-8", xml_declaration=True)
        (self.run / "request.next.xml").replace(self.run / "request.xml")
        return seq

    def native(self, command=None, timeout_ms=3000):
        assert c.lock_state()["unlocked"], "session not unlocked"
        with c.owned(self.case) as (_, _, _, u, _, _, frame):
            assert u.IsIconic(frame), "Editor was restored unexpectedly"
            assert u.IsWindowEnabled(frame), "Editor blocked by modal"
            if command is None:
                command = c.scripts.find_script(u, u.GetMenu(frame))["id"]
            else:
                items = c.save.save_menu_items(u, u.GetMenu(frame))
                assert (
                    command == 6001
                    and len(items) == 1
                    and not items[0]["state"] & c.save.MFS_DISABLED
                )
            value = c.save.DWORD_PTR()
            ctypes.set_last_error(0)
            started = time.monotonic()
            returned = u.SendMessageTimeoutW(
                frame,
                c.save.WM_COMMAND,
                command,
                0,
                c.save.SMTO_ABORTIFHUNG | c.save.SMTO_ERRORONEXIT,
                timeout_ms,
                ctypes.byref(value),
            )
            result = {
                "returned": bool(returned),
                "last_error": ctypes.get_last_error(),
                "elapsed_s": time.monotonic() - started,
            }
            assert u.IsIconic(frame)
            return result

    def receipt(self, seq, op, timeout=10):
        file = self.run / f"response-{seq:06d}.xml"
        deadline = time.monotonic() + timeout
        while not file.exists():
            assert time.monotonic() < deadline, "response deadline"
            time.sleep(0.1)
        root = ET.parse(file).getroot()
        values = {child.tag: child.text for child in root}
        assert values.get("seq") == str(seq) and values.get("op") == op, values
        assert values.get("ok") == "true", values
        assert (
            Path(values["scene"]).resolve()
            == (self.run / "asset" / TARGET.name).resolve()
        )
        snapshot_xml = self.run / f"snapshot-{seq:06d}.xml"
        if snapshot_xml.exists():
            snapshot = ET.parse(snapshot_xml).getroot().findtext("json")
            write_json(self.run / f"snapshot-{seq:06d}.json", json.loads(snapshot))
        return values

    def request(self, op, **fields):
        seq = self.publish(op, **fields)
        result = self.native()
        assert result["returned"], result
        receipt = self.receipt(seq, op)
        self.record("request", seq=seq, op=op, transport=result, receipt=receipt)
        return seq, receipt

    def save(self):
        existing = set(self.run.glob("save-*.xml"))
        started = time.time_ns()
        result = self.native(6001)
        assert result["returned"], result
        fresh = set(self.run.glob("save-*.xml")) - existing
        assert len(fresh) == 1
        file = fresh.pop()
        assert file.stat().st_mtime_ns >= started
        values = {child.tag: child.text for child in ET.parse(file).getroot()}
        assert values.get("ok") == "true" and values.get("op") == "save", values
        self.record(
            "save",
            transport=result,
            receipt=values,
            asset_hashes=hashes(self.run / "asset"),
        )

    def stop(self):
        self.request("quit")
        self.process.wait(timeout=20)
        summary = json.loads((self.run / "summary.json").read_text())
        assert (
            summary["editor_exit_code"] == 0 and summary["desktop_absent_after_close"]
        ), summary
        self.record("clean_exit", desktop_removed=True)

    def force_exit(self):
        with c.owned(self.case) as (_, identity, kernel, _, _, _, _):
            kernel.OpenProcess.argtypes = (c.w.DWORD, c.w.BOOL, c.w.DWORD)
            kernel.OpenProcess.restype = c.w.HANDLE
            handle = kernel.OpenProcess(0x00100001, False, identity["pid"])
            assert handle, "owned process terminate handle unavailable"
            try:
                assert kernel.TerminateProcess(handle, 73), "owned terminate failed"
                assert kernel.WaitForSingleObject(handle, 5000) == 0
            finally:
                kernel.CloseHandle(handle)
        self.process.wait(timeout=15)
        summary = json.loads((self.run / "summary.json").read_text())
        assert (
            summary["editor_exit_code"] == 73 and summary["desktop_absent_after_close"]
        )
        self.record("forced_owned_exit", exit_code=73, desktop_removed=True)

    def cleanup(self):
        if self.process is not None and self.process.poll() is None:
            try:
                self.force_exit()
            except Exception:
                self.process.terminate()
                self.process.wait(timeout=15)
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument(
        "--mode",
        choices=("prepare", "run", "reload", "forced-exit", "recover-in-place"),
        default="prepare",
    )
    parser.add_argument("--source")
    args = parser.parse_args()
    source = e.case_dir(args.source) if args.source else None
    if args.mode == "prepare":
        run = prepare(args.case, source)
        print(json.dumps({"prepared": str(run)}))
        return
    run = e.case_dir(args.case)
    if args.mode == "recover-in-place":
        prior = json.loads((run / "result.json").read_text())
        assert prior["mode"] == "forced-exit" and prior["status"] == "passed"
        backup = BASE / (args.case + "-proof")
        assert not backup.exists() and backup.resolve().is_relative_to(BASE.resolve())
        shutil.copytree(run, backup)
        archive = run / "prior-run"
        assert not archive.exists() and archive.resolve().is_relative_to(run.resolve())
        archive.mkdir()
        for file in list(run.iterdir()):
            if file.is_file() and file.name not in (
                "spec.json",
                "editor.xml",
                "replacement.xml",
            ):
                destination = archive / file.name
                assert file.resolve().is_relative_to(
                    run.resolve()
                ) and destination.resolve().is_relative_to(archive.resolve())
                shutil.move(str(file), str(destination))
    session = Session(run)
    try:
        session.start()
        if args.mode == "run":
            _, first = session.request("inspect")
            time.sleep(1.2)
            _, second = session.request("inspect")
            delta = float(second["clock"]) - float(first["clock"])
            assert 1 <= delta <= 3, ("getTime must advance in seconds", delta)
            session.record("clock_calibrated_seconds", delta=delta)
            session.request("render")
            session.request("render", kind="overview")
            session.request("import")
            session.request("inspect")
            session.request("render", kind="overview")
            session.request("fit")
            session.request("render")
            before = json.loads(
                (run / f"snapshot-{session.sequence:06d}.json").read_text()
            )
            replacement_path = TARGET_NODE.rsplit("/", 1)[0] + "/researchReplacement"
            x_before = next(
                n["translation"][0]
                for n in before["nodes"]
                if n["path"] == replacement_path
            )
            seq = session.publish("slow-mutate")
            transport = session.native(timeout_ms=100)
            assert not transport["returned"], "delay probe unexpectedly acknowledged"
            receipt = session.receipt(seq, "slow-mutate", timeout=15)
            assert receipt.get("changedCount") == "1"
            after = json.loads((run / f"snapshot-{seq:06d}.json").read_text())
            x_after = next(
                n["translation"][0]
                for n in after["nodes"]
                if n["path"] == replacement_path
            )
            assert abs(x_after - x_before - 0.01) < 1e-5
            receipt_hash = e.sha256(run / f"response-{seq:06d}.xml")
            assert session.native()["returned"], "duplicate dispatch did not return"
            assert receipt_hash == e.sha256(run / f"response-{seq:06d}.xml")
            session.request("inspect")
            duplicate = json.loads(
                (run / f"snapshot-{session.sequence:06d}.json").read_text()
            )
            x_duplicate = next(
                n["translation"][0]
                for n in duplicate["nodes"]
                if n["path"] == replacement_path
            )
            assert abs(x_duplicate - x_after) < 1e-6
            session.record(
                "uncertain_ack_reconciled",
                delayed_seq=seq,
                transport=transport,
                applied_delta=x_after - x_before,
                replay_applied_delta=x_duplicate - x_after,
            )
            session.request("fit")
            session.request("render")
            session.request("replace")
            session.request("inspect")
            session.request("render")
            session.request("render", kind="overview")
            session.save()
            session.request("inspect")
            session.request("render")
        else:
            session.request("inspect")
            session.request("render")
            session.request("render", kind="overview")
        if args.mode == "forced-exit":
            disk_before = hashes(run / "asset")
            seq = session.publish("slow-mutate")
            transport = session.native(timeout_ms=6000)
            assert transport["returned"]
            receipt = session.receipt(seq, "slow-mutate")
            assert receipt.get("changedCount") == "1"
            session.record(
                "unsaved_mutation_before_forced_exit",
                seq=seq,
                transport=transport,
                receipt=receipt,
            )
            session.request("inspect")
            session.force_exit()
            assert disk_before == hashes(run / "asset"), (
                "unsaved change reached disk unexpectedly"
            )
        else:
            session.stop()
        if args.mode == "run":
            before = json.loads((run / "source-hashes.json").read_text())
            assert before == {
                "target": hashes(TARGET.parent),
                "donor": hashes(DONOR.parent),
            }, "installed asset changed"
        write_json(
            run / "result.json",
            {"status": "passed", "mode": args.mode, "records": session.records},
        )
    finally:
        session.cleanup()


if __name__ == "__main__":
    main()
