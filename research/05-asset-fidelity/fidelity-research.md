# Keyframe and visual-fidelity investigation

Date: 2026-10-16. Status: preparation and controlled runtime/menu-Save tests completed. See [controlled fidelity results](fidelity-results.md) for the later live evidence and its limits. The preparation described below did not launch the Editor; the subsequent experiments did.

The original phase produced research only, with no MCP server or published skill.

## Offline finding

The trial's `sentinelGarage_gate_animation.i3d.anim` files allowed a bounded comparison of all 1,095 records across seven tracks. The original and previously native-saved file both parse to exactly 35,172 bytes with no unparsed tail. Track record counts are 118, 113, 111, 113, 112, 246 and 282.

After resolving serialized node IDs through each companion I3D, track targets match by scene path and name. The serialized IDs changed from 2-8 to 31-37. All record-time float bits and all observed flag words match. Each track begins at zero and ends at 10000. The first header word changed from 7 to 10. This reader does not assume a general format contract from that word.

In 1,045 records, one of the six stored float components changed numerically. Only component index 3, using zero-based indexing, changed; its largest absolute delta is `0.000041484832763671875`. The other five components are numerically equal. The units and interpolation semantics of these six fields have not been established by this decoder. No visual-error or angular-error claim follows from that scalar delta alone.

Derived evidence is in [keyframe-records.metadata.json](keyframe-records.metadata.json). The input files are the original scratch copy and the saved scratch copy retained from the [preceding practical phase](practical-results.md), not newly saved files. Therefore this finding does not establish what normal menu Save does.

## Reader boundary

[instruments/gate_keyframes.py](../07-instruments/gate_keyframes.py) is a read-only inspector for this known fixture. It accepts only leading words 7/10, one named character set, one named clip of duration 10000, seven tracks, flag-3 records and the observed padded ASCII strings. It validates companion-I3D target IDs, finite values, monotonic times, full time range and exact end of file. Unknown flags, headers or layouts are refusals. It does not infer a layout for arbitrary animation assets.

Reproduction from the research worktree, with an external Python cache:

```powershell
$env:PYTHONPYCACHEPREFIX = "$env:TEMP\repo-pycache"
python docs/research/skills/fs25-modding/giants-editor-mcp/instruments/gate_keyframes.py --before .docs/giants-editor-practical/animated-gate/baseline/asset/sentinelGarage_gate_animation.i3d.anim --before-scene .docs/giants-editor-practical/animated-gate/baseline/asset/sentinelGarage_gate_animation.i3d --after .docs/giants-editor-practical/animated-gate/asset/sentinelGarage_gate_animation.i3d.anim --after-scene .docs/giants-editor-practical/animated-gate/asset/sentinelGarage_gate_animation.i3d --output docs/research/skills/fs25-modding/giants-editor-mcp/keyframe-records.metadata.json
```

## Runtime sources and prepared probe

The installed Editor `scriptBinding.xml` declares `setAnimTrackTime(characterSetId, trackId, time, immediateUpdate)`. The installed game source uses enable, immediate seek and disable in `gameSource.zip!dataS/scripts/objects/AnimatedObject.lua` near lines 653-657 and `dataS/scripts/vehicles/specializations/AnimatedVehicle.lua` near lines 1803-1810. This supplies a source-backed pose-evaluation method without realtime playback. No keyframe/channel enumeration API was found in the inspected bindings.

[instruments/fidelity_scene_probe.lua](../07-instruments/fidelity_scene_probe.lua) is prepared, not live-validated. It deduplicates nonzero character-set handles and captures translation, quaternion, Euler rotation and scale with 17 significant digits. It also captures per-shape material albedo values. Sampling seeks 41 evenly spaced times per clip and records requested time, track time and changed-node count. Acceptance must reject an empty sample, unexpected clip/duration, missing frames, or a frozen animation that should move. Runtime quaternion comparison must account for equivalent `q` and `-q` representations.

