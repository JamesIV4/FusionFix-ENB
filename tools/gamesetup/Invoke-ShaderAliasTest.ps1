<#
.SYNOPSIS
User-run, reversible file setup for the September 2026 shader alias experiment.
.DESCRIPTION
Does not start the game. Uses a prepared kit with baseline/probe/aliases/effect
overlays. Snapshots every potentially touched file before setup, including its
original absence. Each phase starts from the same baseline. Restore preserves
unrelated files and existing shader variant directories. Keep the kit until
restoration completes. See research/alias-test.md.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Baseline', 'FixedBaseline', 'Probe', 'Aliases', 'Effect', 'TraceAliases', 'CollectTrace', 'Restore')][string]$Action,
    [Parameter(Mandatory)][string]$Kit,
    [string]$Game = 'C:\Games\Steam\steamapps\common\Grand Theft Auto IV\GTAIV'
)
$ErrorActionPreference = 'Stop'
$gameRoot = (Resolve-Path -LiteralPath $Game).Path.TrimEnd('\')
$kitRoot = (Resolve-Path -LiteralPath $Kit).Path.TrimEnd('\')
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath (Join-Path $gameRoot 'GTAIV.exe'))) { throw 'GTAIV.exe is missing.' }
if ($kitRoot.StartsWith($gameRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Keep the kit outside the game.' }
if (Get-Process GTAIV -ErrorAction SilentlyContinue) { throw 'Close GTAIV before switching files.' }
$snapshot = Join-Path $kitRoot 'snapshot'
$manifestPath = Join-Path $snapshot 'manifest.json'

function Game-Path([string]$relative) {
    $path = [IO.Path]::GetFullPath((Join-Path $gameRoot $relative))
    if (-not $path.StartsWith($gameRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Path escapes game: $relative" }
    return $path
}
function Snapshot-Path([string]$relative) {
    $root = Join-Path $snapshot 'files'
    $path = [IO.Path]::GetFullPath((Join-Path $root $relative))
    if (-not $path.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid backup path.' }
    return $path
}

if (-not (Test-Path -LiteralPath $manifestPath)) {
    if ($Action -ne 'Baseline') { throw 'Run Baseline first; there is no snapshot.' }
    if (Test-Path -LiteralPath $snapshot) { throw 'An incomplete snapshot exists; preserve and inspect it before retrying.' }
    if (Test-Path -LiteralPath (Join-Path $gameRoot 'update\common\shaders\win32_30_nv8')) {
        throw 'The chosen stock overlay already exists. This kit requires the restored baseline, not another active experiment.'
    }
    foreach ($plugin in 'icenhancer.asi', 'icenhancer.enbcompat', 'plugins\icenhancer.asi') {
        if (Test-Path -LiteralPath (Join-Path $gameRoot $plugin)) { throw "Remove the active iCEnhancer plugin from this test setup first: $plugin" }
    }
    $expected = Get-Content -LiteralPath (Join-Path $kitRoot 'expected-originals.json') -Raw | ConvertFrom-Json
    foreach ($item in $expected) {
        $path = Game-Path $item.path
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $item.sha256) {
            throw "Original file changed since kit preparation; regenerate the kit: $($item.path)"
        }
    }
    $relativeFiles = @()
    foreach ($phase in 'baseline', 'probe', 'aliases', 'effect') {
        $root = Join-Path $kitRoot $phase
        foreach ($file in Get-ChildItem -LiteralPath $root -File -Recurse) {
            $relativeFiles += $file.FullName.Substring($root.Length + 1)
        }
    }
    $entries = @()
    $createdDirectories = @()
    New-Item -ItemType Directory -Path $snapshot | Out-Null
    foreach ($relative in ($relativeFiles | Sort-Object -Unique)) {
        $target = Game-Path $relative
        $existed = Test-Path -LiteralPath $target
        $hash = $null
        if ($existed) {
            if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw "Expected file: $target" }
            $saved = Snapshot-Path $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $saved) | Out-Null
            Copy-Item -LiteralPath $target -Destination $saved
            $hash = (Get-FileHash -LiteralPath $saved -Algorithm SHA256).Hash
        }
        $parent = Split-Path -Parent $target
        while ($parent -ne $gameRoot -and -not (Test-Path -LiteralPath $parent)) {
            $createdDirectories += $parent.Substring($gameRoot.Length + 1)
            $parent = Split-Path -Parent $parent
        }
        $entries += [pscustomobject]@{ path = $relative; existed = $existed; sha256 = $hash }
    }
    $manifest = [pscustomobject]@{ game = $gameRoot; entries = $entries; directories = @($createdDirectories | Sort-Object -Unique) }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.game -ne $gameRoot) { throw 'Snapshot belongs to another game directory.' }

if ($Action -eq 'CollectTrace') {
    $diagnostics = Game-Path 'ENBCompat'
    foreach ($required in 'shaders.csv', 'shader_first_binds.csv', 'trace-session.json') {
        if (-not (Test-Path -LiteralPath (Join-Path $diagnostics $required) -PathType Leaf)) {
            throw "Trace is incomplete; missing $required. Run TraceAliases with the new build, launch a scene, and exit normally."
        }
    }
    $runRoot = Join-Path $kitRoot 'trace-runs'
    New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
    $run = Join-Path $runRoot (Get-Date -Format 'yyyyMMdd-HHmmss')
    if (Test-Path -LiteralPath $run) { throw "Trace destination already exists: $run" }
    New-Item -ItemType Directory -Path $run | Out-Null
    Copy-Item -LiteralPath $diagnostics -Destination (Join-Path $run 'ENBCompat') -Recurse
    $reporter = Join-Path $repoRoot 'tools\shader_dump\report_runtime_aliases.py'
    & python $reporter (Join-Path $run 'ENBCompat') --out (Join-Path $run 'runtime-aliases.json')
    if ($LASTEXITCODE -ne 0) { throw "Runtime alias report failed ($LASTEXITCODE). Trace was retained at $run" }
    Write-Host "Trace copied and audited: $run"
    exit
}

$phases = @('baseline')
if ($Action -eq 'TraceAliases') {
    $phases += 'aliases'
} elseif ($Action -notin @('Baseline', 'FixedBaseline', 'Restore')) {
    $phases += $Action.ToLowerInvariant()
}
$expectedInstalled = @{}
if ($Action -ne 'Restore') {
    foreach ($phase in $phases) {
        $root = Join-Path $kitRoot $phase
        $phaseFiles = @(Get-ChildItem -LiteralPath $root -File -Recurse)
        if ($phaseFiles.Count -eq 0) { throw "Kit phase is empty: $phase" }
        foreach ($file in $phaseFiles) {
            $relative = $file.FullName.Substring($root.Length + 1)
            $null = Game-Path $relative
            if ($relative -notin $manifest.entries.path) { throw "Kit changed after snapshot: $relative" }
            # Later phases deliberately override baseline files such as enbeffect.fx.
            $expectedInstalled[$relative] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        }
        if ($phase -eq 'probe') {
            foreach ($name in 'pshA5F4E880.txt', 'pshFDFF185D.txt', 'psh1D661524.txt') {
                if (-not (Test-Path -LiteralPath (Join-Path $root "shaderinput\$name") -PathType Leaf)) {
                    throw "Terrain probe file missing from kit: $name"
                }
            }
        }
    }
}
# Validate all backup files and target paths before any restoration/mutation.
foreach ($entry in $manifest.entries) {
    $null = Game-Path $entry.path
    if ($entry.existed) {
        if ((Get-FileHash -LiteralPath (Snapshot-Path $entry.path) -Algorithm SHA256).Hash -ne $entry.sha256) {
            throw "Backup hash mismatch: $($entry.path)"
        }
    }
}
foreach ($entry in $manifest.entries) {
    $target = Game-Path $entry.path
    if ($entry.existed) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath (Snapshot-Path $entry.path) -Destination $target -Force
    } elseif (Test-Path -LiteralPath $target -PathType Leaf) {
        Remove-Item -LiteralPath $target
    }
}
if ($Action -eq 'Restore') {
    foreach ($relative in ($manifest.directories | Sort-Object { $_.Length } -Descending)) {
        $path = Game-Path $relative
        if ((Test-Path -LiteralPath $path -PathType Container) -and
            @(Get-ChildItem -LiteralPath $path -Force).Count -eq 0) {
            Remove-Item -LiteralPath $path
        }
    }
    Write-Host 'Original touched files restored; unrelated files and diagnostic logs retained. Keep the snapshot.'
    exit
}
foreach ($phase in $phases) {
    $root = Join-Path $kitRoot $phase
    foreach ($file in Get-ChildItem -LiteralPath $root -File -Recurse) {
        $relative = $file.FullName.Substring($root.Length + 1)
        if ($relative -notin $manifest.entries.path) { throw "Kit changed after snapshot: $relative" }
        $target = Game-Path $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target -Force
    }
}
foreach ($relative in $expectedInstalled.Keys) {
    $target = Game-Path $relative
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
        throw "Phase installation incomplete; do not launch GTAIV. Missing: $relative"
    }
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $expectedInstalled[$relative]) {
        throw "Phase installation verification failed; do not launch GTAIV. Changed: $relative"
    }
}
if ($Action -eq 'Probe') {
    Write-Host 'Verified all three magenta probe files in the game shaderinput folder:'
    Write-Host '  pshA5F4E880.txt, pshFDFF185D.txt, psh1D661524.txt'
}

