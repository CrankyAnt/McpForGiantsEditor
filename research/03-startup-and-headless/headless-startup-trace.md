# True headless startup trace

Date: 2026-10-17. Target: GIANTS Editor 10.0.14.0, `editor.exe` SHA-256 `c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`.

## Question and scope

Can the pinned Editor start, load an I3D, run `-runScriptCode`, and use native Save without any Editor HWND or graphics initialization?

This is a static trace of the local executable, packaged Lua, and packaged `editor.xml`. It did not start a process, modify an asset, alter configuration, or patch the binary. Raw vendor disassembly is excluded from this tracked note.

## Finding

No true headless startup route was found. The only startup parser flags are the previously documented flags in `startup-flags.md`. No parsed flag selects a no-window, no-renderer, software-renderer, null-renderer, offscreen, batch, or quit route.

The parser constructs the main application object at RVA `0x1507fa`, then immediately calls the vtable entry at offset `0x1c8` with `DL = 1` at `0x150818`. The constructor begins at `0x15c440`; it receives the parsed arguments and initializes the application object before the previously known `-logging nogui` bit test at `0x15c99e`.

That vtable entry resolves to `0xef64b0`. With the parser's true argument, its display-state path reaches `ShowWindow` at `0xef65d7`. The branch selects a nonzero show command. Its reachable values are `3`, `4`, `5`, `6`, `8`, and `9`, which are normal Windows show, minimize, restore, or activate forms. The only local route that supplies `0` to this `ShowWindow` call requires the vtable entry's boolean argument to be false. The parser passes true. This establishes a startup show operation after application construction. It does not by itself name the HWND or prove the location of `CreateWindowExW`.

Therefore, `-runScriptCode` is not an established pre-window or no-window action. The parser collects its argument at `0x1500f0` and `0x150120`. When it finds the following argument, `0x1502af` copies that argument into the parser's startup string at `[RBP+0x1a8]`; `0x1507bc` passes that string's address into the application constructor. The parser then takes the normal application-init and show path. This pass found no parser-side Lua evaluation call, no branch that evaluates the supplied code before the application obtains its GUI state, and no branch that bypasses the GUI state before evaluating it. It also does not prove that the application queues script evaluation only after `ShowWindow`; that needs a runtime trace of the stored string or Lua `loadstring`.

## Startup controls and configuration

The parser's established startup literals remain:

- `-configXML <path>` at `0x14e740` and `0x14e770`.
- `-globalTime` at `0x14e690`.
- `-disableLuaErrorReporting` at `0x14e6e0`.
- `-onlyLoadRuntimeReferences` at `0x14e8b0`.
- `-disableTextureStreaming` at `0x14e8f0`.
- `-noVersionSelection` at `0x14f3a0` and `0x14f50c`.
- `-runScriptCode <code>` at `0x1500f0` and `0x150120`.
- `-codeSvnDir <path>` at `0x1503e0`.
- `-supressChangelog` at `0x150550`.
- `-logging <value>` at `0x150590`, including value `nogui` at `0x150684`.

`-logging nogui` sets constructor flag `0x2`, which skips a logging-sink setup call at `0x15c9c9`. The show path above occurs later through the parser's vtable startup call and is not controlled by this bit.

The package default `editor.xml` contains only `window_layout` geometry and perspective, plus regular editor settings. The captured user configuration has a separate `editor/graphic/renderer` element with value `Vulkan`. It does not make `renderer` a command-line switch or a no-window control.

The executable carries an engine backend-name table at RVA `0x214b448` through `0x214b4a0`: `PS5`, `GNM`, `Direct 3D 12`, `NULL_TRACKING`, `D3D_12`, `NULL TRACKING`, `NULL`, `Vulkan`, `Metal`, and `NVN`. Pointers at `0x205ad30` through `0x205ad68` select entries in that table. This supplies candidates for a controlled configuration-reader trace. It does not prove that the Editor accepts every listed value on Windows, nor that `NULL` or `NULL_TRACKING` skip frame creation, graphics initialization, or an Editor HWND.

The exact ASCII key `editor.graphic.renderer` is at RVA `0x212c320`. Its sole direct code reference is `0x1dfcee`, in `0x1dfc40` through `0x1e3162`. That code selects the renderer-name pointer from the same table using the dword at object offset `0x2b0`, then calls a configuration-object virtual method with the exact key and selected name. It is a configuration writer: its only direct caller is `0x168464`, in `0x168420` through `0x168885`, where the caller first replaces object vtables and passes `DL = 1`. This is a destruction or save-configuration path, so it cannot identify startup's configuration reader. It is still a precise hook for recording the persisted backend enum and its selected name.

The startup constructor gives that enum a concrete internal location. It allocates an `0x850`-byte configuration object at `0x15c827`, constructs it at `0x15c85c`, then stores its pointer at application-object offset `0x690` at `0x15c862`. The configuration constructor writes `5` to its offset `0x2b0` at `0x1d90f7`. The backend pointer table maps index `0` to `Direct 3D 12`, `1` to `GNM`, `2` to `PS5`, `3` to `NVN`, `4` to `Metal`, `5` to `Vulkan`, `6` to `NULL`, and `7` to `NULL_TRACKING`. This accounts for the observed fallback to Vulkan when the XML renderer text is changed.

