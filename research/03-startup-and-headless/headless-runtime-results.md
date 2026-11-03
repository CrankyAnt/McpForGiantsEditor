# Headless runtime investigation

Date: 2026-10-17. Target: GIANTS Editor 10.0.14.0, executable SHA256 `c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`.

## Conclusion

No working headless Editor mode was found in the installed build. This phase tested the actual startup candidates and every enum in the discovered renderer table, including direct in-process NULL overrides. All 16 runs that reached Lua had created GUI windows. The other 16 stopped or timed out before the Lua receipt. No run met the headless acceptance condition.

The strongest negative finding is specific. The Editor canvas factory accepts Vulkan through its normal construction branch. Its seven other enum values, including NULL and NULL_TRACKING, reach an unsupported-canvas branch and terminate before Lua. This is stronger evidence than absent documentation or ignored command-line flags. It establishes the behavior of that factory in this exact build, not the impossibility of writing a different startup program or changing proprietary implementation.

The previously proven private Win32 desktop remains a separate GUI automation route. This phase did not substitute that result for a headless success.

## Acceptance and isolation

The headless requirement was to load a scene and execute Lua without an Editor GUI or viewport. Successful scene persistence would then be required before calling it a usable headless editing route. Internal message-only windows were distinguished from the Editor UI rather than treating every helper HWND as a visible application window.

Each runtime trial used a fresh private Win32 desktop, a copied one-node I3D, its own config and Lua file, the pinned executable, a suspended process and an owned kill-on-close job. Frida 17.24.0 attached before the primary thread resumed. Hooks recorded `CreateWindowExA/W`, native `NtUserCreateWindowEx`, show operations and selected internal startup functions. No desktop switch, input injection or visible fallback occurred. Instrumented memory changes existed only in the owned child process. The installed binary was not patched.

The Lua probe was immediate `-runScriptCode`, not an idle callback. It wrote a typed receipt containing the current scene, root and child count, then exited. All 16 successful receipts match their exact fixture scene and have root greater than zero and child count two. Their file timestamps follow the recorded suspended-process sample before `ResumeThread`. This supplied a recorded freshness check as well as the live controller's check during the trial.

No headless candidate reached that first Lua gate. A headless Save test therefore could not proceed. Save after ordinary GUI initialization was already established by the preceding phases.

## Tested methods

There were 32 process starts, including controls, repeats and backend confirmations. The complete per-case data is in [derived metadata](headless-runtime-results.metadata.json).

| Method | Runtime result | What it establishes |
| --- | --- | --- |
| Normal startup controls | Lua completed, with GUI windows and Vulkan | The fixture and instrumentation work. |
| `-headless`, `-nogui`, `-batch` | Lua completed through the normal GUI route | These exact tokens did not enable headless operation. Static parser inspection found no handlers for them. |
| `-logging nogui` | Lua completed with GUI windows | The traced log-sink flag does not bypass the GUI. |
| XML renderer `NULL`, `NULL_TRACKING`, `D3D_12` | Snapshot-backed repeats constructed enum 5 and used Vulkan | These XML values did not select the internal backend. Pre-run config snapshots were checked during the trial; their recorded hash evidence remains in the derived metadata, while the raw snapshots were discarded. |
| Speculative XML `None` and `Headless` | Lua completed through GUI startup | No headless behavior was observed. These preliminary cases lack a retained input-config snapshot and do not independently prove the submitted token. |
| `STARTF_USESHOWWINDOW` with `SW_HIDE` | No Lua receipt within 20 seconds | This startup-show variant failed under the tested bound; it does not prove a general hidden-window impossibility. |
| Force hidden styles, `ShowWindow` and `SetWindowPos` | No Lua receipt within 20 seconds | Broad show suppression failed. It changes many windows and does not isolate a main-frame dependency. |
| Deny every `NtUserCreateWindowEx` | OLE initialization failed before Lua | Total HWND denial breaks early toolkit infrastructure. This alone says nothing about whether an Editor frame could be removed. |
| Deny only the observed top-level `wxWindowNR` startup window | One `Starting...` window creation was refused; the process exited with access violation before Lua | Allowing OLE helpers was insufficient. This identifies a startup-window dependency in this run, not necessarily the final main frame. |
| Force the real internal renderer enum | Vulkan reached Lua; all seven other values exited with code 1 before Lua | The NULL names are present in the common enum table but do not provide working Editor canvases in this build. |

## Internal backend test

The [static trace](headless-startup-trace.md) found the application configuration pointer at application offset `0x690`, and the renderer enum at configuration offset `0x2b0`. Configuration constructor RVA `0x1d8670` initializes the enum to 5. Canvas factory RVA `0x304330` consumes it. The factory branches on enum 5 at `0x304454`; every other value takes the branch at `0x304c21`.

The runtime hook changed the configuration enum after its constructor returned. A second hook independently recorded the value entering the factory. The final eight cases cover every entry in the table. These are internal memory overrides, not XML configuration tests.

