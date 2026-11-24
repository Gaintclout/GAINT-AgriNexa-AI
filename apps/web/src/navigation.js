
export const NAVIGATION = [
  {
    id: 'overview',
    label: 'Dashboard',
    roles: null
  },
  {
    id: 'parcels',
    label: 'Parcel Registry',
    roles: [
      'farmer',
      'field_verifier',
      'officer',
      'admin',
      'gis_operator',
      'ml_team'
    ]
  },
  {
    id: 'verification',
    label: 'Field Verification',
    roles: ['field_verifier']
  },
  {
    id: 'review',
    label: 'Officer Review',
    roles: ['officer', 'admin']
  },
  {
    id: 'scim',
    label: 'Satellite Catalogue / SCIM',
    roles: ['admin', 'gis_operator', 'ml_team']
  },
  {
    id: 'crop',
    label: 'Crop Intelligence',
    roles: ['admin', 'gis_operator', 'ml_team']
  },
  {
    id: 'agents',
    label: 'AI Agents',
    roles: ['admin', 'gis_operator', 'ml_team']
  }
];

const FARMER_LABELS = {
  overview: 'Home',
  parcels: 'My Land'
};

export function navigationForRole(role) {
  const allowedNavigation = NAVIGATION.filter(
    item =>
      item.roles === null ||
      item.roles.includes(role)
  );

  if (role === 'farmer') {
    return allowedNavigation.map(item => ({
      ...item,
      label: FARMER_LABELS[item.id] || item.label
    }));
  }

  return allowedNavigation;
}
