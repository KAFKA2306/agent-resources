$ErrorActionPreference = "Stop"

$Version = "8.30.1"
$Root = Join-Path $HOME ".local\gitleaks"
$Hooks = Join-Path $HOME ".git-hooks"
$Tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("gitleaks-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $Root, $Hooks, $Tmp | Out-Null

$Archive = "gitleaks_${Version}_windows_x64.zip"
$Checksums = "gitleaks_${Version}_checksums.txt"
$Base = "https://github.com/gitleaks/gitleaks/releases/download/v${Version}"

Invoke-WebRequest "$Base/$Archive" -OutFile (Join-Path $Tmp $Archive)
Invoke-WebRequest "$Base/$Checksums" -OutFile (Join-Path $Tmp $Checksums)

$ExpectedLine = Get-Content (Join-Path $Tmp $Checksums) | Where-Object { $_ -match [regex]::Escape($Archive) + '$' }
if (-not $ExpectedLine) { throw "Checksum entry not found for $Archive" }
$Expected = ($ExpectedLine -split '\s+')[0].ToLowerInvariant()
$Actual = (Get-FileHash (Join-Path $Tmp $Archive) -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Expected -ne $Actual) { throw "Gitleaks checksum mismatch" }

Expand-Archive -Path (Join-Path $Tmp $Archive) -DestinationPath $Tmp -Force
Copy-Item (Join-Path $Tmp "gitleaks.exe") (Join-Path $Root "gitleaks.exe") -Force

$PreCommit = @'
#!/bin/sh
set -eu
gitleaks_bin="$HOME/.local/gitleaks/gitleaks.exe"
if [ ! -x "$gitleaks_bin" ]; then
  echo "BLOCKED: gitleaks is missing: $gitleaks_bin" >&2
  exit 1
fi
exec "$gitleaks_bin" git --pre-commit --redact --staged --verbose .
'@

$PrePush = @'
#!/bin/sh
set -eu
gitleaks_bin="$HOME/.local/gitleaks/gitleaks.exe"
if [ ! -x "$gitleaks_bin" ]; then
  echo "BLOCKED: gitleaks is missing: $gitleaks_bin" >&2
  exit 1
fi
exec "$gitleaks_bin" git --redact --verbose --log-opts="--all --not --remotes" .
'@

Set-Content -Path (Join-Path $Hooks "pre-commit") -Value $PreCommit -Encoding utf8NoBOM
Set-Content -Path (Join-Path $Hooks "pre-push") -Value $PrePush -Encoding utf8NoBOM
git config --global core.hooksPath $Hooks

Remove-Item -Recurse -Force $Tmp
& (Join-Path $Root "gitleaks.exe") version
Write-Host "Global Gitleaks hooks enabled for commit and push."
