const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

function builder() {
  const file = path.resolve(__dirname, '../scripts/build_frontend.js');
  assert.ok(fs.existsSync(file), 'Static frontend builder must exist');
  return require(file);
}

test('production config requires an HTTPS backend and rejects credentials or paths', () => {
  const { validateApiBase } = builder();
  assert.equal(validateApiBase('https://api.example.com/'), 'https://api.example.com');
  for (const base of ['', 'http://api.example.com', 'https://user:secret@api.example.com', 'https://api.example.com/api', 'https://api.example.com?token=value']) {
    assert.throws(() => validateApiBase(base), /backend|HTTPS|origin/i);
  }
  assert.equal(validateApiBase('', { allowSameOrigin: true }), '');
});

test('static output includes fonts and public config but never backend files or secrets', (t) => {
  const { buildFrontend } = builder();
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cutflow-static-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, 'frontend'), { recursive: true });
  fs.mkdirSync(path.join(root, 'backend/assets/fonts'), { recursive: true });
  fs.writeFileSync(path.join(root, 'frontend/index.html'), '<script src="/runtime-config.js"></script>');
  fs.writeFileSync(path.join(root, 'backend/assets/fonts/Test.ttf'), 'font-fixture');
  fs.writeFileSync(path.join(root, '.env'), 'SECRET=must-not-ship');
  buildFrontend({ rootDir: root, apiBase: 'https://api.example.com' });
  assert.ok(fs.existsSync(path.join(root, 'dist/index.html')));
  assert.equal(fs.readFileSync(path.join(root, 'dist/assets/fonts/Test.ttf'), 'utf8'), 'font-fixture');
  const config = fs.readFileSync(path.join(root, 'dist/runtime-config.js'), 'utf8');
  assert.match(config, /https:\/\/api\.example\.com/);
  assert.doesNotMatch(config, /SECRET|must-not-ship/);
  assert.ok(!fs.existsSync(path.join(root, 'dist/backend')));
  assert.ok(!fs.existsSync(path.join(root, 'dist/.env')));
});

test('invalid production backend configuration leaves no publishable output', (t) => {
  const { buildFrontend } = builder();
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cutflow-static-invalid-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, 'frontend'));
  assert.throws(() => buildFrontend({ rootDir: root, apiBase: '' }), /backend/i);
  assert.ok(!fs.existsSync(path.join(root, 'dist')));
});
