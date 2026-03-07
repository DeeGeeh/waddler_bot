#!/usr/bin/env bash
# Author: 100% Cursor generated, dont blame me for this shit.
# Cross-build rust_motor for Raspberry Pi OS 64-bit (aarch64).
# Run on Linux or WSL2. Copies .so into python_controller for easy transfer.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUST_MOTOR="$REPO_ROOT/waddler_bot/rust_motor"
OUT_DIR="$REPO_ROOT/waddler_bot/python_controller"
TARGET="aarch64-unknown-linux-gnu"

echo "=== Cross-build for Pi 64-bit (aarch64) ==="
echo "Repo root: $REPO_ROOT"

# Ensure Cargo config exists
CARGO_CONFIG="$REPO_ROOT/.cargo/config.toml"
mkdir -p "$(dirname "$CARGO_CONFIG")"
if [[ ! -f "$CARGO_CONFIG" ]]; then
  echo "[target.$TARGET]" > "$CARGO_CONFIG"
  echo 'linker = "aarch64-linux-gnu-gcc"' >> "$CARGO_CONFIG"
  echo "Wrote $CARGO_CONFIG"
fi

# Check toolchain
if ! command -v aarch64-linux-gnu-gcc &>/dev/null; then
  echo "Install cross-compiler: sudo apt install gcc-aarch64-linux-gnu"
  exit 1
fi
rustup target add "$TARGET" 2>/dev/null || true

# Build
cd "$RUST_MOTOR"
cargo build --release --target "$TARGET"

# Copy .so next to Python code (Python can load from same dir or parent)
LIB_SRC="$RUST_MOTOR/target/$TARGET/release/librust_motor.so"
LIB_DST="$OUT_DIR/rust_motor.so"
cp -f "$LIB_SRC" "$LIB_DST"
echo "Copied: $LIB_DST"
echo "Done. Sync waddler_bot/ to the Pi (e.g. scp -r waddler_bot pi@<PI_IP>:~/)."