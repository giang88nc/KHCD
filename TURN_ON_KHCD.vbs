' ============================================================
'  TURN_ON_KHCD.vbs - Bat KHCD AN HOAN TOAN (khong cua so, khong taskbar).
'  Chi la vo boc cua TURN_ON_KHCD.bat - MOT cua vao duy nhat, giong KHJ/KHBL.
'
'  Truoc 16/09/2026 tep nay goi THANG scripts\start.ps1, tuc la bo qua:
'    - buoc cho dich vu MySQL80 (bat truoc MySQL thi truy van dau tien loi CSDL)
'    - buoc lui ve bat truc tiep khi tac vu "KHCD Web Host" khong con
'    - buoc tu do lai suc khoe that o CA hai cong 8200 va 8201
'  Ai con go quen tay .vbs nay van duoc bao boc day du.
' ============================================================
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
shell.Run "cmd /c """ & root & "\TURN_ON_KHCD.bat""", 0, False
