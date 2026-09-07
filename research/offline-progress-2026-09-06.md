# September 6: offline progress and remaining work

**Follow-up completed:** the three translations listed as pending below have
now been implemented. The current package has eleven adapted inputs, unchanged
grass, and fifteen aliases. See [the completed translations and validation](translations-complete-2026-09-06.md).
The rest of this page records the earlier eight-input checkpoint.

The project still has unresolved darkening and visual artifacts. Today's work
extends the material compatibility layer and prepares measurable follow-up
tests. No game was launched, no computer-use tools were used, and no real game
files were changed.

## Completed

`build_preset_adapters.py` uses the recovered **exact 1.0.4.0 identities** for
all twelve preset inputs. It reconstructs every original program and the entire
original-to-preset delta with D3DX assembly before attempting a modern adapter.
It pins the exports, source/preset/target programs, adapted bytecode, and every
container in the complete 103-container modern variant. Missing containers,
changed programs, scratch-register conflicts and alias collisions stop the
build before publication. Installed assembly hashes use deterministic LF bytes.

The reviewed recipes are in
[modern-preset-adapters.json](contracts/modern-preset-adapters.json).
The older three-terrain backend remains available for reproducing historical
experiments. The new backend accounts for every input:

| Original preset input | Current result | Modern aliases |
|---|---|---|
| `psh0CBF49C5` | Terrain delta built | `pshC0223F26` |
| `psh405ABC1B` | Terrain delta built | `psh07FE34FB` |
| `psh841FD9AE` | Terrain delta built | `pshD3E7B05D` |
| `psh2DF967C6` | Alpha material delta built for cutout, default and both wire passes | `pshD27C2451`, `pshB59C0F9F`, `psh89F19EB7`, `psh5FF05F86` |
| `psh323E9BB8` | Default/cutout diffuse delta built | `psh534939FB`, `psh54B11AF3` |
| `pshF5256B40` | Specular material delta built | `psh38133605` |
| `psh8DB4CDB2` | Normal/specular material delta built | `psh830C2AC8` |
| `psh46A43A9F` | Billboard shadow wind delta built | `pshBD733B58` |
| `psh71CC11CF` | **No preset delta:** complete program equals original grass | No alias needed |
| `vsh54F25463`, `vshC35A5E05` | Light-shaft translation pending | None published |
| `psh22DCDB69` | Secondary composite `/10` translation pending | None published |

This is **eight inputs adapted, one unchanged, three pending**; twelve modern
aliases are generated because several material inputs cover multiple programs.
It is shader-file coverage, not a rendering-quality percentage.

The material adapters insert the preset's detail calculations into the modern
programs. They preserve modern alpha coverage, normal reconstruction, G-buffer
outputs and logarithmic depth. The normal adapter moves its sampled normal
work to `r3`; `r1.x` stays available for modern coverage. The specular adapter
also accounts for the modern reassignment of the shininess/specularity
components. Their new scratch registers must be unused in the pinned inputs.

The billboard's modern VS is shared by `wd_draw` and `wd_masked_draw`. Changing
that VS would unintentionally change the masked pass. Its adapter instead
doubles the already interpolated wind factor in the `wd_draw` pixel shader
and applies the original offset ratio `0.001 / 0.0015625 = 0.64`. Modern
imposter-size scaling, alpha rejection and shadow moments remain intact.

These surface adapters require ENB's detail texture at `s13`; normal/specular
detail also consumes ENB's `c199.x`. Their values and the resulting image still
need runtime verification. No replacement texture, guessed constant or exposure
override was added.

Artifacts are in **`build/modern-preset-adapters-v3`**. The
[build manifest](evidence/2026-09-06/modern-preset-adapters.json) records all
program hashes, edits, named-pass audits and the full collision scan.

## Dark-output diagnostics

There are still no automatic postfx texel captures available in the real game
directory. The September 5 darkening cannot be attributed to a measured input
fault yet. The existing `Diagnose` action remains the capture mechanism.

`analyze_postfx_capture.py` now supplements the raw reader with:

- All four log-depth provider components checked against the clip planes.
- Converted depth compared with the CPU reference on matching texel grids.
- Nonpositive or nonfinite adaptation values and nonfinite constants/output
  identified explicitly.
- The effect's observed `HDR / adaptation.red * 0.06` intermediate reported
  for uniform sampled adaptation. Spatially varying adaptation is left
  unevaluated because the grids do not reproduce texture filtering.
- Missing captures rejected; zero sampled output reported as an observation.

