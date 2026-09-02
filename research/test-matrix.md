# Test matrix and scenes

The configurations and scenes every experiment in this project is measured
against. Capturing the same scenes under each configuration is what makes two
results comparable; a screenshot with no matching baseline proves nothing.

---

## 1. Configurations

| ID | Configuration | Purpose | Available here |
|---|---|---|---|
| A | CE 1.2.0.59, nothing installed | baseline for everything | yes |
| B | CE + FusionFix | what users have today | yes |
| C | CE + target ENB, no FusionFix | does the ENB work on CE at all | yes |
| D | CE + FusionFix + ENB | the conflict to reproduce | yes |
| E | GTA IV 1.0.4.0 or 1.0.7.0 + ENB | the reference the preset was built for | optional |
| F | GTA IV 1.0.4.0 or 1.0.7.0, stock | reference baseline | optional |

**E and F are optional.** They were originally listed as the reference for what
the preset expects, but that turned out to be recoverable without them: ENB
documents the interface it wants in `enbeffect.fx`, and the shaders it targets
are present in Complete Edition essentially unchanged -- three of the twelve
match at similarity 1.000. [enb-contract.md](enb-contract.md) §4 breaks down,
question by question, what an old install would and would not add.

The one thing it would settle outright is ENB's hash function: hash a known
1.0.x shader, compare to the `shaderinput` filename. That is not on the critical
path, and if it becomes necessary the function lives in ENB's own `d3d9.dll`.

Old builds are no longer distributed by Rockstar, and the third-party mirrors
that carry them are not worth the risk. The only clean route would be Steam's
own CDN, via the `download_depot` console command against a licence already
owned -- and even that depends on the old manifests still being served.

Everything below proceeds on A-D alone.

## 2. Preconditions

* `GTAIV/d3d9.cfg` must be `[MAIN] API = 0`. ENBSeries is a D3D9 wrapper and
  does nothing under the DXVK path.
* Same resolution, same in-game graphics settings, same display mode across all
  configurations.
* Same save, same weather, same time of day. Use the debug time/weather controls
  or a scripted setter rather than waiting.

## 3. Configuration recipes

**A** -- stock install. Remove `plugins/GTAIV.EFLC.FusionFix.asi`,
`update/common/shaders`, `update/GTAIV.EFLC.FusionFix`, and FusionFix's
`d3d9.dll`.

**B** -- a normal FusionFix install, `[ENBCompatibility] Mode = 0`.

**C** -- stock install plus the ENB preset. For the wrapper build, drop ENB's
`d3d9.dll` next to the exe. For the injector build, run `ENBInjector.exe`.

**D** -- B plus C. Decide the DLL chain first; see
[proxy-chain-results.md](proxy-chain-results.md).

**D′ (ENB mode)** -- D with `[ENBCompatibility] Mode = 1` and the stock shader
package staged by `tools/shader_dump/make_vanilla_package.py`.

## 4. Scenes

Twelve scenes, chosen to cover each part of the pipeline separately so a failure
can be attributed rather than merely observed.

| # | Scene | What it exercises |
|---|---|---|
| 1 | Bright daytime exterior | tone mapping, exposure, sky |
| 2 | Sunset | sun shafts, atmospheric scattering, bloom |
| 3 | Midnight city street | night lighting, emissive shaders, the black-night bug |
| 4 | Rain | rain drop refraction, wetness, the quarter-res HDR copy |
| 5 | Interior | interior lighting path, no sky |
| 6 | Vehicle paint and reflections | cubemap reflect shaders, car dirt |
| 7 | Water | water shaders, reflection render target, shoreline blending |
| 8 | Shadow-heavy scene | cascaded shadow maps, the shadow filter |
| 9 | Vegetation | tree shaders, wind sway vertex constants, tree alpha |
| 10 | Artificial light sources | deferred lights, light volumes, coronas |
| 11 | Cutscene | cutscene camera, depth of field |
| 12 | Pause / menu transition | menu blur, device state save and restore |

Scene 3 is the one issue #180 reports going black, and scene 9 is where the
FusionFix-only `gta_trees_extended` shader lives, so those two carry the most
information per capture.

## 5. What to record per scene

* screenshot, same filename scheme in every configuration
* frame rate
* crash or no crash
* with ENB: the effect toggled on and off, both captured
* `ENBCompat/d3d9_trace.log` for at least one frame (`D3D9Trace = 1`,
  `TraceStartFrame` set past the loading screens)
* `ENBCompat/shaders.csv`
* whether the FusionFix replacement shaders were the ones loaded
  (`ENBCompat.log` reports the installed package)

## 6. Naming

```
captures/<config>/<scene-number>-<scene-name>/<what>.<ext>
    e.g. captures/D-ce-ff-enb/03-midnight-street/screenshot.png
                                                /d3d9_trace.log
                                                /shaders.csv
```

Keeping the configuration first makes a whole-configuration diff a directory
diff.
