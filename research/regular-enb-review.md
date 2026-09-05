# Regular ENB baseline review — 2026-09-05

**Verdict: ENB loads and its postfx hook executes, but the baseline is not a
validated, correctly rendering ENB setup.** The screenshots show more than an
exposure preference: rectangular foliage cards, conspicuous ground triangles,
washed-out shaded surfaces and clipped-looking pavement. Lowering brightness
cannot restore missing foliage transparency. The ground faceting also needs a
matched reference before deciding how much is original mesh/vertex lighting
and how much is a compatibility defect.

Reviewed commit `c18e6cf9194437c7fb8639ac87b16a0f28a25b31`, its native changes
against its parent, current source, installed configuration, original ENB
archive inputs, historical captures/notes and the user's September 4 screenshots.
This review starts no game, changes no installed files and does not run the
pending TraceAliases/Effect tests. The later test kit inherited the baseline's
structural problems; they are not confined to the earlier commit.

Compact file/bytecode/PE evidence:
[regular-enb-review.json](evidence/2026-09-05/regular-enb-review.json).

## 1. High priority: the retained tree shader loses its runtime inputs

The old setup calls `--stage-extras` an all-stock package, but copies modern
`gta_trees_extended.fxc` into the stock variant. `ENBLegacy` simultaneously sets
`ShaderConstantInjection = 0`.

That shader is not standalone. Its pixel program PS1 uses **c221.w for texture
alpha**, then thresholds and discards pixels. Five of its six pixel programs
write depth using **c209.x/y**. Two vertex programs use **c233.x for wind**.
The gated hooks in `source/shaders.ixx` supply exactly these values:

* lines 367–404: c209 depth parameters, skipped when constant injection is off;
* lines 411–419: early return prevents the BeginScene constant provider;
* lines 438–447: c233 wind provider inside that skipped hook;
* lines 540–573: c221 tree alpha provider inside that skipped hook.

This is confirmed in the **installed binary**, not just source comments:
13,796-byte container, SHA256
`ee6a564b8d06b9d27cf0beaf6df30d196ef9ca40c3d77fe31aa55be779abc6e2`.
Its extracted slots 0/3 read vertex c233; slot 5 reads pixel c209/c221; slots
6/7/8/10 read pixel c209 and write depth. These are external reads, excluding
locally defined constants. The startup log says the constant provider is off.

There is also a depth contract mismatch: modern extended-tree pixels write
logarithmic camera depth, while the stock deferred/postfx readers reconstruct
the stock depth representation. Globally re-enabling constant injection could
supply tree alpha/wind values but would not reconcile the two depth encodings.

**Implication:** there is a concrete unsupported shader/provider combination.
It is a strong lead for foliage/depth defects; the exact tree draw in the image
was not captured, so attributing each visible rectangle to this shader is still
an inference. Zero/stale/other-written register contents must not be assumed to
produce one particular symptom.

**Required direction:** provide an extended-tree variant compatible with the
stock depth pipeline and its required parameters, or restore matching original
tree assets and their original shaders as a unit. Merely removing the container
previously caused missing-resource failures because retained content needs it.
The three-container package detector also omits this known modern exception,
so its `stock` log is not a complete audit of loaded shaders.

Sources: `tools/shader_dump/make_vanilla_package.py:35`,
`tools/shader_dump/prepare_alias_test.py:62`,
`source/enb_compat/enbcompat.ixx:228`,
`shaders/GTAIV.EFLC.FusionShaders/win32_30_nv8/gta_trees_extended/`.

## 2. High priority: ENBLegacy omits shadow/G-buffer resource changes

`source/shadows.ixx:215–327` remains unconditional with respect to the ENB
profile. It changes shadow texture formats, a G-buffer format selection,
cascade sizing/ranges and shadow-matrix parameters. The module does not consult
ENBCompat. Disabling the nine logged compatibility flags does not disable it.

On-disk pattern inspection of the installed CE executable confirms:

| Patch | Matched instruction RVA | Original enum / format | FusionFix writes |
|---|---|---|---|
| Shadow atlas format | 0x0071D260 | 3 / R16F | 4 / R32F |
| G-buffer format selection | 0x006D15C2 | 5 / A2R10G10B10 | 2 / A8R8G8B8 |

The enum mapping is in `source/comvars.ixx:1065–1101`. The second row is one
conditional format-selection path; it does not prove every render target has
that format at runtime. The original immediates are read from the executable,
and the replacement values from the source. No process was inspected or patched
to obtain these results.

**Implication:** stock shader names/bytecode do not restore stock resource and
shadow semantics. The G-buffer change alters channel precision/allocation;
the remaining shadow changes alter inputs used by stock lighting shaders. These
must be audited with their consumers before the setup is called a baseline.
The presence of these changes is confirmed; their contribution to the exact
brightness/faceting in the screenshots needs a controlled comparison.

**Required direction:** make these resource/matrix changes explicit in the
compatibility profile, then choose coherent stock or modern producers/readers.
Do not label them disabled simply because all existing flags are zero.

## 3. High priority: the old evidence conflates postfx and material substitution

The September 2 method changed both three material shaderinput files and the
fullscreen postfx effect. Its reported observation establishes that the postfx
tint appeared when DOF enabled a recognized pass. It does not independently
establish that any of the four ordinary material replacements was loaded.

The recovered ENB hash scan finds **none of the four original ENB 0.163
shaderinput filenames in stock CE** (they are a subset of the twelve scanned
iCEnhancer names). Therefore the claim that switching to stock containers is
enough for all regular ENB replacements to fire is unsupported. Runtime shader
bytes could differ from the container; no old capture resolved that distinction.

