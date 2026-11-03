# GIANTS Editor MCP publication and license review

Date: 2026-10-17.

Status: historical source audit from 2026-10-17 with unresolved applicability questions. The sources have not been refreshed for this archive. This is not a legal-clearance opinion or a current determination of applicable terms.

## Question and scope

Can an independently written, open-source MCP bridge support a user's installed GIANTS Editor 10.0.14 for FS25 without shipping GIANTS code, assets, binaries, credentials, or configuration files?

The reviewed route uses original Lua, a private Win32 desktop, native Save command
dispatch, bounded inspection, and native PNG rendering. It does not inject or patch
the Editor in the intended product. Earlier binary analysis and Frida hooks were
diagnostic research only.

This review covers publication and distribution risk. It does not decide contract enforceability, mandatory law, or whether private use has an exemption.

## Audit conclusion

No reviewed source expressly bans an independently written MCP bridge by that description. The reviewed texts also do not settle its classification or the proposed automation/publication route. Normal scripting support does not by itself license redistribution of vendor material. This audit cannot turn that gap into blanket permission or a formal ban.

## Source facts

### GIANTS general terms

The public [GIANTS Terms](https://www.farming-simulator.com/termsAndConditions.php?country=gb&lang=en), issued October 2016, concern website offers. Section 3.4 prohibits reverse engineering and related acts for Games; application to Editor 10 is not explicit. Sections 6.1 and 6.2 require a legally acquired game and grant personal Editor use. The terms defer to special UGC conditions where those conflict. The independent bridge and UI automation are not expressly classified. This leaves applicability and permission unresolved, rather than proving a universal automation ban.

### GIANTS Mod terms

The [special Mod terms](https://modhub.giants-software.com/terms.php), issued October 2016, cover Editor/SDK and UGC. Sections 2.2 and 2.3 restrict Editor use to personal use and Mod distribution to free, non-commercial availability unless permitted. Sections 2.5 and 2.6 require Mod labeling and reject implied GIANTS authorship. Section 2.8 restricts Mods outside the games and taking game parts. Sections 3.1 to 3.3 retain author rights while granting GIANTS broad rights in shared UGC. The bridge's classification is unspecified.

### 2026 statement on paid Mods

GIANTS' ["Regarding Mods" statement](https://www.farming-simulator.com/newsArticle.php?campaignIndex=9&country=gb&lang=en&news_id=705) is dated 24 August 2026. It says "Mods have to be free." It forbids paid access,
paid early access, required donations, paid Mod shops, restricted download speeds,
and paid Mod downloads or required assets. It permits voluntary donations,
monetized videos, communities, and official ModHub opportunities.

The statement concerns access to Farming Simulator Mods. It neither licenses
open-source software nor addresses Editor automation, independent tooling, binary
analysis, source inspection, or redistribution of GIANTS material.

### GDN and the public Steam page

[GDN Downloads](https://gdn.giants-software.com/downloads.php) lists GIANTS Editor 10.0.14 for FS25 1.24.0+ with a 13 October 2026 date. The public download index and its footer show no tool EULA or Terms link. The page is a product index, not a grant for automation or redistribution.

The official [Steam product page for app 2300320](https://store.steampowered.com/app/2300320/Farming_Simulator_25/) identifies GIANTS Software as developer and publisher. It shows no public EULA text. The public Steam EULA endpoint returned an error during this review. The installed user's acquisition channel and acceptance history were not established; a public Steam page is not evidence of the agreement they accepted.

Static inspection downloaded the index-linked Editor 10.0.14 installer without executing it. It recorded SHA-256 `edce36547b142fd0391405c75d1acaf29868d3f40e6f517a248b684309f88eef`, version 10.0.14.0, and 43,457,528 bytes. Its Inno Setup archive listing found `readme.txt` but no file named LICENSE, EULA, or TERMS. `--info` reported only English.

**PENDING, limits of that review:** it did not fully decode embedded license-wizard metadata. It cannot establish that the installer contains no EULA, or identify the controlling agreement. Record the actual applicable FS25 and Editor EULA, version, date, and precedence before release. Do not infer it from the Steam page, GDN index, or filename search.

### Local proprietary material

The installed `scripts/editor.lua` and `scripts/editorUtils.lua` begin with a GIANTS copyright/confidential/all-rights-reserved notice. No open-source grant for those files was found. They are not candidates for copying into the bridge. Installed `readme.txt` identifies build 10.0.14 dated 8 October 2026; its SHA-256 is `144fce87190a40f4cedd95acb00c1c733efe90fa67f8f201b251f8524f76a0ad`. The binding reference `scriptBinding.xml` has SHA-256 `efaa702d96e665b3fdb46a9a6f8b9fe62100e8eeab008ee616b096befaa647b2`; a function reference is not a license grant.

### Open source definition

The [Open Source Definition](https://opensource.org/osd) requires licenses to allow free redistribution, derived works, and use in every field of endeavor. Its section 6 says a license cannot prohibit business use. A non-commercial restriction therefore does not meet that definition.

This explains why a non-commercial term cannot describe software as OSD open source.
It does not prove that GPL, MIT, Apache-2.0, or any other license conflicts with the
GIANTS terms. That depends first on the unresolved classification of the bridge and
its files.

## Historical activity and artifact assessment

This table retains the earlier audit's packaging recommendations and uncertainties. It does not establish a blanket product prohibition on diagnostic techniques. Implementation choices follow the [design assessment boundary](../01-design-input/mcp-design.md#executable-integrity-and-legal-assessment).

| Activity or artifact | Technical evidence | Contractual position | Copyright and release policy |
| --- | --- | --- | --- |
| Original bridge Lua | The tested route executes original Lua in an owned Editor session. | Editor personal-use wording applies. Whether bridge Lua is UGC or a Mod is unresolved. | Own code only. Do not copy vendor Lua. |
| Win32 private desktop | POC uses an owned inactive desktop and no input-desktop launch. | Not explicitly addressed; independent-bridge classification is unresolved. | Ship only original Windows interop code. |
| Native Save command | POC records the built-in Save path through a native command. | No explicit independent-bridge automation term established. | Do not ship command tables, vendor code, or binary-derived implementation. |
| Native PNG rendering | POC records built-in viewport output. | Private viewport use and public screenshot redistribution are distinct; the bridge's publication rights are unresolved. | Do not include vendor scenes or screenshots in release fixtures. |
| Private desktop operation | The POC keeps the Editor on a private desktop and minimizes it for sustained work. | No contractual classification found. | Treat as a technical requirement, not vendor endorsement. |
| No hooks in product | Product scope excludes injection and patching. | This reduces the factual link to Section 3.4 but does not create permission. | No DLL, Frida, patch, or binary modification code. |
| Prior Frida and binary research | Earlier work used diagnostic hooks and static analysis only. | Section 3.4 creates unresolved risk if it covers Editor or relevant files. | Exclude raw disassembly, hooks, offsets, and research-only artifacts pending clarification. |
| Vendor binaries, Lua, assets, configs | Local materials carry GIANTS copyright and are proprietary inputs. | The terms bar taking parts from games. | Never redistribute them. Generate a clean synthetic fixture. |
| Derived behavior and identifiers | Research produced facts such as observed Save behavior and function names. | No source decides their legal status. | Do not call them illegal. Exclude unnecessary addresses and vendor-derived detail pending clarification. |

## Historical product-package recommendations

These recommendations concern a distributable product package. The separate historical research archive includes original diagnostic code and derived executable-address records; inclusion here is not a product requirement or a legal-clearance conclusion. The design records the current development assessment boundary.

Keep the bridge source tree limited to original code, original tests, a synthetic
fixture, user-written documentation, and reproducible build metadata. Require each
user to install and point the bridge at their own licensed Editor and game.

Do not bundle the Editor, game, SDK, downloaded GDN packages, vendor Lua, extracted
archives, vendor XML or configuration templates, I3D assets, screenshots from vendor
scenes, logs, credentials, raw disassembly, Frida scripts, binary offsets, or
copy-protection workarounds.

State only that the bridge is independent and requires user-installed software. Do
not use GIANTS or Farming Simulator logos. Do not describe it as official, endorsed,
or part of Farming Simulator. Treat any compatibility wording and required
attribution as subject to the applicable trademark framework.

## Uncertainties and next steps

The exact applicable EULA, contractual scope, Mod/UGC classification, trademark use, automation permission and mandatory-law effects remain unresolved in the historical audit. Before a product release, review actual code, fixture rights, dependency obligations and final license under the repository publication policy. This archive does not establish a vendor-contact prerequisite.

## Archive context

This report records the 2026-10-16/17 research against the pinned Editor build. Raw assets, screenshots, configurations and machine logs referenced under `.docs/` are local-only and are not distributed. Reproduction commands retain their historical workspace assumptions; read the [instrument index](../07-instruments/README.md) before adapting or running them.
