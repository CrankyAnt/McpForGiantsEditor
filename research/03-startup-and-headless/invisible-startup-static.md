# Fully invisible startup: static feasibility

Date: 2026-10-17. Target: GIANTS Editor 10.0.14.0, executable SHA-256 `c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`.

## Question and scope

Can this installed build start fully invisibly while still creating the windows and render or update loop needed by the existing command bridge?

This is static research only. It read the pinned PE, the packaged `editor.xml`, and the existing local 10.0.14 configuration. It did not start an Editor or another GUI process, change a binary, change XML, or send a Windows message. Earlier `SW_HIDE` starts that timed out are failed observations, not proof of impossibility.

## Findings

### No established fully invisible startup path

The prior startup-parser result remains the only named startup-control result: `-logging nogui` skips a logging-sink setup call. It does not suppress application or window setup. See [startup-flags.md](startup-flags.md).

This pass found direct imported Win32 window operations, but it does not link a hidden call to the Editor main frame or render loop. Static evidence therefore does not establish a supported or working fully invisible startup. It provides specific locations for a debugger or an isolated-desktop probe.

### Direct Win32 import triage

The PE imports `GetStartupInfoW` at import-slot RVA `0x1c45770`; `CreateWindowExA` at `0x1c461c0`; `CreateWindowExW` at `0x1c461e0`; `IsIconic` at `0x1c46440`; `UpdateWindow` at `0x1c46600`; `IsWindowVisible` at `0x1c466a8`; `SetWindowPos` at `0x1c466c8`; and `ShowWindow` at `0x1c466e0`.

The read-only IAT scan verified each listed instruction by decoding the complete exception-directory function that contains its RVA. Function bounds come from the PE exception directory.

| API | Verified direct-call RVAs | Function-bound evidence | Interpretation |
| --- | --- | --- | --- |
| `GetStartupInfoW` | `0xc077de`, `0x11e0910`, `0x12200f8` | `0xc07710-0xc07853`, `0x11e08f4-0x11e092e`, `0x12200d8-0x12201c5` | The process reads Windows startup information. This scan cannot identify which call, if any, supplies the main-frame show state. |
| `CreateWindowExW` | `0xda94b1`, `0xe6f5f0`, `0xeecb89`, `0xef34a6`, `0xf638c5`, `0xfae243`, `0xfc704b`, `0xfd66fd`, `0x10253a2`, `0x1058fb9`, `0x1a7259a`, `0x1ab814a`, `0x1ab86eb`, `0x1ab8799`, `0x1ac1bd3`, `0x1ac2119` | Examples: `0xef3180-0xef39e5`, `0x1ab8680-0x1ab88a7`. | Window creation exists. This result does not name a created HWND as the Editor main frame. |
| `IsWindowVisible` | `0xe74f40`, `0xf4252a`, `0xfe1703`, `0xfe18e3`, `0x1a709be` | `0xe74b10-0xe75004`, `0xf42501-0xf42566`, `0xfe1670-0xfe19ae`, `0x1a70810-0x1a71dfb` | These are state checks. The scan does not show a branch that gates Editor initialization or rendering on visible state. |
| `IsIconic` | `0xef27ee`, `0xef3a27`, `0xef3b1d`, `0xef460b`, `0xef48a8`, `0xef64f5`, `0xef6584`, `0x1a717fe` | `0xef27d0-0xef292c`, `0xef3a10-0xef3a37`, `0xef3af0-0xef3b2e`, `0xef4600-0xef461b`, `0xef4860-0xef5110`, `0xef64b0-0xef6653`, `0x1a70810-0x1a71dfb` | The binary contains minimization-dependent behavior. It does not show that a never-visible window acts like a minimized window. |
| `ShowWindow` | 24 verified calls or jumps, including `0xe77a08`, `0xeece36`, `0xef3a90`, `0xef4813`, `0xef5c4a`, `0xef65d7`, `0xef693a`, `0xfc988c`, `0xfd6f6c`, `0xfdba78`, `0x1096432`, `0x1ab8837` | The local JSON receipt records every matching direct IAT use. | Several calls are outside the parser and main-application evidence already reconstructed, so their relation to Editor startup is unresolved. |

