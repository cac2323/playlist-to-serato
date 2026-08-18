/* ─────────────────────────────────────────────────────────────
   app.js — Playlist → Serato frontend logic
   Communicates with Python via window.pywebview.api.*
───────────────────────────────────────────────────────────── */

// ── State ────────────────────────────────────────────────────
const state = {
  source: 'apple_music',   // 'apple_music' | 'spotify'
  playlists: [],
  playlistIds: {},         // name → id (Spotify only)
  unmatched: [],           // [{artist, title}, ...] — parallel to missing-list items
  selectedIndices: new Set(),
  downloading: false,
  notFoundTracks: [],      // tracks searched but not on Soulseek
  errorTracks: [],         // tracks that failed due to connection/timeout
};

// ── DOM refs ─────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const playlistInput    = $('playlist-input');
const playlistDrop     = $('playlist-dropdown');
const crateInput       = $('crate-input');
const btnCreate        = $('btn-create');
const btnRefresh       = $('btn-refresh');
const btnSettings      = $('btn-settings');
const statusEl         = $('status');
const resultsEl        = $('results');
const trackListEl      = $('track-list');
const statMatched      = $('stat-matched');
const statFuzzy        = $('stat-fuzzy');
const statMissing      = $('stat-missing');
const missingSec       = $('missing-section');
const missingLabel     = $('missing-label');
const missingListEl    = $('missing-list');
const btnDownload      = $('btn-download');
const btnCancel        = $('btn-cancel');
const downloadLogEl    = $('download-log');
const btnSelectAll     = $('btn-select-all');
const btnSelectNone    = $('btn-select-none');
const btnSourceApple   = $('btn-source-apple');
const btnSourceSpotify = $('btn-source-spotify');

// Settings modal
const modalOverlay       = $('modal-overlay');
const modalClose         = $('modal-close');
const sUsername          = $('s-username');
const sPassword          = $('s-password');
const sFolder            = $('s-folder');
const btnBrowse          = $('btn-browse');
const btnSave            = $('btn-save-settings');
const modalStatus        = $('modal-status');
const btnSpotifyConnect  = $('btn-spotify-connect');
const btnSpotifyDisconn  = $('btn-spotify-disconnect');
const spotifyStatusEl    = $('spotify-status');
const btnTestConn        = $('btn-test-conn');
const testConnStatusEl   = $('test-conn-status');

// ── Boot ─────────────────────────────────────────────────────
window.addEventListener('pywebviewready', () => {
  loadPlaylists();
});

// fallback if pywebviewready already fired
if (window.pywebview) loadPlaylists();

function loadPlaylists() {
  setStatus('Loading playlists…');
  playlistInput.disabled = true;
  btnCreate.disabled = true;

  window.pywebview.api.get_playlists(state.source).then(result => {
    if (result && result.error) {
      if (result.error === 'no_spotify_client_id') {
        setStatus('Enter your Spotify Client ID in ⚙ Settings to connect.');
      } else {
        setStatus('Error loading playlists: ' + result.error, 'error');
      }
      return;
    }

    if (state.source === 'spotify') {
      // result is [{id, name}, ...]
      state.playlistIds = {};
      state.playlists = (result || []).map(p => {
        state.playlistIds[p.name] = p.id;
        return p.name;
      });
    } else {
      state.playlists = result || [];
      state.playlistIds = {};
    }

    playlistInput.disabled = false;
    playlistInput.placeholder = 'Search playlists…';
    btnCreate.disabled = false;
    setStatus('Select a playlist to get started.');
  });
}

// ── Source toggle ─────────────────────────────────────────────
btnSourceApple.addEventListener('click', () => {
  if (state.source === 'apple_music') return;
  state.source = 'apple_music';
  btnSourceApple.classList.add('active');
  btnSourceSpotify.classList.remove('active');
  playlistInput.value = '';
  crateInput.value = '';
  resultsEl.hidden = true;
  loadPlaylists();
});

btnSourceSpotify.addEventListener('click', () => {
  if (state.source === 'spotify') return;
  state.source = 'spotify';
  btnSourceSpotify.classList.add('active');
  btnSourceApple.classList.remove('active');
  playlistInput.value = '';
  crateInput.value = '';
  resultsEl.hidden = true;
  loadPlaylists();
});

