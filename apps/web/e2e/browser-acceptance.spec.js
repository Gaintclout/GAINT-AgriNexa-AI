import { createHash } from 'node:crypto';
import { expect, test } from '@playwright/test';

const API = 'http://127.0.0.1:5182';
const FARMER_A = 'farmer-a';
const FARMER_B = 'farmer-b';
const VERIFIER_A = 'verifier-a';
const VERIFIER_B = 'verifier-b';
const PARCEL_A = '10000000-0000-4000-8000-000000000001';
const PARCEL_B = '20000000-0000-4000-8000-000000000002';
const EVIDENCE_IDS = [
  '30000000-0000-4000-8000-000000000001',
  '30000000-0000-4000-8000-000000000002',
  '30000000-0000-4000-8000-000000000003',
];
const PHOTO = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/r7sAAAAASUVORK5CYII=',
  'base64',
);
const PHOTO_HASH = createHash('sha256').update(PHOTO).digest('hex');
const capturedAt = new Date(Date.now() - 60_000).toISOString();

const parcels = [
  {
    id: PARCEL_A,
    external_id: 'FARMER-A-PARCEL',
    village_code: 'VIL-01',
    area_hectares: 2.5,
    farmer_id: FARMER_A,
    created_at: capturedAt,
  },
  {
    id: PARCEL_B,
    external_id: 'FARMER-B-PARCEL',
    village_code: 'VIL-02',
    area_hectares: 4,
    farmer_id: FARMER_B,
    created_at: capturedAt,
  },
];

const parcelFeature = parcel => ({
  type: 'Feature',
  id: parcel.id,
  geometry: {
    type: 'Polygon',
    coordinates: [[
      [78.48, 17.38],
      [78.49, 17.38],
      [78.49, 17.39],
      [78.48, 17.39],
      [78.48, 17.38],
    ]],
  },
  properties: {
    external_id: parcel.external_id,
    village_code: parcel.village_code,
    area_hectares: parcel.area_hectares,
    farmer_id: parcel.farmer_id,
  },
});

function jsonResponse(route, data, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
  });
}

function makeEvidence(id, overrides = {}) {
  return {
    id,
    client_record_id: id.replace(/-/g, '_'),
    parcel_id: PARCEL_A,
    verifier_id: VERIFIER_A,
    observation: `Synthetic observation ${id.slice(-1)}`,
    latitude: 17.385,
    longitude: 78.4867,
    captured_at: capturedAt,
    status: 'submitted',
    photo_sha256: PHOTO_HASH,
    reviewer_id: null,
    review_note: null,
    reviewed_at: null,
    created_at: capturedAt,
    ...overrides,
  };
}

