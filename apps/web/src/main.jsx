
import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Home,
  MapPinned,
  LayoutDashboard,
  ClipboardList,
  ClipboardCheck,
  Satellite,
  Sprout,
  Bot,
  PanelLeftClose,
  PanelLeftOpen,
  Menu,
  X,
  ChevronRight
} from 'lucide-react';

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

const STAFF_ICONS = {
  overview: LayoutDashboard,
  parcels: MapPinned,
  verification: ClipboardList,
  review: ClipboardCheck,
  scim: Satellite,
  crop: Sprout,
  agents: Bot
};

const STAFF_LABELS = {
  overview: 'Dashboard',
  parcels: 'Land Management',
  verification: 'Field Verification',
  review: 'Officer Review',
  scim: 'Satellite Catalogue',
  crop: 'Crop Intelligence',
  agents: 'AI Agents'
};

function App() {
  const { session } = useAuth();

  const [page, setPage] = useState('overview');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [health, setHealth] = useState('Checking');
  const [meta, setMeta] = useState(null);

  const role = session?.principal.role;

  const navigation = useMemo(
    () => navigationForRole(role),
    [role]
  );

  // Existing API health and metadata checks
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

        const ready = await readyResponse.json()
          .catch(() => null);

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

  // Existing role-based navigation
  const selectPage = id => {
    if (navigation.some(item => item.id === id)) {
      setPage(id);
      setMobileNavOpen(false);
    }
  };

  useEffect(() => {
    if (!navigation.some(item => item.id === page)) {
      setPage('overview');
    }
  }, [navigation, page]);

  // Return to dashboard after signing out
  useEffect(() => {
    if (!session) {
      setPage('overview');
    }
  }, [session]);

  // Standalone login and registration screen
  if (!session) {
    return (
      <main className="agrinexa-login-page">

        <div className="agrinexa-login-container">
          <AuthPanel />

          <footer className="agrinexa-login-footer">
            <p>
              Powered by GAINT Clout Technologies Pvt. Ltd.
            </p>

            <small>
              &copy; {new Date().getFullYear()} GAINT AgriNexa AI
            </small>
          </footer>
        </div>

      </main>
    );
  }

  // Farmer-specific application layout
  if (role === 'farmer') {
    return (
      <div className="farmer-shell">

        <header className="farmer-header">

          <img
            src="/branding/agrinexa-logo.webp"
            alt="GAINT AgriNexa AI"
            className="farmer-header-logo"
          />

          <div className="farmer-header-account">
            <AuthPanel />
          </div>

        </header>

        <main className="farmer-main">

          {page === 'overview' && (
            <RoleDashboard
              role={role}
              navigation={navigation}
              onNavigate={selectPage}
            />
          )}

          {page === 'parcels' &&
            navigation.some(item => item.id === 'parcels') && (
              <ParcelRegistry />
          )}

        </main>

        <nav
          className="farmer-bottom-nav"
          aria-label="Farmer navigation"
        >
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
              {item.id === 'overview' ? (
                <Home size={24} aria-hidden="true" />
              ) : (
                <MapPinned size={24} aria-hidden="true" />
              )}

              <span>{item.label}</span>
            </button>
          ))}
        </nav>

      </div>
    );
  }

  // Authenticated staff application dashboard

  const currentLabel =
    STAFF_LABELS[page] ||
    navigation.find(item => item.id === page)?.label ||
    'Dashboard';

  const canOpen = id =>
    page === id &&
    navigation.some(item => item.id === id);

  return (
    <div
      className={[
        'shell',
        'agrinexa-staff-shell',
        sidebarCollapsed ? 'staff-sidebar-collapsed' : '',
        mobileNavOpen ? 'staff-mobile-open' : ''
      ].filter(Boolean).join(' ')}
    >

      <aside className="staff-sidebar" id="staff-sidebar">

        <div className="staff-brand-row">

          <div className="brand agrinexa-sidebar-brand">
            <img
              src="/branding/agrinexa-logo.webp"
              alt="GAINT AgriNexa AI"
              className="agrinexa-sidebar-logo"
            />
          </div>

          <button
            type="button"
            className="staff-mobile-close"
            aria-label="Close navigation"
            onClick={() => setMobileNavOpen(false)}
          >
            <X size={23} />
          </button>

        </div>

        <span className="staff-nav-heading">
          Workspace
        </span>

        <nav className="nav staff-nav" aria-label="Main navigation">

          {navigation.map(item => {

            const Icon = STAFF_ICONS[item.id] || LayoutDashboard;
            const label = STAFF_LABELS[item.id] || item.label;

            return (
              <button
                key={item.id}
                type="button"
                className={page === item.id ? 'active' : ''}
                onClick={() => selectPage(item.id)}
                aria-current={page === item.id ? 'page' : undefined}
                aria-label={label}
                title={label}
              >
                <Icon size={21} strokeWidth={1.8} aria-hidden="true" />

                <span className="staff-nav-label">
                  {label}
                </span>

                {page === item.id && (
                  <ChevronRight
                    size={16}
                    className="staff-nav-indicator"
                    aria-hidden="true"
                  />
                )}

              </button>
            );
          })}

        </nav>

        <div className="staff-sidebar-footer">

          <button
            type="button"
            className="staff-collapse-button"
            aria-label={
              sidebarCollapsed
                ? 'Expand sidebar'
                : 'Collapse sidebar'
            }
            aria-expanded={!sidebarCollapsed}
            onClick={() => setSidebarCollapsed(value => !value)}
          >

            {sidebarCollapsed
              ? <PanelLeftOpen size={21} />
              : <PanelLeftClose size={21} />}

            <span className="staff-nav-label">
              Collapse sidebar
            </span>

          </button>

          <p className="staff-environment">
            GAINT AgriNexa AI
          </p>

        </div>

      </aside>

      {mobileNavOpen && (
        <button
          type="button"
          className="staff-mobile-overlay"
          aria-label="Close navigation"
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      <main className="staff-main">

        <header className="staff-header">

          <div className="staff-header-title">

            <button
              type="button"
              className="staff-mobile-menu"
              aria-label="Open navigation"
              aria-expanded={mobileNavOpen}
              aria-controls="staff-sidebar"
              onClick={() => setMobileNavOpen(value => !value)}
            >
              <Menu size={24} />
            </button>

            <div>
              <small>AgriNexa AI</small>
              <strong>{currentLabel}</strong>
            </div>

          </div>

          <div className="staff-header-actions">

            <span
              className={`staff-system-status ${
                health === 'Online'
                  ? 'system-online'
                  : health === 'Offline'
                    ? 'system-offline'
                    : 'system-warning'
              }`}
              role="status"
              aria-live="polite"
              title={`API: ${health}`}
            >
              <span className="staff-status-dot" />

              <span>
                {health === 'Online (dependencies unavailable)'
                  ? 'Limited availability'
                  : health}
              </span>

            </span>

            <AuthPanel />

          </div>

        </header>

        <div className="staff-page-content">

          {canOpen('overview') && (
            <RoleDashboard
              role={role}
              navigation={navigation}
              onNavigate={selectPage}
            />
          )}

          {canOpen('parcels') && <ParcelRegistry />}

          {canOpen('scim') && <SCIMDashboard />}

          {canOpen('verification') && <FieldVerification />}

          {canOpen('review') && <OfficerReview />}

          {canOpen('crop') && <CropIntelligence />}

          {canOpen('agents') && <AgentGovernance />}

        </div>

      </main>

    </div>
  );
}

createRoot(
  document.getElementById('root')
).render(
  <AuthProvider>
    <App />
  </AuthProvider>
);
