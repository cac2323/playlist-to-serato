import struct
from pathlib import Path

SERATO_DB_PATH = Path.home() / "Music" / "_Serato_" / "database V2"


def _read_tlv_fields(data: bytes) -> dict:
    """Parse TLV fields from a raw bytes block, return tag -> decoded string."""
    fields = {}
    i = 0
    while i + 8 <= len(data):
        tag = data[i:i+4].decode("ascii", errors="replace")
        length = struct.unpack(">I", data[i+4:i+8])[0]
        i += 8
        value = data[i:i+length]
        i += length
        # String fields: decode as UTF-16 Big Endian
        try:
            fields[tag] = value.decode("utf-16-be")
        except Exception:
            fields[tag] = value  # keep raw bytes for non-string fields
    return fields


def parse_database(db_path: Path = SERATO_DB_PATH) -> list[dict]:
    """
    Parse the Serato 'database V2' binary file and return a list of tracks.

    Each track is a dict with keys: 'path', 'title', 'artist'.
    """
    raw = db_path.read_bytes()
    tracks = []
    i = 0

    while i + 8 <= len(raw):
        tag = raw[i:i+4].decode("ascii", errors="replace")
        length = struct.unpack(">I", raw[i+4:i+8])[0]
        i += 8
        block = raw[i:i+length]
        i += length

        if tag == "otrk":
            fields = _read_tlv_fields(block)
            tracks.append({
                "path": fields.get("pfil", ""),
                "title": fields.get("tsng", ""),
                "artist": fields.get("tart", ""),
            })

    return tracks


if __name__ == "__main__":
    print(f"Parsing: {SERATO_DB_PATH}\n")
    tracks = parse_database()
    print(f"Total tracks found: {len(tracks)}\n")
    print("Sample (first 5 tracks):")
    for t in tracks[:5]:
        print(f"  Artist : {t['artist']}")
        print(f"  Title  : {t['title']}")
        print(f"  Path   : {t['path']}")
        print()
