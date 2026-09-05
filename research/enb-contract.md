# The rendering contract ENBSeries expects

> September 4 correction: the named interface remains useful, but normalized
> assembly equality does not imply raw hash equality. ENB 0.163 recognizes CE
> postfx AA1C0C36 as one of six aliases for the canonical C215BE6E effect.
> The twelve iCEnhancer shaderinput filenames do not match stock CE on disk.
> See [the recovered hash and filename bridge](legacy-shader-bridge.md).

The project plan asks: *"What rendering contract does this ENB expect, and how
can FusionFix expose that contract while retaining its modern fixes?"*

It turns out ENB documents that contract itself, in plain text, inside the
preset. No old-patch reference install is required to read it, and no reverse
engineering of the closed-source binary either.

---

## 1. Where the contract is written down

`enbseries_gta4_v0163.zip` ships `enbeffect.fx` as commented HLSL source. Its
main entry point is named after the hash of the game shader it replaces:

```hlsl
float4 PS_C215BE6E(VS_OUTPUT_POST IN) : COLOR
{
//   Name                         Reg   Size
//   ---------------------------- ----- ----
//   globalScreenSize             c44      1
//   Exposure                     c66      1
//   motionBlurMatrix             c72      4
//   TexelSize                    c76      1
//   dofProj                      c77      1
//   dofDist                      c78      1
//   dofBlur                      c79      1
//   gDirectionalMotionBlurLength c80      1
//   ToneMapParams                c81      1
//   deSatContrastGamma           c82      1
//   ColorCorrect                 c83      1
//   ColorShift                   c84      1
//   PLAYER_MASK                  c85      1
//   GBufferTextureSampler2       s0       1
//   GBufferTextureSampler3       s1       1
//   HDRSampler                   s2       1
//   BloomSampler                 s3       1
//   AdapLumSampler               s4       1
//   JitterSampler                s5       1
//   StencilCopySampler           s6       1
```

That is the whole contract for the post-process stage: twenty named parameters
at fixed registers, carried over from the GTA IV build the preset was made for.
ENB's own effect is written against those registers, so anything that changes
them breaks the preset regardless of anything else.

The preset also declares `sampler2D s13`, which is ENB's own detail texture
(`enbdetail.dds`) rather than something the game provides.

iCEnhancer 4.0's `enbeffect.fx` is a precompiled binary effect rather than
source, but its CTAB lists the same interface — `ScreenSize`, `_c44`, `_c66`,
`_c72`..`_c85`, `texs0`..`texs7`, `texs13`, `texs15` — so the two presets agree.

## 2. Complete Edition still honours it — exactly

`common/shaders/win32_30/rage_postfx.fxc` in CE 1.2.0.59 holds 30 shaders. Four
of them (indices 13, 15, 17, 19) match the table above on **all twenty
parameters**, name and register:

```
rage_postfx_013_ps_3_0   FULL MATCH (20 params)
rage_postfx_015_ps_3_0   FULL MATCH (20 params)
rage_postfx_017_ps_3_0   FULL MATCH (20 params)
rage_postfx_019_ps_3_0   FULL MATCH (20 params)
```

Reading the instruction stream rather than the reflection table gives the same
answer — those shaders read constants `c44, c66, c72..c85` and samplers
`s0..s6`, and nothing else.

Three further variants exist with a shifted layout (`PLAYER_MASK` at c86,
samplers pushed up by one, or the DOF parameters dropped), which is the usual
result of one uber-shader compiled with different feature combinations. The
variant ENB targets is present and unshifted.

**So Complete Edition did not break this part of the contract.** That removes a
whole branch of the plan's decision tree: for the post-process stage there is no
old rendering contract to re-create, because the current game already exposes
it.

## 3. FusionFix does break it

The same measurement over `update/common/shaders/win32_30/rage_postfx.fxc`:

