# Playlist → Serato

Convert an Apple Music playlist into a Serato DJ Pro crate — and download any missing tracks via Soulseek.

---

## For DJs (no coding required)

### Prerequisites

1. **Serato DJ Pro** — install it and open it at least once so the library database is created.
2. **sldl** *(only needed if you want to download missing tracks)*
   - This app does not include `sldl`. Download it yourself from the upstream [releases](https://github.com/fiso64/slsk-batchdl/releases) and treat that file as untrusted until you are satisfied with the source.
   - Open Terminal and run:
     ```
     sudo mv ~/Downloads/sldl /usr/local/bin/
     sudo codesign --sign - /usr/local/bin/sldl
     ```
   - The signed app looks for `/usr/local/bin/sldl` and `/opt/homebrew/bin/sldl` even when launched from Finder (those folders are often missing from a double-clicked app's PATH).

### Installation

1. Download `Playlist.to.Serato.zip` from **this project's** [Releases](../../releases) page — not a copy hosted elsewhere
2. Unzip and drag **Playlist to Serato.app** to your Applications folder
3. Optional: confirm the app is signed by the developer you expect:
   ```
   codesign -dv --verbose=4 "/Applications/Playlist to Serato.app"
   ```
4. Double-click to open. A stapled, notarized build should not show a Gatekeeper warning. If macOS creates **Playlist to Serato 2**, delete the extra copy and keep a single app named **Playlist to Serato**.

### First run

1. Open the app
2. Select a playlist from the dropdown
3. Enter a name for the Serato crate
4. Click **Create Crate** — the crate is written even if some tracks are missing from Serato
5. *(Optional)* Download missing tracks via Soulseek:
   - Install `sldl` first (see Prerequisites). Until it is installed, the missing list is visible but there is **no download button**
   - Click **⚙**, enter Soulseek credentials, choose a download folder, Save
   - Select missing tracks and **Download via Soulseek**. When the run finishes, a summary stays on screen (saved vs not found). Reopen Serato DJ Pro to see the crate
6. If you skipped Soulseek, reopen Serato DJ Pro to see the crate from step 4

Soulseek is optional. Files come from other people on a peer-to-peer network; this app does not scan them. You are responsible for what you download. `sldl` is a **separate** program you install yourself — this app does not ship, sign, or verify that binary.

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
macOS Gatekeeper blocks unsigned binaries downloaded from the internet. The `codesign --sign -` command applies an ad-hoc signature that satisfies Gatekeeper without needing a paid developer certificate. You are trusting that `sldl` binary independently of this app.

**Where are my Soulseek credentials stored?**
The password is stored in the macOS Keychain when the OS allows it. If Keychain rejects the signed app, the password is written to `~/.playlist-to-serato/soulseek.pass` (mode 600) instead of failing the save. The username and download-folder path are in `~/.playlist-to-serato.json` (mode 600). While a download runs, a temporary 600 config file is written for `sldl` so the password is not visible in the process list; it is deleted when the process exits.

**Are Soulseek downloads safe?**
No guarantee. They are unverified peer-to-peer files. Use the feature only if you accept that risk. Copyright compliance is your responsibility.

**Which playlists appear in the dropdown?**
All playlists in your Apple Music library (read via AppleScript).

**The crate doesn't appear in Serato.**
Serato reads crates on launch. Quit and reopen Serato DJ Pro after creating a crate, and again after a Soulseek download finishes.

**I don't see Download via Soulseek.**
The app hides that button until it finds `sldl` in `/usr/local/bin`, `/opt/homebrew/bin`, or your PATH. Install `sldl` as in Prerequisites, then reopen the app (or Save in Settings). Creating a crate never requires Soulseek.

**The app won't open after I drag a new zip into Applications.**
Use one copy named **Playlist to Serato.app**. A Finder duplicate (**Playlist to Serato 2**) is easy to mix up with an older build. Download the latest zip from this repo's Releases page, delete extra copies, and replace the app in Applications.
