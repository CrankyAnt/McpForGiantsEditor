# Copied building-part replacement research

Date: 2026-10-17. Target: GIANTS Editor 10.0.14.0, SHA256 `c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`. This phase used copied basegame assets and inactive private Win32 desktops. It did not switch the input desktop, inject input, start a visible Editor, change Windows settings or repeat a workstation-lock test. No MCP server was built.

## Result

A rigid door with its hardware was imported from a different building, fitted to one separate gate leaf in a calf shed, and saved through native Editor Save. A fresh process loaded the replacement with the intended dimensions and position. The same saved file also reopened at its original path after an intentional unsaved change and forced process exit. Native viewport captures show the original metal gate replaced by a wooden door, with neighboring gates retained.

The bounded result supports building a first Windows MCP around the private-desktop route. File ownership, request sequencing, uncertain-operation reconciliation and process supervision still need implementation. This is evidence for a rigid geometry-editing workflow, not complete gameplay acceptance or transactional crash-safe saving.

## Predeclared task and chosen objects

The goal was to replace one rendered part, fit its parent-space X/Y dimensions and XYZ center, retain the other parts, then Save and independently reload. The tolerance was 0.0005 model units, treated as meters for these basegame assets. Z depth was intentionally not scaled. The initial plan was retained before runtime in ignored `replacement-door1/plan.json`.

Target: `data/placeables/brandless/animalHusbandries/specialCalfShed/specialCalfShed.i3d`. Its scene contains 50 nodes and 25 shapes, including nine separate gate leaves. The selected leaf was `specialCalfShed01/visuals/instances/gate01/gate01`. Its parent transform and the eight other gate instances were retained.

Donor: `data/placeables/brandless/constructibles/farmGarageConstructable02/farmGarageConstructable02.i3d`. Only `farmGarageBuildable02/visual/visual_lod/farmGarageBuildable02_lod0/phase07/doorLeftSmall_lod0` and its child `doorLeftSmallParts` were cloned into the target. These are two rigid shapes with 829 vertices in total. The original gate leaf had 979 vertices. Neither selected subtree uses skin bindings. The entire donor building was temporarily loaded for import, then its loaded root was deleted after cloning.

An earlier candidate, garageSmall's rolling door, had skin bindings spanning several doors. It was rejected to avoid confusing independent part replacement with skeleton and animation remapping. The selected static calf-shed gate has no door-opening animation to preserve. Its surrounding scene, rather than the donor's construction phases or gameplay XML, was the controlled editing target.

Both source directories were copied under ignored research storage. Hashes of all nine target source files and five donor source files remained unchanged. The resulting asset still depends on the installed game's `$data` resources. This is not a standalone packaged mod.

## Fit measurements

Bounds were computed from every renderable descendant shape vertex through `localToLocal(shape, targetParent, x, y, z)`. Target and donor therefore used the same coordinate space. Both selected roots had zero local rotation, so independent local X/Y scaling was supported. The fitting step measured again after scaling and corrected the XYZ center by local translation.

| Measurement | Original gate | Imported donor | Fitted donor | Fresh reload |
| --- | ---: | ---: | ---: | ---: |
| Width | 1.157018490 | 1.375442500 | 1.157018540 | 1.157019140 |
| Height | 0.933348477 | 2.360840770 | 0.933348477 | 0.933348924 |
| Depth | 0.327058163 | 0.166330814 | 0.166330576 | 0.166330576 |

The replacement scale was approximately `0.84119767, 0.395345807, 1`. The largest fitting error across width, height and XYZ center was about `5e-8` m in the retained snapshot. After Save and fresh load it was about `2.06e-6` m, below the declared 0.0005 m tolerance. These are float/snapshot measurements, not claims of physical or submicrometer precision.

The original leaf was deleted only after the replacement passed the fit check. The scene changed from 50 to 51 nodes and from 25 to 26 shapes, as one shape was replaced by a two-shape subtree. Runtime snapshots include an additional document root and camera, yielding 52 nodes before and 53 after.

All other scene-node names, visibility flags, renderability, material-slot counts, vertex counts and quantized vertex signatures matched after reload. Sixteen retained nodes had transform rounding, with a maximum difference of about `3.82e-6`. This is consistent with the existing Save serialization boundary. The modular vertex signature is serialized with nine significant digits. It is a bounded position check, not proof of normals, UVs, indices or exact material-property equivalence.

## Request uncertainty and forced-exit recovery

One request moved the imported replacement by +0.01 on local X before deliberately delaying completion. The host's 100 ms native-message timeout returned Win32 error 1460. The later matching XML receipt recorded one application. Inspection confirmed approximately +0.01, and a repeated dispatch of the same request sequence did not change X again. The original completed receipt remained unchanged. The part was fitted again before replacement and Save.

The delay used the Editor's coarse, whole-second `getTime()` function, after host-spaced receipts checked its units. A loop-count cap bounded a stalled clock. The observed delay was several seconds; it was not an exact four-second timer. This deliberately blocked script callback is fault injection on a disposable scene, not a proposed production technique.

Deduplication was demonstrated only for an existing completed receipt in one process. This does not prove exactly-once mutation across restart, an interrupted write, a missing receipt after an applied mutation, or a lost disk journal. An MCP must expose an uncertain result and reconcile actual scene state before deciding whether another mutation is safe.

