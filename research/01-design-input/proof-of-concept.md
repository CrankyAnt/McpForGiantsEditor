# GIANTS Editor MCP proof of concept

Status: completed research proof of concept. The standalone MCP remains design-only; this archive contains no MCP implementation.

## Purpose and boundary

This PoC tests a narrow Windows file-editing workflow around GIANTS Editor 10.0.14.0.
It is bounded to the installed build, the tested Windows session, and the proven
inactive private Win32 desktop route.
The target build is GIANTS Editor 10.0.14.0, SHA256
`c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`.
The route keeps the Editor away from the user's input desktop while the host reads
state and writes a copied scene through the native Editor save path.
The PoC is a design/build handoff. It does not choose a wider architecture, service
model, licensing disposition, or product contract for the future standalone repo.

## Evidence that sets the scope

The executed target was `specialCalfShed.i3d` and the donor was
`farmGarageConstructable02.i3d`. The selected target is the static gate leaf
`specialCalfShed01/visuals/instances/gate01/gate01`.
The donor subtree is `doorLeftSmall_lod0` with child `doorLeftSmallParts`.
The target had 50 nodes and 25 shapes before the edit. The result had 51 nodes and
26 shapes, while the other eight gate instances remained in the scene.
The fit used parent-space bounds, local X/Y scaling, and XYZ translation. The
declared tolerance was 0.0005 model units. The retained fit error was about 5e-8 m;
fresh reload error was about 2.06e-6 m at the largest measured center value.
The replacement was saved and independently loaded in a fresh process. The saved
scene retained unaffected node and geometry signatures within the documented save
rounding boundary. The installed target and donor source files remained unchanged; only the copied target was edited.

One delayed native request returned Win32 error 1460. The receipt showed one applied
operation. Replaying the same request sequence in the same session produced zero
additional movement. This is one-apply same-session deduplication, not exactly-once
delivery across restart, missing receipts, interrupted writes, or lost journals.

An intentionally unsaved change was followed by owned-process termination with exit
code 73. A fresh process reopened the exact original scene path and recovered the
completed Save state, including the saved X coordinate. This is recovery after a
completed Save, not crash recovery during Save.

The evidence contains 18 native PNGs from scene viewers. They are native viewport
renders, not screenshots of the real desktop or proof of interactive desktop viewing.

Handle-growth evidence bounds sustained work. Restored-window batches added 181 and
198 Event handles across 200 inspections; matched minimized batches added zero.
A fifteen-minute minimized run completed 5,133 inspections, 133 mutations, 29 Save
receipts, and 28 PNG renders without an increasing Event pattern. The route still
needs explicit minimized-state checks and a persistence-first restart policy.

Invisible-startup trials used two copied assets and four private desktops. They
completed inspect, mutation, native Save, fresh-load readback, animation sampling,
and rendering without an Editor window on the input desktop. The Editor still creates
GUI windows and initializes Vulkan. The result is not true headless execution.

## Planned PoC workflow

1. Pin and verify the exact Editor executable hash before starting a session.
2. Create a disposable fixture from an owned synthetic scene and record its manifest.
3. Start the Editor on an inactive private Win32 desktop with no visible fallback.
4. Keep the owned Editor minimized before sustained traffic and verify `IsIconic`.
5. Read the scene and return bounded node, shape, transform, and resource evidence.
6. Write only the declared target replacement and parent-space fit operation.
7. Re-read the scene and validate dimensions, center, retained gates, and receipts.
8. Save through the tested native path, then close the owned process cleanly.
9. Start a fresh owned process, read the saved scene, and compare the receipt.
10. On timeout or uncertain acknowledgement, report uncertainty and reconcile state
    before allowing another write. Do not infer success from a transport response.
11. Capture native PNG evidence where useful, while labeling it as viewport output.
12. Release the private desktop and owned process handles; retain closed-session evidence under the chosen retention policy.

The PoC exposes file read/write operations and their evidence receipts only. It does
not define general Editor UI control, arbitrary UI commands, or an interactive viewer.

## Transfer inventory for a future standalone repository

Product implementation needs its own source manifest, build instructions, synthetic-fixture provenance, version/hash gate, receipt format, cleanup rules and CI checks. Public test fixtures must be independently authored and usable without installed game assets.

Historical instruments and executable-analysis records are retained separately as research. They are not product dependencies or validated product interfaces. Copied vendor assets, runtime logs, configurations and raw disassembly are not distributed with this archive.

The proposed contracts are in [the design](mcp-design.md) and [build plan](mcp-build-plan.md).

## Unsupported or unproven features

This PoC does not support true headless mode, arbitrary rotations, skinned geometry,
animation remapping, LOD replacement, collision or trigger acceptance, gameplay XML,
multi-file atomicity, crash recovery during Save, general modal-dialog recovery, other GPU or
Editor versions, remote sessions, or unbounded operation.

It does not prove a universal Windows unlock result, driver independence, security
isolation, or a stable private-desktop route across machines. The minimized run covers
the measured fifteen-minute workload only.

The [license audit](../06-publication/publication-license-review.md) retains unresolved applicability questions. The PoC does not grant redistribution rights for vendor assets or establish legally certified clean-room development.

## Archive context

This report records the 2026-10-16/17 research against the pinned Editor build. Raw assets, screenshots, configurations and machine logs referenced under `.docs/` are local-only and are not distributed. Reproduction commands retain their historical workspace assumptions; read the [instrument index](../07-instruments/README.md) before adapting or running them.
