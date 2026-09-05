# FusionFix rendering pipeline, as it stands

> September 5 correction: regular ENB review found that the prior profile did
> not gate `shadows.ixx` resource/cascade changes or several FusionShader state
> tweaks. ENBLegacy now disables those via `ShadowPipelineFixes` and
> `FusionShaderTweaks`; the required extended tree uses a stock-depth rebuild
> with c221/c233 uploads retained. See
> [regular-enb-review.md](regular-enb-review.md).

Reconnaissance for the ENB compatibility work. Everything here was read out of
this repository at commit `c3f9a9a` and out of a Complete Edition 1.2.0.59
install; nothing is inferred from documentation.

Where a claim has not been verified in a running game it says so.

---

## 1. What FusionFix ships

| Piece | Path in this repo | Path in the install |
|---|---|---|
| The ASI | `source/**.ixx` → `bin/GTAIV.EFLC.FusionFix.asi` | `GTAIV/plugins/` |
| A `d3d9.dll` wrapper | `source/d3d9/d3d9.cpp` | `GTAIV/d3d9.dll` |
| A replacement shader package | `shaders/GTAIV.EFLC.FusionShaders` (submodule) | `GTAIV/update/common/shaders/` |
| Content packages | `data/update/GTAIV.EFLC.FusionFix/` | `GTAIV/update/GTAIV.EFLC.FusionFix/` |

The `d3d9.dll` is not a rendering wrapper. It forwards all seventeen D3D9
exports to either the system `d3d9.dll` or, when `d3d9.cfg` has `[MAIN] API=1`,
to `vulkan.dll` (a DXVK build). It creates no device and wraps no interface. Its
only other job is to exist so the game has something to load.

All actual rendering work is done by the ASI, through pattern-scanned hooks on
the game's own code plus direct calls on the device pointer the game already
holds (`rage::grcDevice::ms_pD3DDevice`).

## 2. How shaders are built and loaded

Source form is Direct3D 9 shader assembly, one file per shader:

```
shaders/GTAIV.EFLC.FusionShaders/win32_30_nv8/<shader>/<shader>PS<n>.asm
                                             /<shader>VS<n>.asm
```

`buildshaders.bat` runs `tools/RageShaderEditor/RageShaderEditor.exe` over the
`.xml` manifests to assemble each set into a RAGE `.fxc` container, copies every
`.fxc` into `data/update/common/shaders/win32_30/`, and copies
`shaders/GTAIV.EFLC.FusionShaders/resources` over `data/update`.

`snippets/AddShadersSignature2.lua` stamps an identifying constant into each
shader before assembly: `def c219, <4 floats>` for pixel shaders and
`def c230, ...` for vertex shaders. Those float bytes spell `FusionShader`
followed by a little-endian integer id. `GetFusionShaderID()` in
[shaders.ixx](../source/shaders.ixx) reads it back out of the bytecode at
runtime. It is also the cheapest way to tell, from the outside, whether an
installed `.fxc` came from FusionFix or from the stock game --
`ENBCompat::DetectShaderPackage()` uses exactly that.

At runtime FusionFix redirects every shader-variant path to one folder, so the
`win32_30_nv8` / `win32_30_atidx10` / `win32_30_low_ati` sets in the stock
install are never consulted once the ASI is loaded; only `win32_30` is -- which
is the folder its own package overlays, and is how the FusionFix shaders come to
be loaded at all. `[ENBCompatibility] FusionShaderPackage = 0` retargets that
same hook at a folder nothing overlays, which is the whole of the runtime
bypass. It also patches the in-memory path for `win32_30/rage_perlinnoise.fxc`
to a loose file if one exists next to the exe.

The six variants are near-duplicates: `win32_30` and `win32_30_nv8` are
byte-identical for 1688 of their 1689 shaders on CE 1.2.0.59, the exception
being `deferred_lighting.fxc#11`.

### Package contents, measured

`update/common/shaders/win32_30` in a FusionFix 5.0.1 install holds 103 `.fxc`
containers: the same 102 names the stock game has, all rewritten, plus one
genuinely new shader, `gta_trees_extended` (with `db/gta_trees_extended.sps` and
`dcl/gta_trees_extended.dcl`). That single addition is why deleting the package
outright produces a resource error before the main menu -- the FusionTrees
content package references a shader that no longer exists.

## 3. Where FusionFix touches D3D9

Only these modules issue D3D9 calls or install rendering hooks. Everything else
in `source/` is gameplay, input, UI, streaming, text or timing.

### `postfx.ixx` -- the largest surface by far

Four call-site hooks and one inline hook, all installed from `onInitEventAsync`:

