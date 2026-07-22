# One-time Google auth for Colab CLI (opens browser, paste code back here)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Write-Host ""
Write-Host "A browser URL will appear. Open it, approve access, then paste the authorization code here." -ForegroundColor Cyan
Write-Host ""
& python "$Root\tools\colab\colab_win.py" sessions
if ($LASTEXITCODE -eq 0) {
  Write-Host "Auth OK. Creating GPU session 'cctv' (T4)…" -ForegroundColor Green
  & python "$Root\tools\colab\colab_win.py" new -s cctv --gpu T4
  & python "$Root\tools\colab\colab_win.py" status -s cctv
}
exit $LASTEXITCODE
