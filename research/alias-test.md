# User-run test: CE terrain shader filename bridge

**Paused on 2026-09-05 at the user's request.** Review of the regular ENB
baseline found tree-provider and shadow/G-buffer compatibility gaps. A repaired
FixedBaseline is now staged for user validation; run that before continuing
these identity/effect tests. See [regular-enb-review.md](regular-enb-review.md).

With GTAIV closed:

```powershell
$kit = 'C:\temp\enb-revisit\user-test-kit'
& 'S:\Repos\FusionFix-ENB\tools\gamesetup\Invoke-ShaderAliasTest.ps1' -Kit $kit -Action FixedBaseline
```

This restores regular ENB shaderinput, installs the rebuilt stock-depth tree
container and current ASI, disables the modern shadow/G-buffer/FusionShader
tweaks, keeps tree alpha/wind constants, and verifies the installed hashes. The
script does not launch GTAIV. Compare the same daytime scene with trees and the
building-side ground strip, then exit and retain ENBCompat.log plus a screenshot.

The user has run **Baseline** and confirmed an outdoor scene loads, with strong
over-brightening still present (September 4, screenshot 20260904210046_1.jpg).
The corrected **Probe** run is also positive: a conspicuous magenta ground strip
appears beside buildings in
[screenshot 20260904223905_1.jpg](evidence/2026-09-04/user-terrain-probe.jpg). Read-only inspection
confirmed all three installed probe files exactly match the kit. This proves
runtime substitution for at least one terrain alias, but the combined probe does
not distinguish the 2-, 3-, and 4-layer programs. The earlier search with the
probe files absent remains an invalid negative control. **Aliases** now also
loads: the same strip is textured rather than magenta, though it appears faded
and other rendering failures prevent a clean quality judgment. Automatic trace
capture is next; Effect remains untested. The prepared
kit is `C:\temp\enb-revisit\user-test-kit`. It contains ENB 0.163, the existing
compatibility build, a stock shader overlay, three iCEnhancer terrain aliases,
a separate magenta probe, and the original iCEnhancer postfx effect. No
iCEnhancer ASI is included. Full iCEnhancer compatibility remains unproven.

## First, test only the baseline

Close GTAIV. In PowerShell:

```powershell
$kit = 'C:\temp\enb-revisit\user-test-kit'
& "$kit\Invoke-ShaderAliasTest.ps1" -Kit $kit -Action Baseline
```

Then launch GTAIV yourself through the usual launcher. Set **Depth of Field to
Low or higher** and load an outdoor save. The setup has `API = 0`, ENBLegacy
mode, stock shaders, tracing disabled, no version spoof, and no iCEnhancer ASI.
It does not change the game settings file or start the game. A bright image may
still reflect the default ENB tuning; first establish whether it loads a scene.

**If this crashes or cannot load a scene, stop here and report that result.**
Retain ENBCompat.log and any newly written GTAIV crash dump. The September 4
failed launch used tracing and a different shaderinput set, so it is not a
valid control for this kit. Do not mix additional preset components into a
failing baseline.

## Then test the recovered filenames

Use the updated repository script for Probe; the older script copied into the
kit does not include installation hash verification. After closing GTAIV:

```powershell
$kit = 'C:\temp\enb-revisit\user-test-kit'
& 'S:\Repos\FusionFix-ENB\tools\gamesetup\Invoke-ShaderAliasTest.ps1' -Kit $kit -Action Probe
```

Before launching, it must print **Verified all three magenta probe files** and
list `pshA5F4E880.txt`, `pshFDFF185D.txt`, `psh1D661524.txt`, then **Probe files
ready**. If it does not, retain the console output; more terrain searching will
not resolve missing setup files. This script update has only been inspected
and parsed offline, not executed against the game by the assistant.

Launch and revisit the same outdoor view, ideally somewhere with blended dirt
or grass **ground surfaces**, such as a park. The diagnostic forces diffuse RGB
to magenta in three terrain shaders while preserving their other GBuffer outputs.
The expected observation is conspicuous magenta ground where those passes draw.
It does not target every road, object or grass blade. Lighting/post-processing
can affect the visible shade. No visible change in one location is inconclusive.