What remains supported is useful and narrower: ENB runs, a postfx pass is
recognized under AA1C0C36, and DOF affects whether that pass is selected.
September 4's recovered terrain aliases subsequently produced a localized
magenta strip. That confirms at least one renamed terrain replacement, not the
four original ENB filenames or all ENB lighting effects.

Sources: `research/research-log.md:101–136`,
`research/evidence/2026-09-04/enb163-identity.json`,
`research/evidence/2026-09-04/user-terrain-probe.json`.

## 4. Brightness: strong curve, unmeasured inputs, premature conclusion

The September 2 notes say the remaining brightness is a tuning issue once DOF
is on. That was not established by the tint test. Binding the right shader
does not verify its luminance texture, HDR input range, exposure or color space.

The installed enbeffect.fx exactly matches the original ENB 0.163 archive file
(SHA256 `5676d6393cb82983f0a23a85c20919549a6a95093188fb36e289ce35acce4d63`).
No ad hoc brightness edit was found there. The default active V2 path:

1. takes the post-blur scene color;
2. divides by `tex2D(s4, 0).x`, its adaptation luminance, without an epsilon;
3. multiplies by EBrightnessV2 = 0.076;
4. applies EColoringV2 = 0.45 and a gray-value exponent EDarkeningV2 = 0.34.

The power operation alone maps 0.01 to approximately 0.209 and 0.1 to 0.457.
Those are examples of the curve, not measured input values from these frames.
It strongly lifts low values, so the shipped curve is a credible contributor to
the washed-out appearance. An incorrectly scaled/near-zero luminance sample can
also amplify the image. The screenshots do not distinguish these causes.

`APPLYGAMECOLORCORRECTION` is commented out. The active V2 output overwrites
the earlier original-game color result, so game contrast/gamma controls cannot
be assumed to correct the final image in this mode. The separate console-gamma
blit is gated off, making that particular double-blit an unlikely explanation
under this configuration; other resource/color-space problems remain open.

**Required direction:** after repairing the structural baseline, compare ENB
on/off at the same save/time/weather and inspect the HDR and adaptation inputs
at the recognized postfx draw. Then decide whether to correct the interface or
tune the curve. Alias first-bind logs alone cannot establish texture contents.

## 5. Other active state and limits of the old controls

* The original register-use audit has a concrete blind spot:
  `tools/shader_dump/check_interface.py:33` uses `\bc(\d+)\b`, which misses
  operands such as `c221_abs.w` and `c209_abs.z` because underscore is a word
  character. The parser reports `c221.w` but not `c221_abs.w`; both forms occur
  in the shader corpus. The binary operand inspection in this review avoids
  that omission. Earlier broad conclusions based on the reported register-use
  sets need this caveat; the bug alone does not prove a register collision.
* The reviewed baseline changes the reflection multiplier from 0.6 to 1.0.
  `FusionShaderTweaks` now restores the original multiplier with stock shaders.
  The separate console reflection/dirt option remains available and must be
  controlled in a vehicle comparison.
* The reviewed baseline installs the console contrast adjustment. ConsoleGamma
  is 1 in the persisted settings, but ConsoleGammaBlit is 0. Its effect on the
  final V2 path is limited as explained above; the menu value is not proof the
  original console-gamma path is actually active. `FusionShaderTweaks` now
  disables this offset with stock shaders.
* The adaptive-tessellation render-state suppression and rain texture rebinding
  at `source/shaders.ixx:666–713` are also ungated. Their relevance to these
  screenshots is not established. They belong in the audit rather than being
  described as renderer-neutral.
  The repair now gates the adaptive-state suppression through
  `FusionShaderTweaks`, leaving the native-D3D9 game calls intact. The nearby
  rain texture rebinding remains active and unproven for dry scenes.
* The installed update timecycle/visualsettings and settings-driven timecycle
  callbacks remain. The update timecycle is labeled X360. Stock shader selection
  does not undo lighting/content overrides; their presence does not alone prove
  that they cause over-brightening.
* The old `ENBCompat-Mode.cmd C` disables the ASI and two variant folders, but
  does not inventory all update content/other variants. It cannot establish a
  clean original CE + ENB reference on its own.

## Revised priority

The first repair is now implemented and built:

* `ShadowPipelineFixes` disables the shadow/G-buffer format, cascade and matrix
  patches in ENBLegacy; it also leaves the extra model-shadow changes inactive.
* `FusionShaderTweaks` disables the reflection multiplier, console-gamma
  contrast offset and DXVK adaptive-state suppression with stock/native D3D9.
* ENBLegacy retains `ShaderConstantInjection` because extended-tree alpha/wind
  consume c221/c233.
* `make_legacy_tree_shader.py` rebuilds the required extended-tree container
  after removing five marked log-depth blocks and unused pixel v9 declarations.
  The 13,276-byte output has eleven shaders, no c209 reads and no explicit depth
  outputs; its SHA256 is
  `8e6ef1dfd44a87603b3160b20b5e565be73272cbd9bcf6ebbb7b80663de5142a`.
* `check_interface.py` now recognizes `_abs` source modifiers.

The native Release build and 25 offline tests pass. A synthetic FixedBaseline
setup/restore verified the intended ASI, tree and ini hashes and restored its
original test files. Rendering remains unverified until the user runs the
prepared FixedBaseline against the same scene.

Keep the alias/effect capture paused for that comparison. If foliage, faceting
or exposure remain, next isolate the postfx curve and actual luminance/HDR
inputs. Resume broader shader mapping after the baseline supports a meaningful
visual comparison.

The earlier hook-gating work, DOF discovery, extractor and reversible staging
remain useful. The review changes the acceptance criterion: **loading and
showing a probe are milestones, not proof of correct rendering.**
