@echo off
rem Puts the ENB shader files back the way they shipped, removing the visual
rem probes. Run this once the probe test has been read.
rem
rem   ENBCompat-Probe off    restore the original shaderinput\ and enbeffect.fx
rem   ENBCompat-Probe on     re-apply the probes from the saved probe copies

setlocal
set "G=%~dp0"

if /i "%~1"=="off" goto :restore
if /i "%~1"=="on"  goto :apply

echo Usage: ENBCompat-Probe [on^|off]
echo.
echo   off   restore the shaders ENB shipped
echo   on    re-apply the colour probes
echo.
goto :state

:restore
if not exist "%G%shaderinput.orig" echo No backup found: %G%shaderinput.orig & goto :state
if exist "%G%shaderinput.probe" rd /s /q "%G%shaderinput.probe"
xcopy /e /i /y /q "%G%shaderinput" "%G%shaderinput.probe" >nul
if exist "%G%enbeffect.fx" copy /y "%G%enbeffect.fx" "%G%enbeffect.fx.probe" >nul
rd /s /q "%G%shaderinput"
xcopy /e /i /y /q "%G%shaderinput.orig" "%G%shaderinput" >nul
copy /y "%G%enbeffect.fx.orig" "%G%enbeffect.fx" >nul
echo Probes removed. ENB's original shaders are back.
goto :state

:apply
if not exist "%G%shaderinput.probe" echo No probe copy found. & goto :state
rd /s /q "%G%shaderinput"
xcopy /e /i /y /q "%G%shaderinput.probe" "%G%shaderinput" >nul
copy /y "%G%enbeffect.fx.probe" "%G%enbeffect.fx" >nul
echo Probes re-applied.
goto :state

:state
echo.
findstr /c:"ENBCOMPAT PROBE" "%G%enbeffect.fx" >nul 2>&1
if errorlevel 1 (echo   enbeffect.fx probe  off) else (echo   enbeffect.fx probe  ON)
findstr /b /c:"mov oC0" "%G%shaderinput\psh2DF967C6.txt" >nul 2>&1
if errorlevel 1 (echo   shaderinput probes  off) else (echo   shaderinput probes  ON)
echo.
pause
