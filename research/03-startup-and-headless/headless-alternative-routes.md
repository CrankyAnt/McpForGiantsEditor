# Headless alternative routes for GIANTS Editor 10.0.14

## Question and scope

Can the installed GIANTS Editor 10.0.14, its installed companion tools, the
installed Farming Simulator 25 runtime, or an official GIANTS offering provide
a genuine windowless or headless route for scene conversion, validation or
automation?

This pass did not start an Editor, game, server or tool process. It inspected
the pinned Editor package, the installed game directory and Windows uninstall
registration. It also checked current GIANTS Developer Network pages and a
GIANTS Software forum post. This report does not propose or build an MCP
server.

The Editor target is
`C:\Program Files\GIANTS Software\GIANTS_Editor_10.0.14\editor.exe`,
SHA-256 `c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d`.
The installed game root is `D:\Games\Farming Simulator 2025`.

## Result

No genuine windowless route was established for full-scene Editor work. One
installed executable does expose a concrete batch candidate for textures:
`textureTool.exe` has a console PE subsystem and static command-line tokens
including `-silent`, `-recursive`, `-sourceFiles`, `-targetFile` and `-help`.
This establishes a likely noninteractive texture-conversion route, not a
scene reader, I3D writer, Lua host or rendered scene validator. Its option
semantics and whether `-silent` suppresses every dialog remain untested.

The official batch candidate for mod validation is TestRunner. It was not
installed, so this pass fetched the official FS25 v0.9.22 archive to `C:\\TMP`
without running it. The current archive confirms that it is a console program
with embedded `EditorCheck` and static-Editor-Lua resources. It validates mods
rather than exposing a scene conversion API. Static inspection cannot determine
whether its Editor child creates a user-visible window, so it remains the one
current FS25 route that needs a controlled private-desktop runtime test.

The existing private-Win32-desktop route remains useful when the requirement is
no Editor window on the user's input desktop. It still starts the normal GUI
Editor with its renderer on an inactive desktop, so it is deliberately outside
the headless result.

## Candidate routes

| Route | Sourced fact | Coverage | Headless verdict | Actionable use |
| --- | --- | --- | --- | --- |
| Editor `-logging nogui` | The pinned startup analysis traces this value to a logging-sink constructor flag. It does not suppress application or window setup. | Logging output only. | Reject. It is not a `-nogui` launch mode. | Do not use as an automation or CI switch. |
| Existing private Win32 desktop | The local controlled trials completed scene inspection, native Save, fresh readback and rendering without an Editor window on the input desktop. The Editor frame remained visible on its own desktop and the renderer initialized. | Two copied FS25 assets on this machine and build. | Not headless. | Use only when an isolated normal GUI process is acceptable. |
| GIANTS TestRunner for FS25 | The fetched official v0.9.22 archive contains a CUI `TestRunner_public.exe`, `TestRunner_HowTo.pdf` and changelog. Its embedded `EditorCheck` calls `subprocess.Popen` for Editor with `-noVersionSelection -supressChangelog -disableTextureStreaming -runScriptCode source(<temporary Lua>) -configXML <temporary XML>`, capturing stdout/stderr but supplying no Windows startup or hide flags. | Batch validation of an unzipped mod, including I3D and shader checks. It is not a general scene API. | No documented windowless route. The current arguments request no headless, no-render or hide mode; the child-window result still needs one controlled runtime check. | Test it only on a disposable mod and private desktop. Record child processes and windows, then retain the generated report. Pass exact quoted game and Editor paths because the local game is in a non-default path with spaces. |
| `textureTool.exe` in the Editor package | The package contains `tools\\textureTool.exe` and `textureTool.xml`. Its PE subsystem is `CUI`, it exports no API, and its static option tokens include `-help`, `-silent`, `-recursive`, `-abortOnError`, `-sourceFiles`, `-inputs`, `-targetFile`, `-format`, `-quality` and `-showDialogs`. It also imports GUI DLLs. | Texture conversion only. No I3D, scene, Lua or render operation was identified. | A concrete headless-candidate route for texture work only. It is not yet runtime-proven to avoid all dialogs. | First run `textureTool.exe -help` in an isolated writable directory, retain the exact help text, then test one copied texture with `-silent` and an explicit target. Do not use it for I3D conversion. |
| Editor "Mod Converter" | The installed Editor changelog says 10.0.4 added a converter from FS22 mods to FS25 mods. It names no separate executable, batch switch or library. | FS22-to-FS25 mod migration, not arbitrary I3D conversion. | No headless route established. | Treat it as an Editor feature until GIANTS publishes a command-line contract. |
| Game runtime `FarmingSimulator2025Game.exe -server` | The actual x64 game executable has `-server` plus the usage text `start as dedicated server (optional)`. It also contains internal I3D loader and streamer names. Its PE subsystem is `GUI`, it imports `USER32` and `GDI32`, and its 17 exports are audio/GPU-selection symbols, not an engine or Lua-host ABI. | Running a dedicated game server, subject to a separate runtime test. Internal I3D loading is not a file-conversion API. | No headless Editor route established. The `-server` token warrants a server-specific test, but does not establish windowlessness or arbitrary asset processing. | Use only for a dedicated-server requirement. Do not attempt to load the executable as an engine DLL. |
| Installed `dedicatedServer.exe` | `D:\Games\Farming Simulator 2025` contains `dedicatedServer.exe`, which has no exports and contains server web-feed names. It has no identified scene-load, I3D-save or conversion contract. | Dedicated-server administration, if configured. | No basis to call it a headless Editor or asset pipeline. | Do not use it for Editor conversion or validation. A separate server-administration investigation would be needed for server tasks. |
| GDN exporter and GRLE tools | GDN lists Blender and Maya exporters and a GRLE Converter as separate offerings, not as installed programs. The catalog does not present them as a replacement for Editor scene loading and saving. | DCC export or GRLE-specific conversion, depending on the tool. | Out of scope for existing-asset Editor automation. | Evaluate only for a specific DCC or GRLE input/output requirement. |

