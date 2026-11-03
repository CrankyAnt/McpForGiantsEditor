# Private desktop observation and locked-session research

Date: 2026-10-17. Target: GIANTS Editor 10.0.14.0, SHA256 `c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`.

## Question and scope

What observation can a user receive while the pinned Editor runs on its existing private Win32 desktop, including a workstation lock, an Editor modal dialog, and a long run? This note covers Windows contracts and the already retained native-Lua PNG result. It defines tests and decision boundaries. It does not launch the Editor, create or switch a desktop, lock a session, capture a window, or define an MCP implementation.

## Established context

The retained runtime trials started the pinned Editor on an inactive private desktop, kept the input desktop unchanged, and produced decodable native Lua PNGs. They also found a private Editor frame through explicit private-desktop enumeration. [Invisible startup runtime results](../03-startup-and-headless/invisible-startup-results.md). This is machine and build evidence. It does not prove observer behavior after a lock, a remote disconnect, a modal dialog, or across another GPU stack.

Windows calls the visible desktop that receives input the input desktop. A window station can contain several desktops, but only one is active. Windows restricts messages between processes to the same desktop. A private Editor window therefore remains a window on that desktop until a process switches the input desktop. [Desktops](https://learn.microsoft.com/en-us/windows/desktop/winstation/desktops).

This is distinct from Windows virtual desktops. Virtual desktops group top-level windows. They do not provide a separate Win32 desktop object, a separate USER message boundary, or the `STARTUPINFO.lpDesktop` process assignment used by the retained private-desktop route. See [Private Win32 desktop feasibility](private-desktop-feasibility.md) and [IVirtualDesktopManager](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nn-shobjidl_core-ivirtualdesktopmanager).

## Lock and secure-desktop boundary

### Facts

`LockWorkStation` displays the workstation lock UI. Windows applications that register with `WTSRegisterSessionNotification` receive `WM_WTSSESSION_CHANGE`. Its documented event values include `WTS_SESSION_LOCK`, `WTS_SESSION_UNLOCK`, console and remote disconnects, and `WTS_SESSION_DESKTOP_READY`. [Locking the workstation](https://learn.microsoft.com/en-us/windows/win32/shutdown/how-to-lock-the-workstation), [WTSRegisterSessionNotification](https://learn.microsoft.com/en-us/windows/win32/api/wtsapi32/nf-wtsapi32-wtsregistersessionnotification), and [WM_WTSSESSION_CHANGE](https://learn.microsoft.com/en-us/windows/win32/termserv/wm-wtssession-change).

`OpenInputDesktop` opens the desktop currently receiving input only when the caller has an input-capable associated window station and sufficient access. It can return `NULL`, with the extended error available through `GetLastError`. Desktop access checks apply to `OpenInputDesktop`. [OpenInputDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-openinputdesktop) and [Desktop security and access rights](https://learn.microsoft.com/en-us/windows/win32/winstation/desktop-security-and-access-rights).

Microsoft documents `Winlogon` as a default interactive-window-station desktop. Its security descriptor admits a restricted set of accounts. Ordinary applications generally cannot access it or switch another desktop while it is active. `SwitchDesktop` also documents access-denied failure for processes associated with a secured desktop such as Winlogon or ScreenSaver. [Desktops](https://learn.microsoft.com/en-us/windows/desktop/winstation/desktops) and [SwitchDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-switchdesktop).

`SwitchDesktop` makes a desktop visible and activates it for input. It requires `DESKTOP_SWITCHDESKTOP`. It does not promise a return to the previous input desktop. [SwitchDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-switchdesktop).

### Inference and operating rule

Treat a `WTS_SESSION_LOCK`, disconnect, or failed input-desktop read as an observation discontinuity. Pause dispatch and all live-capture attempts. Keep the Editor process private and do not switch its desktop. At `WTS_SESSION_UNLOCK` or `WTS_SESSION_DESKTOP_READY`, reacquire the input desktop and revalidate the private desktop, Editor PID, executable hash, expected frame, and outstanding receipt state before resuming.

This rule does not assume that `OpenInputDesktop` will always fail during lock. It handles both permitted and denied access without trying to open or interact with Winlogon. `ERROR_ACCESS_DENIED` is a useful recorded result when it occurs, not a reason to request more rights or retry against a secured desktop.

## Observer modes

### Mode A: native Lua viewport PNG

The existing native Lua route already rendered fresh PNGs while the Editor stayed on its private desktop. The observer reads a named PNG file and associated request receipt. It does not need the observer to own an Editor `HWND`, obtain a screen DC, capture the private desktop, activate the frame, or call `SwitchDesktop`. [Invisible startup runtime results](../03-startup-and-headless/invisible-startup-results.md).

This is the preferred long-run status view. It reports only the scene and camera that the allowlisted Lua request renders. It does not show native menus, file dialogs, crash dialogs, modal confirmations, or any other Editor chrome. A fresh PNG plus a correlated receipt can show that that render request completed. It cannot prove that no modal dialog is open after the request, and a missing PNG cannot distinguish a blocked Editor, GPU fault, missing render support, or a failed request without separate process and receipt evidence.

The user can watch this mode through a normal viewer outside the private desktop, for example a local status page or image viewer that refreshes only completed PNG files. The viewer stays on the user's active desktop. It is an observation route, not a control route.

### Mode B: private-dialog `PrintWindow` snapshot

`PrintWindow` asks the owner of a supplied `HWND` to render to a caller-supplied device context. The target processes `WM_PRINT`, or `WM_PRINTCLIENT` with `PW_CLIENTONLY`. Microsoft documents the call as synchronous and potentially blocking. [PrintWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-printwindow).

This makes a bounded snapshot probe plausible for a known top-level private-desktop dialog or Editor frame. It must run in a disposable observer worker with a timeout boundary outside that worker. The observer must first establish private-desktop membership and exact PID ownership. It must never enumerate or message the user's input desktop as a fallback.

`PrintWindow` is not a universal GPU-frame capture contract. The target window chooses how it handles `WM_PRINT`; a Vulkan canvas may return a black, stale, partial, or failed image even while it renders correctly on the private desktop. The prior native PNG result is the available safe scene-viewer route. A `PrintWindow` image can add UI diagnostics, but it cannot replace it.

Modal UI is the key limit. A modal dialog can block the Editor's normal message handling, while `PrintWindow` itself waits synchronously for target processing. Therefore a snapshot timeout or unchanged snapshot is evidence of unavailable UI observation, not proof that a particular dialog exists. The bounded probe should record the exact owned `HWND`, class, title, visibility, `IsWindowEnabled` state, pixel result, duration, and timeout result. It should show a last successful snapshot with its timestamp instead of presenting it as live.

### Why desktop `BitBlt` and Windows Graphics Capture are not the baseline

`GetDC(NULL)` and `GetWindowDC(NULL)` return the current screen or primary-monitor DC. `BitBlt` copies pixels between device contexts. Those APIs document pixel transfer, not capture of an inactive private desktop or a GPU-backed Editor canvas on it. `CAPTUREBLT` only includes layered windows above the source window. [GetDC](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getdc), [GetWindowDC](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowdc), and [BitBlt](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-bitblt).

Windows Graphics Capture can acquire frames from a user-selected display or application window. The documented picker uses secure system UI and Windows draws a yellow border around an actively captured item. `GraphicsCaptureSession.IsSupported` only answers whether screen capture is supported on that device. The documentation does not state that capture can attach to an inactive private Win32 desktop, a secured desktop, or an application HWND that the user cannot select. [Screen capture](https://learn.microsoft.com/en-us/windows/apps/develop/media-authoring-processing/screen-capture) and [GraphicsCaptureSession.IsSupported](https://learn.microsoft.com/en-us/uwp/api/windows.graphics.capture.graphicscapturesession.issupported).

Full live viewing of the private desktop therefore has unresolved dependencies: whether the capture API can create an item for the exact private `HWND`; its behavior while that desktop remains inactive; GPU and compositor output; session lock and disconnect behavior; and the required consent UI or visual indicator. Treat it as a separate, explicit experiment. It is not suitable as the default long-run observer.

## User-visible behavior and authorization

The default user-visible behavior should be a status record and the latest completed native PNG, both timestamped. During lock or unavailable observation, show "paused at lock/session boundary" and retain the last good image as historical evidence. After unlock, show "revalidating" until the identity and receipt checks pass.

Interactive private-desktop switching has a different impact. It changes the visible input desktop and can interrupt the user's work. It may also fail on a secured desktop and does not provide a documented automatic-return contract. Require a conspicuous notice that identifies the private desktop and states that input will move there. Obtain explicit authorization for each switch. Record the prior input-desktop identity, the switch result, the operator, and the observed restoration result. Do not offer automatic switching during a lock, disconnect, or alert condition.

## Bounded lock and observer test plan

Run only after a normal inactive-private-desktop launch has passed for the pinned build. Use a disposable fixture, dedicated Editor configuration, one owned process, an allowlisted read-only Lua PNG request, and a controller window registered for notifications in the current session. The user must know that the test will lock the workstation and must initiate or explicitly authorize that lock.

1. Before the run, record build hash, private desktop name, Editor PID, exact frame HWND, input-desktop identity, foreground HWND and PID, observer worker PID, PNG receipt correlation, and the WTS registration result.
2. Request one native PNG and one bounded `PrintWindow` snapshot. Record separate success, duration, output hash, and error fields. Do not use either result as a precondition for the other.
3. Record baseline status for a chosen duration with the private desktop inactive. The user may continue normal work. The controller must not switch desktops or synthesize input.
4. The user locks the workstation, or explicitly authorizes an already prepared lock action. On `WTS_SESSION_LOCK`, stop new Editor requests and snapshot attempts. Record the event timestamp and any `OpenInputDesktop` result with its immediate error code. Do not retry privileged access and do not inspect Winlogon.
5. Wait a fixed, recorded interval. Verify only owned-process liveness through non-UI process observation. Do not infer Editor health from lack of frames or lack of a snapshot while locked.
6. After the user unlocks, wait for `WTS_SESSION_UNLOCK` and, if received, `WTS_SESSION_DESKTOP_READY`. Reacquire the input desktop. Re-enumerate the known private desktop. Require the original Editor PID, executable hash, expected private frame, and no Editor-PID window on the input desktop before re-enabling work.
7. Submit one fresh native PNG request. Then take one bounded `PrintWindow` snapshot only if the pre-lock private-frame identity still matches. Compare request/receipt and snapshot timestamps. Do not claim pixel equality between those two methods.
8. Repeat the input-desktop and foreground samples, terminate only the owned Editor after the run, wait for exit, close observer resources, and retain the facts above plus every WTS event. Record gaps and unavailable fields explicitly.

Pass criteria are narrow. The process preserves its assigned private desktop across the tested lock interval, no Editor PID window appears on the input desktop in the recorded samples, the controller does not switch desktops, post-unlock revalidation succeeds, and a fresh native PNG receipt completes. A `PrintWindow` result is an independent capability result. It may be marked unavailable without invalidating the native PNG route.

Fail closed when an ownership check changes, the input desktop unexpectedly becomes the private desktop, a `SwitchDesktop` attempt is observed in controller telemetry, an Editor-PID window is found on the input desktop, or an uncorrelated receipt appears. Leave the process paused after an observer timeout until the user or a later bounded recovery procedure decides its disposal.

## Uncertainties

Windows documents session notifications and desktop access rules, but not the pinned Editor's behavior under a lock or across a remote disconnect. No current test establishes private-desktop graphics capture through GDI, `PrintWindow`, or Windows Graphics Capture. No current test establishes recovery from a real modal dialog. The native Lua PNG route remains the only retained viewer evidence for this Editor build and machine.

## Sources

All Windows claims above use Microsoft Learn pages linked next to the claim. The GIANTS Editor facts use the local retained results named in this report. Sources were checked on 2026-10-17. Recheck platform claims when the Windows version, graphics driver, Editor build, or controller design changes.

## Runtime-policy clarification

The pause-on-lock behavior proposed above is a conservative controller policy, not a Windows requirement that background Editor work must stop. A bounded experiment continued verified private-desktop operations during lock, without opening or inspecting the secure desktop. That experiment uses WTS session flags, a session-bound dispatch permit and a 90-second outer research window within the planned two-minute interval. Its active work stops earlier. These timing limits belong to this experiment and are not proposed MCP product limits.

The [operational runtime results](desktop-operational-results.md) distinguish actual lock observations from prepared but unexecuted tests. Future behavior should follow measured capabilities and explicit ownership of the private process. Missing input-desktop access is unavailable observation; it does not by itself establish that the private Editor stopped.

## Archive context

The original raw inputs were discarded; historical `.docs/` paths are no longer available. See [evidence availability](../../README.md#evidence-and-applicability) for the retained results and limits. Historical commands require new prepared data and reviewed paths; see the [instrument index](../07-instruments/README.md).
