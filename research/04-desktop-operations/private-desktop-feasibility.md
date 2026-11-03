# Private Win32 desktop feasibility for GIANTS Editor

Date: 2026-10-17. This design-research note starts no process, creates no desktop, switches no desktop, and sends no window message.

## Question and scope

Can a controller launch GIANTS Editor on a separate non-input Win32 desktop in the current interactive window station (`WinSta0`) so its windows cannot appear on the user's active desktop, while retaining the existing native-menu and Lua-file bridge?

This note covers documented Win32 desktop and process-connection rules, access rights, control messages, and Vulkan WSI limits. It does not claim that the target Editor, graphics driver, or compositor will render successfully on an inactive desktop. That needs the bounded runtime test below.

## Findings

### A private Win32 desktop fits the containment boundary

A Win32 desktop is a securable object within a window station. It has a logical display surface and holds windows, menus, and hooks. `CreateDesktopW` creates a desktop in the caller's current window station and assigns it to the calling thread. It requires `DESKTOP_CREATEWINDOW`, because the API internally creates a window. With a null security-attributes argument, the new desktop receives the parent window station's default security descriptor. [About window stations and desktops](https://learn.microsoft.com/en-us/windows/win32/winstation/about-window-stations-and-desktops) and [CreateDesktopW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-createdesktopw).

For a current-user controller already associated with interactive `WinSta0`, a new named desktop can use the default DACL. No ACL modification, Winlogon desktop, service account, Session 0, or new window station is needed. This is an implementation choice based on the documented default-DACL rule, not proof that every local security policy grants creation rights. Creation must fail closed when it does not.

`SwitchDesktop` makes a desktop visible and able to receive user input. It requires `DESKTOP_SWITCHDESKTOP`. The controller must never call it. [SwitchDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-switchdesktop).

This is ordinary-process containment, not a security sandbox against the launched Editor. A process with an eligible desktop handle and `DESKTOP_SWITCHDESKTOP` can theoretically call `SwitchDesktop`. Avoiding that call does not prove that unrelated code will never make one. Keep handles non-inheritable and request the smallest useful access mask.

### Bind the launched process by `STARTUPINFO.lpDesktop`

`STARTUPINFO.lpDesktop` names the desktop, or the window-station and desktop together. After process connection to a window station, desktop selection prefers an explicit `SetThreadDesktop`, then an inherited desktop, then the `lpDesktop` name, and otherwise the station default. If multiple desktop handles are inherited, selection is undefined. [STARTUPINFOW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/ns-processthreadsapi-startupinfow) and [Thread connection to a desktop](https://learn.microsoft.com/en-us/windows/win32/winstation/thread-connection-to-a-desktop).

Call `CreateProcessW` with `bInheritHandles=FALSE`, a fully qualified executable path, and `STARTUPINFOW.lpDesktop` equal to the private desktop name. This avoids inherited desktop handles and selects the child desktop by name. `CreateProcessW` runs the child in the caller's security context. [CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw).

Use a dedicated helper process, not the controller's UI thread. The helper owns no window or hook when it attaches to a desktop. Read-only USER32 observations before creation are permitted; they do not create controller windows. `CreateDesktopW` assigns its caller thread to the new desktop. If a thread must move, call `SetThreadDesktop` before it owns a window or hook. Microsoft documents that it fails after either exists. [SetThreadDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setthreaddesktop).

### Observe, rather than activate, the desktop

`OpenInputDesktop` returns the desktop that receives user input. Open it with a non-inheritable handle and use its name as the before/after input-desktop identity. [OpenInputDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-openinputdesktop).

`GetThreadDesktop` retrieves a target thread's desktop. `EnumDesktopWindows` enumerates top-level windows on a supplied desktop and requires `DESKTOP_READOBJECTS`. This can establish that the verified Editor frame exists on the private desktop and that no Editor-PID window exists on the input desktop. Enumeration is evidence, not a launch-isolation requirement. [GetThreadDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getthreaddesktop) and [EnumDesktopWindows](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumdesktopwindows).

For creation and enumeration, use `DESKTOP_CREATEWINDOW | DESKTOP_READOBJECTS`. Do not request activation, hooks, journaling, DACL, or owner rights. Microsoft documents these rights separately. [Desktop security and access rights](https://learn.microsoft.com/en-us/windows/win32/winstation/desktop-security-and-access-rights).

The assertion "no window showed on the active desktop" needs these samples: unchanged input-desktop name, unchanged foreground HWND and owning PID, expected Editor frame on the private desktop, and no Editor-PID window on the input desktop. Samples cannot prove that a transient visual effect never occurred between them. Record that limit.

### Reuse the existing bridge only after private-frame discovery

The current bridge invokes a verified Editor menu command with `SendMessageTimeoutW(..., WM_COMMAND, ...)`, then treats its XML/Lua receipt and persisted scene as completion evidence. It must discover the private desktop's exact Editor main frame after launch and must not broadcast.

`SendMessageTimeoutW` invokes the receiving window procedure and may wait until it finishes. A zero result covers failure or timeout and the API does not always set a last error. `SMTO_ABORTIFHUNG` and a bounded timeout bound the host wait, but cannot cancel a command already being handled. [SendMessageTimeoutW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendmessagetimeoutw).

The normal controller should open the private desktop for observation, enumerate its frame, verify the existing executable hash, PID, title, document and enabled menu item, then send the bounded `WM_COMMAND`. Retain the established one-request-at-a-time, receipt correlation, no-blind-retry, and fresh-load persistence checks from [Runtime results](../02-lua-and-save/live-results.md). The documented APIs do not promise that every cross-desktop menu command works for every application.

### Vulkan presentation on the inactive desktop is an experimental gate

Vulkan's Win32 WSI extension requires a valid `HWND` and `HINSTANCE` for a Win32 surface. The application must query presentation support for its actual surface and queue family. Win32 WSI also requires an active message pump. Swapchain creation, acquire and present may invoke `SendMessage`, and a missing pump may deadlock. [Vulkan Win32 platform WSI](https://docs.vulkan.org/spec/latest/chapters/VK_KHR_surface/wsi.html#_win32_platform) and [surface support](https://docs.vulkan.org/spec/latest/chapters/VK_KHR_surface/wsi.html#vkGetPhysicalDeviceSurfaceSupportKHR).

The Vulkan specification does not say that a window must be on the input-active Win32 desktop. It also does not guarantee successful presentation, composition, or survival after the desktop becomes inactive. This is an inference from the specified requirements, not a Vulkan statement. Require target-machine success through surface creation, per-surface support, non-zero extent, swapchain create/acquire/present, native Save, and fresh-load verification while the desktop remains inactive. Treat `VK_ERROR_SURFACE_LOST_KHR`, a zero extent, a hung request, or a missing receipt as a failed gate. [Vulkan surface loss](https://docs.vulkan.org/spec/latest/chapters/VK_KHR_surface/wsi.html#_wsi_surface).

### This is neither virtual desktops nor headless execution

Windows virtual desktops group top-level windows. When one is hidden, its windows are hidden, and Microsoft tells applications to put new windows on the currently active virtual desktop. That mechanism does not bind a process to a separate Win32 desktop. [IVirtualDesktopManager](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nn-shobjidl_core-ivirtualdesktopmanager).

The proposal uses an actual Win32 desktop within `WinSta0`. It still launches a normal GUI process and needs the Editor GUI and render loop. It is neither a Windows virtual desktop nor true headless mode. The pinned build's startup research found no supported headless launch mode. [Static startup and headless controls](../03-startup-and-headless/startup-flags.md).

## Smallest controlled test

Notify the user before the test. Containment failure may show a window. Use one exact hash-pinned `editor.exe`, an isolated configuration and script directory, and a copied disposable one-node I3D fixture. Leave normal Editor configuration and installed assets untouched.

1. Record the input-desktop name through `OpenInputDesktop` and `GetUserObjectInformation`, the foreground HWND, its PID, and title.
2. In a fresh helper process, create a unique private desktop in `WinSta0` with null security attributes, a non-inheritable handle, and `DESKTOP_CREATEWINDOW | DESKTOP_READOBJECTS`. Do not call `SwitchDesktop`.
3. Use `CreateProcessW` with no inherited handles and `lpDesktop` set to that desktop. Launch the exact Editor executable with the established dedicated config, fixture, and native bridge.
4. Poll only the private desktop with `EnumDesktopWindows` until one verified Editor frame matches expected PID, executable hash, title, document, and script menu entry. On timeout, terminate Editor and wait for it.
5. Re-record input-desktop and foreground identity. Enumerate the input desktop for Editor-PID windows. Send one allowlisted inspect request through the private frame. Require its correlated XML response, then native Save and a fresh read-only load.
6. Repeat the input-desktop and foreground checks after dispatch and at exit. Retain the private-desktop name, expected frame HWND/PID, result files, exit status, and all samples.
7. Close process and thread handles. Terminate a timed-out Editor, wait, then close the helper desktop handle. `CloseDesktop` fails while a calling-process thread uses the handle, so helper lifetime and handle ownership must be explicit. [CloseDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-closedesktop).

Success is narrow. The target fixture loaded, one command and one Save completed with correlated receipts and fresh-load persistence, every recorded input-desktop and foreground identity was unchanged, and no Editor-PID window was found on the input desktop. It does not establish GPU correctness beyond the observed machine/run, permanent absence of visual artifacts, or a security sandbox against Editor.

## Sources and limits

Microsoft links above are official API documentation. Vulkan links are the current Khronos specification. They document API contracts, not GIANTS Editor behavior. This note is current on 2026-10-17. Recheck it if the Windows contract, GPU driver, Editor build, or bridge changes.

## Runtime follow-up

The later [private-desktop runtime trials](../03-startup-and-headless/invisible-startup-results.md) passed invisible startup, native Save, fresh-load readback and rendering for the pinned build. This finding uses normal GUI initialization on an inactive Win32 desktop. It does not establish a hidden-window startup switch or true windowless execution.

## Archive context

This report records the 2026-10-16/17 research against the pinned Editor build. Raw assets, screenshots, configurations and machine logs referenced under `.docs/` are local-only and are not distributed. Reproduction commands retain their historical workspace assumptions; read the [instrument index](../07-instruments/README.md) before adapting or running them.
