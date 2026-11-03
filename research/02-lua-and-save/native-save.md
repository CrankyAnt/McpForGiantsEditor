# Native Save command analysis

## Result

The pinned Editor executable contains a concrete native command route for Save and Save As. Save uses command ID `6001`, and Save As uses `6002`. This is static evidence for a controlled Windows-message experiment. It does not prove that either command can execute while minimized, that the current document is correctly named, or that a successful message dispatch means a file was written.

## Evidence chain

| Anchor | RVA | Observation |
|---|---:|---|
| Save toolbar label | `0x20e8a88` | Null-terminated ASCII label `Save i3D file` |
| Save toolbar command argument | `0x164dbc` | Within initializer `0x15c440`, the toolbar-registration call receives ID `0x1771`, decimal 6001 |
| Save As toolbar label | `0x20e8ad0` | Null-terminated ASCII label `Save i3D file as` |
| Save As toolbar command argument | `0x164eda` | Same initializer registers `0x1772`, decimal 6002 |
| Save menu registration | `0x15d514` | Same command ID 6001 is passed in the menu initialization path |
| Save event binding | `0x7dedd`, `0x7ea93` | Both event-table initialization sequences construct a callback to `0x175620`, then associate it with ID 6001 |
| Save As event binding | `0x7df51`, `0x7eb07` | Corresponding callback target is `0x175680` for ID 6002 |
| Save handler | `0x175620` | Calls document function `0x1f8970`, passing an object from frame offset `0x690`; selects flags and an optional pointer using frame state |
| Save As handler | `0x175680` | Calls the same document function with flags 3 and a null optional pointer |
| Document save entry | `0x1f8970` | Passes its mode to `0x1f8d90` in the full-document branch |
| Full-document save | `0x1f8d90` | Contains references to the Save As dialog title, save error message and post-save Lua notification |
| Save As dialog reference | `0x1f8f34` | Refers to `Save As with Files` at `0x2107fc0` |
| Save error references | `0x1f98ed`, `0x1f9f54` | Refer to `Error while saving i3d file` at `0x20f5438` |
| Lua notification reference | `0x1fa0e7` | Refers to `onSave` at `0x212c7a8` |

The small Save handler does not itself inspect window minimization. Its deeper callees and framework message routing may still impose conditions. No minimized-operation claim follows from this observation alone.

The same command ID also appears in another UI class, binding callback `0x531730`. Therefore a runtime probe must target the exact main Editor frame, not any window belonging to the process. A PID check alone is insufficient.

## Questions recorded before runtime testing

- Whether a direct `WM_COMMAND` to the named main frame follows this route in the running build.
- Whether native Save works with the frame minimized and Lua updates paused.
- Whether Lua mutations have to mark the document dirty separately.
- Which frame/document flags govern direct-save versus file-dialog behavior. Their semantic names have not been recovered; offsets are not an external interface.
- Whether a post-save callback, complete file write and fresh engine reload all confirm the same mutation.
- Whether geometry, sidecars, terrain and other complex assets preserve their intended state. A simple TransformGroup test cannot settle those cases.

## Proposed bounded runtime experiment

Start a disposable, already named I3D with one fixture group and an isolated Editor config. Query the active document name through Lua. Change the fixture, then inspect the main menu and its Save ID before sending anything. Send only Save 6001 through a timeout-bounded native message. Verify the resulting I3D independently and observe the save notification. A zero message result alone is not acceptance evidence.

Repeat with a second fixture value while the main frame is minimized. Make no mouse/keyboard input or foreground activation during the save. Afterwards load the saved document in a fresh Editor process and verify the value. If a modal appears, the source file is not the expected fixture, or the process is unresponsive, stop the probe rather than retrying blind.

## Reproduction

Run the hash-pinned `instruments/native_save.py` against the installed executable. Useful queries are `--text "Save i3D file"`, `--immediate 6001`, `--rva 0x175620 --function`, and `--rva 0x1f8d90 --function`. Redirect raw assembly to the ignored `.docs` evidence directory. Addresses, selected call relations and command identifiers above are derived facts; no vendor code is copied here.
## Runtime follow-up

The controlled experiment confirmed direct Save while minimized, the save notification, the actual I3D contents and exact readback in a new Editor process. A native custom-script menu command also executed Lua mutations while minimized. See [live-results.md](live-results.md) for the receipts, reproduction and remaining asset coverage. The earlier questions about message routing and simple TransformGroup persistence are resolved for this pinned build. Complex assets, document flags and Save As remain outside the tested scope.

## Archive context

The original raw inputs were discarded; historical `.docs/` paths are no longer available. See [evidence availability](../../README.md#evidence-and-applicability) for the retained results and limits. Historical commands require new prepared data and reviewed paths; see the [instrument index](../07-instruments/README.md).