// ── Playlist search dropdown ──────────────────────────────────
playlistInput.addEventListener('input', () => {
  const q = playlistInput.value.toLowerCase();
  const matches = state.playlists.filter(p => p.toLowerCase().includes(q));
  renderDropdown(matches);
});

playlistInput.addEventListener('keydown', e => {
  const items = playlistDrop.querySelectorAll('.dropdown-item');
  const active = playlistDrop.querySelector('.active');
  let idx = Array.from(items).indexOf(active);

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    idx = Math.min(idx + 1, items.length - 1);
    items.forEach((el, i) => el.classList.toggle('active', i === idx));
    items[idx]?.scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    idx = Math.max(idx - 1, 0);
    items.forEach((el, i) => el.classList.toggle('active', i === idx));
    items[idx]?.scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Enter') {
    if (active) selectPlaylist(active.textContent);
    else if (items.length === 1) selectPlaylist(items[0].textContent);
  } else if (e.key === 'Escape') {
    hideDropdown();
  }
});

playlistInput.addEventListener('focus', () => {
  const q = playlistInput.value.toLowerCase();
  const matches = q
    ? state.playlists.filter(p => p.toLowerCase().includes(q))
    : state.playlists;
  renderDropdown(matches);
});

document.addEventListener('mousedown', e => {
  if (!playlistDrop.contains(e.target) && e.target !== playlistInput) {
    hideDropdown();
  }
});

function renderDropdown(items) {
  playlistDrop.innerHTML = '';
  if (!items.length) { hideDropdown(); return; }
  items.forEach(p => {
    const div = document.createElement('div');
    div.className = 'dropdown-item';
    div.textContent = p;
    div.addEventListener('mousedown', e => {
      e.preventDefault(); // prevent blur before click registers
      selectPlaylist(p);
    });
    playlistDrop.appendChild(div);
  });
  playlistDrop.hidden = false;
}

function selectPlaylist(name) {
  playlistInput.value = name;
  if (!crateInput.value || state.playlists.includes(crateInput.value)) {
    crateInput.value = name;
  }
  hideDropdown();
}

function hideDropdown() {
  playlistDrop.hidden = true;
}

// ── Create crate ─────────────────────────────────────────────
btnCreate.addEventListener('click', async () => {
  const playlist = playlistInput.value.trim();
  const crate    = crateInput.value.trim();

  if (!playlist) { setStatus('Please select a playlist.', 'error'); return; }
  if (!crate)    { setStatus('Please enter a crate name.', 'error'); return; }

  if (!state.playlists.includes(playlist)) {
    setStatus(`"${playlist}" is not a valid playlist name.`, 'error');
    return;
  }

  // Check for existing crate
  const exists = await window.pywebview.api.check_crate_exists(crate);
  if (exists && exists.error) {
    setStatus(exists.error, 'error');
    return;
  }
  if (exists) {
    if (!confirm(`A crate named "${crate}" already exists. Overwrite it?`)) return;
  }

  btnCreate.disabled = true;
  resultsEl.hidden = true;
  setStatus('Loading Serato library…');

  const playlistId = state.playlistIds[playlist] || null;
  const result = await window.pywebview.api.create_crate(playlist, crate, state.source, playlistId);

  btnCreate.disabled = false;

  if (result.error) {
    setStatus('Error: ' + result.error, 'error');
    return;
  }

  renderResults(result);
  setStatus(`Crate "${crate}" created — ${result.matched.length} tracks.`, 'ok');
});

btnRefresh.addEventListener('click', loadPlaylists);

