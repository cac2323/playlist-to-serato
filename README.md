# Playlist → Serato

Convert an Apple Music playlist into a Serato DJ Pro crate — and download any missing tracks via Soulseek.

---

## For DJs (no coding required)

### Prerequisites

1. **Serato DJ Pro** — install it and open it at least once so the library database is created.
2. **sldl** *(only needed if you want to download missing tracks)*
   - Download the latest macOS arm64 binary from [github.com/fiso64/slsk-batchdl/releases](https://github.com/fiso64/slsk-batchdl/releases)
   - Open Terminal and run:
     ```
     sudo mv ~/Downloads/sldl /usr/local/bin/
     sudo codesign --sign - /usr/local/bin/sldl
     ```

### Installation

1. Download `Playlist.to.Serato.zip` from the [Releases](../../releases) page
2. Unzip and drag **Playlist to Serato.app** to your Applications folder
3. Double-click to open — no security warnings

### First run

1. Open the app
2. Click **⚙** (settings) and enter your Soulseek username and password, and choose a download folder
3. Select a playlist from the dropdown
4. Enter a name for the Serato crate
5. Click **Create Crate**
6. If any tracks are missing from your Serato library, select them and click **Download via Soulseek**
7. Reopen Serato DJ Pro to see the new crate

---

## For developers (run from source)

### Requirements

- Python 3.11+
- macOS (uses AppleScript to read Apple Music)
- Serato DJ Pro installed

### Setup

```bash
git clone https://github.com/YOUR_USERNAME/playlist-to-serato.git
cd playlist-to-serato
pip install -r requirements.txt
python main.py
```

### Project structure

```
main.py               — entry point
webgui.py             — PyWebView backend / JS API
apple_music.py        — reads playlists via AppleScript
serato_db.py          — parses Serato's binary database
serato_crate.py       — writes Serato .crate files
matcher.py            — three-pass track matching (exact → fuzzy → title-only)
downloader.py         — sldl wrapper + macOS Keychain credential storage
frontend/
  index.html          — app UI
  style.css           — dark minimal styles
  app.js              — UI logic
```

### Building the .app

You need an Apple Developer account and Xcode command-line tools.

```bash
export TEAM_ID="YOUR_TEAM_ID"        # 10-char ID from developer.apple.com
export APPLE_ID="you@example.com"
export APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"  # app-specific password from appleid.apple.com

bash build.sh
```

The signed and notarized app will be at `dist/Playlist to Serato.app` and the zip ready for upload at `dist/Playlist.to.Serato.zip`.

---

## FAQ

**Why does sldl need to be codesigned?**
macOS Gatekeeper blocks unsigned binaries downloaded from the internet. The `codesign --sign -` command applies an ad-hoc signature that satisfies Gatekeeper without needing a paid developer certificate.

**Where are my Soulseek credentials stored?**
In the macOS Keychain — never in plain text on disk.

**Which playlists appear in the dropdown?**
All playlists in your Apple Music library (read via AppleScript).

**The crate doesn't appear in Serato.**
Serato reads crates on launch. Quit and reopen Serato DJ Pro after creating a crate.
