# Private desktop operational trials

Date: 2026-10-17. Target: GIANTS Editor 10.0.14.0, executable SHA256 `c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`. This is local research, with disposable copied assets and dedicated configuration. No MCP server or runtime installation was created.

## Result

The inactive private Win32 desktop supported a 15-minute command run, native Save, native viewport rendering, commands during a real workstation lock, and recovery from a blocking Save error. Fresh processes loaded the final expected translations from all three saved test scenes. These are observations on this machine and build, not a general unattended-operation guarantee.

| Trial | Observed result |
| --- | --- |
| Duration | 900.88 seconds; 371 commands, including 31 Saves and 30 renders; no missing or invalid command receipts |
| Latency | Host median 172.95 ms, p95 186.93 ms; native median 2.41 ms, p95 15.95 ms |
| Real lock | WTS reported locked for 154.10 seconds, then unlocked; all 29 commands with locked flags before and after had valid receipts |
| Locked commands | 10 inspections, 11 mutations, 4 renders and 4 Saves |
| Active-work stop boundary | Active locked work stopped after 65.03 seconds; the controller only waited for unlock afterward |
| Fresh reload | Final x values 0.339, 0.033 and 0.011; y=-1.5 and z=2.125; all matched within 1e-5 |
| Cleanup | Duration, lock, modal and fresh reload processes exited with code 0; their private desktop objects were removed |

The planned lock duration was 120 seconds. The actual measured lock interval was 154.10 seconds. The report uses the measured interval. No lock or unlock action was automated, and no secure-desktop windows were enumerated or captured.

The duration run sampled process and desktop state 4,372 times. It recorded no Editor frame on the observable Default desktop. Unavailable input-desktop observations during lock remain unknown containment observations; they do not establish either escape or isolation. Private PID, executable hash, scene identity, and request receipts were checked separately.

## Reported Windows unlock problem

The recorded unlock symptom was an error sound without the expected credential UI when the login screen was activated. Ctrl+Alt+Delete restored the screen. This report changes the operational assessment: the trial does not establish an unobstructed interactive unlock. It establishes only that WTS reported an unlock transition and that the controller subsequently completed private-desktop commands.

The private-desktop logs did not capture the login screen, input attempts, error sound or secure-desktop focus. They cannot confirm or exclude a relationship with the Editor, its private desktop, the controller or another component. During the lock, Editor-owned window inventories did not identify a native Error dialog. This observation does not cover the login UI. The background-only handle investigation did not repeat the lock trial.

The deliberately blocked I3D belonged to a separate fault-injection experiment. WTS reported unlock at 09:18:52.186 Europe/Amsterdam; the modal-case Editor started at 09:20:31.414, about 99.23 seconds later. Its exclusive file lock did not overlap the Windows lock. Releasing a workstation lock and releasing an exclusive I3D file handle are different operations.

The later [unlock investigation](unlock-investigation.md) adds the pre-credential clarification, retrospective LockApp identity match and time-filtered Windows events. It does not establish a cause.

## Native Save error and recovery

A host process exclusively opened the disposable I3D. A second open returned sharing violation 32, proving the fault was active. Native Save command 6001 did not return within its 3-second message timeout and reported Win32 error 1460. The Editor main frame was disabled by its owned Error dialog. A private-window `PrintWindow` capture showed `Error while saving i3d file` with an OK button.

The controller verified PID, private desktop, main-frame owner, dialog title, button caption and button identity before sending the confirmation command. An initial permit with a mistyped numeric window handle was rejected. No blind dismissal occurred. The test released the exclusive lock; the on-disk scene hash was unchanged by the failed Save. After confirmation, a new explicit Save completed in 12.88 ms and Lua inspection succeeded. The final scene was changed again and saved, then verified through a fresh Editor process.

The original top-level class-name buffer was too large and returned empty class strings. The instrument now uses a 256-character class buffer. Dialog child controls already used that size and identified the OK button. The original captured result therefore proves PID, owner, title and button matching, with an empty top-level class observation. It does not prove that a nonempty class was matched in that first trial.

A Save message timeout is an uncertain outcome, not proof of cancellation. A bridge must inspect owned dialogs and verify disk state before retrying. The research controller was subsequently tightened to exit nonzero for a failed native dispatch while preserving its uncertainty JSON. The original trial used its earlier exit-0-on-timeout revision; the harness and analysis inspected `returned:false` explicitly.

## Lua errors and update loop

A caught Lua error produced an error receipt. An uncaught Lua error produced no response receipt, while the next inspection succeeded. Loading an intentionally missing I3D returned node 0 and the following inspection also succeeded. Neither control prevented later rendering, Save or clean exit. These tests cover the chosen failures only, not every possible native crash or modal dialog.

