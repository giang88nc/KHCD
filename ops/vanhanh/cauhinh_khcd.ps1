# ============================================================
#  cauhinh_khcd.ps1 - Cau hinh van hanh KHCD (cam do) cho dong co vanhanh.ps1 (07/10/2026)
#  Cua vao duy nhat: D:\PYTHON\KHCD\RESET_KHCD.bat
#  CONG cua don vi KHCD (RESET_KHCD chi dung toi dung cac cong/tien trinh nay):
#     18202 cau noi khach hang = manage.py run_customer_bridge CUA KHBL (venv KHBL) nhung
#           THUOC KHCD - KHCD bat, KHCD tat; RESET_KHBL khong dung toi
#     8201  web waitress run.py (CHI loopback)     8200  Caddy HTTPS (LAN) -> 8201
#     8219  khoa vong giam sat (thay tac vu "KHCD Web Host" + scripts\host.ps1 cu)
#  Kiem suc khoe that: https://localhost:8200/health phai tra app KHCD + customer_service ok
#  (Caddy van giu 8200 khi backend chet - luc do moi trang 502, chi hoi cong la bao doi).
#  KHCD khong co scheduler.  CHI ky tu ASCII.
# ============================================================
$G = 'D:\PYTHON\KHCD'
$KHBL = 'D:\PYTHON\KHBL'
@{
    Ten          = 'KHCD'
    Goc          = $G
    ThuMucLog    = "$G\instance"
    TacVu        = 'KimHanh2-VanHanh-KHCD'
    CongGiamSat  = 8219
    ChuKyGiamSat = 60
    DichVu       = @('MySQL80')
    TepCan       = @("$G\.venv\Scripts\python.exe", "$G\run.py", "$G\ops\caddy\caddy.exe", "$G\ops\caddy\Caddyfile",
        "$G\instance\caddy-data\pki\authorities\local\root.key", "$G\instance\customer-bridge.key",
        "$KHBL\venv\Scripts\python.exe", "$KHBL\manage.py")
    # Vong giam sat CU (tac vu "KHCD Web Host" -> host.ps1, 15s/lan) phai DUNG HAN truoc khi
    # tat, khong thi no bat lai KHCD ngay sau lung. host.stop = co dung cua host.ps1.
    TruocKhiTat  = {
        Set-Content -LiteralPath 'D:\PYTHON\KHCD\instance\host.stop' -Value 'Dung boi vanhanh.ps1 (07/10/2026)' -ErrorAction SilentlyContinue
        & schtasks.exe /Query /TN 'KHCD Web Host' 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            & schtasks.exe /End /TN 'KHCD Web Host' 2>&1 | Out-Null
            & schtasks.exe /Change /TN 'KHCD Web Host' /DISABLE 2>&1 | Out-Null
        }
    }
    ThanhPhan    = @(
        @{ Ten = 'CauNoi'; Cong = 18202; DauHieu = 'run_customer_bridge'; ThuMuc = $KHBL; ChoGiay = 40
            Lenh = "`"$KHBL\venv\Scripts\python.exe`" -X utf8 `"$KHBL\manage.py`" run_customer_bridge --key-file `"$G\instance\customer-bridge.key`""
            Log = "$G\instance\bridge-out.log"; LogLoi = "$G\instance\bridge-error.log"
            Env = @{ KHCD_ENV_FILE = $null; PYTHONUTF8 = '1' } }
        @{ Ten = 'Web'; Cong = 8201; DauHieu = 'run\.py'; ThuMuc = $G; ChoGiay = 40
            Lenh = "`"$G\.venv\Scripts\python.exe`" -X utf8 `"$G\run.py`""
            Log = "$G\instance\server-out.log"; LogLoi = "$G\instance\server-error.log"
            Env = @{ KHCD_ENV_FILE = $null; PYTHONUTF8 = '1' } }
        @{ Ten = 'Caddy'; Cong = 8200; DauHieu = 'Caddyfile'; ThuMuc = $G; ChoGiay = 20
            Lenh = "`"$G\ops\caddy\caddy.exe`" run --config `"$G\ops\caddy\Caddyfile`" --adapter caddyfile"
            Log = "$G\instance\caddy-out.log"; LogLoi = "$G\instance\caddy-error.log"
            Http = @{ Url = 'https://localhost:8200/health'; Ma = '^200$'; NoiDung = @('"app":\s*"KHCD"', '"customer_service":\s*"ok"') } }
    )
    DonSot       = @(
        @{ Ten = 'host.ps1 cu (KHCD Web Host)'; DauHieu = 'host\.ps1'; CanGoc = $true }
        @{ Ten = 'TURN_ON_KHCD cu'; DauHieu = 'TURN_ON_KHCD' }
        @{ Ten = 'start.ps1 cu'; DauHieu = 'scripts\\start\.ps1'; CanGoc = $true }
    )
}
