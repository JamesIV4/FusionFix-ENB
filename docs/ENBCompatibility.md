# ENB mode with stock Complete Edition shaders

ENB mode uses the exact stock CE 1.2.0.59 shader baseline. FusionFix's modern
shader package and shader-dependent rendering changes are disabled. Gameplay,
camera, input, timing, save, UI and content fixes remain under their existing
settings. `Mode = 0` retains normal FusionFix rendering.

The old modern-shader adapters, postfx/depth bridge and extended-tree workaround
have been removed. Their old setup commands are no longer supported.

## Prepared package and user-run setup

The current package is `build/stock-enb-v1`. It contains the new ASI, 339 exact
stock shader/definition/declaration/preload files and eleven stock-targeted
shaderinput aliases. The preset's grass program contains no change, so CE's
original grass shader remains active.

With GTA IV closed, run from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/gamesetup/Invoke-StockENBTest.ps1 -Kit 'C:\temp\enb-revisit\user-test-kit' -Action Apply
```

This preflights the stock originals, approved aliases and audited ENB 0.163
wrapper, then snapshots the affected files. It installs the stock cache under
`plugins/ENBCompat/StockCE`, installs the ASI/aliases, removes known retired
modern aliases and bridge assets, and sets `Mode = 1`. Other INI settings,
ENB effects, presets and FusionFix update content are preserved.

The new `stock-ce-snapshot` is separate from the earlier experimental snapshots.
Restore the pre-test files using the same command with `-Action Restore`.
The helper never launches GTA IV. A failed preflight changes no game files.

## What ENB mode disables

- FusionShaders file selection and additional shader preloading, including
  `gta_trees_extended`.
- FusionFix shader constant injection, logarithmic-depth helpers and sky split.
- FusionFix's replacement postfx, AA, AO, sun shafts, pre-alpha copy and gamma blit.
- Replacement shadow/G-buffer formats, cascade ranges and matrices.
- Reflection MSAA/blur shaders and the snow shader pass.
- Shader-dependent reflection, contrast, water-target, refraction, adaptive-state
  and emissive shader-state changes.

Native shadow-caster and night-shadow logic that uses existing game techniques
remains available. Mirror camera-plane, vehicle dirt/spawn and rain-setting
reader fixes are preserved, as are the gameplay/camera/input modules. No whole
non-shader module is disabled to achieve this boundary.

ENB mode no longer accepts per-shader-feature override keys. Old values such as
`FusionShaderPackage = 1` or `ShaderConstantInjection = 1` are ignored by the ASI
and removed by the new setup helper. Non-shader compatibility settings, such as
scoped version reporting for another plugin, are retained.

## Exact baseline selection

The ASI embeds the SHA256 whitelist for all 339 files. Before initialization,
it checks every cached file and uses the ASI loader's file-mapping API to route
shader lookups to that cache. All six native variant paths select the pinned
stock `win32_30_nv8` programs; definitions, declarations and the preload list
also come from stock CE. FusionFix's update folder stays intact for its other
fixes and for normal Mode 0.

A missing or changed cache stops ENB startup with a setup error; it cannot fall
back to modern FusionShaders. The current installed ASI loader exposes the
required mapping API. Mode 0 does not install these mappings.

## Verification and limits

Exact original/preset hashes, complete edit recipes and the unchanged CE
instruction-token checks are recorded in
[the stock CE implementation record](../research/stock-ce-strategy.md).
Native build, headless profile/file-route checks and synthetic setup/restore
pass. These checks do not establish GPU rendering correctness.

First test a matched indoor scene. Keep the effect/preset and game settings
stable so the baseline change is measurable. Shadow tuning can wait until the
basic shader path is validated. Optional `D3D9Trace`/`DumpShaders` diagnostics
remain available; the removed modern input/depth capture path does not.
