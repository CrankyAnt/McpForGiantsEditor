# Controlled Save, keyframe and render results

Date: 2026-10-16. Target: GIANTS Editor 10.0.14.0, executable SHA-256 `c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`. These are local research results for two copied FS25 assets. No MCP server, skill publication or runtime installation was performed.

## Outcome

Normal File > Save and native `WM_COMMAND/6001` produced the same I3D XML for both fixtures and the same gate animation bytes. Both routes reproduced the previously observed serialization changes. The native route therefore introduces no additional difference in those compared files. The `.shapes` files are not byte-identical, including between two runs of the same Save route. Their internal layout remains undecoded.

A script can seek the gate to a requested animation time, frame a camera and write a PNG through `renderScreenshot`. New start, middle and end images also succeeded while the Editor was minimized. This extends the demonstrated background-control route to visual feedback without mouse/keyboard input. Startup in these tests remained visible. Entirely headless initialization is still unproven.

## Controls and evidence

The primary matrix contained baseline, native and manual cases for each of the water trailer and animated gate. Each asset's three prepared I3Ds and copied sidecars matched before launch. All processes used a dedicated `editor.xml`, script directory and scratch document. The only initial scene mutation was the target-root translation `7.25,-1.5,2.125` in all cases.

Baseline processes were never saved. Initial Save controls accepted only inspection and quit. Manual controls used computer use to open the ordinary File menu and click Save. Native controls sent the guarded Save command. Successful `ON_SAVE` receipts identified the exact scratch document. Every saved case was then opened in a fresh process before sampling or rendering. No observation process was saved.

Because `.shapes` hashes differed, the complete Save comparison was repeated from new untouched baseline copies. This added a second manual and second native Save per asset, each followed by a fresh reload. I3D XML and gate animation bytes stayed identical across these four outputs per asset. Shape bytes varied within each route as well as between routes. This establishes run-to-run byte variation, without identifying its encoding or proving full shape-data equivalence.

Raw inputs, receipts, samples and images remain ignored under:

- `.docs/giants-editor-fidelity/` for the primary six-case matrix;
- `.docs/giants-editor-fidelity-repeat/` for capture-only repeat processes;
- `.docs/giants-editor-save-repeat/` for the repeated Save controls and fresh readbacks;
- `.docs/giants-editor-render-timing/` for the bounded image-file timing measurement.

The capture-only repeat cases deliberately use observation permissions regardless of the route that produced their input. Their folder names and `repeat_input_from` identify provenance. They are not additional Save controls.

The reproducible analyzer is [analyze_fidelity.py](../07-instruments/analyze_fidelity.py). Consolidated hashes, validation and numeric differences are in [fidelity-results.metadata.json](fidelity-results.metadata.json). Raw vendor assets and images are not committed.

## Gate keyframes and evaluated poses

All 1,095 records in the bounded animation fixture were decoded in both saved outputs. Seven track targets matched through companion-I3D scene paths. Every key time and flag word remained equal. Relative to baseline, 1,045 records changed one stored float component, with maximum absolute delta `0.000041484832763671875`. Native and manual outputs matched each other exactly. Field units and interpolation semantics remain outside the decoder's established contract.

The engine evaluated one expected clip, `sentinelGarage_gateSource`, duration 10000, at 41 times from 0 through 10000 in steps of 250. All 24 nodes had finite pose values; track times matched requested times, and scene nodes moved in all 40 adjacent intervals. Native and manual samples were identical. Relative to the unsaved baseline, both had these maximum local differences, excluding the perspective camera:

| Quantity | Maximum difference |
| --- | ---: |
| Translation component | `5.0067901611328125e-6` model units |
| Euler component | `1.633167266845703e-5` radians |
| Scale component | `0` |
| Normalized, sign-invariant quaternion angle | approximately `4.14848e-5` radians |

The repeated Saves reloaded to the same sampled gate poses as their first-run counterparts. Sampling does not restore all animation-track state, so it remains an observation-only operation in a disposable process. These checks cover all stored records of this fixture and 41 evaluated instants, not every interpolated instant or arbitrary FS25 animations.

## Materials and images

The loaded baseline already reported albedo components `0.50196081399917603` before any Save for the material slots where the API returned a value. The original I3D material specified `0.5`; saved XML writes approximately `0.501961`. The changed loaded value therefore precedes Save. This does not locate the conversion more precisely inside the loading/material pipeline.

