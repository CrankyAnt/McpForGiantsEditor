# MCP for GIANTS Editor

This branch is a disposable research and design archive for preparing the product specification. It is never merged into `main` and may be removed once the specification supersedes it. No MCP server is implemented here.

## Start with the question

Read only the route relevant to the task. The design is a proposal; the result reports record completed experiments and their limits.

| Question | Start here | What it establishes |
| --- | --- | --- |
| What should the MCP do, and how could it be built? | [Design input](research/01-design-input/README.md) | Proposed architecture, tool contracts, build sequence and PoC boundaries. Input to specification, not a finished specification. |
| Can original Lua edit a scene and save it reliably? | [Lua and native Save](research/02-lua-and-save/README.md) | Lua discovery, native Save behavior, minimized dispatch and fresh-process readback. |
| Can Editor start without disturbing the input desktop? Is it headless? | [Startup and headless investigation](research/03-startup-and-headless/README.md) | Successful private-desktop GUI initialization and the boundaries of 32 unsuccessful headless cases. |
| Can a private-desktop session run for longer, handle errors, and be observed? | [Desktop operations](research/04-desktop-operations/README.md) | Measured duration, handles, lock/session observations, dialog recovery and viewer options. |
| Did real asset edits, animation and Save round trips preserve the intended result? | [Asset fidelity and replacement](research/05-asset-fidelity/README.md) | Manual/native Save comparison, decoded keyframes, pose samples and fitted door replacement. |
| What license and distribution questions remain? | [Historical publication review](research/06-publication/README.md) | Dated source facts and unresolved applicability questions, not current legal clearance. |
| How were the measurements produced? | [Instrument index](research/07-instruments/README.md) | All 32 historical research instruments, their dependencies and execution boundaries. |

## Findings that constrain a specification

- Original Lua mutations and native Save succeeded while minimized, followed by fresh-process verification.
- A separate inactive Win32 desktop supported invisible startup, Save, rendering and fresh-load checks. Editor still creates windows and initializes its graphics backend.
- The 32-case investigation found no working true-headless route for the pinned build. That is measured coverage, not proof about every future build or technique.
- Minimizing the owned frame removed Event-handle growth in the measured inspection workloads. Sustained evidence includes one fifteen-minute workload, not days of operation.
- A copied building part was replaced, fitted on X/Y, centered, saved and reloaded. A timed-out request was reconciled without applying the same move twice in that session.
- Save changes serialized asset data, including under ordinary manual Save. Successful intended edits do not establish lossless serialization or crash atomicity.

For detailed numbers, provenance gaps and unsupported cases, follow the relevant result report rather than generalizing these summaries.

## Evidence and applicability

The research dates are 16 and 17 October 2026. The tested Editor was 10.0.14.0, executable SHA-256 `c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`. Runtime results apply to the measured Windows/GPU environment. Recheck compatibility for another build or machine. This transfer did not run Editor or repeat the experiments.

Eleven metadata JSON files sit beside their reports. [The transfer manifest](research/manifest.json) records the source and imported hashes of all 66 retained source files. Markdown was adapted for public navigation and context. All eleven metadata files and 31 of the 32 instruments are byte-identical. One instrument replaces a personal Python-installation path with the current interpreter, as recorded in the instrument index.

The original raw copied scenes, screenshots, configurations, request receipts, telemetry, installers and diagnostic outputs were deliberately discarded after retention review. No raw trial files are retained in this repository or its local evidence store. Reports name historical `.docs/` paths to explain the original method; those inputs are no longer available. The recorded measurements and hashes preserve the reported result and its limits, not the complete underlying experiment. Historical results can no longer be regenerated or independently re-audited from the old raw data. New reproductions require fresh disposable fixtures and new measurements on a compatible installed environment.

The historical scripts retain fixture-specific paths and version assumptions. Read the [instrument boundaries](research/07-instruments/README.md#execution-boundaries) before adapting them. Their presence is evidence of the investigation, not a product dependency or a requirement to adopt their techniques.

## From research to specification

Use [the proof of concept](research/01-design-input/proof-of-concept.md) for measured scope, [the design](research/01-design-input/mcp-design.md) for proposed behavior and [the build plan](research/01-design-input/mcp-build-plan.md) for proposed sequencing. Resolve open choices in a new product specification. Apply the [executable-integrity and legal-assessment boundary](research/01-design-input/mcp-design.md#executable-integrity-and-legal-assessment) when assessing implementation techniques.

Development agreements remain under [docs/agents](docs/agents/), with [AGENTS.md](AGENTS.md) as the repository instruction entry point. Product releases follow [the publication policy](docs/agents/publication.md).
