# Static startup and headless controls: GIANTS Editor 10.0.14

## Question and scope

This note traces startup-related command-line literals and their code references in
`C:\Program Files\GIANTS Software\GIANTS_Editor_10.0.14\editor.exe` only. The
examined SHA-256 is
`c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`.

No Editor process or UI was started. Raw disassembly is deliberately kept only in
the ignored local evidence area.

## Findings

### `nogui` is a logging-sink switch, not a headless launch mode

The binary accepts this command-line form:

```text
-logging nogui
```

This is a fact from the code path, rather than an inference from a printable
string:

1. The main startup parser is at RVA `0x14e1f0`–`0x150c2d`.
2. It searches the argument vector for `-logging` at RVA `0x150590` and, when
   present, consumes the following argument.
3. That argument is split and each resulting item is compared with `nofile` and
   `nogui`; the latter comparison is at RVA `0x150684`.
4. A `nogui` match sets bit `0x2` in the constructor flags passed at RVA
   `0x1507fa` to the application object (`0x15c440`).
5. That constructor tests bit `0x2` at RVA `0x15c99e`. When set, it skips only
   the log-sink setup call at RVA `0x15c9c9`, after it has already constructed
   the surrounding logging object.

The constructor performs application and window-related setup before this flag
test. The static evidence therefore supports only this statement: `-logging
nogui` disables one GUI-associated log sink. It does not make the Editor
headless, hide its main UI, or establish that it continues updating without a
visible window.

The binary contains no `-nogui` or `-noGUI` token. `nogui` occurs once, as a
lowercase value literal at RVA `0x20e55d8`, and its only code reference is the
comparison described above. Therefore `-nogui` should not be offered as a
supported invocation.

`nofile` is handled beside it at RVA `0x15067d` and sets a separate `0x1` bit.
The splitting helper receives a one-character separator whose actual low byte
is `0x38` (`8`) at RVA `0x20d279f`. This is not a pointer-reading mistake: the
caller copies that byte into a one-character string before invoking the helper.
The single value `nogui` requires no split and remains code-supported. The odd
separator does not document a useful composite syntax, so do not rely on one
without a controlled runtime probe.

### Other startup switches with parser references

The main parser has code references for these switch literals:

| Switch | Evidence / observed parser behavior |
| --- | --- |
| `-configXML <path>` | parser lookup at `0x14e740`/`0x14e770`; the immediately following argument is used as a config-file path, with an explicit open-failure diagnostic at `0x14e88b`. |
| `-globalTime` | parser lookup at `0x14e690`. |
| `-disableLuaErrorReporting` | parser lookup at `0x14e6e0`. |
| `-onlyLoadRuntimeReferences` | parser lookup at `0x14e8b0`. |
| `-disableTextureStreaming` | parser lookup at `0x14e8f0`. |
| `-noVersionSelection` | parser lookup at `0x14f3a0` and `0x14f50c`. |
| `-codeSvnDir <path>` | parser lookup at `0x1503e0`, then consumes a following path. |
| `-supressChangelog` | parser lookup at `0x150550`. The binary's spelling is `supress`, with one `p`. |
| `-runScriptCode <code>` | parser lookup at `0x1500f0`/`0x150120`, then consumes the following argument. |
| `-logging <value>` | parser lookup at `0x150590`; its value is where `nogui` is interpreted. |

The source string `-configXML` starts at `0x20e5340`; the `-logging` string is
at `0x20e5610`. These are offsets for this exact hash only.

### Startup scene argument versus `-runScriptCode`

The parser recognizes an `.i3d` positional input case-insensitively at
`0x14f098`–`0x14f0fa`. This selection occurs before the later independent scan
for `-runScriptCode` at `0x1500f0`–`0x1502af`.

That establishes **argument-collection order** only: the scene candidate is
selected first, then the script-code argument is collected. Both values are
passed into the later application construction path at `0x1507fa`; this static
slice does not prove whether the constructed application's frame/update loop
opens the scene before it evaluates the supplied code. Do not represent either
of these command lines as proven to run script code after document load:

```text
editor.exe scene.i3d -runScriptCode "..."
editor.exe -runScriptCode "..." scene.i3d
```

Their argument order is not a supported execution-order control in the code
examined here. A runtime probe that observes both a document-open callback and
script execution is still needed to resolve this.

## Negative coverage

The following strings are absent from the hash-pinned binary as standalone
startup literals: `headless`, `-nogui`, and `-noGUI`. There is no evidence here
for a `-batch`, `-save`, `-quit`, or frame-pumping command-line switch. Since
`nogui` only gates a log sink, this research found no headless or UI-suppression
mode in the examined startup path.

This is a bounded negative result. The scanner covers the startup parser,
its token-literal region (`0x20e5300`–`0x20e5700`), and RIP-relative references
within that parser. It cannot rule out dynamically constructed options,
configuration/XML behaviour, Lua-registered behaviours, or controls in other
loaded modules. Native Save (`ID 6001`) and Lua registration are outside this
research lane.

## Sources and reproducibility

- Primary source: the local hash-pinned Editor PE named above.
- Reproducible inspector: `instruments/startup_flags.py`. It imports the
  existing read-only `native_save.Image` hash guard, starts no process, and
  emits only derived literal and control-flow metadata.

Run from this directory with:

```powershell
$env:PYTHONPYCACHEPREFIX = "$env:TEMP\repo-pycache"
python instruments\startup_flags.py
```

## Remaining gaps

- The branch proves a skipped logging sink, but static analysis does not name
  that sink's user-visible output. A controlled logging-only probe could do so.
- The order between actual initial-document load and `-runScriptCode` evaluation
  needs a controlled runtime trace.
- The exact accepted grammar for combined `-logging` values needs a runtime
  probe; only the single-item `nogui` form is code-supported by this result.

## Runtime follow-up

A later controlled invocation loaded the named fixture and reached the startup script. A fresh process read the node directly from the loaded document and exited successfully. This confirms that invocation for this build, without making argument order a general execution-order contract. See [live-results.md](../02-lua-and-save/live-results.md). No logging-only runtime experiment was performed.

## Invisible startup follow-up

The later [private-desktop runtime trials](invisible-startup-results.md) passed invisible startup, native Save, fresh-load readback and rendering for the pinned build. This finding uses normal GUI initialization on an inactive Win32 desktop. It does not establish a hidden-window startup switch or true windowless execution.

## Archive context

This report records the 2026-10-16/17 research against the pinned Editor build. Raw assets, screenshots, configurations and machine logs referenced under `.docs/` are local-only and are not distributed. Reproduction commands retain their historical workspace assumptions; read the [instrument index](../07-instruments/README.md) before adapting or running them.