if ($Action -in @('FixedBaseline', 'TraceAliases')) {
    $newAsi = Join-Path $repoRoot 'bin\GTAIV.EFLC.FusionFix.asi'
    if (-not (Test-Path -LiteralPath $newAsi -PathType Leaf)) { throw "Build is missing: $newAsi" }
    $targetAsi = Game-Path 'plugins\GTAIV.EFLC.FusionFix.asi'
    Copy-Item -LiteralPath $newAsi -Destination $targetAsi -Force
    if ((Get-FileHash -LiteralPath $newAsi -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $targetAsi -Algorithm SHA256).Hash) {
        throw 'Trace ASI installation verification failed.'
    }

    $fixedTree = Join-Path $kitRoot 'fixed\gta_trees_extended.fxc'
    $fixedManifest = Join-Path $kitRoot 'fixed\manifest.json'
    if (-not (Test-Path -LiteralPath $fixedTree -PathType Leaf) -or
        -not (Test-Path -LiteralPath $fixedManifest -PathType Leaf)) {
        throw 'Fixed tree package is missing. Rebuild the test kit with prepare_alias_test.py.'
    }
    $treeInfo = Get-Content -LiteralPath $fixedManifest -Raw | ConvertFrom-Json
    if ((Get-FileHash -LiteralPath $fixedTree -Algorithm SHA256).Hash -ne $treeInfo.compiled_sha256) {
        throw 'Fixed tree package hash does not match its manifest.'
    }
    $targetTree = Game-Path 'update\common\shaders\win32_30_nv8\gta_trees_extended.fxc'
    Copy-Item -LiteralPath $fixedTree -Destination $targetTree -Force

    $ini = Game-Path 'plugins\GTAIV.EFLC.FusionFix.ini'
    $text = Get-Content -LiteralPath $ini -Raw
    foreach ($pair in @(@('ShadowPipelineFixes', '0'), @('FusionShaderTweaks', '0'), @('ShaderConstantInjection', '1'),
                         @('D3D9Trace', '0'), @('DumpShaders', '0'))) {
        $key, $value = $pair
        $pattern = '(?m)^' + [regex]::Escape($key) + '\s*=.*$'
        $matches = [regex]::Matches($text, $pattern).Count
        if ($matches -gt 1) { throw "Expected at most one $key setting in FusionFix ini." }
        if ($matches -eq 1) {
            $text = [regex]::Replace($text, $pattern, "$key = $value")
        } else {
            $text += "`n$key = $value`n"
        }
    }
    [IO.File]::WriteAllText($ini, $text, [Text.UTF8Encoding]::new($false))
    if ((Get-FileHash -LiteralPath $targetTree -Algorithm SHA256).Hash -ne $treeInfo.compiled_sha256) {
        throw 'Fixed tree installation verification failed.'
    }
    if ($Action -eq 'FixedBaseline') {
        Write-Host 'FixedBaseline ready: stock shadow/G-buffer and D3D9 state path, stock-depth extended tree, required tree constants enabled.'
        Write-Host 'Launch GTAIV yourself and compare the same daytime tree-and-ground scene.'
        exit
    }
}

