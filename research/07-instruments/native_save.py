"""Read-only, version-pinned PE cross-reference inspection for the Editor probe.

No target process is started. Disassembly belongs in ignored local evidence only.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import re
import struct
from pathlib import Path

import capstone
import pefile
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

EXPECTED_SHA256 = "c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d"
DEFAULT_BINARY = Path(
    r"C:\Program Files\GIANTS Software\GIANTS_Editor_10.0.14\editor.exe"
)


class Image:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        self.sha256 = hashlib.sha256(self.data).hexdigest()
        if self.sha256 != EXPECTED_SHA256:
            raise ValueError(
                "Binary hash differs from the inspected build; review before using offsets"
            )
        self.pe = pefile.PE(data=self.data, fast_load=True)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.cs.detail = True
        pdata = self.section(".pdata")
        pdata_size = self.pe.OPTIONAL_HEADER.DATA_DIRECTORY[3].Size
        entries = struct.iter_unpack(
            "<III",
            self.data[pdata.PointerToRawData : pdata.PointerToRawData + pdata_size],
        )
        self.functions = sorted(
            (begin, end) for begin, end, unwind in entries if begin and end > begin
        )
        self.starts = [entry[0] for entry in self.functions]
        self.pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
        )
        self.imports = {
            imp.address: entry.dll.decode()
            + "!"
            + (imp.name.decode() if imp.name else str(imp.ordinal))
            for entry in self.pe.DIRECTORY_ENTRY_IMPORT
            for imp in entry.imports
        }

    def section(self, name):
        return next(
            s for s in self.pe.sections if s.Name.rstrip(b"\0").decode() == name
        )

    def function(self, rva):
        i = bisect.bisect_right(self.starts, rva) - 1
        return (
            self.functions[i]
            if i >= 0 and self.functions[i][0] <= rva < self.functions[i][1]
            else None
        )

    def instructions(self, start, end):
        raw = self.pe.get_offset_from_rva(start)
        return self.cs.disasm(self.data[raw : raw + end - start], self.base + start)

    def string_locations(self, text):
        result = []
        for encoding in ("ascii", "utf-16le"):
            needle = text.encode(encoding) + (b"\0" if encoding == "ascii" else b"\0\0")
            offset = self.data.find(needle)
            while offset >= 0:
                result.append(
                    {
                        "offset": hex(offset),
                        "rva": hex(self.pe.get_rva_from_offset(offset)),
                        "encoding": encoding,
                    }
                )
                offset = self.data.find(needle, offset + 1)
        return result

    def refs(self, target_rvas):
        targets = set(target_rvas)
        code = self.section(".text")
        raw = self.data[
            code.PointerToRawData : code.PointerToRawData + code.SizeOfRawData
        ]
        code_refs = []
        pattern = rb"[\x48-\x4f][\x8d\x8b\x89][\x05\x0d\x15\x1d\x25\x2d\x35\x3d]...."
        for match in re.finditer(pattern, raw, re.DOTALL):
            rva = code.VirtualAddress + match.start()
            destination = rva + 7 + struct.unpack_from("<i", match.group(), 3)[0]
            if destination not in targets:
                continue
            ins = next(self.instructions(rva, rva + 15), None)
            if ins and any(
                o.type == X86_OP_MEM
                and o.mem.base == X86_REG_RIP
                and ins.address + ins.size + o.mem.disp - self.base in targets
                for o in ins.operands
            ):
                bounds = self.function(rva)
                code_refs.append(
                    {
                        "rva": hex(rva),
                        "target": hex(destination),
                        "instruction": ins.mnemonic + " " + ins.op_str,
                        "function": [hex(v) for v in bounds] if bounds else None,
                    }
                )
        pointers = []
        for target in targets:
            needle = struct.pack("<Q", self.base + target)
            offset = self.data.find(needle)
            while offset >= 0:
                pointers.append(
                    {
                        "rva": hex(self.pe.get_rva_from_offset(offset)),
                        "target": hex(target),
                    }
                )
                offset = self.data.find(needle, offset + 1)
        return {
            "code": code_refs,
            "pointers": pointers,
            "coverage": "REX-prefixed RIP-relative LEA/MOV and absolute 64-bit data pointers; not all possible x86 references",
        }

    def immediate_refs(self, value):
        needle = struct.pack("<I", value)
        text = self.section(".text")
        data = text.get_data()
        candidates = set()
        start = 0
        while (offset := data.find(needle, start)) >= 0:
            bounds = self.function(text.VirtualAddress + offset)
            if bounds:
                candidates.add(bounds)
            start = offset + 1
        results = []
        for begin, end in sorted(candidates):
            instructions = list(self.instructions(begin, end))
            for index, ins in enumerate(instructions):
                if any(
                    op.type == X86_OP_IMM and op.imm == value for op in ins.operands
                ):
                    results.append(
                        {
                            "rva": hex(ins.address - self.base),
                            "function": [hex(begin), hex(end)],
                            "context": [
                                self.describe_instruction(i)
                                for i in instructions[max(0, index - 3) : index + 4]
                            ],
                        }
                    )
        return results

    def describe_instruction(self, ins):
        annotation = []
        for operand in ins.operands:
            if operand.type == X86_OP_MEM and operand.mem.base == X86_REG_RIP:
                dest = ins.address + ins.size + operand.mem.disp
                if dest in self.imports:
                    annotation.append(self.imports[dest])
            if ins.mnemonic in ("call", "jmp") and operand.type == X86_OP_IMM:
                annotation.append("target_rva=" + hex(operand.imm - self.base))
        return f"{ins.address - self.base:08x}  {ins.mnemonic:8} {ins.op_str}" + (
            " ; " + ", ".join(annotation) if annotation else ""
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--text", action="append", default=[])
    parser.add_argument("--rva", type=lambda x: int(x, 0))
    parser.add_argument("--function", action="store_true")
    parser.add_argument("--bytes", type=lambda x: int(x, 0), default=256)
    parser.add_argument("--refs", action="store_true")
    parser.add_argument("--immediate", type=lambda x: int(x, 0))
    args = parser.parse_args()
    image = Image(args.binary)
    if args.immediate is not None:
        print(json.dumps(image.immediate_refs(args.immediate), indent=2))
    elif args.text:
        findings = {}
        for text in args.text:
            locations = image.string_locations(text)
            findings[text] = {
                "locations": locations,
                "refs": image.refs([int(x["rva"], 16) for x in locations]),
            }
        print(
            json.dumps(
                {
                    "sha256": image.sha256,
                    "image_base": hex(image.base),
                    "findings": findings,
                },
                indent=2,
            )
        )
    elif args.rva is not None:
        if args.refs:
            print(json.dumps(image.refs([args.rva]), indent=2))
        else:
            bounds = image.function(args.rva) if args.function else None
            start, end = bounds or (args.rva, args.rva + args.bytes)
            print("range", hex(start), hex(end))
            for ins in image.instructions(start, end):
                print(image.describe_instruction(ins))
    else:
        print(
            json.dumps(
                {
                    "sha256": image.sha256,
                    "image_base": hex(image.base),
                    "runtime_functions": len(image.functions),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
