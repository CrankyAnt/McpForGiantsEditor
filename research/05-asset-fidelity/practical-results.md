# Practical background and asset tests

Date: 2026-10-16. This phase extends the [first runtime experiment](../02-lua-and-save/live-results.md). It records the historical research phase. No MCP server, runtime installation or skill publication was added.

## Result

The pinned Editor 10.0.14 build executed repeated native script commands and native Save while minimized with another process in the foreground. Two copied FS25 assets survived Save and a fresh engine load with the intended translation, node structure, shape/material-slot counts and rounded vertex signatures intact. The animated asset retained the observed clip bindings and durations.

Save is not a byte-preserving operation. It rewrote geometry and animation sidecars, rounded some node translations, changed a material color and omitted shader parameters whose values equal the installed shader defaults. These differences prevent a claim of a lossless round trip or complete visual/gameplay acceptance.

The executable SHA256 is `c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`. All Editor processes from this phase exited. The normal Editor configuration retained SHA256 `31720002d6f6639a6d340ff4d7bb4e558f5ccd1001209c169d1f79f3345871cf`.

## Background operation

The simple fixture received 30 script requests at four-second intervals, including six translation changes. Every before/after measurement had `IsIconic == true` and a foreground PID different from the Editor PID. Every measured foreground HWND was unchanged across its dispatch. Native Save also ran with these conditions and persisted `30.125 -2.5 8.75`.

Measured synchronous dispatch plus receipt inspection took 2.922 to 12.555 milliseconds in that simple-fixture loop. This excludes process launch and most host preparation. It is not a complete MCP latency benchmark.

One other foreground process was observed throughout that loop. The experiment did not inspect user input or other applications' contents. It establishes operation with another application in the foreground; it does not establish sustained switching among several applications, hours of operation, or correctness under arbitrary load.

The first background period included light computer use and application switching, with no reported focus loss or disruption. The final asset-test batch ran while the computer was idle. It therefore does not establish simultaneous interaction with the complex-asset workload. These observations are reported experience, separate from instrumented foreground samples.

The two asset runs each processed 12 work requests, one native Save and one quit request. All work and Save measurements also retained minimization and the external foreground HWND. The helpers never activated the Editor or synthesized input. Normal startup and fresh-load verification still briefly displayed Editor windows, with the user's availability confirmed in advance.

## Assets and acceptance evidence

| Copied FS25 asset | Runtime observations before and after Save |
| --- | --- |
| `data/vehicles/abi/waterTrailer550/waterTrailer550.i3d` | 38 nodes, 13 shapes, 30 material slots, 34,252 vertices. The source I3D has 11 Shape elements, 19 Material elements and 25 File elements. The loaded graph also includes the referenced number-plate light. |
| `data/placeables/agi/sentinelGarage/sentinelGarage_gate_animation.i3d` | 24 nodes, 21 shapes, 21 material slots, 8,782 vertices. The source I3D has 3 Material elements, 8 File elements and an external animation file. Seven node paths expose the same clip name and duration. |

A material-slot count counts assignments on shapes, not unique materials. The seven animation observations are seven node-path bindings with one distinct name-duration pair, `sentinelGarage_gateSource` and `10000` in the native API's duration units. They must not be reported as seven distinct clips.

For each asset, the host changed only the verified first root child to `7.25 -1.5 2.125`. A fresh Editor process loaded the saved copy, returned the exact requested translation and exited 0. A separate fresh process loaded an unmodified scratch copy as the geometry/animation baseline. Node paths, non-document-root names, shape flags, material-slot counts, vertex counts and the two vertex digests matched between those fresh loads. Clip bindings, names and durations matched too.

The geometry digest quantizes coordinates to one millionth of a model unit and uses two rolling arithmetic checks. It is a bounded consistency check, not a cryptographic hash or proof of exact float, triangle, normal or UV equivalence. It found no difference in the sampled vertex-position representation.

## Files and dependency isolation

The tests copied each asset's entire source directory into ignored `.docs/giants-editor-practical/`. Source hashes covered 10 installed water-trailer files and 22 installed garage files, and all remained unchanged. All copied DDS files also retained their source hashes.

The water trailer's six references to textures in its own `$data/vehicles/abi/waterTrailer550/` directory were rewritten only in the scratch I3D to local filenames. This made those resources resolve through the copied files. The garage already used local texture names. Its `.png` references resolved with the copied `.dds` companions without an asset-load error in the observed logs. Shared shaders, shared textures and the number-plate-light I3D continued to resolve through the installed game `$data` root. This is not a self-contained asset-package test.

Each run used its own config and script directory. `MCP_EXPECTED_SCENE` and `MCP_EXPECTED_TARGET` guarded Lua access. The Windows helper restricted the fixture label, scratch path, manifest target, process executable hash and exact main-frame title. Native command IDs were checked against the live menu. Requests and expected response files were published with sequence numbers. A changed test condition, missing receipt or uncertain dispatch stopped the runner instead of retrying a mutation.

