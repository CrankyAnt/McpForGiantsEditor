"""Analyze the bounded GIANTS Editor fidelity experiment.

The reader accepts only the receipts produced by ``fidelity_scene_probe.lua``
and the prepared six-case manifest. It records missing runtime observations as
pending evidence instead of inferring a result. It does not claim general I3D
format equivalence or coverage of unobserved instants.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET

from gate_keyframes import compare as compare_keyframes
from gate_keyframes import read_animation

try:
    from PIL import Image
except ImportError:  # pragma: no cover - reported as unavailable evidence
    Image = None


RUNS = (
    "water-baseline",
    "water-native",
    "water-manual",
    "gate-baseline",
    "gate-native",
    "gate-manual",
)
IMAGE_NAMES = {
    "water": ("view.png", "repeat.png"),
    "gate": ("start.png", "repeat.png", "middle.png", "end.png"),
}
POSE_ATTRS = ("x", "y", "z", "rx", "ry", "rz", "sx", "sy", "sz", "qx", "qy", "qz", "qw")
PERSPECTIVE_PATH = "/1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite_number(value: str | None) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite_numeric_value")
    return result


def nodes(root: ET.Element) -> dict[str, ET.Element]:
    return {n.get("path", ""): n for n in root.findall(".//node")}


def node_pose(node: ET.Element) -> tuple[float, ...]:
    return tuple(finite_number(node.get(key)) for key in POSE_ATTRS)


def compare_receipts(before: Path, after: Path) -> dict:
    left = ET.parse(before).getroot()
    right = ET.parse(after).getroot()
    a, b = nodes(left), nodes(right)
    paths_equal = set(a) == set(b)
    records = []
    for path in sorted(set(a) & set(b)):
        an, bn = a[path], b[path]
        pose_a, pose_b = node_pose(an), node_pose(bn)
        records.append(
            {
                "path": path,
                "name_before": an.get("name"),
                "name_after": bn.get("name"),
                "name_equal": an.get("name") == bn.get("name") or path == "",
                "pose_max_absolute_delta": max(
                    (abs(x - y) for x, y in zip(pose_a, pose_b)), default=0.0
                ),
                "pose_equal": pose_a == pose_b,
                "material_children_equal": [
                    ET.tostring(x, encoding="unicode") for x in an
                ]
                == [ET.tostring(x, encoding="unicode") for x in bn],
            }
        )

    def material_slots(mapping):
        return sorted(
            (
                path,
                child.get("slot"),
                child.get("success"),
                child.get("r"),
                child.get("g"),
                child.get("b"),
                child.get("a"),
            )
            for path, node in mapping.items()
            for child in node.findall("material")
        )

    return {
        "before": before.name,
        "after": after.name,
        "paths_equal": paths_equal,
        "node_count_before": len(a),
        "node_count_after": len(b),
        "document_root_name_before": a.get("", ET.Element("node")).get("name"),
        "document_root_name_after": b.get("", ET.Element("node")).get("name"),
        "document_root_name_ignored": True,
        "scene_path_and_node_paths_are_reported_only": True,
        "nodes": records,
        "max_pose_absolute_delta": max(
            (r["pose_max_absolute_delta"] for r in records), default=0.0
        ),
        "material_slots_before": material_slots(a),
        "material_slots_after": material_slots(b),
        "material_slot_availability_equal": material_slots(a) == material_slots(b),
        "material_success_slot_count_before": sum(
            x[2] == "true" for x in material_slots(a)
        ),
        "material_success_slot_count_after": sum(
            x[2] == "true" for x in material_slots(b)
        ),
        "material_value_equivalence_claimed": False,
    }


def quaternion_angle(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    # POSE_ATTRS stores qx,qy,qz,qw at positions 9..12. Normalize before the
    # absolute dot product so q and -q represent the same orientation.
    a = left[9:13]
    b = right[9:13]
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        raise ValueError("zero_quaternion")
    if a == b or a == tuple(-x for x in b):
        return 0.0
    dot = max(-1.0, min(1.0, abs(sum(x * y for x, y in zip(a, b)) / (na * nb))))
    return 2.0 * math.acos(dot)


def compare_samples(before: Path, after: Path) -> dict:
    if not before.exists() or not after.exists():
        return {"status": "pending", "reason": "missing_sample_pair"}
    left = ET.parse(before).getroot().findall(".//clip/frame")
    right = ET.parse(after).getroot().findall(".//clip/frame")
    if len(left) != len(right):
        return {
            "status": "invalid",
            "reason": "frame_count_changed",
            "before": len(left),
            "after": len(right),
        }
    records = []
    for a_frame, b_frame in zip(left, right):
        if a_frame.get("requestedTime") != b_frame.get("requestedTime"):
            return {"status": "invalid", "reason": "requested_times_changed"}
        a_nodes, b_nodes = nodes(a_frame), nodes(b_frame)
        if set(a_nodes) != set(b_nodes):
            return {"status": "invalid", "reason": "sample_node_paths_changed"}
        local = [
            (p, node_pose(a_nodes[p]), node_pose(b_nodes[p]))
            for p in sorted(a_nodes)
            if p != PERSPECTIVE_PATH
        ]
        records.append(
            {
                "requested_time": int(float(a_frame.get("requestedTime"))),
                "max_local_translation_delta": max(
                    (
                        max(abs(x - y) for x, y in zip(pa[:3], pb[:3]))
                        for _, pa, pb in local
                    ),
                    default=0.0,
                ),
                "max_local_euler_delta": max(
                    (
                        max(abs(x - y) for x, y in zip(pa[3:6], pb[3:6]))
                        for _, pa, pb in local
                    ),
                    default=0.0,
                ),
                "max_local_scale_delta": max(
                    (
                        max(abs(x - y) for x, y in zip(pa[6:9], pb[6:9]))
                        for _, pa, pb in local
                    ),
                    default=0.0,
                ),
                "max_quaternion_angular_delta_radians": max(
                    (quaternion_angle(pa, pb) for _, pa, pb in local), default=0.0
                ),
            }
        )
    return {
        "status": "valid",
        "frame_count": len(records),
        "max_local_translation_delta": max(
            (r["max_local_translation_delta"] for r in records), default=0.0
        ),
        "max_local_euler_delta": max(
            (r["max_local_euler_delta"] for r in records), default=0.0
        ),
        "max_local_scale_delta": max(
            (r["max_local_scale_delta"] for r in records), default=0.0
        ),
        "max_quaternion_angular_delta_radians": max(
            (r["max_quaternion_angular_delta_radians"] for r in records), default=0.0
        ),
        "translation_delta_frame_count": sum(
            r["max_local_translation_delta"] != 0 for r in records
        ),
        "euler_delta_frame_count": sum(
            r["max_local_euler_delta"] != 0 for r in records
        ),
    }


def xml_semantics(path: Path) -> list:
    root = ET.parse(path).getroot()

    def clean(element: ET.Element, index_path: str = ""):
        attrs = {}
        for key, value in sorted(element.attrib.items()):
            # These are the only path-like document fields ignored here.
            if key in {"filename", "externalShapesFile", "externalAnimFile"}:
                attrs[key] = "<ignored-document-path>"
            elif key == "name" and index_path == "":
                attrs[key] = "<ignored-document-rootname>"
            else:
                attrs[key] = value
        children = [
            clean(child, f"{index_path}/{i}") for i, child in enumerate(element)
        ]
        if element.tag == "Material":
            children.sort(key=lambda item: json.dumps(item, sort_keys=True))
        return [element.tag, attrs, children]

    return clean(root)


def material_summary(before: Path, after: Path) -> dict:
    left = ET.parse(before).getroot().findall("Materials/Material")
    right = ET.parse(after).getroot().findall("Materials/Material")
    lm = {item.get("name"): dict(sorted(item.attrib.items())) for item in left}
    rm = {item.get("name"): dict(sorted(item.attrib.items())) for item in right}
    names = sorted(lm.keys() | rm.keys())
    return {
        "before_count": len(left),
        "after_count": len(right),
        "names_equal": set(lm) == set(rm),
        "differing_material_names": [
            name for name in names if lm.get(name) != rm.get(name)
        ],
        "before_lambert1": lm.get("lambert1"),
        "after_lambert1": rm.get("lambert1"),
    }


def saved_asset_compare(native: Path, manual: Path) -> dict:
    return {
        "native": native.name,
        "manual": manual.name,
        "semantic_equal_ignoring_document_paths_and_rootname": xml_semantics(native)
        == xml_semantics(manual),
        "native_sha256": digest(native),
        "manual_sha256": digest(manual),
        "raw_xml_bytes_equal": native.read_bytes() == manual.read_bytes(),
    }


def sidecars(native: Path, manual: Path) -> dict:
    result = {}
    for suffix in (".shapes", ".anim"):
        left, right = (
            native.with_suffix(native.suffix + suffix),
            manual.with_suffix(manual.suffix + suffix),
        )
        if left.exists() and right.exists():
            result[suffix] = {
                "native_sha256": digest(left),
                "manual_sha256": digest(right),
                "equal": left.read_bytes() == right.read_bytes(),
                "native_bytes": left.stat().st_size,
                "manual_bytes": right.stat().st_size,
            }
        else:
            result[suffix] = {
                "status": "missing",
                "native_exists": left.exists(),
                "manual_exists": right.exists(),
            }
    return result


def validate_samples(path: Path) -> dict:
    if not path.exists():
        return {"status": "pending", "reason": "missing_samples_xml"}
    root = ET.parse(path).getroot()
    clips = root.findall(".//clip")
    if len(clips) != 1:
        return {
            "status": "invalid",
            "reason": "expected_one_clip",
            "clip_count": len(clips),
        }
    clip = clips[0]
    frames = clip.findall("frame")
    expected_times = [i * 250.0 for i in range(41)]
    times = [finite_number(f.get("requestedTime")) for f in frames]
    track_times = [finite_number(f.get("trackTime")) for f in frames]
    finite = True
    node_counts = []
    motion = []
    previous = None
    for frame in frames:
        frame_nodes = {n.get("path", ""): n for n in frame.findall("node")}
        node_counts.append(len(frame_nodes))
        current = {}
        for p, node in frame_nodes.items():
            try:
                current[p] = node_pose(node)
            except (ValueError, TypeError):
                finite = False
        if previous is not None and current.keys() == previous.keys():
            motion.append(
                any(current[p] != previous[p] for p in current if p != PERSPECTIVE_PATH)
            )
        previous = current
    return {
        "status": "valid"
        if clip.get("name") == "sentinelGarage_gateSource"
        and finite_number(clip.get("duration")) == 10000
        and len(frames) == 41
        and len(motion) == 40
        and times == expected_times
        and track_times == expected_times
        and node_counts == [24] * 41
        and finite
        and all(motion)
        else "invalid",
        "clip_name": clip.get("name"),
        "clip_duration": finite_number(clip.get("duration")),
        "frame_count": len(frames),
        "node_counts": sorted(set(node_counts)),
        "requested_times": times,
        "track_times": track_times,
        "expected_times": expected_times,
        "all_values_finite": finite,
        "all_interframe_motion_excluding_perspective": bool(motion) and all(motion),
        "motion_intervals": len(motion),
    }


def validate_receipt(path: Path, expected_scene: str, kind: str = "save") -> dict:
    if not path.exists():
        return {"status": "pending", "reason": "missing_receipt"}
    root = ET.parse(path).getroot()
    actual_path = (root.findtext("path") or "").replace("\\", "/").casefold()
    actual_scene = (root.findtext("scene") or "").replace("\\", "/").casefold()
    expected = expected_scene.replace("\\", "/").casefold()
    op_matches = root.findtext("op") == kind
    receipt_fields_match = actual_scene == expected and (
        kind == "ready" or actual_path == expected
    )
    return {
        "status": "valid"
        if root.findtext("ok") == "true" and op_matches and receipt_fields_match
        else "invalid",
        "ok": root.findtext("ok") == "true",
        "kind": kind,
        "op_matches_expected_kind": op_matches,
        "path_matches_expected_scene": actual_path == expected
        if kind == "save"
        else None,
        "scene_matches_expected_scene": actual_scene == expected,
        "receipt_path": actual_path,
        "receipt_scene": actual_scene,
    }


def image_metrics(path: Path) -> dict:
    if not path.exists():
        return {"status": "pending", "reason": "missing_image"}
    if Image is None:
        return {"status": "unavailable", "reason": "PIL_not_importable"}
    with Image.open(path) as image:
        image_format = image.format
        rgba = image.convert("RGBA")
        pixels = list(
            rgba.get_flattened_data()
            if hasattr(rgba, "get_flattened_data")
            else rgba.getdata()
        )
    nonblank = sum(
        1 for pixel in pixels if pixel != (0, 0, 0, 0) and pixel[:3] != (0, 0, 0)
    )
    alpha = sum(1 for pixel in pixels if pixel[3] > 0)
    return {
        "status": "valid" if image_format == "PNG" and nonblank > 0 else "invalid",
        "format": image_format,
        "width": rgba.width,
        "height": rgba.height,
        "sha256": digest(path),
        "nonblank_pixels": nonblank,
        "alpha_pixels": alpha,
        "nonblank": nonblank > 0,
    }


def image_pair(a: Path, b: Path) -> dict:
    result = {"a": a.name, "b": b.name}
    if not a.exists() or not b.exists() or Image is None:
        result["status"] = (
            "pending" if not a.exists() or not b.exists() else "unavailable"
        )
        return result
    with Image.open(a) as ia, Image.open(b) as ib:
        pa, pb = ia.convert("RGBA"), ib.convert("RGBA")
        if pa.size != pb.size:
            return {**result, "status": "invalid", "reason": "different_dimensions"}
        xa = list(
            pa.get_flattened_data()
            if hasattr(pa, "get_flattened_data")
            else pa.getdata()
        )
        xb = list(
            pb.get_flattened_data()
            if hasattr(pb, "get_flattened_data")
            else pb.getdata()
        )
    diffs = [max(abs(x[i] - y[i]) for i in range(4)) for x, y in zip(xa, xb)]
    return {
        **result,
        "status": "valid",
        "different_pixels": sum(d > 0 for d in diffs),
        "max_channel_delta": max(diffs, default=0),
        "mean_channel_max_delta": sum(diffs) / len(diffs) if diffs else 0,
    }


def keyframe_pair(
    baseline: Path, saved: Path, baseline_scene: Path, saved_scene: Path
) -> dict:
    if not baseline.exists() or not saved.exists():
        return {"status": "pending", "reason": "missing_gate_animation"}
    return {
        "status": "valid",
        **compare_keyframes(
            read_animation(baseline, baseline_scene), read_animation(saved, saved_scene)
        ),
    }


def save_repeat_result(root: Path, primary_root: Path) -> dict:
    result = {}
    for route in ("gate-native", "gate-manual", "water-native", "water-manual"):
        run = root / route
        spec = json.loads((run / "spec.json").read_text(encoding="utf-8"))
        filename = Path(spec["scene"]).name
        saved = run / "asset" / filename
        first_run = primary_root / route / "asset" / filename
        before = run / "before.i3d"
        first_before = primary_root / route / "before.i3d"
        side = {}
        for suffix in (".shapes", ".anim"):
            path = saved.with_suffix(saved.suffix + suffix)
            first = first_run.with_suffix(first_run.suffix + suffix)
            side[suffix] = {
                "repeat_sha256": digest(path) if path.exists() else None,
                "first_run_sha256": digest(first) if first.exists() else None,
                "equal_to_first_run": path.exists()
                and first.exists()
                and path.read_bytes() == first.read_bytes(),
            }
            if not path.exists() and not first.exists():
                side[suffix] = {
                    "status": "not_applicable",
                    "reason": "water_fixture_has_no_animation",
                }
        result[route] = {
            "before_sha256": digest(before) if before.exists() else None,
            "first_run_before_sha256": digest(first_before)
            if first_before.exists()
            else None,
            "before_equal_to_first_run": before.exists()
            and first_before.exists()
            and before.read_bytes() == first_before.read_bytes(),
            "save_receipt": validate_receipt(run / "save-001.xml", spec["scene"]),
            "fresh_receipt": validate_receipt(
                run / "fresh-ready.xml", spec["scene"], "ready"
            ),
            "sample_vs_first_run": (
                {"status": "not_applicable", "reason": "water_fixture_has_no_animation"}
                if spec["label"] == "water"
                else compare_samples(
                    run / "samples.xml", primary_root / route / "samples.xml"
                )
            ),
            "check_image_vs_first_run": image_pair(
                run / "check.png",
                primary_root
                / route
                / ("view.png" if spec["label"] == "water" else "middle.png"),
            ),
            "saved_i3d_sha256": digest(saved) if saved.exists() else None,
            "first_run_saved_i3d_sha256": digest(first_run)
            if first_run.exists()
            else None,
            "saved_i3d_equal_to_first_run": saved.exists()
            and first_run.exists()
            and saved.read_bytes() == first_run.read_bytes(),
            "sidecars": side,
        }
    for asset in ("gate", "water"):
        native, manual = result[f"{asset}-native"], result[f"{asset}-manual"]
        result[f"{asset}-cross_route"] = {
            "saved_i3d_equal": native["saved_i3d_sha256"] == manual["saved_i3d_sha256"],
            "sidecars_equal": {
                suffix: (
                    "not_applicable"
                    if native["sidecars"][suffix].get("status") == "not_applicable"
                    else native["sidecars"][suffix]["repeat_sha256"]
                    == manual["sidecars"][suffix]["repeat_sha256"]
                )
                for suffix in (".shapes", ".anim")
            },
        }
    return result


def source_hash_check(run: Path, spec: dict) -> dict:
    expected = spec.get("source_hashes", {})
    actual = {}
    original_root = Path(spec["source"]).parent
    original_actual = {}
    original_missing = []
    missing = []
    for name in expected:
        path = run / "asset" / name
        if path.exists():
            actual[name] = digest(path)
        else:
            missing.append(name)
        original_path = original_root / name
        if original_path.exists():
            original_actual[name] = digest(original_path)
        else:
            original_missing.append(name)
    original_mismatches = sorted(
        name for name in original_actual if original_actual[name] != expected[name]
    )
    prepared = run / "before.i3d"
    prepared_expected = spec.get("prepared_i3d_sha256")
    prepared_actual = digest(prepared) if prepared.exists() else None
    return {
        "expected_file_count": len(expected),
        "copied_file_count": len(actual),
        "copied_missing": missing,
        "copied_hash_mismatches_against_original": sorted(
            name for name in actual if actual[name] != expected[name]
        ),
        "prepared_i3d_sha256_expected": prepared_expected,
        "prepared_i3d_sha256_actual": prepared_actual,
        "prepared_i3d_hash_matches": prepared_expected is not None
        and prepared_actual == prepared_expected,
        "original_source_root": str(original_root),
        "original_file_count": len(original_actual),
        "original_missing": original_missing,
        "original_hash_mismatches": original_mismatches,
        "original_source_hashes_match": not original_missing
        and not original_mismatches,
    }


def case_result(root: Path, run_name: str) -> dict:
    run = root / run_name
    spec = json.loads((run / "spec.json").read_text(encoding="utf-8"))
    result = {
        "case": run_name,
        "asset": spec["label"],
        "mode": spec["mode"],
        "source_hashes": source_hash_check(run, spec),
        "files": {
            name: digest(run / name)
            for name in ("spec.json", "before.i3d")
            if (run / name).exists()
        },
    }
    result["save_receipt"] = (
        validate_receipt(run / "save-001.xml", spec["scene"])
        if spec["mode"] in ("native", "manual")
        else {"status": "not_applicable"}
    )
    saved_asset = run / "asset" / Path(spec["scene"]).name
    result["material_semantics_before_vs_saved"] = (
        material_summary(run / "before.i3d", saved_asset)
        if saved_asset.exists()
        else {"status": "pending"}
    )
    ready = run / "ready.xml"
    fresh = run / "fresh-ready.xml"
    result["ready"] = {
        **validate_receipt(ready, spec["scene"], "ready"),
        "sha256": digest(ready) if ready.exists() else None,
    }
    result["fresh_ready"] = {
        **(
            {"status": "not_applicable"}
            if spec["mode"] == "baseline"
            else validate_receipt(fresh, spec["scene"], "ready")
        ),
        "sha256": digest(fresh) if fresh.exists() else None,
    }
    if ready.exists() and fresh.exists():
        result["ready_vs_fresh"] = compare_receipts(ready, fresh)
    result["samples"] = (
        {"status": "not_applicable", "reason": "water_fixture_has_no_animation"}
        if spec["label"] == "water"
        else validate_samples(run / "samples.xml")
    )
    images = {name: image_metrics(run / name) for name in IMAGE_NAMES[spec["label"]]}
    result["images"] = images
    first = "view.png" if spec["label"] == "water" else "start.png"
    result["repeat_noise"] = image_pair(run / first, run / "repeat.png")
    result["repeat_noise"]["interpretation"] = (
        "one pairwise capture comparison, not a statistical noise bound"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--repeat-root", type=Path)
    parser.add_argument("--timing-root", type=Path)
    parser.add_argument("--save-repeat-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runs = [
        case_result(args.root, name)
        for name in RUNS
        if (args.root / name / "spec.json").exists()
    ]
    by_asset = {}
    for item in runs:
        by_asset.setdefault(item["asset"], {})[item["mode"]] = item
    for asset, values in by_asset.items():
        native = values.get("native")
        manual = values.get("manual")
        if native and manual:
            np = args.root / f"{asset}-native" / "asset"
            mp = args.root / f"{asset}-manual" / "asset"
            filename = Path(
                json.loads(
                    (args.root / f"{asset}-native" / "spec.json").read_text(
                        encoding="utf-8"
                    )
                )["scene"]
            ).name
            if filename:
                values["saved_asset_compare"] = saved_asset_compare(
                    np / filename, mp / filename
                )
                values["sidecars"] = sidecars(np / filename, mp / filename)
                values["sample_pair_native_manual"] = compare_samples(
                    args.root / f"{asset}-native" / "samples.xml",
                    args.root / f"{asset}-manual" / "samples.xml",
                )
                values["sample_pairs_baseline_saved"] = {
                    "baseline_vs_native": compare_samples(
                        args.root / f"{asset}-baseline" / "samples.xml",
                        args.root / f"{asset}-native" / "samples.xml",
                    ),
                    "baseline_vs_manual": compare_samples(
                        args.root / f"{asset}-baseline" / "samples.xml",
                        args.root / f"{asset}-manual" / "samples.xml",
                    ),
                }
                if asset == "water":
                    values["sample_pair_native_manual"] = {
                        "status": "not_applicable",
                        "reason": "water_fixture_has_no_animation",
                    }
                    values["sample_pairs_baseline_saved"] = {
                        "status": "not_applicable",
                        "reason": "water_fixture_has_no_animation",
                    }
                baseline_asset = args.root / f"{asset}-baseline" / "asset" / filename
                baseline_anim = baseline_asset.with_suffix(
                    baseline_asset.suffix + ".anim"
                )
                saved_anim = (np / filename).with_suffix(
                    (np / filename).suffix + ".anim"
                )
                values["keyframes"] = {
                    "baseline_vs_native": keyframe_pair(
                        baseline_anim, saved_anim, baseline_asset, np / filename
                    ),
                    "baseline_vs_manual": keyframe_pair(
                        baseline_anim,
                        (mp / filename).with_suffix((mp / filename).suffix + ".anim"),
                        baseline_asset,
                        mp / filename,
                    ),
                    "native_vs_manual": keyframe_pair(
                        saved_anim,
                        (mp / filename).with_suffix((mp / filename).suffix + ".anim"),
                        np / filename,
                        mp / filename,
                    ),
                }
                if asset == "water":
                    values["keyframes"] = {
                        key: {
                            "status": "not_applicable",
                            "reason": "water_fixture_has_no_animation",
                        }
                        for key in values["keyframes"]
                    }
                values["image_pairs"] = {
                    image: {
                        "baseline_native": image_pair(
                            args.root / f"{asset}-baseline" / image,
                            args.root / f"{asset}-native" / image,
                        ),
                        "baseline_manual": image_pair(
                            args.root / f"{asset}-baseline" / image,
                            args.root / f"{asset}-manual" / image,
                        ),
                        "native_manual": image_pair(
                            args.root / f"{asset}-native" / image,
                            args.root / f"{asset}-manual" / image,
                        ),
                    }
                    for image in IMAGE_NAMES[asset]
                }
    if args.repeat_root:
        for item in runs:
            repeat_case = args.repeat_root / item["case"]
            if not repeat_case.exists():
                item["repeat_capture"] = {
                    "status": "pending",
                    "reason": "missing_repeat_case",
                }
                continue
            names = IMAGE_NAMES[item["asset"]]
            item["repeat_capture"] = {
                "provenance": "capture-only repeat checkout; no save-route proof",
                "pairs": {
                    name: (
                        {
                            "status": "not_comparable_by_design",
                            "reason": "water_repeat_is_1024_and_primary_is_512",
                        }
                        if item["asset"] == "water"
                        else image_pair(
                            args.root / item["case"] / name, repeat_case / name
                        )
                    )
                    for name in names
                    if (repeat_case / name).exists()
                },
                "minimized_pairs": {
                    name: image_pair(
                        args.root / item["case"] / name,
                        repeat_case / f"{name[:-4]}_minimized.png",
                    )
                    for name in names
                    if (repeat_case / f"{name[:-4]}_minimized.png").exists()
                },
                "minimized_state": json.loads(
                    (repeat_case / "minimized-state.json").read_text(encoding="utf-8")
                )
                if (repeat_case / "minimized-state.json").exists()
                else {"status": "not_applicable"},
            }
    repeat_within = {"status": "not_provided"}
    if args.repeat_root:
        repeat_within = {}
        for asset in ("gate", "water"):
            names = IMAGE_NAMES[asset]

            def repeat_path(route, name, asset_name=asset):
                candidate = args.repeat_root / f"{asset_name}-{route}" / name
                if candidate.exists():
                    return candidate
                if (
                    asset_name == "gate"
                    and route == "manual"
                    and name in ("start.png", "end.png")
                ):
                    minimized = candidate.with_name(name[:-4] + "_minimized.png")
                    if minimized.exists():
                        return minimized
                return candidate

            def repeat_pair(left, right):
                if not left.exists() or not right.exists():
                    return {
                        "status": "not_collected",
                        "reason": "capture_pair_not_collected",
                    }
                return image_pair(left, right)

            repeat_within[asset] = {
                "pairs": {
                    name: {
                        "baseline_native": repeat_pair(
                            repeat_path("baseline", name), repeat_path("native", name)
                        ),
                        "baseline_manual": repeat_pair(
                            repeat_path("baseline", name), repeat_path("manual", name)
                        ),
                        "native_manual": repeat_pair(
                            repeat_path("native", name), repeat_path("manual", name)
                        ),
                    }
                    for name in names
                },
                "view_repeat_noise": {
                    route: repeat_pair(
                        repeat_path(
                            route, "start.png" if asset == "gate" else "view.png"
                        ),
                        repeat_path(route, "repeat.png"),
                    )
                    for route in ("baseline", "native", "manual")
                },
            }
    timing = {"status": "not_provided"}
    if args.timing_root:
        timing_path = args.timing_root / "gate-baseline" / "render-timing.json"
        if timing_path.exists():
            observations = json.loads(timing_path.read_text(encoding="utf-8"))
            timing = {
                "status": "valid",
                "poses": [item.get("pose") for item in observations],
                "observation_ms": sorted(
                    {item.get("observation_ms") for item in observations}
                ),
                "first_decodable_ms": {
                    item["pose"]: min(
                        (
                            version["after_launch_ms"]
                            for version in item["file_versions"]
                            if version.get("decodable")
                        ),
                        default=None,
                    )
                    for item in observations
                },
                "no_later_change_observed_within_ms": max(
                    (item.get("observation_ms", 0) for item in observations), default=0
                ),
                "limitation": "bounded file-write timing evidence; it does not establish generic GPU quiescence",
            }
    source_checks = [
        item["source_hashes"]["original_source_hashes_match"] for item in runs
    ]
    save_repeat = (
        save_repeat_result(args.save_repeat_root, args.root)
        if args.save_repeat_root
        else {"status": "not_provided"}
    )
    result = {
        "format": 1,
        "experiment": "controlled_giants_editor_fidelity",
        "scope": {
            "cases": RUNS,
            "source_hashes_verified_against_original_sources": bool(source_checks)
            and all(source_checks),
            "document_paths_and_rootnames": "ignored only in semantic comparison and reported separately",
            "perspective_camera_path_excluded_from_scene_motion": PERSPECTIVE_PATH,
            "coverage_limit": "captured frames and files only; no claim about unobserved instants or general format equivalence",
            "render_timing": timing,
            "repeat_within_routes": repeat_within,
            "save_repeat": save_repeat,
        },
        "cases": by_asset,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "cases": len(runs),
                "pending_cases": sum(
                    1
                    for item in runs
                    if item["ready"]["status"] == "pending"
                    or item["fresh_ready"]["status"] == "pending"
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
