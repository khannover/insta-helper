param(
    [switch]$InstallPyInstaller
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    if ($InstallPyInstaller) {
        python -m pip install pyinstaller
    } else {
        throw 'PyInstaller is not installed. Run: python -m pip install pyinstaller'
    }
}

$ffmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
if ($ffmpeg) {
    New-Item -ItemType Directory -Force "$PSScriptRoot\bin" | Out-Null
    Copy-Item $ffmpeg.Source "$PSScriptRoot\bin\ffmpeg.exe" -Force
}

pyinstaller --noconfirm "$PSScriptRoot\insta_helper.spec"