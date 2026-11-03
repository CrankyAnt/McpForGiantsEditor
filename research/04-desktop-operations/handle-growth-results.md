# Renderer handle growth research

Date: 2026-10-17. Target: GIANTS Editor 10.0.14.0 on the current Windows installation. This phase used copied assets, dedicated configuration and inactive private Win32 desktops. It did not switch the visible desktop, inject input, change drivers or repeat the Windows-lock test. This is research only.

## Finding

The growing kernel-handle count is reproducible. The A/B inspection batches increased the total exclusively through Event handles. A separate bounded native trace linked 47 Event creations to 47 Vulkan-fence creations. Normal window state on an inactive private desktop permits growth during command traffic. Minimizing the Editor within that same inactive desktop removed the measured linear growth from the inspection batches while Lua editing, native Save and native PNG capture continued to work. A broader minimized test added one Event during 30 PNG renders.

The matched within-process test is the strongest control:

| Phase | Native inspections | Event count before | Event count after | Change |
| --- | ---: | ---: | ---: | ---: |
| A, normal window | 200 | 302 | 483 | +181 |
| B, minimized | 200 | 483 | 483 | 0 |
| C, normal window | 200 | 490 | 688 | +198 |
| D, minimized | 200 | 688 | 688 | 0 |

The small changes between stages came from changing window state and settling. Each comparison uses its own before/after snapshots. Minimization stopped the per-inspection growth in those batches but did not reclaim the already retained Events. This was an inactive desktop throughout, so "normal window" does not mean a visible window on the user's desktop.

## Differential tests

| Control | Observation |
| --- | --- |
| Fresh controller per command | Two blocks of 200 inspections added 199 and 195 Events |
| One persistent controller | 500 WM_NULL messages added 477 Events without Lua dispatch; subsequent inspection blocks also grew |
| Explicit Lua garbage collection | Did not reclaim the accumulated Events |
| Idle after normal-window activity | Growth remained after 60 seconds without commands |
| Minimized process | 500 WM_NULL messages, 2,400 inspections and 30 Saves added no Events; 30 PNG renders added one Event |
| Same-process A/B/A/B | Growth returned after restoring the private window and stopped after minimizing again |

All completed short cases exited with code 0 and removed their private desktop objects. The tests did not close arbitrary handles or patch the Editor's behavior. They changed only the state of owned disposable windows within an inactive desktop and sent the already verified native commands.

## Fifteen-minute minimized run

The completed run lasted 901.35 seconds from controller start through cleanup. It produced 5,295 valid script responses and 29 Save receipts. That included 5,133 inspections, 133 mutations, 28 native PNG renders and a clean quit. The first 5,000 inspections ran as a burst; the remaining work ran periodically until the 15-minute boundary. Every script sequence, scene identity and expected translation was checked, and all 28 PNGs decoded at 512 by 512.

| Point | Total handles | Event handles |
| --- | ---: | ---: |
| After 30-second warmup | 1,017 | 302 |
| After 5,000 inspections | 1,017 | 302 |
| Final saved state, before quit | 994 | 295 |

This run showed no increasing handle pattern. Background worker cleanup explains some changes in other types; a declining final total is not proof that every internal resource is leak-free. Initial minimization was checked, and the controller never requested restoration. The retained telemetry did not contain a continuous `IsIconic` field, so future batches should check that state explicitly.

A new Editor process loaded the saved final target translation `5.294,-1.5,2.125` within 1e-5, captured a valid PNG and exited with code 0. Both the original and reload private desktop objects were removed. This is the persistence evidence behind the long-run result; message return status alone was not treated as proof of disk contents.

## Native allocation evidence

The first `NtCreateEvent` trace located the allocation path at `KERNELBASE.dll`, `nvoglv64.dll` and `editor.exe`. Further tracing identified the indirect call at Editor RVA `0x43e708`, returning at `0x43e70a`. The function pointer at RVA `0x27037d0` exactly matched a named `vkCreateFence` lookup using the observed valid Vulkan device. This is a checked API identity, not a name guessed from the NVIDIA module.

