# =============================================================================
#  kiem_khcd.ps1 - CHI DOC. Khong bat, khong tat, khong giet tien trinh nao.
#  Hai viec cho bo tep van hanh TURN_ON / TURN_OFF / RESET_KHCD.bat.
#
#  NGUYEN TAC XUYEN SUOT: KHONG DOC DUOC thi noi la khong doc duoc, TUYET DOI
#  khong doan. "Khong thay ai giu cong" va "khong do duoc cong" la HAI viec khac
#  nhau; gop lam mot la TURN_OFF bao "da tat sach" trong khi he van dang chay, roi
#  RESET bat de len tien trinh cu - ma .py CU chay tiep ma khong ai biet.
#
#    -Viec suc-khoe [-ChoGiay 45]   Cho toi khi KHCD THUC SU phuc vu duoc.
#        0 = /health tra dung {app:KHCD, https:true} VA cau noi 18202 san sang
#        2 = LEN ROI NHUNG CO CANH BAO. Hai truong hop:
#              . web tot ma cau noi 18202 khong len (tra cuu khach se thieu)
#              . backend 8201 tot + cong 8200 DUNG LA Caddy cua KHCD dang giu,
#                nhung goi qua HTTPS tu may nay khong duoc (may chua tin CA noi bo)
#        1 = chua phuc vu duoc
#      Vi sao phai hoi CA HAI cong: Caddy bind 8200 doc lap voi backend, no van giu
#      cong khi waitress 8201 da chet - luc do moi trang tra 502. Va vi sao phai hoi
#      AI giu 8200 chu khong chi hoi "co ai giu khong": mot ung dung la chiem 8200
#      thi khach KHONG vao duoc, bao "he van phuc vu may khac" la bao doi.
#
#    -Viec chu-cong                 Ai dang giu 8200 / 8201 / 18202?
#        0 = ca 3 cong deu trong VA tien trinh giam sat host.ps1 khong con chay
#        2 = co UNG DUNG KHAC giu cong  -> TUYET DOI khong giet, khong xin UAC
#        3 = KHONG KET LUAN DUOC (khong do duoc cong, hoac khong doc noi thong tin
#            tien trinh - thuong la tien trinh cua tai khoan khac, can quyen Admin)
#        4 = con tien trinh CUA KHCD (hoac giam sat host.ps1) dang song
#      Co y KHONG dung ma 1: chinh powershell.exe tra 1 khi script khong chay duoc
#      (thieu tep, sai tham so, chinh sach chan). Tach ma ra thi .bat phan biet duoc
#      "toi do va con tien trinh" voi "toi khong chay noi".
#
#  Dieu kien nhan dien tien trinh chep tu scripts\stop.ps1 - sua ben do thi sua ca
#  ben nay. Khac mot cho CO Y: dung -like (khong phan biet hoa thuong) thay cho
#  .Contains() cua .NET, vi duong dan lay tu $PSScriptRoot mang nguyen chu hoa/thuong
#  luc goi; go "d:\python\khcd\..." chu thuong la .Contains() truot sach.
# =============================================================================
param(
    [ValidateSet('suc-khoe', 'chu-cong')][string]$Viec = 'suc-khoe',
    [int]$ChoGiay = 45
)
$ErrorActionPreference = 'SilentlyContinue'
$goc = Split-Path -Parent $PSScriptRoot
$duongRun = Join-Path $goc 'run.py'
$duongCaddy = Join-Path $goc 'ops\caddy\caddy.exe'
$cauHinhCaddy = Join-Path $goc 'ops\caddy\Caddyfile'
$khoaCauNoi = Join-Path $goc 'instance\customer-bridge.key'
$duongGiamSat = Join-Path $PSScriptRoot 'host.ps1'

