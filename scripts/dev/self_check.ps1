#requires -Version 7.0

param(
    [string]$EnvName = 'pfmt-py312',
    [string]$ApiBaseUrl = '',
    [switch]$RunApi,
    [switch]$StaticOnly,
    [switch]$WarnOnly,
    [string]$Username = '',
    [string]$Password = '',
    [string]$SampleFile = ''
)

. "$PSScriptRoot\pfmt-dev-common.ps1"

$root = Get-PfmtRoot
Import-PfmtDotEnv -Root $root

$failureCount = 0
$warningCount = 0

function Add-PfmtCheckResult {
    param(
        [ValidateSet('PASS', 'WARN', 'FAIL')]
        [string]$Level,
        [Parameter(Mandatory)][string]$Name,
        [string]$Detail = ''
    )

    $color = switch ($Level) {
        'PASS' { 'Green' }
        'WARN' { 'Yellow' }
        default { 'Red' }
    }

    $message = "[$Level] $Name"
    if (-not [string]::IsNullOrWhiteSpace($Detail)) {
        $message = "$message - $Detail"
    }

    Write-Host $message -ForegroundColor $color

    if ($Level -eq 'FAIL') {
        $script:failureCount += 1
    }
    elseif ($Level -eq 'WARN') {
        $script:warningCount += 1
    }
}

function Test-PfmtFileExists {
    param(
        [Parameter(Mandatory)][string]$RelativePath,
        [switch]$Warn
    )

    $target = Join-Path $root $RelativePath
    if (Test-Path -LiteralPath $target) {
        Add-PfmtCheckResult -Level 'PASS' -Name $RelativePath
    }
    elseif ($Warn) {
        Add-PfmtCheckResult -Level 'WARN' -Name $RelativePath -Detail '当前阶段可暂缺，后续业务实现补齐。'
    }
    else {
        Add-PfmtCheckResult -Level 'FAIL' -Name $RelativePath -Detail '缺少必需文件。'
    }
}

Write-PfmtInfo '执行 PFMT 第一阶段静态自检。'

$requiredDocs = @(
    'README.md',
    'docs\Personal_Knowledge_System_Iteration_Plan.md',
    'docs\Personal_Knowledge_System_Project_Structure_Convention.md',
    'docs\Personal_Knowledge_System_Technical_Architecture.md'
)

foreach ($docPath in $requiredDocs) {
    Test-PfmtFileExists -RelativePath $docPath
}

$requiredDevFiles = @(
    '.env.example',
    'scripts\dev\environment.yml',
    'scripts\dev\bootstrap_dev.ps1',
    'scripts\dev\start_server.ps1',
    'scripts\dev\start_web.ps1',
    'scripts\dev\run_tests.ps1',
    'scripts\dev\self_check.ps1',
    'tests\contracts\phase1_api_contract.md',
    'tests\contracts\phase1_api_contract.json',
    'tests\checklists\phase1_self_check.md',
    'tests\fixtures\markdown\phase1_markdown_sample.md'
)

foreach ($filePath in $requiredDevFiles) {
    Test-PfmtFileExists -RelativePath $filePath
}

$environmentPath = Join-Path $root 'scripts\dev\environment.yml'
if (Test-Path -LiteralPath $environmentPath) {
    $environmentText = Get-Content -Raw -LiteralPath $environmentPath
    if ($environmentText -match '(?m)^name:\s*pfmt-py312\s*$' -and $environmentText -match 'python=3\.12') {
        Add-PfmtCheckResult -Level 'PASS' -Name 'conda environment.yml' -Detail '环境名 pfmt-py312，Python 3.12。'
    }
    else {
        Add-PfmtCheckResult -Level 'FAIL' -Name 'conda environment.yml' -Detail '需要固定环境名 pfmt-py312 并使用 Python 3.12。'
    }
}

$envExamplePath = Join-Path $root '.env.example'
if (Test-Path -LiteralPath $envExamplePath) {
    $envExampleText = Get-Content -Raw -LiteralPath $envExamplePath
    $secretPatterns = @(
        'sk-[A-Za-z0-9_-]{20,}',
        'AKIA[0-9A-Z]{16}',
        '-----BEGIN [A-Z ]+PRIVATE KEY-----'
    )

    $matchedSecret = $false
    foreach ($pattern in $secretPatterns) {
        if ($envExampleText -match $pattern) {
            $matchedSecret = $true
            break
        }
    }

    if ($matchedSecret) {
        Add-PfmtCheckResult -Level 'FAIL' -Name '.env.example' -Detail '疑似包含真实密钥格式。'
    }
    else {
        Add-PfmtCheckResult -Level 'PASS' -Name '.env.example' -Detail '未发现常见真实密钥格式。'
    }
}

