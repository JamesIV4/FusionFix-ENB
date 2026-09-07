# Status

**September 6: all preset translations implemented; rendering remains unverified.**
Eleven adapted inputs plus unchanged grass account for all twelve preset inputs.
The complete v4 package contains fifteen aliases and no pending translations.
67 Python tests, D3DX assembly, the Release build, native headless checks and
synthetic installation/upgrade/restoration checks pass. No game was launched or
modified. See [the completed translations and next validation work](translations-complete-2026-09-06.md).
The September 5 notes below are historical runtime evidence; there has been no
new visual test or raw texel capture to establish the darkening's cause.

**20:07 regression report — recover the earlier effect first:** the user reports
that normal/seam artifacts returned and brightness remains broken. The installed
ASI is still `5df954a5...`, identical to the seam-improved 19:04 run; the effect
is `da7f6976...` (iCEnhancer). The new diagnostic ASI `aa316ce1...` is only in
the repository, no capture request exists, and this run has no automatic capture.
The difference established against the earlier pair is the main-effect swap;
the shader-level cause of the reported artifacts is not yet proven. Use
`RestoreEffect` to recover the original `5676d639...` effect while retaining
the earlier bridge. Both files are now hash-verified and preserved separately
in `build/seam-improved-checkpoint`. Do not make the iCEnhancer effect the
baseline or call normal rendering fixed based on the earlier pair alone.
[Screenshot](evidence/2026-09-05/user-ice-regression.jpg),
[log](evidence/2026-09-05/user-ice-regression.txt).

**19:39 iCEnhancer main-effect result:** the user reports a very dark scene;
the screenshot shows almost-black world rendering with visible HUD. The installed
effect hash matches the original compiled iCEnhancer effect, and the bridge still
logs a successful translated draw. The cause is unresolved. A new `Diagnose`
action stages the bridge build with automatic raw input/output captures at
5, 15 and 30 seconds. Release build, 42 Python tests, headless state/readback
checks and synthetic setup/restore checks pass. The user must run the next
indoor test; no game launch or real-game file changes were performed by the
assistant. [Result](evidence/2026-09-05/user-ice-effect.json),
[diagnostic workflow](postfx-bridge.md#automatic-measurement-of-the-dark-output).

**19:04 ENB toggle comparison:** the user reports the world seam/normal problem
appears fixed. The paired indoor shots show much less obvious diagonal wall
splitting; ENB-on still adds a dark gray veil, while ENB-off is clearer. The
installed effect is still the original ENB 0.163 effect. The next prepared
user test is `IceEffect`, which replaces only that file with the inspected
original iCEnhancer compiled effect and maintains a separate backup.
[Pair and evidence](evidence/2026-09-05/user-enb-toggle.json).

**18:38 user test:** the corrected backend installed, recognized modern slot 13
and submitted a translated composite successfully. The screenshot remains dark
and hazy with triangular wall artifacts. This establishes the draw-path
milestone, not corrected rendering. The next user check toggles ENB off in the
same room (Shift+F11) to separate the effect path from earlier rendering.
[Evidence](evidence/2026-09-05/user-bridge-draw.json).

**Latest checkpoint: user-run testing only; no further computer use.** All twelve
iCEnhancer input identities were recovered from the
[1.0.4.0 patch reference](patch1040-reference.md). Indoor testing then exposed
two concrete runtime issues: GetFunction omits shader comments, and GTA IV
exposes a command-queue façade above ENB. The latest bridge resolves the verified
inner device and hooks its actual draw boundary. It is built and passes 37
Python tests plus headless native state/dispatch/router checks, but has **not
been fully visually validated**. It has now reached a successful in-game draw,
as recorded above. See [the current bridge and next test](postfx-bridge.md).
Full rendering compatibility remains unfinished. Older checkpoints below are
historical; the earlier four unidentified shader inputs are now identified,
although their necessary adaptations are not all implemented.

As of 2026-09-05. **iCEnhancer 4 is still unproven in game, but the investigation
has a concrete new route.** The earlier impossibility conclusion is superseded
by [the recovered shader bridge](legacy-shader-bridge.md).

**Compatibility-layer development resumed at the user's request.** The first
modern shader adapter backend builds three iCEnhancer deltas while preserving
FusionFix's modern program/depth output. Targeted postfx input capture is built
for the next interface bridge. See [implementation and next steps](modern-shader-adapter.md).

**Regular ENB baseline repair tested, rendering still unresolved:** the review found a
modern tree shader with disabled providers and ungated shadow/G-buffer/state
changes. The new profile restores the stock resource/state path, keeps required
tree alpha/wind constants, and stages a stock-depth extended-tree build. The
earlier conclusion that over-brightening is merely tuning was premature. See
[the review and implementation](regular-enb-review.md). Loading and probe
execution remain verified milestones. The valid FixedBaseline run loaded; the
user reports trees look exactly the same. Corrected rendering is not confirmed.

## New evidence

* A genuine Steam 1.0.8.0 data reference is now available. In every variant,
  94/102 containers and 1,636/1,689 shader blobs are byte-identical to CE;
  the main terrain/tree/lighting/postfx containers match exactly. No original
  preset filenames match that old shader set either. Six historical FusionFix
  patterns match its executable, and its stock shadow/G-buffer format values
  agree with CE. See [the reference analysis](steam1080-reference.md). Nothing
  from the depot was installed over CE or launched.

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
* The tracer records creation inputs and first successful binds at the
  game-facing device boundary. An ENB wrapper may hide its internally assembled
  replacements, so absence from this trace does not disprove substitution.
  Targeted postfx input snapshots now capture exposed texture/constant state;
  neither tool establishes texture pixel contents or final rendering quality.
* Two existing ASI crash dumps show four changed instruction bytes at
  game+0x8D6D26..29. The resulting displacement explains the invalid read at
  game+0x8D6D22. The writer has not been identified; a bad patch is a hypothesis.

Tools, pinned source links, addresses and machine-readable evidence are in
[legacy-shader-bridge.md](legacy-shader-bridge.md). Thirty-two offline tests
pass for role mapping, hashing, tree rebuilding, alias/delta staging and runtime-report
classification. The postfx-input tracing ASI was rebuilt successfully; warnings were limited to
pre-existing wchar conversion and missing third-party PDBs. It is staged in
`bin`, while the game has the user-tested FixedBaseline ASI. No new build was installed.

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

## Next compatibility-layer work

Baseline loads, the combined terrain Probe is positive, and normal Aliases
remove magenta at the same location. FixedBaseline also loads but did not
improve trees. The user requested work on the compatibility layer instead.
Three modern terrain delta adapters are built offline; five mapped inputs
still require custom translation. The next major target is a coherent final
composite bridge: recognition, relocated inputs and depth representation.
`TracePostFx`/`CollectTrace` are prepared for a future user-run input capture.
The new modern aliases must not be installed into the stock FixedBaseline.

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
