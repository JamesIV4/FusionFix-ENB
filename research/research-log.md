# Research log

## 2026-09-05 — review of the ordinary ENB baseline

At the user's request, paused the next alias capture and reviewed c18e6cf's
renderer changes, evidence and installed baseline against the screenshots.
The review found a retained modern extended-tree shader with its alpha/wind/depth
constant providers disabled; unconditional shadow/G-buffer format and matrix
changes omitted from ENBLegacy; and a register-audit regex that misses `_abs`
operands. Installed tree bytecode and on-disk executable immediates support the
first two findings. Neither exact foliage draw nor runtime resource formats
were captured, so specific screenshot root-cause attribution remains qualified.

The installed ENB effect matches the original archive. Its active 0.34 gray-value
power curve strongly lifts dark values, and it divides by an unmeasured
adaptation sample. The old "remaining brightness is tuning" conclusion was
premature. Postfx execution and the later terrain probe remain real milestones,
but do not establish material/lighting/resource correctness. The later user kit
inherited the structural baseline issues.

No game/native-device test, game-file modification or renderer fix was performed
in this review. Saved [the findings and revised order](regular-enb-review.md)
and [bytecode/PE evidence](evidence/2026-09-05/regular-enb-review.json).
Prioritize coherent ordinary ENB tree and resource behavior before resuming the
prepared TraceAliases/Effect tests. Earlier entries below are historical and
must be read with these corrections.

### 2026-09-05 implementation — coherent fixed baseline

Implemented the first repair from the regular-ENB review. ENBLegacy now disables
`ShadowPipelineFixes`, which gates dynamic model-shadow changes plus the shadow
atlas/G-buffer format, cascade and matrix patches. It also disables
`FusionShaderTweaks`, gating the FusionShader reflection multiplier, console
contrast offset and DXVK-only adaptive-state suppression on native D3D9.

ENBLegacy leaves `ShaderConstantInjection` on because the required FusionFix-only
extended tree reads pixel c221 for alpha and vertex c233 for wind.
`make_legacy_tree_shader.py` rebuilds that container from copied authored sources,
removing exactly five marked logarithmic-depth blocks and now-unused pixel v9
declarations. The source tree is unchanged. The 13,276-byte result has eleven
extractable shaders, no pixel c209 dependency and no explicit depth output;
SHA256 `8e6ef1dfd44a87603b3160b20b5e565be73272cbd9bcf6ebbb7b80663de5142a`.
Both `--stage-extras` and full-package staging now build this variant.

Fixed the interface parser to recognize `cN_abs` operands. The package detector
now includes the extended-tree exception, so stock plus that file logs as mixed
instead of falsely all-stock. The current user kit has a guarded `fixed` tree
artifact. `FixedBaseline` installs the new ASI/tree and required settings after
restoring regular ENB shaderinput, with hash verification.

The full setup/restore passed against a synthetic game tree. No installed GTAIV
file was changed by the assistant. Twenty-five offline tests and the Release
native build pass; build output retains existing wchar conversion and missing
third-party PDB warnings. Runtime rendering remains user validation.
The final repaired ASI is 5,923,328 bytes, SHA256
`EC91097B991A3F1D181F53C58D1D8D255A38F74732536DD5FE501B4429EF2DA4`.

Append one entry per meaningful investigation session. The point is that the
next person, human or otherwise, does not repeat an experiment that has already
been run.

---

## 2026-09-02 (in game, part 2) — iCEnhancer 4 does not work on Complete Edition

### Configuration

CE 1.2.0.59, `API = 0`, ENBSeries 0.163 as `d3d9.dll`, FusionFix in ENB mode,
iCEnhancer 4.0's preset installed over 0.163. Ultimate ASI Loader 9.7.1.

### What iCEnhancer 4 actually is

Released **July 2025**, not 2013 — the first version with physically-based
lighting. Its own page states it is "limited to 1.0.4.0 for now due to the patch
being the most compatible with ENB". It requires ENBSeries 0.163 and ships no
ENB binary of its own; `icenhancer.asi` runs *alongside* ENB rather than
replacing it, and a working install shows two logos.

### Observations

**The version guard reads the executable's version resource.** `icenhancer.asi`
imports `VERSION.dll -> GetFileVersionInfoSizeW`. So the check is satisfiable
from outside: hook the version-info API, let the real call run, and rewrite the
`VS_FIXEDFILEINFO` in the buffer that comes back. Nothing on disk changes, which
matters because editing `GTAIV.exe` would break both Steam's file verification
and FusionFix's pattern scanning.

That works. The log shows the hook firing and no dialog appears:

```
version spoof: reporting 1.0.4.0 to icenhancer.asi
  hook placed
version spoof: reported 1.0.4.0 for GTAIV.exe to icenhancer.enbcompat
```

**And then it crashes.** No `LoadPluginAfterSpoof: ... loaded` line ever
follows: the crash happens inside `LoadLibrary`, in `icenhancer.asi`'s DllMain,
in the same second. Windows records the faulting module as **`GTAIV.exe` itself,
at `+0x008d6d22`**, exception `0xc0000005`.

So the version check is load-bearing. It gates work against the executable at
hard-coded 1.0.4.0 addresses — consistent with the module importing
`GetModuleHandleW` to find the image base. Told it is on 1.0.4.0, iCEnhancer
reaches into addresses that mean something else on Complete Edition.

