<# Headless installation/rollback checks using a new synthetic game directory. #>
[CmdletBinding()]
param([Parameter(Mandatory)][string]$Stage, [Parameter(Mandatory)][string]$EnbWrapper)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$root = Join-Path $repoRoot ('build/stock-setup-test-' + [guid]::NewGuid().ToString('N'))
$game = Join-Path $root 'game'
$kit = Join-Path $root 'kit'
$staged = Join-Path $root 'stage'
$script = Join-Path $PSScriptRoot 'Invoke-StockENBTest.ps1'
New-Item -ItemType Directory -Path $game,$kit,$staged | Out-Null
$stageRoot = (Resolve-Path -LiteralPath $Stage).Path
foreach ($file in Get-ChildItem -LiteralPath $stageRoot -Recurse -File) {
    $relative = $file.FullName.Substring($stageRoot.Length + 1)
    $target = Join-Path $staged $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $target
}
$package = Get-Content -LiteralPath (Join-Path $staged 'manifest.json') -Raw | ConvertFrom-Json
foreach ($file in $package.baseline_files.PSObject.Properties) {
    $target = Join-Path $game ('common/shaders/' + $file.Name)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    Copy-Item -LiteralPath (Join-Path $staged ('StockCE/' + $file.Name)) -Destination $target
}
Copy-Item -LiteralPath $EnbWrapper -Destination (Join-Path $game 'd3d9.dll')
function Write-Fixture([string]$relative, [string]$text) {
    $target = Join-Path $game $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    [IO.File]::WriteAllText($target, $text)
}
Write-Fixture 'GTAIV.exe' 'Synthetic text placeholder; never execute.'
Write-Fixture 'plugins/GTAIV.EFLC.FusionFix.asi' 'Previous ASI'
Write-Fixture 'plugins/ENBCompat/legacy_composite.cso' 'Retired bridge'
Write-Fixture 'shaderinput/pshC0223F26.txt' 'Retired modern terrain alias'
Write-Fixture 'shaderinput/pshDEADBEEF.txt' 'Unrelated user alias'
Write-Fixture 'enbeffect.fx' 'Existing ENB effect'
Write-Fixture 'update/common/shaders/win32_30/gta_default.fxc' 'Normal-mode FusionShader package retained'
Write-Fixture 'update/GTAIV.EFLC.FusionFix/gameplay.sco' 'Gameplay content retained'
$ini = "[MAIN]`r`nFramerateLimit = 90`r`nCameraFOV = 81`r`n[ENBCompatibility]`r`nMode = 1`r`nPostFxBridge = 1`r`nFusionShaderPackage = 1`r`nShaderConstantInjection = 1`r`nStockShaderFolder = win32_30`r`nSpoofGameVersionFor = custom_camera.asi`r`nLoadPluginAfterSpoof = custom_camera.enbcompat`r`n[INPUT]`r`nMouseSensitivity = 7`r`n"
Write-Fixture 'plugins/GTAIV.EFLC.FusionFix.ini' $ini
function Hash([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
function Inventory {
    $result = @{}
    foreach ($file in Get-ChildItem -LiteralPath $game -Recurse -File) {
        $result[$file.FullName.Substring($game.Length + 1)] = Hash $file.FullName
    }
    return $result
}
function Assert-Inventory($expected) {
    $actual = Inventory
    if ($expected.Count -ne $actual.Count) { throw 'File inventory changed unexpectedly.' }
    foreach ($path in $expected.Keys) { if ($actual[$path] -ne $expected[$path]) { throw "Unexpected file change: $path" } }
}
function Run([string]$action, [bool]$okay) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $log = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $script -Action $action -Game $game -Kit $kit -Stage $staged 2>&1 | Out-String
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    Add-Content -LiteralPath (Join-Path $root 'actions.txt') -Value $log
    if (($code -eq 0) -ne $okay) { throw "Unexpected $action result ($code): $log" }
}
$before = Inventory
$bad = Join-Path $staged 'StockCE/preload.list'
$originalBytes = [IO.File]::ReadAllBytes($bad)
[IO.File]::WriteAllText($bad, 'Changed staged preload')
Run Apply $false
Assert-Inventory $before
if (Test-Path -LiteralPath (Join-Path $kit 'stock-ce-snapshot')) { throw 'Failed preflight created a snapshot.' }
[IO.File]::WriteAllBytes($bad, $originalBytes)
Run Apply $true
$after = Inventory
$installedIni = Get-Content -LiteralPath (Join-Path $game 'plugins/GTAIV.EFLC.FusionFix.ini') -Raw
if ($installedIni -match 'PostFxBridge\s*=|FusionShaderPackage\s*=|ShaderConstantInjection\s*=|StockShaderFolder\s*=') { throw 'Retired renderer override survived.' }
foreach ($line in @('FramerateLimit = 90','CameraFOV = 81','MouseSensitivity = 7',
                    'SpoofGameVersionFor = custom_camera.asi','LoadPluginAfterSpoof = custom_camera.enbcompat')) {
    if (-not $installedIni.Contains($line)) { throw 'A non-shader preference was changed.' }
}
foreach ($path in @('enbeffect.fx','shaderinput\pshDEADBEEF.txt','update\common\shaders\win32_30\gta_default.fxc','update\GTAIV.EFLC.FusionFix\gameplay.sco')) {
    if ($after[$path] -ne $before[$path]) { throw 'Unrelated game content changed.' }
}
foreach ($path in @('plugins/ENBCompat/legacy_composite.cso','shaderinput/pshC0223F26.txt')) {
    if (Test-Path -LiteralPath (Join-Path $game $path)) { throw 'Retired shader workaround survived installation.' }
}
foreach ($file in $package.baseline_files.PSObject.Properties) {
    if ((Hash (Join-Path $game ('plugins/ENBCompat/StockCE/' + $file.Name))) -ne $file.Value) { throw 'Installed baseline is not exact.' }
}
Run Apply $true
Assert-Inventory $after
# A changed real baseline is rejected before mutation, even with a valid stage.
$base = Join-Path $game 'common/shaders/preload.list'
[IO.File]::WriteAllText($base, 'Changed actual baseline')
$badBefore = Inventory
Run Apply $false
Assert-Inventory $badBefore
[IO.File]::WriteAllBytes($base, $originalBytes)
# Corrupt backups and unexpected restore paths must not partially restore files.
$saved = Join-Path $kit 'stock-ce-snapshot/plugins/GTAIV.EFLC.FusionFix.asi'
$savedBytes = [IO.File]::ReadAllBytes($saved)
[IO.File]::WriteAllText($saved, 'Changed backup')
Run Restore $false
Assert-Inventory $after
[IO.File]::WriteAllBytes($saved, $savedBytes)
Run Restore $true
Assert-Inventory $before
Run Restore $true
Assert-Inventory $before
$result = 'PASS: 339 exact stock files and 11 aliases; Apply/reapply/Restore/repeated Restore; stale modern overrides and assets removed; non-shader settings/content preserved; changed stage/base/backup rejected before mutation. No game launched.'
Set-Content -LiteralPath (Join-Path $root 'result.txt') -Value $result -Encoding UTF8
Write-Output $result
Write-Output "Evidence: $root"