// ── Render results ────────────────────────────────────────────
function renderResults(data) {
  const { matched, unmatched } = data;
  const exactCount  = matched.filter(t => t.match_type === 'exact').length;
  const fuzzyCount  = matched.length - exactCount;
  const missingCount = unmatched.length;

  statMatched.textContent = matched.length;
  statFuzzy.textContent   = fuzzyCount;
  statMissing.textContent = missingCount;

  // Track list
  trackListEl.innerHTML = '';
  matched.forEach(t => {
    const isExact = t.match_type === 'exact';
    const row = document.createElement('div');
    row.className = 'track';
    row.innerHTML = `
      <span class="track-indicator ${isExact ? 'exact' : 'approx'}">${isExact ? '✓' : '~'}</span>
      <span>
        <span class="track-artist">${esc(t.artist)}</span>
        <span class="track-sep">—</span>
        <span class="track-title">${esc(t.title)}</span>
      </span>
      ${!isExact ? `<span class="track-badge fuzzy">${esc(t.match_type)}</span>` : ''}
    `;
    trackListEl.appendChild(row);
  });

  // Missing
  state.unmatched = unmatched;
  state.selectedIndices = new Set(unmatched.map((_, i) => i));
  missingListEl.innerHTML = '';

  if (unmatched.length > 0) {
    missingLabel.textContent = `✗  ${unmatched.length} not found in Serato`;
    unmatched.forEach((t, i) => {
      const item = document.createElement('div');
      item.className = 'missing-item selected';
      item.dataset.index = i;
      item.innerHTML = `
        <div class="checkbox">✓</div>
        <div class="missing-text">
          <span class="title">${esc(t.title)}</span>
          <span class="track-sep"> — </span>
          <span class="artist">${esc(t.artist)}</span>
        </div>
        <span class="dl-status-icon"></span>
      `;
      item.addEventListener('click', () => toggleMissingItem(i));
      missingListEl.appendChild(item);
    });
    missingSec.hidden = false;
    updateDownloadBtn();
  } else {
    missingSec.hidden = true;
  }

  resultsEl.hidden = false;
}

// ── Missing item selection ────────────────────────────────────
function toggleMissingItem(i) {
  if (state.downloading) return;
  if (state.selectedIndices.has(i)) {
    state.selectedIndices.delete(i);
  } else {
    state.selectedIndices.add(i);
  }
  const item = missingListEl.querySelector(`[data-index="${i}"]`);
  const selected = state.selectedIndices.has(i);
  item.classList.toggle('selected', selected);
  item.querySelector('.checkbox').textContent = selected ? '✓' : '';
  updateDownloadBtn();
}

btnSelectAll.addEventListener('click', () => {
  if (state.downloading) return;
  state.unmatched.forEach((_, i) => state.selectedIndices.add(i));
  missingListEl.querySelectorAll('.missing-item').forEach(el => {
    el.classList.add('selected');
    el.querySelector('.checkbox').textContent = '✓';
  });
  updateDownloadBtn();
});

btnSelectNone.addEventListener('click', () => {
  if (state.downloading) return;
  state.selectedIndices.clear();
  missingListEl.querySelectorAll('.missing-item').forEach(el => {
    el.classList.remove('selected');
    el.querySelector('.checkbox').textContent = '';
  });
  updateDownloadBtn();
});

function updateDownloadBtn() {
  const n = state.selectedIndices.size;
  const total = state.unmatched.length;
  if (n === 0) {
    btnDownload.hidden = true;
  } else {
    btnDownload.hidden = false;
    btnDownload.textContent = n === total
      ? `Download ${n} missing via Soulseek`
      : `Download ${n} of ${total} missing via Soulseek`;
  }
}

// ── Downloads ─────────────────────────────────────────────────
let soulseekWarningAcked = false;

btnDownload.addEventListener('click', async () => {
  const indices = Array.from(state.selectedIndices);
  if (!indices.length) return;

  if (!soulseekWarningAcked) {
    const ok = confirm(
      'Soulseek downloads come from other users on a peer-to-peer network. Files are not scanned for malware. Continue?'
    );
    if (!ok) return;
    soulseekWarningAcked = true;
  }

  const result = await window.pywebview.api.start_downloads(indices);

  if (result.error === 'no_credentials') {
    openSettings(() => {});
    return;
  }
  if (result.error === 'no_sldl') {
    alert('sldl is not installed.\n\nDownload it from: github.com/fiso64/slsk-batchdl\n\nThen run:\n  sudo codesign --sign - /usr/local/bin/sldl');
    return;
  }
  if (result.error === 'no_tracks') {
    setStatus('No valid tracks selected.', 'error');
    return;
  }
  if (result.error) {
    setStatus('Download error: ' + result.error, 'error');
    return;
  }

  state.downloading = true;
  state.notFoundTracks = [];
  state.errorTracks = [];
  btnDownload.hidden = true;
  btnCancel.hidden = false;
  btnCreate.disabled = true;
  downloadLogEl.innerHTML = '';
  downloadLogEl.hidden = false;
  setStatus(`Downloading 0 / ${indices.length}…`);

  // Mark selected items as pending
  indices.forEach(i => {
    const item = missingListEl.querySelector(`[data-index="${i}"]`);
    if (item) item.classList.add('dl-pending');
  });
});