async function installApiMocks(page, { loginFailureStatus = null } = {}) {
  const users = new Map([
    ['farmer.a@example.test', { subject: FARMER_A, role: 'farmer' }],
    ['farmer.b@example.test', { subject: FARMER_B, role: 'farmer' }],
    ['verifier.a@example.test', { subject: VERIFIER_A, role: 'field_verifier' }],
    ['verifier.b@example.test', { subject: VERIFIER_B, role: 'field_verifier' }],
    ['officer@example.test', { subject: 'officer-1', role: 'officer' }],
    ['admin@example.test', { subject: 'admin-1', role: 'admin' }],
    ['gis@example.test', { subject: 'gis-1', role: 'gis_operator' }],
    ['ml@example.test', { subject: 'ml-1', role: 'ml_team' }],
    ['expiry.admin@example.test', { subject: 'expiry-admin-1', role: 'admin' }],
    ['expiry@example.test', { subject: 'expiry-1', role: 'farmer' }],
  ]);
  const tokens = new Map();
  const evidence = new Map(EVIDENCE_IDS.map(id => [id, makeEvidence(id)]));
  const audit = new Map(EVIDENCE_IDS.map(id => [id, [{
    id: `audit-${id}`,
    evidence_id: id,
    actor_id: VERIFIER_A,
    action: 'submitted',
    note: null,
    created_at: capturedAt,
  }]]));
  const state = {
    metadataPosts: [],
    photoPosts: [],
    reviewPosts: [],
    parcelQueries: [],
    registrations: [],
    unexpectedRequests: [],
    loginFailureStatus,
    evidence,
    audit,
  };

  await page.route(url => (
    url.origin === API && (
      url.pathname.startsWith('/api/') ||
      ['/health', '/live', '/ready', '/openapi.json'].includes(url.pathname)
    )
  ), async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const authorization = request.headers().authorization || '';
    const user = tokens.get(authorization.replace(/^Bearer\s+/i, ''));

    if (method === 'GET' && path === '/health') {
      return jsonResponse(route, { status: 'ok', service: 'mock-api' });
    }
    if (method === 'GET' && path === '/live') {
      return jsonResponse(route, { status: 'ok', service: 'mock-api' });
    }
    if (method === 'GET' && path === '/ready') {
      return jsonResponse(route, {
        status: 'ready',
        checks: { database: true, migration: true, postgis: true, photo_storage: true },
      });
    }
    if (method === 'GET' && path === '/api/v1/metadata') {
      return jsonResponse(route, {
        product: 'GAINT AgriNexa AI',
        roles: ['farmer', 'field_verifier', 'officer', 'admin', 'gis_operator', 'ml_team'],
        agents: ['INTAKE', 'PROFILE', 'WEATHER', 'CROP_ADVISORY', 'MARKET', 'SCHEME', 'ESCALATION', 'LEARNING'],
      });
    }
    if (method === 'POST' && path === '/api/v1/auth/register/farmer') {
      const body = request.postDataJSON();
      const email = body.email.trim().toLowerCase();
      if (users.has(email)) return jsonResponse(route, { detail: 'Email already registered' }, 409);
      const account = { subject: `registered-${state.registrations.length + 1}`, role: 'farmer' };
      users.set(email, account);
      state.registrations.push({ email, role: account.role });
      return jsonResponse(route, { id: account.subject, email, role: account.role }, 201);
    }
    if (method === 'POST' && path === '/api/v1/auth/login') {
      if (state.loginFailureStatus) {
        return jsonResponse(route, { detail: 'Database temporarily unavailable' }, state.loginFailureStatus);
      }
      const body = request.postDataJSON();
      const email = body.email.trim().toLowerCase();
      const account = users.get(email);
      if (!account || body.password.length < 12) return jsonResponse(route, { detail: 'Invalid credentials' }, 401);
      const token = `mock-token-${email}`;
      tokens.set(token, { ...account, email });
      return jsonResponse(route, { access_token: token, token_type: 'bearer', expires_in: email.startsWith('expiry') ? 1 : 900 });
    }
    if (method === 'GET' && path === '/api/v1/auth/me') {
      if (!user) return jsonResponse(route, { detail: 'Not authenticated' }, 401);
      return jsonResponse(route, { subject: user.subject, email: user.email, role: user.role });
    }
    if (!user) return jsonResponse(route, { detail: 'Not authenticated' }, 401);

    if (method === 'GET' && path === '/api/v1/agents') {
      if (!['admin', 'gis_operator', 'ml_team'].includes(user.role)) {
        return jsonResponse(route, { detail: 'Forbidden' }, 403);
      }
      const ids = ['INTAKE', 'PROFILE', 'WEATHER', 'CROP_ADVISORY', 'MARKET', 'SCHEME', 'ESCALATION', 'LEARNING'];
      return jsonResponse(route, ids.map(id => ({
        id,
        status: ['INTAKE', 'PROFILE'].includes(id) ? 'enabled' : 'disabled',
        execution_enabled: ['INTAKE', 'PROFILE'].includes(id),
        learning_enabled: false,
      })));
    }
    if (method === 'GET' && path === '/api/v1/agents/intake-profile/availability') {
      if (!['admin', 'gis_operator', 'ml_team'].includes(user.role)) {
        return jsonResponse(route, { detail: 'Forbidden' }, 403);
      }
      return jsonResponse(route, {
        available: true,
        reason: 'Synthetic UAT fixture: persistent audit required',
      });
    }

    if (method === 'GET' && path === '/api/v1/parcels') {
      state.parcelQueries.push({ role: user.role, subject: user.subject });
      const visible = user.role === 'farmer'
        ? parcels.filter(item => item.farmer_id === user.subject)
        : parcels;
      return jsonResponse(route, visible);
    }
    if (method === 'GET' && path === '/api/v1/villages') {
      return jsonResponse(route, [{ code: 'VIL-01', name: 'Synthetic Village' }]);
    }
    if (method === 'GET' && path === '/api/v1/users/farmers') {
      if (!['admin', 'gis_operator'].includes(user.role)) return jsonResponse(route, { detail: 'Forbidden' }, 403);
      return jsonResponse(route, parcels.map(item => ({ id: item.farmer_id, email: `${item.farmer_id}@example.test` })));
    }
    if (method === 'GET' && path === '/api/v1/gis/parcels/geojson') {
      const visible = user.role === 'farmer'
        ? parcels.filter(item => item.farmer_id === user.subject)
        : parcels;
      return jsonResponse(route, { type: 'FeatureCollection', features: visible.map(parcelFeature) });
    }
    const parcelMatch = path.match(/^\/api\/v1\/parcels\/([^/]+)$/);
    if (method === 'GET' && parcelMatch) {
      const parcel = parcels.find(item => item.id === decodeURIComponent(parcelMatch[1]));
      if (!parcel || (user.role === 'farmer' && parcel.farmer_id !== user.subject)) {
        return jsonResponse(route, { detail: 'Not found' }, 404);
      }
      return jsonResponse(route, parcel);
    }

    if (method === 'GET' && path === '/api/v1/field-verification/evidence') {
      const visible = [...evidence.values()].filter(item =>
        user.role === 'field_verifier'
          ? item.verifier_id === user.subject
          : ['officer', 'admin'].includes(user.role) && item.status !== 'pending_photo',
      );
      if (!['field_verifier', 'officer', 'admin'].includes(user.role)) {
        return jsonResponse(route, { detail: 'Forbidden' }, 403);
      }
      return jsonResponse(route, visible);
    }
    if (method === 'POST' && path === '/api/v1/field-verification/evidence') {
      if (user.role !== 'field_verifier') return jsonResponse(route, { detail: 'Forbidden' }, 403);
      const body = request.postDataJSON();
      state.metadataPosts.push({ subject: user.subject, body });
      let existing = [...evidence.values()].find(item =>
        item.verifier_id === user.subject && item.client_record_id === body.client_record_id,
      );
      if (existing && existing.status !== 'submitted') {
        existing = { ...existing, ...body, status: 'pending_photo' };
      }
      if (!existing) {
        existing = makeEvidence(`uploaded-${state.metadataPosts.length}`, {
          ...body,
          verifier_id: user.subject,
          status: 'pending_photo',
          photo_sha256: null,
        });
      }
      evidence.set(existing.id, existing);
      return jsonResponse(route, existing, 201);
    }

    const evidenceMatch = path.match(/^\/api\/v1\/field-verification\/evidence\/([^/]+)(?:\/(photo|audit|review))?$/);
    if (evidenceMatch) {
      const id = decodeURIComponent(evidenceMatch[1]);
      const action = evidenceMatch[2];
      let record = evidence.get(id);
      if (action === 'audit' && method === 'GET') {
        if (!['officer', 'admin'].includes(user.role)) return jsonResponse(route, { detail: 'Forbidden' }, 403);
        if (!record) return jsonResponse(route, { detail: 'Not found' }, 404);
        return jsonResponse(route, audit.get(id) || []);
      }
      if (action === 'photo' && method === 'GET') {
        if (!record || (user.role === 'field_verifier' && record.verifier_id !== user.subject)) {
          return jsonResponse(route, { detail: 'Not found' }, 404);
        }
        if (!['field_verifier', 'officer', 'admin'].includes(user.role)) return jsonResponse(route, { detail: 'Forbidden' }, 403);
        return route.fulfill({
          status: 200,
          contentType: 'image/png',
          headers: { 'cache-control': 'private, no-store' },
          body: PHOTO,
        });
      }
      if (action === 'photo' && method === 'POST') {
        if (!record || user.role !== 'field_verifier' || record.verifier_id !== user.subject) {
          return jsonResponse(route, { detail: 'Not found' }, 404);
        }
        state.photoPosts.push({ id, subject: user.subject });
        record = { ...record, status: 'submitted', photo_sha256: PHOTO_HASH };
        evidence.set(id, record);
        audit.set(id, [...(audit.get(id) || []), {
          id: `photo-audit-${id}`,
          evidence_id: id,
          actor_id: user.subject,
          action: 'submitted',
          note: null,
          created_at: new Date().toISOString(),
        }]);
        return jsonResponse(route, record);
      }
      if (action === 'review' && method === 'POST') {
        if (!['officer', 'admin'].includes(user.role)) return jsonResponse(route, { detail: 'Forbidden' }, 403);
        if (!record) return jsonResponse(route, { detail: 'Not found' }, 404);
        const body = request.postDataJSON();
        if (body.decision !== 'approved' && !body.note?.trim()) {
          return jsonResponse(route, { detail: 'Review note required' }, 422);
        }
        record = {
          ...record,
          status: body.decision,
          reviewer_id: user.subject,
          review_note: body.note.trim() || null,
          reviewed_at: new Date().toISOString(),
        };
        evidence.set(id, record);
        state.reviewPosts.push({ id, role: user.role, ...body });
        audit.set(id, [...(audit.get(id) || []), {
          id: `review-audit-${id}`,
          evidence_id: id,
          actor_id: user.subject,
          action: body.decision,
          note: record.review_note,
          created_at: record.reviewed_at,
        }]);
        return jsonResponse(route, record);
      }
      if (!action && method === 'GET') {
        if (!record || (user.role === 'field_verifier' && record.verifier_id !== user.subject)) {
          return jsonResponse(route, { detail: 'Not found' }, 404);
        }
        return jsonResponse(route, record);
      }
    }

    state.unexpectedRequests.push({ method, path, role: user.role });
    return jsonResponse(route, { detail: 'No synthetic API fixture for this request' }, 404);
  });

  await page.route('https://*.tile.openstreetmap.org/**', route => route.abort());
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: {
        getCurrentPosition(success) {
          success({
            coords: { latitude: 17.385, longitude: 78.4867, accuracy: 4 },
            timestamp: Date.now() - 60_000,
          });
        },
      },
    });
  });
  return state;
}

