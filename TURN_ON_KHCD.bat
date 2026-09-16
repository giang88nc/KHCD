@echo off
REM ============================================================
REM  TURN_ON_KHCD.bat - Bat he thong KHCD (Cam do) - 16/09/2026
REM    Cong 8200 HTTPS : Caddy (ops\caddy\Caddyfile) chuyen tiep sang
REM    Cong 8201       : waitress chay run.py (CHI loopback, khong nghe LAN)
REM    Cong 18202      : cau noi khach hang = manage.py run_customer_bridge CUA KHBL,
REM                      do KHCD bat va KHCD tat (KHBL khong quan ly tien trinh nay)
REM    Luoi an toan    : tac vu Windows "KHCD Web Host" -> scripts\host.ps1,
REM                      15s/lan goi /health, hong thi tu bat lai
REM
REM  KHONG VIET LAI LOGIC BAT O DAY. Logic nam trong scripts\start.ps1 (no kiem tra
REM  CHU SO HUU tung cong truoc khi dung toi tien trinh nao). Tep .bat nay la CUA VAO
REM  quen thuoc giong KHJ/KHBL, lam them 5 viec ma .ps1 khong lam:
REM    1) Cho dich vu MySQL80 chay (KHCD dung DB khj_cd @3308) roi moi bat
REM    2) Kiem DU dieu kien can, ke ca hai thu cua NGUOI KHAC ma start.ps1 doi truoc
REM       tien: khoa instance\customer-bridge.key va venv cua KHBL. Thieu mot trong
REM       hai la start.ps1 nem loi TRUOC khi kip bat web -> quay cam do dung han.
REM    3) Kiem tac vu CO THAT hay khong (dung tin moi tep danh dau) va co duong LUI:
REM       tac vu hong/bi tat -> bat truc tiep qua WMI Win32_Process.Create, de tien
REM       trinh KHONG nam trong Job Object cua app goi lenh (bai hoc 15/09/2026: goi
REM       tu app Claude roi dong app la ca tiem sap)
REM    4) TU DO LAI suc khoe that - hoi CA cong 8200 (va hoi AI dang giu no) LAN cong
REM       8201, vi Caddy van giu 8200 khi backend da chet, luc do moi trang tra 502
REM    5) Bao dung/sai bang ma thoat 0/1 cho RESET_KHCD.bat dua vao
REM
REM  Tham so --kiem : CHI kiem dieu kien can roi thoat, KHONG bat gi, KHONG xoa co
REM                   host.stop. RESET goi truoc khi dam tat he thong.
REM
REM  Goi lai bao nhieu lan cung AN TOAN. KHONG goi tu Git Bash.
REM  Goi qua PowerShell:  cmd /c D:\PYTHON\KHCD\TURN_ON_KHCD.bat
REM ============================================================
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

REM Duong dan TUYET DOI cho lenh he thong: goi tu Git Bash thi PATH co /usr/bin dung
REM truoc, "find" se la find.exe cua Git va tra ket qua NGUOC (da do that: MySQL80
REM dang RUNNING ma van bao khong chay). Bai hoc nay CLAUDE.md muc 10 da ghi.
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "SC=%SystemRoot%\System32\sc.exe"
set "TIM=%SystemRoot%\System32\findstr.exe"
set "TASKS=%SystemRoot%\System32\schtasks.exe"

call :tien_de
if not "%errorlevel%"=="0" exit /b 1
if /i "%~1"=="--kiem" (
    echo [KHCD] Du dieu kien de bat.
    exit /b 0
)

REM --- Xoa co "dung day" NGAY TU DAU, truoc moi duong thoat ---
REM     TURN_OFF de lai instance\host.stop de luoi an toan khong bat lai. Neu xoa no
REM     muon (chi trong nhanh tac vu nhu ban dau) thi moi lan bat that bai giua chung
REM     se de co nam lai -> lan sau tac vu chay len roi tu thoat ngay, khong ai hieu vi sao.
if exist "instance\host.stop" del /q "instance\host.stop" >nul 2>&1

REM --- Chon duong bat ---
%TASKS% /Query /TN "KHCD Web Host" >nul 2>&1
if not "%errorlevel%"=="0" goto thieu_tac_vu
if not exist "instance\windows-host.enabled" goto thieu_danh_dau
goto bat_tac_vu

