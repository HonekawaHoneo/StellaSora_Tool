#!/usr/bin/env bash
set -euo pipefail

# Linux x86_64, from the official v8.30.1 release checksums (not a moving URL).
version='8.30.1'
checksum='551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb'
repo_root="$(git rev-parse --show-toplevel)"
scan_temp="$(mktemp -d)"
trap 'rm -rf "$scan_temp"' EXIT

curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
  --max-time 120 --retry 3 \
  "https://github.com/gitleaks/gitleaks/releases/download/v${version}/gitleaks_${version}_linux_x64.tar.gz" \
  --output "$scan_temp/gitleaks.tar.gz"
printf '%s  %s\n' "$checksum" "$scan_temp/gitleaks.tar.gz" | sha256sum --check --status
tar -xzf "$scan_temp/gitleaks.tar.gz" -C "$scan_temp" gitleaks

cd "$repo_root"
"$scan_temp/gitleaks" git --log-opts='--all' --redact=100 --no-banner --ignore-gitleaks-allow .
"$scan_temp/gitleaks" dir --redact=100 --no-banner --ignore-gitleaks-allow .
