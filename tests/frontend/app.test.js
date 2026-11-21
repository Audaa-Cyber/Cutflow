const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const frontend = path.join(__dirname, '../../frontend');
function browser({config = {apiBase: 'https://media.example.test', configured: true}, responses = []} = {}) {
  const nodes = new Map();
  const requests = [];
  const uploads = [];
  const timers = new Map();
  let timerId = 0;
  class Element {
    constructor(attrs = {}) {
      Object.assign(this, {value: '', hidden: false, disabled: false, style: {}, dataset: {}, listeners: {}, innerHTML: '', textContent: '', paused: true, duration: 10, currentTime: 0, videoWidth: 320, videoHeight: 180, width: 320, height: 180}, attrs);
      this.classes = new Set((attrs.class || '').split(' '));
      this.classList = {add: (v) => this.classes.add(v), remove: (v) => this.classes.delete(v), contains: (v) => this.classes.has(v), toggle: (v, on) => on ? this.classes.add(v) : this.classes.delete(v)};
    }
    addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
    removeEventListener(type, fn) { this.listeners[type] = (this.listeners[type] || []).filter((v) => v !== fn); }
    dispatch(type, props = {}) { for (const fn of this.listeners[type] || []) fn({target: this, ...props}); }
    setAttribute(key, value) { this[key] = value; }
    getContext() { return {}; }
    focus() {}
    scrollIntoView() {}
    pause() { this.paused = true; }
    play() { this.paused = false; return Promise.resolve(); }
    load() {}
    removeAttribute(key) { delete this[key]; }
    querySelectorAll(selector) {
      if (!this.children) {
        this.children = [];
        for (const tag of this.innerHTML.matchAll(/<(?:button|input|div|span)\b([^>]*)>/g)) {
          const attrs = {};
          for (const item of tag[1].matchAll(/([\w-]+)="([^"]*)"/g)) attrs[item[1]] = item[2];
          const el = new Element(attrs);
          for (const [key, value] of Object.entries(attrs)) if (key.startsWith('data-')) el.dataset[key.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = value;
          if (attrs.id) nodes.set('#' + attrs.id, el);
          this.children.push(el);
        }
      }
      return this.children.filter((el) => selector.startsWith('.') ? el.classes.has(selector.slice(1)) : selector === '#' + el.id);
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  }
  const get = (selector) => { if (!nodes.has(selector)) nodes.set(selector, new Element()); return nodes.get(selector); };
  const docEvents = {};
  const document = {body: new Element(), querySelector: get, querySelectorAll: (selector) => [...nodes.values()].filter((el) => selector.startsWith('.') && el.classes.has(selector.slice(1))), addEventListener: (t, fn) => (docEvents[t] ||= []).push(fn), dispatchEvent: (ev) => (docEvents[ev.type] || []).forEach((fn) => fn(ev))};
  const storage = new Map();
  const sessionStorage = {getItem: (k) => storage.get(k) || null, setItem: (k, v) => storage.set(k, v), removeItem: (k) => storage.delete(k)};
  function response(value = {id: 'job-1', template: 'podcast', aspect_ratio: '9:16', status: 'queued'}) { return new Response(typeof value === 'object' && 'body' in value ? value.body : JSON.stringify(value), {status: value.statusCode || 200, headers: {'content-type': value.contentType || 'application/json'}}); }
  class XHR {
    constructor() { this.upload = {}; this.headers = {}; uploads.push(this); }
    open(method, url) { this.method = method; this.url = url; }
    setRequestHeader(k, v) { this.headers[k] = v; }
    getResponseHeader() { return this.contentType; }
    send(body) {
      this.body = body;
      const value = responses.shift() || {id: 'job-1', template: 'podcast', aspect_ratio: '9:16', status: 'queued'};
      this.status = value.statusCode || 200;
      this.contentType = value.contentType || 'application/json';
      this.responseText = 'body' in value ? value.body : JSON.stringify(value);
      this.upload.onprogress?.({lengthComputable: true, loaded: 13 * 1024 * 1024, total: 26 * 1024 * 1024});
      this.onload?.();
    }
    abort() { this.onabort?.(); }
  }
  const context = {document, sessionStorage, location: {origin: 'https://frontend.example.test', href: 'https://frontend.example.test/'}, CUTFLOW_CONFIG: config, URL, Headers, Response, AbortController, Event, FormData: class {constructor() {this.entries = [];} append(...args) {this.entries.push(args);}}, XMLHttpRequest: XHR, fetch: async (url, options = {}) => { requests.push({url, options}); return response(responses.shift()); }, setTimeout: (fn, delay) => {timers.set(++timerId, {fn, delay}); return timerId;}, clearTimeout: (id) => timers.delete(id), requestAnimationFrame: () => 1, cancelAnimationFrame() {}, console, confirm: () => true};
  context.window = context;
  vm.createContext(context);
  if (fs.existsSync(path.join(frontend, 'api.js'))) vm.runInContext(fs.readFileSync(path.join(frontend, 'api.js'), 'utf8'), context);
  vm.runInContext(fs.readFileSync(path.join(frontend, 'app.js'), 'utf8'), context);
  get('#min-duration').value = '10'; get('#max-duration').value = '60'; get('#clip-count').value = '1'; get('#project-filter').value = 'all';
  return {context, get, requests, uploads, timers, run: (code) => vm.runInContext(code, context), flushFrames: () => [...timers.values()].filter((t) => t.delay === 50).forEach((t) => t.fn())};
}

function clip() {
  const words = [{id: 'a', text: 'First', start_ms: 60000, end_ms: 60200}, {id: 'b', text: 'Second', start_ms: 60300, end_ms: 60900}];
  return {filename: 'clip.mp4', start: 60, end: 70, duration: 10, download_url: '/api/jobs/j/clips/clip.mp4', preview_url: '/api/jobs/j/clips/clip.mp4/preview', srt_url: '/api/jobs/j/clips/clip.mp4/subtitles.srt', ass_url: '/api/jobs/j/clips/clip.mp4/subtitles.ass', timeline_url: '/api/jobs/j/clips/clip.mp4/timeline', timeline: {start_ms: 60000, end_ms: 70000, words, phrases: [{word_count: 1, words: [words[0]], start_ms: 60000, end_ms: 60200}, {word_count: 1, words: [words[1]], start_ms: 60300, end_ms: 60900}], styling_metadata: {preset_key: 'focus'}}};
}

test('26 MB multipart upload works without signing in and reports progress', async () => {
  const b = browser();
  b.run("state.file = {name: 'large.mp4', size: 26 * 1024 * 1024}");
  await b.context.createProject();
  assert.equal(b.uploads.length, 1);
  assert.equal(b.uploads[0].url, 'https://media.example.test/api/jobs/upload');
  assert.equal(b.uploads[0].headers.Authorization, undefined);
  assert.equal(b.uploads[0].body.entries[0][0], 'file');
  assert.equal(b.run('state.jobs.length'), 1);
  assert.match(b.get('#upload-progress-label').textContent, /50/);
});

test('project refresh loads the shared workspace without a session or authorization header', async () => {
  const b = browser({responses: [{id: 'shared-job', status: 'completed'}]});
  // Project-list endpoints return arrays rather than a single project.
  b.context.fetch = async (url, options = {}) => {
    b.requests.push({url, options});
    return new Response(JSON.stringify([{id: 'shared-job', status: 'completed'}]));
  };
  await b.context.refreshProjects();
  assert.equal(b.requests.length, 1);
  assert.equal(b.requests[0].options.headers.has('Authorization'), false);
  assert.equal(b.run('state.jobs[0].id'), 'shared-job');
});

for (const error of [{statusCode: 413, contentType: 'text/plain', body: 'Request Entity Too Large'}, {statusCode: 400, body: '{"detail":"Unsupported video"}'}, {statusCode: 502, contentType: 'text/plain', body: 'Backend offline'}]) {
  test(`upload HTTP ${error.statusCode} reports useful error and creates no fake project`, async () => {
    const b = browser({responses: [error]}); b.run("state.file = {name: 'large.mp4', size: 26 * 1024 * 1024}");
    await b.context.createProject();
    assert.equal(b.run('state.jobs.length'), 0);
    assert.match(b.get('#toast').textContent, error.statusCode === 413 ? /413.*(limit|proxy|backend)/i : error.statusCode === 400 ? /Unsupported video/ : /Backend offline/);
    assert.equal(b.get('#create-button').disabled, false);
  });
}

test('HTML success response cannot become a fake queued job', async () => {
  const b = browser({responses: [{contentType: 'text/html', body: '<html>Fallback page</html>'}]});
  b.run("state.file = {name: 'large.mp4', size: 26 * 1024 * 1024}"); await b.context.createProject();
  assert.equal(b.run('state.jobs.length'), 0);
  assert.match(b.get('#toast').textContent, /JSON|backend/i);
});

test('missing runtime configuration blocks requests with a visible setup error', async () => {
  const b = browser({config: null}); b.run("state.file = {name: 'large.mp4', size: 26 * 1024 * 1024}"); await b.context.createProject();
  assert.equal(b.requests.length + b.uploads.length, 0);
  assert.match(b.get('#toast').textContent, /configur.*backend|backend.*configur/i);
});

test('media quality URL uses configured backend without account grants', () => {
  const b = browser();
  const url = new URL(b.context.CutflowAPI.mediaUrl('/api/jobs/j/clips/a.mp4', {resolution: '720'}));
  assert.equal(url.origin, 'https://media.example.test'); assert.equal(url.searchParams.get('media_token'), null); assert.equal(url.searchParams.get('resolution'), '720');
});

test('Studio opens with all 18 presets, clean preview, and source-based caption/SFX clock', async () => {
  const b = browser(); const frames = []; const sounds = [];
  b.context.CaptionCanvasRenderer = {renderFrame: (...args) => {frames.push(args[2]); return {activeWordIdx: 0};}};
  b.context.SFXSubMixer = class {attachVideo() {} syncTimeline() {} suspend() {} dispose() {} unduck() {} update(t) {sounds.push(t);} };
  await b.context.openCaptionStudio(clip(), {id: 'j', caption_style: 'focus', clips: []});
  assert.equal(b.get('#caption-studio-modal').hidden, false);
  assert.equal(b.get('#studio-presets-scroller').querySelectorAll('.studio-preset-chip').length, 18);
  assert.equal(b.get('#studio-video').src, 'https://media.example.test/api/jobs/j/clips/clip.mp4/preview');
  b.get('#studio-video').currentTime = 0.5; b.get('#studio-video').dispatch('timeupdate');
  assert.equal(frames.at(-1), 60.5); assert.equal(sounds.at(-1), 60.5);
  assert.equal(b.run('activeStudio.activeWordIdx'), 1);
  b.context.triggerStudioRedraw(); assert.equal(frames.at(-1), 60.5);
  [...b.timers.values()].filter((t) => t.delay === 200).forEach((t) => t.fn());
  assert.equal(b.get('#caption-studio-modal').hidden, false, 'previous close must not hide newly opened Studio');
});

test('Studio reopening preserves video audio routing and clears the previous sound timeline', async () => {
  const b = browser();
  const attached = new WeakSet();
  const contexts = [];
  class AudioContext {
    constructor() {this.state = 'running'; this.currentTime = 0; this.destination = {}; contexts.push(this);}
    createGain() {return {gain: {value: 1, setValueAtTime() {}, cancelScheduledValues() {}, linearRampToValueAtTime() {}}, connect() {}};}
    createMediaElementSource(video) {
      // Web Audio permanently associates a media element with its first source.
      if (attached.has(video)) throw new Error('Media element already has an audio source');
      attached.add(video);
      video.audioContext = this;
      return {connect() {}};
    }
    resume() {this.state = 'running'; return Promise.resolve();}
    suspend() {this.state = 'suspended'; return Promise.resolve();}
    close() {this.state = 'closed'; return Promise.resolve();}
  }
  b.context.AudioContext = AudioContext;
  vm.runInContext(fs.readFileSync(path.join(frontend, 'sfx_mixer.js'), 'utf8'), b.context);
  await b.context.openCaptionStudio(clip(), {id: 'j'});
  const video = b.get('#studio-video');
  const originalContext = video.audioContext;
  b.context.closeCaptionStudio();
  assert.notEqual(originalContext.state, 'closed', 'closing Studio must preserve the media element audio graph');
  assert.equal(b.run('activeStudio.sfxMixer.events.length'), 0);
  await b.context.openCaptionStudio(clip(), {id: 'j'});
  assert.equal(video.audioContext, originalContext);
  assert.equal(video.audioContext.state, 'running', 'reopened video must have a usable audio output');
  assert.equal(contexts.length, 1);
});

test('Studio nudge bounds and phrase synchronization keep milliseconds and multilingual text', async () => {
  const b = browser(); const c = clip();
  await b.context.openCaptionStudio(c, {id: 'j', caption_style: 'focus'});
  const list = b.get('#studio-words-list');
  const buttons = list.querySelectorAll('.time-nudge-btn');
  buttons.find((v) => v.dataset.idx === '0' && v.dataset.field === 'start' && v.dataset.delta === '-50').dispatch('click');
  assert.equal(b.run('activeStudio.timeline.words[0].start_ms'), 60000);
  for (let i = 0; i < 10; i++) buttons.find((v) => v.dataset.idx === '0' && v.dataset.field === 'start' && v.dataset.delta === '50').dispatch('click');
  assert.equal(b.run('activeStudio.timeline.words[0].start_ms'), 60180);
  const input = list.querySelectorAll('.studio-word-input')[1]; input.value = 'ሰላም, café!'; input.dispatch('input');
  assert.equal(b.run('activeStudio.timeline.words[1].word'), 'ሰላም, café!');
  assert.equal(b.run('activeStudio.timeline.phrases[1].text'), 'ሰላም, café!');
});

test('Studio export reports actual fallback renderer and refreshes clean media URLs', async () => {
  const updated = {ok: true, renderer: 'ass', size: 50, download_url: '/api/jobs/j/clips/clip.mp4', preview_url: '/api/jobs/j/clips/clip.mp4/preview', srt_url: '/api/jobs/j/clips/clip.mp4/subtitles.srt', ass_url: '/api/jobs/j/clips/clip.mp4/subtitles.ass'};
  const b = browser({responses: [updated]}); const c = clip(); const job = {id: 'j', clips: [c]};
  b.context.renderClips = () => {};
  await b.context.openCaptionStudio(c, job); await b.get('#studio-export-btn').onclick();
  assert.match(b.get('#toast').textContent, /ASS/i); assert.doesNotMatch(b.get('#toast').textContent, /Skia|parity/i);
  assert.equal(c.download_url, updated.download_url);
  assert.equal(new URL(b.get('#studio-video').src).pathname, '/api/jobs/j/clips/clip.mp4/preview');
  assert.equal(b.requests[0].options.headers.has('Authorization'), false);
});

test('same-origin Docker configuration resolves API requests locally', async () => {
  const b = browser({config: {apiBase: '', configured: true}, responses: [{ok: true}]});
  await b.context.CutflowAPI.request('/api/health');
  assert.equal(b.requests[0].url, 'https://frontend.example.test/api/health');
});

test('download refreshes media metadata while preserving selected quality', async () => {
  const fresh = clip(); fresh.download_url = '/api/jobs/j/clips/clip.mp4?revision=fresh';
  const b = browser({responses: [{id: 'j', clips: [fresh]}]});
  b.context.location.assign = (url) => {b.context.location.assigned = url;};
  await b.context.downloadClip(clip(), {id: 'j'}, 'download', '720');
  const url = new URL(b.context.location.assigned);
  assert.equal(url.origin, 'https://media.example.test'); assert.equal(url.searchParams.get('revision'), 'fresh'); assert.equal(url.searchParams.get('resolution'), '720');
});

test('open project fetches fresh metadata before rendering a previously idle project', async () => {
  const fresh = {id: 'j', status: 'completed', clips: []}; const b = browser({responses: [fresh]});
  b.run("state.jobs = [{id:'j', status:'completed', clips:[]}]");
  await b.context.openProject('j');
  assert.equal(b.requests.length, 1); assert.equal(b.requests[0].url, 'https://media.example.test/api/jobs/j');
});

test('URL import goes directly to backend without signing in', async () => {
  const b = browser(); b.run("state.sourceMode = 'link'"); b.get('#video-url').value = 'https://youtu.be/example';
  await b.context.createProject();
  assert.equal(b.requests[0].url, 'https://media.example.test/api/jobs/url');
  assert.equal(b.requests[0].options.headers.has('Authorization'), false);
  assert.equal(JSON.parse(b.requests[0].options.body).source_url, 'https://youtu.be/example'); assert.equal(b.uploads.length, 0);
});

test('bulk deletion works without signing in and clears the shared workspace', async () => {
  const b = browser({responses: [{deleted_count: 2}]});
  b.run("state.jobs = [{id:'j'}, {id:'other'}]; state.activeJobId = 'j'; state.pollTimer = setTimeout(() => {}, 2200)");
  await b.context.openCaptionStudio(clip(), {id: 'j'});
  b.get('#clips-grid').innerHTML = 'previous clips';
  await b.context.deleteAllProjects();
  assert.equal(b.requests[0].url, 'https://media.example.test/api/jobs');
  assert.equal(b.requests[0].options.method, 'DELETE');
  assert.equal(b.requests[0].options.headers.has('Authorization'), false);
  assert.equal(b.run('state.jobs.length'), 0); assert.equal(b.run('state.activeJobId'), null);
  assert.equal(b.get('#latest-results').hidden, true); assert.equal(b.get('#active-processing').hidden, true);
  assert.equal(b.get('#clips-grid').innerHTML, ''); assert.equal(b.run('activeStudio.timeline'), null);
  assert.equal(b.get('#caption-studio-modal').hidden, true);
  assert.match(b.get('#toast').textContent, /2 removed/);
});

for (const bulk of [false, true]) {
  test(`${bulk ? 'bulk' : 'single'} deletion shows incomplete stored-media cleanup`, async () => {
    const b = browser({responses: [{ok: true, deleted_count: 1, cloud_cleanup_failures: 2}]});
    b.run("state.jobs = [{id:'j'}]");
    if (bulk) await b.context.deleteAllProjects();
    else await b.context.deleteProject('j');
    assert.equal(b.run('state.jobs.length'), 0);
    assert.match(b.get('#toast').textContent, /2.*(stored|media|files).*(could not|failed|remain)/i);
  });
}