btnCancel.addEventListener('click', async () => {
  btnCancel.disabled = true;
  btnCancel.textContent = 'Cancelling…';
  await window.pywebview.api.cancel_downloads();
});

// ── Download progress callbacks (called from Python) ──────────
window._onDownloadStart = function({ i, artist, title }) {
  const item = missingListEl.querySelector(`[data-index="${i}"]`);
  if (item) {
    item.classList.remove('dl-pending', 'selected');
    item.classList.add('dl-active');
    item.querySelector('.dl-status-icon').textContent = '⬇';
  }
};

window._onDownloadUpdate = function({ i, artist, title, status, done, total }) {
  const item = missingListEl.querySelector(`[data-index="${i}"]`);
  if (item) {
    item.classList.remove('dl-active', 'dl-pending');
    if (status === 'ok') {
      item.classList.add('dl-ok');
      item.querySelector('.dl-status-icon').textContent = '✓';
    } else if (status === 'not_found') {
      item.classList.add('dl-not-found');
      item.querySelector('.dl-status-icon').textContent = '✗';
      state.notFoundTracks.push(`${artist} — ${title}`);
    } else {
      item.classList.add('dl-fail');
      item.querySelector('.dl-status-icon').textContent = '!';
      state.errorTracks.push(`${artist} — ${title}`);
    }
  }
  setStatus(done < total ? `Downloading ${done} / ${total}…` : 'Finishing up…');
};

window._onDownloadLog = function({ msg }) {
  const line = document.createElement('div');
  const isError = /fail|error|could not|login/i.test(msg);
  if (isError) line.className = 'log-error';
  line.textContent = msg;
  downloadLogEl.appendChild(line);
  downloadLogEl.scrollTop = downloadLogEl.scrollHeight;
};

window._onDownloadsComplete = function({ ok, fail, errors }) {
  state.downloading = false;
  btnCancel.hidden = true;
  btnCancel.disabled = false;
  btnCancel.textContent = 'Cancel';
  btnDownload.hidden = false;
  btnDownload.disabled = false;
  btnCreate.disabled = false;

  const loginErr = errors.find(e => e.toLowerCase().includes('login failed'));
  const wasCancelled = errors.includes('cancelled');
  if (loginErr) {
    setStatus(loginErr, 'error');
  } else if (wasCancelled) {
    setStatus(ok > 0 ? `Cancelled — ${ok} downloaded before stop.` : 'Downloads cancelled.', ok > 0 ? 'ok' : '');
  } else {
    let msg = `Done — ${ok} downloaded`;
    if (fail > 0) msg += `, ${fail} not found`;
    if (ok > 0)   msg += '. Reopen Serato to see changes.';
    setStatus(msg, ok > 0 ? 'ok' : '');
  }

  // Append not-found / error summary to the log panel
  if (state.notFoundTracks.length || state.errorTracks.length) {
    const sep = document.createElement('div');
    sep.style.cssText = 'border-top:1px solid #222;margin:6px 0';
    downloadLogEl.appendChild(sep);

    if (state.notFoundTracks.length) {
      const hdr = document.createElement('div');
      hdr.style.color = '#666';
      hdr.textContent = `Not found on Soulseek (${state.notFoundTracks.length}):`;
      downloadLogEl.appendChild(hdr);
      state.notFoundTracks.forEach(t => {
        const el = document.createElement('div');
        el.style.paddingLeft = '8px';
        el.textContent = t;
        downloadLogEl.appendChild(el);
      });
    }

    if (state.errorTracks.length) {
      const hdr = document.createElement('div');
      hdr.className = 'log-error';
      hdr.textContent = `Errors (${state.errorTracks.length}):`;
      downloadLogEl.appendChild(hdr);
      state.errorTracks.forEach(t => {
        const el = document.createElement('div');
        el.className = 'log-error';
        el.style.paddingLeft = '8px';
        el.textContent = t;
        downloadLogEl.appendChild(el);
      });
    }

    downloadLogEl.scrollTop = downloadLogEl.scrollHeight;
  }

  const nonLoginErrors = errors.filter(e => !e.toLowerCase().includes('login failed') && e !== 'cancelled');
  if (nonLoginErrors.length) {
    console.error('Crate errors:', nonLoginErrors);
  }

  // Update download button label
  btnDownload.textContent = 'Re-download missing songs';
};

