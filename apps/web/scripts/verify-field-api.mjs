const API = (
  process.env.API_BASE_URL || 'http://localhost:8000'
).replace(/\/$/, '');

const endpoints = [
  { name: 'Health', path: '/health' },
  { name: 'Metadata', path: '/api/v1/metadata' },
  {
    name: 'Field evidence API',
    path: '/api/v1/field-verification/evidence'
  }
];

async function checkEndpoint(endpoint) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);

  try {
    const response = await fetch(
      `${API}${endpoint.path}`,
      {
        method: 'GET',
        signal: controller.signal,
        redirect: 'manual',
        headers: { Accept: 'application/json' }
      }
    );

    let result;

    if (response.status === 401) {
      result = 'AUTH REQUIRED';
    } else if (response.status === 403) {
      result = 'ACCESS DENIED';
    } else if (response.status === 404) {
      result = 'NOT FOUND';
    } else if (response.status >= 500) {
      result = 'SERVER ERROR';
    } else if (response.status >= 300) {
      result = 'REDIRECT';
    } else if (response.ok) {
      result = 'REACHABLE';
    } else {
      result = 'CHECK REQUIRED';
    }

    return {
      endpoint: endpoint.name,
      status: response.status,
      result
    };
  } catch (error) {
    return {
      endpoint: endpoint.name,
      status: '-',
      result: error.name === 'AbortError'
        ? 'TIMEOUT'
        : 'CONNECTION FAILED'
    };
  } finally {
    clearTimeout(timeout);
  }
}

const results = [];

for (const endpoint of endpoints) {
  results.push(await checkEndpoint(endpoint));
}

console.table(results);

const failures = results.some(
  item => item.result === 'CONNECTION FAILED' ||
    item.result === 'TIMEOUT' ||
    item.result === 'SERVER ERROR' ||
    item.result === 'NOT FOUND'
);

console.log('\nEvidence submission remains DISABLED.');
console.log(
  'Endpoint reachability does not verify authentication, ' +
  'authorization, database migrations or evidence contracts.'
);

if (failures) process.exitCode = 1;
