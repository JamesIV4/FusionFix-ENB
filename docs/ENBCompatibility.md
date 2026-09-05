# ENB compatibility mode

**September 5 review:** the current baseline has unresolved tree constant/depth
and shadow/G-buffer compatibility gaps. It loads and runs shader probes, but
its visual correctness is not established. Further preset tests are paused;
see [the review](../research/regular-enb-review.md) before using these setup
instructions as a validated configuration.

A way to run an old GTA IV ENB preset on Complete Edition 1.2.0.59 alongside
FusionFix, keeping the parts of FusionFix that have nothing to do with the
renderer.

**This is unfinished work.** Earlier tests rendered ENB 0.163 on CE with stock
shaders and DOF enabled. The user has since confirmed that a recovered stock-CE
terrain alias triggers ENB substitution: the combined diagnostic rendered a
localized magenta ground strip. The unchanged aliases restore textured terrain
at that location, but broader rendering failures prevent a quality verdict.
The individual 2-/3-/4-layer member, selective package and full iCEnhancer 4
setup remain unverified. September 4 tests recovered and validated iCEnhancer's compiled
effect interfaces independently of its ASI; see
[the reopened investigation](../research/legacy-shader-bridge.md). What is known
and what is guessed is set out in [research/](../research/). Read
[research/feature-conflicts.md](../research/feature-conflicts.md) before
concluding anything from a result.

With `Mode = 0` — the default — nothing changes. Every feature switch defaults
to on, so no hook that upstream FusionFix installs is skipped.

---

## The problem in one paragraph

ENBSeries hashes the exact shader bytecode submitted to D3D9. CE's stock
postfx pass is already recognized as AA1C0C36, one of six accepted hashes.
However, none of iCEnhancer 4's twelve original shaderinput filenames matches
stock CE's on-disk shader bytes. Three normalized terrain instruction bodies
match, supporting a filename alias bridge. A combined runtime probe has now
confirmed that at least one recovered terrain filename is accepted; this does
not mean every individual mapping is confirmed.

Modern FusionFix also changes the renderer's pass ownership, resource bindings
and depth representation. A stock pixel shader cannot simply replace its modern
counterpart while keeping incompatible samplers or paired vertex outputs.
See [the recovered mapping](../research/legacy-shader-bridge.md) and
[the user-run alias test](../research/alias-test.md). Full iCEnhancer rendering
and the mixed stock/FusionFix shader package remain unverified.

## Setting it up

### 1. Switch off DXVK

ENBSeries is a Direct3D 9 wrapper. It cannot work through the Vulkan path.

In `GTAIV/d3d9.cfg`:

```ini
[MAIN]
API = 0
```

### 2. Decide who owns `d3d9.dll`

Both mods ship one. The simplest arrangement that can work is to let ENB have
the name: FusionFix's wrapper only forwards exports, and the `.asi` is loaded by
Ultimate ASI Loader regardless, so deleting it costs nothing except the DXVK
option you just turned off.

If you want to keep FusionFix's wrapper in place, rename ENB's to
`enbseries_d3d9.dll` and chain to it:

```ini
[MAIN]
API = 0
ProxyLibrary = enbseries_d3d9.dll
```

Or use ENB's Injector build, which never competes for the name.

The permutations and what to record for each are in
[research/proxy-chain-results.md](../research/proxy-chain-results.md).

### 3. Let the stock shaders through

Nothing has to be deleted or swapped.

The game keeps six GPU-specific shader-variant folders — `win32_30`,
`win32_30_low_ati`, `_nv6`, `_nv7`, `_nv8`, `_atidx10` — and picks one at
runtime. FusionFix collapses every lookup onto `win32_30`, which is the one
folder its own package overlays, so that it only has to ship one shader set.

With `FusionShaderPackage = 0` the collapse targets a different folder, which
nothing overlays, and the game loads the stock shaders straight out of
`common/shaders`. The FusionFix package stays on disk, untouched and inert.

The overlay works **per file**, so what you place in that folder decides,
container by container, which side wins. Two useful arrangements:

### Selective — keep most of FusionFix (recommended)

An ENB preset replaces a handful of shaders, not all of them. Only the
containers holding those need to come from stock; everything else can stay
FusionFix.

```
python tools/shader_dump/make_vanilla_package.py ^
    --game "C:\Games\Steam\steamapps\common\Grand Theft Auto IV\GTAIV" ^
    --selective
```

Measured against CE 1.2.0.59, the default set gives up 9 containers holding 191
of 1739 FusionFix shaders — **89% of FusionFix's shader work retained**.

`--keep-stock list` prints the containers and what each one costs.
`--keep-stock a.fxc b.fxc` overrides the set. `deferred_lighting.fxc` is
excluded by default: it holds 62 shaders and only two of them are targeted (the
vegetation wind-sway vertex shaders), so it is a poor trade unless the preset's
tree animation specifically matters.

