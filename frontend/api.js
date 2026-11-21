/* Shared backend transport. Session tokens never appear in media URLs. */
(function (root) {
  'use strict';
  const storageKey = 'cutflow.session';
  let session = null;
  let revision = 0;
  const pending = new Set();
  try { session = JSON.parse(root.sessionStorage.getItem(storageKey)); } catch {}
  if (!session?.token || !session?.user?.id) session = null;

  class APIError extends Error {
    constructor(message, status = 0, stale = false) { super(message); this.status = status; this.stale = stale; }
  }
  function baseUrl() {
    const config = root.CUTFLOW_CONFIG;
    if (!config || config.configured !== true || typeof config.apiBase !== 'string') {
      throw new APIError('The media backend is not configured. Set the public backend URL and rebuild the frontend.');
    }
    let base;
    try {base = new URL(config.apiBase || root.location.origin, root.location.origin);}
    catch {throw new APIError('The configured backend URL is invalid. Use an HTTP or HTTPS backend URL.');}
    if (!['https:', 'http:'].includes(base.protocol) || base.username || base.password || base.search || base.hash) {
      throw new APIError('The configured backend URL is invalid. Use an HTTP or HTTPS backend URL.');
    }
    return base.href.replace(/\/$/, '');
  }
  function mediaUrl(path, params = {}) {
    if (!path || typeof path !== 'string') throw new APIError('This media link is unavailable. Refresh the project and retry.');
    const base = baseUrl();
    const url = new URL(path.startsWith('/') ? base + path : path, base + '/');
    const isBlobStorage = url.hostname.endsWith('.vercel-storage.com');
    if ((url.origin !== new URL(base).origin && !isBlobStorage) || !['http:', 'https:'].includes(url.protocol) || url.username || url.password) {
      throw new APIError('The server returned a media link outside the configured backend. Refresh the project and retry.');
    }
    Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, String(value)));
    return url.href;
  }
  function setSession(value) {
    session = value?.token && value?.user?.id ? value : null;
    revision++;
    for (const cancel of [...pending]) cancel();
    pending.clear();
    try {
      if (session) root.sessionStorage.setItem(storageKey, JSON.stringify(session));
      else root.sessionStorage.removeItem(storageKey);
    } catch {}
    root.document.dispatchEvent(new Event('cutflow:sessionchanged'));
  }
  function errorMessage(status, body) {
    let detail;
    try { const value = JSON.parse(body); detail = value.detail || value.message || value.error; } catch {}
    if (Array.isArray(detail)) detail = detail.map((item) => item.msg || 'Invalid input').join('; ');
    if (typeof detail !== 'string') detail = '';
    const plain = !/<(?:!doctype|html|head|body)\b/i.test(body) ? body.trim().slice(0, 500) : '';
    if (status === 413) return 'Upload rejected (HTTP 413). The backend or its reverse proxy upload limit is too small. Increase that limit or use a smaller video.';
    if (status === 401) return detail || 'Your session expired. Sign in again to continue.';
    return detail || plain || `The backend request failed (HTTP ${status}). Please retry.`;
  }
  function parseBody(status, body) {
    if (status < 200 || status >= 300) throw new APIError(errorMessage(status, body), status);
    if (status === 204) return {};
    try { const value = JSON.parse(body); if (value === null) throw new Error(); return value; } catch {
      throw new APIError('The backend returned an invalid JSON response. Check the backend URL and try again.', status);
    }
  }
  async function request(path, options = {}) {
    const url = mediaUrl(path);
    const {auth = true, ...fetchOptions} = options;
    if (auth && !session) throw new APIError('Sign in to create and manage your projects.', 401);
    const headers = new Headers(fetchOptions.headers || {});
    if (auth) headers.set('Authorization', `Bearer ${session.token}`);
    const controller = new AbortController();
    const cancel = () => controller.abort();
    const started = revision;
    pending.add(cancel);
    try {
      const response = await root.fetch(url, {...fetchOptions, headers, signal: controller.signal});
      const body = await response.text();
      if (started !== revision) throw new APIError('Account changed. Please retry.', 0, true);
      if (response.status === 401 && auth) setSession(null);
      return parseBody(response.status, body);
    } catch (error) {
      if (started !== revision && error.status !== 401) throw new APIError('Account changed. Please retry.', 0, true);
      if (error instanceof APIError) throw error;
      throw new APIError('Cannot reach the media backend. Check your connection and the backend URL, then retry.');
    } finally { pending.delete(cancel); }
  }
  function upload(path, form, onProgress) {
    return new Promise((resolve, reject) => {
      let url;
      try { url = mediaUrl(path); if (!session) throw new APIError('Sign in to upload a video.', 401); } catch (error) {reject(error); return;}
      const started = revision;
      const xhr = new root.XMLHttpRequest();
      const cancel = () => xhr.abort();
      const finish = (fn, value) => {pending.delete(cancel); fn(value);};
      pending.add(cancel);
      xhr.open('POST', url);
      xhr.setRequestHeader('Authorization', `Bearer ${session.token}`);
      xhr.upload.onprogress = (event) => {if (event.lengthComputable && started === revision) onProgress?.(Math.round(event.loaded / event.total * 100));};
      xhr.onload = () => {
        if (started !== revision) {finish(reject, new APIError('Account changed. Please retry.', 0, true)); return;}
        if (xhr.status === 401) {pending.delete(cancel); setSession(null);}
        try { finish(resolve, parseBody(xhr.status, xhr.responseText)); } catch (error) {finish(reject, error);}
      };
      xhr.onerror = () => finish(reject, new APIError('Upload could not reach the backend. Check your connection and backend URL, then retry.'));
      xhr.ontimeout = () => finish(reject, new APIError('Upload timed out. Retry or use a smaller video.'));
      xhr.onabort = () => finish(reject, new APIError('Upload cancelled because the account changed.', 0, true));
      xhr.send(form);
    });
  }
  root.CutflowAPI = {request, upload, mediaUrl, setSession, getSession: () => session, getRevision: () => revision, baseUrl};
})(window);
