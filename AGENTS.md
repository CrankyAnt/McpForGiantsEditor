# McpForGiantsEditor

Development repository for MCP for GIANTS Editor.

## Agent skills

### Issue tracker

Issues, specifications and tickets are tracked in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Requests use the configured Type, Triage, Ready, Status and Resolution labels. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context domain documentation. See `docs/agents/domain.md`.

### Other configuration

Research, delivery paths including direct-main, publication rules and CI: see `docs/agents/`.

## Repository standard

Documentation goes to one of three places:

- `docs/guides/`: for the people who use the product.
- `docs/development/`: for whoever develops or extends the product, agents included: how a part works, how a developer uses it, how to extend it.
- `docs/sources/`: for the same readers, material from outside the repository, kept as `docs/agents/research.md` says.

The product's own technical reference, such as its APIs, commands, configuration or data model, lives with its audience in `docs/guides/` or `docs/development/`.

Each document in `docs/guides/` and `docs/development/` is one [Diataxis](https://diataxis.fr/compass/) type: tutorial, how-to guide, reference or explanation. Why a decision holds is an ADR; a term goes to `GLOSSARY.md`.

The top level of `docs/` holds only `adr/`, `agents/`, `guides/`, `development/`, `sources/`, `out-of-scope/` and the exceptions below. Inside `guides/` and `development/`, a folder holds one broad subject, such as `docs/development/skills/` or `docs/development/modules/`, never a single document. It comes with its first document, when that document clearly passes the Diataxis test and has no standard place yet.

Temporary documents, such as research, notes and plans, stay out of `docs/`.

A place outside this standard, such as another top-level folder in `docs/`, is an exception. It enters `### Exceptions` as one line with its path and its reason, only after the user approves it; a change that ends the exception removes its line.

A rule for the whole repository goes into `AGENTS.md` under the [agents.md](https://agents.md/) heading that fits its subject, such as `## Code style`, `## Security considerations` or `## PR instructions`, or under a heading of its own when none fits. A rule on the subject of a file in `docs/agents/`, such as a delivery rule or a CI choice, goes into that file.

When in doubt about a place, ask the user.

### Exceptions

## Project overview

Every tracked top-level folder whose name does not start with a dot gets one line: the path and at most one short clause that names the folder's purpose, not its contents. No explanation, rules, status, subfolders, nested lists or file pointers. A new top-level folder adds its line; a removed one removes its line; a change that makes a clause untrue rewrites it in the same change.

- `docs/`: The repository's documentation.
- `LICENSES/`: Canonical license texts.

## Testing instructions

One line per validation or test command and per CI workflow the repository runs. A change that adds, removes or renames a command or workflow, or changes what it validates or tests, adds, removes or rewrites its line in the same change.

- `repository-hygiene` (shared, `v1`): the convention checks of branch names, commit subjects and pull-request titles, the credential scan, workflow validation, Dependabot coverage, the Markdown link check and `reuse lint`
