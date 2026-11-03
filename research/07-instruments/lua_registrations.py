#!/usr/bin/env python3
"""Extract bounded, reproducible Lua-registration evidence from GIANTS Editor.

The JSON output intentionally contains names, RVAs, and classification only. It
does not emit bytes or disassembly from the proprietary executable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from collections import defaultdict
from pathlib import Path

import capstone
import pefile

EXPECTED_SHA256 = "c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d"
KNOWN_NAMES = ("getSceneFilename", "addUpdateListener", "editorExit")
REGISTRATION_BLOCK = (0x1B4F58, 0x1B8178)
EXPECTED_REGISTRATION_XREFS = {
    "getSceneFilename": (0x1B5552, 0x1B5562, 0x1B558D),
    "addUpdateListener": (0x1B5362, 0x1B5372, 0x1B539D),
    "editorExit": (0x1B5C96, 0x1B5CA6, 0x1B5CD1),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def section_bytes(pe: pefile.PE, name: bytes) -> tuple[int, bytes]:
    for section in pe.sections:
        if section.Name.rstrip(b"\0") == name:
            return section.VirtualAddress, section.get_data()
    raise ValueError(f"missing {name.decode()} section")


def ascii_strings(section_rva: int, data: bytes) -> dict[str, list[int]]:
    found: dict[str, list[int]] = defaultdict(list)
    for match in re.finditer(rb"[ -~]{4,}\0", data):
        value = match.group()[:-1].decode("ascii")
        found[value].append(section_rva + match.start())
    return dict(found)


def decoder64() -> capstone.Cs:
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    decoder.detail = True
    return decoder


def exception_function_ranges(pe: pefile.PE) -> list[tuple[int, int]]:
    pe.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXCEPTION"]]
    )
    ranges = {
        (entry.struct.BeginAddress, entry.struct.EndAddress)
        for entry in pe.DIRECTORY_ENTRY_EXCEPTION
    }
    return sorted((start, end) for start, end in ranges if start < end)


def code_instructions(pe: pefile.PE):
    base = pe.OPTIONAL_HEADER.ImageBase
    for start_rva, end_rva in exception_function_ranges(pe):
        code = pe.get_data(start_rva, end_rva - start_rva)
        yield from decoder64().disasm(code, base + start_rva)


def instructions_in_range(pe: pefile.PE, start_rva: int, end_rva: int):
    base = pe.OPTIONAL_HEADER.ImageBase
    yield from decoder64().disasm(
        pe.get_data(start_rva, end_rva - start_rva), base + start_rva
    )


def text_decode_coverage(pe: pefile.PE) -> dict[str, int]:
    ranges = exception_function_ranges(pe)
    return {
        "exception_function_count": len(ranges),
        "covered_function_bytes": sum(end - start for start, end in ranges),
    }


def rip_xrefs(
    pe: pefile.PE, target_rvas: set[int], code_range: tuple[int, int]
) -> dict[int, list[int]]:
    base = pe.OPTIONAL_HEADER.ImageBase
    result: dict[int, list[int]] = defaultdict(list)
    for instruction in instructions_in_range(pe, *code_range):
        for operand in instruction.operands:
            if operand.type != capstone.x86.X86_OP_MEM:
                continue
            memory = operand.mem
            if memory.base != capstone.x86.X86_REG_RIP:
                continue
            target = instruction.address + instruction.size + memory.disp - base
            if target in target_rvas:
                result[target].append(instruction.address - base)
    return dict(result)


def rip_references_in_range(
    pe: pefile.PE, start_rva: int, end_rva: int, code_range: tuple[int, int]
) -> list[dict[str, str]]:
    """Report bounded code references into one containing .rdata page range."""
    base = pe.OPTIONAL_HEADER.ImageBase
    refs: list[dict[str, str]] = []
    for instruction in instructions_in_range(pe, *code_range):
        for operand in instruction.operands:
            if (
                operand.type != capstone.x86.X86_OP_MEM
                or operand.mem.base != capstone.x86.X86_REG_RIP
            ):
                continue
            target = instruction.address + instruction.size + operand.mem.disp - base
            if start_rva <= target < end_rva:
                refs.append(
                    {
                        "instruction_rva": f"0x{instruction.address - base:x}",
                        "target_rva": f"0x{target:x}",
                    }
                )
    return refs


def pointer_entries(
    pe: pefile.PE, target_rvas: set[int]
) -> dict[int, list[tuple[int, int]]]:
    """Find aligned pointer-table entries of the form {name_va, wrapper_va}."""
    base = pe.OPTIONAL_HEADER.ImageBase
    entries: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for section in pe.sections:
        data = section.get_data()
        for offset in range(0, max(0, len(data) - 15), 8):
            name_rva = int.from_bytes(data[offset : offset + 8], "little") - base
            if name_rva not in target_rvas:
                continue
            wrapper_rva = (
                int.from_bytes(data[offset + 8 : offset + 16], "little") - base
            )
            entries[name_rva].append((section.VirtualAddress + offset, wrapper_rva))
    return dict(entries)


def integer_occurrences(
    pe: pefile.PE, target_rvas: set[int]
) -> dict[int, dict[str, list[int]]]:
    """Locate raw RVA and VA encodings, including unaligned table formats."""
    base = pe.OPTIONAL_HEADER.ImageBase
    result: dict[int, dict[str, list[int]]] = {}
    for target in target_rvas:
        rva_hits: list[int] = []
        va_hits: list[int] = []
        for section in pe.sections:
            data = section.get_data()
            for needle, hits in (
                (struct.pack("<I", target), rva_hits),
                (struct.pack("<Q", base + target), va_hits),
            ):
                offset = data.find(needle)
                while offset != -1:
                    hits.append(section.VirtualAddress + offset)
                    offset = data.find(needle, offset + 1)
        result[target] = {"rva32": rva_hits, "va64": va_hits}
    return result


def relative32_entries(
    pe: pefile.PE, target_rvas: set[int]
) -> dict[int, list[dict[str, str]]]:
    """Find 32-bit self-relative fields resolving to a selected Lua-name string."""
    text_rva, text = section_bytes(pe, b".text")
    text_end = text_rva + len(text)
    result: dict[int, list[dict[str, str]]] = defaultdict(list)
    for section in pe.sections:
        data = section.get_data()
        for offset in range(0, max(0, len(data) - 7), 4):
            field_rva = section.VirtualAddress + offset
            name_rva = field_rva + struct.unpack_from("<i", data, offset)[0]
            if name_rva not in target_rvas:
                continue
            wrapper_field_rva = field_rva + 4
            wrapper_rva = (
                wrapper_field_rva + struct.unpack_from("<i", data, offset + 4)[0]
            )
            result[name_rva].append(
                {
                    "name_field_rva": f"0x{field_rva:x}",
                    "next_field_target_rva": f"0x{wrapper_rva:x}",
                    "next_field_targets_text": str(
                        text_rva <= wrapper_rva < text_end
                    ).lower(),
                }
            )
    return dict(result)


def surrounding_calls(
    pe: pefile.PE, xref_rvas: list[int], radius: int = 96
) -> dict[int, list[int]]:
    text_rva, text = section_bytes(pe, b".text")
    base = pe.OPTIONAL_HEADER.ImageBase
    decoder = decoder64()
    calls: dict[int, list[int]] = {}
    for xref in xref_rvas:
        start = max(text_rva, xref - radius)
        end = min(text_rva + len(text), xref + radius)
        code = text[start - text_rva : end - text_rva]
        targets = []
        for instruction in decoder.disasm(code, base + start):
            if instruction.mnemonic == "call" and instruction.op_str.startswith("0x"):
                targets.append(int(instruction.op_str, 16) - base)
        calls[xref] = sorted(set(targets))
    return calls


def nearby_text_rip_targets(
    pe: pefile.PE, xref_rvas: list[int], radius: int = 96
) -> list[int]:
    text_rva, text = section_bytes(pe, b".text")
    text_end = text_rva + len(text)
    base = pe.OPTIONAL_HEADER.ImageBase
    targets: set[int] = set()
    for xref in xref_rvas:
        start = max(REGISTRATION_BLOCK[0], xref - radius)
        end = min(REGISTRATION_BLOCK[1], xref + radius)
        for instruction in decoder64().disasm(
            pe.get_data(start, end - start), base + start
        ):
            for operand in instruction.operands:
                if (
                    operand.type != capstone.x86.X86_OP_MEM
                    or operand.mem.base != capstone.x86.X86_REG_RIP
                ):
                    continue
                target = (
                    instruction.address + instruction.size + operand.mem.disp - base
                )
                if text_rva <= target < text_end:
                    targets.add(target)
    return sorted(targets)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("editor", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    digest = sha256(args.editor)
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"unexpected editor.exe SHA-256: {digest}")

    pe = pefile.PE(str(args.editor), fast_load=True)
    rdata_rva, rdata = section_bytes(pe, b".rdata")
    strings = ascii_strings(rdata_rva, rdata)
    selected = {name: strings.get(name, []) for name in KNOWN_NAMES}
    targets = {rva for rvas in selected.values() for rva in rvas}
    direct_xrefs = rip_xrefs(pe, targets, REGISTRATION_BLOCK)
    entries = pointer_entries(pe, targets)
    entry_xrefs = rip_xrefs(
        pe,
        {entry_rva for group in entries.values() for entry_rva, _ in group},
        REGISTRATION_BLOCK,
    )
    encodings = integer_occurrences(pe, targets)
    relative_entries = relative32_entries(pe, targets)
    pool_start = max(rdata_rva, (min(targets) - 0x4000) & ~0xFFF)
    pool_end = min(rdata_rva + len(rdata), ((max(targets) + 0x4000) & ~0xFFF) + 0x1000)
    pool_references = rip_references_in_range(
        pe, pool_start, pool_end, REGISTRATION_BLOCK
    )
    coverage = text_decode_coverage(pe)
    string_by_rva = {rva: name for name, rvas in strings.items() for rva in rvas}
    block_names: dict[str, list[str]] = defaultdict(list)
    for reference in pool_references:
        target_rva = int(reference["target_rva"], 16)
        name = string_by_rva.get(target_rva)
        if name is not None:
            block_names[name].append(reference["instruction_rva"])

    registrations = []
    for name, rvas in selected.items():
        for string_rva in rvas:
            references = direct_xrefs.get(string_rva, [])
            pointer_table_entries = entries.get(string_rva, [])
            registrations.append(
                {
                    "lua_name": name,
                    "string_rva": f"0x{string_rva:x}",
                    "direct_string_rip_xref_rvas": [
                        f"0x{xref:x}" for xref in references
                    ],
                    "pointer_table_entries": [
                        {
                            "entry_rva": f"0x{entry_rva:x}",
                            "wrapper_rva": f"0x{wrapper_rva:x}",
                            "entry_rip_xref_rvas": [
                                f"0x{xref:x}" for xref in entry_xrefs.get(entry_rva, [])
                            ],
                        }
                        for entry_rva, wrapper_rva in pointer_table_entries
                    ],
                    "raw_integer_encoding_rvas": {
                        kind: [f"0x{rva:x}" for rva in rvas]
                        for kind, rvas in encodings[string_rva].items()
                    },
                    "self_relative_32_entries": relative_entries.get(string_rva, []),
                    "nearby_direct_call_target_rvas": {
                        f"0x{xref:x}": [f"0x{target:x}" for target in calls]
                        for xref, calls in surrounding_calls(pe, references).items()
                    },
                    "classification": (
                        "static-name-wrapper-pair"
                        if pointer_table_entries
                        else "self-relative-name-field"
                        if relative_entries.get(string_rva)
                        else "direct-string-reference"
                        if references
                        else "string-only"
                    ),
                    "expected_registration_xref_rvas": [
                        f"0x{xref:x}" for xref in EXPECTED_REGISTRATION_XREFS[name]
                    ],
                    "registration_xrefs_match": references
                    == list(EXPECTED_REGISTRATION_XREFS[name]),
                }
            )

    output = {
        "format": 1,
        "binary": {
            "name": args.editor.name,
            "sha256": digest,
            "image_base": f"0x{pe.OPTIONAL_HEADER.ImageBase:x}",
            "machine": f"0x{pe.FILE_HEADER.Machine:x}",
        },
        "method": {
            "strings": "NUL-terminated printable ASCII in .rdata",
            "xrefs": "x86-64 RIP-relative memory operands in the version-pinned registration or positive-control code block",
            "call_window_bytes": 96,
            "limitation": "A string xref plus nearby calls is evidence for a native registration path, not proof of a Lua state or table at runtime.",
        },
        "text_decode_coverage": coverage,
        "registration_block": {
            "start_rva": f"0x{REGISTRATION_BLOCK[0]:x}",
            "end_rva_exclusive": f"0x{REGISTRATION_BLOCK[1]:x}",
        },
        "registration_positive_control": "Each known Lua name must reproduce its independently mapped three-RIP-xref set in the bounded registration block.",
        "registration_name_references": [
            {
                "lua_name": name,
                "rip_xref_rvas": xrefs,
                "nearby_text_rip_target_rvas": [
                    f"0x{target:x}"
                    for target in nearby_text_rip_targets(
                        pe, [int(xref, 16) for xref in xrefs]
                    )
                ],
            }
            for name, xrefs in sorted(block_names.items())
        ],
        "known_name_registrations": registrations,
        "containing_name_pool_pages": {
            "start_rva": f"0x{pool_start:x}",
            "end_rva_exclusive": f"0x{pool_end:x}",
            "rip_reference_count": len(pool_references),
            "rip_references": pool_references[:32],
        },
        "save_name_matches": sorted(
            name
            for name in strings
            if "save" in name.lower() and "scene" in name.lower()
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