$contractJsonPath = Join-Path $root 'tests\contracts\phase1_api_contract.json'
if (Test-Path -LiteralPath $contractJsonPath) {
    try {
        $contract = Get-Content -Raw -LiteralPath $contractJsonPath | ConvertFrom-Json
        $scenarioIds = @($contract.scenarios | ForEach-Object { $_.id })
        $requiredScenarioIds = @(
            'login',
            'settings_read',
            'settings_update',
            'tree_read',
            'upload_encrypted_markdown',
            'markdown_view'
        )

        $missingScenarioIds = @($requiredScenarioIds | Where-Object { $scenarioIds -notcontains $_ })
        if ($missingScenarioIds.Count -eq 0) {
            Add-PfmtCheckResult -Level 'PASS' -Name 'phase1_api_contract.json' -Detail '登录、配置、目录树、上传加密、Markdown 查看均已覆盖。'
        }
        else {
            Add-PfmtCheckResult -Level 'FAIL' -Name 'phase1_api_contract.json' -Detail "缺少场景：$($missingScenarioIds -join ', ')"
        }
    }
    catch {
        Add-PfmtCheckResult -Level 'FAIL' -Name 'phase1_api_contract.json' -Detail $_.Exception.Message
    }
}

$storageDirs = @('storage\db', 'storage\data', 'storage\tmp', 'storage\preview', 'storage\backup')
foreach ($storageDir in $storageDirs) {
    $target = Join-Path $root $storageDir
    if (Test-Path -LiteralPath $target) {
        Add-PfmtCheckResult -Level 'PASS' -Name $storageDir
    }
    else {
        Add-PfmtCheckResult -Level 'WARN' -Name $storageDir -Detail '运行 bootstrap_dev.ps1 后会创建。'
    }
}

if ($null -ne (Get-Command conda -ErrorAction SilentlyContinue)) {
    try {
        if (Test-PfmtCondaEnv -EnvName $EnvName) {
            $pythonVersionOutput = & conda run -n $EnvName python --version 2>&1
            if ($LASTEXITCODE -ne 0) {
                Add-PfmtCheckResult -Level 'WARN' -Name "conda env $EnvName" -Detail "Python 版本探测失败：$pythonVersionOutput"
            }
            $pythonVersion = (($pythonVersionOutput | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Select-Object -Last 1).ToString()).Trim()
            if ($pythonVersion -match '^Python 3\.12\.') {
                Add-PfmtCheckResult -Level 'PASS' -Name "conda env $EnvName" -Detail 'Python 3.12 可用。'
            }
            else {
                Add-PfmtCheckResult -Level 'FAIL' -Name "conda env $EnvName" -Detail "当前 Python 版本：$pythonVersion"
            }
        }
        else {
            Add-PfmtCheckResult -Level 'WARN' -Name "conda env $EnvName" -Detail '尚未创建，运行 bootstrap_dev.ps1。'
        }
    }
    catch {
        Add-PfmtCheckResult -Level 'WARN' -Name 'conda 检查' -Detail $_.Exception.Message
    }
}
else {
    Add-PfmtCheckResult -Level 'WARN' -Name 'conda' -Detail '本机未发现 conda 命令。'
}

Test-PfmtFileExists -RelativePath 'server\app\main.py' -Warn
Test-PfmtFileExists -RelativePath 'web\package.json' -Warn

