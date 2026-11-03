# Standalone MCP build plan

Status: proposed implementation sequence, based on research completed on 2026-10-17. This plan is input to a future specification for McpForGiantsEditor; it is not an instruction to build on the research branch.

The technical basis is [the PoC handoff](proof-of-concept.md). Proposed behavior and tool contracts are in [the design](mcp-design.md). The [license review](../06-publication/publication-license-review.md) retains historical source facts and unresolved applicability questions.

## Delivery boundaries

Implementation belongs in McpForGiantsEditor after its specification is established. Product release authority follows `docs/agents/publication.md`.

MIT is a proposed license for independently authored product code and synthetic fixtures. The final license remains open. Review actual code provenance and dependency obligations before assigning a license; do not describe a restrictive non-commercial license as OSD open source.

## Phases and completion evidence

| Phase | Concrete work in the future repository | Completion evidence |
| --- | --- | --- |
| 0. Specification and rights handoff | Record product scope, supported MCP client, final license status, code provenance and dependency obligations. Assess executable inspection and runtime behavior techniques against the design legal-assessment boundary. | A concrete product specification and validation contract exist; package contents and publication boundaries are explicit. |
| 1. Owned process lifecycle | Minimal SDK/stdio status handshake plus original minimal config/menu stub, pinned executable discovery, private desktop/job ownership, launch/ready validation, minimization and clean close. Single-session ownership and no visible fallback. | Synthetic scene opens and closes repeatedly without activation. Changed hash, wrong desktop/frame and another Editor are rejected. Startup requires the disclosed session emergency-close grant. Host termination cleans up the owned process under that grant; unrelated processes stay untouched. |
| 2. Request and state contract | Original Lua operation bridge driven by native script-menu dispatch without enabling simulation, native XML receipts, atomic request publication, durable journal, request/epoch/revision correlation, bounded queue and reconciliation. | Timeout-after-apply, completed-key replay, same key/different payload, stale/malformed receipt, wrong epoch, cancellation and host restart return deterministic states without duplicate mutation. |
| 3. Useful editing workflow | Bounded inspection, import/clone, absolute local transform, plan/apply rigid part replacement and fit postconditions. Keep original target until replacement checks pass. | Owned synthetic building with multiple independent parts passes the complete door replacement task. Other parts retain agreed invariants. Unsupported skin/LOD/rotation/physics cases fail with a useful reason. |
| 4. Persistence and recovery | Managed-copy source manifest, backup set, native Save discovery, sidecar manifest, fresh-load checkpoint verification, failed-checkpoint preservation and explicit dirty-state recovery. | I3D/sidecars survive fresh readback. Source copy is untouched. Unsaved shift is lost only after approved discard/forced-exit test. Original-path restart passes. Interrupted Save is either safely restored from backup or explicitly unsupported with no successful-checkpoint claim. |
| 5. MCP and observation | Official SDK stdio tools/resources, schemas, structured errors, status/progress, milestone PNGs and artifact retrieval. Optional read-only viewer after core image path works. | A real target MCP host performs the complete synthetic task from tool calls. Frames have timestamp/revision and match fresh readback. Viewer cannot mutate, serve arbitrary files or capture other apps. Standard output contains only protocol messages. |
| 6. Release candidate | Package only original code/fixtures/docs, dependency notices, reproducible lockfile/build, compatibility notes, installation/uninstallation and operational limits. | Original code, fixture provenance and dependency notices reviewed; packaging contents audited; synthetic public CI green and licensed local Editor integration results retained. User approves public release separately. |

Phases 1 to 5 are build steps, not instructions to execute them in this branch. Phase 2 is a prerequisite for any unattended mutation. Phase 4 is a prerequisite for claiming verified saves. A useful local prototype does not need interactive desktop switching, cloud hosting or general Lua execution.

## Planned repository layout

```text
McpForGiantsEditor/
  README.md
  pyproject.toml
  dependency lockfile
  src/mcp_for_giants_editor/
    mcp.py
    sessions.py
    operations.py
    windows.py
    checkpoints.py
    artifacts.py
    lua/bridge.lua
    lua/menu.lua
  tests/
    unit/
    protocol/
    integration_windows/
    fixtures/synthetic_building/
  docs/
    architecture.md
    operations.md
    permissions.md
    compatibility.md
    licensing.md
  LICENSE                 after the final own-code license is selected
  THIRD_PARTY_NOTICES      only actual distributed dependencies
```

Names are provisional and indicate responsibility; they are not files to generate now. Keep Windows code together instead of scattering handle, desktop and menu logic across tool handlers. Reuse a module only when it removes duplicated behavior. Do not start with an adapter registry or plugin framework.

## Migration inventory

The retained instruments are historical research material. Review `private_desktop_probe.py` and the narrow Windows identity/menu helpers for original lifecycle logic; review `desktop_endurance_probe.py`, `desktop_research_controller.py` and `replacement_scene_probe.lua` for measured sequencing and cleanup. Fixture-specific CLIs are not the product interface.

Diagnostic hooks, executable-address records and reconstruction scripts document how research conclusions were reached. Their presence in this research archive does not make them product features. Apply the executable-integrity and legal-assessment requirements in the design before adopting a technique.

The replacement algorithm can be expressed from the tested binding semantics: load, clone, link, vertex-space bounds, scale, center, measure and replace. Product code and fixtures need their own provenance. Do not copy GIANTS script implementations or vendor fixtures.

## Synthetic acceptance task

