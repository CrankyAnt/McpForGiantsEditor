"""Derive practical-test evidence from isolated local Editor receipts.

Reads scratch files only. Output omits machine paths, PIDs and vendor content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from practical_windows_probe import ASSETS, SCRATCH


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xml_counts(root):
    return {
        tag: len(root.findall(".//" + tag))
        for tag in ("Shape", "TransformGroup", "Material", "File", "Animation")
    }


def material_descriptors(root):
    files = {n.get("fileId"): n.get("filename") for n in root.findall("Files/File")}

    def value(text):
        try:
            return [float(part) for part in text.split()]
        except ValueError:
            return text

    def descriptor(element):
        attrs = {}
        for key, text in element.attrib.items():
            if key == "materialId":
                continue
            attrs[key] = (
                files.get(text, text)
                if key in ("fileId", "customShaderId")
                else value(text)
            )
        children = [descriptor(child) for child in element]
        return [
            element.tag,
            attrs,
            sorted(children, key=lambda x: json.dumps(x, sort_keys=True)),
        ]

    return {
        node.get("name"): descriptor(node)
        for node in root.findall("Materials/Material")
    }


def asset_result(label, filename):
    run = SCRATCH / label
    spec = json.loads((run / "spec.json").read_text())
    original = ET.parse(run / "baseline/fresh-readback.xml").getroot()
    fresh = ET.parse(run / "fresh-readback.xml").getroot()
    before = ET.parse(run / "before.i3d").getroot()
    saved = ET.parse(run / "asset" / filename).getroot()
    left = {n.get("path"): n.attrib for n in original.findall("node")}
    right = {n.get("path"): n.attrib for n in fresh.findall("node")}
    assert left.keys() == right.keys(), "node paths changed"
    stable_keys = ("shape", "materials", "vertices", "vertexDigestA", "vertexDigestB")
    assert all(
        all(a.get(k) == right[path].get(k) for k in stable_keys)
        for path, a in left.items()
    ), "runtime shape/material/vertex signature changed"
    assert all(a["name"] == right[path]["name"] for path, a in left.items() if path), (
        "node name changed"
    )
    target = [float(fresh.findtext("target" + axis)) for axis in "XYZ"]
    assert target == [7.25, -1.5, 2.125], "saved mutation not reloaded"
    clips_before = [n.attrib for n in original.findall("clip")]
    clips_after = [n.attrib for n in fresh.findall("clip")]
    assert clips_before == clips_after, "animation binding changed"
    changes = []
    for path, a in left.items():
        if path == "/0":
            continue
        deltas = {
            axis: float(right[path][axis]) - float(a[axis])
            for axis in "xyz"
            if float(right[path][axis]) != float(a[axis])
        }
        if deltas:
            changes.append({"node_path": path, "deltas": deltas})
    baseline = json.loads((run / "source-hashes.json").read_text())
    source = Path(spec["source"]).parent
    assert baseline == {p.name: digest(p) for p in source.iterdir() if p.is_file()}, (
        "installed asset changed"
    )
    dispatch_paths = sorted(run.glob("dispatch-*.json"))
    assert {p.name for p in dispatch_paths} == {
        f"dispatch-{i:03}.json" for i in range(1, 14)
    }, "missing or extra script-dispatch receipts"
    dispatches = [json.loads(p.read_text()) for p in dispatch_paths]
    assert all(r["action"] == "script" and r["fixture"] == label for r in dispatches)

    save_dispatch = json.loads((run / "native-save.json").read_text())
    assert save_dispatch["dispatch"]["status"] == "returned", "Save transport failed"
    assert all(r["dispatch"]["returned"] for r in dispatches), "script transport failed"
    save_receipt_path = run / "save-001.xml"
    save_receipt = ET.parse(save_receipt_path).getroot()
    assert save_receipt.findtext("ok") == "true", "Save callback failed"
    normalized_scene = Path(spec["scene"]).as_posix().casefold()
    assert (
        save_receipt.findtext("scene").replace("\\", "/").casefold() == normalized_scene
    )
    assert (
        save_receipt.findtext("callbackPath").replace("\\", "/").casefold()
        == normalized_scene
    )
    assert [float(save_receipt.findtext("target" + k)) for k in "XYZ"] == target
    assert (
        save_receipt_path.stat().st_mtime_ns
        >= (run / "response-012.xml").stat().st_mtime_ns
    ), "Save callback predates final work request"
    assert (
        save_receipt_path.stat().st_mtime_ns
        <= (run / "native-save.json").stat().st_mtime_ns
    ), "Save callback postdates dispatch result"
    for receipt in dispatches[:-1] + [save_dispatch]:
        assert receipt["before"]["iconic"] and receipt["after"]["iconic"]
        assert (
            not receipt["before"]["foreground_is_editor"]
            and not receipt["after"]["foreground_is_editor"]
        )
        assert receipt["foreground_unchanged"]
    for sequence in range(1, 14):
        request = run / f"request-{sequence:03}.xml"
        response = run / f"response-{sequence:03}.xml"
        parsed = ET.parse(response).getroot()
        receipt = dispatches[sequence - 1]
        assert receipt["action"] == "script" and receipt["dispatch"]["returned"]
        assert response.stat().st_mtime_ns >= request.stat().st_mtime_ns
        assert (
            parsed.findtext("requestId") == str(sequence)
            and parsed.findtext("ok") == "true"
        )
        if sequence == 4:
            assert [float(parsed.findtext("expected" + k)) for k in "XYZ"] == target
    materials_before = material_descriptors(before)
    materials_after = material_descriptors(saved)
    shader = (
        Path(spec["source"]).parents[3] / "shaders/vehicleShader.xml"
        if label == "water-trailer"
        else None
    )
    defaults = {}
    if shader is not None:
        defaults = {
            n.get("name"): [float(v) for v in n.get("defaultValue").split()]
            for n in ET.parse(shader).getroot().findall(".//Parameter")
            if n.get("defaultValue")
        }
    removed = []
    colors = []
    for material in before.findall("Materials/Material"):
        name = material.get("name")
        other = next(
            n for n in saved.findall("Materials/Material") if n.get("name") == name
        )
        if material.get("diffuseColor") != other.get("diffuseColor"):
            colors.append(
                {
                    "material": name,
                    "before": material.get("diffuseColor"),
                    "after": other.get("diffuseColor"),
                }
            )
        present = {n.get("name") for n in other.findall("CustomParameter")}
        for parameter in material.findall("CustomParameter"):
            if parameter.get("name") not in present:
                value = [float(v) for v in parameter.get("value").split()]
                default = defaults.get(parameter.get("name"))
                removed.append(
                    {
                        "material": name,
                        "parameter": parameter.get("name"),
                        "value": value,
                        "shader_default": default,
                        "equals_shader_default": value == default,
                    }
                )
    sidecars = []
    for suffix in (".shapes", ".anim"):
        path = run / "asset" / (filename + suffix)
        if path.exists():
            sidecars.append(
                {
                    "suffix": suffix,
                    "bytes_after": path.stat().st_size,
                    "bytes_before": (run / "baseline/asset" / path.name).stat().st_size,
                    "different_bytes_in_common_prefix": sum(
                        a != b
                        for a, b in zip(
                            (run / "baseline/asset" / path.name).read_bytes(),
                            path.read_bytes(),
                        )
                    ),
                    "sha256_before": baseline[path.name],
                    "sha256_after": digest(path),
                    "bytes_unchanged": digest(path) == baseline[path.name],
                }
            )
    return {
        "fixture": label,
        "source_basename": filename,
        "source_file_count": len(baseline),
        "installed_source_hashes_unchanged": True,
        "xml_counts_before": xml_counts(before),
        "xml_counts_after": xml_counts(saved),
        "node_count": len(left),
        "runtime_shapes": int(fresh.findtext("shapeCount")),
        "runtime_material_slots": int(fresh.findtext("materialCount")),
        "runtime_vertices": sum(int(a["vertices"]) for a in left.values()),
        "node_paths_and_nonroot_names_equal": True,
        "quantized_vertex_digests_and_slot_counts_equal": True,
        "vertex_digest_resolution": 0.000001,
        "vertex_digest_is_cryptographic": False,
        "material_xml_descriptors_equal": materials_before == materials_after,
        "material_diffuse_color_changes": colors,
        "removed_material_parameters": removed,
        "material_xml_differing_names": sorted(
            k
            for k in materials_before.keys() | materials_after.keys()
            if materials_before.get(k) != materials_after.get(k)
        ),
        "animation_clip_bindings_equal": True,
        "animation_clip_binding_count": len(clips_after),
        "distinct_clip_name_duration_pairs": len(
            {(n["name"], n["duration"]) for n in clips_after}
        ),
        "saved_target_translation": target,
        "document_root_name_before": left[""]["name"],
        "document_root_name_after": right[""]["name"],
        "other_translation_changes": changes,
        "max_other_translation_delta": max(
            (abs(d) for change in changes for d in change["deltas"].values()), default=0
        ),
        "all_mutation_save_checks_iconic_and_foreground_other": True,
        "save_callback_ok_and_expected_document": True,
        "save_callback_after_last_work_response": True,
        "exact_save_dispatch_start_time_retained": False,
        "foreground_unchanged_each_work_dispatch": True,
        "script_requests": 13,
        "baseline_readback_sha256": digest(run / "baseline/fresh-readback.xml"),
        "source_receipt_hashes": {
            name: digest(run / name)
            for name in ("initial-ready.xml", "save-001.xml", "fresh-readback.xml")
        },
        "sidecars": sidecars,
        "local_textures_unchanged": all(
            digest(run / "asset" / name) == h
            for name, h in baseline.items()
            if name.endswith(".dds")
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    simple_run = SCRATCH / "foreground-simple"
    simple = json.loads((simple_run / "summary.json").read_text())
    records = json.loads((simple_run / "foreground-trial.json").read_text())
    assert all(
        simple[k]
        for k in (
            "all_iconic",
            "all_foreground_other_process",
            "foreground_unchanged_each_dispatch",
        )
    )
    assert len(records) == simple["requests"] == 30
    assert all(
        n["before"]["iconic"]
        and n["after"]["iconic"]
        and not n["before"]["foreground_is_editor"]
        and not n["after"]["foreground_is_editor"]
        and n["before"]["foreground_hwnd"] == n["after"]["foreground_hwnd"]
        for n in records
    )
    result = {
        "format": 1,
        "binary_sha256": "c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d",
        "simple_background": {
            k: simple[k]
            for k in (
                "requests",
                "all_iconic",
                "all_foreground_other_process",
                "foreground_unchanged_each_dispatch",
                "foreground_distinct_processes",
                "saved_translation",
            )
        },
        "simple_dispatch_latency_ms_range": [
            min(n["latency_ms"] for n in records),
            max(n["latency_ms"] for n in records),
        ],
        "assets": [asset_result(label, filename) for label, filename in ASSETS.items()],
        "limitations": [
            "No UI rendering or in-game acceptance.",
            "Animation bindings and durations only; no playback or keyframe equivalence proof.",
            "Vertex digests are rounded checks, not bitwise geometry or triangle-topology proof.",
            "One other foreground process was observed in the sampled data; user interaction was not instrumented.",
        ],
    }
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"output": args.output.name, "assets": len(result["assets"])}))


if __name__ == "__main__":
    main()
