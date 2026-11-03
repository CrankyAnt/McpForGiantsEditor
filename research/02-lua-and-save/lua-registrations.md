# Lua registration trace, GIANTS Editor 10.0.14

## Question and scope

Can static analysis of `editor.exe` reconstruct the native Lua C-function
registration tables and identify a full-scene save operation under a different
Lua name? This note covers only the executable named below. It does not start
the editor, inject code, or inspect the native Save-menu handlers.

## Findings

The scanner verified the supplied binary pin before every analysis run:
`editor.exe`, SHA-256
`c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`,
AMD64 image base `0x140000000`. The derived record is
[`lua-registrations.metadata.json`](lua-registrations.metadata.json).

`getSceneFilename`, `addUpdateListener`, and `editorExit` occur as printable,
NUL-terminated strings at RVAs `0x2127168`, `0x2127110`, and `0x21272b0`.
The static registration block at `0x1b4f58..0x1b8178` has three RIP-relative
references to each name. The scanner reproduces all nine references:

| Lua name | Registration xrefs | Nearby native target candidate |
| --- | --- | --- |
| `addUpdateListener` | `0x1b5362`, `0x1b5372`, `0x1b539d` | `0x1b9450` |
| `getSceneFilename` | `0x1b5552`, `0x1b5562`, `0x1b558d` | `0x1b9a70`, `0x1b9b90` |
| `editorExit` | `0x1b5c96`, `0x1b5ca6`, `0x1b5cd1` | `0x1ba9b0` |

This is registration evidence rather than string presence alone. The scanner
derives the nearby native targets from the same local instruction windows. It
does not prove a function boundary or select between adjacent candidates. The
runtime `_G` survey independently confirms that these names become callable.

A separate bounded runtime inventory corroborates the registration context. It
found 2,054 global keys, 131 global tables, and no userdata global. It
enumerated one level of table functions with `next`, without storing values.
The global inventory includes many generic save and export functions such as
`saveXMLFile`. No global name was a full-scene save candidate, and no non-`_G`
table method matched `save`, `export`, or `command`. Global method collection
was capped at 512, although all 2,054 global key/type pairs were captured.
This is an inventory limit, not proof that a save operation is unreachable
through deeper tables, metatables, or a non-Lua UI route.

The supplied public manifest has 1,064 function names and 198 colon methods.
This scanner did not find a `save*scene*` Lua-name literal. Its only matching
printable string is the UI message `Please save your scene to a file first.`
That does not prove there is no full-scene save API. It only shows that the
examined static name pool does not provide a name for one.

The registration block has 180 RIP-relative references into the containing
name-pool neighborhood `0x2123000..0x212c000`. It resolves 86 printable names.
Forty-six have a nearby `.text` target and form the current Editor-native
registration candidates. The other 40 are rendering-mode strings or another
non-wrapper use in the same block. `excludeFromSave` is the sole candidate
whose name contains `save`; it is not a full-scene save name.

## Sources and reproducibility

[`instruments/lua_registrations.py`](../07-instruments/lua_registrations.py) uses
the installed `pefile` and `capstone` packages. It accepts one editor path, rejects a
different SHA-256, and writes bounded JSON with RVAs and classifications only.
It never writes executable bytes or disassembly into tracked files.

Run from the worktree root with the configured Python interpreter:

```powershell
$env:PYTHONPYCACHEPREFIX = "$env:TEMP\repo-pycache"
python `
  docs\research\skills\fs25-modding\giants-editor-mcp\instruments\lua_registrations.py `
  'C:\Program Files\GIANTS Software\GIANTS_Editor_10.0.14\editor.exe' `
  --output docs\research\skills\fs25-modding\giants-editor-mcp\lua-registrations.metadata.json
```

The script reports direct references in a bounded registration block and
checks an independently mapped nine-xref positive control.

## Uncertainties

The binary has no symbols. The wrapper ranges identify native code associated
with the registrations, but this scan does not recover function signatures or
every registration in the block. No dynamic application checks were in scope.

## Next steps

The current parser enumerates 46 nearby-target candidates in the bounded block. Further reconstruction can cover other blocks if a concrete missing operation requires it. The minimized native-script and Save route now supplies a tested alternative; see [live-results.md](live-results.md).

## Archive context

The original raw inputs were discarded; historical `.docs/` paths are no longer available. See [evidence availability](../../README.md#evidence-and-applicability) for the retained results and limits. Historical commands require new prepared data and reviewed paths; see the [instrument index](../07-instruments/README.md).
