<#
.SYNOPSIS
Headless integration test of material Apply/Restore in a new synthetic directory.
.DESCRIPTION
Reads the supplied shader corpus, stage and wrapper; writes only a new build
directory. Its GTAIV.exe is a text placeholder and is never executed. Keeps
the fixture and verification log for review.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Stage,
    [Parameter(Mandatory)][string]$ModernCorpus,
    [Parameter(Mandatory)][string]$EnbWrapper,
    [string]$PreviousStage = ''
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$root = Join-Path $repoRoot ('build\material-setup-test-' + [guid]::NewGuid().ToString('N'))
$game = Join-Path $root 'game'
$kit = Join-Path $root 'kit'
$staged = Join-Path $root 'stage'
$variant = Join-Path $game 'update\common\shaders\win32_30'
$shaderinput = Join-Path $game 'shaderinput'
$ini = Join-Path $game 'plugins\GTAIV.EFLC.FusionFix.ini'
$script = Join-Path $PSScriptRoot 'Invoke-ModernMaterialTest.ps1'
foreach ($directory in @($game, $kit, $staged, $variant, $shaderinput, (Split-Path -Parent $ini),
                          (Join-Path $staged 'shaderinput'), (Join-Path $staged 'assembled'))) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
Copy-Item -LiteralPath (Join-Path $Stage 'manifest.json') -Destination $staged
foreach ($name in @('shaderinput', 'assembled')) {
    Get-ChildItem -LiteralPath (Join-Path $Stage $name) -File | Copy-Item -Destination (Join-Path $staged $name)
}
Get-ChildItem -LiteralPath $ModernCorpus -Filter *.fxc -File | Copy-Item -Destination $variant
Copy-Item -LiteralPath $EnbWrapper -Destination (Join-Path $game 'd3d9.dll')
[IO.File]::WriteAllText((Join-Path $game 'GTAIV.exe'), 'Synthetic fixture; never execute.')
[IO.File]::WriteAllText((Join-Path $game 'enbeffect.fx'), 'Effect must stay unchanged.')
$config = "[ENBCompatibility]`nMode = 1`nPostFxBridge = 1`nFusionShaderPackage = 1`nShaderConstantInjection = 1`nShadowPipelineFixes = 1`nReplacePostFX = 0`n"
[IO.File]::WriteAllText($ini, $config)
$aliases = @(Get-ChildItem -LiteralPath (Join-Path $staged 'shaderinput') -File | Sort-Object Name)
$existing = Join-Path $shaderinput $aliases[0].Name
[IO.File]::WriteAllText($existing, 'Existing user alias')
[IO.File]::WriteAllText((Join-Path $shaderinput 'unrelated.txt'), 'Unrelated shader stays unchanged.')
function Hash([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
$originalHash = Hash $existing
$originalAliases = @{ $aliases[0].Name = $originalHash }
$effectHash = Hash (Join-Path $game 'enbeffect.fx')
function Invoke-TestAction([string]$action, [bool]$succeeds, [string]$testStage = $staged) {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $log = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $script -Action $action -Kit $kit -Game $game -Stage $testStage 2>&1 | Out-String
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    Add-Content -LiteralPath (Join-Path $root 'actions.txt') -Value $log
    if (($code -eq 0) -ne $succeeds) { throw "Unexpected result for $action, exit $code. $log" }
}
function Assert-Installed {
    foreach ($alias in $aliases) {
        if ((Hash (Join-Path $shaderinput $alias.Name)) -ne (Hash $alias.FullName)) { throw 'Installed alias mismatch.' }
    }
    if ((Hash (Join-Path $game 'enbeffect.fx')) -ne $effectHash) { throw 'Effect unexpectedly changed.' }
}
# Missing corpus member must reject before creating a snapshot or changing aliases.
$container = @(Get-ChildItem -LiteralPath $variant -File)[0]
$containerBytes = [IO.File]::ReadAllBytes($container.FullName)
Remove-Item -LiteralPath $container.FullName
Invoke-TestAction Apply $false
if ((Hash $existing) -ne $originalHash -or (Test-Path -LiteralPath (Join-Path $kit 'modern-material-snapshot'))) { throw 'Preflight mutated the fixture.' }
[IO.File]::WriteAllBytes($container.FullName, $containerBytes)
$snapshot = Join-Path $kit 'modern-material-snapshot'
if ($PreviousStage) {
    $previousNames = @(Get-ChildItem -LiteralPath (Join-Path $PreviousStage 'shaderinput') -File | ForEach-Object { $_.Name })
    $newAliases = @($aliases | Where-Object { $_.Name -notin $previousNames })
    if (-not $newAliases.Count) { throw 'The upgrade test needs an expanded stage.' }
    $newOriginal = Join-Path $shaderinput $newAliases[0].Name
    [IO.File]::WriteAllText($newOriginal, 'Original user shader for newly translated pass')
    $originalAliases[$newAliases[0].Name] = Hash $newOriginal
    Invoke-TestAction Apply $true $PreviousStage
    $oldManifest = Get-Content -LiteralPath (Join-Path $snapshot 'manifest.json') -Raw | ConvertFrom-Json
    $oldManifestHash = Hash (Join-Path $snapshot 'manifest.json')
    # An invalid newly added asset must leave the old snapshot and new original intact.
    $newBytes = [IO.File]::ReadAllBytes($newAliases[0].FullName)
    [IO.File]::WriteAllText($newAliases[0].FullName, 'Corrupt upgrade asset')
    Invoke-TestAction Apply $false
    if ((Hash (Join-Path $snapshot 'manifest.json')) -ne $oldManifestHash -or
        (Hash $newOriginal) -ne $originalAliases[$newAliases[0].Name]) { throw 'Rejected upgrade mutated the original state.' }
    [IO.File]::WriteAllBytes($newAliases[0].FullName, $newBytes)
}
# Full apply and reapply retain the original snapshot.
Invoke-TestAction Apply $true
Assert-Installed
if ($PreviousStage) {
    $expandedManifest = Get-Content -LiteralPath (Join-Path $snapshot 'manifest.json') -Raw | ConvertFrom-Json
    if ($expandedManifest.entries.Count -ne $aliases.Count) { throw 'Upgrade did not snapshot every alias.' }
    foreach ($entry in $oldManifest.entries) {
        $retained = @($expandedManifest.entries | Where-Object { $_.name -eq $entry.name })
        if ($retained.Count -ne 1 -or $retained[0].existed -ne $entry.existed -or $retained[0].sha256 -ne $entry.sha256) { throw 'Upgrade replaced an original snapshot entry.' }
    }
    Invoke-TestAction Apply $false $PreviousStage
    Assert-Installed
}
$snapshotHash = Hash (Join-Path $snapshot 'manifest.json')
Invoke-TestAction Apply $true
Assert-Installed
if ((Hash (Join-Path $snapshot 'manifest.json')) -ne $snapshotHash) { throw 'Reapply changed the original snapshot.' }
# Changed stage and incompatible renderer fail before changing any alias.
$assetBytes = [IO.File]::ReadAllBytes($aliases[0].FullName)
[IO.File]::WriteAllText($aliases[0].FullName, 'Changed stage')
Invoke-TestAction Apply $false
[IO.File]::WriteAllBytes($aliases[0].FullName, $assetBytes)
Assert-Installed
[IO.File]::WriteAllText($ini, $config.Replace('FusionShaderPackage = 1', 'FusionShaderPackage = 0'))
Invoke-TestAction Apply $false
Assert-Installed
[IO.File]::WriteAllText($ini, $config)
# A corrupt backup cannot cause a partially restored set.
$saved = Join-Path $snapshot $aliases[0].Name
$savedBytes = [IO.File]::ReadAllBytes($saved)
[IO.File]::WriteAllText($saved, 'Changed backup')
Invoke-TestAction Restore $false
Assert-Installed
[IO.File]::WriteAllBytes($saved, $savedBytes)
Invoke-TestAction Restore $true
if ((Hash $existing) -ne $originalHash) { throw 'Original alias was not restored.' }
foreach ($alias in $aliases) {
    $restored = Join-Path $shaderinput $alias.Name
    if ($originalAliases.ContainsKey($alias.Name)) {
        if ((Hash $restored) -ne $originalAliases[$alias.Name]) { throw 'Original alias was not restored.' }
    } elseif (Test-Path -LiteralPath $restored) { throw 'New alias survived restoration.' }
}
if ((Get-Content -LiteralPath (Join-Path $shaderinput 'unrelated.txt') -Raw) -ne 'Unrelated shader stays unchanged.' -or
    (Hash (Join-Path $game 'enbeffect.fx')) -ne $effectHash -or (Get-Content -LiteralPath $ini -Raw) -ne $config) { throw 'Unrelated fixture data changed.' }
Invoke-TestAction Restore $true
$summary = "PASS: $($aliases.Count) aliases; Apply/reapply/Restore/repeated Restore; missing package, changed asset, stock profile and corrupt backup rejected before mutation. No game launched."
if ($PreviousStage) { $summary += ' Expanded-stage upgrade preserves all original backups; invalid upgrades and shrinking stages rejected.' }
Set-Content -LiteralPath (Join-Path $root 'result.txt') -Value $summary -Encoding UTF8
Write-Output $summary
Write-Output "Evidence: $root"
