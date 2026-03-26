import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from concurrent.futures import ThreadPoolExecutor, as_completed

from apple_music import get_playlists, get_playlist_tracks
from serato_db import parse_database
from matcher import build_serato_index, build_serato_title_index, match_tracks
from serato_crate import write_crate, crate_exists, get_date_crate_name, audio_paths_in_dir, AUDIO_EXTENSIONS
from downloader import (
    check_sldl_installed, download_track, get_download_dir,
    get_credentials, save_credentials, get_base_dir, save_config,
)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Playlist → Serato Crate")
        self.resizable(False, False)
        self._serato_index = None
        self._serato_title_index = None
        self._all_playlists = []
        self._unmatched = []
        self._matched = []
        self._playlist_tracks = []
        self._crate_name = ""
        self._build_ui()
        self._load_playlists()

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        # Playlist row
        tk.Label(self, text="Playlist:").grid(row=0, column=0, sticky="w", **pad)
        self._playlist_var = tk.StringVar()
        self._playlist_entry = tk.Entry(self, textvariable=self._playlist_var, width=42)
        self._playlist_entry.grid(row=0, column=1, sticky="ew", **pad)
        self._playlist_entry.bind("<KeyRelease>", self._on_search)
        self._playlist_entry.bind("<FocusOut>", self._hide_popup)
        self._playlist_entry.bind("<Escape>", self._hide_popup)
        self._playlist_entry.bind("<Return>", self._on_return)

        # Popup listbox for search results
        self._popup = tk.Toplevel(self)
        self._popup.withdraw()
        self._popup.overrideredirect(True)  # No title bar/borders
        self._listbox = tk.Listbox(self._popup, width=42, height=8, activestyle="none")
        self._listbox.pack(fill="both", expand=True)
        self._listbox.bind("<ButtonRelease-1>", self._on_listbox_select)
        self._listbox.bind("<Return>", self._on_listbox_select)

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=0, column=2, padx=(0, 12))
        tk.Button(btn_frame, text="↺", command=self._load_playlists).pack(side="left")
        tk.Button(btn_frame, text="⚙", command=self._open_credentials_dialog).pack(side="left", padx=(4, 0))

        # Crate name row
        tk.Label(self, text="Crate name:").grid(row=1, column=0, sticky="w", **pad)
        self._crate_name_var = tk.StringVar()
        tk.Entry(self, textvariable=self._crate_name_var, width=42).grid(
            row=1, column=1, sticky="ew", **pad
        )

        # Create button
        self._create_btn = tk.Button(
            self, text="Create Crate", command=self._on_create, width=20
        )
        self._create_btn.grid(row=2, column=0, columnspan=3, pady=(4, 8))

        # Status label
        self._status_var = tk.StringVar(value="Loading playlists…")
        tk.Label(self, textvariable=self._status_var, fg="gray").grid(
            row=3, column=0, columnspan=3, **pad
        )

        # Results box
        self._results = tk.Text(self, width=55, height=14, state="disabled", wrap="word")
        self._results.grid(row=4, column=0, columnspan=3, padx=12, pady=(0, 4))
        self._results.tag_config("heading", font=("", 11, "bold"))
        self._results.tag_config("ok", foreground="green")
        self._results.tag_config("miss", foreground="#cc4400")
        self._results.tag_config("dl", foreground="#0055cc")

        # Unmatched tracks panel (hidden until there are unmatched tracks)
        self._unmatched_frame = tk.Frame(self)
        self._unmatched_frame.grid(row=5, column=0, columnspan=3, padx=12, sticky="ew")
        self._unmatched_frame.grid_remove()

        # Header row: label + select all / deselect all
        unmatched_header = tk.Frame(self._unmatched_frame)
        unmatched_header.pack(fill="x")
        self._unmatched_label = tk.Label(unmatched_header, text="", fg="#cc4400")
        self._unmatched_label.pack(side="left")
        tk.Button(unmatched_header, text="All", command=self._select_all, width=4).pack(side="right")
        tk.Button(unmatched_header, text="None", command=self._deselect_all, width=4).pack(side="right", padx=(0, 4))

        # Scrollable listbox (selectmode=multiple: click toggles each item)
        list_frame = tk.Frame(self._unmatched_frame)
        list_frame.pack(fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self._unmatched_listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set, height=6,
            selectmode=tk.MULTIPLE, activestyle="none",
        )
        self._unmatched_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._unmatched_listbox.yview)
        self._unmatched_listbox.bind("<<ListboxSelect>>", lambda e: self._update_download_btn())

        self._unmatched_tracks = []  # list of track dicts, parallel to listbox items

        # Download button
        self._download_btn = tk.Button(
            self, text="", command=self._on_download, width=32
        )
        self._download_btn.grid(row=6, column=0, columnspan=3, pady=(4, 12))
        self._download_btn.grid_remove()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_playlists(self):
        self._set_status("Loading playlists…")
        self._create_btn.config(state="disabled")
        self._playlist_entry.config(state="disabled")
        threading.Thread(target=self._fetch_playlists, daemon=True).start()

    def _fetch_playlists(self):
        try:
            playlists = get_playlists()
        except Exception as e:
            self.after(0, lambda: self._set_status(f"Error loading playlists: {e}", error=True))
            return

        def update():
            self._all_playlists = playlists
            self._playlist_entry.config(state="normal")
            self._set_status("Select a playlist to get started.")
            self._create_btn.config(state="normal")

        self.after(0, update)

    def _ensure_serato_index(self, callback):
        """Load the Serato DB index if not already loaded, then call callback."""
        if self._serato_index is not None:
            callback()
            return

        self._set_status("Loading Serato library…")

        def load():
            try:
                tracks = parse_database()
                self._serato_index = build_serato_index(tracks)
                self._serato_title_index = build_serato_title_index(tracks)
            except Exception as e:
                self.after(0, lambda: self._set_status(f"Error loading Serato DB: {e}", error=True))
                return
            self.after(0, callback)

        threading.Thread(target=load, daemon=True).start()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_search(self, _event=None):
        typed = self._playlist_var.get().lower()
        filtered = [p for p in self._all_playlists if typed in p.lower()]
        self._listbox.delete(0, "end")
        for p in filtered:
            self._listbox.insert("end", p)
        if filtered:
            self._show_popup()
        else:
            self._hide_popup()

    def _show_popup(self):
        # Position the popup directly below the entry widget
        x = self._playlist_entry.winfo_rootx()
        y = self._playlist_entry.winfo_rooty() + self._playlist_entry.winfo_height()
        self._popup.geometry(f"+{x}+{y}")
        self._popup.deiconify()
        self._popup.lift()

    def _hide_popup(self, _event=None):
        self._popup.withdraw()

    def _on_listbox_select(self, _event=None):
        selection = self._listbox.curselection()
        if selection:
            name = self._listbox.get(selection[0])
            self._playlist_var.set(name)
            self._crate_name_var.set(name)
            self._hide_popup()
            self._playlist_entry.focus_set()

    def _on_return(self, _event=None):
        # If there's exactly one filtered result, select it
        if self._listbox.size() == 1:
            self._playlist_var.set(self._listbox.get(0))
            self._crate_name_var.set(self._listbox.get(0))
            self._hide_popup()

    def _on_playlist_selected(self, _event=None):
        name = self._playlist_var.get()
        self._crate_name_var.set(name)

    def _on_create(self):
        playlist = self._playlist_var.get().strip()
        crate_name = self._crate_name_var.get().strip()

        if not playlist:
            messagebox.showwarning("No playlist", "Please select a playlist first.")
            return
        if self._all_playlists and playlist not in self._all_playlists:
            messagebox.showwarning("Invalid playlist", f'"{playlist}" is not a valid playlist name.\nSelect one from the list.')
            return
        if not crate_name:
            messagebox.showwarning("No crate name", "Please enter a name for the crate.")
            return

        if crate_exists(crate_name):
            overwrite = messagebox.askyesno(
                "Crate already exists",
                f'A crate named "{crate_name}" already exists.\nOverwrite it?',
            )
            if not overwrite:
                return

        self._create_btn.config(state="disabled")
        self._ensure_serato_index(lambda: self._run_create(playlist, crate_name))

    def _run_create(self, playlist: str, crate_name: str):
        self._set_status(f'Fetching "{playlist}" from Music app…')

        def work():
            try:
                playlist_tracks = get_playlist_tracks(playlist)
                matched, unmatched = match_tracks(playlist_tracks, self._serato_index, self._serato_title_index)
                track_paths = [t["path"] for t in matched]
                write_crate(crate_name, track_paths, overwrite=True)
                self.after(0, lambda: self._show_results(playlist, crate_name, matched, unmatched, playlist_tracks))
            except Exception as e:
                self.after(0, lambda: self._set_status(f"Error: {e}", error=True))
                self.after(0, lambda: self._create_btn.config(state="normal"))

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg: str, error: bool = False):
        self._status_var.set(msg)

    def _show_results(self, playlist: str, crate_name: str, matched: list, unmatched: list, playlist_tracks: list):
        self._create_btn.config(state="normal")
        self._set_status(f'Crate "{crate_name}" created.')
        self._unmatched = unmatched
        self._matched = matched
        self._playlist_tracks = playlist_tracks
        self._crate_name = crate_name

        self._results.config(state="normal")
        self._results.delete("1.0", "end")

        exact_count = sum(1 for t in matched if t.get("match_type") == "exact")
        approx_count = len(matched) - exact_count
        summary = f"✓ {len(matched)} tracks added to crate"
        if approx_count:
            summary += f"  ({approx_count} approximate)"
        self._results.insert("end", summary + "\n", "ok")

        if matched:
            if approx_count:
                self._results.insert("end", "  (~ = fuzzy or title-only match)\n", "dl")
            for t in matched:
                symbol = "✓" if t.get("match_type") == "exact" else "~"
                tag = "ok" if symbol == "✓" else "dl"
                self._results.insert("end", f"  {symbol} {t['artist']} — {t['title']}\n", tag)

        self._results.config(state="disabled")

        # Clear old listbox entries
        self._unmatched_listbox.delete(0, tk.END)
        self._unmatched_tracks.clear()

        if unmatched:
            self._unmatched_label.config(text=f"✗ {len(unmatched)} not found in Serato:")
            for t in unmatched:
                self._unmatched_tracks.append(t)
                self._unmatched_listbox.insert(tk.END, f"{t['artist']} — {t['title']}")
            self._unmatched_listbox.select_set(0, tk.END)
            self._unmatched_frame.grid()
            self._update_download_btn()
        else:
            self._unmatched_frame.grid_remove()
            self._download_btn.grid_remove()

    def _select_all(self):
        self._unmatched_listbox.select_set(0, tk.END)
        self._update_download_btn()

    def _deselect_all(self):
        self._unmatched_listbox.select_clear(0, tk.END)
        self._update_download_btn()

    def _update_download_btn(self):
        checked = len(self._unmatched_listbox.curselection())
        total = len(self._unmatched_tracks)
        if checked == 0:
            self._download_btn.grid_remove()
        else:
            label = f"Download {checked} of {total} missing songs via Soulseek" if checked < total else f"Download {total} missing songs via Soulseek"
            self._download_btn.config(text=label)
            self._download_btn.grid()

    # ------------------------------------------------------------------
    # Download handlers
    # ------------------------------------------------------------------

    def _on_download(self):
        if not check_sldl_installed():
            messagebox.showerror(
                "sldl not found",
                "sldl is required for downloads.\n\n"
                "Install it with:\n"
                "  brew install sldl\n\n"
                "Or download from:\n"
                "  github.com/fiso64/slsk-batchdl",
            )
            return

        username, password = get_credentials()
        if not username or not password:
            self._open_credentials_dialog(on_save=self._start_downloads)
            return

        self._start_downloads()

    def _start_downloads(self):
        username, password = get_credentials()
        if not username or not password:
            return

        tracks = [self._unmatched_tracks[i] for i in self._unmatched_listbox.curselection()]
        if not tracks:
            return

        self._download_btn.config(state="disabled")
        self._create_btn.config(state="disabled")
        self._unmatched_frame.grid_remove()

        # Reset results to show download progress
        self._results.config(state="normal")
        self._results.delete("1.0", "end")
        self._results.insert("end", f"Downloading {len(tracks)} missing songs…\n\n")
        self._results.config(state="disabled")
        total = len(tracks)
        self._set_status(f"Downloading 0 / {total}…")
        crate_name = self._crate_name
        matched = list(self._matched)
        playlist_tracks = list(self._playlist_tracks)

        def work():
            ok_count = 0
            fail_count = 0
            lock = threading.Lock()
            download_dir = get_download_dir()

            # Start with pre-matched tracks in a (artist, title) → serato_path dict
            track_to_path = {(t["artist"], t["title"]): t["path"] for t in matched}

            def download_one(track):
                artist = track["artist"]
                title = track["title"]
                self.after(0, lambda a=artist, t=title: self._append_result(
                    f"⬇  {a} — {t}\n", "dl"
                ))
                status, file_path = download_track(artist, title, username, password)
                return track, status, file_path

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(download_one, t): t for t in tracks}
                for future in as_completed(futures):
                    track, status, file_path = future.result()
                    artist = track["artist"]
                    title = track["title"]

                    with lock:
                        if file_path:
                            track_to_path[(artist, title)] = str(file_path)[1:]  # strip leading /
                        if status == "ok":
                            ok_count += 1
                            tag, symbol = "ok", "✓"
                        else:
                            fail_count += 1
                            tag, symbol = "miss", "✗"
                        done_so_far = ok_count + fail_count

                    self.after(0, lambda n=done_so_far: self._set_status(
                        f"Downloading {n} / {total}…" if n < total else "Finishing up…"
                    ))
                    self.after(0, lambda a=artist, t=title, sym=symbol, tg=tag: self._append_result(
                        f"{sym} {a} — {t}\n", tg
                    ))

            def done():
                crate_errors = []

                # Rebuild playlist crate in original Apple Music playlist order
                if crate_name and playlist_tracks:
                    ordered_paths = []
                    for t in playlist_tracks:
                        key = (t["artist"], t["title"])
                        if key in track_to_path:
                            ordered_paths.append(track_to_path[key])
                    if ordered_paths:
                        try:
                            write_crate(crate_name, ordered_paths, overwrite=True)
                        except Exception as e:
                            crate_errors.append(f"Playlist crate: {e}")

                # Create/update the date crate with all audio files in today's folder
                if download_dir.exists():
                    date_paths = audio_paths_in_dir(download_dir)
                    if date_paths:
                        try:
                            write_crate(get_date_crate_name(), date_paths, overwrite=True)
                        except Exception as e:
                            crate_errors.append(f"Date crate: {e}")

                self._append_result(
                    f"\nDone — {ok_count} downloaded, {fail_count} not found.\n", "ok"
                )
                if ok_count:
                    self._append_result(
                        "Serato crates updated — reopen Serato to see changes.\n", "ok"
                    )
                for err in crate_errors:
                    self._append_result(f"Error: {err}\n", "miss")

                self._download_btn.config(state="normal", text="Re-download missing songs")
                self._create_btn.config(state="normal")
                self._set_status("Downloads complete.")

            self.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _append_result(self, text: str, tag: str = ""):
        self._results.config(state="normal")
        self._results.insert("end", text, tag)
        self._results.see("end")
        self._results.config(state="disabled")

    def _open_credentials_dialog(self, on_save=None):
        dialog = tk.Toplevel(self)
        dialog.title("Soulseek Credentials")
        dialog.resizable(False, False)
        dialog.grab_set()  # Modal

        pad = {"padx": 12, "pady": 6}

        tk.Label(dialog, text="Soulseek username:").grid(row=0, column=0, sticky="w", **pad)
        username_var = tk.StringVar()
        tk.Entry(dialog, textvariable=username_var, width=28).grid(row=0, column=1, **pad)

        tk.Label(dialog, text="Soulseek password:").grid(row=1, column=0, sticky="w", **pad)
        password_var = tk.StringVar()
        tk.Entry(dialog, textvariable=password_var, show="•", width=28).grid(row=1, column=1, **pad)

        tk.Label(dialog, text="Download folder:").grid(row=2, column=0, sticky="w", **pad)
        folder_var = tk.StringVar(value=str(get_base_dir()))
        folder_frame = tk.Frame(dialog)
        folder_frame.grid(row=2, column=1, sticky="ew", **pad)
        tk.Entry(folder_frame, textvariable=folder_var, width=22, state="readonly").pack(side="left")
        def browse():
            chosen = filedialog.askdirectory(parent=dialog, initialdir=folder_var.get())
            if chosen:
                folder_var.set(chosen)
        tk.Button(folder_frame, text="Browse…", command=browse).pack(side="left", padx=(4, 0))

        # Pre-fill if already saved
        existing_user, existing_pass = get_credentials()
        if existing_user:
            username_var.set(existing_user)
        if existing_pass:
            password_var.set(existing_pass)

        def save():
            u = username_var.get().strip()
            p = password_var.get().strip()
            if not u or not p:
                messagebox.showwarning("Missing fields", "Please enter both username and password.", parent=dialog)
                return
            save_credentials(u, p)
            save_config({"download_base_dir": folder_var.get()})
            dialog.destroy()
            if on_save:
                on_save()

        tk.Button(dialog, text="Save", command=save, width=16).grid(
            row=3, column=0, columnspan=2, pady=(4, 12)
        )
