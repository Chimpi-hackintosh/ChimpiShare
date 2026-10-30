$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
if (-not [Environment]::Is64BitOperatingSystem) { throw "This build targets Windows x64" }
py -3 -m venv .venv-build
if ($LASTEXITCODE -ne 0) { throw "Python 3 with venv is required on the build computer" }
$buildPython = Join-Path $projectRoot ".venv-build\Scripts\python.exe"
& $buildPython -c "import platform, struct; assert struct.calcsize('P') == 8 and platform.machine().lower() in ('amd64', 'x86_64'), 'Use x64 Python'"
if ($LASTEXITCODE -ne 0) { throw "Use 64-bit Python" }
& $buildPython scripts/install_build_dependencies.py
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
& $buildPython scripts/build_native.py
if ($LASTEXITCODE -ne 0) { throw "Application build failed" }
$nsisCommand = Get-Command makensis.exe -ErrorAction SilentlyContinue
if ($nsisCommand) { $nsisPath = $nsisCommand.Source }
else { $nsisPath = Join-Path ${env:ProgramFiles(x86)} "NSIS\makensis.exe" }
if (-not (Test-Path $nsisPath)) {
    Write-Host 'Portable app built at dist\ChimpiShare; install NSIS 3 and run makensis (Resolve-Path packaging\installer.nsi).Path to generate setup'
    exit 0
}
& $nsisPath (Resolve-Path 'packaging/installer.nsi').Path
if ($LASTEXITCODE -ne 0) { throw "Installer build failed" }