**Its preset does not work without its .asi either.** Two runs with iCEnhancer's
`shaderinput`, `enbeffect.fx`, `enbbloom.fx`, `enbclouds.fx` and textures on
ENBSeries 0.163 alone: one crashed in `ucrtbase.dll`, one hung on a black screen
with 37 threads all waiting. Its effect files are precompiled binaries that
appear to expect their own runtime.

### Conclusion

**iCEnhancer 4 cannot run on Complete Edition**, and the obstacle is not
something a compatibility layer can expose. A version number can be exposed;
1.0.4.0's memory map cannot. Making it work would mean mapping every hard-coded
address it uses onto CE equivalents inside a packed anti-tamper binary (entropy
8.00, `CODE` section with raw size 0) — a large reverse-engineering project of a
different kind to everything else here, which succeeded precisely because it
never needed to touch ENB's code.

This is the case §19 of the plan describes and defers, and the answer to its
question "does ENB inspect GTAIV executable addresses directly?" is: ENBSeries
itself, no. iCEnhancer's ASI, yes.

The version-spoof mechanism is kept because it is sound and general — it is the
right answer for a plugin whose check is only a check. It is off by default and
documents this outcome in its own comments.

### Still open

How much of iCEnhancer 4's *preset* ENBSeries 0.163 can run on its own. Its 12
`shaderinput` files are plain assembly that 0.163 compiles itself, with no
dependency on iCEnhancer's runtime; the effect files are the part most likely to
need it. `tools/gamesetup/ENBCompat-Mix.cmd` bisects this one component at a
time from a known-good 0.163 baseline. Untested — the game folder was reverted
before this was run.

### Process notes, so they are not repeated

* **A new source file needs `premake5` re-run.** `enbversion.ixx` was added
  after project generation and therefore never compiled. Three test runs were
  wasted on builds that did not contain the code being tested, and a clean build
  of code that is not being compiled looks exactly like a clean build. Verify a
  new module by grepping the built binary for one of its strings.
* **`inline` namespace-scope variables in a module interface do not link.** Use
  function-local statics, as the rest of this codebase does.
* **GTA IV presents through the swap chain, not the device.** A device-vtable
  hook on `Present` never fires; `EndScene` is the reliable frame boundary.
* Do not disable tracing and then ask for a capture in the same breath.

---

## 2026-09-02 (in game) — ENB runs on Complete Edition, and needs depth of field on

First runs with a real install. **ENBSeries 0.163 initialises and renders on CE
1.2.0.59**, both with and without FusionFix, and its shader substitution fires.
The plan's Question 1 is answered: yes.

### Configuration

CE 1.2.0.59, `API = 0`, ENB 0.163 wrapper as `d3d9.dll`, FusionFix in ENB mode
(`Mode = 1`, stock shaders via `win32_30_nv8`). Config C and D per
[test-matrix.md](test-matrix.md).

### Method

Static analysis could not distinguish "ENB's substitution never fires" from
"ENB's substitution fires and is mistuned", so the shaders were instrumented
directly: ENB ships its own debug lines commented out at the end of three of its
four `shaderinput` files, each writing a different output channel. Uncommenting
them, plus a magenta tint added to `enbeffect.fx`'s `PS_C215BE6E`, turns "did
this shader get replaced" into something visible on screen.

### Observations

**The post-process substitution works.** The magenta tint appeared -- but only in
some scenes. Not a location effect: it tracks the **Depth of Field** setting.
Off or Cutscenes Only, no tint; Low through Very High, tint everywhere.

**Why.** `rage_postfx.fxc` is not one uber-shader. Its trailing table is 28
fixed-size records indexed 01..1C -- 28 passes, one pixel shader each. The final
composite exists in several variants, and two matter:

| pass | constants | samplers | contract |
|---|---|---|---|
| `#13` | `c44, c66, c72..c85` | `s0..s6` | 20/20 -- **ENB's target** |
| `#29` | `c44, c66, c72..c84` | `s0..s5` | 8/20; drops `dofDist` and `BloomSampler`, shifts the rest down one |

Runtime capture confirms it: with DOF on Cutscenes Only, a frame indoors bound
`rage_postfx#13` (plus DOF blur prepasses `#8`, `#9`); a frame outdoors bound
`rage_postfx#29`. The effect applied only in the first.