The sampler restores local node poses and disables its track. It does not restore the full loop/speed/assignment state. All Save controls must therefore run before sampling, posing or camera changes, with a new process for subsequent readback. Do not Save after these observation commands.

An optional `render` command copies the call shape used by the installed `scripts/camera/saveBillboards.lua` near line 164. It requests a 512-by-512 PNG from `renderScreenshot`. That function is used in the bundled Lua but lacks a declaration in the inspected binding. Its use for these assets is unvalidated. Output existence alone will not count as a successful visual test: decode the image, reject an empty or blank image, verify framing and inspect it. If this route fails, capture the actual viewport through the computer-use skill.

## Prepared controlled comparison

Six isolated cases were prepared under ignored `.docs/giants-editor-fidelity/`, three for each of the water trailer and animated gate. Original installed file hashes cover 32 files. Each asset's baseline, native and manual cases have identical prepared I3D hashes and copied sidecars. They retain the earlier scratch-only texture-reference adjustment. Shared resources still resolve through the installed `$data` root.

[instruments/fidelity_host.py](../07-instruments/fidelity_host.py) enforces the initial-control/readback separation before native calls. Initial manual/native control processes accept only inspect and quit requests. Native Save refuses a fresh readback process or any recorded observation operation. Fresh launches require a successful Save receipt for the exact scratch document.

During preparation, a `VISIBLE-ACCESS-DEFERRED.txt` guard refused launch. An offline check confirmed that refusal before any case had a ready marker or launch PID file. The guard was removed for the controlled visible tests. Keep raw vendor assets, logs, images and samples ignored.

The controlled test sequence was:

1. Launch a baseline case and collect albedo and pose observations without saving. Apply the same root translation as the other cases. Confirm the expected gate character set, clip and actual motion.
2. Launch its native case, apply only the controlled root translation, inspect it and invoke native Save. Check the new save notification, file writes and hashes. Quit before visual or sampling operations.
3. Launch its manual case with the same initialization. Use the normal File > Save menu through computer use. Verify the same file/callback evidence. This is the manual-UI control, not another native-command dispatch. Quit without further edits.
4. In fresh processes, load both saved cases and collect equivalent pose and albedo snapshots. Compare every decoded key record in both saved animation files with the baseline and with each other. Do not collapse numeric drift into a success boolean.
5. Frame the same camera and compare baseline/native/manual images at the same resolution and lighting. For the gate, include beginning, middle and end poses. Repeat an unchanged capture to estimate render variability before assigning pixel differences to Save. Inspect the images as well as reporting pixel metrics.
6. If native and menu Save produce different sidecar bytes or properties, repeat the discrepant control with another untouched copy to distinguish route effects from nondeterministic serialization. Recheck all original installed hashes and close every owned Editor process.

Material readback before any Save will test whether the earlier `lambert1` value change already occurs during load. The known removed shader parameters equal installed shader defaults, but render equivalence remains a test, not an assumption.

## What remains open

The later [results](fidelity-results.md) establish bounded pose and image comparisons and a normal-menu Save control. These do not prove every interpolated instant or every render property. The raw-record comparison covers this fixture's entire bounded record stream, with uncertain field semantics kept explicit. Entirely invisible Editor startup remains outside this phase.

## Preparation validation

The parser passed the retained positive fixtures and offline refusals for unknown headers/flags, truncation, trailing bytes and a missing scene target. A valid altered key time produced a negative time-equality result. Python compilation, Lua syntax, Ruff, LF/JSON checks and repository validation passed. The six prepared copies have matched per-asset I3D hashes, no ready markers and no launch PID files. An offline subprocess check confirmed that the deferred-access guard refuses launch before creating an Editor process. Independent review checked the decoder limits and the execution-phase restrictions. These are preparation checks, not runtime or image acceptance.

## Archive context

The original raw inputs were discarded; historical `.docs/` paths are no longer available. See [evidence availability](../../README.md#evidence-and-applicability) for the retained results and limits. Historical commands require new prepared data and reviewed paths; see the [instrument index](../07-instruments/README.md).
