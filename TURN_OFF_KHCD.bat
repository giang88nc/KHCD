@echo off
REM ============================================================
REM  TURN_OFF_KHCD.bat - Tat he thong KHCD - 16/09/2026
REM    0) Dat co instance\host.stop + ket thuc tac vu "KHCD Web Host" TRUOC
REM       (khong thi luoi an toan 15s sau tu bat lai, y het watchdog KHJ/KHBL).
REM       Lam thang o day chu khong pho mac stop.ps1: stop.ps1 chi lam viec nay khi
REM       CO tep danh dau instance\windows-host.enabled - tep do bi xoa ma tac vu van
REM       chay thi TURN_OFF se bao "da tat" roi 15 giay sau he tu song lai.
REM    1) Tat theo DUNG DONG LENH bang scripts\stop.ps1: waitress run.py (8201),
REM       Caddy cua KHCD (8200), cau noi run_customer_bridge (18202). stop.ps1 doi
REM       chieu CommandLine tung tien trinh nen KHONG BAO GIO kill nham KHBL hay KHJ.
REM    2) DO LAI bang scripts\kiem_khcd.ps1 -Viec chu-cong, va xu theo DUNG ma tra ve:
REM         0 = sach          -> bao da tat
REM         4 = con cua KHCD  -> xin quyen Admin mot lan roi tat not
REM         2 = ung dung KHAC -> DUNG LAI, khong xin UAC, khong giet nham
REM         3 = khong ket luan duoc (khong do noi cong / khong doc noi dong lenh)
REM         khac = chinh tep kiem khong chay duoc -> cung DUNG LAI, khong doan bua
REM    3) MOI duong that bai deu BAT LAI LUOI AN TOAN truoc khi thoat (xoa host.stop,
REM       cho tac vu chay lai). Neu khong, he nam chet ma khong ai bat lai: tat dang
REM       do, GD doc dong "DUNG LAI" roi tuong he van chay, den khi khach toi quay moi biet.
REM
REM  LUU Y: cau noi 18202 chay ma nguon cua KHBL nhung chi phuc vu KHCD va do KHCD bat
REM  len -> tat KHCD la tat luon no. Web/scheduler cua KHBL KHONG bi dung toi.
REM  Sau lenh nay KHCD nam im cho toi khi goi TURN_ON_KHCD.bat (no xoa co host.stop).
REM  Goi qua PowerShell:  cmd /c D:\PYTHON\KHCD\TURN_OFF_KHCD.bat
REM ============================================================
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "TASKS=%SystemRoot%\System32\schtasks.exe"

REM --- 0) Luoi an toan nam im TRUOC khi giet tien trinh ---
set "COTACVU=0"
%TASKS% /Query /TN "KHCD Web Host" >nul 2>&1
if not "%errorlevel%"=="0" goto khong_co_tac_vu
set "COTACVU=1"
if not exist "instance" mkdir "instance"
echo Tat chu dong boi TURN_OFF_KHCD.bat> "instance\host.stop"
echo [KHCD] Dat co instance\host.stop va ket thuc tac vu "KHCD Web Host"...
%TASKS% /End /TN "KHCD Web Host" >nul 2>&1
if not "%errorlevel%"=="0" echo [KHCD] CANH BAO: lenh ket thuc tac vu tra ma loi - giam sat co the con song.
ping -n 3 127.0.0.1 >nul
:khong_co_tac_vu

REM --- 1) Tat dung tien trinh (logic o stop.ps1, khong chep lai o day) ---
%PS% -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\stop.ps1"
if not "%errorlevel%"=="0" echo [KHCD] CANH BAO: stop.ps1 bao loi - phep do ben duoi moi la ket luan.
ping -n 4 127.0.0.1 >nul

