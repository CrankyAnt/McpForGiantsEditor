# Windows unlock investigation

Date: 2026-10-17. This phase inspected retained evidence, source code, current component identity and existing Windows events. It performed no new lock, Editor launch, private-desktop creation, visible UI operation or settings change.

## Result

The reported failure occurred before the credential field appeared. Ctrl+Alt+Delete made that screen visible. This bounds the user-reported failure to the period before credential entry. It does not identify the active frontend at the exact failure moment, the failed transition, or its cause.

The recorded accessible foreground during the locked interval belonged to the same still-running, Microsoft-signed `LockApp.exe` instance in the same Windows session. The Editor's private window was not observed on that input desktop. The last 89.07 seconds before WTS unlock contained no Editor commands, although private-window and input-desktop polling continued. Existing logs then recorded a Windows Hello logon and Winlogon notifications before the controller resumed its commands.

The results do not fit the later deliberate I3D file lock or the post-unlock command restart as explanations of the reported pre-credential blockage. They do not exclude an earlier effect of the private Editor, its graphics state, the observer, or an unrelated Windows frontend problem. No causal reproduction or verified fix exists yet.

## Retained timeline

Times below are Europe/Amsterdam on 2026-10-17, UTC+02:00. The exact keypress and error-sound times were not captured.

| Time | Evidence |
| --- | --- |
| 09:16:18.031 to .035 | Winlogon subscriber handling notifications, Event IDs 811/812, payload Event=4 |
| 09:16:18.083 | Controller first recorded WTS locked |
| 09:16:18.662 onward | Accessible Default-desktop foreground samples mapped to LockApp |
| 09:17:23.116 | Active locked Editor work ended, 65.03 seconds after lock detection |
| 09:18:49.398 | Last retained accessible LockApp foreground sample before the late access discontinuity |
| 09:18:49.600 | First late OpenInputDesktop access-denied observation |
| 09:18:51.900 | HelloForBusiness event 5002 |
| 09:18:52.068 | HelloForBusiness event 5001, plus Winlogon 811/812 payload Event=5 |
| 09:18:52.186 | Controller first recorded WTS unlocked |
| 09:18:52.376 | First post-unlock native command reply, about 190 ms after the WTS observation |
| 09:20:31.414 | Separate deliberate I3D Save-fault Editor started |

The installed HelloForBusiness provider definition describes event 5001 as a successful user logon and 5002 as a logon gesture event. The audit retained only IDs and timing for these records, not identity, gesture, credential or SID fields. The installed Winlogon provider definition identifies 811 as subscriber handling start and 812 as handling completion; its public event template names only `Event` and `SubscriberName`. The numbers 4/5 are preserved as payload values without asserting a public semantic mapping. They are not interpreted as `WM_WTSSESSION_CHANGE` constants.

The short access-denied interval is compatible with movement to a protected input desktop. It does not establish the identity of that desktop or when Ctrl+Alt+Delete was pressed. `OpenInputDesktop` reports access to the input desktop, not the visible state of the credential UI. [Microsoft API contract](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-openinputdesktop).

## Foreground identity and source integrity

The historical foreground PID still existed during this investigation. Its process start time was 16 October 2026 at 07:44:14.0089842 CEST, before the trial, so it was not a PID reused after the trial. The current process name, Session ID, executable path and valid Microsoft signature identified LockApp. Its file version was `10.0.26100.9549`. This is a retrospective process-identity match, not a contemporaneous screenshot or a record of which credential control held focus. Raw PIDs, HWNDs and identity fields are omitted from the durable metadata.

The original launcher can be reconstructed exactly by restoring its old class-name buffer length. Its SHA256 matches the run's recorded `001945acbabe5c18c14815c783a458e48b87a52ec90035376b9c6de7cc7be21e`. The retained input Lua matches `7a84a4416319d43f4082c07a599e231c95277f6c199ed68891231905e4de8260`. Both sources were inspected. The original run did not retain a controller source hash; current-controller inspection does not remove that provenance gap.

The audited paths create the private desktop, restore the controller thread's original desktop, and send commands only to the verified private Editor frame. No `SwitchDesktop`, `SetForegroundWindow`, `ShowWindow`, `AttachThreadInput` or input-hook installation was found in the verified launcher or inspected controller paths. Opened desktop handles are closed, while borrowed thread-desktop handles are restored rather than closed. Creating or assigning a thread's desktop is distinct from changing the input desktop. [CreateDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-createdesktopw), [SetThreadDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setthreaddesktop).

That source review does not certify every internal operation of the closed-source Editor, driver, Windows shell or other processes.

## Activity and resources near unlock

No Editor command was dispatched between active-work completion and WTS unlock, an interval of 89.070 seconds. During that interval, sampled process handles ranged from 1,071 to 1,083, working set from 379,600,896 to 379,678,720 bytes, and private usage from 1,188,425,728 to 1,188,581,376 bytes. These per-process measurements do not show a sharp resource climb at that point. They do not measure global GPU or compositor pressure and cannot exclude a graphics interaction.