The first water run used a newly created empty receipt directory. Its response IDs and timestamp order were also checked retrospectively. The later runner explicitly rejected existing expected receipts, required fresh mtimes and checked response IDs and requested translation values. The save receipt had to be absent before Save and newer than dispatch start afterwards. The runner checked that exact start time in memory but did not retain it. Independent analysis checks the callback status, scene and callback path, target translation, successful transport, and a timestamp after the last work response and before the saved dispatch result. It does not reconstruct an exact dispatch-start timestamp.

## Serialization differences

These are observations, not automatic acceptance exceptions:

- The Editor changed the document-root name by appending `.i3d` in both assets. Other node names and node paths matched.
- Eight other water-trailer node translations changed by at most approximately `0.000004` model units. Fourteen gate node translations changed by at most approximately `0.000005`. For example, `2.227716` became `2.22772`. The before/after XML confirms decimal serialization changes. Snapshots record translations to six decimal places, so these figures have that measurement limit. Rotation and scale drift were not measured by this Lua snapshot.
- Both assets' `lambert1` material changed from diffuse RGB `0.5` to `0.501961`. This is numerically consistent with rounding to `128/255`, but the test did not isolate whether loading or saving introduces it and did not establish visual equivalence.
- The water trailer lost four explicit `alphaBlendingClipThreshold=1` entries and two explicit `colorScale=1 1 1` entries. The installed `data/shaders/vehicleShader.xml` declares those exact defaults near its parameter definitions. Omission is consistent with default suppression, but the material XML is not identical.
- The water `.shapes` remained 1,895,892 bytes with a different hash. The gate `.shapes` changed from 526,416 to 525,472 bytes. Its `.anim` remained 35,172 bytes with a different hash and 2,390 differing bytes. Clip names/durations survived reload; keyframe equivalence and playback were not proved.

The logs also contain the pre-existing startup messages `Failed to enable XBTC features` and `Failed to load XBTC.dll`. The same messages occurred in the earlier simple-fixture run, and no matching DLL was present in the installed Editor directory. The phase does not claim warning-free startup or repair this unavailable feature. No additional asset-load failure was found by the focused error scan.

## Reproduction and validation

The original raw receipts and prepared copies were stored under ignored `.docs/giants-editor-practical/` and have since been discarded. They were local trial inputs, not distributable vendor assets. Durable derived results are in [practical-results.metadata.json](practical-results.metadata.json).

`instruments/practical_scene_probe.lua` supplies guarded inspection, translation, save callbacks and readback. Configure the existing menu stub and isolated config as in `live-results.md`. Set `MCP_PROBE_ROOT`, `MCP_EXPECTED_SCENE` and `MCP_EXPECTED_TARGET` before sourcing it. `MCP_READBACK_ONLY=true` writes the independent fresh snapshot and exits. Publish sequential `request-NNN.xml` files for `inspect`, `set` and `quit`.

`instruments/practical_windows_probe.py` accepts only `water-trailer` and `animated-gate` fixtures prepared under the research scratch root. Inspect first with `--fixture`, `--pid` and `--expected-title`; then choose `--action script` or `--action save`. These actions require a minimized Editor and another foreground process. Exit 3 means uncertain/failed transport; exit 4 means a background-test postcondition changed. The quit exemption requires exactly one pending request with `op="quit"`. Never interpret a returned message alone as proof of Lua completion or persistence.

The original regeneration command is preserved below as a historical example. Its old receipts are no longer retained; new trials and reviewed paths are needed:

```powershell
$env:PYTHONPYCACHEPREFIX = "$env:TEMP\repo-pycache"
python docs/research/skills/fs25-modding/giants-editor-mcp/instruments/analyze_practical_results.py --output docs/research/skills/fs25-modding/giants-editor-mcp/practical-results.metadata.json
```

The analyzer verifies request/response sequence and freshness, the saved target translation, source hashes, runtime graph signatures, animation bindings and minimized/foreground conditions. It records material and serialization differences rather than declaring them equal. Independent review checked the command guards, request correlations, callback checks and geometry evidence. Python compilation, `luac -p`, Ruff check/format and repository validation passed. The analyzer regenerated the metadata successfully from the retained receipts.

## Consequence for an MCP

The focus and minimization problem has a tested solution for these assets. A Windows-only research MCP could use this native script/Save route after ordinary startup. It still needs explicit document ownership, correlated requests, uncertain-operation recovery and version checks.

Production acceptance must distinguish successful automation from acceptable asset changes. Animation pose sampling, material/render comparison, normals/UVs, representative large scenes and in-game behavior remain separate checks. Entirely invisible startup was not established in this phase. Later [private-desktop trials](../03-startup-and-headless/invisible-startup-results.md) succeeded. This phase implements neither a general MCP service nor production asset editing.

## Archive context

The original raw inputs were discarded; historical `.docs/` paths are no longer available. See [evidence availability](../../README.md#evidence-and-applicability) for the retained results and limits. Historical commands require new prepared data and reviewed paths; see the [instrument index](../07-instruments/README.md).
