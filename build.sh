#!/bin/bash
set -euo pipefail

APP="dist/Playlist to Serato.app"
ZIP="dist/Playlist.to.Serato.zip"

TEAM_ID="${TEAM_ID:?Set TEAM_ID env var (e.g. export TEAM_ID=ABC123XYZ)}"
APPLE_ID="${APPLE_ID:?Set APPLE_ID env var (e.g. export APPLE_ID=you@example.com)}"
APP_PASSWORD="${APP_PASSWORD:?Set APP_PASSWORD env var (app-specific password from appleid.apple.com)}"

echo "→ Runner"
sw_vers
if command -v python >/dev/null 2>&1; then PY=python; else PY=python3; fi
echo "→ Python: $($PY --version) ($PY)"

echo "→ Code signing identities"
security find-identity -v -p codesigning || true

# Resolve full certificate identity from keychain (do not fail the pipeline on grep miss)
SIGN_ID=$(
  security find-identity -v -p codesigning \
    | grep "Developer ID Application" \
    | grep "$TEAM_ID" \
    | head -1 \
    | sed 's/.*"\(.*\)"/\1/' \
  || true
)
if [ -z "$SIGN_ID" ]; then
  echo "✗ No 'Developer ID Application' certificate found for team $TEAM_ID"
  echo "  Run: security find-identity -v -p codesigning"
  exit 1
fi
echo "→ Using identity: $SIGN_ID"

echo "→ Installing dependencies…"
"$PY" -m pip install -r requirements.txt

echo "→ Building app bundle…"
"$PY" -m PyInstaller playlist_to_serato.spec --noconfirm

if [ -n "${KEYCHAIN_PASSWORD:-}" ]; then
  echo "→ Unlocking signing keychain…"
  security unlock-keychain -p "$KEYCHAIN_PASSWORD" build.keychain
  security default-keychain -s build.keychain
fi

echo "→ Signing nested Mach-O files…"
while IFS= read -r -d '' f; do
  echo "  codesign $f"
  codesign --sign "$SIGN_ID" --force --timestamp --options runtime "$f"
done < <(find "$APP" -type f \( -name "*.dylib" -o -name "*.so" \) -print0)

while IFS= read -r -d '' f; do
  if file "$f" | grep -q "Mach-O"; then
    echo "  codesign $f"
    codesign --sign "$SIGN_ID" --force --timestamp --options runtime "$f"
  fi
done < <(find "$APP" -type f ! -name "*.py" -print0)

echo "→ Signing app bundle…"
codesign --sign "$SIGN_ID" \
  --force --timestamp --options runtime \
  --entitlements entitlements.plist \
  "$APP"

echo "→ Verifying signature…"
codesign --verify --deep "$APP"

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

echo ""
echo "✓ Done: $APP"
echo "  Upload $ZIP to GitHub Releases."