| | constants read | samplers read | reflection table |
|---|---|---|---|
| CE stock | `c44, c66, c72–c85` | `s0–s6` | 28 of 30 shaders have a CTAB |
| FusionFix | `c44, c66, c72–c75, c77, c80–c86, c209, c222` | `s0–s7, s10` | **0 of 30 have a CTAB** |

Three separate departures, each enough on its own:

1. **New dependencies.** The FusionFix shaders read `c209` and `c222`, which no
   part of the game ever writes — they come from FusionFix's own constant
   injection (the z-fighting helper and the FXAA/gamma upload). A FusionFix
   postfx shader running without `ShaderConstantInjection` reads stale
   registers. This is measured, not assumed, and it is why that switch is not
   cosmetic.
2. **Moved and dropped parameters.** `c76`, `c78`, `c79` are gone from most
   variants and `c86` is now used; two extra sampler stages (`s7`, `s10`) are
   bound. An effect compiled against ENB's table would read the wrong things.
3. **No reflection data at all.** RageShaderEditor assembles from `.asm` via
   `D3DXAssembleShader`, which emits no CTAB. Any tool that locates a parameter
   by *name* — and ENB's own effect header, which lists names beside registers,
   suggests it does exactly that — finds nothing to reflect on.

One FusionFix variant, `rage_postfx_019`, still reads precisely `c44, c66,
c72–c85` / `s0–s6`. That is the existence proof for Strategy B in the plan: a
FusionFix shader *can* keep its corrections and still present the legacy
interface, because one of them already does.

## 4. What this means for the reference install

The plan proposed an old GTA IV 1.0.4.0 / 1.0.7.0 install as the reference for
what the preset expects. For the questions that actually matter, it is not
needed:

| Question | Needed the old install? | Answered how |
|---|---|---|
| What interface does ENB expect? | no | `enbeffect.fx` documents it |
| Does CE still provide that interface? | no | measured: 20/20 on four shaders |
| Does FusionFix change it? | no | measured: new constants, moved registers, no CTAB |
| Which game shader does each `shaderinput` file replace? | no | disassembly similarity, `tools/shader_dump/match_enb.py` |
| What is ENB's hash function? | would help | still unidentified — but see below |
| Pixel-exact visual reference | would help | not required for the first milestone |

The hash function remains unidentified, and that is the one place where a known
1.0.x shader would give an instant answer (hash a shader, compare to the
filename). But it is not on the critical path: every conclusion above rests on
*whether the interface and the bytecode changed*, never on reproducing ENB's
specific hash.

If the hash does become necessary, the ENB binary is the place to get it, not
the game — the function is inside `d3d9.dll`, near the code that builds the
`shaderinput\psh%08X.txt` path. That is interop analysis of a file we already
have.

## 5. Consequences for the compatibility design

* The `ENBLegacy` profile's decision to stand FusionFix down from the
  post-process stage is the right shape: CE's own shader already satisfies ENB,
  so the correct move is to let it through untouched.
* `ShaderConstantInjection` and `FusionShaderPackage` genuinely belong together.
  The measurement shows the FusionFix postfx shader reading c209/c222; running
  FusionFix shaders without the injection is a broken configuration, and running
  stock shaders with it is merely wasteful.
* Strategy B is viable for at least the post-process shader, because one
  FusionFix variant already keeps the legacy register layout.

## 6. Reproducing these measurements

```
set G=C:\Games\Steam\steamapps\common\Grand Theft Auto IV\GTAIV
python tools/shader_dump/dump_fxc.py "%G%\common\shaders\win32_30\rage_postfx.fxc" ^
       --out out --label ce-postfx --asm
python tools/shader_dump/dump_fxc.py "%G%\update\common\shaders\win32_30\rage_postfx.fxc" ^
       --out out --label ff-postfx --asm
python tools/shader_dump/check_interface.py --contract research/contracts/enb-postfx.json ^
       "CE stock=out/ce-postfx" "FusionFix=out/ff-postfx"
```
