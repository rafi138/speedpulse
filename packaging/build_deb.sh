#!/usr/bin/env bash
# Build a self-contained .deb from the PyInstaller one-directory payload.
# Usage: bash packaging/build_deb.sh 0.1.0     (run after pyinstaller build)
set -euo pipefail

VERSION="${1:?usage: build_deb.sh VERSION}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PAYLOAD="$ROOT/dist/speedpulse"
TREE="$ROOT/build/deb/speedpulse_${VERSION}_amd64"

[ -x "$PAYLOAD/speedpulse" ] || { echo "missing $PAYLOAD/speedpulse - run pyinstaller first" >&2; exit 1; }

rm -rf "$TREE"
mkdir -p "$TREE/DEBIAN" "$TREE/opt/speedpulse" "$TREE/usr/bin" "$TREE/usr/share/applications"
cp -r "$PAYLOAD/." "$TREE/opt/speedpulse/"

cat > "$TREE/usr/bin/speedpulse" <<'LAUNCHER'
#!/bin/sh
exec /opt/speedpulse/speedpulse "$@"
LAUNCHER
chmod 755 "$TREE/usr/bin/speedpulse"

cat > "$TREE/usr/share/applications/speedpulse.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=SpeedPulse
Comment=Internet speed monitor in your system tray
Exec=/usr/bin/speedpulse
Icon=speedpulse
Terminal=false
Categories=Network;Monitor;Utility;
Keywords=network;speed;bandwidth;monitor;
DESKTOP

for size in 16 22 24 32 48 64 128 256; do
  dir="$TREE/usr/share/icons/hicolor/${size}x${size}/apps"
  mkdir -p "$dir"
  cp "$ROOT/packaging/icons/speedpulse_${size}.png" "$dir/speedpulse.png"
done

SIZE_KB="$(du -sk --exclude=DEBIAN "$TREE" | cut -f1)"
cat > "$TREE/DEBIAN/control" <<CONTROL
Package: speedpulse
Version: ${VERSION}
Section: net
Priority: optional
Architecture: amd64
Installed-Size: ${SIZE_KB}
Depends: libgl1, libegl1, libxkbcommon0, libfontconfig1, libdbus-1-3
Maintainer: rafi138 <rafi138@users.noreply.github.com>
Homepage: https://github.com/rafi138/speedpulse
Description: Internet speed monitor for your system tray
 SpeedPulse shows live download/upload throughput of your network
 interfaces in the system tray, with per-interface selection, bits or
 bytes units, and launch-at-login. Self-contained build (bundled
 Python and Qt runtime).
CONTROL

OUT="$ROOT/dist/speedpulse_${VERSION}_amd64.deb"
dpkg-deb --build --root-owner-group "$TREE" "$OUT"
echo "Built $OUT"
