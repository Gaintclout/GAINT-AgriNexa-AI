import React from 'react';
import { Activity, ClipboardCheck, MapPinned, ShieldCheck, Sprout } from 'lucide-react';

const WORKSPACES = {
  parcels: { icon: MapPinned, description: 'View authorized parcel records and ownership-scoped data.' },
  verification: { icon: ShieldCheck, description: 'Capture field evidence offline and manage your sync queue.' },
  review: { icon: ClipboardCheck, description: 'Inspect submitted field evidence and record auditable decisions.' },
  scim: { icon: Activity, description: 'Discover satellite metadata and review SCIM processing status.' },
  crop: { icon: Sprout, description: 'Calculate spectral indices from validated reflectance inputs.' },
  agents: { icon: Activity, description: 'Inspect the agent identifiers published by the API and the missing governance controls.' }
};

export default function RoleDashboard({ role, navigation, onNavigate }) {
  const workspaces = navigation.filter(item => item.id !== 'overview');

  return (
    <section className="role-dashboard">
      <div className="dashboard-heading">
        <div>
          <span className="eyebrow">ROLE WORKSPACE</span>
          <h1>{role ? `${role.replace(/_/g, ' ')} workspace` : 'Welcome to AgriNexa AI'}</h1>
          <p>{role ? 'Choose an authorized workspace. Data access is enforced by the API for every request.' : 'Sign in to open the workspace assigned to your account, or register a farmer account.'}</p>
        </div>
      </div>
      {!role && <p className="dashboard-notice">Farmer registration is available from the sign-in panel. Staff accounts must be provisioned by an administrator.</p>}
      {role && workspaces.length === 0 && <p className="dashboard-notice">No workspaces are assigned to this role.</p>}
      {workspaces.length > 0 && (
        <div className="dashboard-grid">
          {workspaces.map(item => {
            const workspace = WORKSPACES[item.id];
            const Icon = workspace.icon;
            return (
              <button className="dashboard-card" key={item.id} type="button" onClick={() => onNavigate(item.id)}>
                <Icon size={24} aria-hidden="true" />
                <span className="dashboard-card-title">{item.label}</span>
                <span className="dashboard-card-description">{workspace.description}</span>
                <span className="dashboard-card-action">Open workspace</span>
              </button>
            );
          })}
        </div>
      )}
      <section className="dashboard-boundary" aria-labelledby="dashboard-boundary-title">
        <h2 id="dashboard-boundary-title">Operational boundaries</h2>
        <p>Offline field evidence remains local until a verifier explicitly synchronizes it. Farmer parcel reads are ownership-scoped. Satellite catalogue discovery returns metadata only; imagery processing and AI-agent execution are not represented as active services here.</p>
      </section>
    </section>
  );
}
