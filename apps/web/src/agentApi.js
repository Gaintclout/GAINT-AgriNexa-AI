export async function loadAgentMetadata(request, signal) {
  const response = await request('/api/v1/agents', { method: 'GET', signal });
  if (!response.ok) throw new Error(`Unable to load agent metadata (HTTP ${response.status}).`);
  const data = await response.json().catch(() => null);
  if (!Array.isArray(data)) throw new Error('Agent metadata response is invalid.');
  return data;
}
