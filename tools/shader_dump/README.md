# Stock CE shader tools

Current strategy: [stock CE baseline only](../../research/stock-ce-strategy.md).
No active tool stages FusionFix shaders or converts their depth/interfaces for ENB.

| Tool | Purpose |
|---|---|
| `build_stock_adapters.py` | Exact 1.0.4.0 preset deltas targeting only pinned stock CE programs |
| `prepare_stock_baseline.py` | Stage the 339 stock files, approved CE aliases and current ASI |
| `shader_edits.py` | Exact assembly edits, assembly and unchanged-instruction token checks |
| `enb163_hash.py` | Actual ENB 0.163 raw-byte routing identities |
| `d3d9bc.py` | Shader extraction, token handling and byte identities |
| `audit_shader_pair.py` | Named technique/pass and interface audit |
| `report_runtime_aliases.py` | Read-only creation/bind/dump reports using current exact stock identities |
| `inspect_effect.cpp` | Offline inspection of original compiled ENB effects |

Build the stock aliases:

```powershell
python tools/shader_dump/build_stock_adapters.py --legacy-exports build/legacy1040-exports/old --stock-exports build/legacy1040-exports/ce --stock-corpus 'C:/Games/Steam/steamapps/common/Grand Theft Auto IV/GTAIV/common/shaders/win32_30_nv8' --preset 'C:/temp/enb-revisit/icenhancer40/iCEnhancer/shaderinput' --assembler 'C:/temp/enb-revisit/shader-assembler-2/assemble_shader.exe' --out '<new alias directory>'
```

Stage the complete package after building the ASI:

```powershell
python tools/shader_dump/prepare_stock_baseline.py --stock 'C:/Games/Steam/steamapps/common/Grand Theft Auto IV/GTAIV/common/shaders' --adapters '<alias directory>' --out '<new package directory>'
```

Run Python checks with `python -m unittest discover -s tools/shader_dump -p 'test_*.py'`.
`test_stock_profile.cpp` tests the production shader policy, exact baseline
whitelist and file-route construction without a graphics device.

Generic inspection/comparison tools remain for research. The retired modern
adapters, heuristic alias staging, extended-tree builder, depth converter and
postfx bridge/capture workflows have been removed.
