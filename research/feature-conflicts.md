# FusionFix feature map and ENB conflict classification

Which parts of FusionFix can survive alongside an old ENB preset, which cannot,
and which are still unknown.

Classification follows the project plan:

* **A -- Safe.** Does not touch the renderer. Keep unchanged.
* **B -- Conditionally safe.** Touches the renderer but not the parts ENB owns.
  Keep unless testing says otherwise.
* **C -- Rendering conflict.** Needs an ENB-compatible variant.
* **D -- Mutually exclusive.** Disable while ENB mode is active.

A category is a *hypothesis* until a row's "verified" column says otherwise.
Nothing below has been confirmed in a running game with ENB installed; the
categories come from reading the code and from static analysis of the shader
packages (see [research-log.md](research-log.md)).

---

## 1. Renderer-touching features

| Feature | Source | Shader dep. | Device calls | Game hooks | Category | Switch |
|---|---|---|---|---|---|---|
| Post-process replacement (tone map path, final blit) | `postfx.ixx` | yes | yes | yes | **D** | `ReplacePostFX` |
| FXAA / SMAA | `postfx.ixx` | own shaders | yes | via above | **D** | `PostProcessAA` |
| Ambient occlusion | `postfx.ixx` | own `AO.fx` | yes | yes | **D** | `AmbientOcclusion` |
| Sun shafts | `postfx.ixx` | own shaders | yes | via above | **D** | `SunShafts` |
| Pre-alpha depth copy | `postfx.ixx` | yes | yes | yes | **C** | `PreAlphaDepthCopy` |
| Sky drawn twice into GBuffer diffuse | `postfx.ixx` | yes | yes | yes | **C** | `SkyDiffuseSplit` |
| Console gamma blit at EndScene | `consolegamma.ixx` | own shaders | yes | no | **D** | `ConsoleGammaBlit` |
| Shader constant injection c208..c223 / c227..c237 | `shaders.ixx` | yes | yes | yes | **C** | `ShaderConstantInjection` |
| Replacement shader package | `shaders/` submodule | is the dep. | no | path hook | **D** | `FusionShaderPackage` + `StockShaderFolder` |
| Reflection MSAA | `reflectionmsaa.ixx` | no | no | yes | **B** | off by default |
| Seasonal snow overlay | `seasonal/snow.ixx` | own shaders | yes | yes | **B** | seasonal, event-gated |
| Extra dynamic shadows | `shadows.ixx` | yes | no | yes | **B** | `[SHADOWS] ExtraDynamicShadows` |
| Night shadows | `nightshadows.ixx` | yes | no | yes | **B** | -- |
| LOD lights / coronas (Project2DFX) | `lodlights.ixx`, `coronas.ixx` | no | some | yes | **B** | `[PROJECT2DFX]` |
| Timecycle extensions | `timecyc.ixx`, `timecycext.ixx` | yes | no | yes | **B** | -- |
| Shader-adjacent memory patches (reflection multiplier, mirror plane, car dirt, water RT size, contrast offset, rain lighting) | `shaders.ixx` | no | no | yes | **B** | -- |
| VRAM reporting | `vram.ixx` | no | trivial | yes | **A** | -- |

The `D3D9Trace` instrumentation in `source/enb_compat/enbtrace.ixx` is not in
this table: it is a diagnostic, off by default, and alters no call.

## 2. Renderer-independent features -- category A

Keep all of these unchanged in ENB mode. None of them issues a D3D9 call or
touches a shader.

Gameplay and input: `rawinput.ixx`, `buttons.ixx`, `cheats.ixx`,
`brakelights.ixx`, `turnindicators.ixx`, `ikeeponwalking.ixx`, `sniper.ixx`,
`led.ixx`.
Camera: `centeredcam.ixx`, `cutscenecam.ixx`, `vlikestuntcam.ixx`,
`widescreenfix.ixx`.
UI, text and menus: `gxtloader.ixx`, `altdialogue.ixx`, `extrainfo.ixx`,
`settings.ixx`, `userdata.ixx`, `skipintro.ixx`, `loadingdelays.ixx`.
Timing: `framelimit.ixx`, `frameratevigilante.ixx`.
Streaming, limits and content: `imgloader.ixx`, `rpfloader.ixx`, `limits.ixx`,
`preloadlist.ixx`, `episodiccontent.ixx`, `modupdater.ixx`, `deathmusic.ixx`,
`windowed.ixx`, `fixes.ixx`.

This is the bulk of FusionFix, and it is the reason an ENB compatibility mode is
worth having rather than simply telling people to uninstall.

## 3. The specific conflicts, and the evidence for each

### 3.1 Shader identity -- the dominant one

**Claim.** ENBSeries recognises a game shader by hashing its compiled bytecode
and, on a match, substitutes the assembly in `shaderinput/psh<HASH>.txt` or
`vsh<HASH>.txt`. FusionFix replaces every shader in the game, so every hash
changes and no substitution ever fires.

**Evidence.**

* Both ENB archives in `ENB resources/` contain a `shaderinput/` directory whose
  filenames are `psh` or `vsh` followed by exactly eight hex digits, and whose
  contents are D3D9 shader assembly. enbseries 0.163 ships four; iCEnhancer 4.0
  ships twelve.
* The same hash appears in both presets with *different* file contents
  (`psh2DF967C6.txt` is 2239 bytes in enbseries 0.163 and 1527 bytes in
  iCEnhancer 4.0), so the hash names the shader being replaced, not the
  replacement.
