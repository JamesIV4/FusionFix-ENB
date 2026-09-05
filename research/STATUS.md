# Status

As of 2026-09-05. **iCEnhancer 4 is still unproven in game, but the investigation
has a concrete new route.** The earlier impossibility conclusion is superseded
by [the recovered shader bridge](legacy-shader-bridge.md).

**Regular ENB baseline repair ready for user validation:** the review found a
modern tree shader with disabled providers and ungated shadow/G-buffer/state
changes. The new profile restores the stock resource/state path, keeps required
tree alpha/wind constants, and stages a stock-depth extended-tree build. The
earlier conclusion that over-brightening is merely tuning was premature. See
[the review and implementation](regular-enb-review.md). Loading and probe
execution remain verified milestones; corrected rendering is not yet confirmed.

## New evidence

* All three iCEnhancer effects are standard compiled D3D9 effects. A standalone
  Microsoft D3DX9 harness loaded, validated, bound all seven passes and
  disassembled twelve shader programs without ENB or the iCEnhancer ASI.
  Preshaders and named parameters remain accessible. No geometry was drawn.
* Historical FusionFix's exact shader bundle for 1.0.7.0/1.0.8.0/CE preserves
  all twenty stock postfx bindings. Modern FusionFix moves five and adds depth
  dependencies. The old fork's shader creation/bind experiment is commented
  out; it supplies useful interfaces, not a ready ENB hash/address table.
* ENB 0.163's packed wrapper was decoded **offline without executing it**.
  Its actual hash is reflected CRC32 without final XOR, over raw bytes before
  the first aligned END word. Version and comments count. Both vertex and pixel
  paths were inspected. `d3d9bc.py` now reports this as `enb163`.
* The postfx handler recognizes six hashes. Stock CE rage_postfx#13 is
  **AA1C0C36**, already recognized; C215BE6E is the canonical effect name.
  Stock #29 is 2D5D52B3 and is absent from that chain. This supports the earlier
  finding that DOF must be enabled for ENB's postfx path.
* None of iCEnhancer's twelve original shaderinput filenames matches any of
  10,134 stock shader blobs across six variants on disk. Modern FusionFix's
  1,739 win32_30 blobs match none of those filenames or the six postfx hashes.
  Matching normalized assembly bodies is **not** matching raw shader identities.
* Three strongly supported terrain filename aliases are staged outside the game,
  with a separate magenta diagnostic probe. Five weaker candidate aliases are
  optional; four unresolved files are excluded. SHA256 guards reject changed
  preset/stock inputs, modern FusionFix inputs, and ambiguous hash collisions.
* The user's corrected terrain Probe run produced a localized magenta ground
  strip with all three staged CE aliases verified in place. At least one recovered
  CE filename therefore triggers ENB substitution. Because all three probes were
  active, the individual 2-/3-/4-layer mapping is not isolated yet.
* The following Aliases run removed the diagnostic magenta and restored textured
  ground at the same corridor. The user sees fading near its street boundary,
  but broader broken rendering prevents a clean correctness judgment. All three
  normal alias files matched the staged iCEnhancer inputs.
* A less manual validator is now implemented. The tracer records every shader
  creation and one first-bind row per exact bytecode identity. A report joins
  those records against D3DX-assembled iCEnhancer signatures, distinguishing
  exact-bound, exact-created, unseen and mismatch states in one normal scene.
* Two existing ASI crash dumps show four changed instruction bytes at
  game+0x8D6D26..29. The resulting displacement explains the invalid read at
  game+0x8D6D22. The writer has not been identified; a bad patch is a hypothesis.

Tools, pinned source links, addresses and machine-readable evidence are in
[legacy-shader-bridge.md](legacy-shader-bridge.md). Twenty-five offline tests
pass for role mapping, hashing, tree rebuilding, alias staging and runtime-report
classification. The fixed-baseline/tracing ASI was rebuilt successfully; warnings were limited to
pre-existing wchar conversion and missing third-party PDBs. It is staged in
`bin`, while the game still has the earlier ASI until the user runs FixedBaseline.

## What has and has not rendered

Earlier sessions reported ENB 0.163 rendering on CE 1.2.0.59 with stock shaders,
`API = 0`, DOF enabled and FusionFix's ENBLegacy configuration. Those reports
remain historical evidence. Their broader claim that arbitrary shaderinput
substitution was confirmed needs rechecking with actual ENB hashes.

One earlier September 4 launch used the original ENB effects plus twelve iCEnhancer
shaderinput files, stock shader overlay and tracing enabled, without the
icenhancer ASI. It exited 0xC0000005 before a scene was inspected. There was no
paired stock four-file baseline, so the failing component is unidentified.
That failed blanket test is superseded by the controlled baseline and terrain
probe below.

All sixteen backed-up installed file hashes and original settings were restored;
test-only additions were moved into scratch. **The user requested that they
perform further PC/game testing.** Subsequent work has been offline analysis
only. The user has now installed the prepared Baseline phase and confirmed an
outdoor scene loads. Read-only checks match the staged ENB DLL, effect, ENB ini
and FusionFix ini; the log confirms stock nv8 shaders, ENBLegacy renderer flags
off and no version spoof. Persisted DepthOfField is 9. The screenshot shows
strong over-brightening, washed-out shadows and clipped-looking highlights;
the brightness cause remains unproven. The kit snapshot exists. See
[user-baseline.json](evidence/2026-09-04/user-baseline.json).

## Probe follow-up

The first terrain search showed no magenta, but read-only inspection found that
none of the probe files was installed. The corrected run used the repository
script's file verification and produced a localized magenta terrain strip. All
three installed aliases exactly match the staged probe, and the startup log
confirms the intended stock shader/ENBLegacy configuration. This proves runtime
substitution for at least one terrain alias. It does not distinguish which of
the simultaneously active 2-, 3-, or 4-layer shaders drew the strip. Evidence:
[user-terrain-probe.json](evidence/2026-09-04/user-terrain-probe.json). The
earlier invalid negative is retained in
[user-terrain-search.json](evidence/2026-09-04/user-terrain-search.json).

## Next user test

Baseline loads, the combined terrain Probe is positive, and normal Aliases
remove magenta at the same location. At the user's request, further identity
capture is paused to address the visibly broken regular ENB baseline. The first
coherent tree/resource/state repair is built; run `FixedBaseline` against the
same scene, then establish a comparable scene for exposure analysis.
The prepared `TraceAliases`/`CollectTrace` tools remain available afterward;
shader identity logs alone do not establish postfx texture contents or quality.

If the ASI is eventually required, identify the writer of the four changed
instruction bytes before porting hooks. Restore modern FusionFix rendering only
after stock compatibility works, accounting for each pass's bindings and depth.

## Existing implementation

`source/enb_compat/` provides ENBLegacy renderer gating, package selection,
opt-in tracing and scoped version spoofing. Mode 0 preserves upstream defaults.
`tools/shader_dump/` provides extraction, comparisons, role/interface auditing,
ENB hash mapping, alias staging, effect inspection and existing crash inspection.

The selective package retains roughly 89% of shader **blobs**. Its rendering is
untested; that percentage does not measure retained graphics features. Modern
terrain writes depth and depends on paired vertex outputs, so inserting stock
pixel bytecode alone is not a complete compatibility solution.