async function signIn(page, email, password = 'Synthetic-password-123!') {
  await page.getByLabel('Account email').fill(email);
  await page.getByLabel('Account password').fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.locator('.auth-panel')).toContainText('Signed in:');
}

async function openSection(page, label) {
  await page.getByRole('navigation', { name: 'Main navigation' })
    .getByRole('button', { name: label, exact: true }).click();
}

async function saveSyntheticDraft(page, observation = 'Synthetic offline crop observation') {
  await page.getByLabel('Parcel', { exact: true }).selectOption(PARCEL_A);
  await page.getByLabel('Field observation').fill(observation);
  await page.getByRole('button', { name: 'Capture GPS' }).click();
  await expect(page.getByText('GPS captured. Check its accuracy before saving.')).toBeVisible();
  await page.getByLabel('Evidence photo (max 8 MB)').setInputFiles({
    name: 'synthetic-evidence.png',
    mimeType: 'image/png',
    buffer: PHOTO,
  });
  await page.getByRole('button', { name: 'Save Offline Draft' }).click();
  await expect(page.getByText(observation, { exact: true })).toBeVisible();
}

test('farmer registration, duplicate handling, login, logout, and expiry', async ({ page }) => {
  const state = await installApiMocks(page);
  await page.goto('/');

  await page.getByRole('button', { name: 'Register as farmer' }).click();
  await page.getByLabel('Account email').fill('new.farmer@example.test');
  await page.getByLabel('Account password').fill('Synthetic-password-123!');
  await page.getByRole('button', { name: 'Create farmer account' }).click();
  await expect(page.locator('.auth-panel')).toContainText('Signed in: farmer');
  expect(state.registrations).toEqual([{ email: 'new.farmer@example.test', role: 'farmer' }]);

  await page.getByRole('button', { name: 'Sign out' }).click();
  await page.getByRole('button', { name: 'Register as farmer' }).click();
  await page.getByLabel('Account email').fill('new.farmer@example.test');
  await page.getByLabel('Account password').fill('Synthetic-password-123!');
  await page.getByRole('button', { name: 'Create farmer account' }).click();
  await expect(page.getByRole('alert')).toContainText('Email already registered');

  await page.getByRole('button', { name: 'Sign in instead' }).click();
  await page.getByLabel('Account email').fill('expiry@example.test');
  await page.getByLabel('Account password').fill('Synthetic-password-123!');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Your session expired', { timeout: 4_000 });
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
  expect(state.unexpectedRequests).toEqual([]);
});