:thieu_tac_vu
echo [KHCD] CANH BAO: KHONG thay tac vu Windows "KHCD Web Host" - mat luoi tu phuc hoi 15s.
echo [KHCD]   Cai lai 1 lan ^(hien cua so UAC, bam YES^):
echo [KHCD]   powershell -ExecutionPolicy Bypass -File "%ROOT%\scripts\install-windows-host.ps1"
goto bat_truc_tiep

:thieu_danh_dau
REM     Tac vu CO THAT ma thieu tep danh dau: start.ps1 se di nhanh -Direct, con
REM     TURN_OFF thi VAN /End tac vu -> bat doi xung, RESET lam mat luoi an toan.
REM     Viet lai tep danh dau roi di duong tac vu cho khop hai ben.
echo [KHCD] CANH BAO: co tac vu nhung thieu tep instance\windows-host.enabled - viet lai.
echo KHCD Web Host> "instance\windows-host.enabled"
goto bat_tac_vu

:bat_tac_vu
echo [KHCD] Bat qua tac vu Windows "KHCD Web Host"...
%PS% -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\start.ps1"
if "%errorlevel%"=="0" goto do_suc_khoe
REM     start.ps1 bao loi KHONG chac la he hong: nguong "da len" cua no doi ca cau noi
REM     18202 san sang trong 10 giay, ma cau noi la mot lenh Django cua KHBL, rieng no
REM     khoi dong da vai giay. Do nhanh mot luot; van chua len that thi moi lui ve
REM     duong truc tiep (tac vu co the dang bi Disabled hoac dang ky hong).
echo [KHCD] LUU Y: start.ps1 bao chua san sang - do nhanh mot luot truoc khi ket luan.
%PS% -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\kiem_khcd.ps1" -Viec suc-khoe -ChoGiay 5
if "%errorlevel%"=="0" goto xong
if "%errorlevel%"=="2" goto xong_co_canh_bao
echo [KHCD] Tac vu khong dua he len duoc - LUI VE bat truc tiep.
goto bat_truc_tiep

:bat_truc_tiep
echo [KHCD] Bat truc tiep, TACH khoi tien trinh goi de khong chet theo...
%PS% -NoProfile -Command "$a=@{CommandLine='\"%PS%\" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%ROOT%\scripts\start.ps1\" -Direct'; CurrentDirectory='%ROOT%'}; try { $r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments $a -ErrorAction Stop } catch { Write-Host ('[KHCD] LOI WMI: ' + $_.Exception.Message); exit 1 }; if (-not $r) { Write-Host '[KHCD] LOI: WMI khong tra ket qua nao.'; exit 1 }; if ($r.ReturnValue -ne 0) { Write-Host ('[KHCD] LOI: WMI tu choi tao tien trinh, ma ' + $r.ReturnValue); exit 1 }; exit 0"
if not "%errorlevel%"=="0" (
    echo [KHCD] LOI: khong tao duoc tien trinh nen - xem dong bao loi o tren.
    exit /b 1
)
goto do_suc_khoe

:do_suc_khoe
REM     Vong cho nam GON trong MOT tien trinh powershell -> dung thoi gian nhu ghi o day,
REM     khong phai bat lai powershell 15 lan nhu ban dau (moi lan ton them ~1 giay).
%PS% -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\kiem_khcd.ps1" -Viec suc-khoe -ChoGiay 45
if "%errorlevel%"=="0" goto xong
if "%errorlevel%"=="2" goto xong_co_canh_bao
echo [KHCD] LOI: KHCD chua phuc vu duoc sau 45 giay.
echo [KHCD]   Xem: instance\server-error.log, instance\caddy-error.log, instance\host.log
exit /b 1

:xong_co_canh_bao
echo [KHCD] HOAN TAT ^(kem canh bao o tren^): https://tiemvangkimhanh2:8200
goto nhac_nho

:xong
echo [KHCD] HOAN TAT: https://tiemvangkimhanh2:8200 ^| https://localhost:8200
goto nhac_nho