if ($RunApi -and -not $StaticOnly) {
    if ([string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
        $hostName = Get-PfmtEnvValue -Name 'PFMT_SERVER_HOST' -Default '127.0.0.1'
        $port = Get-PfmtEnvValue -Name 'PFMT_SERVER_PORT' -Default '8000'
        $ApiBaseUrl = "http://$hostName`:$port"
    }

    $apiPrefix = Get-PfmtEnvValue -Name 'PFMT_API_PREFIX' -Default '/api'

    function Join-PfmtApiUri {
        param([Parameter(Mandatory)][string]$Path)

        $base = $ApiBaseUrl.TrimEnd('/')
        $prefix = $apiPrefix.TrimEnd('/')
        if ($base -match '/api(/v[0-9]+)?$') {
            return "$base$Path"
        }
        return "$base$prefix$Path"
    }

    if ([string]::IsNullOrWhiteSpace($Username)) {
        $Username = Get-PfmtEnvValue -Name 'PFMT_ADMIN_USERNAME' -Default 'admin'
    }

    if ([string]::IsNullOrWhiteSpace($Password)) {
        $Password = Get-PfmtEnvValue -Name 'PFMT_ADMIN_PASSWORD' -Default 'admin123456'
    }

    if ([string]::IsNullOrWhiteSpace($SampleFile)) {
        $SampleFile = Join-Path $root 'tests\fixtures\markdown\phase1_markdown_sample.md'
    }

    Write-PfmtInfo "执行 API 联调自检：$ApiBaseUrl"

    try {
        $loginBody = @{ username = $Username; password = $Password } | ConvertTo-Json
        $loginResponse = Invoke-RestMethod -Method Post -Uri (Join-PfmtApiUri -Path '/auth/login') -ContentType 'application/json' -Body $loginBody
        $token = $null
        if ($null -ne $loginResponse.access_token) {
            $token = $loginResponse.access_token
        }
        elseif ($null -ne $loginResponse.token) {
            $token = $loginResponse.token
        }

        if ([string]::IsNullOrWhiteSpace($token)) {
            throw '登录响应未返回 access_token 或 token。'
        }

        Add-PfmtCheckResult -Level 'PASS' -Name 'API 登录'
        $headers = @{ Authorization = "Bearer $token" }

        $settingsResponse = Invoke-RestMethod -Method Get -Uri (Join-PfmtApiUri -Path '/settings') -Headers $headers
        if ($null -eq $settingsResponse) {
            throw '配置读取响应为空。'
        }
        Add-PfmtCheckResult -Level 'PASS' -Name 'API 配置读取'

        # 当前后端按单个 setting_key 更新配置，这里逐项覆盖第一阶段核心开关。
        $settingUpdates = @(
            @{
                Key = 'storage.encryption_enabled'
                Body = @{ setting_value = $true; value_type = 'boolean'; group_name = 'storage'; is_public = $true }
            },
            @{
                Key = 'hidden.feature_enabled'
                Body = @{ setting_value = $true; value_type = 'boolean'; group_name = 'hidden'; is_public = $true }
            },
            @{
                Key = 'hidden.show_hidden_default'
                Body = @{ setting_value = $false; value_type = 'boolean'; group_name = 'hidden'; is_public = $false }
            },
            @{
                Key = 'storage.local_root'
                Body = @{ setting_value = './storage'; value_type = 'string'; group_name = 'storage'; is_public = $true }
            }
        )

        foreach ($item in $settingUpdates) {
            $settingsBody = $item.Body | ConvertTo-Json
            Invoke-RestMethod `
                -Method Put `
                -Uri (Join-PfmtApiUri -Path "/settings/$($item.Key)") `
                -Headers $headers `
                -ContentType 'application/json' `
                -Body $settingsBody | Out-Null
        }
        Add-PfmtCheckResult -Level 'PASS' -Name 'API 配置更新'

        $treeResponse = Invoke-RestMethod -Method Get -Uri (Join-PfmtApiUri -Path '/paths/tree') -Headers $headers
        if ($null -eq $treeResponse) {
            throw '目录树响应为空。'
        }
        Add-PfmtCheckResult -Level 'PASS' -Name 'API 目录树'

        $uploadForm = @{
            path_id = 'root'
            encryption_enabled = 'true'
            file = Get-Item -LiteralPath $SampleFile
        }
        $uploadResponse = Invoke-RestMethod -Method Post -Uri (Join-PfmtApiUri -Path '/files/upload') -Headers $headers -Form $uploadForm
        $fileId = $null
        if ($null -ne $uploadResponse.file_id) {
            $fileId = $uploadResponse.file_id
        }
        elseif ($null -ne $uploadResponse.id) {
            $fileId = $uploadResponse.id
        }

        if ([string]::IsNullOrWhiteSpace($fileId)) {
            throw '上传响应未返回 file_id 或 id。'
        }

        if ($null -ne $uploadResponse.storage_object_name -and $uploadResponse.storage_object_name -eq 'phase1_markdown_sample.md') {
            throw '存储对象名不应等于原始文件名。'
        }

        Add-PfmtCheckResult -Level 'PASS' -Name 'API 上传加密'

        $markdownResponse = Invoke-RestMethod -Method Get -Uri (Join-PfmtApiUri -Path "/files/$fileId/markdown") -Headers $headers
        if ($null -eq $markdownResponse) {
            throw 'Markdown 查看响应为空。'
        }
        Add-PfmtCheckResult -Level 'PASS' -Name 'API Markdown 查看'
    }
    catch {
        Add-PfmtCheckResult -Level 'FAIL' -Name 'API 联调自检' -Detail $_.Exception.Message
    }
}

Write-Host ''
Write-PfmtInfo "自检完成：失败 $failureCount，警告 $warningCount。"

if ($failureCount -gt 0 -and -not $WarnOnly) {
    exit 1
}
