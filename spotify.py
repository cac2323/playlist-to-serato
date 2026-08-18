from pathlib import Path
import os

import spotipy
from spotipy.oauth2 import SpotifyPKCE

CLIENT_ID = 'REPLACE_WITH_CLIENT_ID'
REDIRECT_URI = 'http://127.0.0.1:8888/callback'
SCOPE = 'playlist-read-private playlist-read-collaborative'
CACHE_PATH = Path.home() / '.playlist-to-serato-spotify-cache'


def _lock_cache() -> None:
    try:
        if CACHE_PATH.exists():
            os.chmod(CACHE_PATH, 0o600)
    except OSError:
        pass


def _get_sp(client_id: str = CLIENT_ID) -> spotipy.Spotify:
    auth = SpotifyPKCE(
        client_id=client_id,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path=str(CACHE_PATH),
        open_browser=True,
    )
    sp = spotipy.Spotify(auth_manager=auth)
    _lock_cache()
    return sp


def is_authenticated() -> bool:
    """Return True if a valid cached token exists."""
    try:
        auth = SpotifyPKCE(
            client_id=CLIENT_ID,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            cache_path=str(CACHE_PATH),
            open_browser=False,
        )
        token = auth.get_cached_token()
        _lock_cache()
        return token is not None and not auth.is_token_expired(token)
    except Exception:
        return False


def connect() -> None:
    """Trigger the OAuth browser flow. Blocks until authenticated."""
    _get_sp()
    _lock_cache()


def disconnect() -> None:
    """Delete the cached token."""
    if CACHE_PATH.exists():
        CACHE_PATH.unlink()


def get_playlists() -> list[dict]:
    """Return all user playlists as [{'id': ..., 'name': ...}, ...]."""
    sp = _get_sp()
    playlists = []
    results = sp.current_user_playlists(limit=50)
    while results:
        for item in results['items']:
            if item:
                playlists.append({'id': item['id'], 'name': item['name']})
        results = sp.next(results) if results['next'] else None
    return playlists


def get_playlist_tracks(playlist_id: str) -> list[dict]:
    """Return tracks as [{'title': ..., 'artist': ...}, ...] — same format as apple_music.py."""
    sp = _get_sp()
    tracks = []
    results = sp.playlist_items(
        playlist_id,
        fields='items(track(name,artists(name))),next',
        limit=100,
    )
    while results:
        for item in results['items']:
            track = item.get('track')
            if not track or not track.get('name'):
                continue
            artists = track.get('artists', [])
            artist = artists[0]['name'] if artists else ''
            tracks.append({'title': track['name'], 'artist': artist})
        results = sp.next(results) if results['next'] else None
    return tracks
