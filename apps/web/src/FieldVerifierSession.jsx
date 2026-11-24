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
  return <section className="field-card field-session-card" aria-label="Field Verifier sign-in">
    <h3>Account access</h3>
    {session?.principal.role === 'field_verifier' ? <div className="field-session-active">

  <div className="field-session-information">

    <span className="field-session-icon" aria-hidden="true">
      <svg width="26" height="26" viewBox="0 0 24 24"
        fill="none" stroke="currentColor" strokeWidth="1.8"
        strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11"/>
        <path d="m9 12 2 2 4-4"/>
      </svg>
    </span>

    <div>
      <strong>Field Verifier</strong>
      <span className="field-session-status">
        <span aria-hidden="true" />
        Signed in
      </span>
    </div>

  </div>

  <button
    type="button"
    className="field-secondary"
    onClick={() => logout()}
  >
    Sign out
  </button>

</div> :
      <form onSubmit={login} className="field-form">
        <label htmlFor="fv-email">Email</label><input id="fv-email" type="email" required autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} />
        <label htmlFor="fv-password">Password</label><input id="fv-password" type="password" required autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} />
        <button type="submit" disabled={busy}>{busy ? 'Signing in...' : 'Sign in to load parcels'}</button>
      </form>}
    {error && <p role="alert" className="gis-error">{error}</p>}
  </section>;
}