test('login displays the sanitized service status instead of a generic error', async ({ page }) => {
  await installApiMocks(page, { loginFailureStatus: 503 });
  await page.goto('/');
  await page.getByLabel('Account email').fill('synthetic@example.test');
  await page.getByLabel('Account password').fill('synthetic-only-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('HTTP 503');
  await expect(page.getByRole('alert')).toContainText('server configuration or availability issue');
  await expect(page.getByRole('alert')).not.toContainText('synthetic-only-password');
});

test('farmer parcel list and map contain only owned parcel boundaries', async ({ page }) => {
  const state = await installApiMocks(page);
  await page.goto('/');
  await signIn(page, 'farmer.a@example.test');
  await openSection(page, 'Parcel Registry');

  await expect(page.getByText('FARMER-A-PARCEL')).toBeVisible();
  await expect(page.getByText('FARMER-B-PARCEL')).toHaveCount(0);
  await expect(page.getByText('1 parcels in viewport')).toBeVisible();
  await expect(page.locator('.leaflet-overlay-pane path')).toHaveCount(1);
  expect(state.parcelQueries.every(query => query.subject === FARMER_A)).toBe(true);
  expect(state.unexpectedRequests).toEqual([]);
});

test('offline GPS/photo drafts persist for verifier A and remain isolated from verifier B', async ({ page }) => {
  const state = await installApiMocks(page);
  await page.goto('/');
  await signIn(page, 'verifier.a@example.test');
  await openSection(page, 'Field Verification');
  await saveSyntheticDraft(page);
  await expect(page.getByText('Photo attached locally')).toBeVisible();
  await expect(page.getByText('Saved offline on this device. Nothing uploaded.')).toBeVisible();
  expect(state.metadataPosts).toHaveLength(0);
  expect(state.photoPosts).toHaveLength(0);

  await page.reload();
  await signIn(page, 'verifier.a@example.test');
  await openSection(page, 'Field Verification');
  await expect(page.getByText('Synthetic offline crop observation', { exact: true })).toBeVisible();
  await expect(page.getByText('Photo attached locally')).toBeVisible();

  await page.locator('header').getByRole('button', { name: 'Sign out' }).click();
  await signIn(page, 'verifier.b@example.test');
  await openSection(page, 'Field Verification');
  await expect(page.getByText('No offline drafts saved on this device.')).toBeVisible();
  await expect(page.getByText('Synthetic offline crop observation', { exact: true })).toHaveCount(0);
  expect(state.unexpectedRequests).toEqual([]);
});

test('verifier sync uploads complete evidence once and does not duplicate a completed retry', async ({ page }) => {
  const state = await installApiMocks(page);
  await page.goto('/');
  await signIn(page, 'verifier.a@example.test');
  await openSection(page, 'Field Verification');
  await saveSyntheticDraft(page, 'Synthetic sync-once observation');

  await page.getByRole('button', { name: 'Mark Ready' }).click();
  await expect(page.getByText('Evidence metadata queued locally. Photo retained in the original draft. No server submission.')).toBeVisible();
  expect(state.metadataPosts).toHaveLength(0);

  await page.getByRole('button', { name: 'Sync 1 ready record(s) with photos' }).click();
  await expect(page.getByText('1 complete evidence record(s) submitted with photo.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sync 0 ready record(s) with photos' })).toBeDisabled();
  expect(state.metadataPosts).toHaveLength(1);
  expect(state.photoPosts).toHaveLength(1);
  expect(state.evidence.get(state.photoPosts[0].id).status).toBe('submitted');
  expect(state.unexpectedRequests).toEqual([]);
});