// ── Settings modal ────────────────────────────────────────────
function openSettings(onSaveCallback) {
  window.pywebview.api.get_settings().then(s => {
    sUsername.value = s.username || '';
    sPassword.value = '';
    sPassword.placeholder = s.has_password ? '(saved)' : 'password';
    sFolder.value   = s.base_dir || '';
    updateSpotifyStatus(s.spotify_connected);
  });
  modalStatus.textContent = '';
  modalStatus.className = 'modal-status';
  modalOverlay.hidden = false;
  sUsername.focus();

  // store callback for after save
  btnSave._callback = onSaveCallback || null;
}

function updateSpotifyStatus(connected) {
  if (connected) {
    spotifyStatusEl.textContent = '● connected';
    spotifyStatusEl.className = 'spotify-status ok';
  } else {
    spotifyStatusEl.textContent = '● not connected';
    spotifyStatusEl.className = 'spotify-status';
  }
}

btnSettings.addEventListener('click', () => openSettings());
modalClose.addEventListener('click', () => { modalOverlay.hidden = true; });
modalOverlay.addEventListener('mousedown', e => {
  if (e.target === modalOverlay) modalOverlay.hidden = true;
});

btnBrowse.addEventListener('click', async () => {
  const folder = await window.pywebview.api.browse_folder();
  if (folder) sFolder.value = folder;
});

btnSave.addEventListener('click', async () => {
  const u = sUsername.value.trim();
  const p = sPassword.value.trim();
  const f = sFolder.value.trim();
  if (!u) {
    modalStatus.textContent = 'Username is required.';
    modalStatus.className = 'modal-status error';
    return;
  }

  const result = await window.pywebview.api.save_settings(u, p || null, f);
  if (result.error) {
    modalStatus.textContent = 'Error: ' + result.error;
    modalStatus.className = 'modal-status error';
    return;
  }

  modalStatus.textContent = 'Saved.';
  modalStatus.className = 'modal-status ok';
  setTimeout(() => {
    modalOverlay.hidden = true;
    if (btnSave._callback) btnSave._callback();
  }, 600);
});

btnTestConn.addEventListener('click', async () => {
  testConnStatusEl.textContent = 'Testing…';
  testConnStatusEl.className = 'test-conn-status';
  btnTestConn.disabled = true;
  const result = await window.pywebview.api.test_connection();
  btnTestConn.disabled = false;
  if (result.error === 'no_credentials') {
    testConnStatusEl.textContent = '✗ No credentials saved';
    testConnStatusEl.className = 'test-conn-status error';
  } else if (result.error === 'no_sldl') {
    testConnStatusEl.textContent = '✗ sldl not installed';
    testConnStatusEl.className = 'test-conn-status error';
  } else if (result.status === 'login_error') {
    testConnStatusEl.textContent = '✗ Login failed — check credentials';
    testConnStatusEl.className = 'test-conn-status error';
  } else if (result.status === 'failed') {
    testConnStatusEl.textContent = '✗ Could not connect';
    testConnStatusEl.className = 'test-conn-status error';
  } else {
    testConnStatusEl.textContent = '● Connected';
    testConnStatusEl.className = 'test-conn-status ok';
  }
});

btnSpotifyConnect.addEventListener('click', async () => {
  spotifyStatusEl.textContent = 'Opening browser…';
  spotifyStatusEl.className = 'spotify-status';
  const result = await window.pywebview.api.connect_spotify();
  if (result.error) {
    spotifyStatusEl.textContent = 'Error: ' + result.error;
    spotifyStatusEl.className = 'spotify-status error';
  } else {
    updateSpotifyStatus(true);
  }
});

btnSpotifyDisconn.addEventListener('click', async () => {
  await window.pywebview.api.disconnect_spotify();
  updateSpotifyStatus(false);
  // If currently on Spotify source, reload playlists
  if (state.source === 'spotify') loadPlaylists();
});

// ── Helpers ───────────────────────────────────────────────────
function setStatus(msg, type = '') {
  statusEl.textContent = msg;
  statusEl.className = 'status' + (type ? ' ' + type : '');
}

function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
