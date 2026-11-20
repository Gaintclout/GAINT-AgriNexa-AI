import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = new URL('../', import.meta.url);

function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return /\.(js|jsx|mjs|ts|tsx)$/.test(entry.name) ? [path] : [];
  });
}

test('browser source never selects a loopback API origin', () => {
  const source = fileURLToPath(new URL('src/', root));
  for (const file of sourceFiles(source)) {
    const contents = readFileSync(file, 'utf8');
    assert.doesNotMatch(contents, /https?:\/\/(?:localhost|127\.0\.0\.1)(?::\d+)?/i, file);
    assert.doesNotMatch(contents, /VITE_API_BASE_URL/, file);
  }
});

test('Vite proxy covers browser API and operational endpoints', async () => {
  const configText = readFileSync(new URL('vite.config.js', root), 'utf8');
  assert.match(configText, /VITE_PROXY_TARGET/);
  assert.match(configText, /'0\.0\.0\.0'/);
  for (const route of ['/api', '/health', '/live', '/ready', '/openapi.json']) {
    assert.ok(configText.includes(`'${route}'`), `missing proxy route ${route}`);
  }
  assert.match(configText, /changeOrigin:\s*false/);
});