:nhac_nho
REM     Hai loi nhac, deu la trang thai "van chay nhung mat luoi an toan":
REM      - tac vu khong o trang thai Running -> khong con ai tu bat lai khi tien trinh chet
REM      - KHCD khong co DUONG LEN NAO khi may khoi dong lai. KHCD co hai duong len co the
REM        co: (1) tac vu "KHCD Web Host" co trigger luc boot/dang nhap, (2) chuoi
REM        KHOI_DONG_TOAN_HE_THONG.bat ben KHJ goi TURN_ON_KHCD.bat. Chi nhac khi CA HAI
REM        deu khong co - con mot duong la du. (16/09/2026 da them duong (2).)
REM     BAY: @($t.Triggers).Count tra 1 khi Triggers la $null (mang mot phan tu rong)
REM     nen phai dung Measure-Object.
set "CO_CHUOI=0"
%TIM% /I /L /C:"TURN_ON_KHCD.bat" "D:\PYTHON\KHJ\KHOI_DONG_TOAN_HE_THONG.bat" >nul 2>&1
if "%errorlevel%"=="0" set "CO_CHUOI=1"
%PS% -NoProfile -Command "$t=Get-ScheduledTask -TaskName 'KHCD Web Host' -ErrorAction SilentlyContinue; if (-not $t) { exit 0 }; if ($t.State -ne 'Running') { Write-Host '[KHCD] LUU Y: tac vu KHCD Web Host KHONG o trang thai Running - mat luoi tu phuc hoi 15 giay.' }; if (($t.Triggers | Measure-Object).Count -eq 0) { exit 3 }; exit 0"
if not "%errorlevel%"=="3" goto het
if "%CO_CHUOI%"=="1" goto het
echo [KHCD] LUU Y: tac vu "KHCD Web Host" khong co trigger, va KHOI_DONG_TOAN_HE_THONG.bat
echo [KHCD]   cung khong goi KHCD -^> khoi dong lai may thi KHCD KHONG tu len.
:het
exit /b 0

REM ------------------------------------------------------------
:tien_de
if not exist ".venv\Scripts\python.exe" (
    echo [KHCD] LOI: thieu .venv\Scripts\python.exe - chua tao moi truong ao?
    exit /b 1
)
if not exist "ops\caddy\caddy.exe" (
    echo [KHCD] LOI: thieu ops\caddy\caddy.exe - chep tu D:\PYTHON\KIMHANH\ops\caddy\caddy.exe
    exit /b 1
)
if not exist "ops\caddy\Caddyfile" (
    echo [KHCD] LOI: thieu ops\caddy\Caddyfile - Caddy khong biet phuc vu ten mien nao.
    exit /b 1
)
if not exist "instance\caddy-data\pki\authorities\local\root.key" (
    echo [KHCD] LOI: thieu CA noi bo trong instance\caddy-data - HTTPS 8200 khong len duoc.
    exit /b 1
)
REM Hai thu duoi day la CUA NGUOI KHAC nhung start.ps1 doi TRUOC KHI bat web: thieu la
REM no nem loi ngay o khuc cau noi, web cam do khong bao gio duoc bat. Hoi o day de
REM RESET biet ma KHONG tat he thong dang chay.
if not exist "instance\customer-bridge.key" (
    echo [KHCD] LOI: thieu instance\customer-bridge.key - start.ps1 se dung o khuc cau noi
    echo [KHCD]   va web cam do khong duoc bat. Phuc hoi khoa nay truoc ^(thu muc instance
    echo [KHCD]   nam trong .gitignore nen lay tu ban sao luu C:\KHJ_BACKUP^).
    exit /b 1
)
if not exist "D:\PYTHON\KHBL\venv\Scripts\python.exe" (
    echo [KHCD] LOI: khong thay D:\PYTHON\KHBL\venv\Scripts\python.exe - cau noi khach hang
    echo [KHCD]   chay bang venv cua KHBL. KHBL doi cho venv thi phai sua scripts\start.ps1.
    exit /b 1
)
REM 12 vong x 5 giay = cho toi da khoang 60 giay cho dich vu MySQL80
set /a LAN=0
:cho_mysql
%SC% query MySQL80 | %TIM% /C:"RUNNING" >nul 2>&1
if "%errorlevel%"=="0" exit /b 0
set /a LAN+=1
if %LAN% geq 12 (
    echo [KHCD] LOI: MySQL80 khong chay sau khoang 60 giay. Huy bat he thong.
    exit /b 1
)
ping -n 6 127.0.0.1 >nul
goto cho_mysql
