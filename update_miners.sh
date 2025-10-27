#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

mkdir -p "$ROOT_DIR/miners/xmrig" "$ROOT_DIR/miners/cpuminer-opt"

update_xmrig() {
  echo "[i] Updating XMRig..."
  XMRIG_URL=$(curl -sL -H "Accept: application/vnd.github+json" "https://api.github.com/repos/xmrig/xmrig/releases/latest" | jq -r \
    '.assets[] | select(.name | test("linux-(x64|arm64).*\\.tar\\.gz$")) | .browser_download_url' | head -n1 || true)
  if [[ -z "$XMRIG_URL" ]]; then echo "[!] Failed to find XMRig asset" >&2; return 1; fi
  TMPFILE=$(mktemp)
  curl -L "$XMRIG_URL" -o "$TMPFILE"
  rm -rf "$ROOT_DIR/miners/xmrig/*"
  tar -xzf "$TMPFILE" -C "$ROOT_DIR/miners/xmrig" --strip-components=1 || true
  rm -f "$TMPFILE"
  echo "[i] XMRig updated."
}

update_cpuminer() {
  echo "[i] Updating cpuminer-opt..."
  CPUMINER_URL=$(curl -sL -H "Accept: application/vnd.github+json" "https://api.github.com/repos/JayDDee/cpuminer-opt/releases/latest" | jq -r \
    '.assets[] | select(.name | test("linux.*(x86_64|x64).*(tar\\.gz|zip)$")) | .browser_download_url' | head -n1 || true)
  if [[ -z "$CPUMINER_URL" ]]; then echo "[!] Failed to find cpuminer-opt asset" >&2; return 1; fi
  TMPFILE=$(mktemp)
  curl -L "$CPUMINER_URL" -o "$TMPFILE"
  rm -rf "$ROOT_DIR/miners/cpuminer-opt/*"
  if [[ "$CPUMINER_URL" == *.tar.gz ]]; then
    tar -xzf "$TMPFILE" -C "$ROOT_DIR/miners/cpuminer-opt" --strip-components=1 || true
  elif [[ "$CPUMINER_URL" == *.zip ]]; then
    unzip -o "$TMPFILE" -d "$ROOT_DIR/miners/cpuminer-opt"
  else
    install -m 0755 "$TMPFILE" "$ROOT_DIR/miners/cpuminer-opt/cpuminer"
  fi
  rm -f "$TMPFILE"
  echo "[i] cpuminer-opt updated."
}

update_xmrig || true
update_cpuminer || true

echo "[i] Miner update process finished."