## Evidence

### Local package and installation facts

The checked application binaries are:

| File | SHA-256 | PE subsystem | Exports relevant to this question |
| --- | --- | ---: | --- |
| `GIANTS_Editor_10.0.14\\editor.exe` | `c9d70afba98678264c82e06ebaafa3018409e3f4cdd6d4e53e6fa3932817152d` | 2, GUI | 17 exports. They are audio-decoder and GPU-selection symbols, not scene or Lua API. |
| `GIANTS_Editor_10.0.14\\tools\\textureTool.exe` | `5278e582d12fc37e434fc8c328599b94581b66fcd11d2acc656789db3d1ffbef` | 3, CUI | 0 exports. Static command-line tokens identify a texture batch candidate. |
| `Farming Simulator 2025\\FarmingSimulator2025.exe` | `5c3b3116a6c2dc4c1587f16a4c6670ae67a28ea26f26f48b23ee777efdf616f2` | 2, GUI | 0 exports. This is the game launcher. |
| `Farming Simulator 2025\\x64\\FarmingSimulator2025Game.exe` | `18d3e78c2379eb0c301a685cee71d8c0afd89657f0521901455495eb95696daf` | 2, GUI | 17 audio-decoder and GPU-selection exports only. No engine or Lua host ABI. |
| `Farming Simulator 2025\\dedicatedServer.exe` | `422630114f86c6691a3e2b80190cea39302793933a1625a61f201412b7ce3efc` | 2, GUI | 0 exports. No asset-processing ABI. |

All five are AMD64 executables. The game `x64` directory contains graphics,
audio, hardware-integration and Microsoft runtime DLLs, but no file named as a
GIANTS Engine, I3D, Lua, converter or TestRunner library. The `sdk` directory
contains content and scripting references, not a hostable executable or DLL.
This is a filename and PE-export inventory. It cannot prove that no private
internal interface exists inside a process.

The Editor package contains `editor.exe`, `textureTool.exe`, scripts and data
files. `textureTool.exe` is AMD64 with PE subsystem `CUI` and SHA-256
`5278e582d12fc37e434fc8c328599b94581b66fcd11d2acc656789db3d1ffbef`.
It has no exported functions. Its static option strings name a narrow batch
interface: `-silent`, `-recursive`, `-abortOnError`, `-singleThreaded`,
`-disableCacheServer`, `-ignoreTimestamp`, `-sourceFiles`, `-inputs`,
`-normalMapFiles`, `-targetFile`, `-arch`, `-quality`, `-textureType`,
`-colorSpace`, `-format` and `-help`. Its `TextureToolApplication`,
`ITextureConverter`, `DDSConverter`, `ASTCConverter` and `DefaultConverter`
type names support a texture-only interpretation. Static strings cannot assign
the precise grammar, confirm all switches are live, or prove dialog behavior.

