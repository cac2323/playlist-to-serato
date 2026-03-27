import re
import difflib

# Minimum similarity ratio to accept a fuzzy match (0.0 - 1.0)
FUZZY_THRESHOLD = 0.85


def normalize(artist: str, title: str) -> str:
    """
    Produce a normalized key from artist + title for comparison.

    Steps:
      - Lowercase everything
      - Remove featured artist info (feat., ft., with, etc.)
      - Strip punctuation and extra whitespace
    """
    combined = f"{artist} {title}".lower()
    # Remove featuring credits
    combined = re.sub(r"\(?\b(feat|ft|featuring|with)\b\.?.*?(\)|$)", "", combined)
    # Remove all non-alphanumeric characters except spaces
    combined = re.sub(r"[^a-z0-9 ]", "", combined)
    # Collapse whitespace
    combined = re.sub(r"\s+", " ", combined).strip()
    return combined


def normalize_title(title: str) -> str:
    """Normalize title only (no artist) for title-only matching."""
    return normalize("", title)


def build_serato_index(serato_tracks: list[dict]) -> dict[str, str]:
    """
    Build a lookup dict: normalize(artist, title) -> file path.

    If two tracks normalize to the same key, the last one wins
    (rare edge case, not worth handling specially).
    """
    return {
        normalize(t["artist"], t["title"]): t["path"]
        for t in serato_tracks
        if t["title"] or t["artist"]
    }


def build_serato_title_index(serato_tracks: list[dict]) -> dict[str, list[str]]:
    """
    Build title-only lookup: normalize(title) -> list of file paths.

    Multiple Serato tracks can share the same title (different artists),
    so the value is a list. We only use this index when there is exactly
    one match (unambiguous).
    """
    index: dict[str, list[str]] = {}
    for t in serato_tracks:
        if t["title"]:
            key = normalize_title(t["title"])
            index.setdefault(key, []).append(t["path"])
    return index


def match_tracks(
    playlist_tracks: list[dict],
    serato_index: dict[str, str],
    title_index: dict[str, list[str]] | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Match Apple Music playlist tracks against the Serato index.

    Returns:
        matched   — list of {title, artist, path, match_type} for tracks found
        unmatched — list of {title, artist} for tracks not found

    match_type values: "exact" | "fuzzy" | "title_only"
    """
    matched = []
    unmatched = []
    serato_keys = list(serato_index.keys())

    for track in playlist_tracks:
        key = normalize(track["artist"], track["title"])

        # Pass 1: exact normalized match (artist + title)
        if key in serato_index:
            matched.append({**track, "path": serato_index[key], "match_type": "exact"})
            continue

        # Pass 2: fuzzy match on artist + title
        close = difflib.get_close_matches(key, serato_keys, n=1, cutoff=FUZZY_THRESHOLD)
        if close:
            matched.append({**track, "path": serato_index[close[0]], "match_type": "fuzzy"})
            continue

        # Pass 3: title-only match — catches songs where artist name differs
        # between Apple Music and Serato. Only accept if unambiguous (1 result).
        if title_index is not None:
            title_key = normalize_title(track["title"])
            title_matches = title_index.get(title_key, [])
            if len(title_matches) == 1:
                matched.append({**track, "path": title_matches[0], "match_type": "title_only"})
                continue

        unmatched.append(track)

    return matched, unmatched


if __name__ == "__main__":
    from serato_db import parse_database
    from apple_music import get_playlists, get_playlist_tracks

    # Pick a playlist to test with
    playlists = get_playlists()
    print("Available playlists (first 10):")
    for i, p in enumerate(playlists[:10]):
        print(f"  {i}: {p}")

    idx = int(input("\nEnter number to test: "))
    playlist_name = playlists[idx]

    print("\nLoading Serato database...")
    serato_tracks = parse_database()
    serato_index = build_serato_index(serato_tracks)
    print(f"Indexed {len(serato_index)} Serato tracks")

    print(f"\nFetching Apple Music playlist '{playlist_name}'...")
    playlist_tracks = get_playlist_tracks(playlist_name)
    print(f"Playlist has {len(playlist_tracks)} tracks")

    matched, unmatched = match_tracks(playlist_tracks, serato_index)

    print("\nResults:")
    print(f"  Matched   : {len(matched)}")
    print(f"  Unmatched : {len(unmatched)}")

    if matched:
        print("\nMatched tracks (first 5):")
        for t in matched[:5]:
            print(f"  {t['artist']} — {t['title']}")
            print(f"    → {t['path']}")

    if unmatched:
        print("\nNot found in Serato:")
        for t in unmatched:
            print(f"  {t['artist']} — {t['title']}")
