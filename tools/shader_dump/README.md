# shader_dump

Offline analysis of GTA IV shader packages. Nothing here needs the game running.

| Script | Does |
|---|---|
| `d3d9bc.py` | shared library: D3D9 bytecode token walker, blob extraction from `.fxc`, comment stripping, hashing, assembly normalisation |
| `dump_fxc.py` | extracts and fingerprints every shader in a set of `.fxc` containers; `--asm` also writes `.cso` blobs and disassembly |
| `compare_sets.py` | compares two dumped sets and reports how many shaders keep their bytecode |
| `match_enb.py` | identifies which game shader each ENB `shaderinput` file replaces, by disassembly similarity |
| `check_interface.py` | checks a shader set against a declared interface contract, by name and by actual register use |
| `make_vanilla_package.py` | builds an `update/common/shaders` package with stock bytecode plus FusionFix's genuine additions |
| `assemble_shader.cpp` | assembles one shaderinput file through D3DX with the zero flags used by ENB 0.163; no D3D device |
| `report_runtime_aliases.py` | joins expected shaderinput bytecode to tracer creation dumps and automatic first binds |
| `make_legacy_tree_shader.py` | rebuilds required gta_trees_extended without FusionShaders' explicit log-depth writes for a stock-depth ENB package |

`--asm` and `match_enb.py` need `fxc.exe`; `source/dxsdk/lib/x86/fxc.exe` in this
repository is used by default.

## Quantifying what FusionFix changes

```
set G=C:\Games\Steam\steamapps\common\Grand Theft Auto IV\GTAIV
python dump_fxc.py "%G%\common\shaders\win32_30"        --out out --label ce-stock
python dump_fxc.py "%G%\update\common\shaders\win32_30" --out out --label ce-fusionfix
python compare_sets.py out/ce-stock.json out/ce-fusionfix.json
```

## Identifying an ENB preset's targets

```
python dump_fxc.py "%G%\common\shaders\win32_30" --out out --label ce-stock --asm
python match_enb.py <preset>/shaderinput out/ce-stock.json --top 3 --json out/enb-match.json
```

Two numbers come back per candidate. `sim` is symmetric — matched instruction
lines over the combined length — and is what the ranking uses, because it
penalises a length mismatch in either direction. `cov` is the fraction of the
game shader's body found inside the ENB file, which reads high for any short
shader swallowed by a long ENB one. Trust `sim`.

A low score is not evidence of absence. The comparison is textual, and a shader
recompiled with different register allocation scores poorly while being the same
shader.

**Add `--match-decls`.** It restricts candidates to shaders whose declaration
signature is compatible — identical input declarations, samplers a subset of the
ENB file's. ENB only ever adds a sampler for its own textures and never changes
what a shader receives from the vertex stage, so the filter is sound, and within
a family of shaders that all do nearly the same thing it is far more decisive
than similarity. The printed `lines/pool` column shows how many candidates
survived: a pool of 1 with a high `sim` is an identification, a large pool with
a low `sim` is a lead, and a pool of 0 means nothing in the set has a compatible
signature.

Beware ties. Stock CE holds 1689 shader blobs but only 638 distinct bytecodes,
so the same shader appears in several containers and a three-way tie at an
identical score is usually correct rather than confused — ENB's hash names a
bytecode, not a container.

## Checking a shader set against an interface contract

```
python dump_fxc.py "%G%\common\shaders\win32_30\rage_postfx.fxc"        --out out --label ce-postfx --asm
python dump_fxc.py "%G%\update\common\shaders\win32_30\rage_postfx.fxc" --out out --label ff-postfx --asm
python check_interface.py --contract ../../research/contracts/enb-postfx.json ^
       "CE stock=out/ce-postfx" "FusionFix=out/ff-postfx"
```

Two checks run per shader. *By name* reads the CTAB reflection table and
compares each parameter's register to the contract, catching a moved parameter.
*By use* reads the instruction stream and lists the registers actually read,
which still works on a shader that carries no reflection data — and reports the
absence, since a consumer that looks parameters up by name has nothing to work
with.

## Building an ENB-compatible shader package

```
python make_vanilla_package.py --game "%G%" --keep-stock list   # what each container costs
python make_vanilla_package.py --game "%G%" --selective         # keep FusionFix except those
python make_vanilla_package.py --game "%G%" --stage-extras      # all stock, one file
python make_vanilla_package.py --game "%G%" --out build\pkg --install   # rebuild in place
```

`--selective` is the interesting one: it stages FusionFix's containers into the
stock-shader folder *except* the ones holding a shader an ENB preset replaces,
which then fall through to `common/shaders`. Against CE 1.2.0.59 that gives up
9 containers holding 191 of 1739 FusionFix shaders, so 89% is retained. Keep
`ShaderConstantInjection = 1` alongside it.

`splice_fxc.py` can preserve bytecode and CTAB by replacing length-prefixed
blobs. A successful splice still needs compatible RAGE bindings, pass state and
paired vertex/depth semantics. Retaining 89% of shader blobs does not establish
retaining 89% of working graphics features.

## ENB 0.163 hashes and filename aliases

The hash is now recovered: reflected CRC32 without final XOR over raw shader
bytes preceding the first aligned END word, including version and comments.
`d3d9bc.py` reports `enb163`; the older tracer CRC columns remain different hashes.