* Comparing the stock CE `common/shaders/win32_30` set (1689 shaders) against
  the FusionFix `update/common/shaders/win32_30` set (1739) with
  `tools/shader_dump/compare_sets.py`: **1689 compared, 0 identical, 1689
  changed, 50 added.** Of the 638 *distinct* shader bytecodes in the stock set,
  exactly **2** still exist byte-identical anywhere in the FusionFix set.
* Restricting the comparison to the instruction body, ignoring `def` and `dcl`:
  320 of the 1689 are unchanged apart from constant declarations; 1369 were
  genuinely rewritten.

**What follows.** For an old preset to work at all, the shaders it hashes have
to be present in the form it expects. `FusionShaderPackage = 0` arranges that at
runtime: FusionFix's path hook normally collapses the game's six shader-variant
folders onto `win32_30`, the one its package overlays, and with the switch off
it targets `StockShaderFolder` instead, which nothing overlays. Nothing is moved
or deleted. The 320 shaders whose bodies match are the candidates for Strategy
B -- a FusionFix variant that keeps the correction but restores the interface.

**Complete Edition, by contrast, did not change these shaders.** Matching the
iCEnhancer 4.0 `shaderinput` files against the stock CE set by normalised
disassembly gives three similarity-1.000 identifications and three more above
0.9 -- the game shader's entire instruction body appears verbatim inside the ENB
replacement. Whatever broke, CE's shader *code* is not it. See
[enb-contract.md](enb-contract.md).

**Not established.** Which hash function ENB uses. CRC32, Adler-32, FNV-1a/1,
Jenkins one-at-a-time, MurmurHash2/3, additive and XOR checksums were each tried
over six framings of every shader blob in the stock CE `common/shaders` tree;
nothing produced any of the twelve target hashes. Given that the shader *bodies*
are demonstrably unchanged from what the presets expect, the likeliest
explanation is a hash not in that list rather than a changed shader. It is not
on the critical path either way -- every conclusion here rests on whether
bytecode and interfaces changed, never on reproducing ENB's specific hash. If
it does become necessary, the function lives in ENB's `d3d9.dll`, near the code
that builds the `shaderinput\psh%08X.txt` path.

### 3.2 Post-process ownership

FusionFix replaces the game's post-process draw outright and, with console gamma
on, blits to the real back buffer at EndScene. ENB applies `enbeffect.fx` at the
same point. Both cannot have the last word.

Category D, not C: there is no version of "both run" that produces a correct
image, because each is a complete tone-mapping and output stage.

Beyond ownership, the *interface* diverges, and this one is measured. ENB's
`enbeffect.fx` documents the exact parameter table it expects from the game's
post-process shader. Checking both shader sets against it with
`tools/shader_dump/check_interface.py`:

| | honours the contract | reads | reflection data |
|---|---|---|---|
| CE stock | **4 of 7 candidates, 20/20 by name** | `c44, c66, c72–c85` / `s0–s6` | 28 of 30 shaders have a CTAB |
| FusionFix | 0 of 13 | `+c86, c209, c222`, `−c76, c78, c79` / `+s7, s10` | **0 of 30 have a CTAB** |

`c209` and `c222` come from FusionFix's own constant injection, so the FusionFix
post-process shader cannot run correctly with `ShaderConstantInjection` off —
which is exactly why those two switches belong together. Full analysis in
[enb-contract.md](enb-contract.md).

### 3.3 Constant registers -- probably *not* a conflict

FusionFix writes pixel c208..c223 and vertex c227..c237.

Reading the ENB replacement assembly in both presets: the pixel shaders declare
`def c150`, `c175`, `c177`, `c178` and read game constants c39, c52, c66,
c72..c75. The two iCEnhancer vertex shaders read c208..c222 -- but those are
*vertex* registers, and FusionFix's vertex range starts at c227.

So on the register map there is no overlap in either stage. This is worth
recording precisely because it removes a plausible-sounding hypothesis: if
lighting comes out wrong under ENB, a register collision is not the reason.

Caveat: this is the register map of the *replacement* shaders, which is what ENB
compiles when a hash matches. If no hash matches, those shaders never run, and
the question is moot.

### 3.4 Sampler stage 13 -- unresolved

ENB's replacement pixel shaders declare `dcl_2d s13` and sample it (the detail
texture, `enbdetail.dds`). FusionFix's sun-shaft prepass binds stage 13 as well:
`pDevice->SetTexture(13, PostFxResources.DiffuseTex)` in `postfx.ixx`.

Whether these actually collide depends on whether the bindings survive across
the passes involved, which needs a capture. Set `TraceTextures = 1` and check
which passes touch stage 13.

### 3.5 Hook ordering -- much less of a problem than expected

As shipped, FusionFix installs **no** hooks on any `IDirect3DDevice9` method.
`fusiondxhook.ixx` -- the only code in the repository that would -- begins with
an unconditional `return;`. So the double-hooking failure mode the plan warns
about does not currently exist between these two mods.

What does need deciding is the DLL chain, since both want to be `d3d9.dll`. See
[proxy-chain-results.md](proxy-chain-results.md).

### 3.6 Graphics API

The installed configuration at the time of writing has `d3d9.cfg` set to
`[MAIN] API = 1`, which loads `vulkan.dll` (DXVK). ENBSeries is a D3D9 wrapper
and will not work through it. `API = 0` is a precondition for every experiment
in this project.
