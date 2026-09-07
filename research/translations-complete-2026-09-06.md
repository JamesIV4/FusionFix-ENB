# All preset translations implemented

The three remaining translations are complete and assembled. All twelve
original iCEnhancer inputs are now accounted for: **eleven adapted inputs,
one unchanged grass shader, zero pending translations**. They produce fifteen
modern shaderinput aliases in **`build/modern-preset-adapters-v4`**.

This completes the offline translation work. The reported darkening and visual
artifacts still need game captures and visual validation. No game was launched
or modified, and no computer-use tools were used.

## The final three adapters

| Original input | Modern alias | Translation |
|---|---|---|
| `vsh54F25463` | `vsh6871A11C` | Complete light-volume geometry delta, with preset radius scale 2 and modern smoothing/fog retained |
| `vshC35A5E05` | `vsh2EE562FD` | Complete occluded light-volume delta, including radius scale 100, changed angular/occlusion constants and intensity; modern sampler/fog retained |
| `psh22DCDB69` | `pshDEB9B5B7` | Composite `/10` effect delta applied to its modern input, depth and output contracts |

The [complete manifest](evidence/2026-09-06/completed-translations.json) records
all fifteen aliases, program hashes, edit blocks, named-pass mappings and
the 103-container collision scan. The executable recipes remain in
[modern-preset-adapters.json](contracts/modern-preset-adapters.json).

### Light volumes

`source/shaders.ixx` supplies the relevant providers: VS `c236.z` is the
`SmoothLightVolumes` boolean; `c236.y` enables volumetric fog; `c235` contains
its parameters. Modern shaders replace the original radius factor `c2.w`
with a `c5` interpolation. The adapter applies the preset's factor to that
effective radius:

```text
effective_radius_factor = ((1 - smooth) * 0.662 + smooth * 0.85)
                          * preset_factor / 0.662
```

With smoothing off, this gives the preset's exact scale of 2 or 100. With it
on, the modern smoothing correction remains proportional. The other original
preset edits are applied unchanged. Fog attenuation, projection and modern
depth interpolators remain intact. The occluded variant retains the modern
`gDeferredLightSampler1` binding at vertex sampler s0, including FusionFix's
existing occlusion fix; no missing legacy sampler resource is introduced.

### Secondary composite

Slot 12 already supplies the modern inputs and decodes logarithmic depth.
Its adapter therefore runs directly through ENB's shaderinput substitution;
it does not require the canonical slot-13 interface conversion. The native
router test verifies that both its original and adapted programs bypass that
separate bridge.

Every part of the preset delta has an explicit disposition:

- Change the local averaging/DOF/bloom weight from 0.25 to 0.1 at its modern uses.
- Remove `ToneMapParams.z` and bloom clamping, including the corresponding
  operations in FusionFix's luminance-based bloom branch. Exposure, adaptation
  and the bloom threshold remain active.
- Remove the original desaturation, color correction/shift and doubling steps.
- Apply the preset's RGB power 0.45 while preserving its adaptation-derived
  luminance exponent. Modern `c18.y` already holds exactly that float literal.
- Preserve the modern phone-camera coordinate correction, paired vertex shader,
  log-depth decoder, luminance-variance filter, bloom-mode selection, PQ/LUT
  output and alpha=1.

The old preset also changes `c4.w` in a G-buffer-alpha edge-filter threshold.
Modern `/10` has replaced that entire filter. Its `c4.w` now represents a
half-texel sampling offset, so changing it would break the modern input layout.
That retired threshold has no modern operation to patch; the modern filter is
retained, while the 0.45 tone-power change is translated explicitly. The adapter
does not restore the retired filter or reinterpret modern G-buffer alpha.

## Verification

**67 Python tests pass.** New tests execute the actual shader instruction
fixtures with an independent CPU arithmetic model and texture functions:

- 53 finite light-volume cases match the complete original preset outputs
  with smoothing/fog disabled. Both light types' modern outputs, smoothing
  behavior and enabled fog are checked separately.
- One zero-length original geometry case yields undefined arithmetic in both
  programs; the test records it explicitly instead of reporting valid rendering.
- 120 composite cases match independent effect equations across depth, HDR
  intensity, bloom intensity, both bloom modes and HDR/LUT output.
- Declaration, coordinate/depth and HDR-output blocks remain unchanged.
- The builder checks these fixtures against the real pinned shader exports,
  so numerical tests cannot silently exercise a different program.

The arithmetic model covers the required instruction subset and preserves
destination masks, scalar replication, texture LOD and SM3 sine/cosine behavior.
Those semantics follow Microsoft's [write-mask](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx9-graphics-reference-asm-ps-registers-modifiers-write-mask),
[power](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/pow---ps),
[sine/cosine](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/sincos---vs)
and [vertex texture sampling](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/texldl---vs)
references. It does not emulate GPU precision, texture filtering or driver
behavior outside the specified arithmetic domain.

All original/preset comparisons and fifteen adapted programs pass D3DX assembly
and pinned bytecode checks. The complete 103-container collision scan passes.
Win32 Release builds with installation disabled, and the native production-header
state/router/readback tests pass, including the secondary-composite bypass.
The [verification record](evidence/2026-09-06/completed-translations-validation.json)
records these results and the artifact hashes.

## Installation and restoration prepared

The existing `Invoke-ModernMaterialTest.ps1` now defaults to the complete v4
stage. It can extend an existing twelve-alias snapshot to fifteen while retaining
every original backup. It saves originals for the added aliases and atomically
commits the expanded manifest before installation. A smaller stage is rejected
until restoration, preventing leftover aliases from silently surviving a downgrade.

Fresh installation and the v3-to-v4 upgrade both pass synthetic tests, including
repeat application, exact restoration, invalid packages/assets/settings/backups,
and upgrade rejection before mutation. The real game is unchanged.

For a controlled comparison, capture the existing bridge/effect first, then
apply the complete aliases while keeping that effect unchanged. When ready to
run the game checks, use this command from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/gamesetup/Invoke-ModernMaterialTest.ps1 -Kit 'C:\temp\enb-revisit\user-test-kit' -Action Apply
```

The same command with `-Action Restore` restores the original aliases, including
those added during an upgrade. Restore this snapshot before the separate bridge
or original alias-kit snapshots. For numeric investigation of the dark output,
continue with [the postfx capture procedure](postfx-bridge.md); shader translation
completion does not establish that the full preset renders correctly.