```bat
python tools\shader_dump\decode_enb163.py "<ENB-0.163-wrapper>\d3d9.dll" --out "<new-scratch-directory>"
python tools\shader_dump\map_enb163.py "<game>\common\shaders" --preset "<iCEnhancer>\shaderinput" --out stock-enb-identities.json
python tools\shader_dump\make_shader_aliases.py --shaders "<game>\common\shaders\win32_30" --preset "<iCEnhancer>\shaderinput" --out "<new-alias-directory>"
```

The decoder accepts only the exact researched wrapper SHA256. It executes no
input and produces a non-runnable inspection blob, not a patched DLL. See the
research report for code RVAs. The mapping tool scans actual bytecode; unlike
assembly similarity, its matches use ENB's recovered identity algorithm.

`prepare_alias_test.py --game <game> --enb <wrapper> --ice <preset> --out <new-kit>`
stages a complete user-run test kit with per-file snapshot/restore support.
It reads the installation but never installs or launches anything. See
[the user instructions](../../research/alias-test.md).

The alias builder defaults to three terrain candidates. `--probe` stages a
separate magenta diffuse diagnostic for those three. `--group terrain --group
candidate` additionally selects five weaker mappings. Input shader and preset
SHA256 guards reject changed/modern inputs. It checks every matching slot for
hash collisions, refuses existing outputs and game directories, and never
installs anything. Regular aliases preserve the preset bytes; probes explicitly
modify only the diagnostic output. Neither has been validated in-game.

`inspect_crash.py <existing.dmp> --exe <GTAIV.exe> --out <new.json>` compares the
existing x86 fault context and sixteen captured instruction bytes against disk.
It does not attach to or start a process. Output omits general memory dumps and
private module paths. A byte difference does not identify its writer.

`assemble_shader.cpp` reproduces ENB 0.163's `D3DXAssembleShader` call with
flags zero and does not create a D3D device. Build it from an x86 VS developer
prompt:

```bat
cl /nologo /EHsc /std:c++17 /W4 /I source\dxsdk tools\shader_dump\assemble_shader.cpp /Fe:assemble_shader.exe /link /LIBPATH:source\dxsdk\lib\x86 d3dx9.lib
copy source\dxsdk\lib\x86\D3DX9_43.dll .
assemble_shader.exe <shaderinput.txt> <new-output.cso>
```

The alias contract records the SHA256 and runtime CRC of each assembled result.
With the new diagnostic ASI, `shader_first_binds.csv` contains one row per exact
shader identity when it is first used. `report_runtime_aliases.py <ENBCompat>
--out <new.json>` joins creation, exact dump and first-bind evidence. The
recommended user workflow is `TraceAliases` then `CollectTrace` in
[the focused test](../../research/alias-test.md).

# September 2026 bridge investigation tools

`inspect_effect.cpp` loads a text or compiled D3D9 **effect** through Microsoft
D3DX, enumerates its parameters/techniques/passes, validates and binds its
passes, and dumps each embedded shader. It preserves visibility into preshaders
that a GPU-bytecode-only extraction can miss. It does not draw a frame or prove
game compatibility. `--hal` requires a hardware D3D9 device; the default tries
NULLREF first and falls back to HAL. Use an isolated output/build directory,
not the game folder: runtime.tsv records the actual DLL paths and device type.

From an **x86 Visual Studio developer command prompt**, at the repository root:

```bat
mkdir build\effect-inspector
cl /nologo /EHsc /std:c++17 /W4 /I source\dxsdk tools\shader_dump\inspect_effect.cpp /Fo:build\effect-inspector\inspect_effect.obj /Fe:build\effect-inspector\inspect_effect.exe /link /LIBPATH:source\dxsdk\lib\x86 d3dx9.lib d3d9.lib user32.lib
copy source\dxsdk\lib\x86\D3DX9_43.dll build\effect-inspector\
build\effect-inspector\inspect_effect.exe "<preset>\enbeffect.fx" "<new-output-directory>" --hal
```

The output directory must not already exist. `effect.asm` includes all shader
listings, `interface.tsv` the effect names/types, `validation.tsv` successful
technique/pass binding results, and per-pass `.cso` / `.asm` files the shader
programs. A failed API call returns a nonzero exit code; partial outputs from a
failed run must not be treated as a successful validation.

`audit_shader_pair.py` uses RageShaderEditor XML/assembly exports to map slots by
named technique/pass and stage, then reports named binding changes, explicit
depth writes, declarations and pass state. This is an interface audit, not a
transplant tool. First copy each input `.fxc` into separate scratch directories
and run `tools\RageShaderEditor\RageShaderEditor.exe <copied-file.fxc>` to export
without modifying the game installation. Historical source `.fxc.xml` files
with their adjacent assembly directories can be read directly.

```bat
python tools\shader_dump\audit_shader_pair.py stock\rage_postfx.fxc.xml modern\rage_postfx.fxc.xml --slots 13 --out postfx-map.json
python -m unittest discover -s tools/shader_dump -p test_audit_shader_pair.py -v
```

`map_hook_patterns.py` scans executable PE sections on disk, reporting candidate
RVAs rather than patching the process. It rejects non-32-bit-PE inputs and
records the executable SHA-256. A match needs runtime validation; an on-disk
miss may differ from the loaded process. It accepts an old executable as well
as CE when a reference becomes available.

```bat
python tools\shader_dump\map_hook_patterns.py "<game>\GTAIV.exe" research\contracts\legacy-hooks.json --out hook-candidates.json
```

Checked results and source revisions:
[legacy-shader-bridge.md](../../research/legacy-shader-bridge.md).
