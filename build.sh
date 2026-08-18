#!/bin/bash
set -euo pipefail

APP="dist/Playlist to Serato.app"
ZIP="dist/Playlist.to.Serato.zip"

TEAM_ID="${TEAM_ID:?Set TEAM_ID env var (e.g. export TEAM_ID=ABC123XYZ)}"
PYTHON="${PYTHON:-python3}"

echo "→ Runner"
sw_vers
"$PYTHON" --version

if [ "${SKIP_PYINSTALLER:-}" != "1" ]; then
  echo "→ Installing dependencies…"
  "$PYTHON" -m pip install -r requirements.txt

  echo "→ Building app bundle…"
  "$PYTHON" -m PyInstaller playlist_to_serato.spec --noconfirm
else
  echo "→ Skipping pip / PyInstaller (SKIP_PYINSTALLER=1)"
fi

if [ ! -d "$APP" ]; then
  echo "✗ App bundle missing: $APP"
  exit 1
fi

if [ "${SKIP_SIGN:-}" != "1" ]; then
  echo "→ Code signing identities (no secrets):"
  security find-identity -v -p codesigning || true

  SIGN_ID=$(security find-identity -v -p codesigning \
    | grep "Developer ID Application" \
    | grep "$TEAM_ID" \
    | head -1 \
    | sed 's/.*"\(.*\)"/\1/' || true)
  if [ -z "$SIGN_ID" ]; then
    echo "✗ No 'Developer ID Application' certificate found for team $TEAM_ID"
    exit 1
  fi
  echo "→ Using identity: $SIGN_ID"

  CODESIGN=(codesign --sign "$SIGN_ID" --force --timestamp --options runtime)
  if [ -n "${KEYCHAIN_PATH:-}" ]; then
    CODESIGN+=(--keychain "$KEYCHAIN_PATH")
  fi

  sign_macho() {
    local f="$1"
    if file "$f" | grep -q "Mach-O"; then
      echo "  codesign $f"
      "${CODESIGN[@]}" "$f"
    fi
  }

  echo "→ Signing nested binaries…"
  while IFS= read -r -d '' f; do
    sign_macho "$f"
  done < <(find "$APP" -type f \( -name "*.dylib" -o -name "*.so" \) -print0)

  while IFS= read -r -d '' f; do
    sign_macho "$f"
  done < <(find "$APP" -type f -perm -111 ! -name "*.py" -print0)

  echo "→ Signing bundle…"
  "${CODESIGN[@]}" --entitlements entitlements.plist "$APP"

  echo "→ Verifying signature…"
  codesign --verify --deep --strict "$APP"
else
  echo "→ Skipping codesign (SKIP_SIGN=1)"
fi

if [ "${SKIP_NOTARIZE:-}" != "1" ]; then
  APPLE_ID="${APPLE_ID:?Set APPLE_ID env var}"
  APP_PASSWORD="${APP_PASSWORD:?Set APP_PASSWORD env var}"

  echo "→ Zipping for notarization…"
  rm -f "$ZIP"
  ditto -c -k --keepParent "$APP" "$ZIP"

  echo "→ Submitting for notarization (this may take a few minutes)…"
  xcrun notarytool submit "$ZIP" \
    --apple-id "$APPLE_ID" \
    --password "$APP_PASSWORD" \
    --team-id "$TEAM_ID" \
    --wait

  echo "→ Stapling notarization ticket…"
  xcrun stapler staple "$APP"

  echo "→ Re-zipping stapled app…"
  rm -f "$ZIP"
  ditto -c -k --keepParent "$APP" "$ZIP"
else
  echo "→ Skipping notarization (SKIP_NOTARIZE=1)"
fi

echo ""
echo "✓ Done: $APP"
echo "  Upload $ZIP to GitHub Releases."
