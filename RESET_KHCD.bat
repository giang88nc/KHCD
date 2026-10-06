@echo off
REM ============================================================
REM  RESET_KHCD.bat - CUA VAO DUY NHAT van hanh KHCD cam do (07/10/2026, GD chot)
REM    (bam dup, khong tham so)  RESET: kiem dieu kien -> TAT het -> kiem tat sach
REM                              -> BAT lai -> kiem OK (cong + /health that)
REM    /reset  nhu tren nhung khong dung cho o cuoi (Claude / lenh goi)
REM    /bat    chi bat cai dang thieu   /tat  tat han (bao tri)   /kiem  chi xem
REM  Don vi KHCD = cau noi khach hang 18202 + waitress 8201 + Caddy HTTPS 8200
REM               + giam sat (khoa 8219; THAY tac vu "KHCD Web Host" + scripts\host.ps1 cu).
REM  KHONG dung toi KHJ / KHBL / NGROK.
REM  Ba chot an toan cu GIU NGUYEN trong dong co: thieu dieu kien (MySQL80 / .venv / caddy /
REM  CA noi bo / khoa cau noi / venv KHBL) thi KHONG tat gi; tat khong sach thi BAO RO (con
REM  ma .py CU); bat lai that bai thi bao he dang tat va giam sat van thu bat lai moi 60s.
REM  Quyen thuong cung bam duoc: tu nho tac vu Windows "KimHanh2-VanHanh-KHCD" (khong hoi UAC).
REM  Dong co: ops\vanhanh\vanhanh.ps1 (ban sao giong het KHJ) + cauhinh_khcd.ps1
REM  Log: instance\vanhanh_khcd.log. Goi tu PowerShell: cmd /c D:\PYTHON\KHCD\RESET_KHCD.bat /reset
REM  Sua .py trong khcd\ -> RESET_KHCD. Sua .html/.css/.js -> chi F5.
REM ============================================================
setlocal
set "LENH=reset"
if /i "%~1"=="/bat" set "LENH=bat"
if /i "%~1"=="/tat" set "LENH=tat"
if /i "%~1"=="/kiem" set "LENH=kiem"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\vanhanh\vanhanh.ps1" -CauHinh "%~dp0ops\vanhanh\cauhinh_khcd.ps1" -Lenh %LENH%
set "KQ=%errorlevel%"
if "%~1"=="" pause
exit /b %KQ%