REM --- 2) Con ai giu cong khong, va la AI? ---
call :do_cong
if "%CONG%"=="0" (
    echo [KHCD] Da tat he thong KHCD.
    exit /b 0
)
if "%CONG%"=="2" (
    echo [KHCD] DUNG LAI: cong con lai do UNG DUNG KHAC giu, KHONG phai tien trinh KHCD.
    echo [KHCD]   Khong xin quyen Admin, khong giet nham. PID va ten xem o dong tren.
    goto that_bai
)
if "%CONG%"=="3" (
    echo [KHCD] DUNG LAI: khong ket luan duoc ai dang giu cong ^(khong do noi cong, hoac
    echo [KHCD]   tien trinh thuoc tai khoan khac nen bi che dong lenh^).
    echo [KHCD]   Mo PowerShell "Run as administrator" roi chay lai de doc duoc day du.
    goto that_bai
)
if not "%CONG%"=="4" (
    echo [KHCD] DUNG LAI: scripts\kiem_khcd.ps1 khong chay duoc ^(ma %CONG%^) nen chua biet
    echo [KHCD]   con tien trinh nao khong. KHONG doan bua.
    goto that_bai
)

REM --- CONG=4: dung la tien trinh KHCD con song ---
if /i "%~1"=="--elevated" (
    echo [KHCD] LOI: da nang quyen ma van con tien trinh KHCD giu cong - kiem tra tay.
    exit /b 1
)
net session >nul 2>&1
if "%errorlevel%"=="0" (
    echo [KHCD] LOI: dang la Admin ma van con tien trinh KHCD giu cong - kiem tra tay.
    goto that_bai
)
echo [KHCD] Con tien trinh KHCD khong tat duoc - xin quyen Admin ^(cua so UAC, bam YES^)...
%PS% -NoProfile -Command "try { $p=Start-Process -FilePath '%~f0' -ArgumentList '--elevated' -Verb RunAs -Wait -PassThru -ErrorAction Stop; if (-not $p) { exit 1 }; exit $p.ExitCode } catch { Write-Host ('[KHCD] UAC bi tu choi: ' + $_.Exception.Message); exit 1 }"

REM     KHONG tin ma thoat cua nhanh nang quyen: Start-Process -PassThru co luc tra ve
REM     rong, khi do "exit $p.ExitCode" thanh exit 0 va TURN_OFF bao THANH CONG oan -
REM     RESET se bat de len tien trinh cu, ma .py CU chay tiep ma khong ai biet.
REM     Do lai cong moi la su that.
call :do_cong
if "%CONG%"=="0" (
    echo [KHCD] Da tat he thong KHCD.
    exit /b 0
)
echo [KHCD] LOI: van con tien trinh giu cong sau khi nang quyen ^(ma %CONG%^).
goto that_bai

:that_bai
REM     Tat khong xong: KHONG duoc bo he nam chet kem co host.stop. Bat lai luoi an
REM     toan de nhung gi con cuu duoc thi tu song lai, roi noi THANG trang thai.
REM     Ban --elevated khong lam viec nay: no chi la mot buoc con cua ban goi.
if /i "%~1"=="--elevated" exit /b 1
call :moi_lai_luoi
echo [KHCD] TRANG THAI: KHCD dang TAT hoac chi con mot phan - quay cam do co the khong dung duoc.
echo [KHCD]   Xem ai giu cong: powershell -ExecutionPolicy Bypass -File "%ROOT%\scripts\kiem_khcd.ps1" -Viec chu-cong
exit /b 1

REM ------------------------------------------------------------
:do_cong
%PS% -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\kiem_khcd.ps1" -Viec chu-cong
set "CONG=%errorlevel%"
goto :eof

:moi_lai_luoi
if exist "instance\host.stop" del /q "instance\host.stop" >nul 2>&1
if "%COTACVU%"=="1" (
    %TASKS% /Run /TN "KHCD Web Host" >nul 2>&1
    echo [KHCD] Da go co host.stop va cho tac vu "KHCD Web Host" chay lai ^(15s/lan no se thu bat lai^).
) else (
    echo [KHCD] Da go co host.stop. KHONG co tac vu giam sat nen phai bat tay: cmd /c "%ROOT%\TURN_ON_KHCD.bat"
)
goto :eof
