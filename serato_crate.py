import datetime
import struct
from pathlib import Path

SUBCRATES_DIR = Path.home() / "Music" / "_Serato_" / "Subcrates"

AUDIO_EXTENSIONS = {".mp3", ".flac", ".aiff", ".aif", ".wav", ".m4a", ".ogg", ".opus"}


def get_date_crate_name() -> str:
    """Return today's Serato date crate name, e.g. '2026%%Mar%%Mar 25'."""
    today = datetime.date.today()
    return f"{today.year}%%{today.strftime('%b')}%%{today.strftime('%b %-d')}"


def audio_paths_in_dir(directory: Path) -> list[str]:
    """Return Serato-style paths (no leading /) for all audio files in a directory."""
    return [
        str(f)[1:]
        for f in sorted(directory.iterdir())
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
    ]


def _encode_field(tag: str, value: bytes) -> bytes:
    """Wrap value in a TLV envelope: 4-byte tag + 4-byte big-endian length + value."""
    return tag.encode("ascii") + struct.pack(">I", len(value)) + value


def _encode_string(s: str) -> bytes:
    """Encode a string as UTF-16 Big Endian (Serato's string format)."""
    return s.encode("utf-16-be")


def _build_header() -> bytes:
    """
    Build the crate file header: vrsn + osrt + ovct column definitions.
    This is fixed boilerplate that matches the format of existing crates.
    """
    # Version string
    vrsn = _encode_field("vrsn", _encode_string("1.0/Serato ScratchLive Crate"))

    # Sort info: sort column = '#' (track number), not reversed
    osrt_inner = (
        _encode_field("tvcn", _encode_string("#"))
        + _encode_field("brev", b"\x00")
    )
    osrt = _encode_field("osrt", osrt_inner)

    # Column definitions: (column name, display width in pixels)
    # Widths are taken from observed existing crates
    columns = [
        ("song",       "439"),
        ("playCount",  "0"),
        ("artist",     "0"),
        ("bpm",        "0"),
        ("key",        "0"),
        ("album",      "214"),
        ("length",     "0"),
        ("comment",    "0"),
    ]
    ovct_blocks = b""
    for col_name, col_width in columns:
        ovct_inner = (
            _encode_field("tvcn", _encode_string(col_name))
            + _encode_field("tvcw", _encode_string(col_width))
        )
        ovct_blocks += _encode_field("ovct", ovct_inner)

    return vrsn + osrt + ovct_blocks


def _encode_track(path: str) -> bytes:
    """Encode a single track reference as an otrk block containing a ptrk field."""
    ptrk = _encode_field("ptrk", _encode_string(path))
    return _encode_field("otrk", ptrk)


def crate_exists(crate_name: str) -> bool:
    """Check if a crate with this name already exists."""
    return (SUBCRATES_DIR / f"{crate_name}.crate").exists()


def write_crate(crate_name: str, track_paths: list[str], overwrite: bool = False) -> Path:
    """
    Write a Serato crate file.

    Args:
        crate_name:   Name for the crate (becomes the filename)
        track_paths:  List of file paths from the Serato database (no leading /)
        overwrite:    If True, overwrite an existing crate with the same name

    Returns:
        Path to the written .crate file

    Raises:
        FileExistsError: If crate already exists and overwrite=False
    """
    crate_path = SUBCRATES_DIR / f"{crate_name}.crate"

    if crate_path.exists() and not overwrite:
        raise FileExistsError(f"Crate already exists: {crate_path}")

    # Deduplicate paths while preserving order (same song can appear
    # twice in a playlist but a crate only holds each file once)
    seen = set()
    unique_paths = []
    for path in track_paths:
        if path not in seen:
            seen.add(path)
            unique_paths.append(path)

    data = _build_header()
    for path in unique_paths:
        data += _encode_track(path)

    crate_path.write_bytes(data)
    return crate_path


if __name__ == "__main__":
    from serato_db import parse_database
    from apple_music import get_playlist_tracks
    from matcher import build_serato_index, match_tracks

    TEST_CRATE_NAME = "_playlist_to_serato_test"
    TEST_PLAYLIST = "🦋"

    print("Loading Serato database...")
    serato_tracks = parse_database()
    serato_index = build_serato_index(serato_tracks)

    print(f"Fetching Apple Music playlist '{TEST_PLAYLIST}'...")
    playlist_tracks = get_playlist_tracks(TEST_PLAYLIST)

    matched, unmatched = match_tracks(playlist_tracks, serato_index)
    print(f"Matched {len(matched)}/{len(playlist_tracks)} tracks")

    if not matched:
        print("No matched tracks — nothing to write.")
    else:
        track_paths = [t["path"] for t in matched]

        if crate_exists(TEST_CRATE_NAME):
            print(f"\nCrate '{TEST_CRATE_NAME}' already exists — overwriting.")

        out = write_crate(TEST_CRATE_NAME, track_paths, overwrite=True)
        print(f"\nCrate written to: {out}")
        print(f"\nOpen Serato DJ Pro and look for a crate named '{TEST_CRATE_NAME}'.")
        print("Verify it contains the expected tracks, then we can clean up the test crate.")
