# Modal-error probe design

Date: 2026-10-17. Status: design only. This note does not start the Editor, create a desktop, send a Windows message, or add a host implementation.

## Question and boundary

The pending question is whether GIANTS Editor 10.0.14 exposes a real error modal during a controlled native save failure, and whether a host on the same private Win32 desktop can record and recover from that modal without affecting another Editor window or an unsaved-document prompt.

This is an Editor-native-error experiment. A Lua call to `MessageBox.show` or a Win32 `MessageBoxW` called by a probe only tests the probe. It must be labelled synthetic and cannot satisfy this question.

The existing native route is limited to the pinned executable, exact PID, exact named fixture, and the discovered enabled Save command ID 6001. [windows_save_probe.py](../07-instruments/windows_save_probe.py) already establishes those checks before dispatch. The script route likewise restricts itself to the isolated `MCP Probe Dispatch` menu entry. [windows_script_probe.py](../07-instruments/windows_script_probe.py) does not prove completion from a returned Windows message. Preserve those limits.

## Evidence before a live attempt

The installed `ScriptBindingBuiltins.xml` describes `error` as a Luau exception. The installed `scriptBinding.xml` describes `loadI3DFile(filename, ...)` as returning `rootNodeId` and `failedReason`. It describes `printError` as console output. Neither binding declares a generic error-dialog API.

The installed `scripts/ui/MessageBox.lua` defines the Lua helper `MessageBox.show(title, text, callback, windowX, windowY)`. It constructs an Editor Lua `UIWindow`; it is not evidence that a native save error uses a Win32 dialog. The only binding declaration that explicitly opens a dialog is `showColorDialog`, which is unrelated to saving.

Static Unicode/ASCII string extraction from the pinned `editor.exe` finds these relevant strings: `Error while saving i3d file`, `Error while saving i3d file.`, `ERROR_SAVE_FAILED`, `ERROR_SAVE_NO_SPACE`, `Failed to create temporary file`, `Failed at renaming the new saved %s file to %s`, `Cannot open file %s for writing`, and `Error: Sharing violation on file '%s' ... perhaps open in another program?`. Static strings do not establish a code path, dialog type, owner window, caption, control ID, or whether the Editor writes through a temporary replacement file.

Consequently, a bad Lua request such as `error("MCP_MODAL_MARKER")` is a console-only control. A nonexistent `loadI3DFile` path is also a console-or-return-value control. Both are useful to show that the observer does not mistake console output for a modal. Neither is a candidate acceptance case.

## Disposable native-failure case

Use a new scratch directory below `C:\TMP` and one copy of the one-TransformGroup `native-save-fixture.i3d`. Keep its normal dedicated configuration, runtime-save receipt, exact title, PID, executable path, and SHA-256 checks. Do not use a user scene, normal Editor configuration, a network location, a full disk, global ACL changes, or a different process's document.

The primary case opens the already loaded fixture itself with `CreateFileW` under a parent-owned helper process. It requests read access and zero sharing (`dwShareMode = 0`), retains the handle until the result is captured, and writes nothing. First prove that this handle is actually exclusive with a second controlled `CreateFileW` attempt that must fail with `ERROR_SHARING_VIOLATION`. Then dispatch exactly the already-verified native Save command once.

File locking is a candidate, not a guarantee. The Editor may save through a temporary file and atomically replace the destination, which can bypass a write-open conflict or fail at a later rename. The acceptance receipt must record which of these occurred: no modal and a completed save, no modal and a failed save, a modal with an actual native failure, or an uncertain/hung Editor. Do not infer a modal from the lock alone.

Do not remove directory write access or modify an ACL as the primary way to provoke failure. That broadens the test beyond the owned file and adds recovery work. If the exclusive-file case does not reach a native modal, stop after documenting its result. A later separately authorized design can select a second fault mechanism only after tracing its exact cleanup and ownership boundary.

## Static path reconnaissance before the live case

Before a live run, repeat the pinned-binary hash check and extract only strings relevant to save failure. Record the exact strings above and their offsets when the scanner supports them. Then inspect the surrounding disassembly or cross-references for `ERROR_SAVE_FAILED`, `ERROR_SAVE_NO_SPACE`, and `Error while saving i3d file`.

The required result is a short map of candidate error paths and their reachable preconditions. It may rule out a candidate, but it cannot claim a modal exists until the actual Editor process creates one. Do not attempt to call internal code addresses, patch the binary, inject a DLL, hook UI APIs, or force an exception path.

## Private-desktop observation

Attach the host and the owned Editor process to the same existing `privateWin32desktop`. Never enumerate, activate, move, focus, hook, or send messages to windows outside that desktop.

At a bounded interval after the one Save dispatch, enumerate top-level windows on that desktop. A candidate must meet every check below before it is recorded as the owned error dialog:

1. Its process ID equals the verified Editor PID.
2. Its class name is exactly `#32770` or the observed wxWidgets dialog class recorded during this exact run.
3. Its owner or root owner resolves to the verified named Editor main-frame handle.
4. It is visible and enabled.
5. Its title and visible text match an allowlist captured from the relevant native save-error path. A marker such as the scratch filename may supplement the allowlist, but cannot replace it.
6. It has exactly one allowed button with the expected caption and command ID. The host must read the button control ID before any recovery action.