**Identifying ENB's target, offline.** `enbeffect.fx` is the original shader
translated to HLSL and keeps its `def` constants verbatim as `_c0.._c6`
(`_c7` onward are ENB's own, marked `//mine`). Three independent signals:

1. all 7 original constants match `#13`, `#15`, `#17`, `#19`;
2. only `_c78.z` and `_c79.y/z` are used -- the far-DOF-only path, with no `max`
   of two DOF terms, ruling out `#15` and `#19`;
3. no conditional select anywhere in the body, ruling out `#17`.

So ENB replaces `rage_postfx#13`, crc `1895B35D`.

**This cannot be worked around.** ENBSeries matches a shader by one hash, so a
preset can carry a replacement for exactly one variant. Splicing `#13`'s
bytecode into `#29` would hand ENB's shader a shifted layout -- `dofBlur` read as
`dofDist`, `AdapLumSampler` as `BloomSampler`, plus `c85` and `s6` the game never
binds in that pass. DOF-on is a requirement of running ENB on GTA IV, not a bug
to fix.

### Changes

* `splice_fxc.py`, which rewrites a `.fxc` so several slots share one blob. The
  container is `rgxa` + u16 + a flat run of `[u16 size][u16 size][bytecode]`
  with no offset table (verified: all 30 headers match their measured length),
  so slots can be replaced at differing sizes by rewriting both size fields.
* Used it to point `#15`, `#17`, `#19` at `#13`. **Unproven** -- neither capture
  bound any of the three, so the DOF setting alone may explain everything
  observed. Kept because those three are interface-identical to `#13` (20/20,
  same samplers), so it is safe and may help in scenes that do bind them.
* The tracer's frame counter now runs off `EndScene`, not `Present`: GTA IV
  presents through the swap chain, so a device-vtable hook on `Present` never
  fires and the counter sat at zero. Added shader-bind logging by creation hash,
  and a hotkey trigger, since a frame-number window cannot express "capture
  here, then walk over there and capture that".
* `ENBCompat.log` now warns when ENB mode is active and DOF is below Low.

### Corrections

* `icenhancer.asi` was earlier called "not an ENB binary" because a string search
  found no ENB strings in it. Wrong: every ENB binary here is packed (entropy
  ~7.94-8.00, `CODE` sections with raw size 0), so absent strings prove nothing.
  It is very likely a packed ENB build shipped as an ASI, which would also avoid
  the `d3d9.dll` name clash. Worth testing -- it carries 12 `shaderinput` files
  against 0.163's 4.

### Next experiment

With DOF on, judge the image against the preset's intended look. Remaining
brightness is now a tuning question (`[ADAPTATION]`, `EBrightnessV2`) rather than
a substitution failure, and ENB's in-game GUI (Shift+Enter, present since
v0.127) can drive it live. Then re-run configuration D with `--selective` to see
how much of FusionFix can be kept.

---

## 2026-09-02 (later still) — Selective package: keep FusionFix except where ENB needs stock

### Hypothesis

Only the containers holding a shader an ENB preset replaces have to come from
stock. Everything else can stay FusionFix.

### Observations

**Target count.** iCEnhancer 4.0's twelve `shaderinput` files are a strict
superset of enbseries 0.163's four. `enbeffect.fx` adds one more, `C215BE6E`,
via its `Shader_C215BE6E` technique. `enbbloom.fx` and `enbclouds.fx` define
ENB's own passes rather than game-shader replacements. So **13 distinct
targets**, not 16.

**Identification, sharpened.** Added `--match-decls` to `match_enb.py`: a
candidate now has to have the same declaration signature as the ENB file --
identical input declarations, samplers a subset of the ENB file's. ENB only ever
adds a sampler for its own textures and never changes what a shader receives
from the vertex stage, so this is sound, and it is a far stronger discriminator
than instruction similarity within a family of shaders that all do nearly the
same thing.

Result: seven targets resolve to a **single** candidate, four collapse to a
small tied family, and one has no candidate at all.

| ENB file | candidates | best | verdict |
|---|---|---|---|
| `psh0CBF49C5` | 1 | `gta_terrain_va_2lyr#5` 1.000 | certain |
| `psh405ABC1B` | 1 | `gta_terrain_va_3lyr#7` 1.000 | certain |
| `psh841FD9AE` | 1 | `gta_terrain_va_4lyr#9` 1.000 | certain |
| `psh71CC11CF` | 1 | `gta_grass#2` 0.817 | certain by elimination |
| `vsh54F25463` | 3 | `deferred_lighting#7` 0.995 vs 0.128 | certain |
| `vshC35A5E05` | 4 | `deferred_lighting#8` 0.988 vs 0.629 | certain |
| `psh22DCDB69` | 79 | `rage_postfx#12` 0.912 vs 0.743 | strong |
| `psh2DF967C6` | 11 | three-way tie at 0.667 | see below |
| `psh323E9BB8` | 11 | same three, 0.345 | unresolved |
| `pshF5256B40` | 16 | `gta_glass_spec`/`gta_spec` family, 0.375 | unresolved |
| `psh8DB4CDB2` | 6 | `gta_normal_spec` family, 0.160 | unresolved |
| `psh46A43A9F` | **0** | -- | no CE shader has its signature |

The `psh2DF967C6` tie is not a failure of the method. `gta_cutout_fence#15`,
`gta_default#15` and `gta_wire#14` hold the **same bytecode**, so the tie is
correct and ENB would match all three -- the hash names a bytecode, not a
container. Stock CE has 1689 shader blobs but only 638 distinct bytecodes, so
this kind of duplication is normal.

**Blast radius.** Checking each confidently identified target for duplicates
elsewhere in the set: seven of eight are unique to one container; `2DF967C6`
spans three. Nine containers in total:

```
deferred_lighting.fxc     62      gta_terrain_va_4lyr.fxc   10
rage_postfx.fxc           30      gta_terrain_va_3lyr.fxc    8
gta_default.fxc           24      gta_terrain_va_2lyr.fxc    6
gta_cutout_fence.fxc      24      gta_grass.fxc              3
gta_wire.fxc              24
                                  191 of 1739 FusionFix shaders = 11.0%
```

So a selective package retains **89%** of FusionFix's shader work. Two of those
nine cost nothing much: `rage_postfx` is ENB's territory anyway, and
`deferred_lighting` is worth excluding by default -- 62 shaders for two
vegetation wind-sway vertex shaders is a poor trade. Excluding it: 8 containers,
129 shaders, **92.6% retained**.

