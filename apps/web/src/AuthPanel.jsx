import React, { useState } from 'react';
import { useAuth } from './AuthContext.jsx';
import { registerFarmer } from './gisApi.js';

export default function AuthPanel() {
  const { session, message, login, logout } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [registering, setRegistering] = useState(false);
  async function submit(event) {
    event.preventDefault(); setError(''); setBusy(true);
    let accountCreated = false;
    try {
      if (registering) {
        await registerFarmer(email.trim(), password);
        accountCreated = true;
        setRegistering(false);
      }
      await login(email, password);
      setPassword('');
    }
    catch (err) {
      if (accountCreated) {
        setRegistering(false);
        setError(`Farmer account created, but automatic sign-in failed: ${err.message || 'Try signing in.'}`);
      } else {
        setError(err.message || 'Sign-in failed.');
      }
    }
    finally { setBusy(false); }
  }
  if (session) return <div className="auth-panel"><span>Signed in: {session.principal.role}</span><button type="button" onClick={() => logout()}>Sign out</button></div>;
  return <div className="auth-panel"><form onSubmit={submit} className="auth-form"><input aria-label="Account email" type="email" required autoComplete="username" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} /><input aria-label="Account password" type="password" required minLength={registering ? 12 : undefined} maxLength={128} autoComplete={registering ? 'new-password' : 'current-password'} placeholder={registering ? 'Password (12+ characters)' : 'Password'} value={password} onChange={e => setPassword(e.target.value)} /><button disabled={busy}>{busy ? (registering ? 'Creating account...' : 'Signing in...') : registering ? 'Create farmer account' : 'Sign in'}</button><button type="button" className="auth-mode-button" disabled={busy} onClick={() => { setRegistering(value => !value); setError(''); }}>{registering ? 'Sign in instead' : 'Register as farmer'}</button></form>{(error || message) && <span className="gis-error" role="alert">{error || message}</span>}</div>;
}
