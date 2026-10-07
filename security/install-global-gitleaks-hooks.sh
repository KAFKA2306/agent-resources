#!/usr/bin/env bash
set -euo pipefail

version="8.30.1"
root="$HOME/.local/bin"
hooks="$HOME/.git-hooks"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$root" "$hooks"
archive="gitleaks_${version}_linux_x64.tar.gz"
checksums="gitleaks_${version}_checksums.txt"
base="https://github.com/gitleaks/gitleaks/releases/download/v${version}"

cd "$tmp"
curl -fsSLO "${base}/${archive}"
curl -fsSLO "${base}/${checksums}"
grep "  ${archive}$" "${checksums}" | sha256sum --check --strict -
tar -xzf "${archive}" gitleaks
install -m 0755 gitleaks "$root/gitleaks"

cat > "$hooks/pre-commit" <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail
gitleaks_bin="$HOME/.local/bin/gitleaks"
if [[ ! -x "$gitleaks_bin" ]]; then
  echo "BLOCKED: gitleaks is missing: $gitleaks_bin" >&2
  exit 1
fi
exec "$gitleaks_bin" git --pre-commit --redact --staged --verbose .
HOOK

cat > "$hooks/pre-push" <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail
gitleaks_bin="$HOME/.local/bin/gitleaks"
if [[ ! -x "$gitleaks_bin" ]]; then
  echo "BLOCKED: gitleaks is missing: $gitleaks_bin" >&2
  exit 1
fi
exec "$gitleaks_bin" git --redact --verbose --log-opts="--all --not --remotes" .
HOOK

chmod 0755 "$hooks/pre-commit" "$hooks/pre-push"
git config --global core.hooksPath "$hooks"
"$root/gitleaks" version
echo "Global Gitleaks hooks enabled for commit and push."
