const state = {
  template: "podcast",
  aspectRatio: "9:16",
  captionStyle: "focus",
  captionMode: "auto",
  captionPrompt: "",
  autoHeadline: true,
  autoEmoji: false,
  kineticPop: true,
  uppercase: false,
  sourceMode: "upload",
  file: null,
  jobs: [],
  activeJobId: null,
  pollTimer: null,
  toastTimer: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const templateNames = {
  auto: "Smart Auto-Detect",
  podcast: "Podcast & conversation",
  educational: "Educational & how-to",
  story: "Storytelling",
  funny: "Funny moments",
  gaming: "Gaming highlights",
  music: "Music & performance",
};

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  })[char]);
}
function formatTime(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return minutes ? `${minutes}:${String(rest).padStart(2, "0")}` : `${rest}s`;
}
function formatBytes(bytes) {
  if (!bytes) return "0 MB";
  return bytes > 1024 ** 3 ? `${(bytes / 1024 ** 3).toFixed(1)} GB` : `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}
function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.classList.remove("show"), 3200);
}
function switchView(view) {
  $$(".view").forEach((node) => node.classList.toggle("active", node.id === `${view}-view`));
  $$(".nav-item").forEach((node) => node.classList.toggle("active", node.dataset.view === view));
  $("#breadcrumb-current").textContent = view === "create" ? "Create clips" : "Projects";
  if (view === "projects") renderProjects();
}
function setSourceMode(mode) {
  state.sourceMode = mode;
  $$(".source-tab").forEach((button) => button.classList.toggle("active", button.dataset.source === mode));
  $("#upload-panel").classList.toggle("active", mode === "upload");
  $("#link-panel").classList.toggle("active", mode === "link");
}
function setFile(file) {
  if (!file) return;
  const allowed = /\.(mp4|mov|mkv|webm|m4v|avi)$/i.test(file.name);
  if (!allowed) return showToast("Choose an MP4, MOV, MKV, WEBM, M4V, or AVI video.");
  if (file.size > 1024 * 1024 * 1024) return showToast("This MVP supports files up to 1 GB.");
  state.file = file;
  $("#upload-title").textContent = file.name;
  $("#upload-subtitle").textContent = `${formatBytes(file.size)} · ready to analyze`;
  $("#upload-subtitle").style.color = "#d5ff5f";
  $("#dropzone").classList.add("has-file");
  setSourceMode("upload");
}
function readSettings() {
  const min = Number($("#min-duration").value);
  const max = Number($("#max-duration").value);
  if (min >= max) {
    showToast("Maximum duration must be greater than minimum duration.");
    return null;
  }
  const captionMode = state.captionMode || "auto";
  const captionPrompt = captionMode === "prompt"
    ? ($("#caption-prompt-input") ? $("#caption-prompt-input").value.trim() : "")
    : "";
  return {
    template: state.template,
    aspect_ratio: state.aspectRatio,
    caption_style: state.captionStyle || ($("#caption-style") ? $("#caption-style").value : "focus"),
    caption_mode: captionMode,
    caption_prompt: captionPrompt,
    auto_headline: $("#caption-auto-headline") ? $("#caption-auto-headline").checked : true,
    kinetic_pop: $("#caption-kinetic-pop") ? $("#caption-kinetic-pop").checked : true,
    uppercase: $("#caption-uppercase") ? $("#caption-uppercase").checked : false,
    auto_emoji: false,
    clip_count: Number($("#clip-count").value),
    min_duration: min,
    max_duration: max,
    edit_prompt: $("#edit-prompt").value.trim(),
  };
}
async function createProject() {
  const settings = readSettings();
  if (!settings) return;
  if (state.sourceMode === "upload" && !state.file) {
    showToast("Upload a video first, or switch to Video link.");
    return;
  }
  if (state.sourceMode === "link" && !$("#video-url").value.trim()) {
    showToast("Paste a YouTube or Vimeo video link first.");
    return;
  }
  const button = $("#create-button");
  button.disabled = true;
  $("#create-button-label").textContent = "Starting your project…";
  try {
    let response;
    if (state.sourceMode === "upload") {
      const form = new FormData();
      form.append("file", state.file);
      Object.entries(settings).forEach(([key, value]) => form.append(key, String(value)));
      response = await fetch("/api/jobs/upload", { method: "POST", body: form });
    } else {
      response = await fetch("/api/jobs/url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...settings, source_url: $("#video-url").value.trim() }),
      });
    }
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not start this project.");
    state.activeJobId = data.id;
    state.jobs = [data, ...state.jobs.filter((job) => job.id !== data.id)];
    $("#active-processing").hidden = false;
    $("#latest-results").hidden = true;
    $("#processing-subtitle").textContent = `${templateNames[data.template] || data.template_label} · ${data.aspect_ratio} output`;
    renderProcessing(data);
    switchView("create");
    $("#active-processing").scrollIntoView({ behavior: "smooth", block: "start" });
    pollJob(data.id);
    showToast("Project queued. Cutflow is starting the analysis.");
  } catch (error) {
    showToast(error.message || "Something went wrong.");
  } finally {
    button.disabled = false;
    $("#create-button-label").textContent = "Find my best clips";
  }
}
async function pollJob(jobId) {
  clearTimeout(state.pollTimer);
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
    const job = await response.json();
    if (!response.ok) throw new Error(job.detail || "Could not load project status.");
    upsertJob(job);
    renderProcessing(job);
    if (job.status === "completed") {
      renderClips(job);
      showToast(`Ready. ${job.clips.length} clip${job.clips.length === 1 ? "" : "s"} created.`);
      return;
    }
    if (job.status === "failed") {
      renderClips(job);
      showToast(job.error || "Processing failed. Check the project status.");
      return;
    }
    if (job.status === "cancelled") {
      showToast("Processing was cancelled.");
      return;
    }
    state.pollTimer = setTimeout(() => pollJob(jobId), 2200);
  } catch (error) {
    $("#processing-subtitle").textContent = error.message || "Checking project status…";
    state.pollTimer = setTimeout(() => pollJob(jobId), 4000);
  }
}
function upsertJob(job) {
  const index = state.jobs.findIndex((item) => item.id === job.id);
  if (index >= 0) state.jobs[index] = job;
  else state.jobs.unshift(job);
  state.jobs.sort((a, b) => b.created_at - a.created_at);
  $("#project-count").textContent = state.jobs.length;
}
function renderProcessing(job) {
  const container = $("#processing-list");
  const percent = Number(job.progress || 0);
  $("#processing-percent").textContent = `${percent}%`;
  $("#processing-subtitle").textContent = job.message || job.stage || "Processing";
  const statusText = job.status === "completed" ? "Completed" : job.status === "failed" ? "Needs attention" : job.status === "cancelled" ? "Cancelled" : job.status === "queued" ? "In queue" : "In progress";
  const icon = job.status === "failed"
    ? '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>'
    : job.status === "completed"
    ? '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>'
    : job.status === "cancelled"
    ? '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
    : '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2v20M2 12h20M4.93 4.93l14.14 14.14M4.93 19.07l14.14-14.14"/></svg>';
  const canCancel = job.status === "queued" || job.status === "processing";
  container.innerHTML = `
    <article class="processing-card ${job.status}">
      <button class="close-processing-card-btn" data-dismiss-job="${escapeHtml(job.id)}" aria-label="Remove from view" title="Remove"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
      <div class="processing-head">
        <div class="processing-icon ${job.status === 'cancelled' ? 'cancelled' : ''}">${icon}</div>
        <div class="processing-info">
          <strong>${escapeHtml(job.source_url ? new URL(job.source_url).hostname : (state.file?.name || "Uploaded video"))}</strong>
          <span>${escapeHtml(job.stage || "Waiting")} · ${escapeHtml(statusText)} · ${escapeHtml(job.template_label || templateNames[job.template] || "")}</span>
        </div>
        <span class="processing-percent">${percent}%</span>
      </div>
      <div class="progress-track"><div class="progress-fill ${job.status === 'cancelled' ? 'cancelled' : ''}" style="width:${percent}%"></div></div>
      <div class="processing-actions">
        ${canCancel ? `<button class="cancel-processing-btn" data-cancel-job="${escapeHtml(job.id)}"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="margin-right:4px;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>Cancel processing</button>` : ""}
        ${job.status === "cancelled" || job.status === "failed" ? `<button class="dismiss-processing-btn" data-dismiss-job="${escapeHtml(job.id)}"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="margin-right:4px;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>Remove</button>` : ""}
      </div>
      ${job.style_match ? `
        <div class="style-match-badge ${job.style_match.matched ? "matched" : "mismatch"}">
          <span class="match-icon">${job.style_match.matched ? '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>' : '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>'}</span>
          <div class="match-details">
            <strong>${job.style_match.auto_detected ? `Auto-detected: ${escapeHtml(job.style_match.detected_label || "")}` : (job.style_match.matched ? `Style verified: ${escapeHtml(job.style_match.detected_label || "")}` : `Detected style: ${escapeHtml(job.style_match.detected_label || "")}`)}</strong>
            <span>${escapeHtml(job.style_match.message || (job.style_match.reasons && job.style_match.reasons.length ? job.style_match.reasons.join(" · ") : `Confidence: ${Math.round((job.style_match.confidence || 0) * 100)}%`))}</span>
          </div>
          <span class="match-confidence">${Math.round((job.style_match.confidence || 0) * 100)}% match</span>
        </div>` : ""}
      ${job.error ? `<p class="error-message">${escapeHtml(job.error)}</p>` : ""}
      ${job.warning ? `<p class="warning-message">${escapeHtml(job.warning)}</p>` : ""}
    </article>`;
}
function fitCardToVideo(video) {
  if (!video) return;
  const w = video.videoWidth;
  const h = video.videoHeight;
  if (!w || !h) return;
  const ratio = w / h;
  const card = video.closest(".clip-card");
  const preview = video.closest(".clip-preview");
  const badgeRatio = card ? card.querySelector(".clip-badge-ratio") : null;

  let ratioName = "9:16";
  let ratioClass = "ratio-9-16";
  let cssRatio = `${w} / ${h}`;

  if (ratio >= 1.35) {
    // Landscape (16:9, etc.)
    ratioName = "16:9";
    ratioClass = "ratio-16-9";
  } else if (ratio >= 0.85 && ratio < 1.35) {
    // Square (1:1)
    ratioName = "1:1";
    ratioClass = "ratio-1-1";
  } else {
    // Vertical (9:16, 4:5, etc.)
    ratioName = "9:16";
    ratioClass = "ratio-9-16";
  }

  if (preview) {
    preview.style.aspectRatio = cssRatio;
    preview.style.maxHeight = "none";
    preview.dataset.detectedRatio = ratioName;
    preview.dataset.videoWidth = String(w);
    preview.dataset.videoHeight = String(h);
  }
  if (card) {
    card.classList.remove("ratio-9-16", "ratio-16-9", "ratio-1-1");
    card.classList.add(ratioClass);
  }
  if (badgeRatio) {
    badgeRatio.textContent = `${ratioName} · ${w}×${h}`;
  }

  const grid = document.getElementById("clips-grid");
  if (grid) {
    grid.classList.toggle("aspect-16-9", ratioName === "16:9");
    grid.classList.toggle("aspect-1-1", ratioName === "1:1");
    grid.classList.toggle("aspect-9-16", ratioName === "9:16");
  }
}

function renderClips(job) {
  if (job.status !== "completed" && job.status !== "failed") return;
  $("#latest-results").hidden = false;
  $("#results-count").textContent = `${(job.clips || []).length} CLIPS`;
  const grid = $("#clips-grid");
  if (!job.clips?.length) {
    grid.innerHTML = `<div class="empty-state"><div class="empty-symbol"><svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg></div><strong>No clips were generated</strong><p>${escapeHtml(job.error || "Try a longer video or a different template.")}</p></div>`;
    return;
  }

  const jobRatio = job.aspect_ratio || "9:16";
  grid.classList.toggle("aspect-16-9", jobRatio === "16:9");
  grid.classList.toggle("aspect-1-1", jobRatio === "1:1");
  grid.classList.toggle("aspect-9-16", jobRatio === "9:16");

  grid.innerHTML = job.clips.map((clip, index) => {
    const defaultRatio = clip.aspect_ratio || job.aspect_ratio || "9:16";
    const ratioClass = defaultRatio === "16:9" ? "ratio-16-9" : defaultRatio === "1:1" ? "ratio-1-1" : "ratio-9-16";
    const initialCssRatio = defaultRatio === "16:9" ? "16 / 9" : defaultRatio === "1:1" ? "1 / 1" : "9 / 16";
    return `
    <article class="clip-card ${ratioClass}">
      <div class="clip-preview" style="aspect-ratio:${initialCssRatio};">
        <video controls preload="metadata" playsinline src="${escapeHtml(clip.download_url)}"></video>
        <span class="clip-badge">
          <span class="clip-badge-dot"></span>
          <span class="clip-badge-ratio">${escapeHtml(defaultRatio)}</span>
          <span>·</span>
          <span>${formatTime(clip.duration)}</span>
        </span>
      </div>
      <div class="clip-body">
        <div class="clip-topline"><strong>${escapeHtml(clip.title || `Clip ${index + 1}`)}</strong><span class="score-pill">${Number(clip.score)} / 100</span></div>
        <div class="clip-meta"><span>${formatTime(clip.start)} – ${formatTime(clip.end)}</span><span>${escapeHtml(clip.category || templateNames[clip.clip_style || job.template] || job.template_label)}</span></div>
        ${clip.finishing_label ? `
        <div class="clip-finishing-pill" title="${escapeHtml(clip.finishing_desc || "")}">
          <span class="finishing-spark"><svg viewBox="0 0 24 24" width="10" height="10" fill="currentColor" aria-hidden="true"><polygon points="12,2 15,9 22,12 15,15 12,22 9,15 2,12 9,9"/></svg></span>
          <strong>${escapeHtml(clip.finishing_label)}</strong>
          <span>${escapeHtml(clip.finishing_desc || "")}</span>
        </div>` : ""}
        <p class="clip-excerpt">${escapeHtml(clip.text || "")}</p>
        ${clip.reason ? `<p class="clip-reason">${escapeHtml(clip.reason)}</p>` : ""}
        <div class="quality-download-row">
          <label class="quality-select-label">QUALITY
            <select class="quality-select" data-download-url="${escapeHtml(clip.download_url)}" data-filename="${escapeHtml(clip.filename)}" aria-label="Download resolution">
              <option value="480">480p</option>
              <option value="720">720p</option>
              <option value="1080" selected>1080p</option>
              <option value="2k">2K</option>
            </select>
          </label>
          <a class="download-button" href="${escapeHtml(clip.download_url)}?resolution=1080" download="${escapeHtml(clip.filename)}"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="margin-right:4px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>Download 1080p</a>
        </div>
        <div class="subtitles-download-row">
          <span class="subtitles-label">SUBTITLES:</span>
          <a class="sub-download-btn" href="${escapeHtml(clip.download_url.replace('.mp4', '.srt'))}" download="${escapeHtml(clip.filename.replace('.mp4', '.srt'))}">
            <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
            .SRT
          </a>
          <a class="sub-download-btn" href="${escapeHtml(clip.download_url.replace('.mp4', '.ass'))}" download="${escapeHtml(clip.filename.replace('.mp4', '.ass'))}">
            <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
            .ASS (Karaoke)
          </a>
        </div>
        <p class="quality-download-note">First export at a new quality takes a moment. Later downloads are cached.</p>
      </div>
    </article>`;
  }).join("");

  // Dynamically detect intrinsic video aspect ratio when metadata loads
  grid.querySelectorAll("video").forEach((video) => {
    const onMeta = () => fitCardToVideo(video);
    if (video.readyState >= 1 && video.videoWidth) {
      fitCardToVideo(video);
    } else {
      video.addEventListener("loadedmetadata", onMeta, { once: true });
    }
  });
}
function renderProjects() {
  const list = $("#projects-list");
  const query = ($("#project-search").value || "").trim().toLowerCase();
  const filter = $("#project-filter").value;
  const filtered = state.jobs.filter((job) => {
    const name = job.source_url || state.file?.name || job.template_label || "";
    return (!query || name.toLowerCase().includes(query) || (job.template_label || "").toLowerCase().includes(query))
      && (filter === "all" || (filter === "processing" ? ["queued", "processing"].includes(job.status) : job.status === filter));
  });
  if (!filtered.length) {
    list.innerHTML = `<div class="empty-state"><div class="empty-symbol"><svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg></div><strong>${state.jobs.length ? "No matching projects" : "Your library is waiting"}</strong><p>${state.jobs.length ? "Try another search or status filter." : "Start with a video and your first clips will show up here."}</p></div>`;
    return;
  }
  list.innerHTML = filtered.map((job) => {
    let source = "Video project";
    try { if (job.source_url) source = new URL(job.source_url).hostname; } catch {}
    const status = job.status === "completed" ? "Completed" : job.status === "failed" ? "Needs attention" : job.status === "cancelled" ? "Cancelled" : job.status === "queued" ? "In queue" : "Processing";
    const date = new Date((job.created_at || Date.now() / 1000) * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    const canCancel = job.status === "queued" || job.status === "processing";
    return `<article class="project-row">
      <div class="project-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg></div>
      <div class="project-main"><strong>${escapeHtml(source)} · ${escapeHtml(job.template_label || templateNames[job.template] || "Video")}</strong><span>${escapeHtml(date)} · ${job.clips?.length || 0} clips · ${escapeHtml(job.aspect_ratio || "9:16")}</span></div>
      <span class="status-pill ${escapeHtml(job.status)}">${escapeHtml(status)}</span>
      ${canCancel ? `<button class="project-action cancel-action" data-cancel-job="${escapeHtml(job.id)}">Cancel</button>` : ""}
      <button class="project-action" data-open-job="${escapeHtml(job.id)}">Open</button>
      <button class="project-action" data-delete-job="${escapeHtml(job.id)}" aria-label="Delete project"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </article>`;
  }).join("");
}
async function refreshProjects() {
  try {
    const response = await fetch("/api/jobs");
    if (!response.ok) return;
    const jobs = await response.json();
    jobs.forEach(upsertJob);
    renderProjects();
  } catch {}
}
async function cancelProject(id) {
  if (!id) return;
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not cancel project.");
    upsertJob(data);
    renderProcessing(data);
    renderProjects();
    clearTimeout(state.pollTimer);
    if (state.activeJobId === id) {
      state.activeJobId = null;
    }
    showToast("Project processing was cancelled.");
    const button = $("#create-button");
    if (button) {
      button.disabled = false;
      $("#create-button-label").textContent = "Find my best clips";
    }
    const fileInput = $("#video-file");
    if (fileInput) fileInput.value = "";
  } catch (error) {
    showToast(error.message || "Failed to cancel project.");
  }
}
async function deleteProject(id) {
  if (!confirm("Delete this project and its generated clips? This cannot be undone.")) return;
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (!response.ok) throw new Error("Could not delete this project.");
    state.jobs = state.jobs.filter((job) => job.id !== id);
    if (state.activeJobId === id) {
      state.activeJobId = null;
      $("#active-processing").hidden = true;
      $("#latest-results").hidden = true;
    }
    $("#project-count").textContent = state.jobs.length;
    renderProjects();
    showToast("Project deleted.");
  } catch (error) { showToast(error.message); }
}
function dismissJob(id) {
  if (state.activeJobId === id || !id) {
    state.activeJobId = null;
    $("#active-processing").hidden = true;
    $("#latest-results").hidden = true;
    clearTimeout(state.pollTimer);
    const button = $("#create-button");
    if (button) {
      button.disabled = false;
      $("#create-button-label").textContent = "Find my best clips";
    }
  } else {
    $("#active-processing").hidden = true;
  }
}
function openProject(id) {
  const job = state.jobs.find((item) => item.id === id);
  if (!job) return;
  state.activeJobId = id;
  switchView("create");
  $("#active-processing").hidden = false;
  $("#latest-results").hidden = job.status !== "completed" && job.status !== "failed";
  renderProcessing(job);
  if (job.status === "completed" || job.status === "failed") renderClips(job);
  else pollJob(id);
  $("#active-processing").scrollIntoView({ behavior: "smooth", block: "start" });
}
function init() {
  $$(".nav-item").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
  $$(".template-card").forEach((button) => button.addEventListener("click", () => {
    state.template = button.dataset.template;
    $$(".template-card").forEach((card) => card.classList.toggle("selected", card === button));
  }));
  $$(".source-tab").forEach((button) => button.addEventListener("click", () => setSourceMode(button.dataset.source)));
  $$(".ratio-option").forEach((button) => button.addEventListener("click", () => {
    state.aspectRatio = button.dataset.ratio;
    $$(".ratio-option").forEach((item) => item.classList.toggle("selected", item === button));
  }));
  $("#clips-grid").addEventListener("change", (event) => {
    const select = event.target.closest(".quality-select");
    if (!select) return;
    const resolution = select.value;
    const card = select.closest(".clip-card");
    const link = card.querySelector(".download-button");
    const originalName = select.dataset.filename;
    const stem = originalName.replace(/\.mp4$/i, "");
    link.href = `${select.dataset.downloadUrl}?resolution=${encodeURIComponent(resolution)}`;
    link.download = resolution === "1080" ? originalName : `${stem}-${resolution}.mp4`;
    link.innerHTML = `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="margin-right:4px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>Download ${resolution === "2k" ? "2K" : `${resolution}p`}`;
  });

  // Caption Style Names & Selection Sync
  const captionStyleNames = {
    focus: "Focus · Inverted Dialogue Badge Boxes",
    linen: "Linen · Editorial Serif Hook & Subtitles",
    evo: "Evo · Frosted Glass Gradient Pill & Cyan Pop",
    lift: "Lift · Curved Header Banner & Emerald Pop",
    stack: "Stack · Brutalist Technical Box & Grid",
    align: "Align · Polaroid Frame & Letterbox Dialogue",
    prime: "Prime · Trending Viral Active Pop",
    impact: "Impact II · Bold High-Contrast Punch",
    paper: "Paper II · Polished Editorial Pill",
    elevate: "Elevate · Luxury Minimal Aesthetic",
    pop: "Pop · Bouncy Neon Kinetic",
    y2k: "Y2K · Retro Cyberpunk Glow",
    chalk: "Chalk · Tutorial Sketch Highlighter",
    clean: "Clean · Subtitle Standard",
    pulse: "Pulse · Dynamic Karaoke Highlight",
    glow: "Neon Cyber Glow · Radiant Glowing Accent",
    hormozi: "Hormozi Gold Pop · Bold Creator Style",
    karaoke: "Dynamic Karaoke Pill · High-Contrast Pill",
  };

  function selectCaptionStyle(style) {
    if (!style) return;
    state.captionStyle = style;
    $$(".caption-card").forEach((c) => {
      c.classList.toggle("selected", c.dataset.captionStyle === style);
    });
    const select = $("#caption-style");
    if (select) select.value = style;
    const label = captionStyleNames[style] || style;
    const indicator = $("#active-caption-name");
    if (indicator) indicator.textContent = label;
    const modalLabel = $("#modal-active-label");
    if (modalLabel) modalLabel.textContent = label;
  }

  // Visual 9:16 Caption Style Cards (Showcase + Modal Grid)
  $$(".caption-card").forEach((card) => {
    card.addEventListener("click", () => {
      selectCaptionStyle(card.dataset.captionStyle);
    });
  });

  const captionSelect = $("#caption-style");
  if (captionSelect) {
    captionSelect.addEventListener("change", (event) => {
      selectCaptionStyle(event.target.value);
    });
  }

  // Caption Explorer Modal
  const modal = $("#caption-explorer-modal");
  function openCaptionExplorer() {
    if (modal) {
      modal.hidden = false;
      modal.classList.add("open");
      document.body.style.overflow = "hidden";
    }
  }
  function closeCaptionExplorer() {
    if (modal) {
      modal.classList.remove("open");
      setTimeout(() => { modal.hidden = true; }, 220);
      document.body.style.overflow = "";
    }
  }

  const openModalBtn = $("#open-caption-explorer-btn");
  if (openModalBtn) openModalBtn.addEventListener("click", openCaptionExplorer);

  const closeModalBtn = $("#close-caption-explorer-btn");
  if (closeModalBtn) closeModalBtn.addEventListener("click", closeCaptionExplorer);

  const modalApplyBtn = $("#modal-apply-btn");
  if (modalApplyBtn) {
    modalApplyBtn.addEventListener("click", () => {
      closeCaptionExplorer();
      showToast(`Selected ${captionStyleNames[state.captionStyle] || state.captionStyle}`);
    });
  }

  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeCaptionExplorer();
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal && modal.classList.contains("open")) {
      closeCaptionExplorer();
    }
  });

  // Modal Category Filter Tabs
  $$(".caption-tab-btn").forEach((tab) => {
    tab.addEventListener("click", () => {
      $$(".caption-tab-btn").forEach((t) => t.classList.toggle("active", t === tab));
      const cat = tab.dataset.category;
      $$("#modal-caption-grid .caption-card").forEach((card) => {
        if (cat === "all") {
          card.style.display = "";
        } else {
          const cardCats = (card.dataset.category || "").split(" ");
          card.style.display = cardCats.includes(cat) ? "" : "none";
        }
      });
    });
  });
  $$(".caption-mode-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const mode = tab.dataset.captionMode;
      state.captionMode = mode;
      $$(".caption-mode-tab").forEach((t) => {
        const active = t === tab;
        t.classList.toggle("active", active);
        t.setAttribute("aria-selected", active ? "true" : "false");
      });
      const autoPanel = $("#caption-auto-panel");
      const promptPanel = $("#caption-prompt-panel");
      if (autoPanel) autoPanel.style.display = mode === "auto" ? "block" : "none";
      if (promptPanel) promptPanel.style.display = mode === "prompt" ? "block" : "none";
    });
  });
  $$(".prompt-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const input = $("#caption-prompt-input");
      if (!input) return;
      input.value = chip.dataset.prompt;
      state.captionPrompt = chip.dataset.prompt;
      input.focus();
    });
  });
  if ($("#caption-prompt-input")) {
    $("#caption-prompt-input").addEventListener("input", (event) => {
      state.captionPrompt = event.target.value;
    });
  }
  if ($("#caption-auto-headline")) {
    $("#caption-auto-headline").addEventListener("change", (event) => {
      state.autoHeadline = event.target.checked;
    });
  }
  if ($("#caption-kinetic-pop")) {
    $("#caption-kinetic-pop").addEventListener("change", (event) => { state.kineticPop = event.target.checked; });
  }
  if ($("#caption-uppercase")) {
    $("#caption-uppercase").addEventListener("change", (event) => { state.uppercase = event.target.checked; });
  }
  $("#video-file").addEventListener("click", () => { $("#video-file").value = ""; });
  $("#video-file").addEventListener("change", (event) => setFile(event.target.files?.[0]));
  const dropzone = $("#dropzone");
  ["dragenter", "dragover"].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.remove("dragover"); }));
  dropzone.addEventListener("drop", (event) => setFile(event.dataTransfer.files?.[0]));
  $("#clear-url").addEventListener("click", () => { $("#video-url").value = ""; });
  $("#count-minus").addEventListener("click", () => updateCount(-1));
  $("#count-plus").addEventListener("click", () => updateCount(1));
  $("#create-button").addEventListener("click", createProject);
  $("#new-project-button").addEventListener("click", () => switchView("create"));
  $("#project-search").addEventListener("input", renderProjects);
  $("#project-filter").addEventListener("change", renderProjects);
  $("#processing-list").addEventListener("click", (event) => {
    const cancel = event.target.closest("[data-cancel-job]");
    const dismiss = event.target.closest("[data-dismiss-job]");
    if (cancel) cancelProject(cancel.dataset.cancelJob);
    else if (dismiss) dismissJob(dismiss.dataset.dismissJob);
  });
  $("#projects-list").addEventListener("click", (event) => {
    const open = event.target.closest("[data-open-job]");
    const remove = event.target.closest("[data-delete-job]");
    const cancel = event.target.closest("[data-cancel-job]");
    if (cancel) cancelProject(cancel.dataset.cancelJob);
    else if (open) openProject(open.dataset.openJob);
    else if (remove) deleteProject(remove.dataset.deleteJob);
  });
  $("#min-duration").addEventListener("change", () => {
    if (Number($("#min-duration").value) >= Number($("#max-duration").value)) {
      const options = [...$("#max-duration").options].map((option) => Number(option.value));
      $("#max-duration").value = String(options.find((value) => value > Number($("#min-duration").value)) || 90);
    }
  });
  $("#max-duration").addEventListener("change", () => {
    if (Number($("#min-duration").value) >= Number($("#max-duration").value)) {
      const options = [...$("#min-duration").options].map((option) => Number(option.value)).reverse();
      $("#min-duration").value = String(options.find((value) => value < Number($("#max-duration").value)) || 10);
    }
  });
  refreshProjects();
}
function updateCount(delta) {
  const input = $("#clip-count");
  input.value = String(Math.max(1, Math.min(8, Number(input.value) + delta)));
  $("#clip-count-value").textContent = input.value;
}
document.addEventListener("DOMContentLoaded", init);