The scan found 27 `ShowWindow` byte candidates. It verified 24. The three excluded candidates are `0x1ab8dbe` and `0x1ab8e11`, which are outside exception-directory function bounds and may be thunks, plus `0x1ab9755`, which is not an instruction boundary after decoding its containing function. They are not treated as calls. All three `GetStartupInfoW` candidates are verified instruction boundaries.

At `0xef693a`, `0xfc988c`, and `0xfd6f6c`, the immediately preceding simple EDX assignment is `0`, which is `SW_HIDE` for `ShowWindow`. At `0xfdba78` it is `5` (`SW_SHOW`), at `0x1096432` it is `8` (`SW_SHOWNA`), and at `0x1ab8837` it is `7` (`SW_SHOWMINNOACTIVE`). These are verified local call-site observations. They do not prove that the HWND is the Editor frame or that the path runs at startup. A later `ShowWindow(SW_HIDE)` cannot rule out an earlier visible frame or other visible top-level windows.

`UpdateWindow` and `SetWindowPos` are also imported and directly called. Their presence gives no render-loop guarantee. Existing controlled results show that the bridge's `addUpdateListener` pauses while the Editor is minimized, while the native menu-command route remains usable. See [live-results.md](../02-lua-and-save/live-results.md).

### wxWidgets event names do not expose a main-frame gate

The image contains UTF-16 `wxIdleEvent` at RVA `0x1c50b98` and `wxShowEvent` at `0x1c95ee0`. Their data-pointer records are at `0x24c1060` and `0x24c29d8`. It also contains the ASCII `OnIdle` literal at `0x1c8f3b6`. The existing limited xref scanner found no direct RIP-relative code reference for these symbols. Their pointer records are compatible with framework metadata.

This proves only that wxWidgets event type information is present. It does not identify an Editor `OnShow` or `OnIdle` handler, nor show that one blocks scene load, startup Lua, rendering, or native command dispatch until visibility.

### The combined visibility and iconic checks are SDL window-procedure cases

The function at `0x1a70810-0x1a71dfb` is not an Editor startup, idle, render, or deferred-initialization function. Its first argument is an HWND. At `0x1a708b1` it uses that HWND and the UTF-16 property name `SDL_WindowData` to call `GetPropW`; the returned per-window `SDL_WindowData` object is held in `RSI`. It then dispatches the Windows message from `EDX` through local jump tables.

The `IsWindowVisible` call at `0x1a709be` belongs to the table case for message `0x0051` (`WM_INPUTLANGCHANGE`). `test eax,eax` at `0x1a709c4` branches to `0x1a70966` when the HWND is not visible. The visible path queries modifier-key state and cursor position, converts the cursor with `ScreenToClient`, and calls the local handlers at `0x1ab9d40`, `0x1a8f1c0`, `0x1a8f7d0`, `0x1a97280`, `0x1a6fd80`, `0x1ab9790`, `0x1ab5050`, and `0x1a8f960`. This is an SDL platform-message and input-state path. It is not evidence that Editor frame construction, rendering, or idle processing requires visibility.

The `IsIconic` call at `0x1a717fe` belongs to the table case for message `0x011a` (`WM_GESTURENOTIFY`). Before it, the code verifies SDL-window state. `test eax,eax` at `0x1a71804` branches to `0x1a71844` when the HWND is iconic. The non-iconic path reads and translates the cursor position, then calls `0x1a97280` and `0x1a975b0` before returning. This is a conditional gesture-notification path. It does not gate startup, window creation, the update loop, or rendering.

These two checks explain why their colocated function must not be used as a main-frame visibility gate. The function owns generic SDL Win32 message handling for an HWND, and the state branches only suppress selected input or gesture work.

### XML and alternate-binary checks yield no startup control

