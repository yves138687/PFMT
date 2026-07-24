#requires -Version 7.0

param(
    [ValidateSet('pnpm', 'npm')]
    [string]$PackageManager = 'pnpm',
    [string]$HostName = '',
    [int]$Port = 0,
    [switch]$SkipInstall
)

. "$PSScriptRoot\pfmt-dev-common.ps1"

$root = Get-PfmtRoot
Import-PfmtDotEnv -Root $root

if ([string]::IsNullOrWhiteSpace($HostName)) {
    $HostName = Get-PfmtEnvValue -Name 'PFMT_WEB_HOST' -Default '127.0.0.1'
}

if ($Port -le 0) {
    $Port = [int](Get-PfmtEnvValue -Name 'PFMT_WEB_PORT' -Default '5173')
}

$webDir = Join-Path $root 'web'
$packageJson = Join-Path $webDir 'package.json'

if (-not (Test-Path -LiteralPath $packageJson)) {
    throw "尚未找到前端入口 web/package.json。主线程初始化 Vue 3 + Vite 后，可直接复用本脚本启动。"
}

if ($PackageManager -eq 'pnpm' -and $null -eq (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    throw "未找到 pnpm。请安装 Node.js 20+ 后执行 corepack enable，或改用 -PackageManager npm。"
}

Assert-PfmtCommand -Name $PackageManager

if (-not $SkipInstall) {
    $installArgs = @('install')
    if ($PackageManager -eq 'pnpm' -and (Test-Path -LiteralPath (Join-Path $webDir 'pnpm-lock.yaml'))) {
        $installArgs += '--frozen-lockfile'
    }

    # 本地启动前校验依赖；CI 可通过 -SkipInstall 交给流水线缓存。
    Write-PfmtInfo "安装或校验前端依赖：$PackageManager $($installArgs -join ' ')"
    Invoke-PfmtNative -Command $PackageManager -Arguments $installArgs -WorkingDirectory $webDir
}

if ($PackageManager -eq 'pnpm') {
    $devArgs = @('dev', '--host', $HostName, '--port', [string]$Port)
}
else {
    $devArgs = @('run', 'dev', '--', '--host', $HostName, '--port', [string]$Port)
}

Write-PfmtInfo "启动前端：http://$HostName`:$Port"
Invoke-PfmtNative -Command $PackageManager -Arguments $devArgs -WorkingDirectory $webDir
