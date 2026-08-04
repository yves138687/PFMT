#requires -Version 7.0

param(
    [string]$EnvName = 'pfmt-py312',
    [switch]$SkipBackend,
    [switch]$SkipWeb,
    [switch]$IncludeE2E,
    [switch]$SkipInstall
)

. "$PSScriptRoot\pfmt-dev-common.ps1"

$root = Get-PfmtRoot
$failureCount = 0

function Invoke-PfmtTestStep {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][scriptblock]$Action
    )

    Write-PfmtInfo $Name
    try {
        & $Action
        Write-PfmtOk "$Name 通过"
    }
    catch {
        $script:failureCount += 1
        Write-PfmtWarn "$Name 失败：$($_.Exception.Message)"
    }
}

# 先跑静态自检，保证合同、示例配置和脚本入口没有漂移。
Invoke-PfmtTestStep -Name '阶段一静态自检' -Action {
    & (Join-Path $PSScriptRoot 'self_check.ps1') -StaticOnly -WarnOnly
}

if (-not (Test-PfmtCondaEnv -EnvName $EnvName)) {
    throw "未找到 conda 环境 $EnvName。请先运行：pwsh ./scripts/dev/bootstrap_dev.ps1"
}

$topLevelTests = @(
    Get-ChildItem -LiteralPath (Join-Path $root 'tests') -Recurse -File -Filter 'test_*.py' -ErrorAction SilentlyContinue
)

if ($topLevelTests.Count -gt 0) {
    Invoke-PfmtTestStep -Name '顶层测试与合同校验' -Action {
        Invoke-PfmtCondaRun -EnvName $EnvName -Command @('python', '-m', 'pytest', 'tests') -WorkingDirectory $root
    }
}
else {
    Write-PfmtWarn '未发现顶层 pytest 用例，已跳过 tests/。'
}

if (-not $SkipBackend) {
    $serverTestDir = Join-Path $root 'server\tests'
    $serverTests = @(
        Get-ChildItem -LiteralPath $serverTestDir -Recurse -File -Filter 'test_*.py' -ErrorAction SilentlyContinue
    )

    if ($serverTests.Count -gt 0) {
        Invoke-PfmtTestStep -Name '后端 pytest' -Action {
            Invoke-PfmtCondaRun -EnvName $EnvName -Command @('python', '-m', 'pytest') -WorkingDirectory (Join-Path $root 'server')
        }
    }
    else {
        Write-PfmtWarn 'server/tests 暂无 pytest 用例，已跳过后端测试。'
    }
}

if (-not $SkipWeb) {
    $webDir = Join-Path $root 'web'
    $packageJson = Join-Path $webDir 'package.json'

    if (Test-Path -LiteralPath $packageJson) {
        if ($null -eq (Get-Command npm -ErrorAction SilentlyContinue)) {
            Write-PfmtWarn '未找到 npm，已跳过前端测试。'
        }
        else {
            if (-not $SkipInstall) {
                $vitestCommand = Join-Path $webDir 'node_modules\.bin\vitest.cmd'
                if (Test-Path -LiteralPath $vitestCommand) {
                    Write-PfmtOk '已检测到前端测试依赖，跳过 npm install。'
                }
                else {
                    Invoke-PfmtTestStep -Name '前端依赖安装' -Action {
                        if (Test-Path -LiteralPath (Join-Path $webDir 'node_modules\.pnpm')) {
                            throw "检测到 pnpm 结构的 web\node_modules，但未找到 Vitest。请清理 web\node_modules 后再用 npm 重新安装。"
                        }
                        Invoke-PfmtNative -Command 'npm' -Arguments @('install') -WorkingDirectory $webDir
                    }
                }
            }

            $package = Get-Content -Raw -LiteralPath $packageJson | ConvertFrom-Json
            $scriptNames = @()
            if ($null -ne $package.scripts) {
                $scriptNames = @($package.scripts.PSObject.Properties.Name)
            }

            if ($scriptNames -contains 'test') {
                Invoke-PfmtTestStep -Name '前端 test 脚本' -Action {
                    Invoke-PfmtNative -Command 'npm' -Arguments @('test') -WorkingDirectory $webDir
                }
            }
            elseif ($scriptNames -contains 'test:unit') {
                Invoke-PfmtTestStep -Name '前端 test:unit 脚本' -Action {
                    Invoke-PfmtNative -Command 'npm' -Arguments @('run', 'test:unit') -WorkingDirectory $webDir
                }
            }
            else {
                Write-PfmtWarn 'web/package.json 未声明 test 或 test:unit，已跳过前端单元测试。'
            }

            if ($IncludeE2E) {
                if ($scriptNames -contains 'test:e2e') {
                    Invoke-PfmtTestStep -Name '前端端到端测试' -Action {
                        Invoke-PfmtNative -Command 'npm' -Arguments @('run', 'test:e2e') -WorkingDirectory $webDir
                    }
                }
                else {
                    Write-PfmtWarn '未声明 test:e2e，已跳过端到端测试。'
                }
            }
        }
    }
    else {
        Write-PfmtWarn 'web/package.json 尚未生成，已跳过前端测试。'
    }
}

if ($failureCount -gt 0) {
    throw "测试流程存在失败步骤：$failureCount"
}

Write-PfmtOk '统一测试流程完成。'
