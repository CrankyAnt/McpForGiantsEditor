# Runtime results, 2026-10-16

The installed Editor can execute a Lua request and save its I3D while minimized, without mouse or keyboard input. This establishes a usable Windows background-control route for an MCP bridge. It does not establish headless startup or a supported vendor automation API.

The target is Editor 10.0.14.0 with the binary hash pinned in [README.md](README.md). The user released the computer for these visible startup experiments. All experiments used disposable documents and dedicated configuration files. Every Editor process used by the experiment has exited. The normal user configuration retained its pre-test SHA256 `31720002d6f6639a6d340ff4d7bb4e558f5ccd1001209c169d1f79f3345871cf`.

## Observations

| Experiment | Result and independent confirmation |
| --- | --- |
| Native Save in a normal window | Main menu exposed Save ID 6001. A bounded `WM_COMMAND` saved translation `10.5 -3 8.25` and invoked `onSave`. |
| Native Save while minimized | `IsIconic` was true. Save wrote `21.75 -4.5 9.125` and invoked `onSave`, while a pending update-listener inspection request stayed unanswered. A fresh Editor process read the exact saved translation. |
| Native custom-script dispatch while minimized | The script request remained unanswered for two seconds before dispatch. A discovered Scripts-menu command executed the Lua request and returned translation `31.5 -5.25 12.125`. `IsIconic` was true before and after dispatch. |
| Repeated minimized script dispatch | Inspection succeeded, an unsupported operation returned an error, and a later mutation and inspection succeeded. Final translation was `42.25 -6.5 14.875`. |
| Combined minimized mutation and Save | Script dispatch changed the node. Native Save wrote the final translation and invoked `onSave`. A new Editor process opened the I3D and read exactly `42.25 -6.5 14.875`, then exited with code 0. |
| Clean shutdown through script dispatch | A minimized custom-script request reached `editorExit(0)` and the original process exited. |

The native message return value alone was never the acceptance criterion. XML responses, the actual I3D TransformGroup, the save notification and a fresh engine load provided separate checks. No experiment called an internal function address, injected a DLL, patched the executable, or synthesized input.

## Why the minimized route works

The ordinary `addUpdateListener` bridge pauses when the Editor is minimized. The tested native Save and custom-script command paths remain active. A custom entry in the Scripts menu calls a global Lua dispatch function on the Editor's own thread. The host sends that menu command through `SendMessageTimeoutW` with `WM_COMMAND`, then reads an independent response file. Native Save uses the same Windows mechanism with command ID 6001.

The custom script command ID was 7311 in this run. It is a dynamic menu ID and must be discovered on each launch. The instruments require the pinned executable hash, expected process, exact named main-frame title and a unique enabled menu entry. Save ID 6001 also exists in another UI class, so PID matching alone would be unsafe.

The dispatch helpers contain no foreground activation, mouse or keyboard calls. The foreground-window handle remained unchanged during the minimized script dispatch. That handle still belonged to the minimized Editor in this run, so this experiment alone does not prove dispatch while another application owns the foreground. Earlier normal-window testing established unfocused Lua polling. A sustained minimized run during real user activity remains a separate acceptance check.

## Reproduction setup

Use only an isolated fixture. These are research instruments, not a production service.