The packaged `editor.xml` has `window_layout` attributes `x`, `y`, `width`, `height`, and `perspective`. The inspected local 10.0.14 profile adds `maximized`. Neither has an explicit `hidden` or `minimized` attribute. This is evidence about these two configuration documents, not a complete XML-schema proof. The binary has an ASCII `maximized` literal at `0x20e7add`; the limited direct-xref scan did not link it to code.

Within the installed Editor package, no executable or file name matches `batchconverter`, `convert`, `render`, or `headless` other than normal Editor files. The pinned `editor.exe` has no null-terminated ASCII or UTF-16 literal for `batchconverter`, `renderheadless`, or `headless`. This does not rule out an undocumented external tool outside that package or a dynamically constructed option.

The PE imports `GetProcAddress` at `0x1c45c10`. It has no static import or null-terminated ASCII or UTF-16 literal for `SwitchDesktop`, `OpenDesktop`, or `CreateDesktop`. This is a bounded absence result only. `GetProcAddress` means dynamically resolved desktop APIs remain possible without those literal names, and the scan does not cover other loaded modules.

## Sources and reproducibility

- Primary source: the local hash-pinned `editor.exe` named above.
- Existing parser evidence: [startup-flags.md](startup-flags.md).
- Existing minimized-operation evidence: [live-results.md](../02-lua-and-save/live-results.md) and [fidelity-results.md](../05-asset-fidelity/fidelity-results.md).
- Read-only scanner: [invisible_startup_static.py](../07-instruments/invisible_startup_static.py). It imports the existing hash guard from `native_save.py`, starts no process, and scans only direct `FF 15` and `FF 25` references to selected import slots. It accepts a candidate only after complete decoding of its exception-directory function confirms the instruction boundary. Candidates outside those bounds remain unverified.

Run from the repository root with an external bytecode cache. Store raw JSON only in the ignored local evidence area:

```powershell
$env:PYTHONPYCACHEPREFIX = "$env:TEMP\repo-pycache"
python docs/research/skills/fs25-modding/giants-editor-mcp/instruments/invisible_startup_static.py `
  | Set-Content -NoNewline .docs/giants-editor-invisible/static-iat.json
```

## Uncertainties

The direct-IAT coverage excludes dynamic `GetProcAddress` calls, register-indirect calls, other loaded modules, and static wxWidgets functions. The scan does not trace data flow from process startup through the application object to the main frame. It does not test first paint, GPU context creation, event loop, startup Lua, or render completion.

The static `SW_HIDE` observations are insufficient for a feasibility verdict. They may apply to dialogs, child windows, or later UI actions. Existing hidden-start timeouts show an unresolved failure boundary, not an impossibility claim.

## Next safe test

The next test belongs on the separately isolated Windows desktop lane. It should not use a user's desktop or modify an asset. For this exact binary, it must prove all of the following in one disposable run:

1. The process reaches a durable startup-Lua marker after normal window and renderer initialization, while the first frame is never visible on the user desktop.
2. The probe records the created top-level HWND, `IsWindowVisible`, `IsIconic`, and process startup command before issuing a known non-mutating Lua action.
3. A native script command produces a fresh, decodable screenshot or another non-mutating render receipt, then exits cleanly.

Instrumentation should trace the `GetStartupInfoW` sites and the main-frame `CreateWindowExW` and `ShowWindow` call once its HWND is known. Only that trace can link a requested `SW_HIDE` or startup-info show state to the frame and show whether wxWidgets needs first-show processing for the script or render loop.

## Runtime follow-up

The later [private-desktop runtime trials](invisible-startup-results.md) passed invisible startup, native Save, fresh-load readback and rendering for the pinned build. This finding uses normal GUI initialization on an inactive Win32 desktop. It does not establish a hidden-window startup switch or true windowless execution.

## Archive context

The original raw inputs were discarded; historical `.docs/` paths are no longer available. See [evidence availability](../../README.md#evidence-and-applicability) for the retained results and limits. Historical commands require new prepared data and reviewed paths; see the [instrument index](../07-instruments/README.md).
