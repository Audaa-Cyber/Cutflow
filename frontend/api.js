/* Shared backend transport for the account-free project workspace. */
(function (root) {
  'use strict';
  class APIError extends Error {
    constructor(message, status = 0) { super(message); this.status = status; }
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
  function errorMessage(status, body) {
    let detail;
    try { const value = JSON.parse(body); detail = value.detail || value.message || value.error; } catch {}
    if (Array.isArray(detail)) detail = detail.map((item) => item.msg || 'Invalid input').join('; ');
    if (typeof detail !== 'string') detail = '';
    const plain = !/<(?:!doctype|html|head|body)\b/i.test(body) ? body.trim().slice(0, 500) : '';
    if (status === 413) return 'Upload rejected (HTTP 413). The backend or its reverse proxy upload limit is too small. Increase that limit or use a smaller video.';
    if (status === 401) return detail || 'The backend denied this request (HTTP 401).';
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
    const headers = new Headers(options.headers || {});
    try {
      const response = await root.fetch(url, {...options, headers});
      return parseBody(response.status, await response.text());
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Cannot reach the media backend. Check your connection and the backend URL, then retry.');
    }
  }
  function upload(path, form, onProgress) {
    return new Promise((resolve, reject) => {
      let url;
      try { url = mediaUrl(path); } catch (error) {reject(error); return;}
      const xhr = new root.XMLHttpRequest();
      xhr.open('POST', url);
      xhr.upload.onprogress = (event) => {if (event.lengthComputable) onProgress?.(Math.round(event.loaded / event.total * 100));};
      xhr.onload = () => {
        try { resolve(parseBody(xhr.status, xhr.responseText)); } catch (error) {reject(error);}
      };
      xhr.onerror = () => reject(new APIError('Upload could not reach the backend. Check your connection and backend URL, then retry.'));
      xhr.ontimeout = () => reject(new APIError('Upload timed out. Retry or use a smaller video.'));
      xhr.onabort = () => reject(new APIError('Upload cancelled.'));
      xhr.send(form);
    });
  }
  root.CutflowAPI = {request, upload, mediaUrl, baseUrl};
})(window);
