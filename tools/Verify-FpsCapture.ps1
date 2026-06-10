param(
    [int]$Seconds = 5,
    [int]$Fps = 120
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PresentMon = "C:\Program Files\Intel\PresentMon\PresentMonConsoleApplication\PresentMon-2.4.1-x64.exe"
$TestApp = Join-Path $Root "dist\FpsWireTest.exe"
$Output = Join-Path $Root "dist\fps-capture-verify.csv"
$Python = "C:\Users\KDLEA\AppData\Local\Programs\Python\Python311\python.exe"

if (!(Test-Path $PresentMon)) {
    Write-Error "PresentMon console app not found: $PresentMon"
}
if (!(Test-Path $TestApp)) {
    Write-Error "FpsWireTest.exe not found. Build it with: python -m PyInstaller .\FpsWireTest.spec --noconfirm"
}

Remove-Item $Output -ErrorAction SilentlyContinue
$app = Start-Process -FilePath $TestApp -ArgumentList @("--seconds", ($Seconds + 8), "--fps", $Fps) -WorkingDirectory $Root -PassThru
try {
    Start-Sleep -Seconds 3
    & $PresentMon --output_file $Output --session_name SystemGaugesPowerShellVerify --timed $Seconds --terminate_after_timed | Out-Host
    if (!(Test-Path $Output)) {
        Write-Error "PresentMon did not create $Output"
    }

    $script = @"
import pathlib, sys
sys.path.insert(0, r"$Root")
import monitor
text = pathlib.Path(r"$Output").read_text(encoding="utf-8", errors="ignore")
reading = monitor.parse_presentmon_fps(text)
if not reading:
    raise SystemExit("FAIL: CSV was written but no FPS rows parsed")
print(f"PASS: {reading['application']} {reading['fps']:.1f} FPS over {reading['frames']} frames")
"@
    $script | & $Python -
}
finally {
    if ($app -and !$app.HasExited) {
        Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue
    }
    Get-Process | Where-Object { $_.ProcessName -like "*FpsWireTest*" } | Stop-Process -Force -ErrorAction SilentlyContinue
}
