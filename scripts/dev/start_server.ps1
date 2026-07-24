#requires -Version 7.0

param(
    [string]$EnvName = 'pfmt-py312',
    [string]$HostName = '',
    [int]$Port = 0,
    [switch]$NoReload
)

. "$PSScriptRoot\pfmt-dev-common.ps1"

$root = Get-PfmtRoot
Import-PfmtDotEnv -Root $root

if ([string]::IsNullOrWhiteSpace($HostName)) {
    $HostName = Get-PfmtEnvValue -Name 'PFMT_SERVER_HOST' -Default '127.0.0.1'
}

if ($Port -le 0) {
    $Port = [int](Get-PfmtEnvValue -Name 'PFMT_SERVER_PORT' -Default '8000')
}

$serverDir = Join-Path $root 'server'
$mainFile = Join-Path $serverDir 'app\main.py'

# 启动前先确认独立 conda 环境存在，避免误用 base 或系统 Python。
if (-not (Test-PfmtCondaEnv -EnvName $EnvName)) {
    throw "未找到 conda 环境 $EnvName。请先运行：pwsh ./scripts/dev/bootstrap_dev.ps1"
}

if (-not (Test-Path -LiteralPath $mainFile)) {
    throw "尚未找到后端入口 server/app/main.py。主线程补齐 FastAPI 业务骨架后，可直接复用本脚本启动。"
}

$uvicornArgs = @(
    'python',
    '-m',
    'uvicorn',
    'app.main:app',
    '--app-dir',
    $serverDir,
    '--host',
    $HostName,
    '--port',
    [string]$Port
)

if (-not $NoReload) {
    $uvicornArgs += '--reload'
}

Write-PfmtInfo "启动后端：http://$HostName`:$Port"
Invoke-PfmtCondaRun -EnvName $EnvName -Command $uvicornArgs -WorkingDirectory $root
