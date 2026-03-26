import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import webview

from apple_music import get_playlists, get_playlist_tracks
from serato_db import parse_database
from matcher import build_serato_index, build_serato_title_index, match_tracks
from serato_crate import write_crate, crate_exists, get_date_crate_name, audio_paths_in_dir
from downloader import (
    check_sldl_installed, download_track, get_download_dir,
    get_credentials, save_credentials, get_base_dir, save_config,
)


class Api:
    def __init__(self):
        self._window = None
        self._serato_index = None
        self._serato_title_index = None
        self._matched = []
        self._unmatched = []
        self._playlist_tracks = []
        self._crate_name = ''

    # ── Playlists ──────────────────────────────────────────────────────────

    def get_playlists(self):
        try:
            return get_playlists()
        except Exception as e:
            return {'error': str(e)}

    # ── Serato index ───────────────────────────────────────────────────────

    def _ensure_index(self):
        if self._serato_index is None:
            tracks = parse_database()
            self._serato_index = build_serato_index(tracks)
            self._serato_title_index = build_serato_title_index(tracks)

    # ── Create crate ───────────────────────────────────────────────────────

    def check_crate_exists(self, crate_name):
        return crate_exists(crate_name)

    def create_crate(self, playlist, crate_name):
        try:
            self._ensure_index()
            playlist_tracks = get_playlist_tracks(playlist)
            matched, unmatched = match_tracks(
                playlist_tracks, self._serato_index, self._serato_title_index
            )

            track_paths = [t['path'] for t in matched]
            write_crate(crate_name, track_paths, overwrite=True)

            self._matched = matched
            self._unmatched = unmatched
            self._playlist_tracks = playlist_tracks
            self._crate_name = crate_name

            return {
                'matched': [
                    {'artist': t['artist'], 'title': t['title'], 'match_type': t.get('match_type', 'exact')}
                    for t in matched
                ],
                'unmatched': [
                    {'artist': t['artist'], 'title': t['title']}
                    for t in unmatched
                ],
                'total': len(playlist_tracks),
            }
        except Exception as e:
            return {'error': str(e)}

    # ── Downloads ──────────────────────────────────────────────────────────

    def start_downloads(self, indices):
        """Start parallel downloads for selected tracks (by index into unmatched list)."""
        username, password = get_credentials()
        if not username or not password:
            return {'error': 'no_credentials'}
        if not check_sldl_installed():
            return {'error': 'no_sldl'}

        tracks = [self._unmatched[i] for i in indices]
        total = len(tracks)
        crate_name = self._crate_name
        matched = list(self._matched)
        playlist_tracks = list(self._playlist_tracks)

        def work():
            track_to_path = {(t['artist'], t['title']): t['path'] for t in matched}
            ok_count = 0
            fail_count = 0
            lock = threading.Lock()
            download_dir = get_download_dir()

            def download_one(entry):
                local_i, track = entry
                artist, title = track['artist'], track['title']
                self._js('_onDownloadStart', {'i': local_i, 'artist': artist, 'title': title})
                status, file_path = download_track(artist, title, username, password)
                return local_i, track, status, file_path

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(download_one, (i, t)): t
                    for i, t in enumerate(tracks)
                }
                for future in as_completed(futures):
                    i, track, status, file_path = future.result()
                    with lock:
                        if file_path:
                            track_to_path[(track['artist'], track['title'])] = str(file_path)[1:]
                        if status == 'ok':
                            ok_count += 1
                        else:
                            fail_count += 1
                        done = ok_count + fail_count
                    self._js('_onDownloadUpdate', {
                        'i': i, 'artist': track['artist'], 'title': track['title'],
                        'status': status, 'done': done, 'total': total,
                    })

            # Rebuild playlist crate in Apple Music order
            crate_errors = []
            if crate_name and playlist_tracks:
                ordered = [
                    track_to_path[key]
                    for t in playlist_tracks
                    if (key := (t['artist'], t['title'])) in track_to_path
                ]
                if ordered:
                    try:
                        write_crate(crate_name, ordered, overwrite=True)
                    except Exception as e:
                        crate_errors.append(str(e))

            # Update date crate
            if download_dir.exists():
                date_paths = audio_paths_in_dir(download_dir)
                if date_paths:
                    try:
                        write_crate(get_date_crate_name(), date_paths, overwrite=True)
                    except Exception as e:
                        crate_errors.append(str(e))

            self._js('_onDownloadsComplete', {
                'ok': ok_count, 'fail': fail_count, 'errors': crate_errors,
            })

        threading.Thread(target=work, daemon=True).start()
        return {'ok': True}

    # ── Settings ───────────────────────────────────────────────────────────

    def get_settings(self):
        username, password = get_credentials()
        return {
            'username': username or '',
            'has_password': bool(password),
            'base_dir': str(get_base_dir()),
        }

    def save_settings(self, username, password, folder):
        try:
            if username and password:
                save_credentials(username, password)
            if folder:
                save_config({'download_base_dir': folder})
            return {'ok': True}
        except Exception as e:
            return {'error': str(e)}

    def browse_folder(self):
        result = self._window.create_file_dialog(
            webview.FOLDER_DIALOG,
            directory=str(get_base_dir()),
        )
        return result[0] if result else None

    # ── Helpers ────────────────────────────────────────────────────────────

    def _js(self, fn, data):
        """Call a global JS function with a JSON payload."""
        self._window.evaluate_js(f'window.{fn}({json.dumps(data)})')


def start():
    api = Api()
    base = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).parent
    window = webview.create_window(
        'Playlist → Serato',
        url=str(base / 'frontend' / 'index.html'),
        js_api=api,
        width=520,
        height=840,
        min_size=(480, 600),
        resizable=True,
    )
    api._window = window
    webview.start()


if __name__ == '__main__':
    start()
