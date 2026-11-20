
import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Sprout } from 'lucide-react';

import './style.css';
import ParcelRegistry from './ParcelRegistry.jsx';
import SCIMDashboard from './SCIMDashboard.jsx';
import FieldVerification from './FieldVerification.jsx';
import { AuthProvider, useAuth } from './AuthContext.jsx';
import AuthPanel from './AuthPanel.jsx';
import OfficerReview from './OfficerReview.jsx';
import RoleDashboard from './RoleDashboard.jsx';
import CropIntelligence from './CropIntelligence.jsx';
import AgentGovernance from './AgentGovernance.jsx';
import { navigationForRole } from './navigation.js';

function App() {
  const { session } = useAuth();
  const [page, setPage] = useState('overview');
  const [health, setHealth] = useState('Checking');
  const [meta, setMeta] = useState(null);
  const role = session?.principal.role;
  const navigation = useMemo(() => navigationForRole(role), [role]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadHealth() {
      try {
        const liveResponse = await fetch('/live', {
          signal: controller.signal
        });

        if (!liveResponse.ok) {
          throw new Error('Liveness check failed');
        }

        const live = await liveResponse.json();

        if (live.status !== 'ok') {
          throw new Error('Liveness check failed');
        }

        const readyResponse = await fetch('/ready', {
          signal: controller.signal
        });
        const ready = await readyResponse.json().catch(() => null);

        if (!controller.signal.aborted) {
          setHealth(
            readyResponse.ok && ready?.status === 'ready'
              ? 'Online'
              : 'Online (dependencies unavailable)'
          );
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setHealth('Offline');
        }
      }
    }

    async function loadMetadata() {
      try {
        const response = await fetch(
          '/api/v1/metadata',
          { signal: controller.signal }
        );

        if (!response.ok) {
          throw new Error('Metadata unavailable');
        }

        const data = await response.json();

        if (!controller.signal.aborted) {
          setMeta(data);
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setMeta(null);
        }
      }
    }

    loadHealth();
    loadMetadata();

    return () => controller.abort();
  }, []);

  const selectPage = id => {
    if (navigation.some(item => item.id === id)) {
      setPage(id);
    }
  };

  useEffect(() => {
    if (!navigation.some(item => item.id === page)) setPage('overview');
  }, [navigation, page]);

  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <Sprout size={29} />
          <span>
            GAINT
            <br />
            <small>AgriNexa AI</small>
          </span>
        </div>

        <nav className="nav" aria-label="Main navigation">
          {navigation.map(item => (
            <button
              key={item.id}
              type="button"
              className={page === item.id ? 'active' : ''}
              onClick={() => selectPage(item.id)}
              aria-current={
                page === item.id ? 'page' : undefined
              }
            >
              {item.label}
            </button>
          ))}
        </nav>

        <p className="aside-foot">
          Development environment
        </p>
      </aside>

      <main>
        <header>
          <span>
            Integrated Agricultural Intelligence
          </span>

          <span
            className="status"
            role="status"
            aria-live="polite"
          >
            API: {health}
          </span>
          <AuthPanel />
        </header>

        {page === 'overview' && <RoleDashboard role={session?.principal.role} navigation={navigation} onNavigate={selectPage} />}

        {page === 'parcels' && (
          <ParcelRegistry />
        )}

        {page === 'scim' && (
          <SCIMDashboard />
        )}

        {page === 'verification' && (
          <FieldVerification />
        )}

        {page === 'review' && (
          <OfficerReview />
        )}

        {page === 'crop' && <CropIntelligence />}

        {page === 'agents' && <AgentGovernance />}
      </main>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<AuthProvider><App /></AuthProvider>);