Capture class, title, owner, root owner, PID, child-control class/text/ID, and window rectangle. `PrintWindow` may make a pixel snapshot only after those identity checks, using the owned dialog handle and without activation. Save the bitmap under the disposable run directory. A failed or blank `PrintWindow` result is evidence about capture only, not absence of a dialog.

The observer must never use a global `EnumWindows` result as a dismissal target. It must not use `PostMessage`, `SendInput`, keyboard accelerators, mouse input, `WM_CLOSE`, Escape, Enter, or an arbitrary `IDOK`/`IDCANCEL` value.

## Recovery allowlist

Recovery is optional. First live observation should leave the dialog open long enough to collect the receipt, then terminate only the owned disposable Editor process by its verified PID if manual recovery is unavailable. A later attempt may close the dialog only when all identity checks above pass and the discovered control matches a predeclared tuple:

| Dialog signature | Allowed action | Proof required before sending |
| --- | --- | --- |
| Exact save-failure title/text, one button caption `OK`, button control ID read from this dialog | `WM_COMMAND` with that exact control ID to the owned dialog | Capture receipt plus exact PID, owner, class, title, text, button caption and ID |
| Exact save-failure title/text, one button caption `Cancel`, button control ID read from this dialog | `WM_COMMAND` with that exact control ID to the owned dialog | Same receipt, and no document-selection or save-as text |

There is no reusable hard-coded `OK` or `Cancel` ID. A standard `IDOK` or `IDCANCEL` constant does not prove that an Editor or wxWidgets dialog assigned that ID. Sending `WM_COMMAND` must use `SendMessageTimeoutW`, a short timeout, and `SMTO_ABORTIFHUNG | SMTO_ERRORONEXIT`. A return only proves the window procedure returned.

Reject and require manual handling if the dialog has more than one actionable button, any `Save`, `Save As`, `Don't Save`, `Yes`, `No`, filename, path, overwrite, or unsaved-changes wording, an unexpected owner, an unexpected class, missing control metadata, or a changed binary hash. This prevents a native save failure from turning into blind dismissal of a destructive prompt.

After a permitted recovery action, re-enumerate only owned windows, verify that the candidate disappeared, inspect the fixture bytes and save receipt, and release the held file handle in a `finally` path. Then quit only the verified disposable Editor process. An unexpected modal, uncertain save state, timeout, or process exit produces no retry. Preserve the fixture and receipts for diagnosis.

## Live acceptance and stop conditions

The probe succeeds only if all of the following are retained:

- The file-lock helper proves its own exclusive handle.
- The verified native Save dispatch occurs once against the disposable named fixture.
- The observer records an Editor-owned dialog that satisfies the identity checks, or records a no-dialog result with independent save/failure evidence.
- The static string family and observed dialog text are consistent enough to tie the observed dialog to the native save failure. A Lua marker alone does not count.
- Any automatic recovery uses one observed, exact button ID and leaves no other owned dialogs.
- The helper releases its file handle and the test process exits. The normal configuration hash and all installed-file hashes remain unchanged.

Stop immediately, retain the run directory, and do not auto-dismiss when identity is ambiguous, the exact UI text is new, the dialog exposes destructive choices, a screen snapshot contradicts control enumeration, the Editor becomes unresponsive, or the fixture write outcome is unknown.

## Callable Lua dialog inventory

The installed files expose these potential Lua UI calls, all outside the native-error acceptance path:

| Symbol | Source | Status |
| --- | --- | --- |
| `MessageBox.show(title, text, callback, windowX, windowY)` | `scripts/ui/MessageBox.lua` | Synthetic Editor-Lua message window. Not a native-error test. |
| `MultiOptionDialog.show(title, text, buttons, windowX, windowY)` | `scripts/ui/MultiOptionDialog.lua` | Synthetic multi-button Editor-Lua window. Not a recovery control. |
| `InputStringDialog.show(...)` and `InputFloatDialog.show(...)` | installed `scripts/ui` | Synthetic input windows. Excluded. |
| `showColorDialog(callbackFunction, ...)` | `scriptBinding.xml` | Bound color picker. Unrelated and excluded. |

No generic `showError`, `showMessageDialog`, `messageDialog`, native file-save, or native dialog-dismiss Lua function was found in the inspected `scriptBinding.xml` and `ScriptBindingBuiltins.xml`. This is an inspected-binding result, not proof that no unlisted internal function exists.

## Sources

- Installed `editor.exe`, pinned by the existing save probe hash and path checks, inspected by static string extraction on 2026-10-17.
- Installed `scriptBinding.xml` and `ScriptBindingBuiltins.xml`, inspected on 2026-10-17.
- Installed `scripts/ui/MessageBox.lua` (installed local reference, not distributed), inspected on 2026-10-17.
- Existing [runtime results](../02-lua-and-save/live-results.md), [windows save probe](../07-instruments/windows_save_probe.py), [script probe](../07-instruments/windows_script_probe.py), and [fidelity probe](../07-instruments/fidelity_scene_probe.lua).
- Microsoft Win32 documentation for [CreateFileW](https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-createfilew), [SendMessageTimeoutW](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-sendmessagetimeoutw), [PrintWindow](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-printwindow), and [GetWindowThreadProcessId](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-getwindowthreadprocessid). These document API contracts, not GIANTS Editor behavior.

## Archive context

The original raw inputs were discarded; historical `.docs/` paths are no longer available. See [evidence availability](../../README.md#evidence-and-applicability) for the retained results and limits. Historical commands require new prepared data and reviewed paths; see the [instrument index](../07-instruments/README.md).
