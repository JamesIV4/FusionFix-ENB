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

A container is the finest granularity available — the update tree overlays per
file, and shaders inside a `.fxc` cannot be swapped individually without
rebuilding it, which loses the CTAB and changes the bytecode anyway.

## Why the hashes matter

ENBSeries names each replacement after a 32-bit hash of the original shader's
bytecode. The hash function itself has not been identified — see
[../../research/research-log.md](../../research/research-log.md) for the search
that came up empty — but every conclusion here rests only on *whether bytecode
changed*, not on reproducing ENB's specific hash.