The observer continued sampling every approximately 0.2 seconds, including `OpenInputDesktop`, Default-desktop enumeration restricted to checking for Editor-owned windows, foreground PID lookup, and the private Editor's window inventory. Stopping Editor commands therefore did not stop all probe activity. A future control must separate observer activity from Editor presence.

The first post-unlock request was inspection, followed by rendering and Save. The recorded symptom places the blockage before credential entry, and the independent Hello logon record precedes the WTS-unlock observation and resumed request. This sequence does not support attributing the reported earlier pre-credential blockage to that burst. The exact relation to input events was not captured, and this does not establish that immediate resumption is a good future operating policy.

## Existing Windows logs and build

The final event audit used server-side UTC time filtering for 07:15:00 through 07:21:00Z, with a 2,000-event cap per channel. No channel hit the cap. Winlogon supplied eight informational records and HelloForBusiness supplied two. System, Application and the other available targeted channels returned no matching records in that interval. This supplies no matching recorded crash, display reset or application-hang event in the queried channels; it does not rule out an unlogged UI or graphics problem.

The Security log was access-restricted. Its 4800/4801 records could not be checked with the current token. No administrative consent prompt was opened. Several requested provider patterns had no matching channel, while some found channels were disabled; these states remain distinct in the metadata. No channel was enabled or cleared. The final findings use the corrected time-filtered audit, superseding an initial latest-500 survey.

The machine reported build `26300.9711`, DisplayVersion `26H2`. Microsoft identifies this build as Windows 11 26H2 in KB5127648. The reviewed release notes and release-health information did not identify a matching lock-frontend activation/error-sound issue. An Explorer problem after sign-in described there has a different symptom boundary. This negative source search does not exclude a Windows defect. No updates or driver changes were applied. [Exact build release notes](https://support.microsoft.com/en-us/servicing/os/windows-11/2026/10/kb5127648-windows-11-24h2-25h2-26h2-security-update), [26H2 release health](https://learn.microsoft.com/en-us/windows/release-health/status-windows-11-26h2).

Only two named Ctrl+Alt+Delete values were read: `Policies/System/DisableCAD` was absent, and the legacy `Winlogon/DisableCAD` value was 1. No precedence between these locations or historical effective policy was established. These reads are not a basis for a registry fix. The public policy describes requiring secure attention before logon, not diagnosis of a blocked lock frontend. [Microsoft policy contract](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/security-policy-settings/interactive-logon-do-not-require-ctrl-alt-del).

## Controlled follow-up, not executed

A causal next step needs a human lock/unlock comparison. The first proposed trial is ordinary Windows with no Editor, no test-created private desktop and no running desktop/input observer. Its outcome is whether normal activation exposes the credential field without an error sound. Existing Windows events can be read afterward. One clean attempt does not rule out an intermittent Windows problem.

Only if a comparison is needed after that baseline should the factors be added separately: observer-only, an empty private desktop, a minimized idle Editor with observer stopped, then active commands. Do not combine all factors in the first repeat. Each step needs advance notice and the user's readiness confirmation. Stop after an unexpected unlock problem, retain the user's description, and use the already demonstrated manual Ctrl+Alt+Delete recovery if needed. Do not restart LockApp/LogonUI or alter authentication policy as part of that test.

Any future lock trial needs advance coordination and a bounded active-work interval. The baseline proposed here has no active test work while locked.

Until that comparison exists, the private-desktop route has an unresolved interactive-unlock limitation. Minimized handle stability from the separate research does not validate unlock behavior. A future bridge should suspend active work on lock, avoid inspecting credential UI, and wait for a verified user-desktop state before resuming. These are proposed conservative boundaries, not a tested fix for this incident. Windows documents session unlock and desktop-ready as distinct notification values. [WTS notifications](https://learn.microsoft.com/en-us/windows/win32/termserv/wm-wtssession-change).

## Evidence and validation boundary

[Derived metadata](unlock-investigation.metadata.json) records the timeline, safe event fields, coverage and source hashes. Retained evidence is under ignored `.docs/giants-editor-desktop/unlock-events/` and `unlock-audit/`. No login screenshots, keypress capture or audio recording was made. Credentials, usernames, SIDs and raw authentication messages were not extracted into retained evidence or committed.

This phase completed retrospective evidence checks. It did not create a pass/fail reproduction of the reported symptom, prove a cause, or test a fix. No further lock or visible operation was performed.

## Archive context

This report records the 2026-10-16/17 research against the pinned Editor build. Raw assets, screenshots, configurations and machine logs referenced under `.docs/` are local-only and are not distributed. Reproduction commands retain their historical workspace assumptions; read the [instrument index](../07-instruments/README.md) before adapting or running them.