The cumulative `handles-fence-submit1` trace recorded 47 successful `vkCreateFence` calls and 47 Event creations nested inside those calls. It recorded no destruction of those newly created fences through the monitored `vkDestroyFence` entry point and no matching successful `NtClose` before observation ended. A `VkFence` is a Vulkan synchronization object created and destroyed through those APIs. [Khronos create](https://docs.vulkan.org/refpages/latest/refpages/source/vkCreateFence.html), [destroy](https://docs.vulkan.org/refpages/latest/refpages/source/vkDestroyFence.html).

The trace also observed successful queue submission, acquisition and presentation calls. Fence-status queries returned both signaled and unsignaled states, and waits returned both success and timeout. Those status values alone are not evidence of a device fault. Only 8 of the 47 new fences appeared in the monitored queue-submit calls; the others were not observed there. The monitored modern submit aliases produced no additional calls. This is bounded lifecycle evidence, not a complete reconstruction of every fence owner or queue operation. [Fence status contract](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetFenceStatus.html).

Frida installed temporary in-process observation hooks and affected timing and temporary resource counts. The A/B comparisons and the long run did not use Frida. Their handle totals are independent of those native traces. No Editor or driver binary file was changed, and no API result was replaced.

The allocation takes place through the NVIDIA module, but the evidence does not assign a defect to NVIDIA or GIANTS. It also does not prove that the retained objects are permanently leaked under every presentation state. It does establish that this normal-window private-desktop route does not recycle them within the tested command sequences and idle periods. The minimized counterfactual removed the per-inspection growth in the measured batches without changing the driver or Editor binary.

The native observer retained 47 fence-linked Events through the end of its short observation. It was not a lifetime-to-process-exit trace.

The active NVIDIA module was `nvoglv64.dll` version `32.0.16.1742`, SHA256 `adda6dc8054888d5c52e3f97cf33b742952d16b3f145ced74cfb1012556bd696`, on a system containing an NVIDIA GeForce RTX 3070 Ti and Intel UHD Graphics 770. No alternate GPU, driver version or Editor build was compared. The Editor SHA256 remains `c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`.

## Consequence for long-running control

Use a private desktop with the Editor explicitly minimized before sustained command traffic. Recheck `IsIconic` before a batch, since another operation or a later interactive viewer may restore the window. Native viewport PNGs remain the observation route while it is minimized. Merely moving an ordinary restored Editor window to an inactive desktop is insufficient on this tested stack.

Keep process-handle and memory measurements alongside command receipts. Restarting a process releases its retained handles, but this phase did not implement a restart policy or determine a universal safe threshold. A future restart must first establish completed disk persistence and fresh readback. Do not forcibly close driver or Vulkan handles as a workaround. Microsoft warns that closing arbitrary handles can destabilize an application or the system. [Sysinternals Handle](https://learn.microsoft.com/en-us/sysinternals/downloads/handle).

The normal-window result is a real obstacle to unbounded command traffic in that mode. The minimized result supplies a tested alternative for the measured duration and workload. It does not establish days of operation, a process exhaustion point, RDP behavior, GPU-reset recovery or an unobstructed Windows unlock.

## Windows unlock report and separate file-lock fault

The operator reported an error sound when activating Windows login after the earlier real lock trial; Ctrl+Alt+Delete restored the login screen. The earlier report now distinguishes WTS unlock plus successful controller commands from a trouble-free interactive unlock. The logs did not capture the login UI or its input/focus state. Neither the new handle traces nor the old private-window inventories establish a cause for that symptom.

The blocked I3D was deliberate fault injection in a separate experiment. WTS reported unlock at 09:18:52.186 Europe/Amsterdam. The modal-case Editor started at 09:20:31.414, about 99.23 seconds later. Its exclusive file-open control and Save error therefore did not overlap the workstation lock. [Corrected operational report](desktop-operational-results.md#reported-windows-unlock-problem).

Do not treat minimizing as a tested fix for the reported login problem. No further lock or unlock was requested or performed during this phase.

## Measurement integrity and reproduction

`GetProcessHandleCount` supplies a documented process total; Microsoft describes this as executive-object handles. These counts are distinct from a process's GDI or USER object quota. The read-only signed Microsoft Handle 5.0 tool supplied the type breakdown, using only `-nobanner -s -p <owned PID>`. [Microsoft count API](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesshandlecount), [Handle options](https://learn.microsoft.com/en-us/sysinternals/downloads/handle).

Handle sometimes prints several `<Unknown type>` rows. The initial ignored runners overwrote those duplicate dictionary keys. The reported Event rows and explicit totals were unaffected, but those old dictionaries are not valid type-total evidence. The final analysis reparses the retained text, sums every duplicate type and requires the normalized sum to equal the printed total. Unknown types retain that label; they are not reassigned by guesswork.

[Derived metadata](handle-growth-results.metadata.json) records normalized case stages, source hashes and lifecycle counts. Raw evidence remains ignored under `.docs/giants-editor-desktop/endurance/handles-*`, with test orchestration under `.docs/giants-editor-desktop/`. No raw vendor assets, binary copies or disassembly are committed.

The durable [type observer](../07-instruments/editor_handle_types.py) verifies the pinned Editor and Handle binaries, requires an already accepted Handle EULA and observes only the case's owned PID. The [fence observer](../07-instruments/trace_editor_fences.py) loads the [bounded native hooks](../07-instruments/editor_fence_trace.js) only after the same ownership checks. Run the Frida observer in a disposable helper process with an outer timeout; its 1-to-60-second sampling duration does not bound foreign attach or RPC internals. Native tracing was diagnostic, not required for normal control.

To repeat the differential, prepare fresh copied cases using the [existing launcher](../07-instruments/desktop_endurance_probe.py). Compare normal window state with `ShowWindowAsync(..., SW_SHOWMINNOACTIVE)` inside the private desktop, verify `IsIconic`, run identical inspection batches and snapshot types before and after. Use the read-only type observer with a fresh output filename. A trace can run simultaneously in another bounded helper while the existing controller dispatches the case's commands. Never switch the input desktop as part of this comparison.

## Archive context

This report records the 2026-10-16/17 research against the pinned Editor build. Raw assets, screenshots, configurations and machine logs referenced under `.docs/` are local-only and are not distributed. Reproduction commands retain their historical workspace assumptions; read the [instrument index](../07-instruments/README.md) before adapting or running them.
