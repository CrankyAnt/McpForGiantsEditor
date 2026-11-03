#!/usr/bin/env python3
"""Verify retained replacement receipts and publish derived, non-vendor facts."""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[6]
BASE = ROOT / ".docs/giants-editor-desktop/endurance"
TARGET_PATH = "specialCalfShed01/visuals/instances/gate01/gate01"
REPLACEMENT_PATH = TARGET_PATH.rsplit("/", 1)[0] + "/researchReplacement"
CASES = (
    "replacement-door3",
    "replacement-reload1",
    "replacement-forced1-proof",
    "replacement-recovered1",
    "replacement-forced1",
    "replacement-input-copy1",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot(case, seq):
    run = BASE / case
    path = run / f"snapshot-{seq:06d}.xml"
    native = json.loads(ET.parse(path).getroot().findtext("json"))
    assert native == read(run / f"snapshot-{seq:06d}.json"), "derived snapshot differs"
    return native


def rows(snapshot):
    result = {node["path"]: node for node in snapshot["nodes"]}
    assert len(result) == len(snapshot["nodes"]), "ambiguous node path"
    return result


def image_difference(first, second):
    with Image.open(first) as a, Image.open(second) as b:
        assert a.size == b.size == (1024, 768)
        diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
        changed = sum(1 for pixel in diff.get_flattened_data() if pixel != (0, 0, 0))
        return {
            "changed_pixels": changed,
            "total_pixels": 1024 * 768,
            "changed_fraction": changed / (1024 * 768),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    original = snapshot(CASES[0], 1)
    imported = snapshot(CASES[0], 6)
    fitted = snapshot(CASES[0], 8)
    saved = snapshot(CASES[0], 18)
    reloaded = snapshot(CASES[1], 1)
    unsaved = snapshot(CASES[2], 5)
    recovered = snapshot(CASES[3], 1)
    same_path_recovered = snapshot(CASES[4], 1)
    old, new, load, crash, recover = map(
        rows, (original, saved, reloaded, unsaved, recovered)
    )
    expected_added = {REPLACEMENT_PATH, REPLACEMENT_PATH + "/doorLeftSmallParts"}
    assert set(old) - set(new) == {TARGET_PATH}
    assert set(new) - set(old) == expected_added
    assert set(new) == set(load) == set(crash) == set(recover)
    assert sum(n["shape"] for n in old.values()) == 25
    assert sum(n["shape"] for n in new.values()) == 26
    assert len(old) == 52 and len(new) == 53
    gate_controls = [
        path for path in old if "/gate01instanced" in path and old[path]["shape"]
    ]
    assert len(gate_controls) == 8
    max_delta = 0.0
    rounded_nodes = 0
    for path, a in old.items():
        if path == TARGET_PATH or not path.startswith("specialCalfShed01"):
            continue
        b = load[path]
        for key in (
            "name",
            "shape",
            "nonRenderable",
            "vertices",
            "materials",
            "vertexDigest",
            "visible",
        ):
            assert a[key] == b[key], (path, key)
        deltas = [
            abs(x - y)
            for key in ("translation", "rotation", "scale")
            for x, y in zip(a[key], b[key])
        ]
        max_delta = max(max_delta, max(deltas))
        rounded_nodes += int(any(deltas))
        assert max(deltas) < 1e-5, (path, deltas)
    for path in expected_added:
        for key in ("vertices", "materials", "vertexDigest", "visible", "shape"):
            assert new[path][key] == load[path][key] == recover[path][key], (path, key)
    target = original["targetBounds"]
    fit = fitted["replacementBounds"]
    fresh = reloaded["replacementBounds"]
    fit_errors = {
        key: abs(target[key] - fit[key])
        for key in ("width", "height", "centerX", "centerY", "centerZ")
    }
    reload_errors = {key: abs(target[key] - fresh[key]) for key in fit_errors}
    assert max(fit_errors.values()) < 0.0005
    assert max(reload_errors.values()) < 0.0005
    expected_x = load[REPLACEMENT_PATH]["translation"][0]
    unsaved_x = crash[REPLACEMENT_PATH]["translation"][0]
    recovered_x = recover[REPLACEMENT_PATH]["translation"][0]
    assert abs(unsaved_x - expected_x - 0.01) < 1e-5
    assert abs(recovered_x - expected_x) < 1e-8
    same_path_x = rows(same_path_recovered)[REPLACEMENT_PATH]["translation"][0]
    assert abs(same_path_x - expected_x) < 1e-8
    assert (
        read(BASE / CASES[2] / "summary.json")["scene"]
        == read(BASE / CASES[4] / "summary.json")["scene"]
    )
    case_results = {}
    for case in CASES:
        run = BASE / case
        result = read(run / "result.json")
        summary = read(run / "summary.json")
        assert result["status"] == "passed" and summary["status"] == "completed"
        assert summary["desktop_absent_after_close"]
        assert summary["editor_exit_code"] == (73 if case == CASES[2] else 0)
        inputs = summary["input_hashes_before_start"]
        for key, filename in (
            ("replacement.xml", "input-replacement.xml"),
            ("replacement_scene_probe.lua", "input-probe.lua"),
            ("editor.xml", "input-editor.xml"),
            ("spec.json", "spec.json"),
        ):
            assert inputs[key] == sha(run / filename), (case, key)
        assert sha(run / "replacement.xml") == inputs["replacement.xml"]
        telemetry = [
            json.loads(line)
            for line in (run / "telemetry.jsonl").read_text().splitlines()
        ]
        assert not any(row["input"].get("editor_hwnds_on_input") for row in telemetry)
        assert not any(
            row["input"].get("input_desktop") == summary["desktop"] for row in telemetry
        )
        pngs = sorted(run.glob("view-*.png"))
        for path in pngs:
            with Image.open(path) as image:
                assert image.size == (1024, 768)
                image.verify()
        for receipt_path in run.glob("response-*.xml"):
            data = ET.parse(receipt_path).getroot()
            assert data.findtext("ok") == "true", receipt_path.name
            snapshot(case, int(receipt_path.stem.split("-")[1]))
            assert data.findtext("seq") == str(int(receipt_path.stem.split("-")[1]))
        case_results[case] = {
            "exit_code": summary["editor_exit_code"],
            "private_desktop_removed": True,
            "input_samples": len(telemetry),
            "editor_on_input_desktop_samples": 0,
            "native_pngs": len(pngs),
            "operations_sha256": sha(run / "operations.jsonl"),
            "summary_sha256": sha(run / "summary.json"),
            "telemetry_sha256": sha(run / "telemetry.jsonl"),
            "bridge_sha256": inputs["replacement_scene_probe.lua"],
            "replacement_config_sha256": inputs["replacement.xml"],
        }
    operations = [
        json.loads(line)
        for line in (BASE / CASES[0] / "operations.jsonl").read_text().splitlines()
    ]
    uncertain = next(
        row for row in operations if row["kind"] == "uncertain_ack_reconciled"
    )
    assert (
        not uncertain["transport"]["returned"]
        and uncertain["transport"]["last_error"] == 1460
    )
    assert (
        abs(uncertain["applied_delta"] - 0.01) < 1e-5
        and uncertain["replay_applied_delta"] == 0
    )
    source_hashes = read(BASE / CASES[0] / "source-hashes.json")
    game = Path("D:/Games/Farming Simulator 2025/data/placeables")
    for key, path in (
        ("target", game / "brandless/animalHusbandries/specialCalfShed"),
        ("donor", game / "brandless/constructibles/farmGarageConstructable02"),
    ):
        actual = {
            str(f.relative_to(path)): sha(f) for f in path.rglob("*") if f.is_file()
        }
        assert actual == source_hashes[key], "installed source changed"
    saved_root = ET.parse(BASE / CASES[0] / "asset/specialCalfShed.i3d").getroot()
    references = [f.get("filename") for f in saved_root.findall("./Files/File")]
    assert all(name.startswith("$data/") for name in references)
    for name in references:
        resource = game.parent / name.removeprefix("$data/")
        assert resource.is_file() or resource.with_suffix(".dds").is_file(), name
    saved_hashes = {p.name: sha(p) for p in (BASE / CASES[0] / "asset").glob("*.i3d*")}
    for case in CASES[1:]:
        assert all(
            sha(BASE / case / "asset" / name) == digest
            for name, digest in saved_hashes.items()
        )
    value = {
        "date": "2026-10-17",
        "status": "passed_bounded_research",
        "target": "specialCalfShed.i3d",
        "donor": "farmGarageConstructable02.i3d",
        "target_node": TARGET_PATH,
        "donor_node": "farmGarageBuildable02/visual/visual_lod/farmGarageBuildable02_lod0/phase07/doorLeftSmall_lod0",
        "scene_nodes_before": 50,
        "scene_nodes_after": 51,
        "shapes_before": 25,
        "shapes_after": 26,
        "other_gate_controls": 8,
        "original_bounds_parent_space": target,
        "imported_bounds_parent_space": imported["replacementBounds"],
        "fitted_bounds_parent_space": fit,
        "reloaded_bounds_parent_space": fresh,
        "replacement_scale": new[REPLACEMENT_PATH]["scale"],
        "fit_errors_m": fit_errors,
        "fresh_reload_errors_m": reload_errors,
        "other_nodes_max_transform_rounding": max_delta,
        "other_nodes_with_transform_rounding": rounded_nodes,
        "other_nodes_geometry_signatures_match": True,
        "replacement_geometry_signatures_survive_reload": True,
        "uncertain_ack": {
            "native_timeout_ms": 100,
            "win32_error": 1460,
            "applied_delta_x": uncertain["applied_delta"],
            "same_sequence_replay_delta_x": 0,
        },
        "forced_exit": {
            "exit_code": 73,
            "saved_x": expected_x,
            "unsaved_x": unsaved_x,
            "recovered_x": recovered_x,
            "saved_asset_hashes_unchanged": True,
            "same_original_path_recovery_x": same_path_x,
            "same_original_path_verified": True,
        },
        "native_save_resource_refs": len(references),
        "resource_refs_all_game_data": True,
        "source_files_unchanged": {
            key: len(value) for key, value in source_hashes.items()
        },
        "image_before_after": image_difference(
            BASE / CASES[0] / "view-000003.png", BASE / CASES[0] / "view-000016.png"
        ),
        "image_saved_reload": image_difference(
            BASE / CASES[0] / "view-000019.png", BASE / CASES[1] / "view-000002.png"
        ),
        "image_reload_recovered": image_difference(
            BASE / CASES[1] / "view-000002.png", BASE / CASES[3] / "view-000002.png"
        ),
        "cases": case_results,
        "limits": [
            "Rigid zero-local-rotation subtree fitting only; Z depth not scaled.",
            "Geometry digests quantize vertex positions; normals, UVs, indices and gameplay behavior were not checked.",
            "No claim of transactional multi-file save, recovery after crash during Save, or deduplication across editor restart.",
            "No live private-desktop viewing or switching was performed.",
            "Shared materials and textures remain installed-game data dependencies; this is not a standalone mod package.",
        ],
    }
    args.output.write_text(
        json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "status": value["status"],
                "fit_max_error_m": max(fit_errors.values()),
                "reload_max_error_m": max(reload_errors.values()),
                "cases": len(case_results),
                "pngs": sum(c["native_pngs"] for c in case_results.values()),
            }
        )
    )


if __name__ == "__main__":
    main()
