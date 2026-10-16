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
    tbody.innerHTML = `<tr><td colspan="6" class="text-center">No matching worktrees.</td></tr>`;
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

    // Ports
    const portsList = Object.entries(wt.active_ports || {});
    let portsHtml = "";
    if (portsList.length > 0) {
      portsHtml = portsList
        .map(
          ([k, v]) =>
            `<span class="port-pill"><span class="port-dot"></span>${k}: <strong>${v}</strong></span>`
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
          <div>${statusBadge} ${prBadge}</div>
        </div>
        <div class="wt-card-ports">
          ${portsHtml}
        </div>
      </div>
      <div class="wt-card-footer">
        <span class="text-muted text-xs">${escapeHtml(wt.commit_hash.slice(0, 7))}</span>
        <div class="wt-actions-group">
          <button class="btn btn-secondary btn-sm" onclick="openInEditor('${escapeJsStr(wt.path)}')">Editor</button>
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
      <td>${prBadge || '<span class="text-muted">-</span>'}</td>
      <td>
        <div class="wt-actions-group">
          <button class="btn btn-secondary btn-sm" onclick="openInEditor('${escapeJsStr(wt.path)}')">Editor</button>
          <button class="btn btn-secondary btn-sm" onclick="toggleLock('${escapeJsStr(wt.path)}', ${wt.is_locked})">${wt.is_locked ? "Unlock" : "Lock"}</button>
          ${!wt.is_main ? `<button class="btn btn-danger btn-sm" onclick="deleteWorktree('${escapeJsStr(wt.path)}')">Delete</button>` : ""}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
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

    // Render formatted diff
    renderFormattedDiff(diffData.raw_diff);
  } catch (err) {
    diffViewer.textContent = `Error: ${err.message}`;
  }
}

function renderFormattedDiff(rawDiff) {
  const diffViewer = document.getElementById("diffViewer");
  if (!rawDiff || !rawDiff.trim()) {
    diffViewer.innerHTML = `<span class="text-muted">Empty diff.</span>`;
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

  diffViewer.innerHTML = `<code>${formatted.join("\n")}</code>`;
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
