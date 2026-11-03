"""Read-only IAT-call triage for GIANTS Editor invisible-startup research.

The script uses the existing hash-pinned ``native_save.Image`` loader. It does
not start or modify the Editor. It finds direct x64 IAT calls and jumps to a
small, fixed Win32 API set and records only derived instruction metadata.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from native_save import DEFAULT_BINARY, Image

API_NAMES = {
    "GetStartupInfoW",
    "CreateWindowExA",
    "CreateWindowExW",
    "IsIconic",
    "IsWindowVisible",
    "ShowWindow",
    "SetWindowPos",
    "UpdateWindow",
}


def show_command_hint(image: Image, call_rva: int) -> dict[str, str] | None:
    """Return the last simple EDX assignment before a ShowWindow call.

    Windows x64 passes ShowWindow's second parameter in EDX. This is a local
    hint only. A branch or register copy can make the value path-dependent.
    """
    bounds = image.function(call_rva)
    if bounds is None:
        return None
    instructions = list(image.instructions(bounds[0], call_rva))
    for instruction in reversed(instructions[-16:]):
        operands = instruction.op_str.replace(" ", "")
        if instruction.mnemonic == "xor" and operands == "edx,edx":
            return {
                "instruction_rva": hex(instruction.address - image.base),
                "value": "0",
            }
        if instruction.mnemonic == "mov" and operands.startswith("edx,"):
            return {
                "instruction_rva": hex(instruction.address - image.base),
                "value": operands.split(",", 1)[1],
            }
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    args = parser.parse_args()
    image = Image(args.binary)
    text = image.section(".text")
    raw = image.data[text.PointerToRawData : text.PointerToRawData + text.SizeOfRawData]
    calls = []
    function_instructions = {}
    for offset in range(len(raw) - 6):
        opcode = raw[offset : offset + 2]
        if opcode not in (b"\xff\x15", b"\xff\x25"):
            continue
        rva = text.VirtualAddress + offset
        target = rva + 6 + struct.unpack_from("<i", raw, offset + 2)[0]
        imported = image.imports.get(image.base + target)
        if not imported or imported.rsplit("!", 1)[-1] not in API_NAMES:
            continue
        bounds = image.function(rva)
        if bounds is None:
            instruction = None
            alignment = "unverified_no_pdata_function"
        else:
            if bounds not in function_instructions:
                function_instructions[bounds] = {
                    item.address - image.base: item
                    for item in image.instructions(bounds[0], bounds[1])
                }
            instruction = function_instructions[bounds].get(rva)
            alignment = (
                "verified_pdata_function"
                if instruction is not None
                else "misaligned_pdata_candidate"
            )
        finding = {
            "instruction_rva": hex(rva),
            "kind": "call" if opcode == b"\xff\x15" else "jump",
            "import_slot_rva": hex(target),
            "import": imported,
            "function_rva": [hex(value) for value in bounds] if bounds else None,
            "instruction_boundary": alignment,
            "instruction": (
                instruction.mnemonic + " " + instruction.op_str
                if instruction is not None
                else None
            ),
        }
        if imported.endswith("!ShowWindow") and instruction is not None:
            finding["ncmdshow_hint"] = show_command_hint(image, rva)
        calls.append(finding)
    imports = {
        hex(address - image.base): value
        for address, value in image.imports.items()
        if value.rsplit("!", 1)[-1] in API_NAMES
    }
    print(
        json.dumps(
            {
                "sha256": image.sha256,
                "imports": imports,
                "direct_iat_calls_or_jumps": calls,
                "coverage": (
                    "Direct x64 FF 15/FF 25 RIP-relative calls or jumps from .text to the selected "
                    "static import slots. Candidates are verified only when their RVA is an instruction boundary "
                    "after decoding the complete exception-directory function. Candidates outside .pdata remain "
                    "unverified thunks. Dynamic GetProcAddress calls, register-indirect calls, other modules, and "
                    "non-Win32 toolkit paths are outside this triage."
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
