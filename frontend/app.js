/* ─────────────────────────────────────────────────────────────
   app.js — Playlist → Serato frontend logic
   Communicates with Python via window.pywebview.api.*
───────────────────────────────────────────────────────────── */

// ── State ────────────────────────────────────────────────────
const state = {
  playlists: [],
  unmatched: [],       // [{artist, title}, ...] — parallel to missing-list items
  selectedIndices: new Set(),
  downloading: false,
};

// ── DOM refs ─────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const playlistInput  = $('playlist-input');
const playlistDrop   = $('playlist-dropdown');
const crateInput     = $('crate-input');
const btnCreate      = $('btn-create');
const btnRefresh     = $('btn-refresh');
const btnSettings    = $('btn-settings');
const statusEl       = $('status');
const resultsEl      = $('results');
const trackListEl    = $('track-list');
const statMatched    = $('stat-matched');
const statFuzzy      = $('stat-fuzzy');
const statMissing    = $('stat-missing');
const missingSec     = $('missing-section');
const missingLabel   = $('missing-label');
const missingListEl  = $('missing-list');
const btnDownload    = $('btn-download');
const btnSelectAll   = $('btn-select-all');
const btnSelectNone  = $('btn-select-none');

// Settings modal
const modalOverlay   = $('modal-overlay');
const modalClose     = $('modal-close');
const sUsername      = $('s-username');
const sPassword      = $('s-password');
const sFolder        = $('s-folder');
const btnBrowse      = $('btn-browse');
const btnSave        = $('btn-save-settings');
const modalStatus    = $('modal-status');

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

  window.pywebview.api.get_playlists().then(result => {
    if (result && result.error) {
      setStatus('Error loading playlists: ' + result.error, 'error');
      return;
    }
    state.playlists = result || [];
    playlistInput.disabled = false;
    playlistInput.placeholder = 'Search playlists…';
    btnCreate.disabled = false;
    setStatus('Select a playlist to get started.');
  });
}

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
  if (exists) {
    if (!confirm(`A crate named "${crate}" already exists. Overwrite it?`)) return;
  }

  btnCreate.disabled = true;
  resultsEl.hidden = true;
  setStatus('Loading Serato library…');

  const result = await window.pywebview.api.create_crate(playlist, crate);

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
btnDownload.addEventListener('click', async () => {
  const indices = Array.from(state.selectedIndices);
  if (!indices.length) return;

  const result = await window.pywebview.api.start_downloads(indices);

  if (result.error === 'no_credentials') {
    openSettings(() => {
      // retry after saving credentials
    });
    return;
  }
  if (result.error === 'no_sldl') {
    alert('sldl is not installed.\n\nDownload it from: github.com/fiso64/slsk-batchdl\n\nThen run:\n  sudo codesign --sign - /usr/local/bin/sldl');
    return;
  }
  if (result.error) {
    setStatus('Download error: ' + result.error, 'error');
    return;
  }

  state.downloading = true;
  btnDownload.disabled = true;
  btnCreate.disabled = true;
  setStatus(`Downloading 0 / ${indices.length}…`);

  // Mark selected items as pending
  indices.forEach(i => {
    const item = missingListEl.querySelector(`[data-index="${i}"]`);
    if (item) item.classList.add('dl-pending');
  });
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
    item.classList.add(status === 'ok' ? 'dl-ok' : 'dl-fail');
    item.querySelector('.dl-status-icon').textContent = status === 'ok' ? '✓' : '✗';
  }
  setStatus(done < total ? `Downloading ${done} / ${total}…` : 'Finishing up…');
};

window._onDownloadsComplete = function({ ok, fail, errors }) {
  state.downloading = false;
  btnDownload.disabled = false;
  btnCreate.disabled = false;

  let msg = `Done — ${ok} downloaded`;
  if (fail > 0) msg += `, ${fail} not found`;
  if (ok > 0)   msg += '. Reopen Serato to see changes.';
  setStatus(msg, ok > 0 ? 'ok' : '');

  if (errors.length) {
    console.error('Crate errors:', errors);
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
  });
  modalStatus.textContent = '';
  modalStatus.className = 'modal-status';
  modalOverlay.hidden = false;
  sUsername.focus();

  // store callback for after save
  btnSave._callback = onSaveCallback || null;
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
