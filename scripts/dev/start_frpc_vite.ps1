#requires -Version 7.0

param(
    [string]$FrpcExe = 'D:\software\frp_0.62.1_windows_amd64\frpc.exe',
    [string]$Config = 'D:\software\frp_0.62.1_windows_amd64\frpc-pfmt-vite.toml'
)

. "$PSScriptRoot\pfmt-dev-common.ps1"

if (-not (Test-Path -LiteralPath $FrpcExe)) {
    Write-PfmtInfo "未找到 frpc.exe，跳过 PFMT FRP 映射：$FrpcExe"
    exit 0
}

if (-not (Test-Path -LiteralPath $Config)) {
    Write-PfmtInfo "未找到 PFMT FRP 配置，跳过 PFMT FRP 映射：$Config"
    exit 0
}

$existing = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -ieq 'frpc.exe' -and
        $_.CommandLine -like "*$Config*"
    } |
    Select-Object -First 1

if ($existing) {
    Write-PfmtOk "PFMT FRP 映射已在运行，PID：$($existing.ProcessId)"
    return
}

Write-PfmtInfo "启动 PFMT FRP Vite 映射：$Config"
& $FrpcExe -c $Config
if ($LASTEXITCODE -ne 0) {
    Write-PfmtInfo "PFMT FRP 映射已退出，退出码：$LASTEXITCODE。本地后端和前端不受影响。"
    exit 0
}
