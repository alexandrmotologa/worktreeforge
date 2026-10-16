/**
 * WorktreeForge Web Studio JavaScript Client
 */

let state = {
  status: null,
  worktrees: [],
  stashes: [],
  ports: [],
  selectedStashIndex: null,
  activeTab: "worktrees",
  viewMode: "cards",
  logInterval: null,
  activeLogWorktree: null,
};

let ws = null;

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  setupEventListeners();
  connectWebSocket();
  fetchAllData();
});

function setupNavigation() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;
      state.activeTab = target;

      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");

      document.querySelectorAll(".tab-content").forEach((tc) => {
        tc.classList.remove("active");
      });

      const activeContent = document.getElementById(
        `tab${target.charAt(0).toUpperCase() + target.slice(1)}`
      );
      if (activeContent) activeContent.classList.add("active");

      if (target === "compare") {
        populateCompareDropdown();
      }
    });
  });

  // View toggles
  const cardsBtn = document.getElementById("viewCardsBtn");
  const tableBtn = document.getElementById("viewTableBtn");
  const grid = document.getElementById("worktreesGrid");
  const table = document.getElementById("worktreesTableContainer");

  cardsBtn.addEventListener("click", () => {
    cardsBtn.classList.add("active");
    tableBtn.classList.remove("active");
    grid.classList.remove("hidden");
    table.classList.add("hidden");
    state.viewMode = "cards";
  });

  tableBtn.addEventListener("click", () => {
    tableBtn.classList.add("active");
    cardsBtn.classList.remove("active");
    grid.classList.add("hidden");
    table.classList.remove("hidden");
    state.viewMode = "table";
  });
}

function setupEventListeners() {
  document.getElementById("btnRefresh").addEventListener("click", fetchAllData);
  document.getElementById("btnNewWorktree").addEventListener("click", openNewModal);
  document.getElementById("modalCloseBtn").addEventListener("click", closeNewModal);
  document.getElementById("modalCancelBtn").addEventListener("click", closeNewModal);
  document.getElementById("newWorktreeForm").addEventListener("submit", handleNewWorktreeSubmit);
  document.getElementById("btnPruneMerged").addEventListener("click", handlePruneMerged);

  // Search inputs
  document.getElementById("worktreeSearch").addEventListener("input", (e) => {
    renderWorktrees(e.target.value.trim().toLowerCase());
  });

  document.getElementById("stashSearch").addEventListener("input", (e) => {
    renderStashList(e.target.value.trim().toLowerCase());
  });

  // Stash action buttons
  document.getElementById("btnApplyStash").addEventListener("click", () => {
    if (state.selectedStashIndex !== null) applyStash(state.selectedStashIndex, false);
  });
  document.getElementById("btnPopStash").addEventListener("click", () => {
    if (state.selectedStashIndex !== null) applyStash(state.selectedStashIndex, true);
  });
  document.getElementById("btnDropStash").addEventListener("click", () => {
    if (state.selectedStashIndex !== null) dropStash(state.selectedStashIndex);
  });

  // Compare refresh
  document.getElementById("btnRefreshCompare").addEventListener("click", runBranchComparison);
  document.getElementById("compareTargetSelect").addEventListener("change", runBranchComparison);

  // Logs modal
  document.getElementById("logsModalCloseBtn").addEventListener("click", closeLogsModal);
  document.getElementById("logsModalCloseAction").addEventListener("click", closeLogsModal);
}

// WebSocket Connection
function connectWebSocket() {
  const wsStatus = document.getElementById("wsStatus");
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${proto}//${window.location.host}/ws`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    wsStatus.classList.add("connected");
    wsStatus.querySelector(".status-text").textContent = "Live";
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data && data.event) {
        showToast(`Event: ${data.event}`, "info");
        fetchAllData();
      }
    } catch (e) {}
  };

  ws.onclose = () => {
    wsStatus.classList.remove("connected");
    wsStatus.querySelector(".status-text").textContent = "Reconnecting";
    setTimeout(connectWebSocket, 3000);
  };
}