### Changes

* `match_enb.py --match-decls`, and `d3d9bc.declarations()` behind it.
* `make_vanilla_package.py --selective` stages FusionFix's containers into the
  stock-shader folder *except* the targeted ones, which then fall through to
  `common/shaders`. `--keep-stock list` prints the set and what each costs.
  `gta_trees_extended.fxc` is carried along automatically, so this mode needs no
  separate `--stage-extras` step.
* `DetectShaderPackage()` now probes three containers and distinguishes
  Stock / FusionFix / **Mixed**, and warns when `ShaderConstantInjection` is off
  while FusionFix shaders are still loaded -- which is precisely the trap a
  selective package sets.

### Conclusions

The hybrid is the better default: it keeps the constant injection on, keeps ~90%
of FusionFix's shader work, and gives the preset stock bytecode exactly where it
looks for it.

Two limits are worth stating plainly:

* **A container is the floor.** Shaders inside a `.fxc` cannot be swapped
  individually without rebuilding the container, and rebuilding through
  RageShaderEditor assembles from `.asm` with no CTAB -- different bytecode from
  stock, so the hash would not match anyway. Sub-container granularity needs
  either ENB's hash function or the `.fxc` container format reverse-engineered.
* **Four of thirteen targets are still unidentified**, and one (`psh46A43A9F`)
  has no shader in CE with a matching signature at all. The default selective
  set covers the nine containers we are confident about; if a preset still
  misbehaves, the unresolved four are the first place to look.

And the whole thing still rests on the untested assumption that ENB's hash
matches CE's stock bytecode.

### Next experiment

Unchanged, and now with a clear payoff: configuration C decides whether any of
this works. Then D with `--selective`.

---

## 2026-09-02 (later) — Bypassing the shader package without touching a file

### Configuration

As above. Still static.

### Hypothesis

FusionFix's shader package can be taken out of the picture at runtime, from the
ini, rather than by swapping files in the game folder.

### Observations

The game keeps six GPU-specific shader-variant folders and picks one at runtime.
`GTAIV.exe` holds their names as a contiguous block of string constants:

```
win32_30 | win32_30_low_ati | win32_30_nv6 | win32_30_nv7 | win32_30_nv8 | win32_30_atidx10
```

FusionFix's "redirect path to one unified folder" hook in `shaders.ixx` collapses
every lookup onto entry 0, `win32_30` — which is exactly the folder its own
package overlays. That is the whole mechanism by which the FusionFix shaders get
loaded.

All six folders hold the same 102 containers. Comparing `win32_30` against
`win32_30_nv8` with `compare_sets.py`: **1689 shaders compared, 1688 identical,
1 changed** (`deferred_lighting.fxc#11`, a vertex shader, 14 instructions versus
163). Running `match_enb.py` against `win32_30_nv8` reproduces the `win32_30`
similarity figures to three decimal places, all twelve entries.

### Changes

* Generalised the path hook to take an index instead of hard-coding 0, resolved
  **by folder name** rather than by position, since the pointer table order is
  not guaranteed. With `FusionShaderPackage = 1` it resolves to 0 and the
  emitted behaviour is identical to before.
* Added `StockShaderFolder` (default `win32_30_nv8`).
* `make_vanilla_package.py --stage-extras` copies `gta_trees_extended.fxc` into
  the chosen variant's update overlay — one file, since the update tree overlays
  per file rather than per directory, so every other lookup falls through to the
  stock copy.
* `ENBCompat.log` warns if that file is missing while stock shaders are selected.

### Conclusion

`FusionShaderPackage = 0` now switches the whole package off at runtime. Nothing
is deleted, renamed or backed up; the package stays on disk and inert, and the
switch back is an ini edit. The file-swapping route is kept as a fallback for
targeting `win32_30`'s bytes specifically.

The one thing still not knowable from here is which variant the preset's hashes
were computed against — that depends on the GPU its author was running. Since
the variants are byte-identical bar one shader, this is close to moot, and
`StockShaderFolder` turns it into a six-way bisect if it ever matters.

### Next experiment

Unchanged: configuration C first (stock CE + iCEnhancer, no FusionFix), then D
and D′.

---

## 2026-09-02 — Extractor bug fixed; the ENB contract read directly from the preset

### Configuration

Same as the previous entry. Still no game launched; everything static. The game
has since been switched to `d3d9.cfg [MAIN] API = 0`.

### Correction to the previous entry

`d3d9bc.extract()` scanned for shader version tokens on 4-byte alignment. RAGE
`.fxc` containers do not align their shader blobs, so it found roughly one in
ten. `rage_postfx.fxc` reported 3 shaders; it actually holds 30. Fixed by
scanning byte by byte and validating each candidate by walking its token stream
to an end token.

Every count in the 2026-09-01 entry was low. Corrected, on the same two shader
sets:

```
stock CE win32_30 : 102 containers, 1689 shaders (856 ps / 833 vs)
CE + FusionFix    : 103 containers, 1739 shaders (875 ps / 864 vs)
1689 compared — 0 identical, 1689 changed, 50 added
320 differ only in def/dcl; 1369 have a rewritten instruction body
of 638 distinct stock bytecodes, 2 survive byte-identical into FusionFix
```

The conclusion is unchanged and now rests on a four-times larger sample. The
*identification* results changed a great deal, below.

### Hypotheses under test

