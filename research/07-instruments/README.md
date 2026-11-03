# Historical research instruments

These 32 files contain the historical research code. Thirty-one are retained byte-for-byte; `headless_runtime_probe.py` replaces one personal Python-installation path with `Path(sys.executable)`. This portability/privacy correction has passed syntax validation but has not been runtime-retested. They are not an MCP implementation. They share Python imports and sibling Lua/JavaScript files, so they stay in one directory; the index groups them by investigation.

## Execution boundaries

Do not run the instruments as a batch. Some start Editor, mutate disposable scenes, submit native Windows commands, attach diagnostic hooks or terminate an owned process. Reading source and checking syntax do not authorize a new Editor experiment. Announce visible startup or input-desktop control in advance and obtain the necessary task scope.

The scripts retain their original fixture-specific paths and defaults, including `C:\TMP` evidence roots and the pinned Editor installation. Six use `Path(__file__).resolve().parents[6]` for the former workspace: `analyze_replacement_results.py`, `fidelity_host.py`, `desktop_endurance_probe.py`, `headless_runtime_probe.py`, `practical_windows_probe.py` and `private_desktop_probe.py`. That root assumption does not fit this archive layout. Adapt it and inspect all launch/write paths before attempting reproduction. Reports retain historical command examples; those are evidence of the original invocation, not ready-to-run commands here.

The original raw receipts, copied scenes and isolated trial configurations were deliberately discarded after retention review. The derived metadata and these instruments preserve the documented method and outcome, but cannot regenerate the old analysis or re-audit its complete inputs. A new reproduction must prepare fresh disposable fixtures and configurations in an appropriate licensed Editor/game environment, adapt the historical paths and record new measurements. Syntax checks and the retained JSON do not repeat a runtime experiment.

Some analyzers require `pefile` and `capstone`; the diagnostic JavaScript uses Frida; host probes use Windows APIs. No dependency installation or runtime execution is performed by this archive. The fixture-specific code has not been converted into a portable product API. Apply the [design's executable and legal-assessment boundary](../01-design-input/mcp-design.md#executable-integrity-and-legal-assessment) before adopting a technique.

## Lua and Save

- [lua_registrations.py](lua_registrations.py)
- [native_save.py](native_save.py)
- [native_dispatch_menu.lua](native_dispatch_menu.lua)
- [runtime_readback.lua](runtime_readback.lua)
- [runtime_save_fixture.lua](runtime_save_fixture.lua)
- [windows_save_probe.py](windows_save_probe.py)
- [windows_script_probe.py](windows_script_probe.py)

## Startup and headless

- [analyze_headless_runtime.py](analyze_headless_runtime.py)
- [analyze_invisible_startup.py](analyze_invisible_startup.py)
- [headless_runtime_hooks.js](headless_runtime_hooks.js)
- [headless_runtime_probe.py](headless_runtime_probe.py)
- [invisible_startup_static.py](invisible_startup_static.py)
- [startup_flags.py](startup_flags.py)

## Desktop operations

- [analyze_desktop_endurance.py](analyze_desktop_endurance.py)
- [desktop_endurance_probe.lua](desktop_endurance_probe.lua)
- [desktop_endurance_probe.py](desktop_endurance_probe.py)
- [desktop_research_controller.py](desktop_research_controller.py)
- [editor_fence_trace.js](editor_fence_trace.js)
- [editor_handle_types.py](editor_handle_types.py)
- [private_desktop_probe.py](private_desktop_probe.py)
- [test_editor_handle_observers.py](test_editor_handle_observers.py)
- [trace_editor_fences.py](trace_editor_fences.py)

## Asset fidelity

- [analyze_fidelity.py](analyze_fidelity.py)
- [analyze_practical_results.py](analyze_practical_results.py)
- [analyze_replacement_results.py](analyze_replacement_results.py)
- [fidelity_host.py](fidelity_host.py)
- [fidelity_scene_probe.lua](fidelity_scene_probe.lua)
- [gate_keyframes.py](gate_keyframes.py)
- [practical_scene_probe.lua](practical_scene_probe.lua)
- [practical_windows_probe.py](practical_windows_probe.py)
- [replacement_research.py](replacement_research.py)
- [replacement_scene_probe.lua](replacement_scene_probe.lua)

[Return to the research entry point](../../README.md).
