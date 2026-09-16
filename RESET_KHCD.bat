@echo off
REM ============================================================
REM  RESET_KHCD.bat - Tat roi bat lai KHCD - 16/09/2026
REM    Dung khi sua tep .py trong khcd\ (Python da nap vao tien trinh waitress,
REM    khong nap nong duoc). Sua .html / .css / .js: CHI CAN F5, khong can RESET.
REM
REM  BA CHOT AN TOAN, deu la bai hoc that:
REM   1) KIEM DIEU KIEN TRUOC KHI PHA. Thieu MySQL80 / .venv / caddy.exe / CA noi bo /
REM      khoa cau noi / venv cua KHBL thi TURN_ON se that bai - ma luc do he da bi tat
REM      va luoi an toan cung tat theo. Quay cam do dung han. Nen phai hoi TRUOC.
REM   2) TAT KHONG SACH THI KHONG BAT LAI. Con tien trinh cu giu cong 8201 thi
REM      start.ps1 thay "dung chu so huu" nen BO QUA - ma .py CU van chay tiep va
REM      khong ai bao loi. Doi ma xong tuong da chay, that ra khong.
REM   3) BAT LAI THAT BAI THI PHAI NOI RO HE DANG TAT, va go co host.stop de luoi an
REM      toan con co co hoi tu cuu, thay vi im lang de he nam chet.
REM
REM  Goi qua PowerShell:  cmd /c D:\PYTHON\KHCD\RESET_KHCD.bat
REM ============================================================
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "TASKS=%SystemRoot%\System32\schtasks.exe"

REM --- 1) Hoi truoc khi pha ---
call "%~dp0TURN_ON_KHCD.bat" --kiem
if not "%errorlevel%"=="0" (
    echo [KHCD] DUNG LAI: chua du dieu kien de bat lai nen KHONG tat gi ca - trang thai
    echo [KHCD]   hien tai giu nguyen. Xem dong LOI o tren de biet thieu gi.
    exit /b 1
)

REM --- 2) Tat ---
call "%~dp0TURN_OFF_KHCD.bat"
REM     Dung "if errorlevel 1": no chi dung voi ma DUONG, con ma AM thi cho FALSE
REM     (da do that: exit /b -1 lot qua "if errorlevel 1"). PowerShell tra ma am duoc.
if not "%errorlevel%"=="0" goto loi_tat

ping -n 4 127.0.0.1 >nul

REM --- 3) Bat lai ---
call "%~dp0TURN_ON_KHCD.bat"
if not "%errorlevel%"=="0" goto loi_bat
exit /b 0

:loi_tat
echo [KHCD] LOI: tat khong sach nen KHONG bat lai - tranh chay tiep ma .py CU.
echo [KHCD]   ^(TURN_OFF da go co host.stop va cho tac vu chay lai neu con tac vu.^)
exit /b 1

:loi_bat
echo [KHCD] LOI NANG: da tat xong nhung BAT LAI KHONG DUOC - KHCD DANG TAT, quay cam do
echo [KHCD]   khong dung duoc. Xem instance\server-error.log va instance\caddy-error.log.
if exist "instance\host.stop" del /q "instance\host.stop" >nul 2>&1
%TASKS% /Run /TN "KHCD Web Host" >nul 2>&1
echo [KHCD]   Da go co host.stop va cho tac vu giam sat chay lai de no tu thu bat moi 15 giay.
exit /b 1
