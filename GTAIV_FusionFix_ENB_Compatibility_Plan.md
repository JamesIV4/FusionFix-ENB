# GTA IV Complete Edition + FusionFix: stock-shader ENB plan

## Required boundary

ENB mode must use **unmodified stock Complete Edition shaders as its baseline**.
Every FusionFix modern shader change, custom shader pass, extra constant provider
and dependent GPU resource modification is disabled. There is no extended-tree
exception, mixed shader package, log-depth converter or modern postfx bridge.

FusionFix's gameplay, camera, input, timing, saves, UI/content loading and other
non-shader fixes remain available under their existing settings. Normal Mode 0
retains FusionFix's renderer. Do not solve an ENB problem by reviving FusionShaders.

## Acceptance standard

- Pin raw shader and preset SHA256 identities, including comments for ENB routing.
- Verify original-to-preset changes and target mappings exactly; no similarity
  score is sufficient to select or approve a replacement.
- Require every unedited CE instruction to retain identical bytecode.
- Require exact complete preset-program equality where the interfaces permit it.
- Record explicit CE adaptations where the base game changed its interface.
- Keep build/assembly proof separate from in-game rendering proof.

## Implemented September 7

- [x] ENB profile forcibly disables all fourteen FusionFix shader feature groups;
  old per-feature overrides cannot re-enable them.
- [x] SHA256-pinned stock baseline: 102 CE shader containers, 133 definitions,
  103 declarations and the original preload list (339 files).
- [x] File mappings select those exact originals for all six shader variants,
  retaining FusionFix's normal update content and non-shader fixes.
- [x] Remove the private ENB flush/device bridge, modern depth conversion,
  extended-tree workaround, modern adapters and their installation workflows.
- [x] Translate the preset to stock CE only: eleven aliases, unchanged CE grass,
  all twelve original preset inputs accounted for.
- [x] Build and test a reversible stock-only setup/migration package.
- [x] Verify native build, exact shader edits, baseline routing and synthetic
  installation/restoration. See [the current record](research/stock-ce-strategy.md).

## Remaining validation

1. User-run startup and a matched indoor scene with the new stock package.
2. Verify active stock shader identities and ENB substitution with optional
   creation/bind dumps; do not infer correct rendering merely from a successful draw.
3. Diagnose darkening and material artifacts against that stock baseline.
4. Expand to terrain, foliage, reflective surfaces, the secondary composite,
   weather and shadow scenes. Shadows need not block the first shader test.
5. Verify gameplay/camera behavior and normal-mode restoration.

Full rendering compatibility remains unverified. No game launch or computer
use was performed during this implementation. Current setup:
[docs/ENBCompatibility.md](docs/ENBCompatibility.md).

The previous strategy is retained only as
[historical research](research/history/plan-through-2026-09-06.md).