The first duration instrument had an invalid callback counter, so its zero heartbeat does not prove a paused update loop. A separate explicit `startUpdateLoop` trial recorded 648 callbacks before `stopUpdateLoop`. Physics also ran: the vehicle y coordinate fell to about -582.93. The test stopped simulation, reset the expected translation, saved and verified it in a fresh process. A future control protocol must distinguish static editing from simulation and must not enable this loop merely to get a heartbeat.

## Watching the editor

Native Lua viewport capture produced fresh 512 by 512 PNG images on the inactive desktop, including during the lock. A normal image viewer on the user's desktop can display completed images with their request number and timestamp. This scene observation does not require switching desktops.

`PrintWindow` captured the native Error dialog and the Editor's UI panels. The main Vulkan viewport was white in the full-window snapshot. Use native scene PNGs for scene review and bounded private-window snapshots for UI diagnostics. Neither image should be labelled live without a fresh receipt and timestamp.

This private Win32 desktop is separate from Windows Task View virtual desktops. Win+Tab and Ctrl+Win+Arrow do not select it. Interactive viewing requires a helper that calls `SwitchDesktop` with appropriate rights and guarantees a separate way back. That switch would visibly replace the user's input desktop. No interactive switch was performed in these trials. A bounded switch-and-return test remains separate work requiring advance notice.

## Resource boundary

The duration trial is not proof of constant resource use. After warmup, handles ranged from 1,079 to 1,112; the final steady window ranged from 1,512 to 1,547. That window excludes the last 10 seconds to avoid treating teardown as recovery. Private usage moved from approximately 1.172 to 1.180 GB after warmup to approximately 1.185 GB in the final steady window. Nearest-sample operation correlations do not identify a cause. A fresh focused run observed stage-end handle counts of 1,029 after 20 seconds idle, 1,119 after 100 inspections, 1,253 after 20 Saves, 1,289 after 30 renders and 1,285 after 20 more idle seconds. Private usage at those boundaries was about 1.190, 1.157, 1.177, 1.188 and 1.187 GB. The sequential stages confound operation type, startup and elapsed time. They establish retained growth within the process, without identifying a leak or its cause. Do not extrapolate this 15-minute run to days of operation.

The normal user configuration retained its original SHA256 `31720002d6f6639a6d340ff4d7bb4e558f5ccd1001209c169d1f79f3345871cf`.

The later [handle investigation](handle-growth-results.md) classified the growth and tested minimizing the window within the private desktop.

## Evidence and reproduction

Derived machine-readable facts are in [the metadata](desktop-operational-results.metadata.json). The instruments are [launcher](../07-instruments/desktop_endurance_probe.py), [Lua bridge](../07-instruments/desktop_endurance_probe.lua), [controller](../07-instruments/desktop_research_controller.py) and [analyzer](../07-instruments/analyze_desktop_endurance.py). Windows contracts and observer alternatives are in [observation research](desktop-observation-research.md); fault candidates are in [modal research](modal-probe-design.md).

Raw copied assets, PNGs, launch configurations, request receipts, operation logs and telemetry remain ignored under `.docs/giants-editor-desktop/endurance/`. Cases are `longrun`, `lock-only`, `modal` and `reload-*`. The launcher requires a fresh case directory with `spec.json`, a dedicated `editor.xml`, copied `asset` and isolated `scripts` before launch. It snapshots input Lua/configuration, pins the executable hash, creates a unique private desktop, assigns the Editor to a kill-on-close job, and caps duration.

For repetition, prepare a fresh copied fixture, run `desktop_endurance_probe.py --case <case> --duration-seconds <cap>`, then call the controller with that case and increasing request sequences. Inspect receipts and native return status. A controller exit alone is insufficient persistence evidence. Finish with Save, quit and fresh-process reload, then analyze the raw case with `analyze_desktop_endurance.py --case <directory> --output <analysis.json>`.

The real lock case used a human readiness confirmation followed by a separate start signal. Its explicit permit bound the session hash, PID and private desktop to a 90-second active maximum; the orchestrator stopped at 65 seconds. This is a bounded research permission, not a proposed universal MCP time limit. No RDP disconnect, sleep, GPU reset, logoff, multi-hour run or exhaustive native-dialog catalog was tested.

## Archive context

This report records the 2026-10-16/17 research against the pinned Editor build. Raw assets, screenshots, configurations and machine logs referenced under `.docs/` are local-only and are not distributed. Reproduction commands retain their historical workspace assumptions; read the [instrument index](../07-instruments/README.md) before adapting or running them.