test('officer can approve, reject, request correction, and inspect audit history; verifier access is denied', async ({ page }) => {
  const state = await installApiMocks(page);
  await page.goto('/');
  await signIn(page, 'officer@example.test');
  await openSection(page, 'Officer Review');
  page.on('dialog', dialog => dialog.accept());

  const actions = [
    { id: EVIDENCE_IDS[0], observation: 'Synthetic observation 1', decision: 'approved', label: 'Approve', note: '' },
    { id: EVIDENCE_IDS[1], observation: 'Synthetic observation 2', decision: 'rejected', label: 'Reject', note: 'Synthetic rejection reason' },
    { id: EVIDENCE_IDS[2], observation: 'Synthetic observation 3', decision: 'correction_requested', label: 'Request Correction', note: 'Synthetic correction request' },
  ];
  for (const action of actions) {
    const card = page.locator('.field-draft').filter({ hasText: action.observation }).first();
    await card.getByRole('button', { name: 'Inspect' }).click();
    await expect(page.getByRole('heading', { name: 'Audit History' })).toBeVisible();
    await expect(page.getByRole('img', { name: 'Authorized field evidence' })).toBeVisible();
    await page.getByLabel('Decision').selectOption(action.decision);
    if (action.note) await page.getByLabel('Review note').fill(action.note);
    await page.getByRole('button', { name: 'Record Decision' }).click();
    await expect(page.getByText(`Decision recorded: ${action.label}.`)).toBeVisible();
    await expect(page.locator('.field-note').filter({ hasText: action.decision }).last()).toBeVisible();
  }
  expect(state.reviewPosts.map(item => item.decision)).toEqual(['approved', 'rejected', 'correction_requested']);
  expect(state.unexpectedRequests).toEqual([]);

  await page.getByRole('button', { name: 'Sign out' }).click();
  const anonymousPhoto = await page.evaluate(async ({ api, id }) => {
    const response = await fetch(`${api}/api/v1/field-verification/evidence/${id}/photo`);
    return response.status;
  }, { api: API, id: EVIDENCE_IDS[0] });
  expect(anonymousPhoto).toBe(401);

  await signIn(page, 'verifier.b@example.test');
  const forbiddenReview = await page.evaluate(async ({ api, id }) => {
    const response = await fetch(`${api}/api/v1/field-verification/evidence/${id}/review`, {
      method: 'POST',
      headers: { Authorization: 'Bearer mock-token-verifier.b@example.test', 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision: 'approved', note: '' }),
    });
    return response.status;
  }, { api: API, id: EVIDENCE_IDS[0] });
  const privatePhoto = await page.evaluate(async ({ api, id }) => {
    const response = await fetch(`${api}/api/v1/field-verification/evidence/${id}/photo`, {
      headers: { Authorization: 'Bearer mock-token-verifier.b@example.test' },
    });
    return response.status;
  }, { api: API, id: EVIDENCE_IDS[0] });
  expect(forbiddenReview).toBe(403);
  expect(privatePhoto).toBe(404);
});

