const state = {
  template: "podcast",
  aspectRatio: "9:16",
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
  podcast: "Podcast & conversation",
  educational: "Educational & how-to",
  story: "Storytelling",
  funny: "Funny moments",
  gaming: "Gaming highlights",
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
  return {
    template: state.template,
    aspect_ratio: state.aspectRatio,
    clip_count: Number($("#clip-count").value),
    min_duration: min,
    max_duration: max,
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
  const statusText = job.status === "completed" ? "Completed" : job.status === "failed" ? "Needs attention" : job.status === "queued" ? "In queue" : "In progress";
  container.innerHTML = `
    <article class="processing-card">
      <div class="processing-head">
        <div class="processing-icon">${job.status === "failed" ? "!" : job.status === "completed" ? "✓" : "✳"}</div>
        <div class="processing-info"><strong>${escapeHtml(job.source_url ? new URL(job.source_url).hostname : (state.file?.name || "Uploaded video"))}</strong><span>${escapeHtml(job.stage || "Waiting")} · ${escapeHtml(statusText)} · ${escapeHtml(job.template_label || templateNames[job.template] || "")}</span></div>
        <span class="processing-percent">${percent}%</span>
      </div>
      <div class="progress-track"><div class="progress-fill" style="width:${percent}%"></div></div>
      ${job.error ? `<p class="error-message">${escapeHtml(job.error)}</p>` : ""}
    </article>`;
}
function renderClips(job) {
  if (job.status !== "completed" && job.status !== "failed") return;
  $("#latest-results").hidden = false;
  $("#results-count").textContent = `${(job.clips || []).length} CLIPS`;
  const grid = $("#clips-grid");
  if (!job.clips?.length) {
    grid.innerHTML = `<div class="empty-state"><div class="empty-symbol">↻</div><strong>No clips were generated</strong><p>${escapeHtml(job.error || "Try a longer video or a different template.")}</p></div>`;
    return;
  }
  grid.innerHTML = job.clips.map((clip, index) => `
    <article class="clip-card">
      <div class="clip-preview" style="aspect-ratio:${clip.aspect_ratio === "16:9" ? "16/9" : clip.aspect_ratio === "1:1" ? "1/1" : "9/16"};max-height:${clip.aspect_ratio === "16:9" ? "230px" : "390px"}">
        <video controls preload="metadata" playsinline src="${escapeHtml(clip.download_url)}"></video>
        <span class="clip-badge">${escapeHtml(clip.aspect_ratio)} · ${formatTime(clip.duration)}</span>
      </div>
      <div class="clip-body">
        <div class="clip-topline"><strong>${escapeHtml(clip.title || `Clip ${index + 1}`)}</strong><span class="score-pill">${Number(clip.score)} / 100</span></div>
        <div class="clip-meta"><span>${formatTime(clip.start)} – ${formatTime(clip.end)}</span><span>${escapeHtml(clip.category || templateNames[job.template])}</span></div>
        <p class="clip-excerpt">${escapeHtml(clip.text || "")}</p>
        <a class="download-button" href="${escapeHtml(clip.download_url)}" download="${escapeHtml(clip.filename)}"><span>↓</span> Download MP4 <span>· ${formatBytes(clip.size)}</span></a>
      </div>
    </article>`).join("");
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
    list.innerHTML = `<div class="empty-state"><div class="empty-symbol">▦</div><strong>${state.jobs.length ? "No matching projects" : "Your library is waiting"}</strong><p>${state.jobs.length ? "Try another search or status filter." : "Start with a video and your first clips will show up here."}</p></div>`;
    return;
  }
  list.innerHTML = filtered.map((job) => {
    let source = "Video project";
    try { if (job.source_url) source = new URL(job.source_url).hostname; } catch {}
    const status = job.status === "completed" ? "Completed" : job.status === "failed" ? "Needs attention" : job.status === "queued" ? "In queue" : "Processing";
    const date = new Date((job.created_at || Date.now() / 1000) * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    return `<article class="project-row">
      <div class="project-icon">▧</div>
      <div class="project-main"><strong>${escapeHtml(source)} · ${escapeHtml(job.template_label || templateNames[job.template] || "Video")}</strong><span>${escapeHtml(date)} · ${job.clips?.length || 0} clips · ${escapeHtml(job.aspect_ratio || "9:16")}</span></div>
      <span class="status-pill ${escapeHtml(job.status)}">${escapeHtml(status)}</span>
      <button class="project-action" data-open-job="${escapeHtml(job.id)}">Open</button>
      <button class="project-action" data-delete-job="${escapeHtml(job.id)}" aria-label="Delete project">×</button>
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
  $("#projects-list").addEventListener("click", (event) => {
    const open = event.target.closest("[data-open-job]");
    const remove = event.target.closest("[data-delete-job]");
    if (open) openProject(open.dataset.openJob);
    if (remove) deleteProject(remove.dataset.deleteJob);
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
