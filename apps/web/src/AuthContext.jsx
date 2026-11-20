
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react';

import {
  API,
  loginOperator,
  verifyOperator,
  refreshOperator,
  logoutOperator
} from './gisApi.js';

import {
  authorizationMessage,
  authorizedFetch
} from './authUtils.js';

const AuthContext = createContext(null);

const SESSION_EXPIRED_MESSAGE =
  'Your session expired. Sign in again.';
const LOGOUT_FAILED_MESSAGE =
  'Signed out locally, but the server could not confirm sign-out. Please retry when the API is available.';

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [message, setMessage] = useState('');
  const [restoring, setRestoring] = useState(true);

  const epoch = useRef(0);
  const renewInFlight = useRef(null);
  const sessionRef = useRef(null);
  const logoutPending = useRef(false);

  const updateSession = useCallback((next) => {
    sessionRef.current = next;
    setSession(next);
  }, []);

  const clearSession = useCallback((reason = '') => {
    epoch.current += 1;
    renewInFlight.current = null;
    updateSession(null);
    setMessage(reason);
  }, [updateSession]);

  const applyToken = useCallback(async (result, expectedEpoch) => {
    if (!result?.access_token) {
      return null;
    }

    const principal = await verifyOperator(result.access_token);

    if (epoch.current !== expectedEpoch) {
      return null;
    }

    const next = {
      token: result.access_token,
      principal,
      expiresAt:
        Date.now() +
        Math.max(1, result.expires_in || 900) * 1000
    };

    updateSession(next);
    setMessage('');

    return next;
  }, [updateSession]);

  const renew = useCallback(async () => {
    if (logoutPending.current) {
      return null;
    }

    const currentEpoch = epoch.current;

    if (
      renewInFlight.current &&
      renewInFlight.current.epoch === currentEpoch
    ) {
      return renewInFlight.current.promise;
    }

    const pending = (async () => {
      try {
        const result = await refreshOperator();

        if (
          !result ||
          epoch.current !== currentEpoch ||
          logoutPending.current
        ) {
          return null;
        }

        return await applyToken(result, currentEpoch);
      } catch (error) {
        if (epoch.current === currentEpoch) {
          throw error;
        }

        return null;
      }
    })();

    const entry = {
      epoch: currentEpoch,
      promise: pending
    };

    renewInFlight.current = entry;

    try {
      return await pending;
    } finally {
      if (renewInFlight.current === entry) {
        renewInFlight.current = null;
      }
    }
  }, [applyToken]);

  // Restore an existing browser session on application startup.
  useEffect(() => {
    let active = true;

    const restoreSession = async () => {
      try {
        await renew();
      } catch (error) {
        // A 401 is returned as null by refreshOperator. Other failures mean
        // the backend is unavailable and should not look like an auth error.
        if (active) {
          setMessage(error?.message || 'Unable to restore the session because the API is unavailable.');
        }
      } finally {
        if (active) {
          setRestoring(false);
        }
      }
    };

    restoreSession();

    return () => {
      active = false;
    };
  }, [renew]);

  const login = useCallback(async (
    email,
    password,
    allowedRoles = null
  ) => {
    const currentEpoch = ++epoch.current;

    renewInFlight.current = null;
    updateSession(null);
    setMessage('');

    const result = await loginOperator(
      email.trim(),
      password
    );

    if (epoch.current !== currentEpoch) {
      return null;
    }

    const principal = await verifyOperator(
      result.access_token
    );

    if (epoch.current !== currentEpoch) {
      return null;
    }

    if (
      allowedRoles &&
      !allowedRoles.includes(principal.role)
    ) {
      try {
        await logoutOperator();
      } catch {
        // Preserve the role authorization failure.
      }

      if (epoch.current === currentEpoch) {
        updateSession(null);
      }

      throw new Error(
        `This area requires one of these roles: ${allowedRoles.join(', ')}.`
      );
    }

    const next = {
      token: result.access_token,
      principal,
      expiresAt:
        Date.now() +
        Math.max(1, result.expires_in || 900) * 1000
    };

    if (epoch.current !== currentEpoch) {
      return null;
    }

    updateSession(next);
    setMessage('');

    return next;
  }, [updateSession]);

  const logout = useCallback(async (reason = '') => {
    // Invalidate outstanding authentication operations.
    epoch.current += 1;
    renewInFlight.current = null;

    logoutPending.current = true;

    // Immediately remove access to the authenticated UI.
    updateSession(null);
    setMessage(reason);

    try {
      await logoutOperator();

      setMessage(reason);

      return {
        success: true
      };
    } catch (error) {
      setMessage(LOGOUT_FAILED_MESSAGE);

      return {
        success: false,
        error
      };
    } finally {
      logoutPending.current = false;
    }
  }, [updateSession]);

  // Renew the access token before it expires.
  useEffect(() => {
    if (!session) {
      return;
    }

    const currentEpoch = epoch.current;
    const currentToken = session.token;

    const delay = Math.max(
      0,
      session.expiresAt - Date.now() - 60000
    );

    const timer = setTimeout(async () => {
      if (
        epoch.current !== currentEpoch ||
        sessionRef.current?.token !== currentToken ||
        logoutPending.current
      ) {
        return;
      }

      try {
        const next = await renew();

        if (
          !next &&
          epoch.current === currentEpoch &&
          sessionRef.current?.token === currentToken
        ) {
          clearSession(SESSION_EXPIRED_MESSAGE);
        }
      } catch {
        if (
          epoch.current === currentEpoch &&
          sessionRef.current?.token === currentToken
        ) {
          clearSession(SESSION_EXPIRED_MESSAGE);
        }
      }
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [session, renew, clearSession]);

  const request = useCallback(async (
    path,
    options = {}
  ) => {
    if (logoutPending.current) {
      const error = new Error(
        'Sign-out is in progress.'
      );

      error.status = 401;
      error.authFailure = true;

      throw error;
    }

    let current = sessionRef.current;

    if (
      !current?.token ||
      current.expiresAt <= Date.now() + 5000
    ) {
      current = await renew().catch(() => null);
    }

    if (!current?.token) {
      const error = new Error(
        'Authentication required. Sign in to continue.'
      );

      error.status = 401;
      error.authFailure = true;

      throw error;
    }

    const requestEpoch = epoch.current;

    const response = await authorizedFetch(
      `${API}${path}`,
      options,
      current.token,
      () => {
        if (epoch.current === requestEpoch) {
          clearSession(
            'Your session expired or account access changed. Sign in again.'
          );
        }
      }
    );

    if (
      response.status === 401 ||
      response.status === 403
    ) {
      const error = new Error(
        authorizationMessage(response.status)
      );

      error.status = response.status;
      error.authFailure = response.status === 401;

      throw error;
    }

    return response;
  }, [renew, clearSession]);

  const value = useMemo(() => ({
    session,
    message,
    login,
    logout,
    request,
    restoring
  }), [
    session,
    message,
    login,
    logout,
    request,
    restoring
  ]);

  return (
    <AuthContext.Provider value={value}>
      {restoring ? (
        <div
          role="status"
          aria-live="polite"
        >
          Restoring your session…
        </div>
      ) : (
        children
      )}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const value = useContext(AuthContext);

  if (!value) {
    throw new Error(
      'useAuth must be used inside AuthProvider'
    );
  }

  return value;
}