if ($Action -eq 'TraceAliases') {

    $diagnostics = Game-Path 'ENBCompat'
    if (Test-Path -LiteralPath $diagnostics) {
        $archiveRoot = Join-Path $kitRoot 'trace-archive'
        New-Item -ItemType Directory -Force -Path $archiveRoot | Out-Null
        $archive = Join-Path $archiveRoot (Get-Date -Format 'yyyyMMdd-HHmmss')
        if (Test-Path -LiteralPath $archive) { throw "Trace archive already exists: $archive" }
        Move-Item -LiteralPath $diagnostics -Destination $archive
        Write-Host "Previous diagnostics archived: $archive"
    }
    New-Item -ItemType Directory -Path $diagnostics | Out-Null

    $ini = Game-Path 'plugins\GTAIV.EFLC.FusionFix.ini'
    $text = Get-Content -LiteralPath $ini -Raw
    $values = [ordered]@{
        D3D9Trace = '1'; DumpShaders = '1'; TraceResources = '0';
        TraceShaderBinds = '0'; TraceTextures = '0'; TraceConstants = '0';
        TraceDraws = '0'; TraceKey = '0'; TraceStartFrame = '0'; TraceFrameCount = '0'
    }
    foreach ($key in $values.Keys) {
        $pattern = '(?m)^' + [regex]::Escape($key) + '\s*=.*$'
        if ([regex]::Matches($text, $pattern).Count -ne 1) { throw "Expected one $key setting in FusionFix ini." }
        $text = [regex]::Replace($text, $pattern, "$key = $($values[$key])")
    }
    [IO.File]::WriteAllText($ini, $text, [Text.UTF8Encoding]::new($false))
    $activeAliases = @()
    foreach ($name in 'pshA5F4E880.txt', 'pshFDFF185D.txt', 'psh1D661524.txt') {
        $path = Game-Path "shaderinput\$name"
        $activeAliases += [pscustomobject]@{
            file = $name
            sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        }
    }
    $session = [pscustomobject]@{
        format = 1
        action = 'TraceAliases'
        prepared_utc = [DateTime]::UtcNow.ToString('o')
        fusionfix_asi_sha256 = (Get-FileHash -LiteralPath $targetAsi -Algorithm SHA256).Hash
        aliases = $activeAliases
    }
    [IO.File]::WriteAllText((Join-Path $diagnostics 'trace-session.json'),
                            ($session | ConvertTo-Json -Depth 4),
                            [Text.UTF8Encoding]::new($false))
    Write-Host 'TraceAliases files verified. Launch GTAIV yourself, load any normal scene, move around briefly, then exit normally.'
    Write-Host "After exit run: & '$PSCommandPath' -Kit '$kitRoot' -Game '$gameRoot' -Action CollectTrace"
    exit
}
Write-Host "$Action files ready. Launch GTAIV yourself. Set DOF to Low or higher; do not enable tracing or version spoofing."
