from __future__ import annotations

import ctypes
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))

import editor_handle_types as handles
import trace_editor_fences as fences


class FakeKernel:
    def __init__(self, close_result: bool = True):
        self.close_result = close_result

    def OpenProcess(self, *_):
        return 1

    def GetExitCodeProcess(self, _, code):
        ctypes.cast(code, ctypes.POINTER(ctypes.c_uint32)).contents.value = 259
        return True

    def CloseHandle(self, _):
        return self.close_result


class FakeScript:
    def __init__(self, trace):
        self.exports_sync = mock.Mock(summary=mock.Mock(return_value=trace))
        self.unloaded = False

    def on(self, *_):
        return None

    def load(self):
        return None

    def unload(self):
        self.unloaded = True


class FakeSession:
    def __init__(self, script):
        self.script = script
        self.detached = False

    def create_script(self, _):
        return self.script

    def detach(self):
        self.detached = True


class HandleParserTests(unittest.TestCase):
    def test_parser_sums_unknown_duplicates_and_rejects_bad_total(self):
        counts, total = handles.parse_handle_output(
            "<Unknown type>: 2\n<Unknown type>: 35\nEvent: 3\nTotal handles: 40\n"
        )
        self.assertEqual(37, counts["<Unknown type>"])
        self.assertEqual(40, total)
        with self.assertRaises(handles.ProbeError):
            handles.parse_handle_output("Event: 3\nTotal handles: 4\n")

    def test_output_rejects_ads_and_reserved_device_prefixes(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            for observer in (handles, fences):
                for filename in ("trace:stream.json", "CON.foo.json", "../out.json"):
                    with self.assertRaises(observer.ProbeError):
                        observer.output_paths(run, filename)

    def test_output_rejects_dangling_link_target(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            for observer in (handles, fences):
                with (
                    mock.patch.object(Path, "is_symlink", return_value=True),
                    self.assertRaises(observer.ProbeError),
                ):
                    observer.output_paths(run, "fresh.json")


class FenceFailureTests(unittest.TestCase):
    def run_observer(self, trace, close_result=True):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            script = FakeScript(trace)
            session = FakeSession(script)
            kernel = FakeKernel(close_result)

            @contextmanager
            def owned(_):
                yield run, {"pid": 42}, kernel, None, None, None, None

            frida = mock.Mock(__version__="test")
            frida.attach.return_value = session
            with (
                mock.patch.object(fences.endurance, "case_dir", return_value=run),
                mock.patch.object(fences.controller, "owned", owned),
                mock.patch.object(
                    fences.controller, "lock_state", return_value={"unlocked": True}
                ),
                mock.patch.object(fences, "import_frida", return_value=frida),
                mock.patch.object(
                    fences.save, "verify_process", return_value={"sha256": "pinned"}
                ),
                mock.patch.object(fences.time, "monotonic", side_effect=(0, 0, 2)),
            ):
                code, receipt = fences.observe("case", None, 1, "trace.json")
            persisted = json.loads((run / "trace.json").read_text(encoding="utf-8"))
            return code, receipt, persisted, script, session

    def test_truncated_trace_fails_and_cleans_up(self):
        code, receipt, persisted, script, session = self.run_observer(
            {"truncated": True}
        )
        self.assertEqual(3, code)
        self.assertEqual("failed", receipt["status"])
        self.assertEqual("failed", persisted["status"])
        self.assertTrue(script.unloaded)
        self.assertTrue(session.detached)

    def test_cleanup_failure_cannot_pass_observation(self):
        code, receipt, persisted, script, session = self.run_observer(
            {"truncated": False}, close_result=False
        )
        self.assertEqual(3, code)
        self.assertEqual("failed", receipt["status"])
        self.assertIn("cleanup_errors", persisted)
        self.assertTrue(script.unloaded)
        self.assertTrue(session.detached)


if __name__ == "__main__":
    unittest.main()
