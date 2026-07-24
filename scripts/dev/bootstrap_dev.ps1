#requires -Version 7.0

param(
    [string]$EnvName = 'pfmt-py312',
    [switch]$Update,
    [switch]$CreateLocalEnvFile
)

. "$PSScriptRoot\pfmt-dev-common.ps1"

$root = Get-PfmtRoot
$environmentFile = Join-Path $PSScriptRoot 'environment.yml'

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
$storageDirs = @(
    'storage',
    'storage\db',
    'storage\data',
    'storage\tmp',
    'storage\preview',
    'storage\backup',
    'storage\logs'
)

foreach ($relativePath in $storageDirs) {
    $target = Join-Path $root $relativePath
    if (-not (Test-Path -LiteralPath $target)) {
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Write-PfmtOk "已创建目录：$relativePath"
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
Write-Host '  pwsh ./scripts/dev/start_server.ps1'
Write-Host '  pwsh ./scripts/dev/start_web.ps1'
Write-Host '  pwsh ./scripts/dev/run_tests.ps1'
Write-Host '  pwsh ./scripts/dev/self_check.ps1'