// Data Fetching
async function fetchAllData() {
  try {
    const [statusRes, wtRes, stashesRes, portsRes] = await Promise.all([
      fetch("/api/status").then((r) => r.json()),
      fetch("/api/worktrees").then((r) => r.json()),
      fetch("/api/stashes").then((r) => r.json()),
      fetch("/api/ports?check=true").then((r) => r.json()),
    ]);

    state.status = statusRes;
    state.worktrees = wtRes;
    state.stashes = stashesRes;
    state.ports = portsRes;

    document.getElementById("repoName").textContent = statusRes.repo_name;
    document.getElementById("countWorktrees").textContent = wtRes.length;
    document.getElementById("countStashes").textContent = stashesRes.length;
    document.getElementById("countPorts").textContent = portsRes.length;

    renderWorktrees();
    renderStashList();
    renderPortsTable();
    populateCompareDropdown();
  } catch (error) {
    showToast(`Error fetching data: ${error.message}`, "error");
  }
}

// Worktrees Rendering
function renderWorktrees(filterQuery = "") {
  const grid = document.getElementById("worktreesGrid");
  const tbody = document.getElementById("worktreesTableBody");
  grid.innerHTML = "";
  tbody.innerHTML = "";

  const filtered = state.worktrees.filter((wt) => {
    if (!filterQuery) return true;
    return (
      wt.branch.toLowerCase().includes(filterQuery) ||
      wt.path.toLowerCase().includes(filterQuery)
    );
  });

  if (filtered.length === 0) {
    grid.innerHTML = `<div class="empty-state">No matching worktrees found.</div>`;
    tbody.innerHTML = `<tr><td colspan="7" class="text-center">No matching worktrees.</td></tr>`;
    return;
  }

  filtered.forEach((wt) => {
    // 1. Grid Card
    const card = document.createElement("div");
    card.className = `wt-card ${wt.is_main ? "main-worktree" : ""}`;

    // Status Badge
    let statusBadge = "";
    if (wt.is_locked) {
      statusBadge = `<span class="badge badge-locked">🔒 LOCKED</span>`;
    } else if (wt.is_dirty) {
      statusBadge = `<span class="badge badge-dirty">● DIRTY</span>`;
    } else {
      statusBadge = `<span class="badge badge-clean">✓ CLEAN</span>`;
    }

    // PR Badge
    let prBadge = "";
    if (wt.pr_status && wt.pr_status.state !== "NONE") {
      const numStr = wt.pr_status.number ? ` #${wt.pr_status.number}` : "";
      if (wt.pr_status.state === "MERGED") {
        prBadge = `<span class="badge badge-pr-merged">MERGED${numStr}</span>`;
      } else if (wt.pr_status.state === "OPEN") {
        prBadge = `<span class="badge badge-pr-open">OPEN${numStr}</span>`;
      }
    }

    // Process status
    let serverBadge = "";
    const isRunning = wt.process && wt.process.status === "RUNNING";
    if (isRunning) {
      serverBadge = `<span class="badge badge-server-running">DEV PID ${wt.process.pid}</span>`;
    }

    // Ports
    const portsList = Object.entries(wt.active_ports || {});
    let portsHtml = "";
    if (portsList.length > 0) {
      portsHtml = portsList
        .map(
          ([k, v]) =>
            `<a class="port-pill" onclick="openBrowserForPath('${escapeJsStr(wt.path)}')"><span class="port-dot ${wt.http_ready ? "pulse" : ""}"></span>${k}: <strong>${v}</strong></a>`
        )
        .join("");
    } else {
      portsHtml = `<span class="text-muted text-sm">No ports multiplexed</span>`;
    }

    const folderName = wt.path.split(/[\/\\]/).pop();

    card.innerHTML = `
      <div>
        <div class="wt-card-header">
          <div class="wt-branch-group">
            <span class="wt-branch-name">${escapeHtml(wt.branch)} ${wt.is_main ? '<span class="text-muted text-xs">(main)</span>' : ""}</span>
            <span class="wt-dir-name">${escapeHtml(folderName)}</span>
          </div>
          <div>${statusBadge} ${prBadge} ${serverBadge}</div>
        </div>
        <div class="wt-card-ports">
          ${portsHtml}
        </div>
      </div>
      <div class="wt-card-footer">
        <span class="text-muted text-xs">${escapeHtml(wt.commit_hash.slice(0, 7))}</span>
        <div class="wt-actions-group">
          ${
            isRunning
              ? `<button class="btn btn-warning btn-sm" onclick="stopServer('${escapeJsStr(wt.path)}')">Stop Dev</button>
                 <button class="btn btn-secondary btn-sm" onclick="openLogsModal('${escapeJsStr(wt.path)}', '${escapeJsStr(wt.branch)}')">Logs</button>`
              : `<button class="btn btn-success btn-sm" onclick="startServer('${escapeJsStr(wt.path)}')">Start Dev</button>`
          }
          <button class="btn btn-secondary btn-sm" onclick="openInEditor('${escapeJsStr(wt.path)}')">Editor</button>
          <button class="btn btn-secondary btn-sm" onclick="openBrowserForPath('${escapeJsStr(wt.path)}')">Browser</button>
          ${
            !wt.is_main && (!wt.pr_status || wt.pr_status.state === "NONE")
              ? `<button class="btn btn-secondary btn-sm" onclick="createPR('${escapeJsStr(wt.path)}')">PR</button>`
              : ""
          }
          <button class="btn btn-secondary btn-sm" onclick="toggleLock('${escapeJsStr(wt.path)}', ${wt.is_locked})">${wt.is_locked ? "Unlock" : "Lock"}</button>
          ${!wt.is_main ? `<button class="btn btn-danger btn-sm" onclick="deleteWorktree('${escapeJsStr(wt.path)}')">Delete</button>` : ""}
        </div>
      </div>
    `;
    grid.appendChild(card);

    // 2. Table Row
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${escapeHtml(wt.branch)}</strong> ${wt.is_main ? '<span class="text-muted">(main)</span>' : ""}</td>
      <td class="text-muted text-mono text-sm">${escapeHtml(folderName)}</td>
      <td>${statusBadge}</td>
      <td>${portsHtml}</td>
      <td>${serverBadge || '<span class="text-muted">Stopped</span>'}</td>
      <td>${prBadge || '<span class="text-muted">-</span>'}</td>
      <td>
        <div class="wt-actions-group">
          ${
            isRunning
              ? `<button class="btn btn-warning btn-sm" onclick="stopServer('${escapeJsStr(wt.path)}')">Stop</button>
                 <button class="btn btn-secondary btn-sm" onclick="openLogsModal('${escapeJsStr(wt.path)}', '${escapeJsStr(wt.branch)}')">Logs</button>`
              : `<button class="btn btn-success btn-sm" onclick="startServer('${escapeJsStr(wt.path)}')">Start</button>`
          }
          <button class="btn btn-secondary btn-sm" onclick="openInEditor('${escapeJsStr(wt.path)}')">Editor</button>
          <button class="btn btn-secondary btn-sm" onclick="openBrowserForPath('${escapeJsStr(wt.path)}')">Browser</button>
          <button class="btn btn-secondary btn-sm" onclick="toggleLock('${escapeJsStr(wt.path)}', ${wt.is_locked})">${wt.is_locked ? "Unlock" : "Lock"}</button>
          ${!wt.is_main ? `<button class="btn btn-danger btn-sm" onclick="deleteWorktree('${escapeJsStr(wt.path)}')">Delete</button>` : ""}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// Branch Compare Functions
function populateCompareDropdown() {
  const select = document.getElementById("compareTargetSelect");
  if (!select) return;
  const currentVal = select.value;
  select.innerHTML = "";

  const nonMain = state.worktrees.filter((w) => !w.is_main);
  if (nonMain.length === 0) {
    select.innerHTML = `<option value="">No feature branches available</option>`;
    return;
  }

  nonMain.forEach((w) => {
    const opt = document.createElement("option");
    opt.value = w.path;
    opt.textContent = `${w.branch} (${w.path.split(/[\/\\]/).pop()})`;
    if (w.path === currentVal) opt.selected = true;
    select.appendChild(opt);
  });

  runBranchComparison();
}

async function runBranchComparison() {
  const select = document.getElementById("compareTargetSelect");
  const identifier = select.value;
  if (!identifier) return;

  const diffViewer = document.getElementById("compareDiffViewer");
  diffViewer.innerHTML = "Computing branch differences against main...";

  try {
    const res = await fetch(`/api/compare?identifier=${encodeURIComponent(identifier)}&base=main`);
    if (!res.ok) throw new Error("Comparison query failed");
    const cmp = await res.json();

    document.getElementById("compareAheadPill").textContent = `${cmp.ahead_count} Ahead`;
    document.getElementById("compareBehindPill").textContent = `${cmp.behind_count} Behind`;

    // Commits list
    const commitsUl = document.getElementById("compareCommitsList");
    commitsUl.innerHTML = "";
    if (cmp.commits.length === 0) {
      commitsUl.innerHTML = `<li class="text-muted">No unique commits on branch.</li>`;
    } else {
      cmp.commits.forEach((c) => {
        const li = document.createElement("li");
        li.innerHTML = `<span style="color: var(--accent-yellow)">${c.hash}</span> ${escapeHtml(c.message)} <span class="text-muted">(${escapeHtml(c.author)})</span>`;
        commitsUl.appendChild(li);
      });
    }

    // Changed files
    const filesUl = document.getElementById("compareFilesList");
    filesUl.innerHTML = "";
    if (cmp.changed_files.length === 0) {
      filesUl.innerHTML = `<li class="text-muted">No modified files.</li>`;
    } else {
      cmp.changed_files.forEach((f) => {
        const li = document.createElement("li");
        li.innerHTML = `<span style="color: var(--accent-green)">+${f.insertions}</span> <span style="color: var(--accent-red)">-${f.deletions}</span> ${escapeHtml(f.path)}`;
        filesUl.appendChild(li);
      });
    }

    // Diff
    renderFormattedDiffInElement(cmp.unified_diff, diffViewer);
  } catch (err) {
    diffViewer.textContent = `Error: ${err.message}`;
  }
}

// Dev Server Process Actions
async function startServer(identifier) {
  try {
    const res = await fetch("/api/worktrees/process/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to start server");
    }
    const info = await res.json();
    showToast(`Started dev server (PID: ${info.pid})`, "success");
    fetchAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function stopServer(identifier) {
  try {
    const res = await fetch("/api/worktrees/process/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to stop server");
    }
    showToast("Dev server stopped", "info");
    fetchAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function openLogsModal(identifier, branchName) {
  state.activeLogWorktree = identifier;
  document.getElementById("logsModalTitle").textContent = `Dev Output: ${branchName}`;
  document.getElementById("modalLogs").classList.add("active");
  refreshLogs();

  if (state.logInterval) clearInterval(state.logInterval);
  state.logInterval = setInterval(refreshLogs, 1500);
}

function closeLogsModal() {
  document.getElementById("modalLogs").classList.remove("active");
  if (state.logInterval) {
    clearInterval(state.logInterval);
    state.logInterval = null;
  }
  state.activeLogWorktree = null;
}

async function refreshLogs() {
  if (!state.activeLogWorktree) return;
  try {
    const res = await fetch(
      `/api/worktrees/process/logs?identifier=${encodeURIComponent(state.activeLogWorktree)}&tail=200`
    );
    const data = await res.json();
    const pre = document.getElementById("logsPreText");
    if (!data.logs || data.logs.length === 0) {
      pre.textContent = "No log output recorded yet.";
    } else {
      pre.textContent = data.logs.join("\n");
      const container = document.getElementById("logsConsoleContainer");
      container.scrollTop = container.scrollHeight;
    }
  } catch (err) {}
}

async function openBrowserForPath(identifier) {
  try {
    const res = await fetch("/api/worktrees/browser", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Browser launch failed");
    }
    showToast("Opened localhost in browser", "success");
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function createPR(identifier) {
  if (!confirm("Create a GitHub Pull Request for this branch?")) return;
  try {
    showToast("Creating Pull Request on GitHub...", "info");
    const res = await fetch("/api/worktrees/pr/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to create PR");
    }
    const data = await res.json();
    showToast(`Created PR: ${data.url}`, "success");
    fetchAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// Stash Rendering
function renderStashList(filterQuery = "") {
  const list = document.getElementById("stashList");
  list.innerHTML = "";

  const filtered = state.stashes.filter((s) => {
    if (!filterQuery) return true;
    return (
      s.message.toLowerCase().includes(filterQuery) ||
      s.branch.toLowerCase().includes(filterQuery) ||
      s.author.toLowerCase().includes(filterQuery)
    );
  });

  if (filtered.length === 0) {
    list.innerHTML = `<div class="p-4 text-muted">No stashes found.</div>`;
    return;
  }

  filtered.forEach((s) => {
    const item = document.createElement("div");
    item.className = `stash-item ${state.selectedStashIndex === s.index ? "active" : ""}`;
    item.innerHTML = `
      <div class="stash-item-id">${s.id}</div>
      <div class="stash-item-msg">${escapeHtml(s.message)}</div>
      <div class="stash-item-meta">
        <span>${escapeHtml(s.branch)}</span>
        <span>${s.files.length} file(s)</span>
      </div>
    `;
    item.addEventListener("click", () => selectStash(s.index));
    list.appendChild(item);
  });

  if (state.selectedStashIndex === null && filtered.length > 0) {
    selectStash(filtered[0].index);
  }
}

async function selectStash(index) {
  state.selectedStashIndex = index;
  renderStashList(document.getElementById("stashSearch").value.trim().toLowerCase());

  const stash = state.stashes.find((s) => s.index === index);
  if (!stash) return;

  document.getElementById("detailStashId").textContent = stash.id;
  document.getElementById("detailStashBranch").textContent = `Branch: ${stash.branch} | Author: ${stash.author}`;
  document.getElementById("detailActions").style.display = "flex";

  const diffViewer = document.getElementById("diffViewer");
  diffViewer.innerHTML = "Loading diff...";

  try {
    const res = await fetch(`/api/stashes/${index}/diff`);
    if (!res.ok) throw new Error("Failed to load diff");
    const diffData = await res.json();

    renderFormattedDiffInElement(diffData.raw_diff, diffViewer);
  } catch (err) {
    diffViewer.textContent = `Error: ${err.message}`;
  }
}

function renderFormattedDiffInElement(rawDiff, el) {
  if (!rawDiff || !rawDiff.trim()) {
    el.innerHTML = `<span class="text-muted">Empty diff.</span>`;
    return;
  }

  const lines = rawDiff.split("\n");
  const formatted = lines.map((line) => {
    if (line.startsWith("+") && !line.startsWith("+++")) {
      return `<span class="diff-add">${escapeHtml(line)}</span>`;
    } else if (line.startsWith("-") && !line.startsWith("---")) {
      return `<span class="diff-del">${escapeHtml(line)}</span>`;
    } else if (line.startsWith("@@")) {
      return `<span class="diff-hunk">${escapeHtml(line)}</span>`;
    }
    return escapeHtml(line);
  });

  el.innerHTML = `<code>${formatted.join("\n")}</code>`;
}

// Ports Rendering
function renderPortsTable() {
  const tbody = document.getElementById("portsTableBody");
  tbody.innerHTML = "";

  if (state.ports.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No ports multiplexed.</td></tr>`;
    return;
  }

  state.ports.forEach((p) => {
    const statusHtml = p.is_socket_listening
      ? `<span class="badge badge-locked">LISTENING</span>`
      : `<span class="badge badge-clean">AVAILABLE</span>`;

    const folderName = p.worktree_path.split(/[\/\\]/).pop();

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${escapeHtml(p.branch)}</strong></td>
      <td><span class="text-mono">${escapeHtml(p.port_variable)}</span></td>
      <td>${p.base_port}</td>
      <td><strong style="color: var(--accent-yellow)">${p.allocated_port}</strong></td>
      <td>${statusHtml}</td>
      <td class="text-muted text-mono text-sm">${escapeHtml(folderName)}</td>
    `;
    tbody.appendChild(tr);
  });
}

// Actions
async function openInEditor(path) {
  try {
    const res = await fetch("/api/worktrees/open-editor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    const data = await res.json();
    if (data.success) {
      showToast("Opened in code editor", "success");
    } else {
      showToast("No editor (code/cursor) found in PATH", "warning");
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function toggleLock(identifier, isLocked) {
  const endpoint = isLocked ? "/api/worktrees/unlock" : "/api/worktrees/lock";
  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Action failed");
    }
    showToast(isLocked ? "Unlocked worktree" : "Locked worktree", "success");
    fetchAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function deleteWorktree(identifier) {
  if (!confirm(`Are you sure you want to remove worktree '${identifier}'?`)) return;

  try {
    const res = await fetch("/api/worktrees", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier, force: true }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Deletion failed");
    }
    showToast("Worktree removed successfully", "success");
    fetchAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function handlePruneMerged() {
  if (!confirm("Prune all worktrees with merged GitHub PRs?")) return;

  try {
    const res = await fetch("/api/worktrees/prune", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dry_run: false }),
    });
    const results = await res.json();
    const prunedCount = results.filter((r) => r.success).length;
    showToast(`Pruned ${prunedCount} merged worktree(s)`, "success");
    fetchAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function applyStash(index, drop = false) {
  try {
    const res = await fetch(`/api/stashes/${index}/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ drop }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to apply stash");
    }
    showToast(drop ? "Popped stash" : "Applied stash", "success");
    fetchAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function dropStash(index) {
  if (!confirm(`Permanently drop stash@{${index}}?`)) return;

  try {
    const res = await fetch(`/api/stashes/${index}/drop`, {
      method: "POST",
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to drop stash");
    }
    showToast("Dropped stash", "success");
    state.selectedStashIndex = null;
    fetchAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// Modal
function openNewModal() {
  document.getElementById("modalNewWorktree").classList.add("active");
  document.getElementById("newBranchName").focus();
}

function closeNewModal() {
  document.getElementById("modalNewWorktree").classList.remove("active");
  document.getElementById("newWorktreeForm").reset();
}

async function handleNewWorktreeSubmit(e) {
  e.preventDefault();
  const branch = document.getElementById("newBranchName").value.trim();
  const base_ref = document.getElementById("newBaseRef").value.trim() || null;
  const offsetStr = document.getElementById("newPortOffset").value.trim();
  const port_offset = offsetStr ? parseInt(offsetStr, 10) : null;
  const configure_ports = document.getElementById("checkConfigurePorts").checked;
  const link_deps = document.getElementById("checkLinkDeps").checked;
  const open_editor = document.getElementById("checkOpenEditor").checked;

  const btn = document.getElementById("btnSubmitNewWorktree");
  btn.disabled = true;
  btn.textContent = "Provisioning...";

  try {
    const res = await fetch("/api/worktrees", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        branch,
        base_ref,
        port_offset,
        configure_ports,
        link_deps,
        open_editor,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Provisioning failed");
    }
    showToast(`Worktree '${branch}' created successfully`, "success");
    closeNewModal();
    fetchAllData();
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Provision Worktree";
  }
}

// Helpers
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeJsStr(str) {
  if (!str) return "";
  return String(str).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}
