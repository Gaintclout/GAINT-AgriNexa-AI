import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const ctx=readFileSync(new URL('../src/AuthContext.jsx',import.meta.url),'utf8');
const api=readFileSync(new URL('../src/gisApi.js',import.meta.url),'utf8');
test('M15 session bootstrap and server-side logout are wired',()=>{
 assert.match(ctx,/refreshOperator/);
 assert.match(ctx,/logoutOperator/);
 assert.match(ctx,/restoring \? <div/);
 assert.match(api,/credentials:'same-origin'/);
 assert.match(api,/\/api\/v1\/auth\/refresh/);
 assert.match(api,/\/api\/v1\/auth\/logout/);
});