| Enum | Name | Factory input verified | Result |
| ---: | --- | --- | --- |
| 0 | Direct 3D 12 | 0 | Canvas failure, exit 1, no Lua |
| 1 | GNM | 1 | Canvas failure, exit 1, no Lua |
| 2 | PS5 | 2 | Canvas failure, exit 1, no Lua |
| 3 | NVN | 3 | Canvas failure, exit 1, no Lua |
| 4 | Metal | 4 | Canvas failure, exit 1, no Lua |
| 5 | Vulkan | 5 | Lua completed, exit 0, 1,305 successful `CreateWindowEx` events |
| 6 | NULL | 6 | Canvas failure, exit 1, no Lua |
| 7 | NULL_TRACKING | 7 | Canvas failure, exit 1, no Lua |

Every rejected backend had already created eight User32 windows, including the `Starting...` startup window. The same instrumented process wrote `Unable to create canvas for` followed by its actual backend name. The filtered `WriteFile` hook correlates that diagnostic directly to the child; it does not rely on a potentially stale shared Editor log. No Frida script errors occurred in the 32 trials.

## Companion tools and engine-hosting routes

The [alternative-route investigation](headless-alternative-routes.md) inspected the installed binaries and the current FS25 TestRunner 0.9.22 archive. Its actual EditorCheck code starts the normal Editor with `-runScriptCode`, a Vulkan configuration and no headless switch. Its Lua check loads I3D files and calls `renderScreenshot`. It provides batch orchestration, not a different headless engine startup. The archive was inspected without running the validator.

The installed textureTool has a console/batch interface for texture conversion. It is not an I3D scene editor or Lua host. No public engine-hosting API was identified in the installed DLLs, Editor or game exports. A game dedicated-server launch is a separate runtime and supplies no established Editor scene-save contract. These tools do not supply the missing headless editing route.

`setIs3DGraphicsRenderingEnabled` exists after normal engine initialization. Disabling drawing at that stage would not undo startup windows or canvas construction. It is not a bootstrap solution.

## Evidence limits

This investigation covers the reconstructed startup parser, installed configuration paths, the entire discovered eight-value canvas-backend table, window suppression/denial and relevant installed or official companion tools. It does not exhaust arbitrary process patches, manual mapping of private engine code, a replacement application entry point, or future GIANTS releases. Those would be new implementations, not an existing headless mode found by this research.

The negative conclusion is therefore bounded: no usable headless route was established for this installed Editor, and the tested internal backend alternatives are explicitly rejected by its canvas factory. The evidence does not justify a universal claim that GIANTS engine code can never run headless.

## Cleanup, validation and delivery

All 32 trials recorded `Default` as the input desktop, no owned Editor window there, and another process as foreground in their state samples. Sampling cannot exclude events between samples. Each private desktop handle was closed and a post-close `OpenDesktopW` failed with error 2. A final independent process check found zero `editor.exe` processes. The normal Editor configuration still has SHA256 `31720002d6f6639a6d340ff4d7bb4e558f5ccd1001209c169d1f79f3345871cf`.

The [launcher](../07-instruments/headless_runtime_probe.py), [hooks](../07-instruments/headless_runtime_hooks.js) and [analyzer](../07-instruments/analyze_headless_runtime.py) are research instruments. Raw configs, assets, logs and traces were originally stored under `.docs/giants-editor-headless/` and have since been discarded. The temporary Frida installation and downloaded TestRunner archive/extraction were removed after analysis. Derived runtime results remain in this archive; the raw directory is no longer retained and no vendor implementation is committed.

The original phase produced research artifacts only; no MCP service, skill or runtime installation was produced.

Python compilation, Ruff lint and format checks, JavaScript syntax checking and repository validation passed. Guard controls refused both an invalid case path and existing runtime output before Win32 access. Independent review verified the backend enum inputs, same-process diagnostics, receipt freshness and scoped negative conclusions.

The historical regeneration command was the following. Its original raw inputs no longer exist; new prepared data and reviewed paths are required for a new run:

```powershell
$env:PYTHONPYCACHEPREFIX = "$env:TEMP\repo-pycache"
python docs/research/skills/fs25-modding/giants-editor-mcp/instruments/analyze_headless_runtime.py --output docs/research/skills/fs25-modding/giants-editor-mcp/headless-runtime-results.metadata.json --verify-system
```

New runtime trials require a new prepared directory under `.docs/giants-editor-headless/runtime`, with `spec.json`, a copied `scene.i3d`, a dedicated `editor.xml` and `probe.lua`. Existing receipts are deliberately refused. Input snapshots established the exact submitted configuration during the later trials; those raw snapshots are no longer retained. The launcher pins the build and script hashes. Frida 17.24.0 was installed only into `C:\TMP\giants-headless-tooling`; reproducing the runtime instrumentation requires that temporary dependency again. The read-only analyzer does not require Frida.

## Archive context

The original raw inputs were discarded; historical `.docs/` paths are no longer available. See [evidence availability](../../README.md#evidence-and-applicability) for the retained results and limits. Historical commands require new prepared data and reviewed paths; see the [instrument index](../07-instruments/README.md).
