/**
 * SAM.gov Settings Form Controller
 * Manages the SAM.gov connection form and sync settings UI.
 */

(function() {
  'use strict';

  const API_BASE = '/api/v1/sam-gov';

  // ============================================================
  // Helpers
  // ============================================================

  function getToken() {
    return localStorage.getItem('access_token');
  }

  async function apiCall(method, endpoint, body = null) {
    const options = {
      method,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}`,
      },
    };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(`${API_BASE}${endpoint}`, options);
    if (response.status === 401) {
      window.location.href = '/login';
      return;
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    return data;
  }

  function formatDateTime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString();
  }

  function formatDuration(ms) {
    if (ms == null) return '—';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  function showError(message, field = null) {
    if (field) {
      const input = document.getElementById(field);
      const errorDiv = document.getElementById(`${field}_error`);
      if (input) input.classList.add('is-invalid');
      if (errorDiv) errorDiv.textContent = message;
    } else {
      alert(`Error: ${message}`);
    }
  }

  function clearErrors() {
    document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
  }

  // ============================================================
  // Status Display
  // ============================================================

  async function loadStatus() {
    try {
      const data = await apiCall('GET', '/settings');

      const statusDiv = document.getElementById('status-display');
      const connectCard = document.getElementById('connect-card');
      const syncCard = document.getElementById('sync-settings-card');
      const manualCard = document.getElementById('manual-sync-card');
      const disconnectCard = document.getElementById('disconnect-card');
      const historyCard = document.getElementById('history-card');

      if (!data.connected) {
        statusDiv.innerHTML = `
          <p class="status-disconnected mb-0">
            <i class="bi bi-x-circle-fill"></i>
            <strong>Not connected</strong> — Connect your SAM.gov account to enable automated solicitation fetching.
          </p>
        `;
        connectCard.style.display = 'block';
        syncCard.style.display = 'none';
        manualCard.style.display = 'none';
        disconnectCard.style.display = 'none';
        historyCard.style.display = 'none';
        return;
      }

      const creds = data.credentials;
      const statusClass = creds.last_test_success ? 'status-connected' : 'status-error';
      const statusIcon = creds.last_test_success ? 'bi-check-circle-fill' : 'bi-exclamation-circle-fill';
      const statusText = creds.last_test_success ? 'Connected' : 'Error';

      statusDiv.innerHTML = `
        <p class="${statusClass} mb-2">
          <i class="bi ${statusIcon}"></i>
          <strong>${statusText}</strong> — Entity ID: <code>${creds.entity_id}</code> (key ending ...${creds.api_key_last4})
        </p>
        <small class="text-muted">
          Last tested: ${formatDateTime(creds.last_test_at)}
          ${creds.last_test_error ? `<br><span class="text-danger">Error: ${creds.last_test_error}</span>` : ''}
          ${creds.last_sync_at ? `<br>Last sync: ${formatDateTime(creds.last_sync_at)} (${creds.sync_count} total syncs)` : ''}
        </small>
        <div class="mt-3">
          <button class="btn btn-sm btn-outline-primary" id="test-btn">
            <i class="bi bi-broadcast"></i> Test Connection
          </button>
        </div>
      `;

      connectCard.style.display = 'none';
      syncCard.style.display = 'block';
      manualCard.style.display = 'block';
      disconnectCard.style.display = 'block';
      historyCard.style.display = 'block';

      // Populate sync settings
      const sync = data.sync_settings;
      document.getElementById('auto_sync_enabled').checked = sync.auto_sync_enabled || false;
      document.getElementById('sync_interval_hours').value = sync.sync_interval_hours || 24;
      document.getElementById('naics_codes').value = (sync.naics_codes || []).join(', ');
      document.getElementById('keywords').value = (sync.keywords || []).join(', ');
      document.getElementById('min_value').value = sync.min_value || '';
      document.getElementById('max_value').value = sync.max_value || '';

      // Wire up test button
      document.getElementById('test-btn').addEventListener('click', testConnection);

      // Load history
      loadHistory();
      loadSyncStatus();
    } catch (error) {
      console.error('Load status error:', error);
      document.getElementById('status-display').innerHTML = `
        <p class="text-danger">
          <i class="bi bi-exclamation-triangle"></i>
          Failed to load status: ${error.message}
        </p>
      `;
    }
  }

  // ============================================================
  // Connect / Disconnect
  // ============================================================

  document.getElementById('connect-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors();

    const apiKey = document.getElementById('api_key').value.trim();
    const entityId = document.getElementById('entity_id').value.trim().toUpperCase();
    const testFirst = document.getElementById('test_connection').checked;

    // Client-side validation
    if (apiKey.length < 32) {
      showError('API key must be at least 32 characters', 'api_key');
      return;
    }
    if (!/^[A-Z0-9]{12}$/.test(entityId)) {
      showError('Entity ID must be 12 alphanumeric characters', 'entity_id');
      return;
    }

    const btn = document.getElementById('connect-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Connecting...';

    try {
      const data = await apiCall('POST', '/connect', {
        api_key: apiKey,
        entity_id: entityId,
        test_connection: testFirst,
      });

      alert('✓ SAM.gov connected successfully!');
      // Clear the API key field for security
      document.getElementById('api_key').value = '';
      document.getElementById('entity_id').value = '';
      loadStatus();
    } catch (error) {
      if (error.message.includes('API key')) {
        showError(error.message, 'api_key');
      } else if (error.message.includes('Entity ID')) {
        showError(error.message, 'entity_id');
      } else {
        alert(`Connection failed: ${error.message}`);
      }
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-plug"></i> Connect SAM.gov';
    }
  });

  document.getElementById('disconnect-btn')?.addEventListener('click', async () => {
    if (!confirm('Are you sure you want to disconnect SAM.gov? Your credentials will be permanently deleted.')) {
      return;
    }

    try {
      await apiCall('POST', '/disconnect');
      alert('SAM.gov disconnected');
      loadStatus();
    } catch (error) {
      alert(`Disconnect failed: ${error.message}`);
    }
  });

  // ============================================================
  // Test Connection
  // ============================================================

  async function testConnection() {
    const btn = document.getElementById('test-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Testing...';

    try {
      const result = await apiCall('POST', '/test', {});
      if (result.success) {
        alert(`✓ Connection successful! Latency: ${result.latency_ms}ms`);
      } else {
        alert(`✗ Connection failed: ${result.error}`);
      }
      loadStatus();
    } catch (error) {
      alert(`Test failed: ${error.message}`);
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-broadcast"></i> Test Connection';
    }
  }

  // ============================================================
  // Sync Settings
  // ============================================================

  document.getElementById('sync-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const settings = {
      auto_sync_enabled: document.getElementById('auto_sync_enabled').checked,
      sync_interval_hours: parseInt(document.getElementById('sync_interval_hours').value),
      naics_codes: document.getElementById('naics_codes').value
        .split(',').map(s => s.trim()).filter(s => /^\d{6}$/.test(s)),
      keywords: document.getElementById('keywords').value
        .split(',').map(s => s.trim()).filter(s => s),
      min_value: parseInt(document.getElementById('min_value').value) || null,
      max_value: parseInt(document.getElementById('max_value').value) || null,
    };

    const btn = document.getElementById('save-sync-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Saving...';

    try {
      await apiCall('PATCH', '/settings', settings);
      alert('✓ Sync settings saved');
    } catch (error) {
      alert(`Save failed: ${error.message}`);
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-save"></i> Save Sync Settings';
    }
  });

  // ============================================================
  // Manual Sync
  // ============================================================

  document.getElementById('sync-btn')?.addEventListener('click', async () => {
    const btn = document.getElementById('sync-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Starting sync...';

    try {
      const result = await apiCall('POST', '/sync', {});
      alert(`✓ ${result.message} (sync_id: ${result.sync_id})`);
      loadSyncStatus();

      // Poll status every 5s
      const pollInterval = setInterval(async () => {
        const status = await loadSyncStatus();
        if (status && (status.status === 'success' || status.status === 'failed')) {
          clearInterval(pollInterval);
          loadHistory();
        }
      }, 5000);
    } catch (error) {
      alert(`Sync failed: ${error.message}`);
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Sync Now';
    }
  });

  async function loadSyncStatus() {
    try {
      const data = await apiCall('GET', '/sync-status');
      const display = document.getElementById('sync-status-display');

      if (!data.has_sync) {
        display.innerHTML = '<p class="text-muted">No syncs yet.</p>';
        return;
      }

      const sync = data.sync;
      const statusClass = {
        running: 'text-primary',
        success: 'text-success',
        failed: 'text-danger',
      }[sync.status] || 'text-muted';

      display.innerHTML = `
        <div class="alert alert-light">
          <strong class="${statusClass}">Status: ${sync.status.toUpperCase()}</strong>
          ${sync.status === 'running' ? '<span class="spinner-border spinner-border-sm ms-2"></span>' : ''}
          <br>
          <small>
            Started: ${formatDateTime(sync.started_at)}<br>
            ${sync.completed_at ? `Completed: ${formatDateTime(sync.completed_at)} (${formatDuration(sync.duration_ms)})<br>` : ''}
            Solicitations fetched: ${sync.solicitations_fetched}
            ${sync.error_message ? `<br><span class="text-danger">Error: ${sync.error_message}</span>` : ''}
          </small>
        </div>
      `;
      return sync;
    } catch (error) {
      console.error('Load sync status error:', error);
    }
  }

  // ============================================================
  // Sync History
  // ============================================================

  async function loadHistory() {
    try {
      const data = await apiCall('GET', '/sync-history?limit=10');
      const tbody = document.getElementById('history-tbody');

      if (!data.syncs || data.syncs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No syncs yet</td></tr>';
        return;
      }

      tbody.innerHTML = data.syncs.map(sync => {
        const statusBadge = {
          running: '<span class="badge bg-primary">Running</span>',
          success: '<span class="badge bg-success">Success</span>',
          failed: '<span class="badge bg-danger">Failed</span>',
        }[sync.status] || `<span class="badge bg-secondary">${sync.status}</span>`;

        return `
          <tr>
            <td><small>${formatDateTime(sync.started_at)}</small></td>
            <td>${statusBadge}</td>
            <td>${sync.solicitations_fetched}</td>
            <td>${formatDuration(sync.duration_ms)}</td>
          </tr>
        `;
      }).join('');
    } catch (error) {
      console.error('Load history error:', error);
    }
  }

  // ============================================================
  // Init
  // ============================================================

  document.addEventListener('DOMContentLoaded', () => {
    if (!getToken()) {
      window.location.href = '/login';
      return;
    }
    loadStatus();
  });
})();