This does not evaluate the complete compiled effect, establish a darkening
cause, or claim that the composite boundary is the final presented image.

```powershell
python tools/shader_dump/analyze_postfx_capture.py '<GTAIV/ENBCompat/postfx-run-directory>' --out build/postfx-analysis.json
```

## User-run follow-up, in order

1. **Measure the dark composite first.** Preserve the same indoor scene and
   bridge configuration. `RestoreEffect` recovers the earlier original effect;
   `Diagnose` arms automatic captures. Collect that baseline, then compare the
   original iCEnhancer effect using the existing effect-only switch and another
   capture. See [the bridge procedure](postfx-bridge.md). Keep the new material
   aliases unstaged during this pair so the effect remains the changing variable.
2. **Test the new material adapters separately.** The new helper preflights the
   complete modern shader package, ENB wrapper and active bridge settings,
   saves a separate per-file snapshot, installs twelve aliases, and verifies
   the copies. It changes only those aliases. Compare the same scene and later
   add normal/specular surfaces, fences/wires, terrain and billboard shadows.
3. **Finish light shafts.** Modern FusionFix replaces the old `c2.w` scale use
   with a settings-dependent `c5` interpolation and adds fog/vertex outputs;
   one pass also changes the named sampler. Simply changing the old literal
   would leave its important modern use untouched. Establish the intended
   interaction with those modern providers before publishing either VS alias.
4. **Finish the secondary composite.** `psh22DCDB69` maps to `/10` (slot 12),
   which has ten relocated named inputs. The existing final-composite bridge
   admits slots 13, 15, 25, 27 and 29. Slot 12 requires its own complete input,
   depth and effect-delta translation.
5. **Validate the full rendering matrix**, including outdoor day/night, rain,
   vehicles, water, vegetation, transitions and device recovery. Only then
   generalize presets or proceed to the plan's DXVK phase. The optional
   iCEnhancer ASI crash/hook investigation remains separate.

With GTA IV closed, run the material test from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/gamesetup/Invoke-ModernMaterialTest.ps1 -Kit 'C:\temp\enb-revisit\user-test-kit' -Action Apply
```

Use the same command with `-Action Restore` to restore its original aliases.
Restore this material snapshot **before** using the older bridge or alias-kit
restore. They are separate snapshots and do not remove these twelve files.

## Reproducible verification

The [verification record](evidence/2026-09-06/offline-validation.json) also
records eight full-builder rejection checks and the current Release ASI hash.

- **57 Python tests pass**, including exact edit rejection, scratch-register
  conflicts, corpus completeness/collisions, actual specular-recipe arithmetic,
  wind scaling and numeric capture diagnostics.
- All twelve original/preset programs assemble and reproduce their complete
  audited deltas; all twelve generated modern aliases assemble and match
  their pinned bytecode. The full 103-container collision scan passes.
- **Win32 Release builds** with post-build installation disabled. Warnings
  are the existing missing third-party PDB warnings.
- The production-header native test passes state restoration, COM balance,
  dispatch/recursion, façade validation, readback, scheduling, five modern
  shader identities and the real comment-stripped slot-13 program. It creates
  no graphics device.
- The synthetic material setup test passes Apply/reapply/Restore/repeated
  Restore. Missing packages, changed stage assets, stock-profile settings and
  corrupt backups are rejected before mutation. Original and unrelated files
  survive restoration. Fixture and action logs remain under
  `build/material-setup-test-b66bc438bc544640b4cae67b48f5cdac`.

Run the new builder from the repository root:

```powershell
python tools/shader_dump/build_preset_adapters.py --legacy-exports build/legacy1040-exports/old --modern-exports build/legacy1040-exports/modern --preset 'C:/temp/enb-revisit/icenhancer40/iCEnhancer/shaderinput' --modern-corpus 'C:/Games/Steam/steamapps/common/Grand Theft Auto IV/GTAIV/update/common/shaders/win32_30' --assembler 'C:/temp/enb-revisit/shader-assembler-2/assemble_shader.exe' --out '<new directory>'
```

Run the reusable synthetic setup test using the same read-only reference inputs:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/gamesetup/Test-ModernMaterialSetup.ps1 -Stage build/modern-preset-adapters-v3 -ModernCorpus 'C:/Games/Steam/steamapps/common/Grand Theft Auto IV/GTAIV/update/common/shaders/win32_30' -EnbWrapper 'C:/Games/Steam/steamapps/common/Grand Theft Auto IV/GTAIV/d3d9.dll'
```
