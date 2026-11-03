"""Static, hash-pinned startup-token evidence for GIANTS Editor 10.0.14.

The script never starts the Editor.  It reads the pinned PE and reports only
derived string/token and control-flow metadata; raw disassembly stays local.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from capstone.x86 import X86_OP_MEM, X86_REG_RIP
from native_save import DEFAULT_BINARY, Image

PARSER_RVA = 0x14E1F0
TOKEN_REGION = (0x20E5300, 0x20E5700)
NOGUI_LITERAL_RVA = 0x20E55D8
LOGGING_SEPARATOR_RVA = 0x20D279F
NOGUI_FLAG_TEST_RVA = 0x15C99E
NOGUI_GATED_CALL_RVA = 0x15C9C9


def c_string(image: Image, rva: int) -> str:
    offset = image.pe.get_offset_from_rva(rva)
    return (
        image.data[offset : offset + 160].split(b"\0", 1)[0].decode("ascii", "replace")
    )


def rip_target(image: Image, instruction) -> int | None:
    for operand in instruction.operands:
        if operand.type == X86_OP_MEM and operand.mem.base == X86_REG_RIP:
            return (
                instruction.address + instruction.size + operand.mem.disp - image.base
            )
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    args = parser.parse_args()
    image = Image(args.binary)
    begin, end = image.function(PARSER_RVA)
    uses = []
    for instruction in image.instructions(begin, end):
        target = rip_target(image, instruction)
        if target is not None and TOKEN_REGION[0] <= target < TOKEN_REGION[1]:
            uses.append(
                {
                    "instruction_rva": hex(instruction.address - image.base),
                    "target_rva": hex(target),
                    "text": c_string(image, target),
                    "function_rva": [hex(begin), hex(end)],
                }
            )

    # This region owns the normal Editor's launch switches and nearby startup
    # literals.  Keep the explicit list to make negative results auditable.
    token_region = image.data[
        image.pe.get_offset_from_rva(TOKEN_REGION[0]) : image.pe.get_offset_from_rva(
            TOKEN_REGION[1]
        )
    ]
    tokens = []
    for chunk in token_region.split(b"\0"):
        if chunk.startswith(b"-") and all(32 <= byte < 127 for byte in chunk):
            tokens.append(chunk.decode("ascii"))
    nogui_locations = image.string_locations("nogui")
    separator_offset = image.pe.get_offset_from_rva(LOGGING_SEPARATOR_RVA)
    print(
        json.dumps(
            {
                "sha256": image.sha256,
                "parser_function_rva": [hex(begin), hex(end)],
                "token_region_rva": [hex(value) for value in TOKEN_REGION],
                "switch_literals": tokens,
                "token_region_uses_in_parser": uses,
                "nogui": {
                    "locations": nogui_locations,
                    "uses": image.refs(
                        [int(item["rva"], 16) for item in nogui_locations]
                    ),
                    "logging_value_separator": {
                        "rva": hex(LOGGING_SEPARATOR_RVA),
                        "byte": hex(image.data[separator_offset]),
                        "ascii": chr(image.data[separator_offset]),
                        "evidence": (
                            "The parser copies this low byte into a one-character separator string before splitting "
                            "the -logging value."
                        ),
                    },
                    "consumer": {
                        "flag_test_rva": hex(NOGUI_FLAG_TEST_RVA),
                        "gated_call_rva": hex(NOGUI_GATED_CALL_RVA),
                        "meaning": (
                            "The flag skips one log-sink setup call after the log object is constructed. "
                            "It does not gate application or window construction in this path."
                        ),
                    },
                },
                "negative_scope": (
                    "Only the token-literal region and RIP-relative references within the main startup parser are covered. "
                    "Absence is not proof that a dynamically constructed, config/XML, Lua, or another-module option is unavailable."
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
