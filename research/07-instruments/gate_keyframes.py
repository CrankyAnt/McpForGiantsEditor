"""Inspect only the known sentinel gate animation fixtures, without Editor.

This bounded reader accepts the observed little-endian header words 7/10 and
flag-3 records. It is not a general I3D animation decoder. Six float components
are compared without assuming their units or interpolation semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from xml.etree import ElementTree as ET


def node_map(scene):
    result = {}

    def visit(element, path):
        identifier = element.get("nodeId")
        if identifier is not None:
            if int(identifier) in result:
                raise ValueError("duplicate_scene_node_id")
            result[int(identifier)] = (path, element.get("name"))
        for index, child in enumerate(element):
            visit(child, path + "/" + str(index))

    root = ET.parse(scene).getroot().find("Scene")
    if root is None:
        raise ValueError("missing_scene")
    for index, child in enumerate(root):
        visit(child, "/" + str(index))
    return result


def read_animation(path, scene):
    data = path.read_bytes()
    offset = 0

    def take(fmt):
        nonlocal offset
        size = struct.calcsize(fmt)
        if offset + size > len(data):
            raise ValueError("truncated_animation")
        values = struct.unpack_from(fmt, data, offset)
        offset += size
        return values

    def text():
        nonlocal offset
        (length,) = take("<I")
        if not 0 < length <= 256 or offset + length > len(data):
            raise ValueError("invalid_string_length")
        value = data[offset : offset + length].decode("ascii")
        offset += length
        padded = (offset + 3) & ~3
        if padded > len(data) or any(data[offset:padded]):
            raise ValueError("invalid_string_padding")
        offset = padded
        return value

    leading, sets = take("<II")
    if leading not in (7, 10) or sets != 1:
        raise ValueError("unsupported_header")
    charset = text()
    (clips,) = take("<I")
    if charset != "sentinelGarageGate" or clips != 1:
        raise ValueError("unsupported_character_set")
    clip = text()
    duration, track_count = take("<fI")
    if clip != "sentinelGarage_gateSource" or duration != 10000 or track_count != 7:
        raise ValueError("unsupported_clip")
    nodes = node_map(scene)
    tracks = []
    seen = set()
    for _ in range(track_count):
        node, count = take("<II")
        if node not in nodes or node in seen or not 0 < count <= 10000:
            raise ValueError("invalid_track_target_or_count")
        seen.add(node)
        keys = []
        last_time = -math.inf
        for _ in range(count):
            record_offset = offset
            timestamp, flags, *values = take("<fI6f")
            (time_bits,) = struct.unpack_from("<I", data, record_offset)
            bits = struct.unpack_from("<6I", data, offset - 24)
            if flags != 3:
                raise ValueError("unsupported_key_flags")
            if (
                not all(math.isfinite(v) for v in (timestamp, *values))
                or not last_time <= timestamp <= duration
            ):
                raise ValueError("invalid_key_time_or_value")
            last_time = timestamp
            keys.append(
                {
                    "time": timestamp,
                    "time_bits": time_bits,
                    "flags": flags,
                    "values": values,
                    "value_bits": bits,
                }
            )
        if keys[0]["time"] != 0 or keys[-1]["time"] != duration:
            raise ValueError("unsupported_time_range")
        path_name, name = nodes[node]
        tracks.append({"node_id": node, "path": path_name, "name": name, "keys": keys})
    if offset != len(data):
        raise ValueError("unparsed_trailing_data")
    return {
        "leading_word": leading,
        "charset": charset,
        "clip": clip,
        "duration": duration,
        "tracks": tracks,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def compare(before, after):
    left = {t["path"]: t for t in before["tracks"]}
    right = {t["path"]: t for t in after["tracks"]}
    if left.keys() != right.keys():
        raise ValueError("track_target_paths_changed")
    result = []
    for path in sorted(left):
        a, b = left[path], right[path]
        if a["name"] != b["name"]:
            raise ValueError("track_target_name_changed")
        pairs = list(zip(a["keys"], b["keys"]))
        result.append(
            {
                "node_path": path,
                "node_name": a["name"],
                "node_id_before": a["node_id"],
                "node_id_after": b["node_id"],
                "keys_before": len(a["keys"]),
                "keys_after": len(b["keys"]),
                "key_times_bits_equal": len(a["keys"]) == len(b["keys"])
                and all(x["time_bits"] == y["time_bits"] for x, y in pairs),
                "flags_equal": all(x["flags"] == y["flags"] for x, y in pairs),
                "changed_numeric_records": sum(
                    x["values"] != y["values"] for x, y in pairs
                ),
                "changed_bit_records": sum(
                    x["value_bits"] != y["value_bits"] for x, y in pairs
                ),
                "maximum_component_absolute_deltas": [
                    max(
                        (abs(x["values"][i] - y["values"][i]) for x, y in pairs),
                        default=0,
                    )
                    for i in range(6)
                ],
            }
        )
    return {
        "method": "bounded sentinel gate header-7/header-10 flag-3 record comparison",
        "component_units_and_interpolation_not_established": True,
        "before_sha256": before["sha256"],
        "after_sha256": after["sha256"],
        "leading_word_before": before["leading_word"],
        "leading_word_after": after["leading_word"],
        "duration_before": before["duration"],
        "duration_after": after["duration"],
        "bytes_before": before["bytes"],
        "bytes_after": after["bytes"],
        "total_keys_before": sum(len(t["keys"]) for t in before["tracks"]),
        "total_keys_after": sum(len(t["keys"]) for t in after["tracks"]),
        "tracks": result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--before-scene", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--after-scene", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(
        read_animation(args.before, args.before_scene),
        read_animation(args.after, args.after_scene),
    )
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "keys_before": result["total_keys_before"],
                "keys_after": result["total_keys_after"],
                "output": args.output.name,
            }
        )
    )


if __name__ == "__main__":
    main()
