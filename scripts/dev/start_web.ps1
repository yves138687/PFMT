#requires -Version 7.0

param(
    [ValidateSet('pnpm', 'npm')]
    [string]$PackageManager = 'npm',
    [string]$HostName = '',
    [int]$Port = 0,
    [switch]$SkipInstall,
    [switch]$DryRun
)

. "$PSScriptRoot\pfmt-dev-common.ps1"

$root = Get-PfmtRoot
Import-PfmtDotEnv -Root $root

if ([string]::IsNullOrWhiteSpace($HostName)) {
    $HostName = Get-PfmtEnvValue -Name 'PFMT_WEB_HOST' -Default '0.0.0.0'
}

if ($Port -le 0) {
    $Port = [int](Get-PfmtEnvValue -Name 'PFMT_WEB_PORT' -Default '5173')
}

$webDir = Join-Path $root 'web'
$packageJson = Join-Path $webDir 'package.json'

if (-not (Test-Path -LiteralPath $packageJson)) {
    throw "尚未找到前端入口 web/package.json。主线程初始化 Vue 3 + Vite 后，可直接复用本脚本启动。"
}

Set-Location -LiteralPath $webDir
Write-PfmtInfo "前端工作目录：$webDir"
Assert-PfmtCommand -Name $PackageManager

function Test-PfmtWebCommand {
    param([Parameter(Mandatory)][string]$Name)

    return (
        (Test-Path -LiteralPath (Join-Path $webDir "node_modules\.bin\$Name.cmd")) -or
        (Test-Path -LiteralPath (Join-Path $webDir "node_modules\.bin\$Name"))
    )
}

$hasViteCommand = Test-PfmtWebCommand -Name 'vite'

if ($DryRun) {
    $viteStatus = if ($hasViteCommand) { '已存在' } else { '缺失' }
    Write-PfmtInfo "Vite 启动命令：$viteStatus"
    Write-PfmtAccessUrls -Name '前端' -HostName $HostName -Port $Port
    Write-PfmtInfo "前端启动预检完成：$PackageManager"
    exit 0
}

if (-not $SkipInstall) {
    if ($hasViteCommand) {
        Write-PfmtOk '已检测到前端依赖，跳过 npm install。'
    }
    else {
        if ($PackageManager -eq 'npm' -and (Test-Path -LiteralPath (Join-Path $webDir 'node_modules\.pnpm'))) {
            throw "检测到 pnpm 结构的 web\node_modules，但未找到 Vite 启动命令。请清理 web\node_modules 后再用 npm 重新安装。"
        }

        $installArgs = @('install')
        if ($PackageManager -eq 'pnpm' -and (Test-Path -LiteralPath (Join-Path $webDir 'pnpm-lock.yaml'))) {
            $installArgs += '--frozen-lockfile'
        }

        # 本地启动前校验依赖；CI 可通过 -SkipInstall 交给流水线缓存。
        Write-PfmtInfo "安装前端依赖：$PackageManager $($installArgs -join ' ')"
        Invoke-PfmtNative -Command $PackageManager -Arguments $installArgs -WorkingDirectory $webDir
    }
}

if ($PackageManager -eq 'pnpm') {
    $devArgs = @('dev', '--host', $HostName, '--port', [string]$Port)
}
else {
    $devArgs = @('run', 'dev', '--', '--host', $HostName, '--port', [string]$Port)
}

Write-PfmtAccessUrls -Name '前端' -HostName $HostName -Port $Port
Invoke-PfmtNative -Command $PackageManager -Arguments $devArgs -WorkingDirectory $webDir