# Tra @{ do_duoc = ?; ds = @(...) }. do_duoc = $false nghia la HOI KHONG DUOC,
# khac han voi ds rong (hoi duoc, khong ai giu).
function Nghe($cong) {
    try {
        $ds = @(Get-NetTCPConnection -LocalPort $cong -State Listen -ErrorAction Stop)
        return @{ do_duoc = $true; ds = $ds }
    }
    catch {
        if ($_.FullyQualifiedErrorId -like 'CmdletizationQuery_NotFound*') {
            return @{ do_duoc = $true; ds = @() }
        }
        return @{ do_duoc = $false; ds = @(); loi = $_.Exception.Message }
    }
}

function LaCuaKhcd($p) {
    if ($p.Name -eq 'python.exe' -and $p.CommandLine) {
        if ($p.CommandLine -like "*$duongRun*") { return $true }
        if ($p.CommandLine -like '*D:\PYTHON\KHBL\manage.py*' -and
            $p.CommandLine -like '*run_customer_bridge*' -and
            $p.CommandLine -like "*$khoaCauNoi*") { return $true }
    }
    if ($p.ExecutablePath -eq $duongCaddy -and $p.CommandLine -like "*$cauHinhCaddy*") { return $true }
    return $false
}

function ChuCong($cong) {
    $n = Nghe $cong
    if (-not $n.do_duoc) { return @{ do_duoc = $false; loi = $n.loi } }
    if ($n.ds.Count -eq 0) { return @{ do_duoc = $true; co = $false; cuaKhcd = $true; chuaRo = $false; dong = @() } }
    $dong = @()
    $cuaKhcd = $true
    $chuaRo = $false
    foreach ($ma in @($n.ds.OwningProcess | Select-Object -Unique)) {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId=$ma" -ErrorAction SilentlyContinue
        if (-not $p) {
            $dong += "PID $ma - khong con nua (co ve vua thoat)"
            continue
        }
        if (-not $p.CommandLine -and -not $p.ExecutablePath) {
            # Thuong la tien trinh cua TAI KHOAN KHAC (vd SYSTEM): Win32_Process van tra
            # ve doi tuong nhung che sach dong lenh. KHONG duoc doan la cua ai.
            $chuaRo = $true
            $dong += ("PID $ma " + $p.Name + "  <== khong doc duoc dong lenh, can quyen Admin moi biet cua ai")
            continue
        }
        if (LaCuaKhcd $p) {
            $dong += ("PID $ma " + $p.Name + "  (cua KHCD)")
        }
        else {
            $cuaKhcd = $false
            $dong += ("PID $ma " + $p.Name + "  <== UNG DUNG KHAC, khong phai KHCD")
        }
    }
    return @{ do_duoc = $true; co = $true; cuaKhcd = $cuaKhcd; chuaRo = $chuaRo; dong = $dong }
}

# Tien trinh giam sat host.ps1: con song la 15 giay nua no bat lai ca he thong,
# nen TURN_OFF khong duoc ket luan "da tat" khi no con day.
function GiamSat() {
    return @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*$duongGiamSat*" })
}

if ($Viec -eq 'chu-cong') {
    $coLa = $false
    $coKhcd = $false
    $khongRo = $false
    foreach ($cong in 8200, 8201, 18202) {
        $k = ChuCong $cong
        if (-not $k.do_duoc) {
            Write-Host ("[KHCD] cong " + $cong + ": KHONG DO DUOC - " + $k.loi)
            $khongRo = $true
            continue
        }
        if (-not $k.co) { Write-Host ("[KHCD] cong " + $cong + ": trong"); continue }
        foreach ($d in $k.dong) { Write-Host ("[KHCD] cong " + $cong + ": " + $d) }
        if ($k.chuaRo) { $khongRo = $true }
        if (-not $k.cuaKhcd) { $coLa = $true }
        elseif (-not $k.chuaRo) { $coKhcd = $true }
    }
    # BAY DA DINH 16/09: chi co MOT tien trinh khop thi PowerShell BOC mang ra thanh
    # doi tuong don, va .Count cua CimInstance tra ve RONG (khong phai 1) -> dieu kien
    # sai, dong bao giam sat khong bao gio hien. Ep ve mang ngay tai cho goi.
    $gs = @(GiamSat)
    if (@($gs).Count -gt 0) {
        foreach ($g in $gs) { Write-Host ("[KHCD] giam sat host.ps1 CON SONG - PID " + $g.ProcessId) }
        $coKhcd = $true
    }
    if ($coLa) { exit 2 }
    if ($khongRo) { exit 3 }
    if ($coKhcd) { exit 4 }
    exit 0
}