1. The rendering contract ENB expects can be recovered without a 1.0.x install.
2. Complete Edition still provides that contract.
3. FusionFix is what breaks it.

### Observations

**H1 — confirmed, and it was hiding in plain sight.** enbseries 0.163 ships
`enbeffect.fx` as commented HLSL. Its entry point is `PS_C215BE6E` — named for
the hash of the game shader it replaces — and above the body is the complete
parameter table of that shader: 13 named constants at c44 through c85 and 7
samplers at s0 through s6. That is the post-process contract, written down by
ENB itself. iCEnhancer 4.0's precompiled `enbeffect.fx` declares the same
interface in its CTAB.

Transcribed to `contracts/enb-postfx.json` and checked mechanically by
`tools/shader_dump/check_interface.py`.

**H2 — confirmed, exactly.** CE's `rage_postfx.fxc` holds 30 shaders. Four of
them (#13, #15, #17, #19) match the contract on **all twenty parameters**, name
and register. Reading the instruction stream instead of the reflection table
agrees: they read `c44, c66, c72..c85` and `s0..s6`, nothing else. Three further
variants have the usual uber-shader shifts (`PLAYER_MASK` at c86, samplers up by
one, or DOF dropped); the variant ENB targets is present and unshifted.

**H3 — confirmed.** The same check over the FusionFix package: 0 of 13
candidates honour the contract, and **0 of 30 shaders carry a CTAB at all** —
RageShaderEditor assembles from `.asm` via `D3DXAssembleShader`, which emits no
reflection data. Register use diverges too: `+c86, c209, c222`, `−c76, c78,
c79`, `+s7, s10`. `c209` and `c222` are FusionFix's own injected constants, so
the FusionFix post-process shader is not merely different, it *depends on*
`ShaderConstantInjection`.

Two FusionFix variants (#17, #19) do still read exactly `c44, c66, c72..c85` /
`s0..s6`. Strategy B — keep the correction, restore the interface — is therefore
not hypothetical; one shader in the package already does it.

**Shader identification, now decisive.** Re-running `match_enb.py` against the
correctly extracted stock CE set:

| ENB file | best match in stock CE | similarity |
|---|---|---|
| `psh0CBF49C5` | `gta_terrain_va_2lyr.fxc#5` | **1.000** |
| `psh405ABC1B` | `gta_terrain_va_3lyr.fxc#7` | **1.000** |
| `psh841FD9AE` | `gta_terrain_va_4lyr.fxc#9` | **1.000** |
| `vsh54F25463` | `deferred_lighting.fxc#7` | 0.995 |
| `vshC35A5E05` | `deferred_lighting.fxc#8` | 0.988 |
| `psh22DCDB69` | `rage_postfx.fxc#12` | 0.912 |
| `psh71CC11CF` | `gta_grass.fxc#2` | 0.817 |
| `psh2DF967C6` | `gta_cutout_fence.fxc#15` | 0.667 |
| `psh323E9BB8` | `gta_grass.fxc#2` | 0.483 |
| `pshF5256B40` | `gta_grass.fxc#2` | 0.408 |
| `psh46A43A9F` | `gta_rmptfx_gpurender.fxc#3` | 0.323 |
| `psh8DB4CDB2` | `gta_hair_sorted_alpha_exp.fxc#11` | 0.225 |

A similarity of 1.000 means the game shader's entire instruction body appears
verbatim inside the ENB replacement. Spot-checking `psh0CBF49C5` against
`gta_terrain_va_2lyr#5` line by line: identical, twelve instructions, same
declarations, differing only in the `.w` component of one `def`.

The three shaders that all resolve to `gta_grass.fxc#2` are unresolved — the
matcher is converging on one candidate for three different ENB files, which
means at least two of them are wrong. Re-run with `--top 5` before using them.

### Conclusions

* **Complete Edition did not rewrite the shaders these presets target.** The
  code is the same. So the failure is not "CE changed the rendering and the old
  contract is gone".
* **The post-process contract is intact on CE and broken by FusionFix**, in
  three separate ways: added dependencies on FusionFix's own injected constants,
  moved and dropped registers, and no reflection data at all.
* Taken together, these two make the working hypothesis much sharper than it was
  yesterday: an old preset has a real chance of working on bare CE, and
  FusionFix's shader package is the thing standing in the way.
* **The 1.0.4.0 / 1.0.7.0 reference install is no longer a blocker.** See
  [enb-contract.md](enb-contract.md) §4 for which questions it would and would
  not have answered. The only one it uniquely answers is ENB's hash function,
  and that is not on the critical path.

### Next experiment

Unchanged in shape, but the first step is now much better motivated: configuration
C — stock CE plus iCEnhancer 4.0 at `API = 0`, no FusionFix. The static evidence
says the shaders the preset wants are present and unmodified, so if it does not
work, the reason is something other than the shader code, and that is worth
knowing before touching anything else.

---

## 2026-09-01 — Reconnaissance, static shader analysis, compatibility scaffolding

> Counts in this entry are wrong; see the 2026-09-02 entry for the corrected
> figures. The conclusions held.

### Configuration

* Repository at `c3f9a9a`, submodules initialised.
* Toolchain: Visual Studio 18 (MSVC 14.51), premake5 `vs2026`, Python 3.13.
* Game: Complete Edition 1.2.0.59 at
  `C:\Games\Steam\steamapps\common\Grand Theft Auto IV`, with FusionFix 5.0.1
  installed and `d3d9.cfg` set to `API = 1` (DXVK).
* ENB material: `ENB resources/enbseries_gta4_v0163.zip` and
  `ENB resources/icenhancer40.zip`, extracted but **not installed**.
* No game was launched this session. Everything below is static.

### Hypotheses under test

1. ENB identifies GTA IV shaders by a hash of their compiled bytecode.
2. FusionFix's replacement shader package changes those hashes.
3. FusionFix and ENB collide over shader constant registers.
4. FusionFix and ENB double-hook the same D3D9 functions.

### Changes

* Built FusionFix unmodified — the `.asi`, the `d3d9.dll` and the installer all
  compile clean (plan Task 1).
* Added `tools/shader_dump/` (D3D9 bytecode reader, `.fxc` dumper,
  set comparison, ENB `shaderinput` matcher, stock-package builder),
  `tools/d3d9_trace/`, `tools/frame_compare/`.
* Added `source/enb_compat/enbcompat.ixx` (renderer compatibility profile,
  `[ENBCompatibility]` config, ENB detection, installed-shader-package
  detection, logging) and `source/enb_compat/enbtrace.ixx` (opt-in D3D9 tracer
  and shader fingerprinter).
* Gated the renderer-invasive FusionFix features on the profile in
  `postfx.ixx`, `shaders.ixx` and `consolegamma.ixx`.
* Added `ProxyLibrary` to the FusionFix `d3d9.dll` wrapper.

### Observations

**H1 — confirmed by artifact inspection.** Both ENB archives contain a
`shaderinput/` directory of files named `psh<8 hex>.txt` / `vsh<8 hex>.txt`
holding D3D9 shader assembly. `psh2DF967C6.txt` appears in both presets with
different contents (2239 vs 1527 bytes), so the hash names the *game* shader
being replaced. The replacement assembly is the original with ENB's edits
spliced in — extra `def c150 / c175 / c177 / c178` and an extra `dcl_2d s13`.

**H2 — confirmed.** `compare_sets.py` over the stock CE `common/shaders/win32_30`
set (102 containers, 404 shaders) and the FusionFix
`update/common/shaders/win32_30` set (103 containers, 383 shaders):

```
453 shaders compared
0 identical, 334 changed, 70 removed, 49 added
100.0% of shaders have a different bytecode hash under FusionFix
```

Ignoring `def` and `dcl` tokens, 74 of the 334 paired shaders have an identical
instruction body and 260 were genuinely rewritten. So roughly a fifth of the
overlap is a hash break caused only by the injected `FusionShader` signature
constant; the rest is real code change.

File names are identical between the two sets except for one addition:
`gta_trees_extended` (`.fxc` + `db/*.sps` + `dcl/*.dcl`). That single file
explains the resource error reported in FusionFix issue #180 when
`update/common/shaders` is deleted — FusionFix's own content packages reference
a shader that goes away with it.

**ENB's hash function — not identified.** CRC32 (both polarities), Adler-32,
FNV-1a, FNV-1, Jenkins one-at-a-time, MurmurHash2, MurmurHash3, additive and
XOR-of-dwords, each over six framings of the blob (full, without the version
token, without the end token, without both, comment-stripped, comment-stripped
without the version token), across all 2416 shader blobs in the stock CE
`common/shaders` tree: **no match** against any of the twelve target hashes.
Either the function is not in that list, or CE's shaders differ from the 1.0.x
shaders these presets were built against. Distinguishing the two needs an old
install.

**H3 — probably false.** FusionFix writes pixel c208..c223 and vertex
c227..c237. The ENB replacement pixel shaders define c150/c175/c177/c178 and
read game constants c39, c52, c66, c72..c75; the two iCEnhancer vertex shaders
read c208..c222, which are *vertex* registers and so below FusionFix's vertex
range. No overlap in either stage.

**H4 — false as things stand.** FusionFix installs no hooks on any
`IDirect3DDevice9` method. `fusiondxhook.ixx` is the only code that would, and
its body starts with an unconditional `return;`. The overlap between the two
mods is over *what is drawn where*, not over function ownership.

**Shader identification, partial.** `match_enb.py` compares normalised
disassembly. Two identifications are strong:

* `psh71CC11CF` ↔ stock CE `gta_grass.fxc#0`, similarity 0.817;
* `vsh54F25463` ↔ **FusionFix** `deferred_lighting.fxc#4`, similarity 0.923 —
  against 0.128 for the closest stock CE candidate.

That second one is the surprise of the session and points the other way from
everything else: for this vegetation wind-sway vertex shader, FusionFix's
version is much closer to what the preset expects than Complete Edition's is,
which suggests FusionFix restored an older form of it. Worth confirming before
building anything on it.

The remaining ten are weak (similarity 0.10–0.69). Low similarity is not
evidence of absence — recompilation changes register allocation and the measure
is textual.

### Conclusions

* The dominant conflict is shader identity, and it is total: not one shader
  survives FusionFix with its hash intact.
* Deleting the FusionFix shader package is not the fix, because one shader in it
  is genuinely new and FusionFix's content needs it. The fix is a hybrid
  package: stock bytecode for the 102 original shaders, FusionFix's
  `gta_trees_extended` kept. `tools/shader_dump/make_vanilla_package.py` builds
  exactly that.
* Two hypotheses can be dropped: constant-register collision and D3D9
  double-hooking. Neither is happening.
* `d3d9.cfg` must be set to `API = 0` before any ENB experiment. The current
  install is on DXVK, where an ENB D3D9 wrapper cannot work at all.

### Next experiment

Run the plan's Phase 1 questions, in this order:

1. Configuration C — stock CE plus iCEnhancer 4.0, `API = 0`, no FusionFix. Does
   the ENB initialise, and do its effects appear? This is the question that
   decides whether the project is "resolve a FusionFix conflict" or "translate
   an old rendering contract to Complete Edition", and it needs no new code.
2. Configuration D — add FusionFix at `Mode = 0`. Reproduce issue #180.
3. Configuration D′ — `Mode = 1` plus the staged stock shader package. This is
   the first real test of everything built today.
4. With `D3D9Trace = 1` and `DumpShaders = 1` in configurations B and D, collect
   `shaders.csv` and diff with `tools/frame_compare/compare_shader_csv.py`.

Blocked on external input: an old-patch GTA IV install (1.0.4.0 or 1.0.7.0).
Without it, ENB's hash function cannot be recovered by working backwards from a
known-good match, and "CE broke it" cannot be separated from "FusionFix broke
it".


## 2026-09-04 ? historical FusionFix bridge, recovered ENB hash, manual test handoff

**Request:** revisit the earlier stop on iCEnhancer 4, starting with FusionFix
forks supporting old patches. The user later requested that they perform PC
runtime testing; subsequent work stayed offline.

**Pinned source evidence:** Zolika fork dc33fad and its exact shader submodule
9d86139; Gillian GFWL fork aee995b. The historical Create/SetPixelShader hooks
are commented out. The shader bundle supplies useful named techniques and
bindings across 1.0.7.0/1.0.8.0/CE, not a ready table of ENB hashes. Old postfx
preserves all twenty stock bindings; modern FusionFix moves five. Fourteen
container audits record role, declaration, register, depth and pass-state
changes. Modern terrain's oDepth/paired vertex differences prohibit treating a
bytecode splice as a complete adapter.

**Effect evidence:** before the user's manual-test boundary, the three bundled
iCEnhancer compiled effects loaded, validated and bound all seven passes in a
standalone Microsoft D3DX9 HAL harness without ENB or the ASI; twelve shader
programs disassembled. No geometry was drawn. Their names, interfaces and CPU
preshaders are accessible. Whole-effect fxc failure had been misread as opaque
shader code requiring a custom runtime.

**Actual game attempt:** original ENB 0.163 effects plus twelve iCEnhancer
shaderinput files, stock overlay, compatibility ASI, D3D9 tracing enabled,
no iCEnhancer ASI. Launcher timestamps were 19:33:17 launch / 19:33:51 exit
0xC0000005; no scene was inspected. No paired stock shaderinput control was
run. This identifies neither the failing component nor a failure of the new
aliases, which did not exist yet. Sixteen original file hashes and settings
were restored; added test files were moved to scratch. No further game/native
runtime test followed the user's instruction.

**Offline breakthrough:** independently decoded the exact supplied ENB 0.163
wrapper without executing it. Recovered raw CRC32 identity (no final XOR,
exclude first aligned END, retain version/comments) from both creation paths.
Postfx recognizes six aliases, including stock CE #13 AA1C0C36; #29 2D5D52B3 is
not recognized. None of twelve iCEnhancer filenames matches any of 10,134 stock
blobs in six variants. Modern FusionFix's 1,739 win32_30 blobs match neither
those twelve names nor the postfx aliases. This supersedes earlier claims of
raw identity equality and the unresolved hash algorithm. File matches remain
static until actual runtime shader inputs/substitution are observed.

**Implementation:** added hash calculation to offline fingerprints; decoder,
hash scan, guarded filename-alias builder, terrain color probe, historical
interface auditor, effect inspector and existing-minidump inspector. Staged
three terrain aliases by default, five weaker candidates separately. Four
unresolved files remain excluded. No ENB DLL or game executable patch was made.
Seventeen offline tests pass for mapping ambiguity/indexing, binding/depth
changes, raw CRC behavior, duplicate/colliding identities, modified-input
rejection, output protection and diagnostic probe generation.

**Existing ASI dumps:** two September 2 dumps contain changed instruction bytes
at game+8D6D26..29. In the first, the modified displacement plus captured ESI
exactly explains the invalid read at game+8D6D22. No writer was captured. This
narrows a future debugger experiment to a data breakpoint on those four bytes;
it does not prove a particular ASI hook wrote them. Sanitized reports are saved.

**User test prepared, not run:** `C:\temp\enb-revisit\user-test-kit` contains
Baseline, Probe, Aliases and Effect phases plus a per-file snapshot/restore
script. The script does not launch the game. Baseline uses stock shaders,
tracing off, spoof off; the user enables DOF. Probe forces three terrain diffuse
outputs magenta. Aliases uses untouched iCEnhancer assembly with CE filenames.
Effect resets to the baseline then replaces only enbeffect.fx. Setup/restore
has been parsed/reviewed but not executed; all copies remain outside GTAIV.

Current analysis, code RVAs, pinned sources and evidence:
[legacy-shader-bridge.md](legacy-shader-bridge.md).
Next action is the user's [baseline and terrain test](alias-test.md), not another
blanket claim that obfuscation or a complete old executable map blocks progress.


### 2026-09-04 user follow-up ? Baseline loads, brightness unresolved

The user ran Baseline and supplied screenshot `20260904210046_1.jpg` (21:00:46)
from the Steam GTAIV screenshot folder. An outdoor Hove Beach scene loads;
shadows are washed out and highlights appear clipped. The user reports this
resembles the earlier over-bright ENB result. No diagnosis of brightness yet.

Read-only installed file comparisons match the staged ENB DLL, enbeffect.fx,
enbseries.ini and FusionFix ini. ENBCompat.log at 20:57 confirms stock nv8
shaders, ENBLegacy renderer flags off and no spoof. DepthOfField = 9. The four
original ENB shaderinput files are present; new alias/probe files are absent.
The Baseline snapshot exists. The assistant did not operate or launch the game.

Result: baseline scene-loading passes on the user's run. This does not validate
new shader mappings or iCEnhancer effects. Next: user-run Probe on blended
terrain, with brightness left unchanged. Evidence:
[evidence/2026-09-04/user-baseline.json](evidence/2026-09-04/user-baseline.json).


### 2026-09-04 user follow-up ? no magenta seen, probe files absent

The user reported searching several terrain areas without seeing magenta.
Read-only inspection afterward found just the four original ENB shaderinput
files. pshA5F4E880.txt, pshFDFF185D.txt and psh1D661524.txt were all absent,
although the staged probe folder contains all three. ENBCompat.log's latest
startup is 21:08:10 with stock nv8/ENBLegacy and no version spoof. Whether the
Probe action completed or the user subsequently restored Baseline is pending
clarification; do not count this as a validated negative mapping test.

Re-read the recovered pixel creation routine: the filename open/assemble path
at RVAs 0x1538..0x1608 has no shader-hash whitelist before its file lookup.
This does not prove runtime inputs have the same bytes as the container.

Updated the repository setup script to reject empty phases/missing probe inputs
before mutation, hash the expected final phase files, and verify every installed
file before success. Probe success explicitly lists the three filenames. The
assistant did not run setup or alter game/kit files. The user must invoke the
repository script to get these checks; the staged copy remains the old version.
Evidence: evidence/2026-09-04/user-terrain-search.json.

### 2026-09-04 user follow-up — terrain alias probe confirmed in game

The user repeated Probe using the corrected repository script and found the
expected magenta on a narrow blended-ground corridor beside buildings. Screenshot
`20260904223905_1.jpg` was captured at 22:39:05. The image shows local ground
replacement rather than a fullscreen tint: character, buildings, foliage,
fence, bench and adjacent pavement retain normal shading.

Read-only post-run inspection found all three probe files present and byte-for-byte
equal to the kit: A5F4E880 (2-layer), FDFF185D (3-layer), and 1D661524 (4-layer).
ENBCompat.log confirms the stock nv8 overlay, ENBLegacy mode, all FusionFix
renderer flags off, and no version spoof. The iCEnhancer ASI was absent.

Result: ENB 0.163's filename lookup accepted at least one recovered CE hash and
executed the aliased iCEnhancer-derived terrain program. This validates the
decoded hash/filename bridge at runtime for the combined terrain group. Since
all three probes were active, the screenshot cannot say which individual layer
count drew the strip. Next is `Aliases`, revisiting the same scene to verify that
unchanged iCEnhancer terrain programs render without the diagnostic override.
Evidence: [user-terrain-probe.json](evidence/2026-09-04/user-terrain-probe.json).

### 2026-09-04 user follow-up — unchanged terrain aliases render

The user switched from Probe to Aliases and revisited the same building-side
terrain corridor. Screenshot `20260904230235_1.jpg` shows textured ground with
the diagnostic magenta gone. The user notes visible fading where it meets the
street and toward the right, while broader broken rendering makes correctness
hard to judge. A simple threshold finds zero magenta-like pixels, versus 82,423
in the probe screenshot. All three installed normal aliases hash-match the kit.

This verifies that replacing the diagnostic assembly restores non-probe output
at the known location. It does not prove the visual result is correct or identify
the active layer-count shader. Evidence:
[user-terrain-aliases.json](evidence/2026-09-04/user-terrain-aliases.json).

To eliminate further visual searching, ENBTrace now writes one first-bind row
per raw shader identity for the whole run. `assemble_shader.cpp` reproduced
ENB's zero-flag D3DX assembly path offline; the eight guarded mappings now carry
expected assembled SHA256/raw CRC identities. `report_runtime_aliases.py` joins
creation, exact dumps and first binds into explicit statuses. `TraceAliases` and
`CollectTrace` automate setup and collection; only launching, loading a scene,
and exiting remain manual.

The Release ASI rebuilt successfully with the new first-bind recorder. The build
reported the existing wchar conversion warning in graphics-module logging and
missing third-party PDB warnings; no new compiler or linker failure occurred.
`bin/GTAIV.EFLC.FusionFix.asi` SHA256 is
`520E0AB83B280643E1FFCBD996FC26FEA8FF23BD994EBC4FCF2FBB41F308D444`.
The game retains the earlier ASI until the user runs TraceAliases.

The full Baseline -> TraceAliases -> CollectTrace -> Restore sequence was run
against a synthetic game/kit tree. The report classified one exact-bound test
shader, two installed-but-unseen aliases and five not-installed candidates, then
Restore recovered the original synthetic ASI and ini. No real game files were
used by this validation.
