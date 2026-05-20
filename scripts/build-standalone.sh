#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT/.build/zipapp"
OUT_DIR="$ROOT/dist"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$OUT_DIR"
trap 'rm -rf "$BUILD_DIR"; rmdir "$ROOT/.build" 2>/dev/null || true' EXIT
cp -R "$ROOT/src/amon" "$BUILD_DIR/amon"
cat > "$BUILD_DIR/__main__.py" <<'PY'
from amon.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
PY

python3 -m zipapp "$BUILD_DIR" \
  --python "/usr/bin/env python3" \
  --output "$OUT_DIR/amon"
chmod +x "$OUT_DIR/amon"

echo "$OUT_DIR/amon"