A later process loaded the saved scene, applied another unsaved +0.01 X change and was terminated through its verified owned process handle with exit code 73. Saved I3D and shape-file hashes did not change. A fresh copy loaded the saved transform. A further control restarted the exact original scene path with the same prepared configuration and also returned the saved X `1.15701997`, rather than the unsaved `1.16701996`. It accepted inspect/render/quit without a blocking recovery dialog. This was an intentional termination after a completed Save, not a simulated crash during Save.

The original forced-exit receipts were preserved as `replacement-forced1-proof`. Restart at the original path reused `replacement-forced1`, after its prior root outputs were preserved under `prior-run`. No prior evidence was deleted.

## Visual evidence and background behavior

Eighteen native 1024 by 768 PNGs cover the original scene, imported donor, fitted overlap, completed replacement and fresh/recovered loads. They are scene viewport renders, not screenshots of menus or the entire private desktop. The original local gallery was `.docs/giants-editor-desktop/replacement-gallery.md`; the gallery and raw PNGs have since been discarded. Vendor assets and screenshots are not committed.

Visual inspection confirmed a wooden replacement in the leftmost gate opening. Identical close-view camera presets made the stages comparable. Saved and freshly reloaded images differed in 701 of 786,432 pixels; separate fresh and recovered-copy images were identical. These counts do not prove semantic visual equivalence, and no zero-difference claim is made for the save round trip.

Each command checked that the owned Editor frame was minimized before and after native dispatch. Retained input-desktop samples found no Editor-owned window on the input desktop and never found the private desktop active. The instruments contain no input-desktop switch or synthetic input route. All six completed run/reload cases released their private desktop. Five exited normally; the deliberate forced-exit case used code 73. The normal user Editor configuration retained SHA256 `31720002d6f6639a6d340ff4d7bb4e558f5ccd1001209c169d1f79f3345871cf`.

Two initial instrument preparations stopped before editing: the first found that Editor Lua does not expose `io.open`, and the second sampled the coarse clock too soon to see a whole-second change. Snapshots were changed to native XML carrying JSON text, with host-side JSON extraction. Both earlier private desktop objects were separately confirmed absent. These failed preparations are not counted as successful replacement runs.

## Dependencies and remaining boundaries

The saved I3D contains 25 resource references, all under `$data`. Each resolves to an installed resource, including DDS companions for PNG-named textures. The donor scene file is no longer needed to supply its cloned geometry after native Save. Shared game textures and shaders remain required. The copied placeable XML was not adapted or accepted as a playable mod, and collision/trigger behavior was not tested.

The trial does not establish fitting arbitrary rotations, skinned parts, remapped animation clips, LOD replacement, multi-file atomicity, crash recovery during Save, all native dialogs, live interactive desktop viewing or multi-hour operation. Those limits should become explicit capability boundaries or later acceptance tests. They do not prevent a first MCP exposing owned-session startup, scene inspection, rigid subtree import, transforms, native Save, native viewport capture and verified shutdown.

## Reproduction and validation

[Derived metadata](replacement-results.metadata.json) was produced during the trial by [the analyzer](../07-instruments/analyze_replacement_results.py). [The runner](../07-instruments/replacement_research.py) prepares copied fixtures and drives [the Lua bridge](../07-instruments/replacement_scene_probe.lua) through the existing guarded native controller. The launcher allows only the existing endurance bridge or the new replacement bridge, and requires/hashes the replacement configuration for the latter. Final review changed the bridge to read the launcher's write-once `input-replacement.xml` copy. A further fresh-load case, `replacement-input-copy1`, validated that path. Earlier trials read the prepared configuration directly; the original analysis confirmed its bytes matched the trial's input copy, but those trials did not establish resistance to concurrent configuration changes.

Use a fresh case name. `replacement_research.py --case <name> --mode prepare` copies the two selected directories and writes an isolated configuration. `--mode run` performs the complete edit and timeout test. Prepare a second case with `--source <completed-case>`, then use `--mode reload` for readback. `--mode forced-exit` operates only on an already saved copy, adds an unsaved change and terminates its owned process. `--mode recover-in-place` preserves that forced run and reopens the exact original scene path. These commands launch the Editor on an inactive private desktop; they do not switch the visible desktop.

The original cases used by the analyzer were `replacement-door3`, `replacement-reload1`, `replacement-forced1-proof`, `replacement-recovered1`, the recovered `replacement-forced1` and `replacement-input-copy1`. Raw evidence was stored under `.docs/giants-editor-desktop/endurance/` and has since been discarded. Native XML and derived JSON snapshots must match; the analyzer also checks fit errors, unaffected-node signatures, source hashes, resource existence, PNG validity, input-desktop samples and cleanup.

Python compilation, Lua syntax, Ruff, retained-evidence analysis and repository validation passed. Independent review checked the instruments and evidence; the configuration-copy finding was corrected and verified in a fresh process. No skill publication, runtime installation or remote Git operation is part of this phase.

## Archive context

The original raw inputs were discarded; historical `.docs/` paths are no longer available. See [evidence availability](../../README.md#evidence-and-applicability) for the retained results and limits. Historical commands require new prepared data and reviewed paths; see the [instrument index](../07-instruments/README.md).
