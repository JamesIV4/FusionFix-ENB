@echo off
rem Switches which ENB preset is installed.
rem
rem   ENBCompat-Preset ice40    iCEnhancer 4.0  (12 shaderinput files + icenhancer.asi)
rem   ENBCompat-Preset enb163   ENBSeries 0.163 (4 shaderinput files, the plain base)
rem
rem Both run on the same ENBSeries 0.163 d3d9.dll, which ENBCompat-Mode turns on
rem and off; this only swaps the preset's own files. iCEnhancer 4.0 requires
rem 0.163 specifically, and icenhancer.asi loads alongside it rather than
rem replacing it -- with both active the game shows two logos on startup.
rem
rem Game content that iCEnhancer also ships (american.gxt, the rain/storm effect
rem XMLs, skydome.wtd and visualSettings.dat) is NOT swapped here. Use
rem ENBCompat-Restore to put the originals back.

setlocal
set "G=%~dp0"
set "B=%G%_ENBCompat_Backup"

if /i "%~1"=="ice40"  set "SRC=%B%\ice40"   & set "NAME=iCEnhancer 4.0"   & goto :apply
if /i "%~1"=="enb163" set "SRC=%B%\enb0163" & set "NAME=ENBSeries 0.163"  & goto :apply

echo Usage: ENBCompat-Preset [ice40^|enb163]
echo.
echo   ice40    iCEnhancer 4.0, 12 shader replacements plus icenhancer.asi
echo   enb163   plain ENBSeries 0.163, 4 shader replacements
echo.
goto :report

:apply
if not exist "%SRC%" echo Snapshot not found: %SRC% & goto :report
if /i "%~1"=="ice40" (set "ICE=1") else (set "ICE=")

rem icenhancer belongs only to the iCEnhancer preset; drop it otherwise so the
rem plain 0.163 preset is not silently running iCEnhancer's code as well.
rem
rem Both names have to go. The file is renamed to .enbcompat so the ASI loader
rem ignores it and FusionFix can load it itself at a controlled moment -- and
rem FusionFix will keep doing that from LoadPluginAfterSpoof regardless of which
rem preset is installed, so deleting only the .asi name would leave iCEnhancer
rem running underneath the 0.163 preset.
if exist "%G%icenhancer.asi"       del /q "%G%icenhancer.asi"
if exist "%G%icenhancer.enbcompat" del /q "%G%icenhancer.enbcompat"

rem shaderinput is replaced wholesale: the two presets ship different counts and
rem a leftover file from the other one would keep being matched.
if exist "%G%shaderinput" rd /s /q "%G%shaderinput"

xcopy /e /i /y /q "%SRC%" "%G%" >nul

rem The ice40 snapshot holds icenhancer.asi; rename it so the ASI loader leaves
rem it alone and FusionFix's LoadPluginAfterSpoof owns the timing.
if defined ICE if exist "%G%icenhancer.asi" move /y "%G%icenhancer.asi" "%G%icenhancer.enbcompat" >nul

echo Installed preset: %NAME%
if not defined ICE echo   Remember to blank LoadPluginAfterSpoof in the ini, or set SpoofGameVersion empty.
goto :report

:report
echo.
echo Current state:
set "S1=off"
set "S2=off"
set "S3=none"
if exist "%G%d3d9.dll"             set "S1=ON"
if exist "%G%icenhancer.asi"       set "S2=ON, loaded by the ASI loader"
if exist "%G%icenhancer.enbcompat" set "S2=ON, loaded by FusionFix"
if exist "%G%shaderinput"    for /f %%n in ('dir /b "%G%shaderinput\*.txt" 2^>nul ^| find /c /v ""') do set "S3=%%n files"
echo   ENB d3d9.dll       %S1%
echo   icenhancer.asi     %S2%
echo   shaderinput        %S3%
echo.
pause