**Keep `ShaderConstantInjection = 1` in this mode.** Most of the FusionFix
shaders are still loaded and still read c208..c223 / c227..c237; with the
uploads off they would read stale registers. `ENBCompat.log` warns if the two
disagree.

### All stock

```
python tools/shader_dump/make_vanilla_package.py ^
    --game "C:\Games\Steam\steamapps\common\Grand Theft Auto IV\GTAIV" ^
    --stage-extras
```

Builds and copies one file: a compatibility variant of `gta_trees_extended`,
the single shader FusionFix genuinely adds rather than replaces. Its content
packages reference it, and without it the game throws a resource error before
the main menu. The compatibility build removes FusionShaders' five explicit
log-depth writes so it can share the stock depth pipeline; its alpha and wind
still require the high-register provider. Everything else falls through to stock.

Either way, undoing it is deleting the folder the tool names.

### 4. Turn the mode on

In `GTAIV/plugins/GTAIV.EFLC.FusionFix.ini`:

```ini
[ENBCompatibility]
Mode = 1
FusionShaderPackage = 0
StockShaderFolder = win32_30_nv8
ShaderConstantInjection = 1   ; required by the compatibility extended-tree shader
ShadowPipelineFixes = 0
FusionShaderTweaks = 0
```

`StockShaderFolder` picks which variant the stock shaders come from. It matters
only if the preset's hashes were computed against a different one — on CE
1.2.0.59, `win32_30` and `win32_30_nv8` are byte-identical for 1688 of their
1689 shaders, so start with the default and treat the others as a six-way
bisect if nothing lands. `win32_30` itself is not useful here, since that is the
folder the FusionFix package overlays.

Should you prefer to hand the preset `win32_30`'s bytes specifically, the older
route still exists: `make_vanilla_package.py --out <dir>` builds a replacement
`update/common/shaders` from the stock shaders plus FusionFix's addition, and
`--install` puts it in place after renaming the existing folder to
`shaders.bak-<timestamp>`.

`Mode = Auto` enables it when an ENB is detected in the process — a loaded
`enbseries.dll`/`enbhelper.dll`, or an `enbseries.ini`, `enbeffect.fx`,
`enbbloom.fx` or `shaderinput/` next to the exe. Explicit `1` is better while
anything is still being diagnosed.

Check `GTAIV/ENBCompat.log`. It records the resolved profile, every feature
switch, and whether the installed shader package matches what the config says.

## Depth of Field must be on

**Set Depth of Field to Low or higher.** Off and Cutscenes Only do not work, and
the failure is silent and misleading -- the image comes out washed out and
overexposed with no hint that a menu setting is responsible.

GTA IV's `rage_postfx.fxc` holds 28 passes, and the final composite exists as a
depth-of-field variant (`#13`) and a no-DOF variant (`#29`). Their register
layouts differ: `#29` drops `dofDist` and `BloomSampler` and shifts everything
after them down one, so only 8 of ENB's 20 expected parameters land where it
expects. ENBSeries matches a shader by a single hash of its bytecode, so a preset
can only carry a replacement for one variant, and the presets examined here
target the DOF one. With DOF off the game binds `#29`, nothing matches, the
game's own tone mapping runs, and ENB stacks bloom and adaptation on top of an
already tone-mapped image.

That is a property of how ENB identifies shaders, not something this
compatibility layer can route around. `ENBCompat.log` warns when the setting is
wrong. Confirmed by runtime capture -- see
[research/research-log.md](../research/research-log.md), 2026-09-02.

## ENB's in-game editor

**Shift+Enter** opens ENB's own GUI: sliders for everything in `enbseries.ini`,
applied live, with a save button that writes the file back. Present since ENB
v0.127, so any build you are likely to use has it. It is much the fastest way to
tune brightness and adaptation.

Keys as configured by these instructions:

| key | does |
|---|---|
| Shift+Enter | open / close the settings GUI |
| Shift+F11 | toggle the ENB effect (moved off F12 -- Steam takes that for screenshots) |
| Backspace | reload `enbseries.ini` from disk |
| F10 | toggle ambient occlusion |
| Numpad `*` | show FPS |

`KeyCombination=16` is Shift, which is why the toggle needs the modifier held.

## What the mode changes

| Switch | What stops happening |
|---|---|
| `ReplacePostFX` | FusionFix no longer replaces the game's post-process draw |
| `PostProcessAA` | no FusionFix FXAA or SMAA |
| `AmbientOcclusion` | no FusionFix AO pass |
| `SunShafts` | no FusionFix sun shafts |
| `PreAlphaDepthCopy` | no depth copy before the alpha pass |
| `SkyDiffuseSplit` | the sky is drawn once, not twice |
| `ConsoleGammaBlit` | no gamma blit to the back buffer at EndScene |
| `ShadowPipelineFixes` | preserve stock shadow/G-buffer formats, cascade ranges and matrices |
| `FusionShaderTweaks` | preserve native-D3D9 adaptive states and stock reflection/contrast behavior |
| `ShaderConstantInjection` | uploads to pixel c208..c223 / vertex c227..c237; remains on for extended-tree alpha/wind |
| `FusionShaderPackage` | shader lookups point at `StockShaderFolder`, so the game loads its own shaders instead of FusionFix's |

