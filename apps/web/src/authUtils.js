export function authorizationMessage(status) {
  if (status === 401) return 'Your session expired. Sign in again.';
  if (status === 403) return 'Your account is not authorized for this action.';
  return `Request failed (${status})`;
}

export function withBearer(options = {}, token) {
  const headers = new Headers(options.headers || {});
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return { ...options, headers };
}

export async function authorizedFetch(url, options, token, onUnauthorized, fetchImpl = fetch) {
  const response = await fetchImpl(url, withBearer(options, token));
  if (response.status === 401) onUnauthorized?.();
  return response;
}
