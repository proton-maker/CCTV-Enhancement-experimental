# Google Colab helper for CCTV (Windows PowerShell)
# Usage:
#   .\tools\colab\colab.ps1 version
#   .\tools\colab\colab.ps1 new -s cctv --gpu T4
#   .\tools\colab\colab.ps1 sessions

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
& python "$Root\tools\colab\colab_win.py" @args
exit $LASTEXITCODE
