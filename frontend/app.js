const state = {
  template: "podcast",
  aspectRatio: "9:16",
  fitMode: "blur",
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
    fit_mode: state.fitMode || "blur",
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
    const isJson = (response.headers.get("content-type") || "").includes("application/json");
    if (!response.ok) {
      let msg = "Server temporarily unavailable. Please retry.";
      if (isJson) {
        const err = await response.json().catch(() => ({}));
        msg = err.detail || msg;
      }
      throw new Error(msg);
    }
    const data = isJson ? await response.json() : {};
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
    if (response.status === 404) {
      // Job was deleted or history purged: stop polling immediately
      state.activeJobId = null;
      $("#active-processing").hidden = true;
      return;
    }
    const isJson = (response.headers.get("content-type") || "").includes("application/json");
    if (!response.ok || !isJson) {
      // Temporary network or tunnel latency: silently retry without crashing
      state.pollTimer = setTimeout(() => pollJob(jobId), 3000);
      return;
    }
    const job = await response.json();
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
  } catch {
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
        ${job.status === "failed" ? `<button class="retry-processing-btn" data-retry-job="${escapeHtml(job.id)}"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="margin-right:4px;"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>Retry Clipping</button>` : ""}
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
        <div class="clip-topline">
          <strong>${escapeHtml(clip.title || `Clip ${index + 1}`)}</strong>
          <span style="display:inline-flex;gap:6px;align-items:center;">
            ${job.style_match ? `<span class="match-pill" title="${escapeHtml(job.style_match.message || 'Style verified')}"><svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>${Math.round((job.style_match.confidence || 0) * 100)}% match</span>` : ""}
            <span class="score-pill">${Number(clip.score)} / 100</span>
          </span>
        </div>
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
        <button type="button" class="wysiwyg-edit-btn" data-clip-index="${index}" data-filename="${escapeHtml(clip.filename)}">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          <span>Interactive Caption Studio (WYSIWYG)</span>
        </button>
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

  // Attach WYSIWYG studio opener buttons
  grid.querySelectorAll(".wysiwyg-edit-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const clipIdx = parseInt(btn.dataset.clipIndex, 10);
      const clip = (job.clips || [])[clipIdx];
      if (clip) openCaptionStudio(clip, job);
    });
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
      ${job.status === "failed" ? `<button class="project-action retry-action" data-retry-job="${escapeHtml(job.id)}"><svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>Retry</button>` : ""}
      ${canCancel ? `<button class="project-action cancel-action" data-cancel-job="${escapeHtml(job.id)}">Cancel</button>` : ""}
      <button class="project-action" data-open-job="${escapeHtml(job.id)}">Open</button>
      <button class="project-action" data-delete-job="${escapeHtml(job.id)}" aria-label="Delete project"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </article>`;
  }).join("");
}
async function refreshProjects() {
  try {
    const response = await fetch("/api/jobs");
    const isJson = (response.headers.get("content-type") || "").includes("application/json");
    if (!response.ok || !isJson) return;
    const jobs = await response.json();
    jobs.forEach(upsertJob);
    renderProjects();
  } catch {}
}
async function retryProject(id) {
  if (!id) return;
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(id)}/retry`, { method: "POST" });
    const isJson = (response.headers.get("content-type") || "").includes("application/json");
    if (!isJson) { showToast("Server temporarily unavailable. Please retry."); return; }
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not reprocess project.");
    upsertJob(data);
    state.activeJobId = id;
    $("#active-processing").hidden = false;
    $("#latest-results").hidden = true;
    renderProcessing(data);
    renderProjects();
    switchView("create");
    showToast("Reprocessing clipping job with existing source file…");
    pollJob(id);
  } catch (error) {
    showToast(error.message || "Failed to retry project.");
  }
}
async function cancelProject(id) {
  if (!id) return;
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" });
    const isJson = (response.headers.get("content-type") || "").includes("application/json");
    if (!isJson) { showToast("Server temporarily unavailable. Please retry."); return; }
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
async function deleteAllProjects() {
  if (!confirm("Are you sure you want to delete all projects and generated clips? This cannot be undone.")) return;
  try {
    const response = await fetch("/api/jobs", { method: "DELETE" });
    const isJson = (response.headers.get("content-type") || "").includes("application/json");
    if (!response.ok) {
      let msg = "Could not delete all projects.";
      if (isJson) {
        const err = await response.json().catch(() => ({}));
        msg = err.detail || msg;
      }
      throw new Error(msg);
    }
    const data = isJson ? await response.json() : {};
    state.jobs = [];
    state.activeJobId = null;
    clearTimeout(state.pollTimer);
    $("#active-processing").hidden = true;
    $("#latest-results").hidden = true;
    $("#project-count").textContent = "0";
    const button = $("#create-button");
    if (button) {
      button.disabled = false;
      $("#create-button-label").textContent = "Find my best clips";
    }
    renderProjects();
    showToast(`All projects deleted (${data.deleted_count ?? 0} removed).`);
  } catch (error) {
    showToast(error.message || "Failed to delete projects.");
  }
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
  $$(".fit-mode-btn").forEach((button) => button.addEventListener("click", () => {
    state.fitMode = button.dataset.fitMode;
    $$(".fit-mode-btn").forEach((item) => {
      const isSelected = item === button;
      item.classList.toggle("selected", isSelected);
      item.setAttribute("aria-checked", isSelected ? "true" : "false");
    });
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

  // Caption Style Names & Selection Sync (Phase 4 Archetypes)
  const captionStyleNames = {
    hormozi: "Hormozi Punch · Komika Heavy Strike",
    impact: "Impact II · Anton Massive Punch",
    glow: "Cyberpunk · Syne Neon Bloom",
    prime: "Prime · The Bold Font Viral Pop",
    align: "Align · Bebas Neue Letterbox",
    pop: "Pop · Bouncy Neon Kinetic",
    paper: "Paper II · Polished Editorial Pill",
    evo: "Evo · Frosted Glass Gradient Pill",
    linen: "Linen · Editorial Serif Hook",
    focus: "Focus · Inverted Dialogue Badge Boxes",
    stack: "Stack · JetBrains Mono Brutalist Grid",
    y2k: "Y2K · Cyberpunk Scanlines",
    lift: "Lift · Curved Header Banner & Emerald Pop",
    chalk: "Chalk · Tutorial Sketch Highlighter",
    pulse: "Pulse Viral · Montserrat Dynamic Wave",
    elevate: "Elevate · Luxury Minimal Aesthetic",
    karaoke: "Dynamic Karaoke Pill · Lime Glider",
    clean: "Clean · Subtitle Standard",
  };

  const PRESET_RECIPES = {
    hormozi: {
      font: "Komika Axis",
      uppercase: true,
      kinetic_mode: "pop",
      tilt_deg: -2.5,
      colors: { primary: "#ffffff", accent: "#ffe600", outline: "#000000", upcoming: "#999999", fill: "#ffffff", fill_text: "#000000" },
      shader_stack: {
        outer_stroke: { width: 2.4, color: "#000000" },
        inner_stroke: { width: 0.7, color: "#ffffff" },
        active_gradient: ["#FFE600", "#FF8400"],
        shadow: { blur: 6.0, x: 0, y: 4.0, color: "rgba(0, 0, 0, 0.90)" },
      },
      spring_physics: { tension: 300, friction: 13, mass: 1.0, scale_overshoot: 1.28, slide_y_px: 8 },
      caption_box: "none",
    },
    impact: {
      font: "Anton",
      uppercase: true,
      kinetic_mode: "pop",
      tilt_deg: 1.5,
      colors: { primary: "#ffffff", accent: "#d5ff5f", outline: "#000000", upcoming: "#999999", fill: "#ffffff", fill_text: "#000000" },
      shader_stack: {
        outer_stroke: { width: 2.8, color: "#000000" },
        active_gradient: ["#D5FF5F", "#A6FF00"],
        shadow: { blur: 12.0, x: 0, y: 6.0, color: "rgba(0, 0, 0, 0.85)" },
      },
      spring_physics: { tension: 320, friction: 14, mass: 1.0, scale_overshoot: 1.30, slide_y_px: 8 },
      caption_box: "none",
    },
    glow: {
      font: "Syne",
      uppercase: true,
      kinetic_mode: "wave",
      colors: { primary: "#f0fdf4", accent: "#00f5d4", outline: "#0b0d13", upcoming: "#98a2b3", fill: "#ffffff", fill_text: "#000000" },
      shader_stack: {
        outer_stroke: { width: 1.8, color: "#0B0D13" },
        glow: { blur: 22.0, color: "#00F5D4" },
        active_gradient: ["#B0FFEA", "#00F5D4"],
        shadow: { blur: 8.0, x: 0, y: 3.0, color: "rgba(0, 0, 0, 0.80)" },
      },
      spring_physics: { tension: 240, friction: 16, mass: 1.0, scale_overshoot: 1.18, slide_y_px: 8 },
      caption_box: "none",
    },
    prime: {
      font: "The Bold Font",
      uppercase: true,
      kinetic_mode: "pop",
      colors: { primary: "#ffffff", accent: "#fff500", outline: "#10110f", upcoming: "#999999", fill: "#ffffff", fill_text: "#000000" },
      shader_stack: {
        outer_stroke: { width: 2.2, color: "#10110F" },
        active_gradient: ["#FFF500", "#FF6B6B"],
        shadow: { blur: 6.0, x: 0, y: 3.0, color: "rgba(0, 0, 0, 0.80)" },
      },
      spring_physics: { tension: 270, friction: 15, mass: 1.0, scale_overshoot: 1.22, slide_y_px: 8 },
      caption_box: "none",
    },
    align: {
      font: "Bebas Neue",
      uppercase: true,
      kinetic_mode: "wave",
      frame: "letterbox",
      colors: { primary: "#ffffff", accent: "#fff3b0", outline: "#141414", upcoming: "#b4b4b4", fill: "#ffffff", fill_text: "#000000" },
      shader_stack: {
        outer_stroke: { width: 1.2, color: "#141414" },
        active_gradient: ["#FFF3B0", "#E09F3E"],
      },
      spring_physics: { tension: 210, friction: 19, mass: 1.0, scale_overshoot: 1.15, slide_y_px: 8 },
      caption_box: "none",
    },
    pop: {
      font: "The Bold Font",
      uppercase: true,
      kinetic_mode: "pop",
      colors: { primary: "#ffffff", accent: "#ff007f", outline: "#120a1e", upcoming: "#999999", fill: "#ffffff", fill_text: "#000000" },
      shader_stack: {
        outer_stroke: { width: 2.4, color: "#120A1E" },
        inner_stroke: { width: 0.8, color: "#FF007F" },
        glow: { blur: 16.0, color: "#FF007F" },
        active_gradient: ["#FF007F", "#FFAA00"],
      },
      spring_physics: { tension: 290, friction: 14, mass: 1.0, scale_overshoot: 1.24, slide_y_px: 8 },
      caption_box: "none",
    },
    paper: {
      font: "Merriweather",
      uppercase: false,
      kinetic_mode: "glider",
      colors: { primary: "#120f0e", accent: "#2acbc7", outline: "#120f0e", upcoming: "#78716c", fill: "#f7ece7", fill_text: "#120f0e" },
      shader_stack: {
        shadow: { blur: 14.0, x: 0, y: 5.0, color: "rgba(0, 0, 0, 0.35)" },
      },
      spring_physics: { tension: 200, friction: 18, mass: 1.0, scale_overshoot: 1.12, slide_y_px: 8 },
      caption_box: "pill",
    },
    evo: {
      font: "Montserrat",
      uppercase: true,
      kinetic_mode: "glider",
      colors: { primary: "#ffffff", accent: "#00ffff", outline: "#161420", upcoming: "#a9a9a9", fill: "#221832", fill_text: "#ffffff" },
      shader_stack: {
        glow: { blur: 18.0, color: "#00FFFF" },
        active_gradient: ["#D0FFFF", "#00FFFF"],
      },
      spring_physics: { tension: 200, friction: 18, mass: 1.0, scale_overshoot: 1.15, slide_y_px: 8 },
      caption_box: "pill",
    },
    linen: {
      font: "Merriweather",
      uppercase: false,
      kinetic_mode: "wave",
      frame: "rules",
      colors: { primary: "#f7f4ec", accent: "#00c4a8", outline: "#1e1c1a", upcoming: "#999999", fill: "#ffffff", fill_text: "#000000" },
      shader_stack: {
        outer_stroke: { width: 0.8, color: "#1E1C1A" },
        shadow: { blur: 5.0, x: 0, y: 2.0, color: "rgba(0, 0, 0, 0.50)" },
      },
      spring_physics: { tension: 210, friction: 19, mass: 1.0, scale_overshoot: 1.15, slide_y_px: 8 },
      caption_box: "none",
    },
    focus: {
      font: "Montserrat",
      uppercase: true,
      kinetic_mode: "pop",
      colors: { primary: "#ffffff", accent: "#00ffff", outline: "#141414", upcoming: "#999999", fill: "#ffffff", fill_text: "#000000" },
      shader_stack: {
        shadow: { blur: 8.0, x: 0, y: 4.0, color: "rgba(0, 0, 0, 0.60)" },
      },
      spring_physics: { tension: 280, friction: 24, mass: 1.0, scale_overshoot: 1.18, slide_y_px: 8 },
      caption_box: "per_word",
    },
    stack: {
      font: "JetBrains Mono",
      uppercase: true,
      kinetic_mode: "pop",
      frame: "grid",
      colors: { primary: "#ffffff", accent: "#00ffff", outline: "#000000", upcoming: "#777777", fill: "#ffffff", fill_text: "#000000" },
      shader_stack: {
        outer_stroke: { width: 1.6, color: "#000000" },
        active_gradient: ["#FAFF00", "#70FF00"],
      },
      spring_physics: { tension: 250, friction: 18, mass: 1.0, scale_overshoot: 1.16, slide_y_px: 8 },
      caption_box: "none",
    },
    y2k: {
      font: "JetBrains Mono",
      uppercase: true,
      kinetic_mode: "wave",
      frame: "scanlines",
      colors: { primary: "#ffffff", accent: "#ff007f", outline: "#000000", upcoming: "#777777", fill: "#ff007f", fill_text: "#ffffff" },
      shader_stack: {
        glow: { blur: 20.0, color: "#FF007F" },
        active_gradient: ["#FF007F", "#FFAA00"],
      },
      spring_physics: { tension: 240, friction: 16, mass: 1.0, scale_overshoot: 1.16, slide_y_px: 8 },
      caption_box: "none",
    },
    lift: {
      font: "Bebas Neue",
      uppercase: true,
      kinetic_mode: "pop",
      colors: { primary: "#ffffff", accent: "#05ffd5", outline: "#101812", upcoming: "#999999", fill: "#ffffff", fill_text: "#000000" },
      shader_stack: {
        outer_stroke: { width: 1.8, color: "#101812" },
        active_gradient: ["#B5FFEA", "#05FFD5"],
      },
      spring_physics: { tension: 260, friction: 16, mass: 1.0, scale_overshoot: 1.20, slide_y_px: 8 },
      caption_box: "none",
    },
    chalk: {
      font: "Merriweather",
      uppercase: false,
      kinetic_mode: "wave",
      frame: "rules",
      colors: { primary: "#ffffff", accent: "#00d4fd", outline: "#141414", upcoming: "#999999", fill: "#00d4fd", fill_text: "#141414" },
      shader_stack: {
        shadow: { blur: 6.0, x: 0, y: 3.0, color: "rgba(0, 0, 0, 0.40)" },
      },
      spring_physics: { tension: 220, friction: 18, mass: 1.0, scale_overshoot: 1.14, slide_y_px: 8 },
      caption_box: "none",
    },
    pulse: {
      font: "Montserrat",
      uppercase: true,
      kinetic_mode: "wave",
      colors: { primary: "#ffffff", accent: "#66f4c6", outline: "#121410", upcoming: "#888888", fill: "#ffffff", fill_text: "#000000" },
      shader_stack: {
        outer_stroke: { width: 2.0, color: "#121410" },
        active_gradient: ["#C6FFED", "#66F4C6"],
      },
      spring_physics: { tension: 220, friction: 18, mass: 1.0, scale_overshoot: 1.16, slide_y_px: 8 },
      caption_box: "none",
    },
    elevate: {
      font: "Montserrat",
      uppercase: true,
      kinetic_mode: "wave",
      frame: "rules",
      colors: { primary: "#f2f2f2", accent: "#009c63", outline: "#101010", upcoming: "#666666", fill: "#ffffff", fill_text: "#000000" },
      shader_stack: {
        outer_stroke: { width: 0.5, color: "#101010" },
      },
      spring_physics: { tension: 200, friction: 20, mass: 1.0, scale_overshoot: 1.12, slide_y_px: 8 },
      caption_box: "none",
    },
    karaoke: {
      font: "Montserrat",
      uppercase: false,
      kinetic_mode: "glider",
      colors: { primary: "#ffffff", accent: "#d5ff5f", outline: "#181a14", upcoming: "#999999", fill: "#131a1b", fill_text: "#ffffff" },
      spring_physics: { tension: 210, friction: 18, mass: 1.0, scale_overshoot: 1.14, slide_y_px: 8 },
      caption_box: "pill",
    },
    clean: {
      font: "Montserrat",
      uppercase: false,
      kinetic_mode: "none",
      colors: { primary: "#ffffff", accent: "#66f4c6", outline: "#141414", upcoming: "#999999", fill: "#ffffff", fill_text: "#000000" },
      caption_box: "none",
    },
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

  // Modal Category Segmented Control
  $$(".caption-segmented-btn").forEach((tab) => {
    tab.addEventListener("click", () => {
      $$(".caption-segmented-btn").forEach((t) => {
        const isActive = t === tab;
        t.classList.toggle("active", isActive);
        t.setAttribute("aria-selected", isActive ? "true" : "false");
      });
      const cat = tab.dataset.categoryTab;
      $$("#modal-caption-grid .caption-card").forEach((card) => {
        if (!cat || cat === "all") {
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
  const deleteAllBtn = $("#delete-all-projects-button");
  if (deleteAllBtn) {
    deleteAllBtn.addEventListener("click", deleteAllProjects);
  }
  $("#project-search").addEventListener("input", renderProjects);
  $("#project-filter").addEventListener("change", renderProjects);
  $("#processing-list").addEventListener("click", (event) => {
    const retry = event.target.closest("[data-retry-job]");
    const cancel = event.target.closest("[data-cancel-job]");
    const dismiss = event.target.closest("[data-dismiss-job]");
    if (retry) retryProject(retry.dataset.retryJob);
    else if (cancel) cancelProject(cancel.dataset.cancelJob);
    else if (dismiss) dismissJob(dismiss.dataset.dismissJob);
  });
  $("#projects-list").addEventListener("click", (event) => {
    const retry = event.target.closest("[data-retry-job]");
    const open = event.target.closest("[data-open-job]");
    const remove = event.target.closest("[data-delete-job]");
    const cancel = event.target.closest("[data-cancel-job]");
    if (retry) retryProject(retry.dataset.retryJob);
    else if (cancel) cancelProject(cancel.dataset.cancelJob);
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

if (typeof window !== "undefined") {
  if (window.FontLoader) window.FontLoader.preloadAll();
  if (window.StickerCompositor) window.StickerCompositor.preloadAll();
}


// ── WYSIWYG Caption Studio Live Controller (Phase 2) ─────────────────────────

let activeStudio = {
  clip: null,
  job: null,
  timeline: null,
  rafId: null,
  activeWordIdx: -1,
  cleanups: [],
};

function formatTimePrecise(seconds) {
  if (isNaN(seconds) || seconds < 0) return "00:00.00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  const cs = Math.floor((seconds % 1) * 100);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(cs).padStart(2, "0")}`;
}

async function openCaptionStudio(clip, job) {
  const modal = $("#caption-studio-modal");
  if (!modal) return;

  // Clean up any prior running studio instance
  closeCaptionStudio();

  activeStudio.clip = clip;
  activeStudio.job = job;

  // Ensure full timeline is available: from clip or fetch from API
  if (clip.timeline && clip.timeline.words) {
    activeStudio.timeline = JSON.parse(JSON.stringify(clip.timeline));
  } else {
    try {
      const res = await fetch(`/api/jobs/${job.id}/clips/${clip.filename}/timeline`);
      if (res.ok) {
        activeStudio.timeline = await res.json();
      } else {
        showToast("Loading timeline...");
        activeStudio.timeline = {
          start_ms: Math.round((clip.start || 0) * 1000),
          end_ms: Math.round((clip.end || (clip.start + clip.duration || 5)) * 1000),
          aspect_ratio: clip.aspect_ratio || job.aspect_ratio || "9:16",
          styling_metadata: { preset_key: job.caption_style || "focus" },
          words: [],
          phrases: [],
        };
      }
    } catch {
      activeStudio.timeline = { words: [], phrases: [] };
    }
  }

  // Deterministically ensure active font is ready before initial canvas frame draw
  if (window.FontLoader && activeStudio.timeline && activeStudio.timeline.styling_metadata) {
    const fName = activeStudio.timeline.styling_metadata.font || 'Montserrat';
    await window.FontLoader.ensureFont(fName);
  }

  // Populate Video Source
  const video = $("#studio-video");
  const canvas = $("#studio-overlay-canvas");
  const ctx = canvas.getContext("2d");
  const scrubber = $("#studio-scrubber");
  const timeDisplay = $("#studio-time-display");
  const playBtn = $("#studio-play-btn");
  const playIcon = $("#studio-play-icon");

  video.src = clip.download_url;
  video.currentTime = 0;
  scrubber.value = 0;

  // Populate Presets Scroller
  const presetsContainer = $("#studio-presets-scroller");
  const presetKeys = Object.keys(captionStyleNames);
  const currentKey = activeStudio.timeline?.styling_metadata?.preset_key || job.caption_style || "focus";
  $("#studio-active-preset-badge").textContent = currentKey.toUpperCase();

  presetsContainer.innerHTML = presetKeys.map((k) => `
    <button type="button" class="studio-preset-chip ${k === currentKey ? "active" : ""}" data-preset-key="${k}">
      ${escapeHtml(k.toUpperCase())}
    </button>
  `).join("");

  presetsContainer.querySelectorAll(".studio-preset-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const key = chip.dataset.presetKey;
      presetsContainer.querySelectorAll(".studio-preset-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      $("#studio-active-preset-badge").textContent = key.toUpperCase();

      // Zero-latency update: switch styling metadata and immediately redraw
      if (activeStudio.timeline) {
        if (!activeStudio.timeline.styling_metadata) activeStudio.timeline.styling_metadata = {};
        activeStudio.timeline.styling_metadata.preset_key = key;
        activeStudio.timeline.styling_metadata.label = captionStyleNames[key] || key;

        const recipe = PRESET_RECIPES[key];
        if (recipe) {
          Object.assign(activeStudio.timeline.styling_metadata, JSON.parse(JSON.stringify(recipe)));
        }

        if (window.FontLoader && recipe && recipe.font) {
          window.FontLoader.ensureFont(recipe.font).then(() => renderStudioFrame());
        } else {
          renderStudioFrame();
        }

        if (sfxMixer) sfxMixer.syncTimeline(activeStudio.timeline);
      }
    });
  });

  // Initialize Phase 5 Synchronized SFX Sub-Mixer
  let sfxMixer = null;
  if (window.SFXSubMixer) {
    sfxMixer = new window.SFXSubMixer();
    sfxMixer.attachVideo(video);
    sfxMixer.syncTimeline(activeStudio.timeline);
    activeStudio.cleanups.push(() => {
      if (sfxMixer) {
        sfxMixer.dispose();
        sfxMixer = null;
      }
    });
  }

  // Populate Words List with inline text edit & -50ms/+50ms nudge buttons
  renderStudioWordsList();

  function renderStudioFrame() {
    if (!video || !canvas || !activeStudio.timeline) return;
    const w = video.videoWidth || 1080;
    const h = video.videoHeight || 1920;
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }

    const t = video.currentTime || 0;
    const dur = video.duration || clip.duration || 1;
    scrubber.value = (t / dur) * 100;
    timeDisplay.textContent = `${formatTimePrecise(t)} / ${formatTimePrecise(dur)}`;

    if (window.CaptionCanvasRenderer) {
      const res = window.CaptionCanvasRenderer.renderFrame(ctx, activeStudio.timeline, t, w, h);
      highlightActiveWordRow(res.activeWordIdx);
    }

    if (sfxMixer) {
      sfxMixer.update(t, video.paused);
    }
  }

  function frameLoop() {
    renderStudioFrame();
    if (!video.paused && !video.ended) {
      activeStudio.rafId = requestAnimationFrame(frameLoop);
    }
  }

  // Play/Pause transport
  function togglePlay() {
    if (video.paused) {
      video.play();
    } else {
      video.pause();
    }
  }

  function onPlay() {
    playIcon.innerHTML = `<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>`;
    if (!activeStudio.rafId) activeStudio.rafId = requestAnimationFrame(frameLoop);
  }

  function onPause() {
    playIcon.innerHTML = `<polygon points="5 3 19 12 5 21 5 3"/>`;
    if (activeStudio.rafId) {
      cancelAnimationFrame(activeStudio.rafId);
      activeStudio.rafId = null;
    }
    if (sfxMixer) sfxMixer.unduck();
    renderStudioFrame();
  }

  function onScrub(e) {
    const pct = parseFloat(e.target.value) / 100;
    const dur = video.duration || clip.duration || 1;
    video.currentTime = pct * dur;
    if (sfxMixer) sfxMixer.resetTracking();
    renderStudioFrame();
  }

  playBtn.addEventListener("click", togglePlay);
  video.addEventListener("play", onPlay);
  video.addEventListener("pause", onPause);
  video.addEventListener("timeupdate", renderStudioFrame);
  video.addEventListener("seeked", renderStudioFrame);
  video.addEventListener("loadedmetadata", renderStudioFrame);
  scrubber.addEventListener("input", onScrub);

  activeStudio.cleanups.push(() => {
    playBtn.removeEventListener("click", togglePlay);
    video.removeEventListener("play", onPlay);
    video.removeEventListener("pause", onPause);
    video.removeEventListener("timeupdate", renderStudioFrame);
    video.removeEventListener("seeked", renderStudioFrame);
    video.removeEventListener("loadedmetadata", renderStudioFrame);
    scrubber.removeEventListener("input", onScrub);
    video.pause();
    if (activeStudio.rafId) cancelAnimationFrame(activeStudio.rafId);
  });

  // Export with 1:1 Headless Parity
  const exportBtn = $("#studio-export-btn");
  if (exportBtn) {
    exportBtn.onclick = async () => {
      exportBtn.disabled = true;
      exportBtn.innerHTML = `<span>Exporting with 1:1 Headless Parity...</span>`;
      try {
        const resp = await fetch(`/api/jobs/${job.id}/clips/${clip.filename}/export`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ timeline: activeStudio.timeline }),
        });
        const result = await resp.json();
        if (resp.ok && result.ok) {
          showToast(`Export complete: 1:1 Skia pixel parity rendered!`);
          clip.timeline = result.timeline;
          clip.size = result.size;
          video.src = `${clip.download_url}?t=${Date.now()}`;
          video.currentTime = 0;
          renderClips(job);
        } else {
          showToast(result.detail || "Export failed. Check backend logs.");
        }
      } catch (err) {
        showToast(`Export error: ${err.message}`);
      } finally {
        exportBtn.disabled = false;
        exportBtn.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg><span>Export with 1:1 Headless Parity</span>`;
      }
    };
  }

  // Open modal
  modal.hidden = false;
  modal.classList.add("open");
  document.body.style.overflow = "hidden";
  setTimeout(renderStudioFrame, 50);
}

function renderStudioWordsList() {
  const container = $("#studio-words-list");
  if (!container || !activeStudio.timeline) return;

  const words = activeStudio.timeline.words || [];
  $("#studio-word-count").textContent = `${words.length} WORDS`;

  if (words.length === 0) {
    container.innerHTML = `<div class="empty-state" style="padding:20px;">No dialogue word tokens in this clip window.</div>`;
    return;
  }

  container.innerHTML = words.map((w, idx) => `
    <div class="studio-word-row" id="studio-word-row-${idx}" data-idx="${idx}">
      <input type="text" class="studio-word-input" data-idx="${idx}" value="${escapeHtml(w.text || w.word || '')}">
      <div class="time-nudge-group">
        <button type="button" class="time-nudge-btn" data-idx="${idx}" data-field="start" data-delta="-50">−</button>
        <span class="time-val" id="time-start-${idx}">${(w.start || (w.start_ms / 1000) || 0).toFixed(2)}s</span>
        <button type="button" class="time-nudge-btn" data-idx="${idx}" data-field="start" data-delta="50">+</button>
      </div>
      <div class="time-nudge-group">
        <button type="button" class="time-nudge-btn" data-idx="${idx}" data-field="end" data-delta="-50">−</button>
        <span class="time-val" id="time-end-${idx}">${(w.end || (w.end_ms / 1000) || 0).toFixed(2)}s</span>
        <button type="button" class="time-nudge-btn" data-idx="${idx}" data-field="end" data-delta="50">+</button>
      </div>
      <button type="button" class="highlight-toggle-btn ${w.highlight ? "highlighted" : ""}" data-idx="${idx}" title="Toggle Active Accent Pop">
        ★
      </button>
    </div>
  `).join("");

  // Attach Word Input Change Listeners
  container.querySelectorAll(".studio-word-input").forEach((inp) => {
    inp.addEventListener("input", (e) => {
      const idx = parseInt(inp.dataset.idx, 10);
      const w = words[idx];
      if (w) {
        w.text = e.target.value;
        w.word = e.target.value.replace(/[^a-zA-Z0-9']/g, "");
        // Also sync phrase words
        syncTimelinePhrases();
        triggerStudioRedraw();
      }
    });
  });

  // Attach Timestamp Nudge Listeners
  container.querySelectorAll(".time-nudge-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.idx, 10);
      const field = btn.dataset.field;
      const delta = parseInt(btn.dataset.delta, 10);
      const w = words[idx];
      if (!w) return;

      if (field === "start") {
        const newStartMs = Math.max(0, (w.start_ms || Math.round(w.start * 1000)) + delta);
        w.start_ms = newStartMs;
        w.start = newStartMs / 1000;
        $(`#time-start-${idx}`).textContent = `${w.start.toFixed(2)}s`;
      } else if (field === "end") {
        const newEndMs = Math.max((w.start_ms || 0) + 20, (w.end_ms || Math.round(w.end * 1000)) + delta);
        w.end_ms = newEndMs;
        w.end = newEndMs / 1000;
        $(`#time-end-${idx}`).textContent = `${w.end.toFixed(2)}s`;
      }
      syncTimelinePhrases();
      triggerStudioRedraw();
    });
  });

  // Attach Highlight Toggle Listeners
  container.querySelectorAll(".highlight-toggle-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.idx, 10);
      const w = words[idx];
      if (w) {
        w.highlight = !w.highlight;
        btn.classList.toggle("highlighted", w.highlight);
        syncTimelinePhrases();
        triggerStudioRedraw();
      }
    });
  });
}

function syncTimelinePhrases() {
  if (!activeStudio.timeline) return;
  const words = activeStudio.timeline.words || [];
  // Re-sync phrases from updated words
  const phrases = activeStudio.timeline.phrases || [];
  if (phrases.length > 0) {
    let wPtr = 0;
    for (const p of phrases) {
      const pWords = [];
      for (let i = 0; i < p.word_count && wPtr < words.length; i++, wPtr++) {
        pWords.push(words[wPtr]);
      }
      p.words = pWords;
      if (pWords.length > 0) {
        p.start = pWords[0].start;
        p.end = pWords[pWords.length - 1].end;
        p.start_ms = pWords[0].start_ms;
        p.end_ms = pWords[pWords.length - 1].end_ms;
        p.text = pWords.map((x) => x.text).join(" ");
      }
    }
  }
}

function triggerStudioRedraw() {
  const video = $("#studio-video");
  const canvas = $("#studio-overlay-canvas");
  if (!video || !canvas || !activeStudio.timeline) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width || 1080;
  const h = canvas.height || 1920;
  if (window.CaptionCanvasRenderer) {
    window.CaptionCanvasRenderer.renderFrame(ctx, activeStudio.timeline, video.currentTime || 0, w, h);
  }
}

function highlightActiveWordRow(activeIdx) {
  if (activeIdx === activeStudio.activeWordIdx) return;
  activeStudio.activeWordIdx = activeIdx;
  $$(".studio-word-row").forEach((row) => row.classList.remove("active-speaking"));
  if (activeIdx >= 0) {
    const row = $(`#studio-word-row-${activeIdx}`);
    if (row) {
      row.classList.add("active-speaking");
      row.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }
}

function closeCaptionStudio() {
  const modal = $("#caption-studio-modal");
  if (modal) {
    modal.classList.remove("open");
    setTimeout(() => { modal.hidden = true; }, 200);
    document.body.style.overflow = "";
  }
  for (const cleanup of activeStudio.cleanups) {
    try { cleanup(); } catch {}
  }
  activeStudio.cleanups = [];
  if (activeStudio.rafId) {
    cancelAnimationFrame(activeStudio.rafId);
    activeStudio.rafId = null;
  }
}

const closeStudioBtn = $("#close-caption-studio-btn");
if (closeStudioBtn) closeStudioBtn.addEventListener("click", closeCaptionStudio);

const studioModal = $("#caption-studio-modal");
if (studioModal) {
  studioModal.addEventListener("click", (e) => {
    if (e.target === studioModal) closeCaptionStudio();
  });
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && studioModal && !studioModal.hidden) {
    closeCaptionStudio();
  }
});