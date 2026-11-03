# Invisible startup runtime results

Date: 2026-10-17. Target: GIANTS Editor 10.0.14.0, SHA256 `c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`.

## Result

The Editor started and worked on a separate, inactive Win32 desktop with no Editor window observed on the user's input desktop. Both copied FS25 assets passed Lua inspection, mutation, native Save and readback in a fresh process. Animation sampling and native PNG rendering worked there too. This establishes an invisible startup route for the tested machine and build.

The Editor still creates GUI windows and initializes its renderer. This is not a windowless headless mode. It uses the interactive `WinSta0` window station, a normal Windows user session and the installed graphics driver. No MCP server was built.

## Method

The [private desktop instrument](../07-instruments/private_desktop_probe.py) creates a unique Win32 desktop with read/create rights. It starts the pinned executable through `CreateProcessW`, with `STARTUPINFO.lpDesktop` naming that desktop and handle inheritance disabled. It assigns the suspended child to a job with kill-on-close before resuming it. The instrument never calls `SwitchDesktop`, activates a window or injects mouse/keyboard input.

Editor startup uses the existing dedicated configuration, script directory and disposable asset copies. The helper temporarily attaches its windowless controller thread to the private desktop to verify the exact Editor frame and dispatch the existing native script and Save commands. It restores the controller thread afterwards. The normal user's Editor configuration is not used for these launches.

The monitor records the input desktop, foreground process and Editor windows on the input desktop throughout each process lifetime. A startup timeout, unexpected input desktop, Editor foreground window or Editor window on the input desktop ends the test. The helper terminates only its owned Editor process, waits for it, and releases its handles. There is no fallback launch on the user's desktop.

## Successful trials

Each asset used two fresh Editor processes and two distinct private desktops. The initial process applied root translation `7.25,-1.5,2.125`, inspected the scene and saved through native command ID `6001`. The second process loaded the saved scene without applying that mutation and verified the persisted translation.

| Asset | Initial samples | Fresh-load samples | Result |
| --- | ---: | ---: | --- |
| Animated garage gate | 49 | 97 | Save, readback, 41 poses and three PNGs passed |
| Water trailer | 50 | 62 | Save, readback and one PNG passed |

All four processes exited with code zero. Every one of the 258 telemetry samples reported input desktop `Default`, no Editor window on that desktop and a foreground process other than the corresponding Editor process. The foreground HWND and PID remained constant within each trial. Recorded sample gaps had medians near 62 ms and a maximum of 93.144 ms. The nominal 50 ms polling interval is not a timing guarantee. Samples alone cannot exclude an event between observations; explicit process-to-desktop assignment provides the separate structural evidence.

The Editor frames had `IsWindowVisible=true` and `IsIconic=false` on their private desktops. Windows membership came from `EnumDesktopWindows` with the explicit private desktop handle, followed by PID, executable hash, title and menu checks. `GetThreadDesktop` for the foreign Editor thread returned access denied, error 5. That query is unavailable evidence, not confirmation of a thread desktop. The instrument accepts that specific diagnostic only after explicit private-desktop membership succeeds; other ownership failures still stop the test.

## Scene and rendering comparison

The saved I3D files matched their earlier visible native-Save controls byte for byte. The gate animation sidecar also matched. Shapes sidecars differed, as they did in the preceding fidelity research; these tests do not establish lossless serialization.

The fresh gate process evaluated the same 41 animation times from 0 to 10,000 ms and the same 24 nodes as the visible control. Pose values matched. Start, middle and end gate renders and the trailer render were fresh, decodable 512 by 512 PNGs. Each had zero differing pixels against its visible saved-scene control. This extends the earlier [fidelity results](../05-asset-fidelity/fidelity-results.md) to invisible startup on this machine.

Source hashes cover all 32 installed input files used by the two fixtures. Those files and the normal Editor configuration remained unchanged. After the trials, no Editor process remained. `OpenDesktopW` for all four successful trial names returned null with error 2 after cleanup, confirming that those desktop objects no longer existed.

## Diagnostic attempts

Five earlier private-desktop starts were originally stored separately under the gate fixture's `attempt-01` through `attempt-05` directories. The first four reached the Lua-ready marker but the instrument rejected the unavailable foreign-thread desktop query. The fifth completed inspect, Save and quit, then reported a teardown error caused by stale Win32 last-error state during empty desktop enumeration. The final instrument captures last error immediately, clears it before enumeration, and does not require private-frame discovery after confirmed process exit. These were instrument corrections, not Editor initialization failures. No visible fallback was used.

The four successful processes above ran after those corrections. Their input-desktop observations and receipts are independent of the diagnostic attempts.

## Evidence and reproduction

[Derived metadata](invisible-startup-results.metadata.json) records receipt checks, source hashes, frame membership, telemetry, pose/image comparisons and post-exit system checks. [The analyzer](../07-instruments/analyze_invisible_startup.py) originally generated it from ignored local evidence. Raw assets, logs and images formerly under `.docs/giants-editor-invisible/` have since been discarded; repeating the analysis requires a new trial dataset.

The private launcher exposes read-only `inspect-default` and explicit private launch/controller modes. Its runtime modes require the prepared disposable fixture layout and exact build hash. They are research instruments, not a general editor-control API. The read-only static findings and their limits are in [startup analysis](invisible-startup-static.md); the Windows API design is in [private desktop feasibility](../04-desktop-operations/private-desktop-feasibility.md).

## Remaining limits

The trials cover two existing assets and short process lifetimes. Locked sessions, remote disconnects, Session 0, other Windows/GPU/Editor versions, large terrains, long-running sessions and recovery from Editor modal dialogs remain untested. A private desktop is not a security sandbox against the launched process. No rights or desktop ACLs were changed.

An MCP can use this route to host the existing Lua request bridge, native Save and render requests without occupying the user's input desktop. A production bridge still needs bounded operation handling, private-dialog detection, owned-process cleanup and version checks. It must preserve the no-visible-fallback rule. The present result justifies that next implementation step; it does not supply that implementation.

## Validation and delivery

Python compilation, Ruff lint and format checks, repository validation, the static 24-ShowWindow/three-GetStartupInfoW positive controls and a mocked refusal of stale session receipts passed. Read-only desktop inspection still reported `Default` and no Editor window on the input desktop. The analyzer regenerated the metadata from retained trials and current read-only cleanup checks. Independent review checked the native desktop handling and the claims against the retained evidence.

The original phase performed no remote Git publication, skill update, runtime installation or MCP deployment.

## Archive context

The original raw inputs were discarded; historical `.docs/` paths are no longer available. See [evidence availability](../../README.md#evidence-and-applicability) for the retained results and limits. Historical commands require new prepared data and reviewed paths; see the [instrument index](../07-instruments/README.md).
