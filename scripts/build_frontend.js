const fs = require('node:fs');
const path = require('node:path');

function validateApiBase(value, { allowSameOrigin = false } = {}) {
  const raw = String(value || '').trim();
  if (!raw && allowSameOrigin) return '';
  if (!raw) throw new Error('Set CUTFLOW_API_URL to the HTTPS origin of the persistent Cutflow backend.');
  let url;
  try { url = new URL(raw); } catch { throw new Error('The backend URL must be a valid HTTPS origin.'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || !['', '/'].includes(url.pathname)) {
    throw new Error('The backend URL must be an HTTPS origin without credentials, paths, or query parameters.');
  }
  return url.origin;
}

function buildFrontend({ rootDir = path.resolve(__dirname, '..'), apiBase = process.env.CUTFLOW_API_URL, allowSameOrigin = false } = {}) {
  const base = validateApiBase(apiBase, { allowSameOrigin });
  const root = path.resolve(rootDir);
  const destination = path.join(root, 'dist');
  const frontend = path.join(root, 'frontend');
  if (!fs.existsSync(frontend)) throw new Error('The frontend source directory is missing.');
  // This builder only replaces the known dist artifact inside the specified root.
  fs.rmSync(destination, { recursive: true, force: true });
  fs.cpSync(frontend, destination, { recursive: true });
  const fonts = path.join(root, 'backend/assets/fonts');
  if (fs.existsSync(fonts)) {
    fs.mkdirSync(path.join(destination, 'assets/fonts'), { recursive: true });
    fs.cpSync(fonts, path.join(destination, 'assets/fonts'), { recursive: true });
  }
  const config = JSON.stringify({ apiBase: base, configured: true }).replace(/</g, '\\u003c');
  fs.writeFileSync(path.join(destination, 'runtime-config.js'), `window.CUTFLOW_CONFIG = ${config};\n`);
  console.log(`Static frontend built in ${destination}. Backend: ${base || 'same origin'}`);
  return destination;
}

if (require.main === module) {
  try { buildFrontend({ allowSameOrigin: process.env.VERCEL !== '1' }); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}

module.exports = { validateApiBase, buildFrontend };