1. Create `native-save-fixture.i3d` with a root child TransformGroup named `MCP_Save_Probe`. Use an absolute scratch directory with a trailing slash as `MCP_PROBE_ROOT`.
2. Copy `instruments/native_dispatch_menu.lua` into a dedicated scripts directory. Add `<script_dirs paths="C:/absolute/scratch/scripts/"/>` directly under the dedicated configuration's `<editor>` root. Placing it under `<save>` does not register the script. That incorrect placement was tested first and corrected after inspecting the written XML structure.
3. Start the Editor normally with the fixture as positional input, `-noVersionSelection -supressChangelog -disableTextureStreaming`, `-configXML <dedicated-config>` and `-runScriptCode "MCP_PROBE_ROOT='C:/absolute/scratch/';source('C:/absolute/path/runtime_save_fixture.lua')"`. Notify the user before visible startup. Keep the normal user configuration out of this experiment.
4. Wait for `ready.xml`, check its scene and node, and capture the exact main-frame title. Initial document loading and script initialization succeeded in this invocation. This does not establish a general execution-order guarantee for every startup.
5. Run `windows_script_probe.py --pid <pid> --expected-title <exact-title> --expected-scene <absolute-fixture-path>` without `--invoke` first. It must find exactly one enabled `MCP Probe Dispatch` entry below Scripts. Editor-generated folder labels can insert spaces into a path; do not construct a menu label from the filesystem path.
6. Minimize the isolated window. Write `request-001.xml` with `<request op="set" x="31.5" y="-5.25" z="12.125"/>`. Publish each request atomically and use the next sequence number for subsequent requests. Invoke `windows_script_probe.py` with the same PID/title and `--invoke`. Read `response-001.xml`; do not infer completion from the Windows return value.
7. Use `windows_save_probe.py` with the same PID/title to inspect Save first, then add `--send-save`. Check `save-001.xml` and the I3D. A named, writable document is required. Save As and dialog handling were not tested.
8. Dispatch a `quit` request. Open the saved fixture in a fresh Editor process using `runtime_readback.lua` as the startup source. Check `fresh-readback.xml` and exit status. This fresh load is a visible-startup operation too.

For each Python invocation set an external bytecode cache as required by the repository instructions. The static scanners require `pefile` and `capstone`; the Windows dispatch helpers use only the standard library. Keep raw output in the ignored `.docs` area. The Lua probe allows `set`, `inspect`, `inventory` and `quit` only. Request files use sequential names and responses do not implement production authentication, deduplication or recovery.

## Coverage and limits

The Lua registration analysis traced a bounded Editor-native registration block and the runtime inventory enumerated 2,054 global keys and one level of global table functions. No callable full-scene Lua saver was identified. This does not prove that no hidden saver exists. The native route removes the need to resolve that question before building a background MCP prototype.

The startup analysis shows that `-logging nogui` controls a logging sink. It is not a headless switch. Earlier hidden starts did not reach the initialization marker within their tested timeouts. Normal startup followed by minimized operation is proven; entirely invisible startup was not established in this phase. Later [private-desktop trials](../03-startup-and-headless/invisible-startup-results.md) succeeded.

The fixture contains one TransformGroup. Meshes, terrain, animation, referenced files, sidecars, Save As, modal errors and long-running operations need representative acceptance tests. A two-second Windows-message timeout bounds the host wait, but cannot cancel an operation that has already started. Never retry an uncertain mutation blindly. Version and menu changes must fail closed until revalidated.

## Proposed MCP phase

Build a Windows-only local host that starts a dedicated Editor session, discovers its script command, publishes one allowlisted request at a time and waits for a correlated response. Perform Lua scene mutations through that script entry and use native Save only after confirming the current document. Verify persistence independently. Keep user sessions separate.

The next acceptance gates are sustained minimized operation while another application has focus, representative FS25 assets and sidecars, and failure recovery without duplicate mutations. Invisible startup can remain a separate research lane. No MCP server was built or installed in this phase.

## Instrument review

After the live run, review added a required explicit fixture path and a one-TransformGroup XML guard to both Windows helpers. These checks run before Win32 calls and reject other documents. The post-review guards were checked without starting the Editor. The original live dispatch predates these additional guards. The disposable-directory requirement remains an operator precondition. Derived artifact hashes and minimized-state receipts are recorded in [runtime-results.metadata.json](runtime-results.metadata.json).

## Archive context

This report records the 2026-10-16/17 research against the pinned Editor build. Raw assets, screenshots, configurations and machine logs referenced under `.docs/` are local-only and are not distributed. Reproduction commands retain their historical workspace assumptions; read the [instrument index](../07-instruments/README.md) before adapting or running them.