The getter returned colors for 6 of 30 water slots and 7 of 21 gate slots. Most material slots returned `success=false` from the albedo getter. Matching unavailable values do not prove material equivalence. Texture hashes, the earlier shader-default analysis and the rendered images provide separate bounded observations.

At 512 by 512 pixels, baseline/native/manual gate PNGs were byte-identical at the start, midpoint and end. Repeated unchanged captures matched their originals. The water trailer's native/manual PNGs were identical; baseline versus either saved variant differed by one pixel, with maximum channel delta 1 out of 255. This is a measured difference, not a lossless-render claim.

Additional capture-only processes repeated the gate views and rendered the water trailer at 1024 by 1024 from a closer camera. At this closer water view, baseline versus either saved variant differed in 50 pixels, with maximum RGB channel delta 32 and no alpha differences. The changed pixels occupied the rectangle from x=441 through 459 and y=702 through 753. Native and manual images remained byte-identical. These quantitative comparisons are recorded separately because resolution and camera differ from the primary matrix. The images were decoded, checked for visible content and inspected. The gate visibly progresses from closed, through a bent midpoint pose, to open. The trailer and its textures are visible in the close views.

The manual gate readback was also minimized through the normal window control. While minimized, native script dispatch rendered the current midpoint, sought the end and rendered it, then sought the start and rendered it. All three PNGs matched their corresponding primary views. A guarded read-only Win32 check confirmed `IsIconic=true` after these captures and before quit. This is one minimized process with three distinct evaluated poses, not a long-duration concurrency or invisible-startup test.

## Render completion and limits

The Lua operation initially labels its output `renderCandidate=unvalidated`. A successful dispatch or XML receipt alone is not image acceptance. Some image-tool previews appeared anomalous even when the files were byte-identical and decoded to the same nonblank pixel bounds. Their cause was not established. No renderer or serialization defect is inferred from those previews.

A separate measurement polled image files roughly every 20 ms for three seconds after each of three render requests. Start and end captures briefly existed as zero-byte files before decoding successfully. First decodable files appeared approximately 127 to 465 ms after starting the request subprocess. No later hash change was observed during the three-second windows, and their final hashes matched the primary gate views. These timings include Python startup and command dispatch. They are not isolated renderer latency or a general guarantee about GPU completion.

A future bridge must wait for a new file, successful decoding and an explicit bounded stability condition. It should reject empty, stale or misframed output. One unchanged repeat pair measures that pair's noise; it does not establish a statistical noise bound. Fixed lighting, one camera and two fixtures cannot establish every shader, LOD, transparency, terrain or in-game effect.

## Source preservation and validation

The 32 installed source files retained their pre-test hashes. The normal user Editor configuration retained SHA-256 `31720002d6f6639a6d340ff4d7bb4e558f5ccd1001209c169d1f79f3345871cf`. All owned Editor processes were closed. No game process was required.

One extra capture-only startup stopped on a malformed temporary configuration caused by implicit ANSI decoding of a UTF-8 BOM. Profile replacement was declined. The scratch configurations were regenerated with explicit UTF-8 decoding before successful repetition. This was an instrument-preparation error, separate from the asset results. The previously observed XBTC startup warning also remains outside these asset controls.

Python compilation, Lua syntax, Ruff check/format and LF checks passed. The typed receipt validator accepted three real receipts and rejected ten corrupted receipts covering operation, scene, Save path and success status. Quaternion sign and zero-norm controls passed. The final metadata contained no unresolved invalid or pending evidence statuses. Uncollected or inapplicable supplemental captures remain explicitly labelled. Independent review checked the analyzer and report against retained evidence. The original repository validation passed with 35 managed skills, 35 registrations and 22 labels. These are historical source-repository checks, not current MCP implementation or CI results.

To reproduce the analysis against the retained local evidence:

```powershell
$env:PYTHONPYCACHEPREFIX = "$env:TEMP\repo-pycache"
python docs/research/skills/fs25-modding/giants-editor-mcp/instruments/analyze_fidelity.py --root .docs/giants-editor-fidelity --repeat-root .docs/giants-editor-fidelity-repeat --save-repeat-root .docs/giants-editor-save-repeat --timing-root .docs/giants-editor-render-timing --output docs/research/skills/fs25-modding/giants-editor-mcp/fidelity-results.metadata.json
```

## Archive context

This report records the 2026-10-16/17 research against the pinned Editor build. Raw assets, screenshots, configurations and machine logs referenced under `.docs/` are local-only and are not distributed. Reproduction commands retain their historical workspace assumptions; read the [instrument index](../07-instruments/README.md) before adapting or running them.
