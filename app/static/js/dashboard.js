/**
 * Real-Time Dashboard Controller
 * - Single-click automation start
 * - WebSocket + polling fallback for real-time updates
 * - 5-step progress visualization
 * - Live agent logs with color-coding
 * - Theme toggle (dark/light mode)
 * - Results export
 */

(function() {
  'use strict';

  // ============================================================
  // Configuration
  // ============================================================

  const CONFIG = {
    API_BASE: '/api/v1',
    POLL_INTERVAL_MS: 2000,
    WEBSOCKET_RECONNECT_DELAY_MS: 3000,
    MAX_LOG_ENTRIES: 500,
    ANIMATION_DURATION_MS: 300
  };

  const STEPS = [
    { id: 1, name: 'SamGovAgent', label: 'SAM.gov Scraping' },
    { id: 2, name: 'AttachmentReaderAgent', label: 'RFQ Generation' },
    { id: 3, name: 'RFQParser', label: 'Product Extraction' },
    { id: 4, name: 'VendorSearchAgent', label: 'Vendor Search' },
    { id: 5, name: 'SubmissionAgent', label: 'RFQ Submission' }
  ];

  // ============================================================
  // State
  // ============================================================

  const state = {
    accessToken: localStorage.getItem('access_token'),
    refreshToken: localStorage.getItem('refresh_token'),
    currentRunId: null,
    pollTimer: null,
    socket: null,
    isRunning: false,
    currentStep: 0,
    completedSteps: new Set(),
    failedSteps: new Set(),
    agentLogs: [],
    runStartTime: null
  };

  // ============================================================
  // Utility Functions
  // ============================================================

  function getAuthHeaders() {
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${state.accessToken}`
    };
  }

  function formatDuration(seconds) {
    if (seconds == null) return '—';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  }

  function formatDateTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString();
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // ============================================================
  // API Client
  // ============================================================

  async function apiCall(method, endpoint, body = null) {
    const url = `${CONFIG.API_BASE}${endpoint}`;
    const options = {
      method,
      headers: getAuthHeaders()
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(url, options);

      if (response.status === 401) {
        await refreshAccessToken();
        return apiCall(method, endpoint, body);
      }

      if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'Request failed' }));
        throw new Error(error.error || error.message || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API call failed: ${method} ${endpoint}`, error);
      throw error;
    }
  }

  async function refreshAccessToken() {
    if (!state.refreshToken) {
      redirectToLogin();
      return;
    }

    try {
      const response = await fetch(`${CONFIG.API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${state.refreshToken}`
        }
      });

      if (!response.ok) {
        redirectToLogin();
        return;
      }

      const data = await response.json();
      state.accessToken = data.access_token;
      localStorage.setItem('access_token', data.access_token);
    } catch (error) {
      console.error('Token refresh failed:', error);
      redirectToLogin();
    }
  }

  function redirectToLogin() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/login';
  }

  // ============================================================
  // Theme Management
  // ============================================================

  function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    updateThemeIcon(next);
  }

  function updateThemeIcon(theme) {
    const icon = document.querySelector('#theme-toggle i');
    if (icon) {
      icon.className = theme === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars';
    }
  }

  // ============================================================
  // Log Display
  // ============================================================

  function appendLog(level, message, timestamp = new Date()) {
    const logsContainer = document.getElementById('logs-container');
    if (!logsContainer) return;

    const timeStr = timestamp.toLocaleTimeString();
    const safeMessage = escapeHtml(message);
    const logClass = level.toLowerCase();

    const entry = document.createElement('div');
    entry.className = `log-entry ${logClass}`;
    entry.innerHTML = `<span style="opacity: 0.6;">[${timeStr}]</span> [${level.toUpperCase()}] ${safeMessage}`;

    logsContainer.appendChild(entry);

    // Keep only last N entries
    while (logsContainer.children.length > CONFIG.MAX_LOG_ENTRIES) {
      logsContainer.removeChild(logsContainer.firstChild);
    }

    // Auto-scroll
    logsContainer.scrollTop = logsContainer.scrollHeight;
  }

  function clearLogs() {
    const logsContainer = document.getElementById('logs-container');
    if (logsContainer) {
      logsContainer.innerHTML = '<div class="log-entry info">[INFO] Logs cleared.</div>';
    }
  }

  // ============================================================
  // Step Visualization
  // ============================================================

  function resetSteps() {
    state.completedSteps.clear();
    state.failedSteps.clear();
    state.currentStep = 0;

    for (let i = 1; i <= 5; i++) {
      const step = document.querySelector(`.step[data-step="${i}"]`);
      if (step) {
        step.classList.remove('active', 'success', 'failed');
      }
    }

    document.getElementById('progress-fill').style.width = '0%';
    document.getElementById('progress-percent').textContent = '0%';
  }

  function setStepActive(stepNum) {
    state.currentStep = stepNum;
    const step = document.querySelector(`.step[data-step="${stepNum}"]`);
    if (step) {
      step.classList.add('active');
      step.classList.remove('success', 'failed');
    }
    updateProgress((stepNum - 1) * 20);
  }

  function setStepSuccess(stepNum) {
    state.completedSteps.add(stepNum);
    const step = document.querySelector(`.step[data-step="${stepNum}"]`);
    if (step) {
      step.classList.remove('active', 'failed');
      step.classList.add('success');
    }
    updateProgress(stepNum * 20);
  }

  function setStepFailed(stepNum) {
    state.failedSteps.add(stepNum);
    const step = document.querySelector(`.step[data-step="${stepNum}"]`);
    if (step) {
      step.classList.remove('active', 'success');
      step.classList.add('failed');
    }
  }

  function updateProgress(percent) {
    const fill = document.getElementById('progress-fill');
    const label = document.getElementById('progress-percent');
    if (fill && label) {
      fill.style.width = `${percent}%`;
      label.textContent = `${Math.round(percent)}%`;
    }
  }

  // ============================================================
  // WebSocket Connection
  // ============================================================

  function connectWebSocket(runId) {
    if (typeof io === 'undefined') {
      appendLog('info', 'WebSocket unavailable, using polling');
      return false;
    }

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}`;

      state.socket = io(wsUrl, {
        query: { run_id: runId, token: state.accessToken },
        transports: ['websocket', 'polling']
      });

      state.socket.on('connect', () => {
        appendLog('success', 'Real-time connection established');
      });

      state.socket.on('agent_log', (data) => {
        if (data.log) {
          appendLog(data.log.level || 'info', data.log.message, new Date(data.log.timestamp));
        }
        if (data.step) {
          if (data.step.status === 'running') {
            setStepActive(data.step.number);
          } else if (data.step.status === 'success') {
            setStepSuccess(data.step.number);
          } else if (data.step.status === 'failed') {
            setStepFailed(data.step.number);
          }
        }
      });

      state.socket.on('disconnect', () => {
        appendLog('info', 'Real-time connection lost, falling back to polling');
      });

      state.socket.on('connect_error', (error) => {
        console.warn('WebSocket error:', error);
        appendLog('info', 'Real-time unavailable, using polling');
      });

      return true;
    } catch (error) {
      console.error('WebSocket connection failed:', error);
      return false;
    }
  }

  function disconnectWebSocket() {
    if (state.socket) {
      state.socket.disconnect();
      state.socket = null;
    }
  }

  // ============================================================
  // Polling
  // ============================================================

  function startPolling(runId) {
    stopPolling();

    state.pollTimer = setInterval(async () => {
      try {
        const status = await apiCall('GET', `/automation/${runId}`);
        processAutomationStatus(status);
      } catch (error) {
        appendLog('error', `Polling failed: ${error.message}`);
      }
    }, CONFIG.POLL_INTERVAL_MS);
  }

  function stopPolling() {
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  function processAutomationStatus(status) {
    if (!status) return;

    // Update step visualization based on agent logs
    if (status.agent_logs && status.agent_logs.length > 0) {
      for (const log of status.agent_logs) {
        if (log.status === 'success' && !state.completedSteps.has(log.step_number)) {
          setStepSuccess(log.step_number);
          appendLog('success', `${log.agent_name} completed in ${log.duration_ms}ms`);
        } else if (log.status === 'running' && state.currentStep < log.step_number) {
          setStepActive(log.step_number);
          appendLog('info', `${log.agent_name} is running (attempt ${log.attempt_number})`);
        } else if (log.status === 'retry') {
          appendLog('retry', `${log.agent_name} retrying (attempt ${log.attempt_number}/${log.retry_count_max}): ${log.error_message || 'transient error'}`);
        } else if (log.status === 'failed' && !state.failedSteps.has(log.step_number)) {
          setStepFailed(log.step_number);
          appendLog('error', `${log.agent_name} failed: ${log.error_message}`);
        }
      }
    }

    // Update progress bar
    if (status.progress_percent != null) {
      updateProgress(status.progress_percent);
    }

    // Check completion
    if (status.status === 'completed' || status.status === 'failed' || status.status === 'completed_with_errors') {
      onAutomationComplete(status);
    }
  }

  // ============================================================
  // Automation Control
  // ============================================================

  async function startAutomation() {
    if (state.isRunning) return;

    try {
      const startBtn = document.getElementById('start-btn');
      startBtn.disabled = true;
      startBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Starting...';

      state.isRunning = true;
      state.runStartTime = new Date();

      // Show progress section
      document.getElementById('progress-section').style.display = 'block';
      resetSteps();
      clearLogs();
      appendLog('info', 'Starting automation workflow...');

      // Start automation via API
      const result = await apiCall('POST', '/automation/start', {});
      state.currentRunId = result.run_id;

      appendLog('success', `Automation queued. Run ID: ${result.run_id}`);

      // Update button
      startBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Running...';

      // Try WebSocket first, fall back to polling
      const wsConnected = connectWebSocket(result.run_id);
      if (!wsConnected) {
        appendLog('info', 'Using polling for real-time updates');
        startPolling(result.run_id);
      }
    } catch (error) {
      appendLog('error', `Failed to start: ${error.message}`);
      state.isRunning = false;
      const startBtn = document.getElementById('start-btn');
      startBtn.disabled = false;
      startBtn.innerHTML = '<i class="bi bi-rocket-takeoff-fill"></i> Start Automation';
    }
  }

  async function cancelAutomation() {
    if (!state.currentRunId) return;

    try {
      await apiCall('DELETE', `/automation/${state.currentRunId}`);
      appendLog('info', 'Automation cancelled');
      onAutomationComplete({ status: 'cancelled' });
    } catch (error) {
      appendLog('error', `Cancel failed: ${error.message}`);
    }
  }

  function onAutomationComplete(status) {
    stopPolling();
    disconnectWebSocket();

    state.isRunning = false;
    const startBtn = document.getElementById('start-btn');
    if (startBtn) {
      startBtn.disabled = false;
      startBtn.innerHTML = '<i class="bi bi-rocket-takeoff-fill"></i> Start Automation';
    }

    if (status.status === 'completed' || status.status === 'completed_with_errors') {
      const results = status.results || {};
      appendLog('success', `Automation complete! ${results.solicitations_found || 0} solicitations, ${results.rfqs_generated || 0} RFQs, ${results.vendors_found || 0} vendors, ${results.submissions_sent || 0} submissions`);
      updateProgress(100);
      showCompletionModal(results);
    } else if (status.status === 'failed') {
      appendLog('error', `Automation failed: ${status.error_message || 'Unknown error'}`);
    } else if (status.status === 'cancelled') {
      appendLog('info', 'Automation cancelled by user');
    }

    // Refresh dashboard data
    loadDashboardStats();
    loadRecentRuns();
  }

  // ============================================================
  // Dashboard Data Loading
  // ============================================================

  async function loadDashboardStats() {
    try {
      const stats = await apiCall('GET', '/dashboard/stats');

      document.getElementById('stat-runs').textContent = stats.automations?.total || 0;
      const successRate = stats.automations?.success_rate_percent || 0;
      document.getElementById('stat-success').textContent = `${Math.round(successRate)}%`;
      document.getElementById('stat-rfqs').textContent = stats.rfqs?.total || 0;
      document.getElementById('stat-vendors').textContent = stats.vendors?.total || 0;
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  }

  async function loadRecentRuns() {
    try {
      const data = await apiCall('GET', '/automation/history?limit=10&page=1');
      const tbody = document.getElementById('recent-runs-tbody');
      if (!tbody) return;

      if (!data.runs || data.runs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No runs yet</td></tr>';
        return;
      }

      tbody.innerHTML = data.runs.map(run => {
        const statusBadge = getStatusBadge(run.status);
        const results = run.results || {};
        return `
          <tr>
            <td>#${run.id}</td>
            <td>${statusBadge}</td>
            <td>${formatDateTime(run.created_at)}</td>
            <td>${formatDuration(run.duration_seconds)}</td>
            <td>${results.solicitations_found || 0} / ${results.rfqs_generated || 0} / ${results.vendors_found || 0} / ${results.submissions_sent || 0}</td>
            <td>
              <button class="btn btn-sm btn-outline-primary" onclick="viewRunDetails(${run.id})">
                <i class="bi bi-eye"></i> View
              </button>
            </td>
          </tr>
        `;
      }).join('');
    } catch (error) {
      console.error('Failed to load recent runs:', error);
    }
  }

  function getStatusBadge(status) {
    const map = {
      'completed': '<span class="badge bg-success">Completed</span>',
      'running': '<span class="badge bg-primary">Running</span>',
      'queued': '<span class="badge bg-info">Queued</span>',
      'failed': '<span class="badge bg-danger">Failed</span>',
      'completed_with_errors': '<span class="badge bg-warning">Partial</span>',
      'cancelled': '<span class="badge bg-secondary">Cancelled</span>'
    };
    return map[status] || `<span class="badge bg-secondary">${status}</span>`;
  }

  function viewRunDetails(runId) {
    window.location.href = `/runs/${runId}`;
  }

  // ============================================================
  // User Info
  // ============================================================

  async function loadUserInfo() {
    try {
      const data = await apiCall('GET', '/auth/me');
      const tenantInfo = document.getElementById('tenant-info');
      if (tenantInfo) {
        tenantInfo.textContent = `${data.tenant.name} (${data.tenant.subscription_tier})`;
      }
    } catch (error) {
      console.error('Failed to load user info:', error);
    }
  }

  // ============================================================
  // Modals
  // ============================================================

  function showCompletionModal(results) {
    const modal = document.getElementById('completion-modal');
    if (!modal) return;

    document.getElementById('modal-solicitations').textContent = results.solicitations_found || 0;
    document.getElementById('modal-rfqs').textContent = results.rfqs_generated || 0;
    document.getElementById('modal-vendors').textContent = results.vendors_found || 0;
    document.getElementById('modal-submissions').textContent = results.submissions_sent || 0;

    modal.classList.add('show');
  }

  function hideCompletionModal() {
    const modal = document.getElementById('completion-modal');
    if (modal) {
      modal.classList.remove('show');
    }
  }

  // ============================================================
  // Logout
  // ============================================================

  async function logout() {
    try {
      await apiCall('POST', '/auth/logout');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
    }
  }

  // ============================================================
  // Event Listeners
  // ============================================================

  document.addEventListener('DOMContentLoaded', () => {
    if (!state.accessToken) {
      redirectToLogin();
      return;
    }

    initTheme();

    // Wire up event listeners
    document.getElementById('start-btn')?.addEventListener('click', startAutomation);
    document.getElementById('cancel-btn')?.addEventListener('click', cancelAutomation);
    document.getElementById('clear-logs-btn')?.addEventListener('click', clearLogs);
    document.getElementById('theme-toggle')?.addEventListener('click', toggleTheme);
    document.getElementById('logout-btn')?.addEventListener('click', logout);
    document.getElementById('modal-close-btn')?.addEventListener('click', hideCompletionModal);
    document.getElementById('modal-view-btn')?.addEventListener('click', () => {
      if (state.currentRunId) {
        viewRunDetails(state.currentRunId);
      }
    });

    // Initial data load
    loadUserInfo();
    loadDashboardStats();
    loadRecentRuns();

    // Refresh stats every 30 seconds
    setInterval(() => {
      if (!state.isRunning) {
        loadDashboardStats();
        loadRecentRuns();
      }
    }, 30000);
  });

  // Expose for inline handlers
  window.viewRunDetails = viewRunDetails;
})();
