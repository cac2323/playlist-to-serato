#!/bin/bash
set -e

APP="dist/Playlist to Serato.app"
ZIP="dist/Playlist.to.Serato.zip"

TEAM_ID="${TEAM_ID:?Set TEAM_ID env var (e.g. export TEAM_ID=ABC123XYZ)}"
APPLE_ID="${APPLE_ID:?Set APPLE_ID env var (e.g. export APPLE_ID=you@example.com)}"
APP_PASSWORD="${APP_PASSWORD:?Set APP_PASSWORD env var (app-specific password from appleid.apple.com)}"

echo "→ Runner"
sw_vers
python --version || python3 --version

# Resolve full certificate identity from keychain
SIGN_ID=$(security find-identity -v -p codesigning | grep "Developer ID Application" | grep "$TEAM_ID" | head -1 | sed 's/.*"\(.*\)"/\1/')
if [ -z "$SIGN_ID" ]; then
  echo "✗ No 'Developer ID Application' certificate found for team $TEAM_ID"
  echo "  Run: security find-identity -v -p codesigning"
  security find-identity -v -p codesigning || true
  exit 1
fi
echo "→ Using identity: $SIGN_ID"

echo "→ Installing dependencies…"
pip install -r requirements.txt

echo "→ Building app bundle…"
pyinstaller playlist_to_serato.spec --noconfirm

echo "→ Signing…"
# Sign all loose binaries and dylibs inside the bundle first
find "$APP" -type f \( -name "*.dylib" -o -name "*.so" \) | while read f; do
  codesign --sign "$SIGN_ID" --force --timestamp --options runtime "$f"
done
find "$APP" -type f -perm +111 ! -name "*.py" | while read f; do
  file "$f" | grep -q "Mach-O" && codesign --sign "$SIGN_ID" --force --timestamp --options runtime "$f"
done
# Sign the bundle itself
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
