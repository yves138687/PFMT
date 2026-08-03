#requires -Version 7.0

param(
    [string]$EnvName = 'pfmt-py312',
    [switch]$Update,
    [switch]$CreateLocalEnvFile
)

. "$PSScriptRoot\pfmt-dev-common.ps1"

$root = Get-PfmtRoot
Import-PfmtDotEnv -Root $root
$environmentFile = Join-Path $PSScriptRoot 'environment.yml'
$storageRoot = Get-PfmtStorageRoot -Root $root

Write-PfmtInfo "准备 PFMT 本地 Python 3.12 开发环境：$EnvName"

if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw "未找到 conda 环境文件：$environmentFile"
}

if (Test-PfmtCondaEnv -EnvName $EnvName) {
    if ($Update) {
        Write-PfmtInfo "环境已存在，按 environment.yml 更新并清理无用包。"
        & conda env update -n $EnvName -f $environmentFile --prune
        if ($LASTEXITCODE -ne 0) {
            throw "更新 conda 环境失败：$EnvName"
        }
    }
    else {
        Write-PfmtOk "环境已存在：$EnvName。如需同步依赖，请加 -Update。"
    }
}
else {
    Write-PfmtInfo "开始创建 conda 环境；该操作只影响环境 $EnvName。"
    & conda env create -n $EnvName -f $environmentFile
    if ($LASTEXITCODE -ne 0) {
        throw "创建 conda 环境失败：$EnvName"
    }
}

# 开发期目录只存放本地数据库、密文对象、临时文件和预览缓存。
# 存储根目录跟随 PFMT_STORAGE_ROOT；未配置时默认使用仓库下的 storage。
$storageDirs = @(
    '',
    'db',
    'data',
    'tmp',
    'preview',
    'backup',
    'logs',
    'objects'
)

foreach ($relativePath in $storageDirs) {
    $target = if ([string]::IsNullOrWhiteSpace($relativePath)) {
        $storageRoot
    }
    else {
        Join-Path $storageRoot $relativePath
    }

    if (-not (Test-Path -LiteralPath $target)) {
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Write-PfmtOk "已创建目录：$target"
    }
}

if ($CreateLocalEnvFile) {
    $examplePath = Join-Path $root '.env.example'
    $localEnvPath = Join-Path $root '.env'

    if (-not (Test-Path -LiteralPath $examplePath)) {
        throw "未找到 .env.example，无法生成本地 .env。"
    }

    if (Test-Path -LiteralPath $localEnvPath) {
        Write-PfmtWarn ".env 已存在，未覆盖。请确认其中没有真实密钥被提交。"
    }
    else {
        Copy-Item -LiteralPath $examplePath -Destination $localEnvPath
        Write-PfmtWarn "已从 .env.example 生成 .env，请把示例密钥替换为本机开发值。"
    }
}

Write-PfmtOk "开发环境准备完成。"
Write-Host ''
Write-Host '常用命令：'
Write-Host '  scripts\dev\start_all.bat'
Write-Host '  pwsh ./scripts/dev/start_server.ps1'
Write-Host '  pwsh ./scripts/dev/start_web.ps1'
Write-Host '  pwsh ./scripts/dev/run_tests.ps1'
Write-Host '  pwsh ./scripts/dev/self_check.ps1'
