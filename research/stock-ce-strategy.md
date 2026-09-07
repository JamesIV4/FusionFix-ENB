# Stock CE shader strategy — September 7, 2026

ENB mode now uses **stock Complete Edition shaders exclusively as the game
baseline**. The compatibility layer translates the original preset's changes
to those base-game programs. It does not accommodate FusionFix shaders.

The modern postfx/device bridge, private ENB constant-flush call, logarithmic
depth converter, extended-tree compatibility shader, modern delta recipes,
mixed-package staging and their old installation/capture workflows are removed
from active code. Historical research is marked as superseded.

## Native boundary

`rendererprofile.hxx` governs fourteen shader-only feature groups. ENB mode
forces all fourteen off; old INI overrides cannot turn them back on. Normal
Mode 0 keeps the upstream renderer defaults.

The groups cover replacement shaders/preloading, extra constant uploads,
postfx/AA/AO/sun-shafts, pre-alpha depth, sky split, gamma blit, shadow/G-buffer
resource contracts, shader-dependent render-state tweaks, reflection shaders
and the snow shader pass. The extended-tree exception is gone.

Gameplay, camera, input, timing, save/UI/content-loading modules remain intact.
Mixed modules retain their non-shader logic: vehicle dirt/spawn rules, mirror
camera-plane correction and rain-setting reads. Native shadow-caster flags and
night-shadow logic remain available; replacement formats/ranges/matrices do not.
The user confirmed that shadow tuning need not block the first shader test.

## Exact stock selection

The compiled ASI whitelist contains **339 files** from the CE 1.2.0.59 baseline:
102 `win32_30_nv8` containers, 133 shader definitions, 103 declarations and the
original preload list. Every file is checked by full SHA256 before initialization.
Changing a local manifest cannot authorize different shader bytes.

The loader maps 849 logical file paths to that verified cache: six variant paths
for each container, plus the shared definitions/declarations/preload list.
FusionFix's normal update content stays on disk and available for non-shader
fixes and Mode 0. Added extended-tree resources are explicitly excluded.

This uses Ultimate ASI Loader's public `AddVirtualPathForOverloadW` API, whose
export is present in the installed loader; its interface and mapping behavior
were checked against the [upstream implementation](https://github.com/ThirteenAG/Ultimate-ASI-Loader/blob/master/source/dllmain.cpp).
No ENB device offsets or private entry points are used. A missing, changed or
unusable baseline stops ENB startup; it cannot fall back to FusionShaders.

## Exact translations

All twelve original preset inputs are accounted for: **eleven translated
inputs and unchanged grass**, producing **eleven aliases**. Several CE slots
share identical raw programs, so they share an alias; the former fifteen-alias
count came from distinct FusionFix programs and is retired.

| Original input | Stock CE alias |
|---|---|
| `psh0CBF49C5` | `pshA5F4E880` |
| `psh405ABC1B` | `pshFDFF185D` |
| `psh841FD9AE` | `psh1D661524` |
| `vsh54F25463` | `vsh9EC48C3F` |
| `vshC35A5E05` | `vshF40198F6` |
| `psh22DCDB69` | `psh3185A5E0` |
| `psh2DF967C6` | `pshB3377693` |
| `psh323E9BB8` | `psh12A8C432` |
| `pshF5256B40` | `psh216B7814` |
| `psh8DB4CDB2` | `psh573DE346` |
| `psh46A43A9F` | `psh18B040CA` |
| `psh71CC11CF` | No preset change; retain CE grass |

The original and CE light-shaft executable token streams are **exactly equal**.
Their full blobs differ in compiler comments, which are retained in the separate
raw identities used for ENB filename routing. No similarity score is used.

Six complete generated programs (terrain, both light shafts and secondary
composite) must exactly equal the original assembled preset token streams.
The secondary composite now keeps the CE/legacy depth interface and all original
edge-filter changes, including the preset's 0.45 threshold; no modern interface
conversion or alternate bloom/HDR pipeline remains.

The four material adapters preserve the CE instructions outside the explicit
preset changes, including CE's native coverage/normal/output behavior. The
preset's signed-zero edit is mapped to the corresponding CE constant component.
The billboard adaptation accounts for CE's packed wind input and shadow-moment
output while keeping its shared stock vertex shader. These are **CE interface
adaptations**, with exact inputs, edits and outputs pinned; no FusionFix program
or provider is retained.

For every adapter, the build checks raw source/preset/target hashes, exact
original-to-preset reconstruction, named-pass mapping, complete output hashes,
and byte-for-byte identity of every unedited CE instruction. The full
102-container stock corpus is checked for alias collisions. FusionShader-marked
input is rejected even if a supplied manifest tries to authorize it.

Contracts: [baseline](contracts/stock-ce-baseline.json),
[translations](contracts/stock-ce-adapters.json), and
[current runtime alias identities](contracts/ce-shader-aliases.json).

## Package and verification

The ready package is **`build/stock-enb-v1`**. The
[setup helper](../tools/gamesetup/Invoke-StockENBTest.ps1) preflights originals,
cache, aliases and ENB wrapper, snapshots affected files, installs the new ASI
and stock resources, and removes known retired modern aliases/bridge assets.
Non-shader INI values, ENB effects and normal FusionFix content are preserved.
Restoration recovers the exact pre-test files.

Native Release build, the production profile/routing test, stock shader tests
and synthetic Apply/reapply/Restore checks pass. Damaged stage files, original
baseline files and backups are rejected before mutation. The
[verification record](evidence/2026-09-07/stock-ce-validation.json) and
[adapter manifest](evidence/2026-09-07/stock-ce-adapters.json) preserve the evidence.

No computer use, actual game launch or real-game file change occurred.
**Rendering correctness, darkening and artifacts still need a user-run game
test.** Follow [the setup instructions](../docs/ENBCompatibility.md). The earlier
modern-pipeline experiments do not count as validation of this new baseline.
