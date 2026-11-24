
import React from 'react';
import {
  Activity,
  ClipboardCheck,
  MapPinned,
  ShieldCheck,
  Sprout,
  ArrowRight,
  Leaf,
  LayoutDashboard
} from 'lucide-react';

const WORKSPACES = {
  parcels: {
    icon: MapPinned,
    description: 'View authorized parcel records and ownership-scoped data.'
  },
  verification: {
    icon: ShieldCheck,
    description: 'Capture field evidence offline and manage your sync queue.'
  },
  review: {
    icon: ClipboardCheck,
    description: 'Inspect submitted field evidence and record auditable decisions.'
  },
  scim: {
    icon: Activity,
    description: 'Discover satellite metadata and review SCIM processing status.'
  },
  crop: {
    icon: Sprout,
    description: 'Calculate spectral indices from validated reflectance inputs.'
  },
  agents: {
    icon: Activity,
    description: 'Inspect the agent identifiers published by the API and the missing governance controls.'
  }
};

const ROLE_NAMES = {
  farmer: 'Farmer',
  field_verifier: 'Field Verifier',
  officer: 'Officer',
  admin: 'Administrator',
  gis_operator: 'GIS Operator',
  ml_team: 'ML Team'
};

export default function RoleDashboard({
  role,
  navigation,
  onNavigate
}) {
  const workspaces = navigation.filter(
    item => item.id !== 'overview'
  );

  const canViewLand = workspaces.some(
    item => item.id === 'parcels'
  );

  // Farmer-friendly dashboard
  if (role === 'farmer') {
    return (
      <section className="farmer-dashboard">

        {/* Welcome card */}
        <div className="farmer-welcome">

          <div className="farmer-welcome-content">

            <span className="farmer-welcome-label">
              <Leaf size={18} aria-hidden="true" />
              Your farming companion
            </span>

            <h1>Welcome, Farmer!</h1>

            <p>
              View your agricultural land details
              and records in one place.
            </p>

            {canViewLand && (
              <button
                type="button"
                className="farmer-primary-button"
                onClick={() => onNavigate('parcels')}
              >
                View my land
                <ArrowRight size={20} aria-hidden="true" />
              </button>
            )}

          </div>

          <div
            className="farmer-welcome-art"
            aria-hidden="true"
          >
            <Sprout size={100} strokeWidth={1.3} />
          </div>

        </div>

        {/* Available services */}
        <div className="farmer-section-heading">
          <h2>My services</h2>
          <p>Select a service to get started.</p>
        </div>

        <div className="farmer-services-grid">

          {canViewLand && (
            <button
              type="button"
              className="farmer-service-card"
              onClick={() => onNavigate('parcels')}
            >
              <span className="farmer-service-icon">
                <MapPinned
                  size={30}
                  strokeWidth={1.8}
                  aria-hidden="true"
                />
              </span>

              <span className="farmer-service-content">
                <strong>My Land</strong>
                <span>
                  View your land details and records.
                </span>
              </span>

              <ArrowRight
                className="farmer-service-arrow"
                size={22}
                aria-hidden="true"
              />
            </button>
          )}

          {workspaces
            .filter(item => item.id !== 'parcels')
            .map(item => {
              const workspace = WORKSPACES[item.id];
              const Icon = workspace?.icon || LayoutDashboard;

              return (
                <button
                  key={item.id}
                  type="button"
                  className="farmer-service-card"
                  onClick={() => onNavigate(item.id)}
                >
                  <span className="farmer-service-icon">
                    <Icon size={30} aria-hidden="true" />
                  </span>

                  <span className="farmer-service-content">
                    <strong>{item.label}</strong>
                    <span>
                      {workspace?.description || 'View service details.'}
                    </span>
                  </span>

                  <ArrowRight
                    className="farmer-service-arrow"
                    size={22}
                    aria-hidden="true"
                  />
                </button>
              );
            })}

        </div>

        {workspaces.length === 0 && (
          <p className="dashboard-notice">
            No services are currently available for your account.
          </p>
        )}

        {/* Data access information */}
        <div className="farmer-privacy-card">

          <ShieldCheck
            size={28}
            strokeWidth={1.8}
            aria-hidden="true"
          />

          <div>
            <strong>Your land information</strong>
            <p>
              You can view land records available
              to your account.
            </p>
          </div>

        </div>

      </section>
    );
  }



  // Unified role-based staff dashboard

  const roleProfiles = {

    admin: {
      label: 'Administration workspace',
      description: 'Manage agricultural land, review field evidence and access agricultural intelligence workspaces.',
      icon: ShieldCheck
    },

    officer: {
      label: 'Evidence review workspace',
      description: 'Review agricultural land records and submitted field evidence.',
      icon: ClipboardCheck
    },

    gis_operator: {
      label: 'Geospatial intelligence workspace',
      description: 'Manage agricultural land records and explore satellite and crop intelligence.',
      icon: MapPinned
    },

    ml_team: {
      label: 'Agricultural intelligence workspace',
      description: 'Explore spectral measurements, satellite metadata and governed AI workflows.',
      icon: Activity
    },

    field_verifier: {
      label: 'Field operations workspace',
      description: 'View assigned land records, capture field evidence and manage offline submissions.',
      icon: ShieldCheck
    }

  };

  const modules = {

    parcels: {
      title: 'Land Management',
      description: ['admin', 'gis_operator'].includes(role)
        ? 'Manage agricultural land records and ownership.'
        : 'View authorized agricultural land records.',
      icon: MapPinned,
      theme: 'green'
    },

    verification: {
      title: 'Field Verification',
      description: 'Capture field evidence, save offline drafts and manage synchronization.',
      icon: ShieldCheck,
      theme: 'orange'
    },

    review: {
      title: 'Officer Review',
      description: 'Inspect submitted field evidence and record review decisions.',
      icon: ClipboardCheck,
      theme: 'blue'
    },

    scim: {
      title: 'Satellite Catalogue',
      description: 'Explore satellite metadata and review SCIM processing status.',
      icon: Activity,
      theme: 'purple'
    },

    crop: {
      title: 'Crop Intelligence',
      description: 'Calculate vegetation, water and moisture indices using validated inputs.',
      icon: Sprout,
      theme: 'orange'
    },

    agents: {
      title: 'AI Agents',
      description: 'Explore registered agents and authorized dedicated workflows.',
      icon: ShieldCheck,
      theme: 'teal'
    }

  };

  const roleName =
    ROLE_NAMES[role] ||
    (role ? role.replace(/_/g, ' ') : 'Guest');

  const profile = roleProfiles[role] || {
    label: 'Your workspace',
    description: 'Access the workspaces available to your account.',
    icon: LayoutDashboard
  };

  const ProfileIcon = profile.icon;

  if (!role) {
    return (
      <section className="role-dashboard">
        <h1>Welcome to AgriNexa AI</h1>
        <p>Please sign in to access your workspace.</p>
        <p>Farmer registration is available from the sign-in panel. Staff accounts must be provisioned by an administrator.</p>
      </section>
    );
  }

  return (

    <section className="unified-staff-dashboard">

      {/* Role-specific welcome card */}

      <div className="unified-welcome">

        <div className="unified-welcome-content">

          <span className="unified-welcome-label">
            <ProfileIcon size={19} aria-hidden="true" />
            {profile.label}
          </span>

          <h1>Welcome, {roleName}</h1>

          <p>{profile.description}</p>

        </div>

        <div className="unified-welcome-art" aria-hidden="true">
          <ProfileIcon size={88} strokeWidth={1.3} />
        </div>

      </div>

      {/* Permission-based account summary */}

      <div className="unified-summary-grid">

        <article className="unified-summary unified-summary-blue">

          <LayoutDashboard size={27} aria-hidden="true" />

          <strong>{workspaces.length}</strong>

          <span>Available workspaces</span>

          <small>Based on your account permissions</small>

        </article>

        <article className="unified-summary unified-summary-purple">

          <ShieldCheck size={27} aria-hidden="true" />

          <strong>{roleName}</strong>

          <span>Account role</span>

          <small>Role-based workspace access</small>

        </article>

      </div>

      {/* Authorized workspace cards */}

      <div className="unified-section-heading">

        <h2>Your workspaces</h2>

        <p>Select a workspace to continue.</p>

      </div>

      <div className="unified-module-grid">

        {workspaces.map(item => {

          const module = modules[item.id] || {
            title: item.label,
            description: WORKSPACES[item.id]?.description ||
              'View workspace details.',
            icon: WORKSPACES[item.id]?.icon || LayoutDashboard,
            theme: 'blue'
          };

          const Icon = module.icon;

          return (

            <article
              className="unified-module-card"
              key={item.id}
            >

              <span className={`unified-module-icon unified-icon-${module.theme}`}>

                <Icon
                  size={28}
                  strokeWidth={1.8}
                  aria-hidden="true"
                />

              </span>

              <h3>{module.title}</h3>

              <p>{module.description}</p>

              <button
                type="button"
                className="unified-module-button"
                onClick={() => onNavigate(item.id)}
                aria-label={`Open ${module.title}`}
              >

                Open workspace

                <ArrowRight
                  size={18}
                  aria-hidden="true"
                />

              </button>

            </article>

          );

        })}

      </div>

      {workspaces.length === 0 && (

        <div className="unified-empty" role="status">
          No workspaces are currently assigned to your account.
        </div>

      )}

      {/* Expandable operational information */}

      <details className="unified-operational">

        <summary>

          <ShieldCheck size={23} aria-hidden="true" />

          <span>Access and operational information</span>

        </summary>

        <div className="unified-operational-content">

          <p>
            Data access is controlled by account permissions
            and enforced by the backend API.
          </p>

          <p>
            Offline field evidence remains local until a
            verifier explicitly synchronizes it.
          </p>

          <p>
            Farmer land records are ownership-scoped.
            Satellite catalogue discovery provides metadata.
          </p>

          <p>
            Processing and dedicated AI workflows are subject
            to their existing backend capabilities and access
            restrictions. Registry metadata does not verify
            runtime readiness.
          </p>

          <p>
            Automatic AI learning and model training are disabled.
          </p>

        </div>

      </details>

    </section>

  );
}