Everything else stays: gameplay and input fixes, camera, menus and UI, text,
frame limiting, streaming and limits, episodic content, timecycle work, LOD
lights and coronas, and the shader-adjacent memory patches that do not depend on
the replacement shaders (reflection multiplier, mirror plane offset, console car
dirt, water render-target size, contrast offset, rain lighting).

Each switch can be set on its own, in either mode, which is how you bisect one
feature at a time:

```ini
[ENBCompatibility]
Mode = 1
ReplacePostFX = 1     ; ENB mode, but put the post-process replacement back
```

## Diagnostics

The D3D9 tracer alters no call. Output goes to `GTAIV/ENBCompat/`.

```ini
[ENBCompatibility]
D3D9Trace = 1
DumpShaders = 1
TraceStartFrame = 2000     ; past the loading screens
TraceFrameCount = 3
```

* `d3d9_trace.log` — the calls, one frame per bracketed number.
  `tools/d3d9_trace/summarize_trace.py` folds it into per-frame counts of render
  targets, depth surfaces, created resources and sampler stages.
* `shaders.csv` — one row per distinct shader the game created, with the raw and
  comment-stripped CRC32 of its bytecode and whether it carries the
  `FusionShader` marker. `tools/frame_compare/compare_shader_csv.py` diffs two
  runs and reports how many shaders survive with their bytecode intact.
* `ENBCompat/shaders/*.cso` — the blobs themselves, with `DumpShaders = 1`.
  `fxc /dumpbin` disassembles them.

`TraceTextures`, `TraceConstants` and `TraceDraws` add per-call lines and are
heavy; turn one on at a time. The resource-usage summary written at shutdown
lists every constant register and sampler stage touched during the run, which is
usually enough without any of them.

The tracer patches the device vtable rather than inline-patching D3D9 exports,
so it composes with whatever wrapper is loaded: each thunk calls the stored
original, which still lands inside ENB's hook if it has one.

Known gap: only `Present` is hooked, not `PresentEx`. Under a D3D9Ex path the
frame counter will not advance.

## Offline tooling

None of these need the game running.

| Tool | Does |
|---|---|
| `tools/shader_dump/dump_fxc.py` | extracts and fingerprints every shader in a set of `.fxc` containers; `--asm` also disassembles |
| `tools/shader_dump/compare_sets.py` | compares two such sets and reports how many shaders keep their bytecode |
| `tools/shader_dump/match_enb.py` | identifies which game shader each ENB `shaderinput` file replaces, by disassembly similarity |
| `tools/shader_dump/check_interface.py` | checks a shader set against a declared interface contract |
| `tools/shader_dump/make_vanilla_package.py` | builds the hybrid shader package described above |

Example — quantify what FusionFix changes:

```
set G=C:\Games\Steam\steamapps\common\Grand Theft Auto IV\GTAIV
python tools/shader_dump/dump_fxc.py "%G%\common\shaders\win32_30"        --out out --label ce-stock
python tools/shader_dump/dump_fxc.py "%G%\update\common\shaders\win32_30" --out out --label ce-fusionfix
python tools/shader_dump/compare_sets.py out/ce-stock.json out/ce-fusionfix.json
```

## What is *not* bypassed

Worth being explicit, because "bypass the shader changes" is easy to read as
more than it is.

ENB replaces a *handful* of shaders, not all of them: enbseries 0.163 ships four
`shaderinput` files and iCEnhancer 4.0 ships twelve (a superset of those four),
plus one more in `enbeffect.fx` — **13 distinct targets**, against 1689 shaders
in the game. Turning the FusionFix package off does not hand those 1689 to ENB;
it hands them back to **the stock game**, which is what the preset was built
against and expects to find.

That is what `--selective` exploits: only the containers holding one of those 13
have to come from stock.

FusionFix keeps everything that is not a shader either way: gameplay and input
fixes, camera, menus and UI, text, frame limiting, streaming and limits,
episodic content, LOD lights and coronas, and the memory patches in
`shaders.ixx` that adjust game behaviour rather than shader code (reflection
multiplier, mirror plane offset, console car dirt, water render-target size,
contrast offset, rain lighting).

What a container costs when it is given up is the FusionFix work inside it —
shadow filters, tone mapping, volumetric fog, tree lighting — plus the
post-process chain the profile switches off separately.

## Going back

Set `Mode = 0`. If you staged the extras, delete the
`update/common/shaders/<variant>` folder it created; if you used `--install`,
restore `update/common/shaders` from the `.bak-*` folder. Put `d3d9.dll` back
and set `API` to what it was. Nothing else is written outside `ENBCompat.log`
and the `ENBCompat/` folder.
