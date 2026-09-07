<#
.SYNOPSIS
Install or restore the strict stock-CE ENB profile without launching the game.
.DESCRIPTION
Preserves FusionFix's normal update content and all non-shader INI settings.
Installs the checked stock cache, stock-only aliases and ASI. Removes retired
modern aliases/bridge assets with a per-file snapshot for exact restoration.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Apply','Restore')][string]$Action,
    [Parameter(Mandatory)][string]$Kit,
    [string]$Game = 'C:\Games\Steam\steamapps\common\Grand Theft Auto IV\GTAIV',
    [string]$Stage = ''
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$gameRoot = (Resolve-Path -LiteralPath $Game).Path.TrimEnd('\')
$kitRoot = (Resolve-Path -LiteralPath $Kit).Path.TrimEnd('\')
function Checked-Path([string]$root, [string]$relative) {
    $path = [IO.Path]::GetFullPath((Join-Path $root $relative))
    if (-not $path.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Path escapes its root.' }
    return $path
}
function Hash([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
if ($kitRoot -eq $gameRoot -or $kitRoot.StartsWith($gameRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Keep the kit outside the game.' }
if (-not (Test-Path -LiteralPath (Join-Path $gameRoot 'GTAIV.exe') -PathType Leaf)) { throw 'GTAIV.exe is missing.' }
if (Get-Process GTAIV -ErrorAction SilentlyContinue) { throw 'Close GTAIV before changing files.' }
$snapshot = Checked-Path $kitRoot 'stock-ce-snapshot'
$snapshotManifest = Join-Path $snapshot 'manifest.json'
$iniPath = Checked-Path $gameRoot 'plugins/GTAIV.EFLC.FusionFix.ini'
$sources = @{}
$expected = @{}
$removed = @()
$whitelist = Get-Content -LiteralPath (Join-Path $repoRoot 'research/contracts/stock-ce-baseline.json') -Raw | ConvertFrom-Json
$recipes = Get-Content -LiteralPath (Join-Path $repoRoot 'research/contracts/stock-ce-adapters.json') -Raw | ConvertFrom-Json
$approvedAliases = @{}
foreach ($entry in $recipes.entries) { foreach ($target in $entry.targets) { $approvedAliases[$target.stock_alias] = $target.assembly_sha256 } }
$retiredPaths = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'retired-shader-paths.json') -Raw | ConvertFrom-Json
foreach ($retiredPath in $retiredPaths) { if ($retiredPath -isnot [string]) { throw 'Invalid retired shader path list.' } }
$allowed = @('plugins/GTAIV.EFLC.FusionFix.asi','plugins/GTAIV.EFLC.FusionFix.ini') + $retiredPaths
$allowed += @($whitelist.files.PSObject.Properties | ForEach-Object { 'plugins/ENBCompat/StockCE/' + $_.Name })
$allowed += @($approvedAliases.Keys | ForEach-Object { 'shaderinput/' + $_ })
if ($Action -eq 'Apply') {
    if (-not $Stage) { $Stage = Join-Path $repoRoot 'build/stock-enb-v1' }
    $stageRoot = (Resolve-Path -LiteralPath $Stage).Path.TrimEnd('\')
    $package = Get-Content -LiteralPath (Join-Path $stageRoot 'manifest.json') -Raw | ConvertFrom-Json
    if ($package.format -ne 1 -or $package.profile -ne 'stock-ce-only') { throw 'Only the stock CE package is supported.' }
    $baseFiles = @($whitelist.files.PSObject.Properties)
    if (@($package.baseline_files.PSObject.Properties).Count -ne $baseFiles.Count) { throw 'Incomplete stock baseline.' }
    foreach ($cacheRoot in @((Join-Path $stageRoot 'StockCE'), (Checked-Path $gameRoot 'plugins/ENBCompat/StockCE'))) {
        if (Test-Path -LiteralPath $cacheRoot -PathType Container) {
            foreach ($file in Get-ChildItem -LiteralPath $cacheRoot -Recurse -File) {
                $relative = $file.FullName.Substring($cacheRoot.Length + 1).Replace('\','/')
                if (-not $whitelist.files.PSObject.Properties[$relative]) { throw 'Unexpected file in the stock shader cache.' }
            }
        }
    }
    foreach ($file in $baseFiles) {
        if ($package.baseline_files.($file.Name) -ne $file.Value) { throw 'Stock whitelist mismatch.' }
        $relative = 'plugins/ENBCompat/StockCE/' + $file.Name
        $sources[$relative] = Checked-Path $stageRoot ('StockCE/' + $file.Name)
        $expected[$relative] = $file.Value
        # The actual target installation must also contain the exact originals.
        if ((Hash (Checked-Path $gameRoot ('common/shaders/' + $file.Name))) -ne $file.Value) { throw "Original CE shader file changed: $($file.Name)" }
    }
    if (@($package.aliases.PSObject.Properties).Count -ne $approvedAliases.Count) { throw 'Incomplete stock alias set.' }
    foreach ($alias in $package.aliases.PSObject.Properties) {
        if ($alias.Name -cnotmatch '^[pv]sh[0-9A-F]{8}\.txt$') { throw 'Invalid stock alias.' }
        if (-not $approvedAliases.ContainsKey($alias.Name) -or $approvedAliases[$alias.Name] -ne $alias.Value) { throw 'Alias differs from the reviewed stock translation.' }
        $relative = 'shaderinput/' + $alias.Name
        $sources[$relative] = Checked-Path $stageRoot $relative
        $expected[$relative] = $alias.Value
    }
    $sources['plugins/GTAIV.EFLC.FusionFix.asi'] = Checked-Path $stageRoot 'GTAIV.EFLC.FusionFix.asi'
    $expected['plugins/GTAIV.EFLC.FusionFix.asi'] = $package.asi_sha256
    foreach ($relative in $sources.Keys) {
        if ((Hash $sources[$relative]) -ne $expected[$relative]) { throw "Staged file hash mismatch: $relative" }
    }
    $removed = $retiredPaths
    $removed = @($removed | Where-Object { -not $sources.ContainsKey($_) })
    if ((Hash (Checked-Path $gameRoot 'd3d9.dll')) -ne '280e2bc15485bb7b944d47bad9e7d553b6e63eba3afb97bdbc546d45fcc203c4') { throw 'The stock aliases require the audited ENB 0.163 wrapper.' }
    $ini = [IO.File]::ReadAllText($iniPath)
    $sections = [regex]::Matches($ini, '(?ims)^\[ENBCompatibility\][^\r\n]*\r?\n(?<body>.*?)(?=^\[|\z)')
    if ($sections.Count -gt 1) { throw 'Duplicate ENBCompatibility section.' }
    if ($sections.Count -eq 0) { $newIni = $ini + "`r`n[ENBCompatibility]`r`nMode = 1`r`n" }
    else {
        $section = $sections[0]
        $body = $section.Groups['body'].Value
        $retiredKeys = 'PostFxBridge|ReplacePostFX|PostProcessAA|AmbientOcclusion|ShadowPipelineFixes|FusionShaderTweaks|SunShafts|PreAlphaDepthCopy|SkyDiffuseSplit|ConsoleGammaBlit|ShaderConstantInjection|FusionShaderPackage|StockShaderFolder|TracePostFxInputs|ShaderPreload|ReflectionShaders|SnowShaders'
        $body = [regex]::Replace($body, ('(?im)^\s*(?:' + $retiredKeys + ')\s*=[^\r\n]*\r?\n?'), '')
        $modeMatches = [regex]::Matches($body, '(?im)^Mode\s*=[^\r\n]*')
        if ($modeMatches.Count -gt 1) { throw 'Duplicate ENB mode setting.' }
        if ($modeMatches.Count) { $body = [regex]::Replace($body, '(?im)^Mode\s*=[^\r\n]*', 'Mode = 1') }
        else { $body = "Mode = 1`r`n" + $body }
        $newIni = $ini.Substring(0, $section.Groups['body'].Index) + $body + $ini.Substring($section.Index + $section.Length)
    }
    $paths = @(@($sources.Keys) + $removed + 'plugins/GTAIV.EFLC.FusionFix.ini' | Sort-Object -Unique)
    foreach ($relative in $paths) {
        $target = Checked-Path $gameRoot $relative
        if ((Test-Path -LiteralPath $target) -and -not (Test-Path -LiteralPath $target -PathType Leaf)) { throw "Expected a file: $relative" }
    }
    if (-not (Test-Path -LiteralPath $snapshotManifest)) {
        if (Test-Path -LiteralPath $snapshot) { throw 'An incomplete stock snapshot exists; preserve and inspect it.' }
        New-Item -ItemType Directory -Path $snapshot | Out-Null
        $entries = @()
        foreach ($relative in $paths) {
            $target = Checked-Path $gameRoot $relative
            $exists = Test-Path -LiteralPath $target -PathType Leaf
            $digest = $null
            if ($exists) {
                $digest = Hash $target
                $saved = Checked-Path $snapshot $relative
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $saved) | Out-Null
                Copy-Item -LiteralPath $target -Destination $saved
                if ((Hash $saved) -ne $digest) { throw 'Backup verification failed.' }
            }
            $entries += [pscustomobject]@{ path = $relative; existed = $exists; sha256 = $digest }
        }
        [pscustomobject]@{ format = 1; game = $gameRoot; entries = $entries } | ConvertTo-Json -Depth 5 |
            Set-Content -LiteralPath $snapshotManifest -Encoding UTF8
    }
}
if (-not (Test-Path -LiteralPath $snapshotManifest)) { throw 'No stock snapshot exists.' }
$manifest = Get-Content -LiteralPath $snapshotManifest -Raw | ConvertFrom-Json
if ($manifest.format -ne 1 -or $manifest.game -ne $gameRoot -or -not $manifest.entries.Count -or
    @($manifest.entries.path | Sort-Object -Unique).Count -ne $manifest.entries.Count) { throw 'Invalid stock snapshot.' }
if ($Action -eq 'Apply' -and @(Compare-Object $paths @($manifest.entries.path)).Count) { throw 'Package paths differ from the existing stock snapshot.' }
foreach ($entry in $manifest.entries) {
    if ($entry.path -notin $allowed) { throw 'Unexpected stock snapshot path.' }
    $null = Checked-Path $gameRoot $entry.path
    if ($entry.existed -and (Hash (Checked-Path $snapshot $entry.path)) -ne $entry.sha256) { throw 'Backup hash mismatch.' }
}
function Restore-Files {
    foreach ($entry in $manifest.entries) {
        $target = Checked-Path $gameRoot $entry.path
        if ($entry.existed) {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            Copy-Item -LiteralPath (Checked-Path $snapshot $entry.path) -Destination $target -Force
            if ((Hash $target) -ne $entry.sha256) { throw 'Restore verification failed.' }
        } elseif (Test-Path -LiteralPath $target -PathType Leaf) { Remove-Item -LiteralPath $target }
    }
}
if ($Action -eq 'Restore') {
    Restore-Files
    Write-Host 'Pre-test files restored; all original snapshots and unrelated content retained.'
    exit
}
try {
    foreach ($relative in $sources.Keys) {
        $target = Checked-Path $gameRoot $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $sources[$relative] -Destination $target -Force
        if ((Hash $target) -ne $expected[$relative]) { throw "Installed hash mismatch: $relative" }
    }
    foreach ($relative in $removed) {
        $target = Checked-Path $gameRoot $relative
        if (Test-Path -LiteralPath $target -PathType Leaf) { Remove-Item -LiteralPath $target }
    }
    [IO.File]::WriteAllText($iniPath, $newIni, [Text.UTF8Encoding]::new($false))
} catch {
    $failure = $_
    Restore-Files
    throw $failure
}
Write-Host 'Strict stock CE ENB mode installed. FusionFix gameplay/camera settings and update content retained. No game launched.'
Write-Host "Restore: & '$PSCommandPath' -Action Restore -Kit '$kitRoot' -Game '$gameRoot'"
