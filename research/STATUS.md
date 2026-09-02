# Status

Where the ENB compatibility project stands, as of 2026-09-02.

The game folder has been reverted to a stock FusionFix 5.0.1 install. Everything
needed to reproduce a test setup lives in this repository —
[tools/gamesetup/](../tools/gamesetup/) installs it and takes it out again.

---

## The headline

**ENBSeries 0.163 works on GTA IV Complete Edition 1.2.0.59, with FusionFix.**

That was the question the whole project hung on, and it was genuinely open: the
community position is "downgrade to 1.0.4.0", and nobody had shown otherwise.
It initialises, its shader substitution fires, its post-process replaces the
game's, its in-game GUI works, and FusionFix keeps everything that is not a
shader.

Two conditions, both now understood rather than guessed:

1. `d3d9.cfg` must be `[MAIN] API = 0`. ENB is a D3D9 wrapper; on the DXVK path
   it does nothing at all.
2. **Depth of Field must be Low or higher.** Off and Cutscenes Only make the
   game bind a post-process pass no preset carries a replacement for.

**iCEnhancer 4 does not work**, and cannot be made to without a large
reverse-engineering effort. See below.

## What is settled

| Question | Answer | How |
|---|---|---|
| Does ENB initialise on CE? | yes | run |
| Does its shader substitution fire? | yes | visual probes in its own `shaderinput` files |
| Did CE break the shaders presets target? | **no** | 3 of 12 match stock CE at similarity 1.000 |
| Does CE still expose ENB's post-process interface? | **yes, exactly** | 4 passes match all 20 parameters |
| Does FusionFix break it? | yes | 1689 shaders, 0 with unchanged bytecode |
| Do they collide on constant registers? | no | register maps do not overlap |
| Do they double-hook D3D9? | no | FusionFix hooks no device method |
| Which pass does ENB replace? | `rage_postfx#13`, crc `1895B35D` | constants, DOF path, absence of a select |
| Why does DOF matter? | `#13` is the DOF composite; `#29` is not, and its layout is shifted | runtime capture, indoors vs outdoors |
| Can FusionFix be kept alongside? | yes, ~89% of its shaders | container analysis |
| Is an old-patch install needed? | **no** | the contract is in `enbeffect.fx`; CE satisfies it |

## What was built

**In the mod** — [source/enb_compat/](../source/enb_compat/):

* `enbcompat.ixx` — `RendererCompatibilityProfile` with `FusionFixDefault` /
  `ENBLegacy`, `[ENBCompatibility]` config, ENB detection, shader-package
  detection (stock / FusionFix / mixed), logging. `Mode = 0` is upstream
  FusionFix, unchanged: every switch defaults on and no hook is skipped.
* `enbtrace.ixx` — opt-in D3D9 tracer. Shader fingerprinting by the same hash
  the offline tools use, shader-bind logging, hotkey-triggered capture.
* `enbversion.ixx` — version spoofing for plugins whose check reads the
  executable's version resource. Scoped by caller module. Off by default.

Renderer features are gated at *hook-installation* time in `postfx.ixx`,
`shaders.ixx` and `consolegamma.ixx`, so ENB mode leaves the original game code
path untouched rather than running a guarded version of it.

**Offline tooling** — [tools/shader_dump/](../tools/shader_dump/):
`.fxc` extraction and fingerprinting, set comparison, ENB `shaderinput`
identification with declaration filtering, interface checking against a declared
contract, selective package building, and `.fxc` slot splicing.

**Setup tooling** — [tools/gamesetup/](../tools/gamesetup/): reversible install,
restore, and scripts to switch configuration, preset, and preset components.

## What is open

**Tuning.** ENB 0.163 renders, but the image was still over-bright at the point
testing stopped. With DOF on this is a tuning problem, not a substitution
failure — `[ADAPTATION]` and `EBrightnessV2`, driven live from ENB's GUI
(Shift+Enter).

**The selective package is untested in game.** `--selective` keeps ~89% of
FusionFix's shaders by serving only the ENB-targeted containers from stock. It
builds and verifies; nobody has run it.

**Four of thirteen shader targets are unidentified.** `323E9BB8`, `F5256B40`,
`8DB4CDB2` narrow to a family but not a shader; `46A43A9F` has no CE shader with
a matching declaration signature at all.

**A sky flicker** was seen with the ENB effect toggled off, and never captured —
tracing was disabled at the time.

**How much of iCEnhancer 4's preset runs without its ASI.**
`ENBCompat-Mix.cmd` bisects it; not yet run.

## The iCEnhancer 4 result

Worth stating plainly because it was the goal.

iCEnhancer 4 (July 2025) is deliberately scoped to patches 1.0.3.0 and 1.0.4.0.
Its `icenhancer.asi` checks the game version by reading `GTAIV.exe`'s version
resource — which we can satisfy from outside, and did. But the check turned out
to gate **1.0.4.0-specific work on the executable**: with the check passed, it
faults inside `GTAIV.exe` at `+0x008d6d22` during its own `DllMain`, before
`LoadLibrary` returns. Its preset also fails without it.

A version number can be exposed. A 1.0.4.0 memory map cannot. Getting further
means mapping its hard-coded addresses onto CE inside a packed anti-tamper
binary — a different kind of project to this one, which worked precisely because
it never needed to touch ENB's code.

That does not undo the rest. The compatibility layer, the DOF finding, the
shader analysis and the tooling apply to any preset that is not version-locked
to an executable — and ENBSeries 0.163 itself is one.

## Next, in order

1. Reinstall with `tools/gamesetup/install.ps1`, ENB 0.163, DOF on, and judge
   the image against the preset's intended look. Tune from ENB's GUI.
2. Re-run with `-Selective` and compare — how much FusionFix survives alongside.
3. Capture the sky flicker with `D3D9Trace = 1` and `TraceShaderBinds = 1`.
4. `ENBCompat-Mix.cmd shaders` — does iCEnhancer 4's shader set run on 0.163
   alone?
5. Resolve the four unidentified shader targets before trusting the selective
   container list for a preset that uses them.
