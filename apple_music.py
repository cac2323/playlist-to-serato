import subprocess


# Playlists to ignore — these are Music app built-ins, not user playlists
_SKIP_PLAYLISTS = {
    "Library", "Music", "Downloaded", "Recently Added", "Recently Played",
    "Top 25 Most Played", "Loved", "Genius", "90's Music", "Classical Music",
    "Music Videos", "My Mix 1", "My Mix 2", "My Mix 3", "My Mix 4",
    "My Mix 5", "My Mix 6",
}


def _run_applescript(script: str, *args: str) -> str:
    """Run an AppleScript string, optionally passing argv (never interpolated)."""
    result = subprocess.run(
        ["osascript", "-", *args],
        input=script,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript error: {result.stderr.strip()}")
    return result.stdout.strip()


def get_playlists() -> list[str]:
    """Return user playlist names from the Music app, excluding built-ins."""
    script = """
tell application "Music"
    set output to ""
    repeat with pl in every playlist
        set output to output & (name of pl) & linefeed
    end repeat
    return output
end tell
"""
    raw = _run_applescript(script)
    names = [n.strip() for n in raw.splitlines()]
    return [n for n in names if n and n not in _SKIP_PLAYLISTS]


def get_playlist_tracks(playlist_name: str) -> list[dict]:
    """
    Return tracks in the given playlist as a list of {title, artist} dicts.

    Uses a tab delimiter between fields and newline between tracks to avoid
    ambiguity with commas in song/artist names.
    """
    script = """
on run argv
    set playlistName to item 1 of argv
    tell application "Music"
        set output to ""
        set t to tracks of playlist playlistName
        repeat with tr in t
            set output to output & (name of tr) & tab & (artist of tr) & linefeed
        end repeat
        return output
    end tell
end run
"""
    raw = _run_applescript(script, playlist_name)
    tracks = []
    for line in raw.splitlines():
        if "\t" in line:
            title, artist = line.split("\t", 1)
            tracks.append({"title": title.strip(), "artist": artist.strip()})
    return tracks


if __name__ == "__main__":
    print("Fetching playlists from Music app...\n")
    playlists = get_playlists()
    print(f"Found {len(playlists)} playlists:")
    for p in playlists:
        print(f"  - {p}")

    if playlists:
        # Show tracks from the first playlist as a sample
        sample = playlists[0]
        print(f"\nSample tracks from '{sample}':")
        tracks = get_playlist_tracks(sample)
        for t in tracks[:5]:
            print(f"  {t['artist']} — {t['title']}")
        if len(tracks) > 5:
            print(f"  ... and {len(tracks) - 5} more")
