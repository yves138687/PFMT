#requires -Version 7.0

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-PfmtRoot {
    # 从 scripts/dev 回到仓库根目录，避免依赖调用时所在目录。
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
}

function Write-PfmtInfo {
    param([Parameter(Mandatory)][string]$Message)
    Write-Host "[PFMT] $Message" -ForegroundColor Cyan
}

function Write-PfmtOk {
    param([Parameter(Mandatory)][string]$Message)
    Write-Host "[PFMT OK] $Message" -ForegroundColor Green
}

function Write-PfmtWarn {
    param([Parameter(Mandatory)][string]$Message)
    Write-Host "[PFMT WARN] $Message" -ForegroundColor Yellow
}

function Assert-PfmtCommand {
    param(
        [Parameter(Mandatory)][string]$Name,
        [string]$InstallHint = ''
    )

    if ($null -eq (Get-Command $Name -ErrorAction SilentlyContinue)) {
        $message = "未找到命令：$Name。"
        if (-not [string]::IsNullOrWhiteSpace($InstallHint)) {
            $message = "$message $InstallHint"
        }
        throw $message
    }
}

function Test-PfmtCondaEnv {
    param([Parameter(Mandatory)][string]$EnvName)

    Assert-PfmtCommand -Name 'conda' -InstallHint '请先安装 Miniconda/Anaconda，并确保 conda 可被 PowerShell 访问。'
    $jsonText = & conda env list --json
    if ($LASTEXITCODE -ne 0) {
        throw "读取 conda 环境列表失败。"
    }

    $envList = ($jsonText | ConvertFrom-Json).envs
    foreach ($envPath in $envList) {
        if ((Split-Path -Leaf $envPath) -eq $EnvName) {
            return $true
        }
    }
    return $false
}

function Invoke-PfmtCondaRun {
    param(
        [Parameter(Mandatory)][string]$EnvName,
        [Parameter(Mandatory)][string[]]$Command,
        [Parameter(Mandatory)][string]$WorkingDirectory
    )

    Push-Location -LiteralPath $WorkingDirectory
    try {
        & conda run --no-capture-output -n $EnvName @Command
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if ($exitCode -ne 0) {
        throw "命令执行失败，退出码：$exitCode；命令：conda run -n $EnvName $($Command -join ' ')"
    }
}

function Invoke-PfmtNative {
    param(
        [Parameter(Mandatory)][string]$Command,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$WorkingDirectory
    )

    Push-Location -LiteralPath $WorkingDirectory
    try {
        & $Command @Arguments
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if ($exitCode -ne 0) {
        throw "命令执行失败，退出码：$exitCode；命令：$Command $($Arguments -join ' ')"
    }
}

function Import-PfmtDotEnv {
    param([Parameter(Mandatory)][string]$Root)

    $envPath = Join-Path $Root '.env'
    if (-not (Test-Path -LiteralPath $envPath)) {
        return
    }

    # 仅解析 KEY=VALUE 形式，供本地开发脚本使用；复杂生产配置请交给后端配置模块。
    foreach ($line in Get-Content -LiteralPath $envPath) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith('#')) {
            continue
        }

        $parts = $trimmed -split '=', 2
        if ($parts.Count -ne 2) {
            continue
        }

        $key = $parts[0].Trim()
        if ($key -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
            continue
        }

        $value = $parts[1].Trim()
        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        [Environment]::SetEnvironmentVariable($key, $value, 'Process')
    }
}

function Get-PfmtEnvValue {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Default
    )

    $value = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    return $value
}

function Resolve-PfmtPath {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][string]$Path
    )

    $expandedPath = [Environment]::ExpandEnvironmentVariables($Path.Trim())
    if ([System.IO.Path]::IsPathRooted($expandedPath)) {
        return [System.IO.Path]::GetFullPath($expandedPath)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $Root $expandedPath))
}

function Get-PfmtStorageRoot {
    param([Parameter(Mandatory)][string]$Root)

    $rawStorageRoot = Get-PfmtEnvValue -Name 'PFMT_STORAGE_ROOT' -Default './storage'
    return Resolve-PfmtPath -Root $Root -Path $rawStorageRoot
}

function Get-PfmtLanIpAddresses {
    try {
        return @(
            [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
                Where-Object {
                    $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and
                    -not [System.Net.IPAddress]::IsLoopback($_) -and
                    -not $_.ToString().StartsWith('169.254.')
                } |
                ForEach-Object { $_.ToString() } |
                Sort-Object -Unique
        )
    }
    catch {
        return @()
    }
}

function Write-PfmtAccessUrls {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$HostName,
        [Parameter(Mandatory)][int]$Port
    )

    if ($HostName -in @('0.0.0.0', '::', '*')) {
        Write-PfmtInfo ("{0} 本机访问：http://127.0.0.1:{1}" -f $Name, $Port)
        $lanIps = @(Get-PfmtLanIpAddresses)
        foreach ($ip in $lanIps) {
            Write-PfmtInfo ("{0} 局域网访问：http://{1}:{2}" -f $Name, $ip, $Port)
        }
        if ($lanIps.Count -eq 0) {
            Write-PfmtWarn ("未能自动识别局域网 IP，请用 ipconfig 查看本机 IPv4 后访问 http://<IPv4>:{0}" -f $Port)
        }
        return
    }

    Write-PfmtInfo ("{0} 访问地址：http://{1}:{2}" -f $Name, $HostName, $Port)
}