The package has no file whose name matches `TestRunner`, `batchconverter`,
`headless` or a public engine SDK. The prior read-only startup
scan also found no standalone `headless`, `-nogui`, `-batch`, `-save` or
`-quit` literal in the pinned startup path. That is bounded static coverage,
not an impossibility proof for dynamically built options or future releases.

Windows uninstall registration lists GIANTS Editor 10.0.12, 10.0.13 and
10.0.14 plus Farming Simulator 25. A recursive executable scan of the actual
game root found the game, dedicated server and crash reporter, with no
TestRunner or separate asset converter. `sdk\\` has content and scripting
reference files, but no `.exe` or `.dll`; the actual engine executable is
`x64\\FarmingSimulator2025Game.exe`. That AMD64 GUI-subsystem executable has
only 17 exports, all audio decoder or GPU-selection names, so it supplies no
public hostable engine or Lua API. A targeted scan of Program Files, Program
Files (x86) and LocalAppData found no `*TestRunner*.exe`.

The game engine's static usage block supplies an actionable but separate
candidate: `-server`, `-scriptDebug`, `-externalScripts`, `-externalScriptsDir`
and display-related switches including `-windowResolution` and `-fullscreenMode`.
It also names `loadI3DFile`, `loadSharedI3DFile` and streaming operations.
These are internal runtime facilities. They do not create a documented C ABI,
do not identify an Editor-style save operation, and were not executed here.

The earlier startup analysis supplies the more specific `-logging nogui`
result. It follows the argument to bit `0x2` of a logging constructor and shows
the skipped log-sink call after surrounding setup. The conclusion is about
that code path, not a generic conclusion from the word "nogui".

### TestRunner v0.9.22 is a current FS25 batch candidate

