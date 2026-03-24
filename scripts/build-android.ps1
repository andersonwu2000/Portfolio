$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logDir = Join-Path $PSScriptRoot "..\logs"
$logFile = Join-Path $logDir "android_build_$timestamp.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# 確保 JAVA_HOME 設定（Android Studio 內建 JBR）
if (-not $env:JAVA_HOME) {
    $env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
    Write-Host "JAVA_HOME set to: $env:JAVA_HOME" -ForegroundColor Yellow
}

Write-Host "Starting Android debug build..."
Write-Host "Log file: $logFile"

Push-Location (Join-Path $PSScriptRoot "..\apps\mobile\android")
try {
    & .\gradlew.bat assembleDebug 2>&1 | Tee-Object -FilePath $logFile
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n=== BUILD SUCCESSFUL ===" -ForegroundColor Green
        $apk = Get-ChildItem -Recurse -Filter "*.apk" -Path "app\build\outputs" | Select-Object -First 1
        if ($apk) {
            Write-Host "APK: $($apk.FullName)" -ForegroundColor Cyan
            Write-Host "Size: $([math]::Round($apk.Length / 1MB, 2)) MB" -ForegroundColor Cyan
        }
    } else {
        Write-Host "`n=== BUILD FAILED (exit code: $LASTEXITCODE) ===" -ForegroundColor Red
    }
} finally {
    Pop-Location
}
