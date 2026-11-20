import React, { useState } from 'react';
import { useAuth } from './AuthContext.jsx';

export default function FieldVerifierSession() {
  const { session, login: authenticate, logout } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function login(event) {
    event.preventDefault(); setError(''); setBusy(true);
    try {
      await authenticate(email, password, ['field_verifier']);
      setPassword('');
    } catch (err) { setError(err.message || 'Sign-in failed'); }
    finally { setBusy(false); }
  }
  return <section className="field-card" aria-label="Field Verifier sign-in">
    <h3>Field Verifier access</h3>
    {session?.principal.role === 'field_verifier' ? <div><p>Authenticated Field Verifier session active.</p><button type="button" onClick={() => logout()}>Sign out</button></div> :
      <form onSubmit={login} className="field-form">
        <label htmlFor="fv-email">Email</label><input id="fv-email" type="email" required autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} />
        <label htmlFor="fv-password">Password</label><input id="fv-password" type="password" required autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} />
        <button type="submit" disabled={busy}>{busy ? 'Signing in...' : 'Sign in to load parcels'}</button>
      </form>}
    {error && <p role="alert" className="gis-error">{error}</p>}
  </section>;
}
