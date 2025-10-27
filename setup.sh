#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "[i] Running non-root. Will use sudo for package installs if needed." >&2
  SUDO="sudo"
else
  SUDO=""
fi

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "[!] This setup script currently supports Linux only." >&2
  exit 1
fi

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) ARCH_TAG="x64" ;;
  aarch64|arm64) ARCH_TAG="arm64" ;;
  *) echo "[!] Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

ensure_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_packages() {
  if ensure_cmd apt-get; then
    $SUDO apt-get update -y
    $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y \
      python3 python3-venv python3-pip \
      php-cli php-curl \
      curl jq tar gzip xz-utils git build-essential cmake automake libtool pkg-config \
      libssl-dev \
      ca-certificates
  elif ensure_cmd dnf; then
    $SUDO dnf install -y python3 python3-virtualenv python3-pip php-cli curl jq tar gzip xz git make gcc cmake automake libtool pkgconf openssl-devel ca-certificates
  elif ensure_cmd yum; then
    $SUDO yum install -y python3 python3-virtualenv python3-pip php-cli curl jq tar gzip xz git make gcc cmake automake libtool pkgconfig openssl-devel ca-certificates
  elif ensure_cmd pacman; then
    $SUDO pacman -Sy --noconfirm python python-virtualenv python-pip php curl jq tar gzip xz git base-devel cmake automake libtool pkgconf openssl ca-certificates
  else
    echo "[!] Could not detect package manager. Please install dependencies manually." >&2
  fi
}

mkdir -p "$ROOT_DIR/miners/xmrig" "$ROOT_DIR/miners/cpuminer-opt" "$ROOT_DIR/logs/miners" "$ROOT_DIR/var/state" "$ROOT_DIR/config"

install_packages

# Python environment
if [[ ! -d "$ROOT_DIR/.venv" ]]; then
  python3 -m venv "$ROOT_DIR/.venv"
fi
"$ROOT_DIR/.venv/bin/pip" install --upgrade pip
"$ROOT_DIR/.venv/bin/pip" install -r "$ROOT_DIR/orchestrator/requirements.txt"

# Download XMRig
XMRIG_API="https://api.github.com/repos/xmrig/xmrig/releases/latest"
XMRIG_URL=$(curl -sL -H "Accept: application/vnd.github+json" "$XMRIG_API" | jq -r \
  '.assets[] | select(.name | test("linux-(x64|arm64).*\\.tar\\.gz$")) | .browser_download_url' | \
  grep "$ARCH_TAG" | head -n1 || true)
if [[ -n "${XMRIG_URL:-}" ]]; then
  echo "[i] Downloading XMRig from: $XMRIG_URL"
  TMPFILE=$(mktemp)
  curl -L "$XMRIG_URL" -o "$TMPFILE"
  tar -xzf "$TMPFILE" -C "$ROOT_DIR/miners/xmrig" --strip-components=1 || true
  rm -f "$TMPFILE"
  if [[ -x "$ROOT_DIR/miners/xmrig/xmrig" ]]; then
    echo "[i] XMRig installed at miners/xmrig/xmrig"
  else
    echo "[!] Failed to place xmrig binary. Please check the archive structure." >&2
  fi
else
  echo "[!] Could not resolve XMRig download URL for arch $ARCH_TAG." >&2
fi

# Download cpuminer-opt (x86_64 preferred)
CPUMINER_URL=""
if [[ "$ARCH_TAG" == "x64" ]]; then
  CPUMINER_URL=$(curl -sL -H "Accept: application/vnd.github+json" "https://api.github.com/repos/JayDDee/cpuminer-opt/releases/latest" | jq -r \
    '.assets[] | select(.name | test("linux.*(x86_64|x64).*(tar\\.gz|zip)$")) | .browser_download_url' | head -n1 || true)
fi
if [[ -n "${CPUMINER_URL:-}" ]]; then
  echo "[i] Downloading cpuminer-opt from: $CPUMINER_URL"
  TMPFILE=$(mktemp)
  curl -L "$CPUMINER_URL" -o "$TMPFILE"
  if [[ "$CPUMINER_URL" == *.tar.gz ]]; then
    tar -xzf "$TMPFILE" -C "$ROOT_DIR/miners/cpuminer-opt" --strip-components=1 || true
  elif [[ "$CPUMINER_URL" == *.zip ]]; then
    if ensure_cmd unzip; then
      $SUDO apt-get install -y unzip || true
      unzip -o "$TMPFILE" -d "$ROOT_DIR/miners/cpuminer-opt"
    else
      echo "[!] unzip not found to extract cpuminer-opt archive." >&2
    fi
  else
    # some releases provide a single binary
    install -m 0755 "$TMPFILE" "$ROOT_DIR/miners/cpuminer-opt/cpuminer"
  fi
  rm -f "$TMPFILE"
else
  echo "[i] No prebuilt cpuminer-opt for this arch. Attempting from source (optional)."
  if ensure_cmd git; then
    ( set -x; \
      rm -rf "$ROOT_DIR/miners/cpuminer-opt-src"; \
      git clone --depth=1 https://github.com/JayDDee/cpuminer-opt "$ROOT_DIR/miners/cpuminer-opt-src"; \
      cd "$ROOT_DIR/miners/cpuminer-opt-src"; \
      ./build.sh || true; \
      if [[ -f cpuminer ]]; then install -m 0755 cpuminer "$ROOT_DIR/miners/cpuminer-opt/cpuminer"; fi )
  fi
fi

# Config
if [[ ! -f "$ROOT_DIR/config/config.yaml" ]]; then
  cp "$ROOT_DIR/config/config.example.yaml" "$ROOT_DIR/config/config.yaml"
  echo "[i] Created config/config.yaml from example. Please edit your pool and wallet." 
fi

echo "\n[i] Setup complete. Next steps:" 
echo "  1) Edit config/config.yaml to set your wallet and pool(s)"
echo "  2) Run ./start.sh to launch the orchestrator and dashboard"