This is a deliberate color probe, not the intended iCEnhancer appearance. It has
now appeared in a verified run. Close the game and switch to the actual preset
assembly:

```powershell
& 'S:\Repos\FusionFix-ENB\tools\gamesetup\Invoke-ShaderAliasTest.ps1' -Kit $kit -Action Aliases
```

Revisit the same view. This uses unchanged iCEnhancer program bytes under the new
filenames. The user has confirmed the magenta disappears and textured terrain
returns. Its fade is visible, but other broken rendering prevents a reliable
image-quality verdict. Evidence:
[user-terrain-aliases.json](evidence/2026-09-04/user-terrain-aliases.json).
The other five static candidates and four unresolved files remain outside this
first test.

## Automatic runtime audit

The tracer now records every created shader and the first time each shader is
actually bound. Expected iCEnhancer assemblies are precomputed with the same
`D3DXAssembleShader` API and zero flags used by ENB 0.163. This replaces visual
color hunting with exact bytecode and bind evidence.

With GTAIV closed, prepare the current three-alias trace:

```powershell
$kit = 'C:\temp\enb-revisit\user-test-kit'
& 'S:\Repos\FusionFix-ENB\tools\gamesetup\Invoke-ShaderAliasTest.ps1' -Kit $kit -Action TraceAliases
```

The script installs the freshly built tracing ASI, keeps the normal aliases,
archives old diagnostics, enables shader dumps, and writes a session manifest.
Launch GTAIV yourself, load any ordinary scene, move around briefly, then exit
normally. No particular terrain or screenshot is required. After exit:

```powershell
& 'S:\Repos\FusionFix-ENB\tools\gamesetup\Invoke-ShaderAliasTest.ps1' -Kit $kit -Action CollectTrace
```

Collection copies the trace into a timestamped `trace-runs` directory and prints
one status per alias: exact bound, exact created but not bound, not encountered,
or bytecode mismatch. It does not start or attach to the game.

## Separate effect test

After the baseline works, this action tests only the original compiled
iCEnhancer `enbeffect.fx`, resetting shaderinput to the original ENB baseline:

```powershell
& 'S:\Repos\FusionFix-ENB\tools\gamesetup\Invoke-ShaderAliasTest.ps1' -Kit $kit -Action Effect
```

DOF stays enabled. Record whether the scene loads, whether post-processing
changes, and any crash. This test isolates effect loading from terrain aliases
and from the ASI. It does not include the full preset's bloom, clouds or assets.

## Restore

Close GTAIV, then:

```powershell
& 'S:\Repos\FusionFix-ENB\tools\gamesetup\Invoke-ShaderAliasTest.ps1' -Kit $kit -Action Restore
```

The script snapshots every potentially touched file, including whether it was
originally absent, before applying the first phase. Each phase starts from that
snapshot plus the same baseline. Restore validates backup hashes, restores
original files, removes only files introduced by the kit, and removes newly
created directories only if empty. It preserves unrelated files and diagnostic
logs. Settings you change manually in the game remain your settings.

Keep the kit and its `snapshot` until restoration is complete. Use this script's
Restore action for this test, **not the older ENBCompat-Restore.cmd**: that older
helper deletes entire variant directories, including ones that may have existed
before its test. This kit requires the restored setup and refuses an existing
win32_30_nv8 overlay rather than merging another active experiment.

The script was parsed and reviewed offline. The user has now executed Baseline
and Probe successfully; Aliases, Effect and Restore remain untested. The
assistant did not operate the game during these user-run tests.

## Rebuild the kit elsewhere

From the repository root, with the archives extracted:

```powershell
python tools/shader_dump/prepare_alias_test.py --game '<GTAIV folder>' --enb '<ENB Wrapper version>' --ice '<iCEnhancer root>' --out '<new directory outside game>'
```

This only reads source/game inputs and writes the kit. It pins the researched
ENB wrapper, the terrain shader and preset SHA256 values, and checks the selected
stock nv8 variant. The generated manifests record all staged file hashes.
Prepared config files derive from the current FusionFix ini; the user-run
script refuses setup if the original ini, game executable or FusionFix binary
changed after preparation. Rebuild in that case.

Evidence and limitations: [legacy-shader-bridge.md](legacy-shader-bridge.md).