The public fixture should be authored for the new repository and have its own stated license. Require a per-file provenance manifest for geometry, materials, textures and shader inputs, recording author/source, license and whether redistribution is allowed. Any reference to an installed proprietary dependency is identified separately and excluded from public CI fixtures; missing provenance blocks fixture publication. It contains a shed-like structure, at least three independently addressable gate/door parts, nested transforms and a separate donor door with a hardware child. The donor must differ in width and height so both X and Y scaling are exercised. Native materials must be original/basic and use no GIANTS assets, logos or paid-model textures.

The target keeps stable control nodes. Predeclare widths, heights, centers and expected node additions/removals. Measure in the target parent's coordinates. Start with the proven zero-local-rotation rigid case. Use a 0.0005-scene-unit fit threshold only for a fixture authored in the declared meter convention; do not assume arbitrary imported models have correct physical units.

The acceptance run must:

1. Record original fixture hashes and node/shape/transform signatures.
2. Start privately and minimize; verify the user's input desktop remains unchanged at bounded samples.
3. Capture original close/overview images with named camera presets.
4. Import the donor subtree, fit width/height, align center and capture a preview while the old target remains.
5. Apply replacement only if the measured plan still matches the current revision.
6. Inject a timeout after one deliberate change; reconcile it without replaying an uncertain mutation.
7. Save and independently reload; verify structure, bounds, controls and image availability.
8. Make an explicitly discardable unsaved change, terminate the owned process, reopen the same scene path and verify the last checkpoint.
9. Close and prove owned-process/private-desktop cleanup. Retain receipts, manifests and synthetic images under a documented retention policy.

The existing calf-shed/basegame trial is local evidence for this design, not a public test fixture. A local opt-in regression may use a user's legally available game assets after rights review. Public CI must not download a game, Editor, vendor SDK or assets to run tests.

## Failure and compatibility test matrix

| Test | Required outcome |
| --- | --- |
| Wrong Editor version/hash or missing required Lua binding | Reject before mutation; no binary patching or guessed compatibility. |
| Duplicate request key, wrong payload or stale epoch | Cached known result or conflict; never duplicate a started uncertain operation. |
| Timeout before dispatch | Not applied; safe to resubmit with the documented operation identity. |
| Timeout/cancel after dispatch | Explicit uncertain/completed status and bounded reconciliation; no assumption of rollback. |
| Write succeeds but completion receipt is missing | Freeze writes, compare scene with intent and checkpoint; preserve uncertainty if evidence is insufficient. |
| Known Save error modal | Detect exact owned dialog. Acknowledge only under the scoped tested recovery policy, then verify disk state. |
| Unknown modal, blocked capture or hung callback | Bounded worker timeout, status/artifact evidence, no blind Enter/Escape/OK or desktop switch. |
| Static inspect/capture/idle workload | No automatic update-loop activation or unintended control-node movement. Unexpected simulation state blocks further static operations until reconciled. |
| Force-stop before Save | Only owned process stops under the emergency-close grant. Preserve journal; deliberate checkpoint rollback requires its own matching session/checkpoint/revision loss grant. |
| Force-stop during Save | Never report a verified checkpoint. Restore only an intact known backup under approved recovery; preserve failed files. |
| Source changes after copy or before promotion | Refuse overwrite and present a new diff/conflict. |
| Symlink/reparse/path escape or unapproved dependency | Reject the request or require a new source scope; do not silently read/write outside roots. |
| Frame unexpectedly restored | Stop further command batches, re-minimize only the owned private frame and revalidate before resuming. |
| Lock/disconnect/sleep boundary | Pause new work, never inspect secure UI, reconcile on return. Sleep/RDP/GPU-reset behavior stays unsupported until tested. |
| Viewer refresh while another app has focus | No focus move; viewer reads completed images and cannot create an unbounded render queue. |

Test pure validation and state transitions without launching the Editor. Test transport through the real SDK/stdio contract. Run licensed Editor integration tests separately on the supported Windows/GPU stack and publish only synthetic artifacts cleared for redistribution. A mocked passing test is not evidence that the installed Editor serialized a scene.

## Observation milestones and consent

Phase 5 first returns native PNGs through MCP. This already lets a supporting host show the user the current scene and progress. A local read-only viewer is optional and requires a normal window only when the user requests it. It shows completed image age and paused/uncertain state.

Interactive takeover is a later milestone after v1. Its acceptance must prove explicit switch approval, a usable return control on the private desktop, restoration of the prior input desktop, paused agent commands during human editing, re-minimization and reference invalidation on resume. A screenshot success is not takeover acceptance.

Use one task-scoped authorization for routine background work in the managed copy. Keep explicit approvals for new write roots, unapproved original-file promotion, visible input control and potentially lossy recovery. Startup also records the emergency-close loss scope for this disposable session. Recovery grants identify the exact checkpoint and revision range that may be discarded. Record grants through a trusted host/user control; the model cannot grant itself permission by filling a boolean. Do not add per-command confirmation where the user's existing task scope already authorizes it.

## Release and decision checklist

Before implementation:

- Establish the product specification, v1 scope and target MCP host.
- Review the executable-integrity and legal-assessment boundary in the design.
- Carry historical license uncertainties into implementation decisions.

Before a product release:

- Select the final own-code license and review dependency obligations and fixture provenance.
- Audit package contents and history for vendor components, credentials and unintended diagnostic tooling.
- Complete SDK/client and Windows integration checks with explicit build support and limitations.
- Obtain product-release authorization under `docs/agents/publication.md`.

## Archive context

The original raw inputs were discarded; historical `.docs/` paths are no longer available. See [evidence availability](../../README.md#evidence-and-applicability) for the retained results and limits. Historical commands require new prepared data and reviewed paths; see the [instrument index](../07-instruments/README.md).
