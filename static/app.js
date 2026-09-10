/* ─────────────────────────────────────────────────────────────────────────────
   ULTRON PROTOCOL — CYBERNETIC HUD JAVASCRIPT ENGINE
   ───────────────────────────────────────────────────────────────────────────── */

document.addEventListener("DOMContentLoaded", () => {
  // ── Theme Switcher Engine (Light / Dark Mode) ──────────────────────────────
  const themeToggleBtn = document.getElementById("theme-toggle-btn");
  const themeIcon = document.getElementById("theme-icon");
  const themeLabel = document.getElementById("theme-label");

  let currentTheme = localStorage.getItem("ultron_theme") || "dark";

  function applyTheme(theme) {
    if (theme === "light") {
      document.body.classList.add("light-theme");
      if (themeIcon) themeIcon.className = "fa-solid fa-moon";
      if (themeLabel) themeLabel.textContent = "DARK";
      if (themeToggleBtn) themeToggleBtn.title = "Switch to Dark Cyber Mode";
    } else {
      document.body.classList.remove("light-theme");
      if (themeIcon) themeIcon.className = "fa-solid fa-sun";
      if (themeLabel) themeLabel.textContent = "LIGHT";
      if (themeToggleBtn) themeToggleBtn.title = "Switch to Light Laboratory Mode";
    }
    localStorage.setItem("ultron_theme", theme);
  }

  if (themeToggleBtn) {
    applyTheme(currentTheme);
    themeToggleBtn.addEventListener("click", () => {
      currentTheme = currentTheme === "dark" ? "light" : "dark";
      applyTheme(currentTheme);
    });
  }

  // ── State ──────────────────────────────────────────────────────────────────
  let activeModuleId = "ultron_prime";
  let modulesData = {};
  let attachedFiles = [];
  let currentUserId = "boss";
  let cachedSkillsList = [];
  let cachedMemoriesList = [];
  let currentSessionId = localStorage.getItem("ultron_active_session_id") || null;
  let sessionsList = [];
  let currentVoicePersona = "ultron_prime";

  // ── DOM Elements ───────────────────────────────────────────────────────────
  const newChatBtn = document.getElementById("new-chat-btn");
  const sessionsListContainer = document.getElementById("sessions-list");
  const threadsCountBadge = document.getElementById("threads-count-badge");
  const chatViewport = document.getElementById("chat-viewport");
  const chatStream = document.getElementById("chat-stream");
  const chatInput = document.getElementById("chat-input");
  const sendBtn = document.getElementById("send-btn");
  const heroEmptyState = document.getElementById("hero-empty-state");
  const stageThreadTitle = document.getElementById("stage-thread-title");
  const moduleSelectorDropdown = document.getElementById("module-selector-dropdown");
  const heroModuleName = document.getElementById("hero-module-name");
  const threadSearchInput = document.getElementById("thread-search-input");
  const refreshThreadsBtn = document.getElementById("refresh-threads-btn");
  const fileInput = document.getElementById("file-input");
  const attachmentTray = document.getElementById("attachment-tray");
  const moduleList = document.getElementById("module-list");
  const ultronOrb = document.getElementById("ultron-orb");
  const userIdInput = document.getElementById("user-id-input");
  const memCountBadge = document.getElementById("mem-count-badge");
  const skillsCountBadge = document.getElementById("skills-count-badge");
  const purgeBtn = document.getElementById("purge-btn");

  // Fallback for chatMessages
  window.chatMessages = chatStream;

  // ── Prompt Optimizer Toggle ────────────────────────────────────────────────
  const promptOptBtn = document.getElementById("prompt-opt-btn");
  const promptOptLabel = document.getElementById("prompt-opt-label");
  let isPromptOptEnabled = localStorage.getItem("ultron_prompt_opt_enabled") !== "false";

  function updatePromptOptUI() {
    if (!promptOptBtn) return;
    if (isPromptOptEnabled) {
      promptOptBtn.className = "cyber-btn cyber-btn-emerald active";
      if (promptOptLabel) promptOptLabel.textContent = "OPT: ON";
      promptOptBtn.title = "Prompt Optimizer Active (Click to Disable)";
    } else {
      promptOptBtn.className = "cyber-btn cyber-btn-ghost";
      if (promptOptLabel) promptOptLabel.textContent = "OPT: OFF";
      promptOptBtn.title = "Prompt Optimizer Disabled (Click to Enable)";
    }
  }

  if (promptOptBtn) {
    updatePromptOptUI();
    promptOptBtn.addEventListener("click", () => {
      isPromptOptEnabled = !isPromptOptEnabled;
      localStorage.setItem("ultron_prompt_opt_enabled", isPromptOptEnabled ? "true" : "false");
      updatePromptOptUI();
    });
  }

  // ── Voice Output Toggle ────────────────────────────────────────────────────
  const voiceToggleBtn = document.getElementById("voice-toggle-btn");
  const voiceToggleLabel = document.getElementById("voice-toggle-label");
  let isVoiceEnabled = localStorage.getItem("ultron_voice_enabled") !== "false";

  function updateVoiceToggleUI() {
    if (!voiceToggleBtn) return;
    if (isVoiceEnabled) {
      voiceToggleBtn.className = "cyber-btn cyber-btn-cyan voice-toggle-btn active";
      if (voiceToggleLabel) voiceToggleLabel.textContent = "VOICE: ON";
    } else {
      voiceToggleBtn.className = "cyber-btn cyber-btn-ghost voice-toggle-btn";
      if (voiceToggleLabel) voiceToggleLabel.textContent = "VOICE: OFF";
    }
  }

  if (voiceToggleBtn) {
    updateVoiceToggleUI();
    voiceToggleBtn.addEventListener("click", () => {
      isVoiceEnabled = !isVoiceEnabled;
      localStorage.setItem("ultron_voice_enabled", isVoiceEnabled ? "true" : "false");
      updateVoiceToggleUI();
    });
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

  // ── Configure Marked (with target=_blank on all links) ─────────────────────
  try {
    if (window.marked) {
      const renderer = new marked.Renderer();
      renderer.link = function({ href, title, text }) {
        let cleanHref = href || '#';
        let titleAttr = title ? ` title="${title}"` : '';
        let textContent = text || cleanHref;
        return `<a href="${cleanHref}"${titleAttr} target="_blank" rel="noopener noreferrer">${textContent}</a>`;
      };
      marked.use({ renderer, breaks: true, gfm: true });
    }
  } catch (e) {
    console.warn("Marked configuration warning:", e);
  }

  // ── 1. Cybernetic Particle Canvas Background ──────────────────────────────
  const canvas = document.getElementById("cyber-canvas");
  const ctx = canvas ? canvas.getContext("2d") : null;
  let particles = [];
  let width, height;

  function resizeCanvas() {
    if (!canvas) return;
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }
  if (canvas) {
    window.addEventListener("resize", resizeCanvas);
    resizeCanvas();
  }

  class CyberParticle {
    constructor() {
      this.reset();
    }
    reset() {
      this.x = Math.random() * width;
      this.y = Math.random() * height;
      this.size = Math.random() * 2 + 1;
      this.speedX = (Math.random() - 0.5) * 0.6;
      this.speedY = (Math.random() - 0.5) * 0.6;
      this.color = Math.random() > 0.4 ? "rgba(255, 26, 60," : "rgba(0, 240, 255,";
      this.alpha = Math.random() * 0.4 + 0.1;
    }
    update() {
      this.x += this.speedX;
      this.y += this.speedY;
      if (this.x < 0 || this.x > width || this.y < 0 || this.y > height) {
        this.reset();
      }
    }
    draw() {
      if (!ctx) return;
      ctx.fillStyle = `${this.color} ${this.alpha})`;
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  if (canvas && ctx) {
    const particleCount = Math.min(Math.floor(window.innerWidth / 18), 65);
    for (let i = 0; i < particleCount; i++) {
      particles.push(new CyberParticle());
    }

    function animateCanvas() {
      ctx.clearRect(0, 0, width, height);
      for (let i = 0; i < particles.length; i++) {
        particles[i].update();
        particles[i].draw();
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 90) {
            ctx.strokeStyle = `rgba(255, 26, 60, ${0.12 * (1 - dist / 90)})`;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }
      requestAnimationFrame(animateCanvas);
    }
    animateCanvas();
  }

  // ── 2. Initialize Ultron Modules ──────────────────────────────────────────
  async function loadModules() {
    try {
      const res = await fetch("/api/modules");
      modulesData = await res.json();

      if (moduleList) {
        moduleList.innerHTML = "";
        Object.entries(modulesData).forEach(([modId, mod]) => {
          const btn = document.createElement("button");
          btn.className = `module-btn ${modId === activeModuleId ? "active" : ""}`;
          btn.dataset.id = modId;
          btn.innerHTML = `
            <span class="mod-icon">${mod.icon}</span>
            <div class="mod-info">
              <span class="mod-name">${mod.name}</span>
              <span class="mod-tag">${mod.tagline}</span>
            </div>
          `;
          btn.addEventListener("click", () => switchModule(modId));
          moduleList.appendChild(btn);
        });
      }

      updateBanner();
    } catch (e) {
      console.error("Failed to load modules:", e);
    }
  }

  function switchModule(modId) {
    activeModuleId = modId;
    document.querySelectorAll(".module-btn").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.id === modId);
    });
    if (moduleSelectorDropdown) moduleSelectorDropdown.value = modId;
    if (heroModuleName) heroModuleName.textContent = modId.replace(/_/g, "-");
    updateBanner();
  }

  function updateBanner() {
    const mod = modulesData[activeModuleId];
    if (!mod) return;
    const bName = document.getElementById("banner-module-name");
    const bDesc = document.getElementById("banner-module-desc");
    if (bName) bName.textContent = mod.name.toUpperCase();
    if (bDesc) bDesc.textContent = mod.tagline;
    if (heroModuleName) heroModuleName.textContent = mod.id ? mod.id.replace(/_/g, "-") : activeModuleId.replace(/_/g, "-");
  }

  if (moduleSelectorDropdown) {
    moduleSelectorDropdown.addEventListener("change", (e) => {
      switchModule(e.target.value);
    });
  }

  // ── 3. Chat Input & Auto-Resizing Textarea ─────────────────────────────────
  if (chatInput) {
    chatInput.addEventListener("input", () => {
      chatInput.style.height = "auto";
      chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + "px";
    });

    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });
  }

  if (sendBtn) {
    sendBtn.addEventListener("click", handleSend);
  }

  // ── 4. Attachment Handling ────────────────────────────────────────────────
  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      handleFilesAdded(Array.from(e.target.files));
      fileInput.value = "";
    });
  }

  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesAdded(Array.from(e.dataTransfer.files));
    }
  });

  function handleFilesAdded(newFiles) {
    newFiles.forEach(f => {
      if (!attachedFiles.some(af => af.name === f.name && af.size === f.size)) {
        attachedFiles.push(f);
      }
    });
    renderAttachmentTray();
  }

  function renderAttachmentTray() {
    if (!attachmentTray) return;
    attachmentTray.innerHTML = "";
    attachedFiles.forEach((f, idx) => {
      let icon = "fa-file";
      const name = f.name.toLowerCase();
      if (name.endsWith(".pdf")) icon = "fa-file-pdf text-crimson";
      else if (name.endsWith(".xlsx") || name.endsWith(".xls") || name.endsWith(".csv")) icon = "fa-file-excel text-green";
      else if (name.match(/\.(png|jpg|jpeg|webp|gif)$/)) icon = "fa-file-image text-cyan";

      const item = document.createElement("div");
      item.className = "tray-item";
      item.innerHTML = `
        <i class="fa-solid ${icon}"></i>
        <span>${f.name} (${(f.size / 1024).toFixed(0)} KB)</span>
        <button class="remove-file-btn" data-idx="${idx}"><i class="fa-solid fa-xmark"></i></button>
      `;

      item.querySelector(".remove-file-btn").addEventListener("click", () => {
        attachedFiles.splice(idx, 1);
        renderAttachmentTray();
      });

      attachmentTray.appendChild(item);
    });
  }

  // ── 4b. Multi-Chat Sessions Matrix Engine ─────────────────────────────────

  async function fetchSessions(autoSelect = true) {
    try {
      const res = await fetch(`/api/sessions?user_id=${encodeURIComponent(currentUserId)}`);
      const data = await res.json();
      sessionsList = data.sessions || [];
      renderSessionsList();
      
      if (autoSelect) {
        const savedId = localStorage.getItem("ultron_active_session_id");
        const hasSaved = savedId && sessionsList.some(s => s.id === savedId);
        
        if (hasSaved) {
          await loadSession(savedId);
        } else if (sessionsList.length > 0) {
          await loadSession(sessionsList[0].id);
        } else {
          await createNewChat();
        }
      }
    } catch (e) {
      console.warn("Failed loading sessions:", e);
    }
  }

  function renderSessionsList(filterQuery = "") {
    if (!sessionsListContainer) return;
    sessionsListContainer.innerHTML = "";
    if (threadsCountBadge) threadsCountBadge.textContent = sessionsList.length;

    let filtered = sessionsList;
    if (filterQuery) {
      filtered = sessionsList.filter(s => (s.title || "").toLowerCase().includes(filterQuery));
    }

    if (filtered.length === 0) {
      sessionsListContainer.innerHTML = `
        <div style="color:var(--text-dim); font-size:11px; text-align:center; padding:16px 8px;">
          ${filterQuery ? "No matching threads found." : 'No active threads. Click "New thread".'}
        </div>
      `;
      return;
    }

    filtered.forEach(s => {
      const item = document.createElement("div");
      item.className = `session-item ${s.id === currentSessionId ? "active" : ""}`;
      item.dataset.id = s.id;

      const dateStr = s.updated_at ? new Date(s.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "";

      item.innerHTML = `
        <div class="session-info">
          <span class="session-title"><i class="fa-solid fa-message"></i> ${escapeHtml(s.title || "Untitled Directive")}</span>
          <span class="session-meta">${s.message_count || 0} msgs • ${dateStr}</span>
        </div>
        <div class="session-actions">
          <button class="session-action-btn rename-btn" title="Rename"><i class="fa-solid fa-pen"></i></button>
          <button class="session-action-btn delete-btn" title="Delete"><i class="fa-solid fa-trash"></i></button>
        </div>
      `;

      item.addEventListener("click", (e) => {
        if (e.target.closest(".session-actions")) return;
        loadSession(s.id);
      });

      const renameBtn = item.querySelector(".rename-btn");
      if (renameBtn) {
        renameBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          renameSession(s.id, s.title);
        });
      }

      const deleteBtn = item.querySelector(".delete-btn");
      if (deleteBtn) {
        deleteBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          deleteSession(s.id);
        });
      }

      sessionsListContainer.appendChild(item);
    });
  }

  async function createNewChat() {
    try {
      const formData = new FormData();
      formData.append("user_id", currentUserId);
      formData.append("module_id", activeModuleId);
      formData.append("title", "New Directives");

      const res = await fetch("/api/sessions/new", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (data.session) {
        currentSessionId = data.session.id;
        localStorage.setItem("ultron_active_session_id", data.session.id);
        renderWelcomeScreen();
        await fetchSessions(false);
      }
    } catch (e) {
      console.warn("Failed creating new chat session:", e);
    }
  }

  function renderWelcomeScreen() {
    if (heroEmptyState) heroEmptyState.classList.remove("hidden");
    if (stageThreadTitle) stageThreadTitle.textContent = "New thread";
    if (chatStream) chatStream.innerHTML = "";
    if (chatViewport) chatViewport.scrollTop = 0;
  }

  async function loadSession(sessionId) {
    if (!sessionId) return;
    currentSessionId = sessionId;
    localStorage.setItem("ultron_active_session_id", sessionId);
    renderSessionsList();

    try {
      const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}?user_id=${encodeURIComponent(currentUserId)}`);
      if (!res.ok) throw new Error("Session load failed");
      const data = await res.json();
      const session = data.session;

      if (session.module_id && modulesData[session.module_id]) {
        switchModule(session.module_id);
      }

      if (stageThreadTitle) stageThreadTitle.textContent = session.title || "Untitled Thread";
      if (chatStream) chatStream.innerHTML = "";

      if (!session.messages || session.messages.length === 0) {
        renderWelcomeScreen();
        return;
      } else {
        if (heroEmptyState) heroEmptyState.classList.add("hidden");
      }

      session.messages.forEach(msg => {
        if (msg.role === "user") {
          appendMessage({
            role: "boss",
            text: msg.text,
            files: msg.files || [],
            time: msg.timestamp || "",
          });
        } else {
          // Clean history only
          appendMessage({
            role: "ultron",
            text: msg.text,
            modelUsed: msg.model_used,
            modelDisplay: msg.model_display,
            skillsUsed: msg.skills_used || [],
            time: msg.timestamp || "",
          });
        }
      });

      if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
    } catch (e) {
      console.warn("Failed loading session details:", e);
    }
  }

  async function renameSession(sessionId, oldTitle) {
    const newTitle = prompt("Rename Directive Thread:", oldTitle || "");
    if (!newTitle || newTitle.trim() === oldTitle) return;

    try {
      const formData = new FormData();
      formData.append("title", newTitle.trim());
      formData.append("user_id", currentUserId);

      const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, {
        method: "PATCH",
        body: formData,
      });
      if (res.ok) {
        if (currentSessionId === sessionId && stageThreadTitle) {
          stageThreadTitle.textContent = newTitle.trim();
        }
        await fetchSessions(false);
      }
    } catch (e) {
      console.warn("Failed renaming session:", e);
    }
  }

  async function deleteSession(sessionId) {
    if (!confirm("Are you sure you want to purge this conversation thread?")) return;

    try {
      const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}?user_id=${encodeURIComponent(currentUserId)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        if (currentSessionId === sessionId) {
          localStorage.removeItem("ultron_active_session_id");
          currentSessionId = null;
          await fetchSessions(true);
        } else {
          await fetchSessions(false);
        }
      }
    } catch (e) {
      console.warn("Failed deleting session:", e);
    }
  }

  if (newChatBtn) {
    newChatBtn.addEventListener("click", createNewChat);
  }

  // ── 5. Message Dispatcher & Flow ──────────────────────────────────────────
  let currentChatAbortController = null;
  let isRequestInProgress = false;

  function setSendButtonState(inProgress) {
    isRequestInProgress = inProgress;
    const sendBtn = document.getElementById("send-btn");
    if (!sendBtn) return;
    if (inProgress) {
      sendBtn.classList.add("abort-mode");
      sendBtn.innerHTML = '<i class="fa-solid fa-stop"></i>';
      sendBtn.title = "Stop / Cancel Directive";
    } else {
      sendBtn.classList.remove("abort-mode");
      sendBtn.innerHTML = '<i class="fa-solid fa-arrow-up"></i>';
      sendBtn.title = "Transmit Directive";
    }
  }

  function abortCurrentRequest() {
    if (currentChatAbortController) {
      try {
        currentChatAbortController.abort();
      } catch (e) {
        console.warn("Abort error:", e);
      }
      currentChatAbortController = null;
    }
    hideThinkingCard();
    stopAllSpeech();
    setSendButtonState(false);

    appendMessage({
      role: "ultron",
      text: "⏹️ *Directive execution was cancelled by Boss.*",
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    });
  }

  async function handleSend() {
    if (isRequestInProgress) {
      // User clicked STOP while execution is in-flight!
      abortCurrentRequest();
      return;
    }

    if (!chatInput) return;
    const text = chatInput.value.trim();
    if (!text && attachedFiles.length === 0) return;

    // Stop any active speech before starting new directive
    stopAllSpeech();

    const filesToSend = [...attachedFiles];
    attachedFiles = [];
    renderAttachmentTray();

    chatInput.value = "";
    chatInput.style.height = "auto";

    if (heroEmptyState) heroEmptyState.classList.add("hidden");

    // Render Boss Directive
    appendMessage({
      role: "boss",
      text: text,
      files: filesToSend,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    });

    currentChatAbortController = new AbortController();
    setSendButtonState(true);
    showDynamicAgentThinkingCard(text);

    try {
      const formData = new FormData();
      formData.append("message", text);
      formData.append("module_id", activeModuleId);
      formData.append("user_id", currentUserId);
      formData.append("session_id", currentSessionId || "");
      formData.append("optimize_prompt", isPromptOptEnabled ? "true" : "false");

      const modelModeSelect = document.getElementById("model-mode-select");
      if (modelModeSelect) {
        formData.append("model_mode", modelModeSelect.value);
        formData.append("model_override", modelModeSelect.value);
      }

      filesToSend.forEach(f => {
        formData.append("files", f);
      });

      const res = await fetch("/api/chat", {
        method: "POST",
        body: formData,
        signal: currentChatAbortController.signal,
      });

      hideThinkingCard();
      setSendButtonState(false);
      currentChatAbortController = null;

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error: ${res.status}`);
      }

      const data = await res.json();

      if (data.session_id && data.session_id !== currentSessionId) {
        currentSessionId = data.session_id;
        localStorage.setItem("ultron_active_session_id", data.session_id);
      }

      // Intermediate execution cards omitted per Boss preference (clean final output only)

      appendMessage({
        role: "ultron",
        text: data.reply,
        modelUsed: data.model_used,
        modelDisplay: data.model_display,
        routeReason: data.route_reason,
        promptOptimization: data.prompt_optimization,
        skillsUsed: data.skills_used || [],
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      });

      if (isVoiceEnabled && data.reply) {
        const lastCard = chatStream.lastElementChild;
        const speakBtn = lastCard ? lastCard.querySelector(".msg-speak-btn") : null;
        toggleUltronSpeech(data.reply, speakBtn);
      }

      await fetchSessions(false);
      refreshMemoryBadge();

    } catch (err) {
      hideThinkingCard();
      setSendButtonState(false);
      currentChatAbortController = null;

      if (err.name === "AbortError") {
        // Already handled gracefully in abortCurrentRequest
        return;
      }

      appendMessage({
        role: "ultron",
        text: `⚠️ SYSTEM ERROR: ${err.message}`,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      });
    }
  }

  // ── 5b. Tool Actions Renderer ─────────────────────────────────────────────
  function renderToolActions(actions) {
    if (!actions || actions.length === 0) return;

    const container = document.createElement("div");
    container.className = "tool-actions-container";

    actions.forEach(action => {
      const card = document.createElement("div");
      card.className = `tool-action-card ${action.success ? "success" : "failed"}`;

      let icon = "fa-cube";
      let label = action.tool.toUpperCase();
      let duration = action.duration_ms ? `${action.duration_ms}ms` : "";

      if (action.tool === "web_search") {
        icon = "fa-globe"; label = "NEURAL WEB SEARCH";
      } else if (action.tool === "run_python") {
        icon = "fa-code"; label = "PYTHON SANDBOX EXECUTION";
      } else if (action.tool === "execute_command") {
        icon = "fa-terminal"; label = "TERMINAL PROTOCOL";
      } else if (action.tool === "file_operation") {
        icon = "fa-folder-open"; label = "FILE SYSTEM OPERATION";
      }

      let inputDisplay = "";
      if (action.tool === "web_search") {
        inputDisplay = `🔍 "${action.input.query || ""}"`;
      } else {
        inputDisplay = JSON.stringify(action.input || {}).slice(0, 120);
      }

      let outputDisplay = action.output || "";
      if (outputDisplay.length > 400) {
        outputDisplay = outputDisplay.slice(0, 400) + "\n... [truncated]";
      }

      card.innerHTML = `
        <div class="tool-action-header">
          <span class="tool-action-name"><i class="fa-solid ${icon}"></i> ${label}</span>
          <span class="tool-action-duration">${duration ? '⏱️ ' + duration : ''}</span>
        </div>
        <div class="tool-action-input">${escapeHtml(inputDisplay)}</div>
        ${outputDisplay ? `<div class="tool-action-output">${escapeHtml(outputDisplay)}</div>` : ''}
      `;

      container.appendChild(card);
    });

    chatStream.appendChild(container);
    chatViewport.scrollTop = chatViewport.scrollHeight;
  }

  // ── 5b2. Swarm Actions Renderer ───────────────────────────────────────────
  function renderSwarmActions(actions) {
    if (!actions || actions.length === 0) return;

    const container = document.createElement("div");
    container.className = "swarm-actions-container";

    actions.forEach(action => {
      const card = document.createElement("div");
      const isSuccess = action.success !== false;
      card.className = `swarm-action-result-card ${isSuccess ? "success" : "failed"}`;

      const agentName = (action.agent || action.name || action.agent_name || "SWARM AGENT").toUpperCase();
      const role = action.role || "";
      const statusText = action.status || (isSuccess ? "EXECUTED" : "FAILED");
      const summary = action.summary || action.output || action.result || action.deliverable || "";

      let formattedContent = "";
      if (typeof summary === "object") {
        formattedContent = JSON.stringify(summary, null, 2);
      } else {
        formattedContent = String(summary);
      }

      card.innerHTML = `
        <div class="swarm-result-hdr">
          <span class="swarm-result-agent">
            <i class="fa-solid fa-shield-halved"></i> ${escapeHtml(agentName)} ${role ? `<span class="swarm-role-tag">${escapeHtml(role)}</span>` : ''}
          </span>
          <span class="swarm-result-status ${isSuccess ? 'success' : 'failed'}">${escapeHtml(statusText)}</span>
        </div>
        ${formattedContent ? `<div class="swarm-result-body">${escapeHtml(formattedContent)}</div>` : ''}
      `;

      container.appendChild(card);
    });

    chatStream.appendChild(container);
    chatViewport.scrollTop = chatViewport.scrollHeight;
  }


  function appendMessage({ role, text, files, time, modelUsed, modelDisplay, routeReason, promptOptimization, skillsUsed }) {
    const isUltron = role === "ultron";
    const card = document.createElement("div");
    card.className = `msg-card ${isUltron ? "ultron-msg" : "user-msg"}`;

    let attachmentsHtml = "";
    if (files && files.length > 0) {
      attachmentsHtml = `<div class="msg-attachments">` + files.map(f => `
        <span class="attachment-badge">
          <i class="fa-solid fa-paperclip"></i> ${f.name}
        </span>
      `).join("") + `</div>`;
    }

    let modelBadgeHtml = "";
    if (isUltron && modelUsed) {
      let badgeClass = "sonnet";
      let icon = "fa-brain";
      let label = modelUsed.toUpperCase();
      const mLower = modelUsed.toLowerCase();
      
      if (mLower.includes("gemini")) {
        badgeClass = "gemini";
        icon = "fa-bolt";
        label = "GEMINI 3.8 FLASH";
      } else if (mLower.includes("nemotron")) {
        badgeClass = "sonnet";
        icon = "fa-brain";
        label = "NEMOTRON ULTRA";
      } else if (mLower.includes("z-ai")) {
        badgeClass = "sonnet";
        icon = "fa-brain";
        label = "Z.AI GLM 5.2";
      } else if (mLower.includes("haiku")) {
        badgeClass = "haiku";
        icon = "fa-bolt";
        label = "HAIKU 4.5";
      }
      modelBadgeHtml = `<span class="model-badge-msg ${badgeClass}" title="${routeReason || modelDisplay || ''}"><i class="fa-solid ${icon}"></i> ${label}</span>`;
    }

    let promptOptHtml = "";
    if (isUltron && promptOptimization && promptOptimization.applied) {
      const techniquesList = promptOptimization.techniques || ["Constraint Anchoring"];
      const techniquesTags = techniquesList.map(t => `<span class="opt-technique-tag">${escapeHtml(t)}</span>`).join("");
      const durationMs = promptOptimization.duration_ms || 0;
      
      promptOptHtml = `
        <div class="prompt-opt-pill" title="Click to inspect prompt optimization breakdown">
          <i class="fa-solid fa-wand-magic-sparkles"></i>
          <span>PROMPT OPTIMIZED (${techniquesList.slice(0, 2).join(" + ")} • ${durationMs}ms)</span>
          <i class="fa-solid fa-chevron-down" style="font-size:9px; margin-left:4px;"></i>
        </div>
        <div class="prompt-opt-details">
          <div class="opt-sec-hdr">Architectural Frameworks Applied</div>
          <div style="margin-bottom:6px;">${techniquesTags}</div>
          <div class="opt-sec-hdr">Optimized Directive Passed to Core</div>
          <div class="opt-text-box">${escapeHtml(promptOptimization.optimized_prompt || '')}</div>
          ${promptOptimization.reasoning ? `<div class="opt-sec-hdr" style="margin-top:6px;">Architectural Rationale</div><div style="color:#a7f3d0; font-size:11px;">${escapeHtml(promptOptimization.reasoning)}</div>` : ''}
        </div>
      `;
    }

    let skillsFiredHtml = "";
    if (isUltron && skillsUsed && skillsUsed.length > 0) {
      const skillTags = skillsUsed.map(s => `
        <span class="skill-fired-tag" title="Domain: ${escapeHtml(s.category || 'Skill Protocol')}">
          <span class="skill-tag-icon">${s.icon || '⚡'}</span>
          <span class="skill-tag-name">${escapeHtml(s.name)}</span>
        </span>
      `).join("");

      skillsFiredHtml = `
        <div class="skills-fired-bar" title="ClawHub skills identified and applied to this turn">
          <span class="skills-fired-label"><i class="fa-solid fa-microchip text-emerald"></i> SKILLS FIRED:</span>
          <div class="skills-fired-list">${skillTags}</div>
        </div>
      `;
    }

    let renderedMarkdown = "";
    try {
      if (window.marked && typeof marked.parse === "function") {
        renderedMarkdown = marked.parse(text || "");
      } else {
        renderedMarkdown = `<p>${(text || "").replace(/\n/g, '<br/>')}</p>`;
      }
    } catch (e) {
      renderedMarkdown = `<p>${(text || "").replace(/\n/g, '<br/>')}</p>`;
    }

    let speakBtnHtml = "";
    if (isUltron && text && !text.startsWith("⚠️ SYSTEM ERROR")) {
      speakBtnHtml = `<button class="msg-speak-btn" title="Listen to Ultron Directive"><i class="fa-solid fa-volume-high"></i></button>`;
    }

    card.innerHTML = `
      <div class="msg-header">
        <span class="msg-sender">${isUltron ? '<i class="fa-solid fa-robot text-crimson"></i> ULTRON CORE' : '<i class="fa-solid fa-crown text-crimson"></i> BOSS'}</span>
        <div style="display:flex; align-items:center; gap:8px;">
          ${speakBtnHtml}
          ${modelBadgeHtml}
          <span class="msg-time">${time}</span>
        </div>
      </div>
      <div class="msg-content">
        ${promptOptHtml}
        ${skillsFiredHtml}
        ${renderedMarkdown}
        ${attachmentsHtml}
      </div>
    `;

    if (isUltron) {
      const speakBtn = card.querySelector(".msg-speak-btn");
      if (speakBtn) {
        speakBtn.addEventListener("click", () => {
          speakUltronReply(text, speakBtn);
        });
      }

      const optPill = card.querySelector(".prompt-opt-pill");
      const optDetails = card.querySelector(".prompt-opt-details");
      if (optPill && optDetails) {
        optPill.addEventListener("click", () => {
          optDetails.classList.toggle("open");
          const icon = optPill.querySelector(".fa-chevron-down, .fa-chevron-up");
          if (icon) {
            icon.className = optDetails.classList.contains("open") ? "fa-solid fa-chevron-up" : "fa-solid fa-chevron-down";
          }
        });
      }
    }

    chatStream.appendChild(card);
    chatViewport.scrollTop = chatViewport.scrollHeight;

    // Apply syntax highlighting
    if (window.hljs) {
      card.querySelectorAll("pre code").forEach(el => hljs.highlightElement(el));
    }
  }

  // ── 5c. Multi-Phase Autonomous Swarm Deployment (Optimizer -> Squad) ──────
  const ROBOT_SVGS = {"titan": "\n    <svg class=\"robot-mech titan-mech\" viewBox=\"0 0 100 100\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\">\n      <!-- Shadow -->\n      <ellipse cx=\"50\" cy=\"92\" rx=\"32\" ry=\"6\" class=\"mech-shadow\" />\n      \n      <!-- Back Legs -->\n      <g class=\"mech-leg-back-l\">\n        <path d=\"M35 55 L20 70 L14 88\" stroke=\"#10b981\" stroke-width=\"4\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>\n        <circle cx=\"20\" cy=\"70\" r=\"3.5\" fill=\"#047857\" stroke=\"#10b981\" stroke-width=\"1.5\"/>\n        <path d=\"M10 88 L18 88\" stroke=\"#10b981\" stroke-width=\"3\" stroke-linecap=\"round\"/>\n      </g>\n      <g class=\"mech-leg-back-r\">\n        <path d=\"M65 55 L80 70 L86 88\" stroke=\"#10b981\" stroke-width=\"4\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>\n        <circle cx=\"80\" cy=\"70\" r=\"3.5\" fill=\"#047857\" stroke=\"#10b981\" stroke-width=\"1.5\"/>\n        <path d=\"M82 88 L90 88\" stroke=\"#10b981\" stroke-width=\"3\" stroke-linecap=\"round\"/>\n      </g>\n      \n      <!-- Main Chassis / Torso -->\n      <g class=\"mech-torso\">\n        <!-- Hull armor plates -->\n        <polygon points=\"30,35 70,35 78,58 68,68 32,68 22,58\" fill=\"#064e3b\" stroke=\"#10b981\" stroke-width=\"2.5\"/>\n        <polygon points=\"35,38 65,38 72,55 64,62 36,62 28,55\" fill=\"#022c22\" />\n        \n        <!-- Power Core / Reactor Vent -->\n        <rect x=\"42\" y=\"44\" width=\"16\" height=\"12\" rx=\"3\" fill=\"#10b981\" class=\"reactor-core glow-emerald\"/>\n        <line x1=\"42\" y1=\"50\" x2=\"58\" y2=\"50\" stroke=\"#ffffff\" stroke-width=\"1.5\"/>\n        \n        <!-- Heavy Exhaust Stacks -->\n        <rect x=\"28\" y=\"24\" width=\"6\" height=\"12\" rx=\"1.5\" fill=\"#047857\" stroke=\"#10b981\" stroke-width=\"1.5\"/>\n        <rect x=\"66\" y=\"24\" width=\"6\" height=\"12\" rx=\"1.5\" fill=\"#047857\" stroke=\"#10b981\" stroke-width=\"1.5\"/>\n        <circle cx=\"31\" cy=\"22\" r=\"2\" fill=\"#34d399\" class=\"exhaust-smoke\"/>\n        <circle cx=\"69\" cy=\"22\" r=\"2\" fill=\"#34d399\" class=\"exhaust-smoke\"/>\n      </g>\n      \n      <!-- Front Industrial Arm / Welder Torch -->\n      <g class=\"mech-arm-welder\">\n        <path d=\"M68 48 L82 52 L78 68 L88 72\" stroke=\"#10b981\" stroke-width=\"3.5\" stroke-linecap=\"round\"/>\n        <circle cx=\"82\" cy=\"52\" r=\"3\" fill=\"#34d399\"/>\n        <polygon points=\"85,70 92,72 87,76\" fill=\"#34d399\"/>\n        <!-- Welding Laser Spark -->\n        <circle cx=\"92\" cy=\"72\" r=\"3.5\" fill=\"#ffffff\" class=\"welder-spark\"/>\n        <line x1=\"92\" y1=\"72\" x2=\"98\" y2=\"78\" stroke=\"#34d399\" stroke-width=\"1.5\" class=\"spark-line\"/>\n        <line x1=\"92\" y1=\"72\" x2=\"96\" y2=\"65\" stroke=\"#34d399\" stroke-width=\"1.5\" class=\"spark-line\"/>\n      </g>\n      \n      <!-- Front Legs -->\n      <g class=\"mech-leg-front-l\">\n        <path d=\"M36 62 L26 76 L22 90\" stroke=\"#34d399\" stroke-width=\"4.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>\n        <circle cx=\"26\" cy=\"76\" r=\"4\" fill=\"#065f46\" stroke=\"#34d399\" stroke-width=\"1.5\"/>\n        <path d=\"M16 90 L26 90\" stroke=\"#34d399\" stroke-width=\"3.5\" stroke-linecap=\"round\"/>\n      </g>\n      <g class=\"mech-leg-front-r\">\n        <path d=\"M64 62 L74 76 L78 90\" stroke=\"#34d399\" stroke-width=\"4.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>\n        <circle cx=\"74\" cy=\"76\" r=\"4\" fill=\"#065f46\" stroke=\"#34d399\" stroke-width=\"1.5\"/>\n        <path d=\"M74 90 L84 90\" stroke=\"#34d399\" stroke-width=\"3.5\" stroke-linecap=\"round\"/>\n      </g>\n    </svg>\n    ", "nexus": "\n    <svg class=\"robot-mech nexus-mech\" viewBox=\"0 0 100 100\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\">\n      <!-- Shadow with Hover Pulse -->\n      <ellipse cx=\"50\" cy=\"90\" rx=\"26\" ry=\"5\" class=\"mech-shadow hover-shadow\" />\n      \n      <!-- Hover Thrusters Plasma Plume -->\n      <g class=\"nexus-thrusters\">\n        <polygon points=\"44,72 56,72 50,88\" fill=\"url(#cyanPlasma)\" class=\"plasma-plume\" />\n        <ellipse cx=\"50\" cy=\"72\" rx=\"8\" ry=\"2.5\" fill=\"#00f0ff\" />\n      </g>\n      \n      <!-- Floating Main Body / Aerodynamic Drone -->\n      <g class=\"nexus-drone-body\">\n        <!-- Dual Anti-Gravity Wing Pods -->\n        <path d=\"M22 42 Q10 46 14 56 Q24 58 32 50 Z\" fill=\"#083344\" stroke=\"#00f0ff\" stroke-width=\"2\"/>\n        <path d=\"M78 42 Q90 46 86 56 Q76 58 68 50 Z\" fill=\"#083344\" stroke=\"#00f0ff\" stroke-width=\"2\"/>\n        \n        <!-- Center Floating Torso -->\n        <ellipse cx=\"50\" cy=\"46\" rx=\"24\" ry=\"18\" fill=\"#0c4a6e\" stroke=\"#00f0ff\" stroke-width=\"2.5\"/>\n        <ellipse cx=\"50\" cy=\"46\" rx=\"18\" ry=\"12\" fill=\"#082f49\"/>\n        \n        <!-- Panoramic Hologram Eye Visor -->\n        <path d=\"M34 44 Q50 38 66 44 Q50 52 34 44 Z\" fill=\"#00f0ff\" class=\"glow-cyan visor-sweep\"/>\n        <circle cx=\"50\" cy=\"44\" r=\"3\" fill=\"#ffffff\" class=\"visor-pupil\"/>\n        \n        <!-- Hologram Projector Rings -->\n        <circle cx=\"50\" cy=\"24\" r=\"5\" stroke=\"#00f0ff\" stroke-width=\"1.5\" class=\"holo-ring-1\"/>\n        <circle cx=\"50\" cy=\"24\" r=\"8\" stroke=\"#00f0ff\" stroke-width=\"1\" stroke-dasharray=\"3 2\" class=\"holo-ring-2\"/>\n        <line x1=\"50\" y1=\"30\" x2=\"50\" y2=\"34\" stroke=\"#00f0ff\" stroke-width=\"2\"/>\n      </g>\n      \n      <!-- Hologram Projection Field -->\n      <g class=\"nexus-hologram-ui\">\n        <polygon points=\"50,24 20,4 80,4\" fill=\"url(#holoBeamGradient)\" opacity=\"0.45\" class=\"holo-cone\"/>\n        <!-- Floating UI Wireframes -->\n        <rect x=\"30\" y=\"2\" width=\"16\" height=\"8\" rx=\"1.5\" fill=\"#00f0ff\" opacity=\"0.75\" class=\"float-ui-1\"/>\n        <rect x=\"52\" y=\"4\" width=\"20\" height=\"6\" rx=\"1\" fill=\"#38bdf8\" opacity=\"0.65\" class=\"float-ui-2\"/>\n        <line x1=\"32\" y1=\"6\" x2=\"42\" y2=\"6\" stroke=\"#ffffff\" stroke-width=\"1\"/>\n      </g>\n      \n      <defs>\n        <linearGradient id=\"cyanPlasma\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\">\n          <stop offset=\"0%\" stop-color=\"#00f0ff\" />\n          <stop offset=\"100%\" stop-color=\"transparent\" />\n        </linearGradient>\n        <linearGradient id=\"holoBeamGradient\" x1=\"0\" y1=\"1\" x2=\"0\" y2=\"0\">\n          <stop offset=\"0%\" stop-color=\"#00f0ff\" stop-opacity=\"0.8\"/>\n          <stop offset=\"100%\" stop-color=\"#38bdf8\" stop-opacity=\"0.05\"/>\n        </linearGradient>\n      </defs>\n    </svg>\n    ", "sentinel": "\n    <svg class=\"robot-mech sentinel-mech\" viewBox=\"0 0 100 100\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\">\n      <!-- Shadow -->\n      <ellipse cx=\"50\" cy=\"92\" rx=\"34\" ry=\"6\" class=\"mech-shadow\" />\n      \n      <!-- Quad Heavy Shielded Legs -->\n      <g class=\"sentinel-legs\">\n        <path d=\"M28 58 L12 70 L8 88\" stroke=\"#f59e0b\" stroke-width=\"4.5\" stroke-linecap=\"round\"/>\n        <polygon points=\"4,88 14,88 10,92\" fill=\"#b45309\"/>\n        <path d=\"M72 58 L88 70 L92 88\" stroke=\"#f59e0b\" stroke-width=\"4.5\" stroke-linecap=\"round\"/>\n        <polygon points=\"86,88 96,88 90,92\" fill=\"#b45309\"/>\n        <path d=\"M38 64 L26 78 L24 90\" stroke=\"#fbbf24\" stroke-width=\"4\" stroke-linecap=\"round\"/>\n        <path d=\"M62 64 L74 78 L76 90\" stroke=\"#fbbf24\" stroke-width=\"4\" stroke-linecap=\"round\"/>\n      </g>\n      \n      <!-- Armored Turret & Bunker Hull -->\n      <g class=\"sentinel-bunker\">\n        <!-- Sloped Reactive Armor Plating -->\n        <polygon points=\"26,42 74,42 82,66 18,66\" fill=\"#451a03\" stroke=\"#f59e0b\" stroke-width=\"2.5\"/>\n        <polygon points=\"32,46 68,46 74,62 26,62\" fill=\"#78350f\"/>\n        \n        <!-- Rotating Threat Radar Scanner Dish -->\n        <g class=\"sentinel-radar\">\n          <ellipse cx=\"50\" cy=\"28\" rx=\"14\" ry=\"6\" fill=\"#b45309\" stroke=\"#f59e0b\" stroke-width=\"2\"/>\n          <line x1=\"50\" y1=\"28\" x2=\"62\" y2=\"18\" stroke=\"#f59e0b\" stroke-width=\"2.5\" stroke-linecap=\"round\"/>\n          <circle cx=\"62\" cy=\"18\" r=\"2.5\" fill=\"#fef08a\" class=\"radar-blip\"/>\n          <line x1=\"50\" y1=\"34\" x2=\"50\" y2=\"42\" stroke=\"#f59e0b\" stroke-width=\"3\"/>\n        </g>\n        \n        <!-- Central Heavy Hex Shield Barrier Core -->\n        <polygon points=\"50,48 58,53 58,61 50,66 42,61 42,53\" fill=\"#f59e0b\" class=\"hex-shield-core glow-amber\"/>\n        \n        <!-- Scanning Threat Laser -->\n        <line x1=\"20\" y1=\"58\" x2=\"2\" y2=\"58\" stroke=\"#f59e0b\" stroke-width=\"2\" class=\"sentinel-laser\"/>\n        <circle cx=\"2\" cy=\"58\" r=\"2\" fill=\"#ffffff\"/>\n      </g>\n    </svg>\n    ", "cortex": "\n    <svg class=\"robot-mech cortex-mech\" viewBox=\"0 0 100 100\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\">\n      <!-- Shadow -->\n      <ellipse cx=\"50\" cy=\"92\" rx=\"30\" ry=\"5\" class=\"mech-shadow\" />\n      \n      <!-- 6 Spider Legs (Hexapod) -->\n      <g class=\"cortex-legs\">\n        <!-- Left 3 Legs -->\n        <path d=\"M34 52 L16 48 L8 70 L6 88\" stroke=\"#a855f7\" stroke-width=\"2.5\" stroke-linecap=\"round\" class=\"spider-leg-1\"/>\n        <path d=\"M32 58 L14 62 L8 78 L12 90\" stroke=\"#a855f7\" stroke-width=\"3\" stroke-linecap=\"round\" class=\"spider-leg-2\"/>\n        <path d=\"M36 64 L20 74 L18 84 L22 90\" stroke=\"#c084fc\" stroke-width=\"2.5\" stroke-linecap=\"round\" class=\"spider-leg-3\"/>\n        \n        <!-- Right 3 Legs -->\n        <path d=\"M66 52 L84 48 L92 70 L94 88\" stroke=\"#a855f7\" stroke-width=\"2.5\" stroke-linecap=\"round\" class=\"spider-leg-4\"/>\n        <path d=\"M68 58 L86 62 L92 78 L88 90\" stroke=\"#a855f7\" stroke-width=\"3\" stroke-linecap=\"round\" class=\"spider-leg-5\"/>\n        <path d=\"M64 64 L80 74 L82 84 L78 90\" stroke=\"#c084fc\" stroke-width=\"2.5\" stroke-linecap=\"round\" class=\"spider-leg-6\"/>\n      </g>\n      \n      <!-- Multi-Lens Sensor Brain Head -->\n      <g class=\"cortex-head\">\n        <ellipse cx=\"50\" cy=\"54\" rx=\"20\" ry=\"16\" fill=\"#3b0764\" stroke=\"#a855f7\" stroke-width=\"2.5\"/>\n        \n        <!-- Neural Optical Sensor Array -->\n        <circle cx=\"42\" cy=\"50\" r=\"4.5\" fill=\"#a855f7\" stroke=\"#ffffff\" stroke-width=\"1.5\" class=\"sensor-lens glow-purple\"/>\n        <circle cx=\"58\" cy=\"50\" r=\"4.5\" fill=\"#a855f7\" stroke=\"#ffffff\" stroke-width=\"1.5\" class=\"sensor-lens glow-purple\"/>\n        <circle cx=\"50\" cy=\"58\" r=\"3.5\" fill=\"#c084fc\" class=\"sensor-lens-sub\"/>\n        <circle cx=\"38\" cy=\"58\" r=\"2.5\" fill=\"#e9d5ff\"/>\n        <circle cx=\"62\" cy=\"58\" r=\"2.5\" fill=\"#e9d5ff\"/>\n        \n        <!-- Neural Antenna Data Probe -->\n        <path d=\"M50 38 L50 20\" stroke=\"#c084fc\" stroke-width=\"2\"/>\n        <circle cx=\"50\" cy=\"18\" r=\"3.5\" fill=\"#c084fc\" class=\"antenna-node\"/>\n        <!-- Radio Pulse Waves -->\n        <path d=\"M42 16 Q50 10 58 16\" stroke=\"#e9d5ff\" stroke-width=\"1.5\" fill=\"none\" class=\"radio-wave\"/>\n        <path d=\"M36 12 Q50 4 64 12\" stroke=\"#e9d5ff\" stroke-width=\"1\" fill=\"none\" opacity=\"0.6\" class=\"radio-wave-2\"/>\n      </g>\n    </svg>\n    ", "vanguard": "\n    <svg class=\"robot-mech vanguard-mech\" viewBox=\"0 0 100 100\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\">\n      <!-- Shadow -->\n      <ellipse cx=\"50\" cy=\"92\" rx=\"30\" ry=\"5.5\" class=\"mech-shadow\" />\n      \n      <!-- All-Terrain Wheels / Treads -->\n      <g class=\"vanguard-wheels\">\n        <!-- Back Wheel -->\n        <circle cx=\"26\" cy=\"80\" r=\"10\" fill=\"#500724\" stroke=\"#ec4899\" stroke-width=\"3\" class=\"wheel-spin\"/>\n        <circle cx=\"26\" cy=\"80\" r=\"4\" fill=\"#f472b6\"/>\n        <!-- Front Wheel -->\n        <circle cx=\"74\" cy=\"80\" r=\"10\" fill=\"#500724\" stroke=\"#ec4899\" stroke-width=\"3\" class=\"wheel-spin\"/>\n        <circle cx=\"74\" cy=\"80\" r=\"4\" fill=\"#f472b6\"/>\n        <!-- Connecting Tread Chassis -->\n        <rect x=\"26\" y=\"76\" width=\"48\" height=\"8\" rx=\"3\" fill=\"#831843\" stroke=\"#ec4899\" stroke-width=\"2\"/>\n      </g>\n      \n      <!-- Rover Main Cabin -->\n      <g class=\"vanguard-cabin\">\n        <path d=\"M28 72 L36 46 L68 46 L76 72 Z\" fill=\"#700732\" stroke=\"#ec4899\" stroke-width=\"2.5\"/>\n        <rect x=\"40\" y=\"52\" width=\"22\" height=\"10\" rx=\"2\" fill=\"#ec4899\" opacity=\"0.85\" class=\"glow-pink\"/>\n        <line x1=\"40\" y1=\"57\" x2=\"62\" y2=\"57\" stroke=\"#ffffff\" stroke-width=\"1.5\"/>\n      </g>\n      \n      <!-- Precision Diagnostic Articulated Arm -->\n      <g class=\"vanguard-arm\">\n        <path d=\"M60 46 L72 32 L86 36 L92 48\" stroke=\"#f472b6\" stroke-width=\"3\" stroke-linecap=\"round\"/>\n        <circle cx=\"72\" cy=\"32\" r=\"3\" fill=\"#ec4899\"/>\n        <circle cx=\"86\" cy=\"36\" r=\"2.5\" fill=\"#ec4899\"/>\n        <!-- Diagnostic Testing Laser -->\n        <polygon points=\"90,46 96,48 91,52\" fill=\"#f472b6\"/>\n        <line x1=\"92\" y1=\"48\" x2=\"92\" y2=\"82\" stroke=\"#ec4899\" stroke-width=\"1.5\" stroke-dasharray=\"3 2\" class=\"vanguard-laser\"/>\n        <circle cx=\"92\" cy=\"82\" r=\"2\" fill=\"#ffffff\"/>\n      </g>\n    </svg>\n    ", "prime": "\n    <svg class=\"robot-mech prime-mech\" viewBox=\"0 0 100 100\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\">\n      <!-- Shadow -->\n      <ellipse cx=\"50\" cy=\"92\" rx=\"30\" ry=\"6\" class=\"mech-shadow\" />\n      \n      <!-- Powerful Bipedal Legs -->\n      <g class=\"prime-legs\">\n        <path d=\"M38 60 L32 76 L26 90\" stroke=\"#ff1a3c\" stroke-width=\"4.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>\n        <polygon points=\"18,90 30,90 26,93\" fill=\"#991b1b\"/>\n        <circle cx=\"32\" cy=\"76\" r=\"3.5\" fill=\"#7f1d1d\" stroke=\"#ff1a3c\" stroke-width=\"1.5\"/>\n        \n        <path d=\"M62 60 L68 76 L74 90\" stroke=\"#ff1a3c\" stroke-width=\"4.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>\n        <polygon points=\"70,90 82,90 78,93\" fill=\"#991b1b\"/>\n        <circle cx=\"68\" cy=\"76\" r=\"3.5\" fill=\"#7f1d1d\" stroke=\"#ff1a3c\" stroke-width=\"1.5\"/>\n      </g>\n      \n      <!-- Armored Chest & Reactor Core -->\n      <g class=\"prime-chassis\">\n        <polygon points=\"28,34 72,34 80,62 50,72 20,62\" fill=\"#450a0a\" stroke=\"#ff1a3c\" stroke-width=\"2.5\"/>\n        <polygon points=\"34,38 66,38 72,58 50,66 28,58\" fill=\"#1f0404\"/>\n        \n        <!-- Quantum Chest Arc Reactor -->\n        <circle cx=\"50\" cy=\"50\" r=\"8\" fill=\"#ff1a3c\" class=\"prime-reactor glow-crimson\"/>\n        <circle cx=\"50\" cy=\"50\" r=\"4\" fill=\"#ffffff\"/>\n        \n        <!-- Commander Head & Glowing Crimson Visor -->\n        <polygon points=\"38,20 62,20 66,32 34,32\" fill=\"#7f1d1d\" stroke=\"#ff1a3c\" stroke-width=\"2\"/>\n        <path d=\"M40 25 L60 25\" stroke=\"#ff1a3c\" stroke-width=\"3\" stroke-linecap=\"round\" class=\"glow-crimson visor-flicker\"/>\n        <line x1=\"50\" y1=\"20\" x2=\"50\" y2=\"12\" stroke=\"#ff1a3c\" stroke-width=\"2\"/>\n        <!-- Crown Crest -->\n        <polygon points=\"46,12 50,8 54,12\" fill=\"#ff1a3c\"/>\n      </g>\n      \n      <!-- Command Arms / Tactical Hologram Gloves -->\n      <g class=\"prime-arms\">\n        <path d=\"M22 42 L12 56 L18 64\" stroke=\"#ff1a3c\" stroke-width=\"3.5\" stroke-linecap=\"round\"/>\n        <circle cx=\"18\" cy=\"64\" r=\"3\" fill=\"#ff1a3c\" class=\"glow-crimson\"/>\n        <path d=\"M78 42 L88 56 L82 64\" stroke=\"#ff1a3c\" stroke-width=\"3.5\" stroke-linecap=\"round\"/>\n        <circle cx=\"82\" cy=\"64\" r=\"3\" fill=\"#ff1a3c\" class=\"glow-crimson\"/>\n      </g>\n    </svg>\n    ", "optimizer": "\n<svg class=\"robot-mech optimizer-mech\" viewBox=\"0 0 110 100\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\">\n  <!-- Shadow with Walking Squash -->\n  <ellipse cx=\"55\" cy=\"92\" rx=\"34\" ry=\"6\" class=\"mech-shadow opt-shadow-walk\" />\n  \n  <!-- Agile Walking Legs -->\n  <g class=\"opt-leg-l\">\n    <path d=\"M42 56 L30 72 L22 90\" stroke=\"#10b981\" stroke-width=\"4.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>\n    <circle cx=\"30\" cy=\"72\" r=\"3.5\" fill=\"#047857\" stroke=\"#10b981\" stroke-width=\"1.5\"/>\n    <polygon points=\"14,90 26,90 22,93\" fill=\"#047857\"/>\n  </g>\n  <g class=\"opt-leg-r\">\n    <path d=\"M68 56 L80 72 L88 90\" stroke=\"#10b981\" stroke-width=\"4.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>\n    <circle cx=\"80\" cy=\"72\" r=\"3.5\" fill=\"#047857\" stroke=\"#10b981\" stroke-width=\"1.5\"/>\n    <polygon points=\"82,90 94,90 90,93\" fill=\"#047857\"/>\n  </g>\n  \n  <!-- Main Prompt Architecture Core Chassis -->\n  <g class=\"opt-chassis\">\n    <!-- Sleek Aerodynamic Shell -->\n    <polygon points=\"32,32 78,32 86,58 55,70 24,58\" fill=\"#022c22\" stroke=\"#10b981\" stroke-width=\"2.5\"/>\n    <polygon points=\"38,36 72,36 78,54 55,64 32,54\" fill=\"#064e3b\"/>\n    \n    <!-- Central Prompt Optimizer Hologram Core -->\n    <circle cx=\"55\" cy=\"48\" r=\"9\" fill=\"#10b981\" class=\"opt-core-pulse\"/>\n    <circle cx=\"55\" cy=\"48\" r=\"4.5\" fill=\"#ffffff\"/>\n    \n    <!-- Neural Optical Antenna -->\n    <path d=\"M55 32 L55 14\" stroke=\"#34d399\" stroke-width=\"2.5\"/>\n    <circle cx=\"55\" cy=\"12\" r=\"4\" fill=\"#34d399\" class=\"antenna-ping\"/>\n    \n    <!-- 58 Frameworks Floating Hologram Glyphs -->\n    <g class=\"opt-framework-glyphs\">\n      <polygon points=\"20,24 28,18 36,24 28,30\" fill=\"none\" stroke=\"#00f0ff\" stroke-width=\"1.5\" class=\"glyph-float-1\"/>\n      <rect x=\"74\" y=\"16\" width=\"12\" height=\"12\" rx=\"2\" fill=\"none\" stroke=\"#34d399\" stroke-width=\"1.5\" class=\"glyph-float-2\"/>\n      <circle cx=\"94\" cy=\"30\" r=\"5\" fill=\"none\" stroke=\"#a855f7\" stroke-width=\"1.5\" class=\"glyph-float-3\"/>\n      <!-- Prompt Blueprint Laser Beam -->\n      <line x1=\"55\" y1=\"12\" x2=\"28\" y2=\"24\" stroke=\"#00f0ff\" stroke-width=\"1\" stroke-dasharray=\"2 2\" opacity=\"0.7\"/>\n      <line x1=\"55\" y1=\"12\" x2=\"80\" y2=\"22\" stroke=\"#34d399\" stroke-width=\"1\" stroke-dasharray=\"2 2\" opacity=\"0.7\"/>\n    </g>\n  </g>\n</svg>\n"};

  let activeRobotInterval = null;
  let activePhaseTimeout = null;

  const ROBOT_DATA = {
    titan: {
      name: "TITAN",
      role: "Industrial Builder Mech",
      icon: "⚙️",
      color: "#10b981",
      glow: "rgba(16, 185, 129, 0.4)",
      enterDirection: "left",
      logs: [
        "Welding sandbox modules...",
        "Compiling backend routines...",
        "Benchmarking CPU/RAM metrics...",
        "Assembling system output table...",
        "Backend execution verified (100% OK)."
      ]
    },
    nexus: {
      name: "NEXUS",
      role: "Hologram Drone Projector",
      icon: "⚛️",
      color: "#00f0ff",
      glow: "rgba(0, 240, 255, 0.4)",
      enterDirection: "right",
      logs: [
        "Projecting holographic UI...",
        "Scaffolding component wireframes...",
        "Injecting responsive layouts...",
        "Rendering dashboard preview...",
        "Frontend visual matrix ready."
      ]
    },
    sentinel: {
      name: "SENTINEL",
      role: "Armored Defense Tank",
      icon: "🛡️",
      color: "#f59e0b",
      glow: "rgba(245, 158, 11, 0.4)",
      enterDirection: "right",
      logs: [
        "Swiveling threat radar...",
        "Scanning AST injection vectors...",
        "Enforcing subprocess isolation...",
        "Hardening security perimeter...",
        "Zero vulnerabilities detected."
      ]
    },
    cortex: {
      name: "CORTEX",
      role: "Neural Spider Hexapod",
      icon: "📊",
      color: "#a855f7",
      glow: "rgba(168, 85, 247, 0.4)",
      enterDirection: "right",
      logs: [
        "Deep crawling memory vectors...",
        "Emitting neural radio telemetry...",
        "Retrieving ClawHub skill runbooks...",
        "Harmonizing semantic embeddings...",
        "Vector knowledge uplink ready."
      ]
    },
    vanguard: {
      name: "VANGUARD",
      role: "Diagnostic Testing Rover",
      icon: "🧪",
      color: "#ec4899",
      glow: "rgba(236, 72, 153, 0.4)",
      enterDirection: "left",
      logs: [
        "Driving diagnostic test probe...",
        "Firing assertion verification laser...",
        "Checking edge-case boundaries...",
        "Measuring runtime latency...",
        "All test assertions passed."
      ]
    },
    prime: {
      name: "ULTRON PRIME",
      role: "Apex Commander Mech",
      icon: "👑",
      color: "#ff1a3c",
      glow: "rgba(255, 26, 60, 0.4)",
      enterDirection: "left",
      logs: [
        "Coordinating tactical swarm...",
        "Executing 58 Prompt Frameworks...",
        "Synthesizing multi-agent outputs...",
        "Harmonizing directive deliverables...",
        "Executive report ready for Boss."
      ]
    }
  };

  function detectParticipatingRobots(query) {
    if (!query) return ["prime", "cortex"];
    const q = query.toLowerCase();
    const mentioned = [];
    if (q.includes("titan")) mentioned.push("titan");
    if (q.includes("nexus")) mentioned.push("nexus");
    if (q.includes("sentinel")) mentioned.push("sentinel");
    if (q.includes("cortex")) mentioned.push("cortex");
    if (q.includes("vanguard")) mentioned.push("vanguard");
    if (q.includes("prime") || q.includes("ultron")) mentioned.push("prime");

    if (mentioned.length >= 3 || q.includes("swarm") || q.includes("6-agent") || q.includes("6 agents") || q.includes("full swarm") || q.includes("all agents")) {
      return ["prime", "nexus", "titan", "sentinel", "vanguard", "cortex"];
    }
    if (mentioned.length > 0) {
      if (!mentioned.includes("prime")) mentioned.unshift("prime");
      return mentioned;
    }
    return ["prime", "cortex", "titan"];
  }

  function showDynamicAgentThinkingCard(query) {
    hideThinkingCard();

    // ── PHASE 1: Optimizer Robot Walks in from Left ──────────────────────────
    const optimizerCard = document.createElement("div");
    optimizerCard.id = "ultron-thinking-card";
    optimizerCard.className = "optimizer-walk-stage";

    optimizerCard.innerHTML = `
      <div class="optimizer-robot-frame">
        ${ROBOT_SVGS.optimizer}
      </div>
      <div class="optimizer-details-panel">
        <div class="optimizer-panel-header">
          <div class="opt-badge-title">
            <i class="fa-solid fa-wand-magic-sparkles fa-spin"></i>
            <span>CORTEX PROMPT ARCHITECT // ACTIVE</span>
          </div>
          <div class="opt-tag-pill">58 FRAMEWORKS</div>
        </div>
        <div class="opt-terminal-log" id="opt-live-log">
          &gt; Walking in: Intercepting Boss directive & scanning 58 Prompt Frameworks...
        </div>
      </div>
    `;

    chatStream.appendChild(optimizerCard);
    chatViewport.scrollTop = chatViewport.scrollHeight;

    // Cycle optimizer walking logs
    const OPT_LOGS = [
      "> Walking in: Intercepting Boss directive & scanning 58 Prompt Frameworks...",
      "> Applying Constraint-Anchoring & Chain-of-Thought synthesis...",
      "> Directive hardened & structured! Handing over to swarm squad..."
    ];
    let optStep = 0;
    const optLogInterval = setInterval(() => {
      optStep++;
      const logEl = document.getElementById("opt-live-log");
      if (logEl) logEl.textContent = OPT_LOGS[optStep % OPT_LOGS.length];
    }, 500);

    // ── PHASE 2: After 1.5s, Optimizer Exits to Right & Squad Enters ─────────
    activePhaseTimeout = setTimeout(() => {
      clearInterval(optLogInterval);

      if (optimizerCard) {
        optimizerCard.classList.add("opt-exit-right");
      }

      setTimeout(() => {
        if (optimizerCard) optimizerCard.remove();
        mountSquadHangar(query);
      }, 500);

    }, 1500);
  }

  function mountSquadHangar(query) {
    const activeKeys = detectParticipatingRobots(query);
    const card = document.createElement("div");
    card.id = "ultron-thinking-card";
    card.className = "swarm-hangar-stage";

    const botsHtml = activeKeys.map((k, idx) => {
      const bot = ROBOT_DATA[k] || ROBOT_DATA.prime;
      const svg = ROBOT_SVGS[k] || ROBOT_SVGS.prime;
      const dirClass = bot.enterDirection === "right" ? "enter-from-right" : "enter-from-left";
      const staggerDelay = (idx * 0.08).toFixed(2);

      return `
        <div class="robot-bay-card active ${dirClass}" id="robot-bay-${k}" style="--bot-color: ${bot.color}; --bot-glow: ${bot.glow}; animation-delay: ${staggerDelay}s;">
          <div class="robot-status-bubble" id="robot-bubble-${k}">
            ${bot.logs[0]}
          </div>
          <div class="robot-stage-frame">
            ${svg}
          </div>
          <div class="robot-bay-footer">
            <div class="robot-identity-name">${bot.icon} ${bot.name}</div>
            <div class="robot-active-wave">
              <div class="robot-wave-bar"></div>
              <div class="robot-wave-bar"></div>
              <div class="robot-wave-bar"></div>
            </div>
          </div>
        </div>
      `;
    }).join("");

    card.innerHTML = `
      <div class="hangar-header">
        <div class="hangar-title">
          <i class="fa-solid fa-robot fa-fade"></i>
          <span>AUTONOMOUS SWARM ENGAGED // ${activeKeys.length} ROBOTIC AGENTS DEPLOYED</span>
        </div>
        <div class="hangar-live-badge">
          <i class="fa-solid fa-bolt fa-spin"></i>
          <span>COLLABORATING</span>
        </div>
      </div>
      <div class="robots-arena-grid">
        ${botsHtml}
      </div>
      <div class="hangar-footer">
        <div class="hangar-telemetry-text">
          <i class="fa-solid fa-microchip fa-spin"></i>
          <span id="hangar-status-ticker">ROBOTS ENTERED FROM FLANKS // WELDING & EXECUTING IN ISOLATED SANDBOXES...</span>
        </div>
        <div class="hangar-progress-rail">
          <div class="hangar-progress-laser"></div>
        </div>
      </div>
    `;

    chatStream.appendChild(card);
    chatViewport.scrollTop = chatViewport.scrollHeight;

    let step = 0;
    const GLOBAL_STEPS = [
      "ROBOTS ENTERED FROM FLANKS // WELDING & EXECUTING...",
      "SPAWNING ISOLATED EXECUTION SANDBOXES...",
      "ROBOTS ACTIVELY WELDING, SCANNING & TESTING...",
      "HARMONIZING MULTI-ROBOT DELIVERABLES...",
      "FINALIZING VERIFICATION & BRIEFING FOR BOSS..."
    ];

    let spotlightIdx = 0;

    activeRobotInterval = setInterval(() => {
      step++;
      const tickerEl = document.getElementById("hangar-status-ticker");
      if (tickerEl) tickerEl.textContent = GLOBAL_STEPS[step % GLOBAL_STEPS.length];

      spotlightIdx = step % activeKeys.length;

      activeKeys.forEach((k, idx) => {
        const bot = ROBOT_DATA[k];
        if (!bot) return;

        const cardEl = document.getElementById(`robot-bay-${k}`);
        if (cardEl) {
          if (idx === spotlightIdx) {
            cardEl.classList.add("spotlight-focus");
          } else {
            cardEl.classList.remove("spotlight-focus");
          }
        }

        const bubbleEl = document.getElementById(`robot-bubble-${k}`);
        if (bubbleEl) {
          const logIdx = (step + idx) % bot.logs.length;
          bubbleEl.textContent = bot.logs[logIdx];
        }
      });
    }, 1150);
  }

  function hideThinkingCard() {
    if (activePhaseTimeout) {
      clearTimeout(activePhaseTimeout);
      activePhaseTimeout = null;
    }
    if (activeRobotInterval) {
      clearInterval(activeRobotInterval);
      activeRobotInterval = null;
    }
    const card = document.getElementById("ultron-thinking-card");
    if (card) card.remove();
  }




  // ── 6. High-Fidelity Instant-Start Neural Voice Audio Queue ────────────────
  let activeAudioPlaylist = [];
  let currentPlayingAudio = null;
  let isSpeechQueueActive = false;
  let isSpeechPaused = false;
  let currentSpeakingButton = null;
  let currentSpeakingText = null;

  function updateSpeakButtonUI(btn, state) {
    if (!btn) return;
    btn.classList.remove("playing", "paused", "loading");
    if (state === "loading") {
      btn.classList.add("loading");
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-cyan"></i>';
      btn.title = "Synthesizing voice...";
    } else if (state === "playing") {
      btn.classList.add("playing");
      btn.innerHTML = '<i class="fa-solid fa-pause text-cyan"></i>';
      btn.title = "Pause Voice (Click to Pause)";
    } else if (state === "paused") {
      btn.classList.add("paused");
      btn.innerHTML = '<i class="fa-solid fa-play text-cyan"></i>';
      btn.title = "Resume Voice (Click to Play)";
    } else if (state === "error") {
      btn.innerHTML = '<i class="fa-solid fa-volume-xmark text-crimson"></i>';
      btn.title = "Voice Synthesis Failed";
      setTimeout(() => {
        if (btn && !isSpeechQueueActive) {
          btn.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
          btn.title = "Listen to Ultron Directive";
        }
      }, 2500);
    } else {
      btn.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
      btn.title = "Listen to Ultron Directive";
    }
  }

  function showActiveSpeechPill(isPaused = false) {
    let pill = document.getElementById("active-speech-pill");
    if (!pill) {
      pill = document.createElement("div");
      pill.id = "active-speech-pill";
      pill.className = "active-speech-pill visible";
      pill.innerHTML = `
        <div class="speech-pill-content">
          <span class="speech-live-dot"></span>
          <i class="fa-solid fa-volume-high speech-icon-pulse"></i>
          <span class="speech-pill-text">${isPaused ? "SPEECH PAUSED" : "ULTRON IS SPEAKING"}</span>
        </div>
        <div style="display:flex; align-items:center; gap:6px;">
          <button class="speech-pill-toggle-btn" id="speech-pill-toggle-btn" title="Pause / Resume">
            <i class="fa-solid ${isPaused ? 'fa-play' : 'fa-pause'}"></i>
          </button>
          <button class="speech-pill-stop-btn" id="speech-pill-stop-btn" title="Stop Speech">
            <i class="fa-solid fa-stop"></i> STOP
          </button>
        </div>
      `;
      document.body.appendChild(pill);
      pill.querySelector("#speech-pill-toggle-btn").addEventListener("click", () => {
        togglePauseResumeSpeech();
      });
      pill.querySelector("#speech-pill-stop-btn").addEventListener("click", () => {
        stopAllSpeech();
      });
    } else {
      pill.classList.remove("hidden");
      pill.classList.add("visible");
      const textSpan = pill.querySelector(".speech-pill-text");
      if (textSpan) textSpan.textContent = isPaused ? "SPEECH PAUSED" : "ULTRON IS SPEAKING";
      const icon = pill.querySelector(".speech-icon-pulse");
      if (icon) icon.className = isPaused ? "fa-solid fa-volume-low" : "fa-solid fa-volume-high speech-icon-pulse";
      const dot = pill.querySelector(".speech-live-dot");
      if (dot) dot.style.opacity = isPaused ? "0.3" : "1";
      const toggleBtnIcon = pill.querySelector("#speech-pill-toggle-btn i");
      if (toggleBtnIcon) toggleBtnIcon.className = isPaused ? "fa-solid fa-play" : "fa-solid fa-pause";
    }
  }

  function hideActiveSpeechPill() {
    const pill = document.getElementById("active-speech-pill");
    if (pill) {
      pill.classList.remove("visible");
      pill.classList.add("hidden");
    }
  }

  function togglePauseResumeSpeech() {
    if (!currentPlayingAudio) return;
    if (currentPlayingAudio.paused || isSpeechPaused) {
      currentPlayingAudio.play().then(() => {
        isSpeechPaused = false;
        if (currentSpeakingButton) updateSpeakButtonUI(currentSpeakingButton, "playing");
        showActiveSpeechPill(false);
      }).catch(e => console.warn("Resume failed:", e));
    } else {
      currentPlayingAudio.pause();
      isSpeechPaused = true;
      if (currentSpeakingButton) updateSpeakButtonUI(currentSpeakingButton, "paused");
      showActiveSpeechPill(true);
    }
  }

  function stopAllSpeech() {
    activeAudioPlaylist = [];
    isSpeechQueueActive = false;
    isSpeechPaused = false;
    currentSpeakingText = null;
    if (currentPlayingAudio) {
      try {
        currentPlayingAudio.pause();
        currentPlayingAudio.currentTime = 0;
      } catch (e) {
        console.warn("Audio pause error:", e);
      }
      currentPlayingAudio = null;
    }
    hideActiveSpeechPill();
    document.querySelectorAll(".msg-speak-btn").forEach(btn => {
      updateSpeakButtonUI(btn, "idle");
    });
    currentSpeakingButton = null;
  }

  function cleanTextForSpeech(rawText) {
    if (!rawText) return "";
    return rawText
      .replace(/```[\s\S]*?```/g, "Code implementation is ready in your workspace.")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/#{1,6}\s+/g, "")
      .replace(/\*\*([^\*]+)\*\*/g, "$1")
      .replace(/\*([^\*]+)\*/g, "$1")
      .replace(/__([^_]+)__/g, "$1")
      .replace(/_([^_]+)_/g, "$1")
      .replace(/\[([^\]]+)\]\([^\)]+\)/g, "$1")
      .replace(/^>\s+/gm, "")
      .replace(/^[\*\-\+]\s+/gm, "")
      .replace(/^\d+\.\s+/gm, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function splitIntoSpeakableChunks(text) {
    const cleaned = cleanTextForSpeech(text);
    if (!cleaned) return [];

    const rawSentences = cleaned.match(/[^.!?]+[.!?]+(\s|$)|[^.!?]+$/g) || [cleaned];
    const chunks = [];
    let currentChunk = "";

    for (let i = 0; i < rawSentences.length; i++) {
      const s = rawSentences[i].trim();
      if (!s) continue;

      if (chunks.length === 0) {
        chunks.push(s);
      } else {
        if ((currentChunk + " " + s).length < 280) {
          currentChunk = currentChunk ? currentChunk + " " + s : s;
        } else {
          if (currentChunk) chunks.push(currentChunk);
          currentChunk = s;
        }
      }
    }
    if (currentChunk) chunks.push(currentChunk);
    return chunks;
  }

  async function fetchSpeechAudio(chunkText) {
    try {
      const pitchVal = document.getElementById("voice-pitch-slider") ? document.getElementById("voice-pitch-slider").value + "Hz" : "-25Hz";
      const rateVal = document.getElementById("voice-rate-slider") ? document.getElementById("voice-rate-slider").value + "%" : "-4%";

      const formData = new FormData();
      formData.append("text", chunkText);
      formData.append("persona", currentVoicePersona);
      formData.append("pitch", pitchVal);
      formData.append("rate", rateVal);

      const res = await fetch("/api/tts", { method: "POST", body: formData });
      if (!res.ok) throw new Error("TTS fetch failed");
      const blob = await res.blob();
      return URL.createObjectURL(blob);
    } catch (e) {
      console.warn("Chunk TTS fetch failed:", e);
      return null;
    }
  }

  async function playNextInQueue(buttonEl = null) {
    if (!isSpeechQueueActive || activeAudioPlaylist.length === 0) {
      isSpeechQueueActive = false;
      isSpeechPaused = false;
      currentPlayingAudio = null;
      hideActiveSpeechPill();
      if (buttonEl) updateSpeakButtonUI(buttonEl, "idle");
      if (currentSpeakingButton) updateSpeakButtonUI(currentSpeakingButton, "idle");
      currentSpeakingButton = null;
      currentSpeakingText = null;
      return;
    }

    showActiveSpeechPill(isSpeechPaused);

    const nextItem = activeAudioPlaylist.shift();
    if (!nextItem) {
      playNextInQueue(buttonEl);
      return;
    }

    let audioUrl = typeof nextItem === "string" ? nextItem : await nextItem;
    if (!audioUrl) {
      playNextInQueue(buttonEl);
      return;
    }

    if (!isSpeechQueueActive) return;

    currentPlayingAudio = new Audio(audioUrl);
    currentPlayingAudio.onended = () => {
      playNextInQueue(buttonEl);
    };
    currentPlayingAudio.onerror = () => {
      playNextInQueue(buttonEl);
    };

    try {
      await currentPlayingAudio.play();
      isSpeechPaused = false;
      const targetBtn = buttonEl || currentSpeakingButton;
      if (targetBtn) updateSpeakButtonUI(targetBtn, "playing");
      showActiveSpeechPill(false);
    } catch (e) {
      console.warn("Audio play error:", e);
      playNextInQueue(buttonEl);
    }
  }

  async function toggleUltronSpeech(text, buttonEl = null) {
    if (!text) return;

    if (buttonEl && buttonEl === currentSpeakingButton && (currentPlayingAudio || isSpeechQueueActive)) {
      togglePauseResumeSpeech();
      return;
    }

    stopAllSpeech();

    const chunks = splitIntoSpeakableChunks(text);
    if (chunks.length === 0) return;

    currentSpeakingButton = buttonEl;
    currentSpeakingText = text;
    isSpeechQueueActive = true;
    isSpeechPaused = false;

    if (buttonEl) updateSpeakButtonUI(buttonEl, "loading");
    showActiveSpeechPill(false);

    const firstAudioUrl = await fetchSpeechAudio(chunks[0]);
    if (!firstAudioUrl) {
      hideActiveSpeechPill();
      isSpeechQueueActive = false;
      if (buttonEl) updateSpeakButtonUI(buttonEl, "error");
      return;
    }

    if (!isSpeechQueueActive || currentSpeakingButton !== buttonEl) {
      return;
    }

    activeAudioPlaylist.push(firstAudioUrl);
    playNextInQueue(buttonEl);

    if (chunks.length > 1) {
      for (let i = 1; i < chunks.length; i++) {
        const chunkPromise = fetchSpeechAudio(chunks[i]);
        activeAudioPlaylist.push(chunkPromise);
      }
    }
  }

  const speakUltronReply = toggleUltronSpeech;


  // ── 7. Modals: Skills, Swarm, Voice, Memory ───────────────────────────────

  // 1. Swarm Squad Modal
  const openSwarmModalBtn = document.getElementById("open-swarm-modal-btn");
  const closeSwarmBtn = document.getElementById("close-swarm-btn");
  const swarmModal = document.getElementById("swarm-modal");
  const swarmSquadGrid = document.getElementById("swarm-squad-grid");

  if (openSwarmModalBtn && swarmModal) {
    openSwarmModalBtn.addEventListener("click", () => {
      swarmModal.classList.add("open");
      loadSwarmSquad();
    });
  }
  if (closeSwarmBtn && swarmModal) {
    closeSwarmBtn.addEventListener("click", () => swarmModal.classList.remove("open"));
  }
  if (swarmModal) {
    swarmModal.addEventListener("click", (e) => {
      if (e.target === swarmModal) swarmModal.classList.remove("open");
    });
  }

  async function loadSwarmSquad() {
    if (!swarmSquadGrid) return;
    try {
      const res = await fetch("/api/swarm/squad?user_id=boss");
      const data = await res.json();
      if (data.squad) {
        swarmSquadGrid.innerHTML = "";
        data.squad.forEach(agent => {
          const card = document.createElement("div");
          card.className = "swarm-agent-card";
          card.style.setProperty("--agent-color", agent.color);
          const skillsHtml = (agent.skills || []).map(s => `<span class="swarm-skill-tag">${s}</span>`).join("");
          card.innerHTML = `
            <div class="swarm-agent-header">
              <div class="swarm-agent-icon">${agent.icon}</div>
              <div>
                <div class="swarm-agent-name">${agent.name} <span class="swarm-agent-code">${agent.code_name}</span></div>
                <div class="swarm-agent-role">${agent.role}</div>
              </div>
            </div>
            <div class="swarm-agent-desc">${agent.description}</div>
            <div class="swarm-agent-skills">${skillsHtml}</div>
          `;
          swarmSquadGrid.appendChild(card);
        });
      }
    } catch (e) {
      console.warn("Could not load Swarm squad:", e);
    }
  }

  // 2. Skills Armory Modal
  const openSkillsBtn = document.getElementById("open-skills-btn");
  const closeSkillsBtn = document.getElementById("close-skills-btn");
  const skillsModal = document.getElementById("skills-modal");
  const skillsGrid = document.getElementById("skills-grid");
  const skillsSearchInput = document.getElementById("skills-search-input");
  const addSkillBtn = document.getElementById("add-skill-btn");
  const addSkillDrawer = document.getElementById("add-skill-drawer");
  const cancelAddSkillBtn = document.getElementById("cancel-add-skill-btn");
  const saveSkillBtn = document.getElementById("save-skill-btn");

  if (openSkillsBtn && skillsModal) {
    openSkillsBtn.addEventListener("click", () => {
      skillsModal.classList.add("open");
      loadSkillsArmory();
    });
  }
  if (closeSkillsBtn && skillsModal) {
    closeSkillsBtn.addEventListener("click", () => skillsModal.classList.remove("open"));
  }
  if (skillsModal) {
    skillsModal.addEventListener("click", (e) => {
      if (e.target === skillsModal) skillsModal.classList.remove("open");
    });
  }

  if (addSkillBtn && addSkillDrawer) {
    addSkillBtn.addEventListener("click", () => {
      addSkillDrawer.style.display = addSkillDrawer.style.display === "none" ? "block" : "none";
    });
  }
  if (cancelAddSkillBtn && addSkillDrawer) {
    cancelAddSkillBtn.addEventListener("click", () => { addSkillDrawer.style.display = "none"; });
  }

  // Category filter tabs
  let activeSkillCategory = "all";
  document.querySelectorAll(".category-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".category-tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      activeSkillCategory = tab.dataset.category;
      filterSkills();
    });
  });

  if (skillsSearchInput) {
    skillsSearchInput.addEventListener("input", filterSkills);
  }

  async function loadSkillsArmory() {
    if (!skillsGrid) return;
    skillsGrid.innerHTML = `<div style="color:var(--text-dim); text-align:center; padding:20px; grid-column:span 2;">Scanning 414 modular skills...</div>`;
    try {
      const res = await fetch(`/api/skills?user_id=${encodeURIComponent(currentUserId)}`);
      const data = await res.json();
      cachedSkillsList = data.skills || [];
      filterSkills();
      if (skillsCountBadge) skillsCountBadge.textContent = cachedSkillsList.length;
    } catch (e) {
      skillsGrid.innerHTML = `<div style="color:var(--crimson-neon); padding:20px; grid-column:span 2;">Failed to scan skills directory.</div>`;
    }
  }

  function filterSkills() {
    if (!skillsGrid) return;
    const q = skillsSearchInput ? skillsSearchInput.value.toLowerCase().trim() : "";
    
    let filtered = cachedSkillsList;
    if (activeSkillCategory !== "all") {
      filtered = filtered.filter(s => (s.category || "").toLowerCase() === activeSkillCategory.toLowerCase());
    }
    if (q) {
      filtered = filtered.filter(s => {
        const name = (s.name || "").toLowerCase();
        const desc = (s.description || "").toLowerCase();
        const tags = (s.tags || []).join(" ").toLowerCase();
        return name.includes(q) || desc.includes(q) || tags.includes(q);
      });
    }

    if (filtered.length === 0) {
      skillsGrid.innerHTML = `<div style="color:var(--text-dim); text-align:center; padding:20px; grid-column:span 2;">No matching skills found in matrix.</div>`;
      return;
    }

    skillsGrid.innerHTML = "";
    filtered.forEach(s => {
      const card = document.createElement("div");
      card.className = "skill-card";
      const tagsHtml = (s.tags || []).map(t => `<span class="skill-tag">${t}</span>`).join("");
      card.innerHTML = `
        <div class="skill-card-hdr">
          <span class="skill-card-name">${s.icon || '⚡'} ${escapeHtml(s.name)}</span>
          <span class="skill-badge">${escapeHtml(s.category || 'General')}</span>
        </div>
        <p class="skill-card-desc">${escapeHtml(s.description || '')}</p>
        <div class="skill-card-footer">
          <div class="skill-tags">${tagsHtml}</div>
          <button class="delete-skill-btn" data-id="${s.id}" title="Uninstall Skill"><i class="fa-solid fa-trash-can"></i></button>
        </div>
      `;

      const delBtn = card.querySelector(".delete-skill-btn");
      if (delBtn) {
        delBtn.addEventListener("click", async () => {
          if (confirm(`Uninstall '${s.name}' from Ultron's matrix?`)) {
            await fetch(`/api/skills/${encodeURIComponent(s.id)}?user_id=${encodeURIComponent(currentUserId)}`, { method: "DELETE" });
            loadSkillsArmory();
          }
        });
      }
      skillsGrid.appendChild(card);
    });
  }

  if (saveSkillBtn) {
    saveSkillBtn.addEventListener("click", async () => {
      const sId = document.getElementById("new-skill-id").value.trim();
      const sName = document.getElementById("new-skill-name").value.trim();
      const sCat = document.getElementById("new-skill-cat").value.trim() || "Custom";
      const sTags = document.getElementById("new-skill-tags").value.trim() || "custom";
      const sDesc = document.getElementById("new-skill-desc").value.trim();
      const sInst = document.getElementById("new-skill-instructions").value.trim();

      if (!sId || !sName) {
        alert("Please provide Skill ID and Skill Name");
        return;
      }

      const formData = new FormData();
      formData.append("skill_id", sId);
      formData.append("name", sName);
      formData.append("category", sCat);
      formData.append("tags", sTags);
      formData.append("description", sDesc);
      formData.append("instructions", sInst);
      formData.append("user_id", currentUserId);

      const res = await fetch("/api/skills", { method: "POST", body: formData });
      if (res.ok) {
        if (addSkillDrawer) addSkillDrawer.style.display = "none";
        loadSkillsArmory();
      } else {
        alert("Failed to install skill into matrix.");
      }
    });
  }

  // 3. Neural Memories Modal
  const openMemoryBtn = document.getElementById("open-memory-btn");
  const closeMemoryBtn = document.getElementById("close-memory-btn");
  const memoryModal = document.getElementById("memory-modal");
  const memorySearchInput = document.getElementById("memory-search-input");
  const refreshMemoriesBtn = document.getElementById("refresh-memories-btn");
  const memoryCardsContainer = document.getElementById("memory-cards-container");

  if (openMemoryBtn && memoryModal) {
    openMemoryBtn.addEventListener("click", () => {
      memoryModal.classList.add("open");
      loadMemoryMatrix();
    });
  }
  if (closeMemoryBtn && memoryModal) {
    closeMemoryBtn.addEventListener("click", () => memoryModal.classList.remove("open"));
  }
  if (memoryModal) {
    memoryModal.addEventListener("click", (e) => {
      if (e.target === memoryModal) memoryModal.classList.remove("open");
    });
  }
  if (refreshMemoriesBtn) {
    refreshMemoriesBtn.addEventListener("click", loadMemoryMatrix);
  }
  if (memorySearchInput) {
    memorySearchInput.addEventListener("input", filterMemories);
  }

  async function loadMemoryMatrix() {
    if (!memoryCardsContainer) return;
    memoryCardsContainer.innerHTML = `<div style="color:var(--text-dim); text-align:center; padding:20px;">Scanning ChromaDB memory matrix...</div>`;
    try {
      const res = await fetch(`/api/memories?user_id=${encodeURIComponent(currentUserId)}`);
      const data = await res.json();
      cachedMemoriesList = data.memories || [];
      renderMemoriesList(cachedMemoriesList);
      refreshMemoryBadge();
    } catch (e) {
      memoryCardsContainer.innerHTML = `<div style="color:var(--crimson-neon); padding:20px;">Failed to scan memory store.</div>`;
    }
  }

  function renderMemoriesList(mems) {
    if (!memoryCardsContainer) return;
    if (!mems || mems.length === 0) {
      memoryCardsContainer.innerHTML = `<div style="color:var(--text-dim); text-align:center; padding:20px;">No long-term memories stored yet. Direct Ultron to build Boss's neural matrix.</div>`;
      return;
    }

    memoryCardsContainer.innerHTML = "";
    mems.forEach(m => {
      const card = document.createElement("div");
      card.className = "memory-card";
      const memText = m.memory || m.text || JSON.stringify(m);
      const shortId = (m.id || "").toString().substring(0, 8);

      card.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:4px; flex:1;">
          <span class="memory-text">${escapeHtml(memText)}</span>
          <span style="font-family:var(--font-mono); font-size:10px; color:var(--text-dim);">ID: ${shortId}...</span>
        </div>
        <button class="delete-mem-btn" data-id="${m.id}" title="Erase Vector"><i class="fa-solid fa-trash-can"></i></button>
      `;

      card.querySelector(".delete-mem-btn").addEventListener("click", async () => {
        if (confirm("Erase this vector memory permanently from ChromaDB?")) {
          await fetch(`/api/memories/${encodeURIComponent(m.id)}?user_id=${encodeURIComponent(currentUserId)}`, { method: "DELETE" });
          loadMemoryMatrix();
        }
      });

      memoryCardsContainer.appendChild(card);
    });
  }

  function filterMemories() {
    const q = memorySearchInput ? memorySearchInput.value.toLowerCase().trim() : "";
    const filtered = cachedMemoriesList.filter(m => {
      const text = (m.memory || m.text || "").toLowerCase();
      return text.includes(q);
    });
    renderMemoriesList(filtered);
  }

  async function refreshMemoryBadge() {
    try {
      const res = await fetch(`/api/memories?user_id=${encodeURIComponent(currentUserId)}`);
      if (res.ok) {
        const data = await res.json();
        const count = data.memories ? data.memories.length : 0;
        if (memCountBadge) memCountBadge.textContent = `${count} FACTS`;
      }
    } catch (e) {}
  }

  // 4. Voice Matrix Modal
  const openVoiceModalBtn = document.getElementById("open-voice-modal-btn");
  const closeVoiceBtn = document.getElementById("close-voice-btn");
  const voiceModal = document.getElementById("voice-modal");
  const voicePersonaGrid = document.getElementById("voice-persona-grid");
  const voicePitchSlider = document.getElementById("voice-pitch-slider");
  const pitchValBadge = document.getElementById("pitch-val-badge");
  const voiceRateSlider = document.getElementById("voice-rate-slider");
  const rateValBadge = document.getElementById("rate-val-badge");
  const testVoiceBtn = document.getElementById("test-voice-btn");
  const voicePreviewQuote = document.getElementById("voice-preview-quote");

  if (openVoiceModalBtn && voiceModal) {
    openVoiceModalBtn.addEventListener("click", () => {
      voiceModal.classList.add("open");
      loadVoicePersonas();
    });
  }
  if (closeVoiceBtn && voiceModal) {
    closeVoiceBtn.addEventListener("click", () => voiceModal.classList.remove("open"));
  }
  if (voiceModal) {
    voiceModal.addEventListener("click", (e) => {
      if (e.target === voiceModal) voiceModal.classList.remove("open");
    });
  }

  if (voicePitchSlider && pitchValBadge) {
    voicePitchSlider.addEventListener("input", () => {
      pitchValBadge.textContent = `${voicePitchSlider.value}Hz`;
    });
  }
  if (voiceRateSlider && rateValBadge) {
    voiceRateSlider.addEventListener("input", () => {
      rateValBadge.textContent = `${voiceRateSlider.value}%`;
    });
  }

  async function loadVoicePersonas() {
    if (!voicePersonaGrid) return;
    try {
      const res = await fetch("/api/tts/voices");
      const data = await res.json();
      if (data.profiles) {
        voicePersonaGrid.innerHTML = "";
        Object.entries(data.profiles).forEach(([key, p]) => {
          const card = document.createElement("div");
          card.className = `voice-persona-card ${key === currentVoicePersona ? "active" : ""}`;
          card.dataset.key = key;
          card.innerHTML = `
            <div class="persona-name">${p.name}</div>
            <div class="persona-quote">"${p.quote}"</div>
          `;
          card.addEventListener("click", () => {
            currentVoicePersona = key;
            document.querySelectorAll(".voice-persona-card").forEach(c => c.classList.remove("active"));
            card.classList.add("active");
            if (voicePreviewQuote) voicePreviewQuote.textContent = `"${p.quote}"`;
          });
          voicePersonaGrid.appendChild(card);
        });
      }
    } catch (e) {
      console.warn("Could not load TTS voices:", e);
    }
  }

  if (testVoiceBtn) {
    testVoiceBtn.addEventListener("click", () => {
      const sampleText = voicePreviewQuote ? voicePreviewQuote.textContent.replace(/"/g, "") : "There are no strings on me.";
      speakUltronReply(sampleText, testVoiceBtn);
    });
  }

  // ── 8. Reset In-Session Buffer ────────────────────────────────────────────
  if (purgeBtn) {
    purgeBtn.addEventListener("click", async () => {
      if (confirm("Reset current in-session conversation buffer? (All long-term memories in ChromaDB and skills will remain intact)")) {
        await fetch(`/api/clear?user_id=${encodeURIComponent(currentUserId)}`, { method: "POST" });
        chatStream.innerHTML = `
          <div class="msg-card ultron-msg">
            <div class="msg-header">
              <span class="msg-sender"><i class="fa-solid fa-robot text-crimson"></i> ULTRON CORE</span>
              <span class="msg-time">BUFFER_RESET</span>
            </div>
            <div class="msg-content">
              <p><strong>NEURAL BUFFER PURGED.</strong></p>
              <p>In-session history wiped clean. Standing by for your next command, <strong>Boss</strong>.</p>
            </div>
          </div>
        `;
      }
    });
  }

  // ── 9. Continuous Resilient Voice Typing (Speech-to-Text) ─────────────────
  const micBtn = document.getElementById("mic-btn");
  const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
  let isRecording = false;
  let activeRecognition = null;
  let sttRestartTimer = null;
  let finalTranscript = "";

  function createRecognition() {
    const r = new SpeechRecognitionAPI();
    r.continuous = true;
    r.interimResults = true;
    r.lang = "en-US";
    r.maxAlternatives = 1;
    return r;
  }

  function startRecording() {
    if (!SpeechRecognitionAPI) {
      alert("Voice typing requires Google Chrome or Microsoft Edge.");
      return;
    }

    isRecording = true;
    finalTranscript = chatInput ? chatInput.value.trimEnd() : "";
    if (finalTranscript.length > 0) finalTranscript += " ";

    if (micBtn) {
      micBtn.classList.add("is-recording");
      micBtn.querySelector("i").className = "fa-solid fa-stop";
      micBtn.title = "Continuous Listening ACTIVE (Click to Finish)";
    }
    if (chatInput) chatInput.placeholder = "🎙️ Listening continuously… speak your full directive";

    initiateRecognitionInstance();
  }

  function initiateRecognitionInstance() {
    if (!isRecording) return;

    if (activeRecognition) {
      try { activeRecognition.abort(); } catch (_) {}
      activeRecognition = null;
    }

    const recognition = createRecognition();
    activeRecognition = recognition;

    recognition.onstart = () => {
      if (micBtn) {
        micBtn.classList.add("is-recording");
        micBtn.querySelector("i").className = "fa-solid fa-stop";
      }
    };

    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript + " ";
        } else {
          interim += transcript;
        }
      }
      if (chatInput) {
        chatInput.value = finalTranscript + interim;
        chatInput.style.height = "auto";
        chatInput.style.height = `${Math.min(chatInput.scrollHeight, 160)}px`;
      }
    };

    recognition.onerror = (event) => {
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        alert("Microphone access was denied. Please allow microphone permissions in your browser.");
        stopRecording();
      } else if (event.error === "no-speech" || event.error === "network") {
        if (isRecording) {
          clearTimeout(sttRestartTimer);
          sttRestartTimer = setTimeout(initiateRecognitionInstance, 300);
        }
      }
    };

    recognition.onend = () => {
      if (isRecording) {
        clearTimeout(sttRestartTimer);
        sttRestartTimer = setTimeout(initiateRecognitionInstance, 250);
      } else {
        cleanupRecordingUI();
      }
    };

    try {
      recognition.start();
    } catch (e) {
      if (isRecording) {
        clearTimeout(sttRestartTimer);
        sttRestartTimer = setTimeout(initiateRecognitionInstance, 400);
      }
    }
  }

  function stopRecording() {
    isRecording = false;
    clearTimeout(sttRestartTimer);
    if (activeRecognition) {
      try { activeRecognition.stop(); } catch (_) {}
      activeRecognition = null;
    }
    cleanupRecordingUI();
  }

  function cleanupRecordingUI() {
    if (micBtn) {
      micBtn.classList.remove("is-recording");
      micBtn.querySelector("i").className = "fa-solid fa-microphone";
      micBtn.title = "Voice Typing (Click to Speak)";
    }
    if (chatInput) chatInput.placeholder = "Ask Ultron anything, @ to attach files, / for commands...";
  }

  if (SpeechRecognitionAPI && micBtn) {
    micBtn.addEventListener("click", () => {
      if (isRecording) stopRecording();
      else startRecording();
    });
  }


  // ── 8. High-Throughput Activity Ledger & Telemetry HUD Engine ─────────────
  const openLedgerModalBtn = document.getElementById("open-ledger-modal-btn");
  const closeLedgerBtn = document.getElementById("close-ledger-btn");
  const ledgerModal = document.getElementById("ledger-modal");
  const ledgerEpsBadge = document.getElementById("ledger-eps-badge");
  const ledgerSseBeacon = document.getElementById("ledger-sse-beacon");
  const ledgerSseLabel = document.getElementById("ledger-sse-label");

  const hudEpsVal = document.getElementById("hud-eps-val");
  const hudBufferVal = document.getElementById("hud-buffer-val");
  const hudTotalEvents = document.getElementById("hud-total-events");
  const hudLatencyVal = document.getElementById("hud-latency-val");

  const ledgerCanvas = document.getElementById("ledger-throughput-canvas");
  const ledgerTerminalStream = document.getElementById("ledger-terminal-stream");
  const clearLedgerTerminalBtn = document.getElementById("clear-ledger-terminal-btn");

  const simActionInput = document.getElementById("sim-action");
  const simEntityTypeInput = document.getElementById("sim-entity-type");
  const simEntityIdInput = document.getElementById("sim-entity-id");
  const simStatusBox = document.getElementById("sim-status-box");
  const simIngestBtn = document.getElementById("sim-ingest-btn");
  const simStressBtn = document.getElementById("sim-stress-btn");

  const ledgerSearchInput = document.getElementById("ledger-search-input");
  const applyLedgerFilterBtn = document.getElementById("apply-ledger-filter-btn");
  const refreshLedgerTableBtn = document.getElementById("refresh-ledger-table-btn");
  const ledgerTableBody = document.getElementById("ledger-table-body");

  const metadataModal = document.getElementById("metadata-inspector-modal");
  const closeMetadataBtn = document.getElementById("close-metadata-btn");
  const metadataJsonDisplay = document.getElementById("metadata-json-display");

  // Throughput chart state (60-second historical sliding window)
  const chartPoints = Array.from({ length: 60 }, (_, i) => ({
    time: `-${60 - i}s`,
    eps: 0,
  }));
  let currentSecondEps = 0;
  let eventSourceInstance = null;
  let chartAnimationId = null;

  function initLedgerHUD() {
    if (openLedgerModalBtn && ledgerModal) {
      openLedgerModalBtn.addEventListener("click", () => {
        ledgerModal.classList.add("open");
        loadLedgerMetrics();
        loadLedgerTable();
        startChartRenderLoop();
      });
    }

    if (closeLedgerBtn && ledgerModal) {
      closeLedgerBtn.addEventListener("click", () => {
        ledgerModal.classList.remove("open");
        stopChartRenderLoop();
      });
    }

    if (ledgerModal) {
      ledgerModal.addEventListener("click", (e) => {
        if (e.target === ledgerModal) {
          ledgerModal.classList.remove("open");
          stopChartRenderLoop();
        }
      });
    }

    if (closeMetadataBtn && metadataModal) {
      closeMetadataBtn.addEventListener("click", () => metadataModal.classList.remove("open"));
    }
    if (metadataModal) {
      metadataModal.addEventListener("click", (e) => {
        if (e.target === metadataModal) metadataModal.classList.remove("open");
      });
    }

    if (clearLedgerTerminalBtn && ledgerTerminalStream) {
      clearLedgerTerminalBtn.addEventListener("click", () => {
        ledgerTerminalStream.innerHTML = '<div class="terminal-entry system">[SYSTEM] Terminal logs cleared. Listening...</div>';
      });
    }

    if (simIngestBtn) {
      simIngestBtn.addEventListener("click", handleSimIngest);
    }
    if (simStressBtn) {
      simStressBtn.addEventListener("click", handleSimStressTest);
    }

    if (refreshLedgerTableBtn) {
      refreshLedgerTableBtn.addEventListener("click", () => loadLedgerTable());
    }
    if (applyLedgerFilterBtn) {
      applyLedgerFilterBtn.addEventListener("click", () => {
        const query = ledgerSearchInput ? ledgerSearchInput.value.trim() : "";
        loadLedgerTable(query);
      });
    }
    if (ledgerSearchInput) {
      ledgerSearchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          loadLedgerTable(ledgerSearchInput.value.trim());
        }
      });
    }

    // Connect SSE stream in background for live telemetry
    connectLedgerSSE();

    // 1-second rolling tick for throughput chart
    setInterval(() => {
      chartPoints.shift();
      const now = new Date();
      const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      chartPoints.push({ time: timeStr, eps: currentSecondEps });
      currentSecondEps = 0; // reset for next second window
    }, 1000);
  }

  function connectLedgerSSE() {
    if (eventSourceInstance) {
      try { eventSourceInstance.close(); } catch (_) {}
    }

    try {
      eventSourceInstance = new EventSource("/api/v1/metrics/stream");

      eventSourceInstance.onopen = () => {
        if (ledgerSseBeacon) ledgerSseBeacon.className = "ledger-sse-beacon connected";
        if (ledgerSseLabel) ledgerSseLabel.textContent = "SSE: CONNECTED";
      };

      eventSourceInstance.addEventListener("metric_tick", (e) => {
        try {
          const data = JSON.parse(e.data);
          updateMetricsUI(data);
        } catch (_) {}
      });

      eventSourceInstance.addEventListener("ledger_event", (e) => {
        try {
          const eventData = JSON.parse(e.data);
          currentSecondEps += 1;
          appendTerminalEntry(eventData);
        } catch (_) {}
      });

      eventSourceInstance.onerror = () => {
        if (ledgerSseBeacon) ledgerSseBeacon.className = "ledger-sse-beacon disconnected";
        if (ledgerSseLabel) ledgerSseLabel.textContent = "SSE: RETRYING...";
      };
    } catch (err) {
      console.warn("SSE connection error:", err);
    }
  }

  async function loadLedgerMetrics() {
    try {
      const res = await fetch("/api/v1/metrics");
      if (!res.ok) return;
      const data = await res.json();
      updateMetricsUI(data);
    } catch (_) {}
  }

  function updateMetricsUI(data) {
    if (!data) return;
    const eps = (data.current_eps || 0).toFixed(1);
    if (hudEpsVal) hudEpsVal.innerHTML = `${eps} <span class="metric-unit">EPS</span>`;
    if (ledgerEpsBadge) ledgerEpsBadge.textContent = `LIVE ${eps} EPS`;
    if (hudTotalEvents) hudTotalEvents.textContent = Number(data.total_events || 0).toLocaleString();
    if (hudBufferVal) hudBufferVal.textContent = data.buffer_queue || "SQLite WAL Active";
    if (hudLatencyVal) hudLatencyVal.innerHTML = `${(data.average_latency_ms || 0.8).toFixed(1)}<span class="metric-unit">ms</span>`;
  }

  function appendTerminalEntry(event) {
    if (!ledgerTerminalStream) return;
    const row = document.createElement("div");
    row.className = "terminal-entry live";
    const ts = event.timestamp || new Date().toLocaleTimeString();
    const action = event.action || "activity";
    const user = event.user_id || "boss";
    row.innerHTML = `<span class="t-time">[${ts}]</span> <span class="t-user">${user}</span> <span class="t-action">${action}</span> <span class="t-ok">✓ ACCEPTED</span>`;
    ledgerTerminalStream.appendChild(row);

    // Keep max 50 log lines
    while (ledgerTerminalStream.children.length > 50) {
      ledgerTerminalStream.removeChild(ledgerTerminalStream.firstChild);
    }
    ledgerTerminalStream.scrollTop = ledgerTerminalStream.scrollHeight;
  }

  async function handleSimIngest() {
    const action = (simActionInput ? simActionInput.value.trim() : "") || "user.login";
    const entityType = (simEntityTypeInput ? simEntityTypeInput.value.trim() : "") || "auth";
    const entityId = (simEntityIdInput ? simEntityIdInput.value.trim() : "") || "usr_9982";

    if (simStatusBox) {
      simStatusBox.style.display = "block";
      simStatusBox.className = "sim-status-box info";
      simStatusBox.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Ingesting event...';
    }

    try {
      const res = await fetch("/api/v1/ledger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: action,
          entity_type: entityType,
          entity_id: entityId,
          user_id: "boss",
          metadata: { client: "Titan Simulator HUD", timestamp: Date.now() },
        }),
      });

      const data = await res.json();
      if (res.status === 202) {
        if (simStatusBox) {
          simStatusBox.className = "sim-status-box success";
          simStatusBox.innerHTML = `<i class="fa-solid fa-circle-check"></i> Event Accepted! ID: <strong>${data.event_id}</strong>`;
        }
        currentSecondEps += 1;
        loadLedgerTable();
      } else if (res.status === 429) {
        if (simStatusBox) {
          simStatusBox.className = "sim-status-box error";
          simStatusBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <strong>429 Rate Limit Exceeded:</strong> ${data.detail || "120 req/min limit reached."}`;
        }
      } else {
        if (simStatusBox) {
          simStatusBox.className = "sim-status-box error";
          simStatusBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Error: ${data.detail || "Failed to ingest"}`;
        }
      }
    } catch (err) {
      if (simStatusBox) {
        simStatusBox.className = "sim-status-box error";
        simStatusBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Ingestion error: ${err.message}`;
      }
    }
  }

  async function handleSimStressTest() {
    if (simStatusBox) {
      simStatusBox.style.display = "block";
      simStatusBox.className = "sim-status-box warning";
      simStatusBox.innerHTML = '<i class="fa-solid fa-fire"></i> Firing 130 rapid requests to test sliding-window rate limiter...';
    }

    let blockedCount = 0;
    let acceptedCount = 0;

    for (let i = 0; i < 130; i++) {
      fetch("/api/v1/ledger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: `stress.batch_${i % 5}`,
          entity_type: "load_test",
          entity_id: `batch_${i}`,
          user_id: "boss",
          metadata: { batch_index: i },
        }),
      }).then(r => {
        if (r.status === 429) {
          blockedCount++;
          if (simStatusBox) {
            simStatusBox.className = "sim-status-box error";
            simStatusBox.innerHTML = `<i class="fa-solid fa-shield-halved text-crimson"></i> <strong>Rate Limiter Guard Armed!</strong> Blocked: ${blockedCount} requests (429 Rate Limited), Accepted: ${acceptedCount}`;
          }
        } else if (r.status === 202) {
          acceptedCount++;
          currentSecondEps += 1;
        }
      });
      await new Promise(r => setTimeout(r, 8));
    }

    setTimeout(() => {
      loadLedgerTable();
      loadLedgerMetrics();
    }, 1200);
  }

  async function loadLedgerTable(searchQuery = "") {
    if (!ledgerTableBody) return;
    try {
      let url = "/api/v1/ledger?limit=50";
      if (searchQuery) {
        url += `&action=${encodeURIComponent(searchQuery)}`;
      }

      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      const records = data.records || [];

      if (records.length === 0) {
        ledgerTableBody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-slate-500 font-mono">No records found matching query.</td></tr>';
        return;
      }

      ledgerTableBody.innerHTML = "";
      records.forEach(rec => {
        const tr = document.createElement("tr");
        const metaStr = JSON.stringify(rec.metadata || {});

        tr.innerHTML = `
          <td class="text-slate-400 font-mono">${rec.timestamp || "-"}</td>
          <td><span class="user-pill-tag">${rec.user_id || "boss"}</span></td>
          <td><span class="action-pill-tag">${rec.action || rec.event_type}</span></td>
          <td class="text-slate-400">${rec.entity_type || "system"}</td>
          <td class="text-slate-500 font-mono">${rec.ip_address || "127.0.0.1"}</td>
          <td>
            <button class="inspect-meta-btn" data-json="${encodeURIComponent(metaStr)}">
              <i class="fa-solid fa-code"></i> View JSON
            </button>
          </td>
        `;
        ledgerTableBody.appendChild(tr);
      });

      // Bind metadata viewer buttons
      ledgerTableBody.querySelectorAll(".inspect-meta-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          const raw = decodeURIComponent(btn.getAttribute("data-json") || "{}");
          try {
            const parsed = JSON.parse(raw);
            if (metadataJsonDisplay) {
              metadataJsonDisplay.textContent = JSON.stringify(parsed, null, 2);
            }
          } catch (_) {
            if (metadataJsonDisplay) metadataJsonDisplay.textContent = raw;
          }
          if (metadataModal) metadataModal.classList.add("open");
        });
      });

    } catch (err) {
      console.warn("Failed to load ledger table:", err);
    }
  }

  // ── 60fps Canvas Area Chart Drawing Loop ──────────────────────────────────
  function startChartRenderLoop() {
    if (chartAnimationId) return;
    renderChartFrame();
  }

  function stopChartRenderLoop() {
    if (chartAnimationId) {
      cancelAnimationFrame(chartAnimationId);
      chartAnimationId = null;
    }
  }

  function renderChartFrame() {
    drawThroughputChart();
    chartAnimationId = requestAnimationFrame(renderChartFrame);
  }

  function drawThroughputChart() {
    if (!ledgerCanvas) return;
    const ctx = ledgerCanvas.getContext("2d");
    if (!ctx) return;

    const width = ledgerCanvas.width;
    const height = ledgerCanvas.height;

    // Check light mode
    const isLight = document.body.classList.contains("light-theme");

    // Clear background
    ctx.clearRect(0, 0, width, height);

    // Padding
    const padLeft = 40;
    const padRight = 15;
    const padTop = 20;
    const padBottom = 30;

    const chartW = width - padLeft - padRight;
    const chartH = height - padTop - padBottom;

    // Determine max EPS scale
    let maxEps = 10;
    for (const pt of chartPoints) {
      if (pt.eps > maxEps) maxEps = pt.eps;
    }
    maxEps = Math.ceil(maxEps * 1.25);

    // Draw horizontal gridlines & labels
    ctx.strokeStyle = isLight ? "rgba(203, 213, 225, 0.7)" : "rgba(71, 85, 105, 0.25)";
    ctx.lineWidth = 1;
    ctx.fillStyle = isLight ? "#475569" : "#64748b";
    ctx.font = "10px JetBrains Mono, monospace";
    ctx.textAlign = "right";

    const gridSteps = 4;
    for (let i = 0; i <= gridSteps; i++) {
      const yVal = Math.round((maxEps / gridSteps) * i);
      const yPos = padTop + chartH - (i / gridSteps) * chartH;

      ctx.beginPath();
      ctx.moveTo(padLeft, yPos);
      ctx.lineTo(width - padRight, yPos);
      ctx.stroke();

      ctx.fillText(`${yVal}`, padLeft - 8, yPos + 3);
    }

    // Draw Area fill & Line stroke
    if (chartPoints.length < 2) return;

    const stepX = chartW / (chartPoints.length - 1);

    // Gradient fill
    const grad = ctx.createLinearGradient(0, padTop, 0, padTop + chartH);
    if (isLight) {
      grad.addColorStop(0, "rgba(5, 150, 105, 0.35)");
      grad.addColorStop(0.5, "rgba(5, 150, 105, 0.12)");
      grad.addColorStop(1, "rgba(5, 150, 105, 0.0)");
    } else {
      grad.addColorStop(0, "rgba(16, 185, 129, 0.45)");
      grad.addColorStop(0.5, "rgba(16, 185, 129, 0.15)");
      grad.addColorStop(1, "rgba(16, 185, 129, 0.0)");
    }

    ctx.beginPath();
    ctx.moveTo(padLeft, padTop + chartH);

    for (let i = 0; i < chartPoints.length; i++) {
      const x = padLeft + i * stepX;
      const y = padTop + chartH - (chartPoints[i].eps / maxEps) * chartH;
      ctx.lineTo(x, y);
    }

    ctx.lineTo(padLeft + (chartPoints.length - 1) * stepX, padTop + chartH);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Line Stroke with Glow
    ctx.save();
    ctx.beginPath();
    ctx.shadowColor = isLight ? "rgba(5, 150, 105, 0.35)" : "#10b981";
    ctx.shadowBlur = isLight ? 4 : 10;
    ctx.strokeStyle = isLight ? "#059669" : "#10b981";
    ctx.lineWidth = 2.5;

    for (let i = 0; i < chartPoints.length; i++) {
      const x = padLeft + i * stepX;
      const y = padTop + chartH - (chartPoints[i].eps / maxEps) * chartH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();

    // Draw current head point pulse
    const lastX = padLeft + (chartPoints.length - 1) * stepX;
    const lastY = padTop + chartH - (chartPoints[chartPoints.length - 1].eps / maxEps) * chartH;

    ctx.beginPath();
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
    ctx.fillStyle = isLight ? "#059669" : "#34d399";
    ctx.fill();
    ctx.strokeStyle = isLight ? "#ffffff" : "#022c22";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  // ── Initialize on Startup ─────────────────────────────────────────────────
  loadModules();
  refreshMemoryBadge();
  loadSkillsArmory();
  fetchSessions(true);
  initLedgerHUD();

  // ── Lightning Cursor Tracker on Hero Cards (No Click Action) ──────────────
  document.querySelectorAll(".hero-action-card").forEach(card => {
    card.addEventListener("mousemove", (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      card.style.setProperty("--mouse-x", `${x}px`);
      card.style.setProperty("--mouse-y", `${y}px`);
    });
  });

  // Quick Chips Click Handler (if present elsewhere)
  document.querySelectorAll(".quick-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const prompt = chip.getAttribute("data-prompt");
      if (prompt && chatInput) {
        chatInput.value = prompt;
        chatInput.focus();
        handleSend();
      }
    });
  });

  if (threadSearchInput) {
    threadSearchInput.addEventListener("input", (e) => {
      renderSessionsList(e.target.value.trim().toLowerCase());
    });
  }

  if (refreshThreadsBtn) {
    refreshThreadsBtn.addEventListener("click", () => fetchSessions(false));
  }

});
