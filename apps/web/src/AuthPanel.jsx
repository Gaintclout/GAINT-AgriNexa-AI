
import React, { useState } from 'react';
import { useAuth } from './AuthContext.jsx';
import { registerFarmer } from './gisApi.js';

const AUTH_ROLE_LABELS = {
  farmer: 'Farmer',
  admin: 'Administrator',
  field_verifier: 'Field Verifier',
  officer: 'Officer',
  gis_operator: 'GIS Operator',
  ml_team: 'ML Team'
};

export default function AuthPanel() {
  const { session, message, login, logout } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Existing authentication and registration logic
  async function submit(event) {
    event.preventDefault();
    setError('');
    setBusy(true);

    let accountCreated = false;

    try {
      if (registering) {
        await registerFarmer(email.trim(), password);
        accountCreated = true;
        setRegistering(false);
      }

      await login(email, password);
      setPassword('');
      setShowPassword(false);

    } catch (err) {
      if (accountCreated) {
        setRegistering(false);

        setError(
          `Farmer account created, but automatic sign-in failed: ${
            err.message || 'Try signing in.'
          }`
        );
      } else {
        setError(err.message || 'Sign-in failed.');
      }

    } finally {
      setBusy(false);
    }
  }

  // Existing signed-in user interface
  if (session) {
    return (
      <div className="auth-panel">
        <span>
          Signed in: {AUTH_ROLE_LABELS[session.principal.role] || session.principal.role}
        </span>

        <button
          type="button"
          onClick={() => logout()}
        >
          Sign out
        </button>
      </div>
    );
  }

  // Login and farmer registration interface
  return (
    <div className="auth-panel agrinexa-auth">

      {/* Official application logo */}
      <div className="agrinexa-auth-brand">
        <img
          src="/branding/agrinexa-logo.webp"
          alt="GAINT AgriNexa AI"
          className="agrinexa-auth-logo"
        />

        <h1>
          {registering
            ? 'Create your account'
            : 'Welcome back'}
        </h1>

        <p>
          {registering
            ? 'Register to get started with AgriNexa AI.'
            : 'Sign in to access your agriculture services.'}
        </p>
      </div>

      {/* Authentication form */}
      <form
        onSubmit={submit}
        className="auth-form agrinexa-auth-form"
      >

        {/* Email address */}
        <div className="agrinexa-field">
          <label htmlFor="agrinexa-email">
            Email address
          </label>

          <input
            id="agrinexa-email"
            aria-label="Account email"
            type="email"
            required
            autoComplete="username"
            placeholder="Enter your email address"
            value={email}
            onChange={e => setEmail(e.target.value)}
          />
        </div>

        {/* Password */}
        <div className="agrinexa-field">
          <label htmlFor="agrinexa-password">
            Password
          </label>

          <div className="agrinexa-password-field">

            <input
              id="agrinexa-password"
              aria-label="Account password"
              type={showPassword ? 'text' : 'password'}
              required
              minLength={registering ? 12 : undefined}
              maxLength={128}
              autoComplete={
                registering
                  ? 'new-password'
                  : 'current-password'
              }
              placeholder="Enter your password"
              value={password}
              onChange={e => setPassword(e.target.value)}
            />

            {/* Password visibility button */}
            <button
              type="button"
              className="agrinexa-password-toggle"
              aria-label={
                showPassword
                  ? 'Hide password'
                  : 'Show password'
              }
              aria-pressed={showPassword}
              title={
                showPassword
                  ? 'Hide password'
                  : 'Show password'
              }
              onClick={() =>
                setShowPassword(value => !value)
              }
            >
              {showPassword ? (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M3 3l18 18" />
                  <path d="M10.6 10.7a2 2 0 002.7 2.7" />
                  <path d="M9.9 5.2A10.9 10.9 0 0112 5c6 0 10 7 10 7a16 16 0 01-2.3 3.1" />
                  <path d="M6.2 6.2C3.6 8 2 12 2 12s4 7 10 7a10 10 0 004.8-1.3" />
                </svg>
              ) : (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          </div>

          {registering && (
            <small>
              Use at least 12 characters for your password.
            </small>
          )}
        </div>

        {/* Sign-in or registration button */}
        <button
          type="submit"
          className="agrinexa-primary-button"
          disabled={busy}
        >
          {busy
            ? registering
              ? 'Creating account...'
              : 'Signing in...'
            : registering
              ? 'Create farmer account'
              : 'Sign in'}
        </button>

        {/* Inline authentication messages */}
        {(error || message) && (
          <div
            className="gis-error agrinexa-auth-message"
            role="alert"
          >
            {error || message}
          </div>
        )}

        {/* Switch between login and registration */}
        <div className="agrinexa-auth-switch">
          <p>
            {registering
              ? 'Already have an account?'
              : 'New to AgriNexa AI?'}
          </p>

          <button
            type="button"
            className="auth-mode-button"
            disabled={busy}
            onClick={() => {
              setRegistering(value => !value);
              setError('');
              setShowPassword(false);
            }}
          >
            {registering
              ? 'Sign in instead'
              : 'Register as farmer'}
          </button>
        </div>

      </form>
    </div>
  );
}
