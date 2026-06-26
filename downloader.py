import datetime
import json
import socket
import subprocess
import time
from pathlib import Path

import keyring

_KEYRING_SERVICE = "playlist-to-serato"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(('', 0))
        return s.getsockname()[1]

CONFIG_PATH = Path.home() / ".playlist-to-serato.json"


def get_base_dir() -> Path:
    """Return the base download directory, from config or default."""
    cfg = load_config()
    stored = cfg.get("download_base_dir")
    if stored:
        return Path(stored)
    return Path.home() / "Documents" / "Murzik" / str(datetime.date.today().year)


def get_download_dir() -> Path:
    """Return today's dated subfolder, creating it if needed.

    Structure: get_base_dir() / "March" / "Mar 25"
    """
    today = datetime.date.today()
    month_folder = today.strftime("%B")      # "March"
    day_folder   = today.strftime("%b %-d")  # "Mar 25" (%-d = no leading zero)
    path = get_base_dir() / month_folder / day_folder
    path.mkdir(parents=True, exist_ok=True)
    return path


# ------------------------------------------------------------------
# Credential storage
# ------------------------------------------------------------------

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {}


def save_config(data: dict):
    existing = load_config()
    existing.update(data)
    CONFIG_PATH.write_text(json.dumps(existing, indent=2))


def get_credentials() -> tuple[str | None, str | None]:
    cfg = load_config()
    username = cfg.get("soulseek_username")
    if not username:
        return None, None
    password = keyring.get_password(_KEYRING_SERVICE, username)
    return username, password


def save_credentials(username: str, password: str):
    keyring.set_password(_KEYRING_SERVICE, username, password)
    save_config({"soulseek_username": username})


# ------------------------------------------------------------------
# sldl integration
# ------------------------------------------------------------------

_LOGIN_ERROR_PATTERNS = (
    "login failed",
    "failed to login",
    "unable to connect",
    "connection refused",
    "invalid username",
    "incorrect password",
    "wrong password",
    "not connected",
)


def check_sldl_installed() -> bool:
    """Return True if sldl is available on PATH."""
    try:
        result = subprocess.run(
            ["sldl", "--help"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0 or b"sldl" in result.stdout.lower() + result.stderr.lower()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def test_connection(username: str, password: str) -> str:
    """
    Attempt to log into Soulseek via sldl without downloading anything.
    Returns 'ok', 'login_error', or 'failed'.
    """
    cmd = [
        "sldl", "connection_test_ping_xyzzy",
        "--user", username,
        "--pass", password,
        "--search-timeout", "5000",
        "--listen-port", str(_free_port()),
        "--no-progress",
    ]
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        got_past_login = False
        try:
            for line in process.stdout:
                line_lower = line.lower()
                print(line.rstrip(), flush=True)
                if any(p in line_lower for p in _LOGIN_ERROR_PATTERNS):
                    process.kill()
                    return "login_error"
                # "Searching" means we successfully logged in
                if "searching" in line_lower or "no files found" in line_lower or "no results" in line_lower:
                    got_past_login = True
                    process.kill()
                    break
        except Exception:
            pass
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
        # If no login error lines were seen, treat as ok
        return "ok"
    except FileNotFoundError:
        return "failed"


_LOG_KEYWORDS = ("login", "searching", "failed", "succeeded", "could not", "error", "connect")


def download_track(
    artist: str,
    title: str,
    username: str,
    password: str,
    target_dir: "Path | None" = None,
    on_log=None,
) -> "tuple[str, Path | None]":
    """
    Download a single track from Soulseek using sldl.

    Downloads into target_dir (defaults to get_download_dir()).
    Returns (status, file_path) where:
        status    — "ok" | "not_found" | "failed"
        file_path — Path of downloaded file, or None if not found/failed
    """
    import shutil
    from pathlib import Path as _Path

    download_dir = get_download_dir()

    # Use a private temp subdir to isolate this download from concurrent ones
    if target_dir is None:
        target_dir = download_dir / f"_dl_{artist}_{title}"[:60].replace("/", "_")

    target_dir = _Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    query = f"{artist} - {title}" if artist else title

    cmd = [
        "sldl", query,
        "--user", username,
        "--pass", password,
        "--path", str(target_dir),
        "--format", "flac,mp3,m4a,aiff,wav,ogg,opus",
        "--pref-format", "flac,mp3",
        "--fast-search",
        "--remove-ft",
        "--search-timeout", "15000",
        "--listen-port", str(_free_port()),
        "--no-progress",
    ]

    _PROGRESS_PREFIXES = ("Searching", "Login", "Initialize", "Succeeded", "Failed", "Could not")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        output_lines = []
        succeeded = False

        for line in process.stdout:
            line = line.rstrip()
            if not line:
                continue
            output_lines.append(line)
            print(line, flush=True)
            if on_log and any(kw in line.lower() for kw in _LOG_KEYWORDS):
                on_log(f"[{artist} — {title}] {line}")
            if line.startswith("Succeeded"):
                succeeded = True

        process.wait(timeout=120)

        # Move downloaded audio file(s) to the final download_dir
        audio_exts = {".mp3", ".flac", ".aiff", ".aif", ".wav", ".m4a", ".ogg", ".opus"}
        moved_path = None
        for f in sorted(target_dir.rglob('*')):
            if f.is_file() and f.suffix.lower() in audio_exts:
                dest = download_dir / f.name
                shutil.move(str(f), str(dest))
                moved_path = dest
                break  # only expect one file per track

        # Clean up temp dir
        shutil.rmtree(target_dir, ignore_errors=True)

        full_output = "\n".join(output_lines).lower()

        if any(p in full_output for p in _LOGIN_ERROR_PATTERNS):
            return "login_error", None

        if succeeded or (process.returncode == 0 and moved_path):
            time.sleep(2)
            return "ok", moved_path

        if any(phrase in full_output for phrase in ("no results", "failed to find", "not found", "could not")):
            time.sleep(2)
            return "not_found", None

        return "failed", None

    except subprocess.TimeoutExpired:
        process.kill()
        return "failed", None
    except FileNotFoundError:
        return "failed", None
