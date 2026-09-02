# Proxy chain

Both FusionFix and ENBSeries ship a file called `d3d9.dll` that goes next to
`GTAIV.exe`. Only one of them can have that name, so one has to load the other.

Status: **the mechanism is implemented, the permutations are untested.** Fill in
the results table as each is tried.

---

## What each side provides

**FusionFix's `d3d9.dll`** ([source/d3d9/d3d9.cpp](../source/d3d9/d3d9.cpp))
forwards all seventeen D3D9 exports to a backing library. It creates no device
and wraps no interface, so anything downstream of it sees the game's calls
unmodified. It picks its backing library in this order:

1. `[MAIN] ProxyLibrary` from `d3d9.cfg`, when `API = 0`;
2. `vulkan.dll` next to the exe, when `API = 1`;
3. `%WINDIR%\System32\d3d9.dll`.

`ProxyLibrary` was added for this project. A relative name resolves against the
exe folder, so an unrelated DLL further along the search path cannot satisfy it,
and a failure to load is a hard error rather than a silent fallback -- a silent
fallback here would look exactly like "ENB stopped working" with no clue why.

**ENBSeries** ships two builds. The wrapper build is a `d3d9.dll`. The injector
build is `enbseries.dll` plus `ENBInjector.exe`, which sidesteps the name clash
entirely. ENB also has its own chaining support:

```ini
[PROXY]
EnableProxyLibrary=true
InitProxyFunctions=true
ProxyLibrary=other_d3d9.dll
```

ENB's own documentation warns that some wrappers do not work when loaded
indirectly this way.

## Permutations to test

Run each with `[MAIN] API = 0`, native D3D9, no DXVK.

| # | Chain | Setup | Result |
|---|---|---|---|
| A | exe → FusionFix `d3d9.dll` → ENB → system | rename ENB's `d3d9.dll` to `enbseries_d3d9.dll`; `d3d9.cfg`: `ProxyLibrary = enbseries_d3d9.dll` | untested |
| B | exe → ENB `d3d9.dll` → FusionFix → system | ENB's `d3d9.dll` in place; rename FusionFix's to `fusionfix_d3d9.dll`; `enbseries.ini` `[PROXY] ProxyLibrary=fusionfix_d3d9.dll` | untested |
| C | exe → ENB injector, no FusionFix wrapper | use the ENB Injector build; FusionFix's `d3d9.dll` stays as-is | untested |
| D | exe → ENB `d3d9.dll` → system, FusionFix wrapper removed | delete FusionFix's `d3d9.dll`; the ASI loads via the ASI loader regardless | untested |

Permutation D is the simplest thing that can work and is the one to try first:
FusionFix's wrapper does nothing but forward, so removing it costs only the
`API = 1` DXVK option, which is incompatible with ENB anyway.

Permutation C is the next-simplest, because the injector build never competes
for the name.

DXVK combinations are deliberately out of scope until native D3D9 works.

## What to record for each

* Does the game reach the main menu?
* Does `ENBCompat.log` list both modules? (`D3D9Trace = 1` writes a
  `graphics modules:` line naming every graphics-related module in the process.)
* Does ENB's own log appear, and does the effect toggle key work?
* Which module ends up owning `Present`?

## Notes

* The ASI is loaded by Ultimate ASI Loader, not by `d3d9.dll`, so removing
  FusionFix's wrapper does not unload FusionFix. `CompatibilityWarnings()` in
  `compat.ixx` will complain if the ASI loader is missing or too old.
* FusionFix's wrapper also exports `FusionFixGraphicsApiSwitch`, an empty
  function used as a marker. Anything that looks for that export will not find
  it if a different `d3d9.dll` owns the name.