test('parcel workspace has no horizontal page overflow at mobile, tablet, and desktop sizes', async ({ page }) => {
  const state = await installApiMocks(page);
  await page.goto('/');
  await signIn(page, 'farmer.a@example.test');
  await openSection(page, 'Parcel Registry');

  for (const width of [390, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(() => page.evaluate(() =>
      document.documentElement.scrollWidth <= window.innerWidth,
    )).toBe(true);
  }
  expect(state.unexpectedRequests).toEqual([]);
});

test('agent metadata renders all eight backend records for authorized governance roles', async ({ page }) => {
  const state = await installApiMocks(page);
  const browserErrors = [];
  page.on('pageerror', error => browserErrors.push(error.message));
  for (const account of ['admin@example.test', 'gis@example.test', 'ml@example.test']) {
    await page.goto('/');
    await signIn(page, account);
    await openSection(page, 'AI Agents');

    await expect(page.getByRole('heading', { name: 'Agent metadata' })).toBeVisible();
    await expect(page.locator('.agent-card')).toHaveCount(8);
    await expect(page.locator('.agent-summary')).toContainText('Total agents8');
    await expect(page.locator('.agent-summary')).toContainText('Configured enabled2');
    await expect(page.locator('.agent-summary')).toContainText('Configured disabled6');
    await expect(page.locator('.agent-summary')).toContainText('Dedicated routes8');
    const weatherCard = page.locator('.agent-card').filter({
      has: page.locator('.agent-id').getByText('WEATHER', { exact: true }),
    });
    const learningCard = page.locator('.agent-card').filter({
      has: page.locator('.agent-id').getByText('LEARNING', { exact: true }),
    });
    await expect(weatherCard).toContainText('Runtime readinessNot verified');
    await expect(learningCard).toContainText('Learning capabilityDisabled');

    if (account === 'gis@example.test') {
      await expect(page.getByRole('heading', { name: 'Learning and feedback review' })).toHaveCount(0);
    } else {
      await expect(page.getByRole('heading', { name: 'Learning and feedback review' })).toBeVisible();
    }

    await page.getByRole('button', { name: 'Sign out' }).click();
  }
  expect(browserErrors).toEqual([]);
  expect(state.unexpectedRequests).toEqual([]);
});

test('unauthorized and expired accounts cannot retain Agent Metadata access', async ({ page }) => {
  const state = await installApiMocks(page);
  await page.goto('/');
  await signIn(page, 'farmer.a@example.test');
  await expect(page.getByRole('navigation', { name: 'Main navigation' })
    .getByRole('button', { name: 'AI Agents', exact: true })).toHaveCount(0);

  await page.getByRole('button', { name: 'Sign out' }).click();
  await page.getByLabel('Account email').fill('expiry.admin@example.test');
  await page.getByLabel('Account password').fill('Synthetic-password-123!');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Your session expired', { timeout: 4_000 });
  await expect(page.getByRole('heading', { name: 'Agent metadata' })).toHaveCount(0);
  expect(state.unexpectedRequests).toEqual([]);
});