For a research-only process-memory test, a runtime hook can let the configuration constructor return at `0x15c85c`, then set `*(uint32_t *)(configuration + 0x2b0)`, where `configuration = *(void **)(application_this + 0x690)`, to `6` for `NULL`, or `7` for `NULL_TRACKING`, before the later backend factory reads it. This is an internal enum override, not proof that either backend is valid for the Editor. The trace must record the selected factory branch, graphics-device initialization, window creation, Lua completion, and clean exit.

There is one direct startup consumer of the field. The application constructor calls `0x304330` at `0x15cb1a`, passing the configuration pointer as its third register argument. `0x304432` reads `config+0x2b0`, copies it to a new object's offset `0x278`, and compares it with `5` at `0x304454`. Value `5` enters the long construction path at `0x30445d`. Every other value branches to `0x304c21`, which resolves the enum through `0x331260`; that helper indexes the same backend-name table at `0x205ad30`. The non-`5` branch then reaches the end of `0x304330` after common handling. Static evidence does not establish whether that handler reports an unsupported backend, exits, or later creates a valid null device. It does establish that `NULL` is not a simple alias for the normal value-`5` path.

On the direct constructor path examined here, `0x1d90f7` is the only identified initialization write of the configuration renderer field before `0x15cb1a` consumes it. The runtime hook must still log the field immediately before the consumer, because virtual calls or indirect paths are outside this direct-call coverage.

The executable contains no null-terminated ASCII or UTF-16 startup literal for `headless`, `offscreen`, `renderDevice`, `batchconverter`, or `renderheadless`. `-nogui` and `-noGUI` are absent. The standalone `batch`, `software`, renderer, graphics, D3D, OpenGL, and Vulkan strings are not startup-parser literals. They do not establish a command-line startup switch.

## Lua and rendering evidence

The captured runtime binding inventory contains `loadstring`, `setIs3DGraphicsRenderingEnabled`, and `BatchedScreenshotRenderer`. That records APIs available after normal engine initialization. It does not provide a startup mode or prove those APIs work without a window or graphics device.

The packaged `MapOverviewGenerator.lua` creates `BatchedScreenshotRenderer` only after it has set the camera, refreshed the viewport, and ensured the update loop runs. This is an editor automation path that assumes normal graphics initialization. It is not a headless bootstrap route.

The known native Save and `-runScriptCode` runtime invocations include a fixture path, `-noVersionSelection`, `-supressChangelog`, `-disableTextureStreaming`, `-runScriptCode`, and `-configXML`. They do not include a no-window or renderer-bypass control. Their successful operation is evidence for normal GUI initialization on an inactive private desktop, as documented in `invisible-startup-results.md`, not for an HWND-free process.

## Boundaries and next trace

This pass identifies the parser-to-constructor-to-show chain and rules out the named startup controls in this binary. It does not complete a data-flow proof from the application object to the `CreateWindowExW` call that creates the Editor frame. Each of the direct `CreateWindowExW` call sites is in a function with no direct `E8` caller, which is consistent with virtual or toolkit dispatch and prevents a reliable static nesting path to the constructor. It also does not identify the exact method that evaluates the stored `-runScriptCode` string.

The next useful static or debugger trace is narrow:

1. Break on the parser call at `0x1507fa`, the post-constructor virtual call at `0x150818`, and `ShowWindow` at `0xef65d7`. Record the application object and the HWND passed to `ShowWindow`.
2. Break on the matching `CreateWindowExW` call for that HWND, then trace its caller back to the application object.
3. Break at `0x1dfcee` to record the persisted renderer enum and name. Separately hook the startup configuration reader or its string comparison for `editor.graphic.renderer`, then record the selected backend for `Vulkan`, `D3D_12`, `NULL`, and `NULL_TRACKING`. For each accepted value, record whether the matching window creation and graphics-device setup still run.
4. Break on Lua `loadstring` or the stored `-runScriptCode` buffer, and record whether it runs before or after the matching window creation and graphics-device setup.

Until that trace finds a constructor flag or configuration value that bypasses both the matching window creation and graphics initialization, use the proven inactive-private-desktop route for invisible work. Do not claim a true headless mode for this build.

## Sources

- Hash-pinned local `editor.exe`, analysed read-only.
- `startup-flags.md` for parser and `nogui` evidence.
- `invisible-startup-static.md` for direct Win32-import and configuration coverage.
- Packaged `editor.xml` and `scripts/map/mapToolkit/utils/MapOverviewGenerator.lua`.
- Captured runtime binding inventory under ignored local evidence, used only to distinguish post-initialization Lua APIs from startup controls.

## Runtime follow-up

The [32-case runtime investigation](headless-runtime-results.md) exercised the candidates above. It observed all eight backend enums at the factory. Vulkan completed the Lua probe with GUI windows; every other enum produced a canvas-creation failure before Lua. The NULL names identify common engine enum values, not working headless backends in this Editor canvas factory.

## Archive context

The original raw inputs were discarded; historical `.docs/` paths are no longer available. See [evidence availability](../../README.md#evidence-and-applicability) for the retained results and limits. Historical commands require new prepared data and reviewed paths; see the [instrument index](../07-instruments/README.md).
