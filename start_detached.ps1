# Detached TARS Launcher via Windows WMI
# Spawns TARS completely outside any IDE / Antigravity Job Object.
# TARS will continue running even after Antigravity is closed!

Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "      🚀 LAUNCHING TARS AS DETACHED WINDOWS BACKGROUND SERVICE" -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host ""

$workDir = "C:\Users\Lenovo\OneDrive\ドキュメント\n8n prjects"
$pythonExe = "C:\Users\Lenovo\AppData\Local\Programs\Python\Python313\python.exe"
$supervisorScript = "$workDir\tars_supervisor.py"

# 1. Kill any existing TARS processes
Write-Host "1. Clearing any existing TARS processes..." -ForegroundColor Yellow
Get-Process python*, pythonw* -ErrorAction SilentlyContinue | Where-Object { 
    $_.CommandLine -like "*tars*" -or $_.CommandLine -like "*call_server*" 
} | Stop-Process -Force -ErrorAction SilentlyContinue

Start-Sleep -Seconds 1

# 2. Spawn via WMI (Parent will be WmiPrvSE.exe - 100% detached from Antigravity)
Write-Host "2. Spawning TARS Supervisor under Windows WMI..." -ForegroundColor Yellow
$cmdLine = "`"$pythonExe`" `"$supervisorScript`""
$result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $cmdLine
    CurrentDirectory = $workDir
}

if ($result.ReturnValue -ne 0) {
    Write-Host "❌ Failed to spawn process via WMI. Error code: $($result.ReturnValue)" -ForegroundColor Red
    exit 1
}

$newPid = $result.ProcessId
Write-Host "✅ TARS Supervisor spawned successfully with PID: $newPid (Parent: WmiPrvSE.exe)" -ForegroundColor Green
Write-Host "3. Waiting 10 seconds for SIP registration..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# 4. Check active ports
Write-Host "4. Verifying active ports (8080 & 5060)..." -ForegroundColor Yellow
$ports = netstat -ano | findstr ":8080 :5060"
if ($ports) {
    Write-Host $ports -ForegroundColor Gray
    Write-Host ""
    Write-Host "==============================================================" -ForegroundColor Green
    Write-Host " 🎉 TARS IS RUNNING COMPLETELY DETACHED FROM ANTIGRAVITY!" -ForegroundColor Green
    Write-Host " 🛡️ YOU CAN NOW CLOSE ANTIGRAVITY / THE CHAT WINDOW COMPLETELY!" -ForegroundColor Green
    Write-Host " 👉 TARS WILL KEEP RUNNING IN THE BACKGROUND INDEFINITELY." -ForegroundColor Green
    Write-Host " 📞 DIAL 'suhail_tars' ON LINPHONE ANYTIME!" -ForegroundColor Green
    Write-Host "==============================================================" -ForegroundColor Green
} else {
    Write-Host "⚠️ Ports not detected yet. Check tars_supervisor.log for details." -ForegroundColor DarkYellow
}