GIANTS currently advertises the FS25 TestRunner in its own downloads page as
`Farming Simulator 25 Test Runner v0.9.22`, for FS25 1.24.0+ on Windows. The
download link resolves to `download.php?downloadId=162`. This pass fetched that
archive to ignored temporary storage, recorded SHA-256
`eb557ddfc638f7f9c1a06b0cbfa5e2760909e1ee05e7b9c5c3ab058db3667cad`, and
did not execute any file from it.
[GDN downloads](https://gdn.giants-software.com/downloads.php)

The archive has exactly `changelog.txt`, `TestRunner_HowTo.pdf` and
`TestRunner_public.exe`. The executable is AMD64, PE subsystem `CUI`, has no
exports, and imports only `USER32`, `KERNEL32` and `ADVAPI32`. Its PyInstaller
container holds `modules.EditorCheck`, `modules.ShaderCheckEditor`,
`dataCollectors.I3DCollector`, `additionals\\EditorCheck_staticLuaScript.lua`,
`additionals\\ShaderCheckEditor_staticLuaScript.lua` and
`additionals\\editor.xml`. These are current-archive evidence that the FS25
tool runs Editor-oriented checks with bundled Lua and an Editor configuration.

The extracted current `modules.EditorCheck` bytecode constructs this exact
Editor command sequence:

```text
<editor.exe> -noVersionSelection -supressChangelog -disableTextureStreaming
  -runScriptCode source("<temporary loadI3DFiles.lua>")
  -configXML <temporary editor.xml>
```

It then calls `subprocess.Popen(args, stdout=PIPE, stderr=STDOUT)`. The static
call supplies no `STARTUPINFO`, creation flags or Editor switch for hiding,
headlessness or disabling the renderer. This does not prove that the child
will be visible, because Editor can choose its own window state. It proves
that the current TestRunner does not request a Windows-hidden child itself.

The embedded Lua loads each I3D with `loadI3DFile`, links it into the scene,
walks and checks nodes, requests an 8-by-8 `renderScreenshot`, then calls
`editorExit(0)`. The bundled `editor.xml` selects `Vulkan` and the `Very Low`
performance class. It has no null-renderer, headless or window-state setting.
This is direct evidence that the current FS25 EditorCheck expects an Editor
renderer, even at a low profile. It does not identify the final OS window
state.

The temporary analysis inputs were `C:\\TMP\\fs25-testrunner-0.9.22.zip`, its
extracted directory `C:\\TMP\\fs25-testrunner-0.9.22\\`, and the extracted
`PYZ.pyz` inside that directory. They contain vendor material and stay outside
the repository.

The bundled FS25 changelog supplies further version-specific evidence. v0.9.20
states that `-e` resolution for `editor.exe` was fixed and that a Lua-mods check
was added. v0.9.18 says an editor script was changed because its node-linking
method had become deprecated. v0.9.10 says I3D parsing uses a default editor
XML with a very-low hardware profile and does not modify the LocalAppData
editor XML. This is stronger evidence than applying FS22 process behavior to
FS25, but it still does not decide window creation.

The older official FS22 announcement remains useful only for the general
product model: GIANTS describes mod checks, HTML/XML output and Editor-based
validation there. It must not be used to claim current FS25 window behavior.
[GIANTS TestRunner announcement for FS22](https://forum.giants-software.com/viewtopic.php?t=187502)

### Official offerings do not fill the gap

The GDN downloads page separately lists the FS25 TestRunner, exporter plugins,
the older GIANTS Texture Tool v9.0.1, DEM Converter and GRLE Converter. The
locally installed Texture Tool comes with Editor 10.0.14, so the catalog does
not establish that its options match the separately listed v9.0.1 download.
[GDN downloads](https://gdn.giants-software.com/downloads.php)
None of the inspected official catalog text describes a public standalone
headless GIANTS Engine runtime or a command-line full-scene reader/writer.
This is a catalog-level finding. A logged-in download may contain further
documentation, so it does not rule out an undocumented feature.

## Inferences and limits

- TestRunner is a current CUI batch-validation candidate with real embedded
  Editor checks. It drives a normal renderer-enabled Editor command and does
  not request hide flags. A controlled FS25 run must still record the Editor
  child and its windows before treating it as unsuitable for a no-visible-window
  requirement.
- The private desktop route solves user-desktop visibility, not renderer,
  window creation, Session 0, service or GPU independence. Calling it
  "headless" would overstate the evidence.
- `textureTool.exe` has static option tokens consistent with a command-line
  texture tool. Its exact argument grammar, write behavior and dialog handling
  remain untested.
- The dedicated server's presence does not identify a reusable supported
  editor or I3D conversion interface. No process was started, and no claim is
  made about its server launch behavior.

## Remaining routes worth checking only if the requirement changes

1. If "batch validation that may launch Editor" is acceptable, obtain the same
   hash-pinned FS25 TestRunner v0.9.22 archive for one run on a disposable mod
   copy with explicit quoted game and Editor paths. Record the Editor child,
   its windows, renderer behavior and generated report.
2. If only texture conversion is needed, inspect `textureTool.exe -help` in an
   isolated disposable directory and retain its exact output. The binary makes
   this an evidence-backed candidate, but the static scan cannot define the
   input-list grammar or `-silent` behavior.
3. If dedicated game hosting is the goal, test the actual game executable's
   documented static `-server` switch separately. It is not a scene converter
   or reusable engine library.
4. If a normal GUI engine on a non-user desktop is acceptable, keep using the
   bounded private-desktop controller and its version pin. That is the only
   locally demonstrated non-interactive route, but it is not an answer to a
   true headless requirement.

## Sources

- Local, hash-pinned startup and package evidence:
  [startup-flags.md](startup-flags.md),
  [invisible-startup-static.md](invisible-startup-static.md), and the package
  paths stated above.
- Local runtime boundary:
  [invisible-startup-results.md](invisible-startup-results.md).
- Official GIANTS catalog, checked 2026-10-17:
  [GDN documentation](https://gdn.giants-software.com/documentation.php).
- Official GIANTS TestRunner process and validation description:
  [GIANTS Software forum post](https://forum.giants-software.com/viewtopic.php?t=187502).

The temporary downloaded archive and extraction were removed after the completed static analysis. The hashes and derived findings above remain the provenance record.

## Archive context

The original raw inputs were discarded; historical `.docs/` paths are no longer available. See [evidence availability](../../README.md#evidence-and-applicability) for the retained results and limits. Historical commands require new prepared data and reviewed paths; see the [instrument index](../07-instruments/README.md).
