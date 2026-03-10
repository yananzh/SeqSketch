@echo off
setlocal
cd /d %~dp0\..

set PROFILE=%1
if "%PROFILE%"=="" set PROFILE=balanced

powershell -ExecutionPolicy Bypass -File ".\scripts\build_windows_onefile.ps1" -Profile %PROFILE%
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

echo Build succeeded.
exit /b 0
