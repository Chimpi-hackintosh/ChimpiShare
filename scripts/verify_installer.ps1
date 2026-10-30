$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$setup = Join-Path $projectRoot 'dist\ChimpiShare-0.1.0-Setup-x64.exe'
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('ChimpiShare-InstallCheck-' + [guid]::NewGuid().ToString('N'))
$installFolder = Join-Path $testRoot 'Installed'
$receivedFolder = Join-Path $testRoot 'Received'
$preferencesFolder = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'SnoopyOS Company\ChimpiShare'
$preferences = Join-Path $preferencesFolder 'settings.json'
New-Item -ItemType Directory -Path $testRoot, $receivedFolder, $preferencesFolder -Force | Out-Null
$existingPreferences = if (Test-Path $preferences) { [IO.File]::ReadAllBytes($preferences) } else { $null }

function Run-Checked($program, $arguments) {
    $process = Start-Process -FilePath $program -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "Process failed with exit code $($process.ExitCode): $program" }
}

try {
    Run-Checked $setup @('/S', "/D=$installFolder")
    $installedApp = Join-Path $installFolder 'ChimpiShare.exe'
    if (-not (Test-Path $installedApp)) { throw 'Installer did not install ChimpiShare.exe' }
    foreach ($localeName in @('pt-BR', 'en')) {
        if (-not (Test-Path (Join-Path $installFolder "locales\$localeName.json"))) { throw 'Installed locale missing' }
    }
    if (Get-ChildItem $installFolder -Recurse -File | Where-Object { $_.Extension -in @('.py', '.pyw') }) {
        throw 'Python source exposed in installed application'
    }
    $settings = @{ language = 'pt-BR'; receive_folder = $receivedFolder } | ConvertTo-Json
    [IO.File]::WriteAllText($preferences, $settings, [Text.UTF8Encoding]::new($false))
    $sentinel = Join-Path $receivedFolder 'preserve-this-file.txt'
    [IO.File]::WriteAllText($sentinel, 'ChimpiShare installer verification')
    $reportFolder = Join-Path $projectRoot 'build\verification'
    Run-Checked $installedApp @('self-test', '--output', (Join-Path $testRoot 'installed-transfer.json'))
    Run-Checked $installedApp @('gui-smoke', '--output', (Join-Path $testRoot 'installed-gui.json'))
    $guiReport = Get-Content (Join-Path $testRoot 'installed-gui.json') -Raw | ConvertFrom-Json
    if ($guiReport.language -ne 'pt-BR') { throw 'Saved Portuguese locale did not take precedence' }
    Run-Checked $setup @('/S')
    if (-not (Test-Path $installedApp)) { throw 'Upgrade did not preserve registered installation directory' }
    if ([IO.File]::ReadAllText($preferences) -ne $settings) { throw 'Upgrade replaced user preferences' }
    $metadata = Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ChimpiShare'
    if ($metadata.DisplayName -ne 'ChimpiShare') { throw 'Uninstall registration missing' }
    Run-Checked (Join-Path $installFolder 'Uninstall.exe') @('/S')
    if (Test-Path $installedApp) { throw 'Uninstaller left the application executable behind' }
    if (-not (Test-Path $sentinel)) { throw 'Uninstaller removed received files' }
    if ([IO.File]::ReadAllText($preferences) -ne $settings) { throw 'Uninstaller removed user preferences' }
    $report = @{ installation = 'passed'; installed_transport = 'passed'; installed_gui_pt_BR = 'passed'; upgrade = 'passed'; uninstall = 'passed'; preferences_preserved = $true; received_files_preserved = $true }
    $report | ConvertTo-Json | Set-Content (Join-Path $reportFolder 'installer-checks.json') -Encoding utf8
    $report | ConvertTo-Json
} finally {
    if ($null -ne $existingPreferences) { [IO.File]::WriteAllBytes($preferences, $existingPreferences) }
    elseif (Test-Path $preferences) { Remove-Item $preferences }
}