# ---------------- che do suc-khoe ----------------
$het = (Get-Date).AddSeconds($ChoGiay)
$webTot = $false
do {
    $backend = $false
    try {
        $h = Invoke-RestMethod 'https://localhost:8200/health' -TimeoutSec 3
        if ($h.app -eq 'KHCD' -and $h.https) {
            if ($h.customer_service -eq 'ok') {
                Write-Host ('[KHCD] /health tra loi tot - kho phieu dang dung: ' + $h.loan_store)
                exit 0
            }
            # Web song nhung cau noi chua len: KHONG ket luan voi - cho het gio da,
            # cau noi la mot lenh Django cua KHBL, rieng no khoi dong da vai giay va
            # luoi an toan cung dang thu bat lai no moi 15 giay.
            $webTot = $true
        }
    }
    catch { }
    try {
        $b = Invoke-RestMethod 'http://127.0.0.1:8201/health' -TimeoutSec 3
        if ($b.app -eq 'KHCD') { $backend = $true }
    }
    catch { }
    if ((Get-Date) -ge $het) { break }
    Start-Sleep -Seconds 2
} while ($true)

if ($webTot) {
    Write-Host '[KHCD] Web cam do 8200 PHUC VU BINH THUONG, nhung cau noi khach hang (cong 18202) KHONG len.'
    Write-Host '[KHCD]   Tra cuu khach se thieu du lieu. Xem instance\bridge-error.log va kiem tra KHBL.'
    Write-Host '[KHCD]   Luoi an toan host.ps1 cung coi day la chua khoe nen se bat lai moi 15 giay.'
    exit 2
}

# Backend do LAN CUOI trong vong lap (khong dung co cu tu 45 giay truoc: waitress
# hay len duoc vai giay roi vo khi nap phai module .py vua sua hong).
$k8200 = ChuCong 8200
if ($backend -and $k8200.do_duoc -and $k8200.co -and $k8200.cuaKhcd -and -not $k8200.chuaRo) {
    Write-Host '[KHCD] Backend 8201 tra loi TOT va cong 8200 DUNG LA Caddy cua KHCD dang giu, nhung goi'
    Write-Host '[KHCD]   https://localhost:8200/health tu MAY NAY thi khong duoc - thuong la may nay chua tin'
    Write-Host '[KHCD]   CA noi bo, he van phuc vu may khac. Mo thu bang trinh duyet de chac chan.'
    exit 2
}
if ($k8200.do_duoc -and $k8200.co -and (-not $k8200.cuaKhcd -or $k8200.chuaRo)) {
    Write-Host '[KHCD] Cong 8200 do NGUOI KHAC giu, Caddy cua KHCD chua len -> khach KHONG vao duoc:'
    foreach ($d in $k8200.dong) { Write-Host ('[KHCD]   ' + $d) }
    exit 1
}
if ($backend) {
    Write-Host '[KHCD] Backend 8201 song nhung KHONG ai giu cong 8200 - Caddy chua len. Xem instance\caddy-error.log'
}
elseif ($k8200.co) {
    Write-Host '[KHCD] Cong 8200 co nguoi giu nhung backend 8201 KHONG tra loi - moi trang se ra loi 502.'
    Write-Host '[KHCD]   Xem instance\server-error.log (thuong la loi trong ma .py vua sua).'
}
else {
    Write-Host '[KHCD] Ca 8200 lan 8201 deu khong phuc vu. Xem instance\server-error.log va instance\caddy-error.log'
}
exit 1
