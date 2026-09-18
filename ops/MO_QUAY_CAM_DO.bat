@echo off
REM MO_QUAY_CAM_DO.bat - Mo quay CAM DO trong mot tien trinh Edge RIENG (khong co --kiosk-printing).
REM Ly do: --kiosk-printing la co CUA CA TIEN TRINH Edge -> in thang ra may in MAC DINH cua Windows (LBP6230dn).
REM   BAN LE van chay Edge kiosk nhu cu (in thang LBP). CAM DO chay Edge rieng: bam IN PHIEU -> hop thoai in
REM   hien ra, Edge tu nho MAY IN DUNG LAN TRUOC cua ho so nay -> lan dau chon "HP Laser CAM DO", tu lan sau
REM   chi can bam ENTER la in. Khong bao gio dung lan voi Ban le vi hai ho so Edge tach biet.
REM Chep tep nay ra Desktop may quay (PC KK). Sua dia chi ben duoi neu can (localhost / tiemvangkimhanh2).
set "URL=https://tiemvangkimhanh2:8200/camdo/lap-phieu"
set "DATA=%LOCALAPPDATA%\KHCD_Edge"
if not exist "%DATA%" mkdir "%DATA%"
start "" msedge --user-data-dir="%DATA%" --no-first-run --no-default-browser-check --app=%URL%