| Hook | Target | Effect |
|---|---|---|
| `hbDrawPrimitivePostFX` | the game's post-process draw | dispatches to `NewFog()` or `NewPostFX()` instead of the original draw |
| `hbDrawCallPostFX` | the post-process draw call site | arms the above |
| `hbDrawSkyHook` | the sky draw | runs it twice, the first time with RT1 pointed at the GBuffer diffuse texture |
| `hbDrawCallFog` | the fog draw call site | arms `NewFog()`, which takes the pre-alpha depth copy |
| `RenderPedAndVehicleFakeShadows` | after ped/vehicle fake shadows | appends the ambient-occlusion pass |

`NewPostFX()` replaces the game's entire tail of the frame: it re-binds the
saved pre-post-process textures, runs sun shafts (three half-res passes), calls
the original post-process draw into either the back buffer or a temp target,
then optionally runs FXAA or the three SMAA passes and blits to the back buffer.
It also creates its own render targets: `FullScreenTex_temp1/2`,
`FullScreenDownsampleTex/2`, `edgesTex`, `blendTex`, `AOTex`, `AOBlurTex`,
`AOCamDepthTex`, `PreAlphaDepthCopyRT`.

### `shaders.ixx` -- constant injection

Three upload sites, all writing registers only the FusionFix shaders read:

* a mid hook at BeginScene -- pixel **c208, c210, c211, c217, c218, c220, c221,
  c222, c223**, vertex **c233, c235, c236, c237**;
* an `OnBeforeLighting` render-list callback -- pixel **c212..c216**, vertex
  **c228, c229, c231, c232, c234**;
* a mid hook on the viewport transform update (the z-fighting helper) -- pixel
  **c209**, vertex **c227**.

So the FusionFix-owned ranges are **pixel c208..c223** and
**vertex c227..c237**.

`shaders.ixx` also applies a number of one-off memory patches that have nothing
to do with the shader package: reflection multiplier, mirror plane offset,
console car dirt, water render-target resolution, contrast slider offset, and
the rain-lighting read from `visualSettings.dat`. Those are independent of any
external post-processor.

### `consolegamma.ixx`

At the game's EndScene, if the console-gamma menu option is on, it
`StretchRect`s the current render target into its own texture, then draws a
full-screen quad through `PS_BlitGamma` onto **the real swap-chain back
buffer**. This is the last thing FusionFix does in a frame and it is the same
slot an external post-processor wants.

### `reflectionmsaa.ixx`

Patches multisample counts for the reflection render targets. Off by default
(`ReflectionMSAAQuality = 0`).

### `seasonal/snow.ixx`

Draws a screen-space snow overlay, and only when the snow seasonal event is
active. Two `DrawPrimitive` calls of its own.

### `fusiondxhook.ixx`

Dead code. It contains a complete D3D9 vtable-hooking implementation and the
`FusionFix::D3D9::on*` event set in `common.ixx` that goes with it, but the
body begins with an unconditional `return;` and the file carries
`#pragma message ("FusionDxHook is disabled")`. All of those events are marked
`[[deprecated]]`. Nothing in the shipped build hooks D3D9 through it.

**This matters for the ENB question**: as shipped, FusionFix installs no hooks
on any `IDirect3DDevice9` method. There is no double-hooking of `Present`,
`EndScene` or `CreatePixelShader` to resolve between FusionFix and ENB, because
FusionFix does not hook them at all. The overlap is at the level of *what gets
drawn and where*, not of who owns a function pointer.

The tracer added in `source/enb_compat/enbtrace.ixx` does patch the device
vtable, but it is a diagnostic, off by default, and it alters no call.

## 4. Frame shape, as far as the source shows

```
  game frame
    |
    +-- sky draw ................... hbDrawSkyHook (runs it twice, RT1 = GBuffer diffuse)
    |
    +-- deferred lighting .......... OnBeforeLighting callback uploads c212..c216 / c228..c234
    |
    +-- ped/vehicle fake shadows ... RenderPedAndVehicleFakeShadows appends the AO pass
    |
    +-- fog draw ................... hbDrawCallFog -> NewFog(), takes the pre-alpha depth copy
    |
    +-- post-process draw .......... hbDrawCallPostFX + hbDrawPrimitivePostFX -> NewPostFX()
    |                                  sun shafts, original tonemap draw, FXAA/SMAA, blit
    |
    +-- EndScene ................... ConsoleGamma blit onto the real back buffer
    |
    +-- Present
```

Ordering inside the frame has not been confirmed against a capture. Use the
tracer (`D3D9Trace = 1`) before relying on it.

## 5. Open questions this document does not answer

* Where exactly in this sequence ENBSeries inserts itself.
* Whether ENB's replacement shaders and FusionFix's post-process chain fight
  over sampler stage 13, which both use (see
  [feature-conflicts.md](feature-conflicts.md)).
* Whether the game issues `Present` or `PresentEx`; the tracer currently only
  hooks `Present`.
