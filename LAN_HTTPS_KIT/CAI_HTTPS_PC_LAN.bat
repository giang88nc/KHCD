@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0configure-lan.ps1"
if errorlevel 1 (
  echo Khong hoan tat. Xem install-result.txt trong thu muc nay.
  pause
)
